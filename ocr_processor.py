import os
from PIL import Image
import time
from openai import OpenAI
import base64
import io

GEMINI_MODEL_NOT_FOUND = "__GEMINI_MODEL_NOT_FOUND__"

def _is_gemini_model_not_found(error_text: str) -> bool:
    """判斷 Gemini 錯誤是否為模型不存在/不支援，這類錯誤不應每頁重試。"""
    lowered = (error_text or "").lower()
    return "404" in lowered and ("not_found" in lowered or "is not found" in lowered or "not found" in lowered)


def process_image_with_gemini(image_path, api_key, model_name):
    """
    對單張圖片進行 Gemini OCR 處理。
    相容最新的 google-genai SDK 與傳統的 google-generativeai SDK。
    """
    if not model_name:
        print("Gemini 未設定模型，跳過 Gemini 原生 API。")
        return None

    prompt = "你是一個專業的 OCR 引擎。請將這張圖片中的所有內容，包含標題、段落、列表和表格，轉換為結構良好、語法正確的 Markdown 格式。請盡力還原原始的排版結構。"
    
    # 優先嘗試新的 google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        with Image.open(image_path) as img:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, img]
            )
        if response.text:
            print(f"成功使用 Gemini 處理圖片 {image_path}。")
            return response.text
        else:
            print(f"處理圖片 {image_path} 後，Gemini 未回傳有效內容。")
            return ""
    except ImportError:
        pass
    except Exception as e:
        err_msg = str(e)
        if _is_gemini_model_not_found(err_msg):
            print(f"Gemini 模型不存在或不支援 generateContent：{model_name}，本次批次將停用 Gemini 並改用備援 API。")
            return GEMINI_MODEL_NOT_FOUND
        if "response.text" in err_msg or "Candidate" in err_msg:
            print(f"Gemini API 處理圖片 {image_path} 時被阻擋或未回傳文字。")
        else:
            print(f"呼叫 Gemini API (google-genai) 處理圖片 {image_path} 時發生錯誤: {e}")
        return None

    # 次選嘗試舊版 google-generativeai SDK
    try:
        import google.generativeai as genai_legacy
        genai_legacy.configure(api_key=api_key)
        model = genai_legacy.GenerativeModel(model_name)
        with Image.open(image_path) as img:
            response = model.generate_content([prompt, img])
        if response.text:
            print(f"成功使用 Gemini 處理圖片 {image_path}。")
            return response.text
        else:
            print(f"處理圖片 {image_path} 後，Gemini 未回傳有效內容。")
            return ""
    except ImportError:
        print("錯誤：找不到 google-genai 或 google-generativeai 套件，請執行 pip install google-genai")
        return None
    except Exception as e:
        err_msg = str(e)
        if _is_gemini_model_not_found(err_msg):
            print(f"Gemini 模型不存在或不支援 generateContent：{model_name}，本次批次將停用 Gemini 並改用備援 API。")
            return GEMINI_MODEL_NOT_FOUND
        if "response.text" in err_msg or "Candidate" in err_msg:
            print(f"Gemini API 處理圖片 {image_path} 時被阻擋或未回傳文字。")
        else:
            print(f"呼叫 Gemini API 處理圖片 {image_path} 時發生錯誤: {e}")
        return None

def process_image_with_openai(image_path, api_key, base_url, model_name):
    """
    使用 OpenAI 相容 API 對單張圖片進行 OCR。
    """
    try:
        if not base_url:
            print(f"警告：未提供 base_url，將使用預設 OpenAI URL。")
        
        print(f"  [Debug] 正在呼叫 OpenAI API: model={model_name}, url={base_url}")
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        prompt = "你是一個專業的 OCR 引擎。請將這張圖片中的所有內容，包含標題、段落、列表和表格，轉換為結構良好、語法正確的 Markdown 格式。請盡力還原原始的排版結構。"
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                    ],
                }
            ],
            max_tokens=4096,
        )

        markdown_text = response.choices[0].message.content
        print(f"成功使用 OpenAI 相容 API 處理圖片 {image_path}。")
        return markdown_text

    except Exception as e:
        err_str = str(e)
        if "<html" in err_str.lower() or "<!doctype" in err_str.lower():
            print(f"呼叫 OpenAI 相容 API 處理圖片 {image_path} 時發生錯誤: 伺服器回傳 HTML 頁面 (可能被防火牆/Cloudflare 封鎖，請確認 API URL 是否正確)")
        else:
            print(f"呼叫 OpenAI 相容 API 處理圖片 {image_path} 時發生錯誤: {err_str[:300]}")
        return None
