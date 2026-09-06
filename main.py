import os
import shutil
import sys
from dotenv import load_dotenv
from pdf_handler import convert_pdf_to_images
from ocr_processor import process_image_with_gemini, process_image_with_openai
from opencc import OpenCC
from converters import (
    convert_epub,
    convert_mobi_family,
    convert_pdf_direct,
    convert_txt,
    convert_office,
    to_traditional_chinese,
    to_traditional_chinese_preserving_obsidian_embeds,
    markdown_images_to_obsidian,
    sanitize_filename
)

# --- 常數定義 ---
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
TEMP_IMAGE_FOLDER = "temp_images"

EBOOK_EXTENSIONS = (".epub", ".mobi", ".azw", ".azw3", ".txt")
OFFICE_EXTENSIONS = (".docx", ".xlsx")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
ALL_SUPPORTED_EXTENSIONS = EBOOK_EXTENSIONS + OFFICE_EXTENSIONS + IMAGE_EXTENSIONS + (".pdf",)
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

def process_file_ai_ocr(filename, output_format, config):
    """使用 AI Vision API (Gemini / OpenAI) 進行 OCR 處理。"""
    file_path = os.path.join(INPUT_FOLDER, filename)
    file_ext = os.path.splitext(filename)[1].lower()
    safe_base_name = sanitize_filename(os.path.splitext(filename)[0])
    temp_output_path = os.path.join(OUTPUT_FOLDER, f"{safe_base_name}_temp.md")

    image_paths = []
    full_markdown_content = []
    processed_pages = 0

    if not config["gemini"]["api_key"] and not config["openai_providers"]:
        print(f"錯誤：處理 {filename} 需要 AI API，但找不到任何 API 金鑰設定。")
        return False

    # 1. 準備圖片路徑
    if file_ext == ".pdf":
        print(f"\n--- 正在透過 AI OCR 處理 PDF 檔案: {filename} ---")
        image_paths = convert_pdf_to_images(file_path, TEMP_IMAGE_FOLDER)
    elif file_ext in IMAGE_EXTENSIONS:
        print(f"\n--- 正在透過 AI OCR 處理圖片檔案: {filename} ---")
        image_paths.append(file_path)

    if not image_paths:
        print(f"檔案 {filename} 未能成功擷取頁面圖片。")
        return True

    # 2. 檢查並處理暫存檔案
    if os.path.exists(temp_output_path):
        while True:
            choice = input(f"找到檔案 '{filename}' 的暫存進度，要繼續嗎？ (y/n): ").strip().lower()
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

        # 4. 處理完成並儲存
        if full_markdown_content:
            out_ext = ".md" if output_format.lower() == "md" else ".txt"
            output_filename = f"{safe_base_name}{out_ext}"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            sep = "\n\n---\n\n" if output_format.lower() == "md" else "\n\n"
            combined_content = sep.join(full_markdown_content)
            if output_format.lower() == "md":
                combined_content = markdown_images_to_obsidian(combined_content)
                final_content = to_traditional_chinese_preserving_obsidian_embeds(combined_content)
            else:
                final_content = to_traditional_chinese(combined_content)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            print(f"\n[成功] 已將結果儲存至: {output_path}")
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        else:
            print(f"檔案 {filename} 未能產生任何有效內容。")

    except KeyboardInterrupt:
        print("\n使用者中斷操作。")
        save_progress(temp_output_path, full_markdown_content)
        return False

    return True

def ask_user_options(has_pdf: bool):
    """提供互動式選單詢問使用者輸出格式與 PDF 處理模式。"""
    print("\n" + "=" * 55)
    print("                eBook Converter 選單")
    print("=" * 55)
    print("請選擇輸出格式 (Output Format)：")
    print("  [1] Markdown (.md) - 保留標題結構，圖片存放於子資料夾")
    print("  [2] 純文字 Text (.txt) - 純文字提取，無格式標記")
    
    while True:
        choice = input("\n請輸入選項 [1 或 2，預設 1]: ").strip()
        if choice in ["", "1"]:
            output_format = "md"
            break
        elif choice == "2":
            output_format = "txt"
            break
        else:
            print("輸入無效，請輸入 1 或 2。")

    pdf_mode = "direct"
    if has_pdf:
        print("\n偵測到 input 資料夾中包含 PDF 檔案，請選擇 PDF 處理模式：")
        print("  [1] 直接文字提取 (Direct Extract) - 快速、不需 AI，適用於數位文字版 PDF/電子書")
        print("  [2] AI 視覺 OCR (AI Vision OCR)  - 需 API 金鑰，適用於掃描件、圖片版 PDF")
        
        while True:
            pdf_choice = input("\n請輸入 PDF 處理選項 [1 或 2，預設 1]: ").strip()
            if pdf_choice in ["", "1"]:
                pdf_mode = "direct"
                break
            elif pdf_choice == "2":
                pdf_mode = "ocr"
                break
            else:
                print("輸入無效，請輸入 1 或 2。")

    print("=" * 55 + "\n")
    return output_format, pdf_mode

