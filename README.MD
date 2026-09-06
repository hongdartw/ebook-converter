# eBook Converter (多格式電子書與文件轉換器)

本專案提供一個強大的電子書與文件轉換工具，支援多種常見電子書格式（EPUB、MOBI、AZW3/AZW、TXT、PDF）以及 Microsoft Office 文件，並提供 **直接快速轉換（不需 AI）**、**officecli 文件擷取** 與 **AI 視覺 OCR（Gemini & OpenAI 相容 API）** 三種處理模式。所有輸出內容均自動轉換為台灣慣用繁體中文。

## 主要功能

- **多種輸入格式支援**：
  - **電子書與文字檔**：`EPUB`、`MOBI`、`AZW`、`AZW3`、`TXT`（自動辨識編碼，不需消耗 AI API）。
  - **PDF 雙模式**：
    - **快速文字提取**：直接解析數位文字版 PDF 與嵌入圖片（不需 AI，秒級轉換）。
    - **AI 視覺 OCR**：針對掃描件或純圖片 PDF 呼叫 AI Vision 模型識別。
  - **Microsoft Office 文件**：支援 `DOCX`、`XLSX`，透過本機 `officecli view ... text` 擷取內容；請先安裝並確認 `officecli` 在 PATH 中。
  - **獨立圖片 OCR**：支援 `JPG`、`JPEG`、`PNG`、`WEBP`、`BMP` 圖片 OCR。
- **靈活的輸出格式（互動式選單）**：
  - **Markdown (`.md`)**：保留標題、章節與表格結構；若文件含有圖片，自動抽取並存入專屬子資料夾（如 `output/<檔名>_images/`）且自動於 Markdown 中相對引用。
  - **純文字 Text (`.txt`)**：抽取純文字內容，去除格式標記。
- **台灣繁體中文相容**：全自動透過 OpenCC (`s2twp`) 將輸出文字轉換為台灣慣用字與詞彙。
- **中斷續傳與錯誤重試**：AI OCR 模式支援頁面暫存（`*_temp.md`）與多輪嘗試機制。

## 專案結構

```
eBook-Converter/
│
├───input/                  # 放置待轉換的電子書、PDF 與圖片檔案
├───output/                 # 輸出目錄 (Markdown, TXT 與圖片子目錄)
├───converters/             # 各格式非 AI 直接解析模組
│   ├── base.py             # 繁簡轉換、HTML2MD、編碼與檔案工具
│   ├── epub_converter.py   # EPUB 解析器
│   ├── mobi_converter.py   # MOBI / AZW / AZW3 解析器
│   ├── pdf_direct.py       # PDF 直接文字與圖片提取
│   └── txt_converter.py    # TXT 多編碼偵測與轉換
├───main.py                 # 主程式 (互動選單與批次轉換調度)
├───pdf_handler.py          # PDF 轉圖檔模組 (供 AI OCR 使用)
├───ocr_processor.py        # AI 視覺 OCR 模組 (Gemini / OpenAI)
├───requirements.txt        # Python 依賴套件清單
└───env.example             # 環境變數設定範例
```

## 如何使用

### 1. 安裝環境與套件
```bash
# 建議先啟用虛擬環境
python -m venv venv
.\.venv\Scripts\Activate.ps1   # (Windows PowerShell)

# 安裝依賴套件
pip install -r requirements.txt
```

### 2. 設定 API 金鑰（僅使用 AI OCR 模式時需要）
若需使用 AI OCR 功能處理掃描件 PDF 或圖片，請建立 `.env` 檔案並填入金鑰：
```env
# Gemini API 設定 (優先使用)
GEMINI_API_KEY="your_gemini_api_key"
GEMINI_MODEL="gemini-1.5-flash-latest"

# OpenAI 或相容的第 3 方 API 設定
OPENAI_API_KEY="your_openai_api_key"
OPENAI_API_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o"
```
*(若只轉換一般 EPUB、MOBI、AZW3、TXT 或文字型 PDF，則不需配置 API 金鑰即可直接使用)*

### 3. 執行轉換
1. 將欲轉換的檔案放入 `input/` 資料夾。
2. 執行主程式：
   ```bash
   python main.py
   ```
3. 根據終端機上的互動選單進行選擇：
   - 選擇輸出格式（`1: Markdown` 或 `2: Text`）
   - 若有 PDF 檔案，選擇處理模式（`1: 直接文字提取` 或 `2: AI 視覺 OCR`）
4. 轉換完成後，成果將輸出至 `output/` 資料夾中。

## 依賴套件
- `google-generativeai` & `openai`：AI 視覺 OCR
- `PyMuPDF (fitz)`：PDF 解析與圖檔提取
- `EbookLib` & `mobi`：EPUB、MOBI、AZW3 電子書解析
- `beautifulsoup4` & `markdownify`：HTML/XML 結構清理與 Markdown 轉換
- `opencc-python-reimplemented`：繁簡中文轉換 (s2twp)
- `charset-normalizer` & `Pillow`：編碼辨識與影像處理
