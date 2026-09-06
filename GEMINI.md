# eBook Converter (多格式電子書與文件轉換器)

## 專案概述
本專案是一個基於 Python 的電子書與文件多格式轉換工具，支援 EPUB、MOBI、AZW3/AZW、TXT、PDF 以及掃描圖片格式。系統提供雙軌轉換機制：
1. **直接數位轉換（不需 AI）**：適用於 EPUB、MOBI、AZW3、TXT 及文字型 PDF，快速提取章節結構、內嵌圖片與文字。
2. **AI 視覺 OCR**：結合 Google Gemini 與 OpenAI 相容的多模態 API，處理掃描版 PDF 及純圖片檔。

所有輸出文字均自動通過 OpenCC（`s2twp`）轉換為台灣習慣的繁體中文詞彙與字形。

### 核心模組架構
- `main.py`：互動選單控制、格式分流與處理調度。
- `converters/`：非 AI 直接解析模組（EPUB、MOBI/AZW3、PDF 直接提取、TXT 偵測）。
- `ocr_processor.py`：Gemini 與 OpenAI Vision API 封裝。
- `pdf_handler.py`：PDF 頁面轉圖檔工具（用於 AI OCR）。
- `input/`：輸入目錄。
- `output/`：輸出目錄（含圖片子資料夾如 `<書名>_images/`）。

## 環境設定與執行

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 配置環境變數（可選，僅 AI OCR 需要）
參考 `env.example` 建立 `.env`：
```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

OPENAI_API_KEY=your_openai_api_key
OPENAI_API_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### 3. 執行程式
將檔案放入 `input/` 目錄後執行：
```bash
python main.py
```
依照畫面選單選擇輸出格式（Markdown 或 TXT）與 PDF 處理模式（直接文字提取 或 AI OCR）。