def main():
    """主執行函式"""
    load_dotenv()
    config = get_config()

    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"已建立 '{INPUT_FOLDER}' 資料夾，請放入待轉換檔案後重新執行。")
        return
        
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    if os.path.exists(TEMP_IMAGE_FOLDER):
        shutil.rmtree(TEMP_IMAGE_FOLDER)
    os.makedirs(TEMP_IMAGE_FOLDER)

    print("=======================================================")
    print("       eBook Converter - 電子書與文件多格式轉換工具       ")
    print("=======================================================")
    print(f"支援格式: EPUB, MOBI, AZW, AZW3, PDF, TXT, DOCX, XLSX, JPG, PNG")
    print(f"繁簡轉換: 輸出全自動轉換為台灣常用繁體中文 (s2twp)")

    # 檢查 input 檔案
    all_files = [f for f in os.listdir(INPUT_FOLDER) if os.path.isfile(os.path.join(INPUT_FOLDER, f))]
    valid_files = [f for f in all_files if os.path.splitext(f)[1].lower() in ALL_SUPPORTED_EXTENSIONS]

    if not valid_files:
        print(f"\n[提示] '{INPUT_FOLDER}' 資料夾中沒有找到支援的檔案。")
        print(f"請將 EPUB, MOBI, AZW3, PDF, TXT 或 圖片檔放入 '{INPUT_FOLDER}' 後再試。")
        return

    has_pdf = any(os.path.splitext(f)[1].lower() == ".pdf" for f in valid_files)
    output_format, pdf_mode = ask_user_options(has_pdf)

    print(f"即將開始處理 {len(valid_files)} 個檔案...")
    print(f"目標格式: {output_format.upper()} | PDF 模式: {'AI 視覺 OCR' if pdf_mode == 'ocr' else '直接快速提取'}\n")

    success_count = 0
    fail_count = 0

    try:
        for filename in valid_files:
            file_path = os.path.join(INPUT_FOLDER, filename)
            ext = os.path.splitext(filename)[1].lower()
            print(f"\n>> 正在處理: {filename}")

            try:
                # 1. EPUB
                if ext == ".epub":
                    out_path = convert_epub(file_path, output_format, OUTPUT_FOLDER)
                    print(f"  [完成] 輸出至: {out_path}")
                    success_count += 1

                # 2. MOBI / AZW / AZW3
                elif ext in [".mobi", ".azw", ".azw3"]:
                    out_path = convert_mobi_family(file_path, output_format, OUTPUT_FOLDER)
                    print(f"  [完成] 輸出至: {out_path}")
                    success_count += 1

                # 3. TXT
                elif ext == ".txt":
                    out_path = convert_txt(file_path, output_format, OUTPUT_FOLDER)
                    print(f"  [完成] 輸出至: {out_path}")
                    success_count += 1

                # 4. Microsoft Office 文件 -> 透過 officecli 擷取文字
                elif ext in OFFICE_EXTENSIONS:
                    out_path = convert_office(file_path, output_format, OUTPUT_FOLDER)
                    print(f"  [完成] officecli 輸出至: {out_path}")
                    success_count += 1

                # 5. PDF
                elif ext == ".pdf":
                    if pdf_mode == "ocr":
                        ok = process_file_ai_ocr(filename, output_format, config)
                        if ok:
                            success_count += 1
                        else:
                            fail_count += 1
                            break
                    else:
                        out_path = convert_pdf_direct(file_path, output_format, OUTPUT_FOLDER)
                        print(f"  [完成] 輸出至: {out_path}")
                        success_count += 1

                # 6. 獨立圖片 (JPG, PNG 等) -> 走 AI OCR
                elif ext in IMAGE_EXTENSIONS:
                    ok = process_file_ai_ocr(filename, output_format, config)
                    if ok:
                        success_count += 1
                    else:
                        fail_count += 1
                        break

            except Exception as e:
                print(f"  [錯誤] 處理 {filename} 時發生異常: {e}")
                fail_count += 1

        print("\n" + "=" * 55)
        print(f"處理結束！ 成功: {success_count} 個, 失敗/中斷: {fail_count} 個")
        print(f"轉換成果已存放於: {os.path.abspath(OUTPUT_FOLDER)}")
        print("=" * 55)

    finally:
        if os.path.exists(TEMP_IMAGE_FOLDER):
            shutil.rmtree(TEMP_IMAGE_FOLDER, ignore_errors=True)

if __name__ == "__main__":
    main()
