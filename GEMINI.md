# eBook Converter (PDF/圖片 OCR 轉換器)

## 專案概述
本專案是一個基於 Python 的工具，用於將 PDF 檔案、圖片與電子書內容轉換為高品質的 Markdown 格式。它結合了 Google Gemini 的多模態能力與 OpenAI 相容介面的靈活性，支援大規模文件處理、中斷續傳，並能自動將結果轉換為繁體中文。

### 核心技術
- **Python 3.x**
- **Google Generative AI SDK**: 用於原生 Gemini API 調用。
- **OpenAI SDK**: 用於所有 OpenAI 相容的第 3 方 API。
- **PyMuPDF (fitz)**: 用於高效的 PDF 解析與圖片轉換。
- **OpenCC**: 用於簡繁中文轉換（s2twp 模式）。
- **Pillow**: 圖片處理與 Base64 編碼。

## 環境設定與執行

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 配置環境變數
建立 `.env` 檔案，參考 `env.example`：
```env
# Gemini API 設定
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash-latest

# OpenAI 或相容的第 3 方 API 設定
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_URL=https://yourai.com/v1
OPENAI_MODEL=gpt-4o
```

### 3. 執行程式
將檔案放入 `input/` 目錄後執行：
```bash
python main.py
```

## AI 調用策略
為了符合合規性並提高可用性，本專案採用以下策略：
1. **單一 Key 原則**：不再使用多金鑰輪詢機制，避免觸發 Google 的濫用檢測。
2. **優先權順序**：
   - 系統首先嘗試使用 `GEMINI_API_KEY`（若已設定）。
   - 若 Gemini 調用失敗或未設定，則嘗試使用 `OPENAI_API_KEY` 與指定的 `OPENAI_API_URL`。
3. **錯誤重試**：每張圖片/頁面最多重試 3 次。

## 開發慣例
- **中斷續傳**：處理過程中會生成 `*_temp.md` 檔案，中斷後重啟可選擇恢復進度。
- **繁體化**：所有輸出預設通過 OpenCC 轉換為台灣慣用繁體中文。
- **自動清理**：處理結束後會自動刪除 `temp_images/` 下的臨時圖檔。

## 專案結構
- `main.py`: 流程控制與環境變數管理。
- `ocr_processor.py`: 封裝 Gemini 與 OpenAI 的影像處理邏輯。
- `pdf_handler.py`: 負責 PDF 轉圖檔。
- `input/`: 輸入目錄。
- `output/`: 輸出目錄。
