import os
import shutil
import sys
from dotenv import load_dotenv
from pdf_handler import convert_pdf_to_images
from ocr_processor import process_image_with_gemini, process_image_with_openai
from opencc import OpenCC

# --- 常數定義 ---
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_IMAGE_FOLDER = "temp_images"
SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
MAX_RETRY_ROUNDS = 3

# --- 初始化 OpenCC ---
cc = OpenCC('s2twp')

def get_config():
    """從環境變數中讀取 AI 設定。"""
    openai_providers = []

    if os.getenv("OPENAI_API_KEY"):
        openai_providers.append({
            "name": "OpenAI",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_API_URL"),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        })

    i = 1
    while True:
        key = os.getenv(f"PROXY_{i}_API_KEY")
        if not key:
            break
        openai_providers.append({
            "name": f"Proxy {i} ({os.getenv(f'PROXY_{i}_MODEL', 'unknown')})",
            "api_key": key,
            "base_url": os.getenv(f"PROXY_{i}_API_URL"),
            "model": os.getenv(f"PROXY_{i}_MODEL", "gpt-4o"),
        })
        i += 1

    config = {
        "gemini": {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest"),
        },
        "openai_providers": openai_providers,
    }
    return config

def save_progress(temp_path, content_list):
    """將目前的進度儲存到暫存檔案。"""
    if not content_list:
        return
    print(f"\n正在儲存進度到 {temp_path}...")
    try:
        full_content = "\n\n---\n\n".join(content_list)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        print("進度儲存成功。")
    except IOError as e:
        print(f"錯誤：無法寫入暫存檔案 {temp_path}: {e}")

def process_file(filename, config):
    """處理單一檔案 (PDF 或圖片) 的完整流程。"""
    file_path = os.path.join(INPUT_FOLDER, filename)
    file_ext = os.path.splitext(filename)[1].lower()
    output_filename_base = os.path.splitext(filename)[0]
    temp_output_path = os.path.join(OUTPUT_FOLDER, f"{output_filename_base}_temp.md")

    image_paths = []
    full_markdown_content = []
    processed_pages = 0

    # 1. 準備圖片路徑
    if file_ext == ".pdf":
        print(f"\n--- 正在處理 PDF 檔案: {file_path} ---")
        image_paths = convert_pdf_to_images(file_path, TEMP_IMAGE_FOLDER)
    elif file_ext in SUPPORTED_IMAGE_EXTENSIONS:
        print(f"\n--- 正在處理圖片檔案: {file_path} ---")
        image_paths.append(file_path)
    else:
        return True # 不是支援的檔案，直接跳過

    if not image_paths:
        print(f"檔案 {filename} 未能成功轉換或不是支援的格式。")
        return True

    # 2. 檢查並處理暫存檔案
    if os.path.exists(temp_output_path):
        while True:
            choice = input(f"找到檔案 '{filename}' 的暫存進度，要繼續嗎？ (y/n): ").lower()
            if choice in ['y', 'yes']:
                print(f"正在從 {temp_output_path} 載入進度...")
                with open(temp_output_path, "r", encoding="utf-8") as f:
                    loaded_content = f.read()
                    if loaded_content:
                        full_markdown_content.append(loaded_content)
                        processed_pages = loaded_content.count("\n\n---\n\n") + 1
                print(f"已載入 {processed_pages} 頁的進度。")
                break
            elif choice in ['n', 'no']:
                print("將忽略暫存檔案，從頭開始處理。")
                processed_pages = 0
                full_markdown_content = []
                break
            else:
                print("無效的輸入，請輸入 'y' 或 'n'。")

    # 3. 核心 OCR 處理迴圈
    try:
        for i, image_path in enumerate(image_paths):
            if i < processed_pages:
                print(f"跳過已處理的頁面 {i + 1}/{len(image_paths)}")
                continue

            print(f"--- 開始處理頁面 {i + 1}/{len(image_paths)} ---")
            markdown_part = None
            page_processed = False

            for round_num in range(MAX_RETRY_ROUNDS):
                print(f"第 {round_num + 1}/{MAX_RETRY_ROUNDS} 輪嘗試...")
                
                # 優先嘗試 Gemini
                if config["gemini"]["api_key"]:
                    print(f"  嘗試使用 Gemini: {config['gemini']['model']}")
                    markdown_part = process_image_with_gemini(
                        image_path,
                        config["gemini"]["api_key"],
                        config["gemini"]["model"]
                    )
                    if markdown_part:
                        full_markdown_content.append(markdown_part)
                        page_processed = True
                        break

                # 依序嘗試所有 OpenAI 相容 API (含 Proxy)
                for provider in config["openai_providers"]:
                    print(f"  嘗試使用 {provider['name']}: {provider['model']}")
                    markdown_part = process_image_with_openai(
                        image_path,
                        provider["api_key"],
                        provider["base_url"],
                        provider["model"]
                    )
                    if markdown_part:
                        full_markdown_content.append(markdown_part)
                        page_processed = True
                        break

                if page_processed:
                    break

            if not page_processed:
                print(f"\n!!! 嚴重錯誤：頁面 {i + 1} ({os.path.basename(image_path)}) 處理失敗。")
                save_progress(temp_output_path, full_markdown_content)
                print("程式將終止。請檢查您的網路連線或 API 設定。")
                return False

        # 4. 處理完成
        if full_markdown_content:
            output_filename = f"{output_filename_base}.md"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            combined_markdown = "\n\n---\n\n".join(full_markdown_content)
            final_markdown_content = cc.convert(combined_markdown)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_markdown_content)

            print(f"\n成功將結果儲存至 {output_path}")
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        else:
            print(f"檔案 {filename} 未能產生任何有效的 Markdown 內容。")

    except KeyboardInterrupt:
        print("\n使用者中斷操作。")
        save_progress(temp_output_path, full_markdown_content)
        return False

    return True

def main():
    """主執行函式"""
    load_dotenv()
    config = get_config()

    if not config["gemini"]["api_key"] and not config["openai_providers"]:
        print("錯誤：找不到任何 API 設定。請確保您的 .env 檔案已正確設定。")
        return

    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"已建立 '{INPUT_FOLDER}' 資料夾，請放入檔案。")
        return
        
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    if os.path.exists(TEMP_IMAGE_FOLDER):
        shutil.rmtree(TEMP_IMAGE_FOLDER)
    os.makedirs(TEMP_IMAGE_FOLDER)

    print("--- eBook Converter (PDF/圖片 OCR 處理程式 - Gemini & OpenAI 相容版) ---")

    try:
        files_to_process = [f for f in os.listdir(INPUT_FOLDER) if os.path.isfile(os.path.join(INPUT_FOLDER, f))]
        for filename in files_to_process:
            if not process_file(filename, config):
                break
        else:
            print("\n--- 所有檔案處理完畢 ---")
    finally:
        if os.path.exists(TEMP_IMAGE_FOLDER):
            shutil.rmtree(TEMP_IMAGE_FOLDER)


if __name__ == "__main__":
    main()
