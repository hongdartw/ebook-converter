# eBook Converter (PDF/圖片 OCR 轉換器)

本專案提供一個強大的工具，使用 Google Gemini API 或 OpenAI 相容 API 將 PDF 檔案、圖片與電子書內容轉換為 Markdown 文字。它被設計用來無縫處理大型檔案、中斷續傳，並支援多種 AI 模型調用。

## 功能

- **支援 PDF 和圖片**: 將 PDF 檔案和獨立的圖片（JPG, JPEG, PNG）轉換為 Markdown。
- **中斷處理**: 自動儲存進度，並允許從上次成功處理的頁面恢復。
- **AI 策略**: 支援原生 Google Gemini API 以及 OpenAI 相容的第 3 方 API（如 Groq, DeepSeek, gpt-4o 等）。
- **重試機制**: 為處理每個頁面實作重試循環，以增強可靠性。
- **中文支援**: 包含將輸出文字從簡體中文轉換為繁體中文的功能。
- **暫存檔案管理**: 處理完成後清理暫存的圖片檔案。

## 專案結構

```
eBook-Converter/
│
├───input/                  # 用於輸入 PDF 和圖片檔案的資料夾
├───output/                 # 用於輸出 Markdown 檔案的資料夾
├───main.py                 # 執行 OCR 處理的主腳本
├───pdf_handler.py          # 處理 PDF 到圖片的轉換
├───ocr_processor.py        # 使用 AI API 處理圖片
├───requirements.txt        # Python 依賴套件
└───env.example             # 環境變數設定範例
```

## 如何使用

1.  **先決條件**:
    *   Python 3.x
    *   Google Gemini API 金鑰 或 OpenAI 相容 API 金鑰

2.  **安裝**:
    *   複製儲存庫：
        ```bash
        git clone https://github.com/hongdartw/ebook-converter.git
        cd ebook-converter
        ```
    *   安裝所需的 Python 套件：
        ```bash
        pip install -r requirements.txt
        ```

3.  **設定**:
    *   在專案根目錄中建立一個 `.env` 檔案。
    *   參考 `env.example` 設定您的 API 金鑰。您可以同時設定兩者，系統將優先使用 Gemini：
        ```env
        # Gemini API 設定
        GEMINI_API_KEY="您的 API 金鑰"
        GEMINI_MODEL="gemini-1.5-flash-latest"

        # OpenAI 或相容的第 3 方 API 設定
        OPENAI_API_KEY="您的 API 金鑰"
        OPENAI_API_URL="https://api.openai.com/v1"
        OPENAI_MODEL="gpt-4o"
        ```

4.  **執行 OCR**:
    *   將您的 PDF 或圖片檔案放入 `input` 資料夾。
    *   執行主腳本：
        ```bash
        python main.py
        ```
    *   腳本將處理每個檔案，並將輸出儲存為 Markdown 檔案在 `output` 資料夾中。

5.  **恢復中斷的會話**:
    *   如果腳本被中斷（例如，按下 `Ctrl+C` 或因錯誤），一個暫存檔案（`*_temp.md`）將被儲存在 `output` 資料夾中。
    *   當您再次執行腳本時，它會偵測到暫存檔案並詢問您是否要恢復。輸入 `y` 以從上次中斷的地方繼續。

## 主要元件

### `main.py`

協調整個流程的主腳本。它處理：
- 從 `.env` 檔案載入 AI 設定。
- 優先嘗試 Gemini，失敗時切換至 OpenAI 相容 API。
- 管理用於中斷處理的暫存進度檔案。
- 呼叫 `pdf_handler` 和 `ocr_processor` 模組。
- 將最終輸出從簡體中文轉換為繁體中文。

### `pdf_handler.py`

-   **`convert_pdf_to_images(pdf_path, output_folder)`**: 使用 `PyMuPDF` 將給定 PDF 檔案的每一頁轉換為 PNG 圖片。

### `ocr_processor.py`

-   **`process_image_with_gemini`**: 使用 Google 原生 SDK 進行 OCR。
-   **`process_image_with_openai`**: 使用 OpenAI SDK 對接相容介面（如 GPT-4o, Claude via Proxy 等）。

## 依賴套件

-   `google-generativeai`
-   `openai`
-   `python-dotenv`
-   `Pillow`
-   `PyMuPDF`
-   `opencc-python-reimplemented`

透過執行 `pip install -r requirements.txt` 來安裝所有依賴套件。
