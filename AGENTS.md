# AGENTS.md

This file provides guidance to AGENT Code (AGENT.ai/code) when working with code in this repository.

## Project Overview

eBook Converter (PDF/Image OCR Processor) — a Python CLI tool that converts PDFs, images, and eBooks into Traditional Chinese Markdown using AI vision APIs (Google Gemini primary, OpenAI-compatible fallback).

## Setup & Running

```bash
pip install -r requirements.txt
cp env.example .env          # then fill in API keys
python main.py
```

No build step. No test suite. Entry point is `main.py::main()`.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini (first priority) | — |
| `GEMINI_MODEL` | Gemini model name | `gemini-1.5-flash-latest` |
| `OPENAI_API_KEY` | OpenAI-compatible endpoint | — |
| `OPENAI_API_URL` | Custom base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model name | `gpt-4o` |
| `PROXY_N_API_KEY` | Nth extra proxy key (N=1,2,3…) | — |
| `PROXY_N_API_URL` | Nth proxy base URL | — |
| `PROXY_N_MODEL` | Nth proxy model name | `gpt-4o` |

At least one of `GEMINI_API_KEY` or `OPENAI_API_KEY` (or any `PROXY_N_API_KEY`) must be set.

## Architecture

Three-module pipeline:

```
main.py          — orchestration, interrupt recovery, OpenCC s2twp conversion
pdf_handler.py   — PyMuPDF PDF→PNG page extraction into temp_images/
ocr_processor.py — Gemini and OpenAI vision API calls, returns markdown text
```

**Data flow:** `input/*.{pdf,jpg,png}` → per-page images in `temp_images/` → AI OCR per page → concatenated markdown with `---` separators → Traditional Chinese conversion → `output/*.md` → temp cleanup.

**Interrupt recovery:** On failure/KeyboardInterrupt, progress is saved to `*_temp.md`. On next run, user is prompted to resume or restart.

**API priority:** Per page, tries Gemini first (if configured), then iterates through all OpenAI-compatible providers in order (`OPENAI_*` → `PROXY_1_*` → `PROXY_2_*` …). Each page retries the full chain up to `MAX_RETRY_ROUNDS = 3` times before failing.

## Key Behaviors

- `input/`, `output/`, and `temp_images/` are created automatically if missing.
- `temp_images/` is wiped at startup and cleaned at completion.
- Both PDF pages and standalone images (`.jpg`, `.jpeg`, `.png`) are processed.
- All output text is converted from Simplified to Traditional Chinese via OpenCC (`s2twp` mode).
