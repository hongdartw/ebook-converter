# AGENTS.md

This file provides guidance to AGENT Code (AGENT.ai/code) when working with code in this repository.

## Project Overview

eBook Converter — a Python CLI tool that converts eBooks and documents (EPUB, MOBI, AZW, AZW3, PDF, TXT, images) into Traditional Chinese Markdown or Plain Text. It supports both direct fast parsing (no AI) and AI Vision OCR (Google Gemini primary, OpenAI-compatible fallback).

## Setup & Running

```bash
pip install -r requirements.txt
cp env.example .env          # optional, only needed if using AI OCR
python main.py
```

Entry point is `main.py::main()`.

## Architecture

- `main.py` — CLI interactive menu, routing, batch orchestration, interrupt recovery.
- `converters/` — Direct non-AI document & eBook parsing:
  - `epub_converter.py`: EPUB chapter & image parsing via `ebooklib` + `markdownify`
  - `mobi_converter.py`: MOBI / AZW / AZW3 unpacker via `mobi`
  - `pdf_direct.py`: Fast PDF text & embedded image extraction via `PyMuPDF`
  - `txt_converter.py`: Multi-encoding auto-detection via `charset-normalizer`
  - `base.py`: Common helpers for OpenCC `s2twp`, HTML to MD/Text, filename sanitization
- `ocr_processor.py` — Gemini and OpenAI vision API OCR for scanned PDFs & standalone images.
- `pdf_handler.py` — PyMuPDF PDF→PNG page extraction into `temp_images/` for AI OCR.

## Output & Image Handling

- **Markdown (`.md`)**: Preserves heading hierarchy; extracted images are stored in `output/<filename>_images/` and referenced relatively in Markdown.
- **Plain Text (`.txt`)**: Clean text without markup tags.
- **Traditional Chinese**: All extracted text is converted via OpenCC (`s2twp` mode) to standard Taiwan Traditional Chinese phrases and characters.
