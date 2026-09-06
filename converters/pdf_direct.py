import os
import re
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from .base import to_traditional_chinese, sanitize_filename, clean_xml_artifacts


def _join_pdf_wrapped_lines(lines):
    """合併同一 PDF 文字區塊中因頁面寬度產生的換行。"""
    merged = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 標題必須保留獨立一行；一般內文則視為同一段落的自動換行。
        if line.startswith("#") or current.startswith("#"):
            if current:
                merged.append(current)
            current = line
        else:
            # 英數字跨行時補回單字間距；中文則不插入空格。
            separator = " " if current and re.search(r"[A-Za-z]$", current) and re.match(r"[A-Za-z0-9]", line) else ""
            current += separator + line
    if current:
        merged.append(current)
    return merged

def _pdf_block_gap(box, previous_box):
    """取得相鄰文字區塊間距，兼容橫排與直排 PDF。"""
    if not previous_box:
        return 9999
    # 直排文字通常是窄而高的區塊，欄位方向在 X 軸。
    vertical = (box[3] - box[1]) > (box[2] - box[0]) * 3
    return box[0] - previous_box[2] if vertical else box[1] - previous_box[3]


def _merge_overlapping_short_lines(lines):
    """
    合併 PyMuPDF 對部分直排標題產生的重疊短行。

    有些直排中文字型會被提取為滑動片段，例如：
    「序」「序一」「一」或「經」「經方」「方實」「實踐」「踐」。
    這不是三/五個標題，而是同一個直排標題；用相鄰片段的最大重疊還原。
    """
    if len(lines) < 2:
        return lines
    texts = [line.get("text", "").strip() for line in lines]
    if not texts or any(not text for text in texts):
        return lines
    # 僅處理短標題片段，避免誤合併內文。
    if any(len(text) > 4 for text in texts):
        return lines

    merged = texts[0]
    for text in texts[1:]:
        max_overlap = min(len(merged), len(text))
        overlap = 0
        for size in range(max_overlap, 0, -1):
            if merged.endswith(text[:size]):
                overlap = size
                break
        merged += text[overlap:]

    # 若沒有任何合併效果，維持原狀。
    if merged == "".join(texts):
        return lines

    first = lines[0]
    return [{
        "text": merged,
        "max_size": max(line.get("max_size", 0.0) for line in lines),
        "is_bold": any(line.get("is_bold", False) for line in lines),
        "bbox": first.get("bbox"),
    }]


_SENTENCE_END_PUNCTUATION = set(",，.。!！?？;；:：、…‥」』）)〕］】》〉』\"'”’—")
_CLOSING_PUNCTUATION = set("」』）)〕］】》〉\"'”’")


def _last_sentence_char(text):
    """取得文字尾端用於判斷句子是否結束的字元，忽略右引號/括號。"""
    stripped = text.rstrip()
    if not stripped:
        return ""
    idx = len(stripped) - 1
    while idx >= 0 and stripped[idx] in _CLOSING_PUNCTUATION:
        idx -= 1
    return stripped[idx] if idx >= 0 else stripped[-1]


def _first_content_line(text):
    """取得下一頁第一個非空行，用來避免把標題、圖片接到前一頁內文。"""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _should_join_page_boundary(previous_text, next_text):
    """若前一頁最後一字不是標點，判定下一頁首段是跨頁續文並直接接續。"""
    first_next_line = _first_content_line(next_text)
    if not first_next_line or first_next_line.startswith(("#", "![", "<")):
        return False

    last_previous_line = _first_content_line("\n".join(reversed(previous_text.splitlines())))
    if last_previous_line.startswith(("#", "![", "<")):
        return False

    last_char = _last_sentence_char(previous_text)
    return bool(last_char and last_char not in _SENTENCE_END_PUNCTUATION)


def _combine_page_contents(page_contents):
    """合併頁面內容：移除換頁分隔線，必要時把跨頁斷句直接接續。"""
    if not page_contents:
        return ""
    combined = page_contents[0].strip()
    for page_text in page_contents[1:]:
        page_text = page_text.strip()
        if not page_text:
            continue
        if _should_join_page_boundary(combined, page_text):
            combined = combined.rstrip() + page_text.lstrip()
        else:
            combined = combined.rstrip() + "\n\n" + page_text.lstrip()
    return combined


def _merge_pdf_plain_blocks(page):
    """依文字區塊垂直間距合併 PDF 內文行，保留段落間距。"""
    blocks = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = ["".join(span.get("text", "") for span in line.get("spans", [])) for line in block.get("lines", [])]
        text = "\n".join(_join_pdf_wrapped_lines(lines)).strip()
        if text:
            blocks.append((block.get("bbox", (0, 0, 0, 0)), text))
    # 保留 PDF 原本的文字閱讀順序，避免直式版面被座標排序打亂。
    if not blocks:
        return ""
    sizes = [max(1.0, (box[2] - box[0]) if (box[3] - box[1]) > (box[2] - box[0]) * 3 else (box[3] - box[1])) for box, _ in blocks]
    gap_limit = max(2.0, sorted(sizes)[len(sizes) // 2] * 0.35)
    paragraphs, current, previous_box = [], "", None
    for box, text in blocks:
        gap = _pdf_block_gap(box, previous_box)
        if current and gap > gap_limit:
            paragraphs.append(current)
            current = ""
        current = "\n".join(_join_pdf_wrapped_lines(current.splitlines() + text.splitlines())) if current else text
        previous_box = box
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)


def extract_page_markdown(page, doc, page_num, images_dir_rel, images_dir_abs, base_font_size=11.0):
    """
    從 PDF 單頁結構中根據字型大小與排版智慧識別不同層級的標題 (#, ##, ###) 與文字段落。
    """
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    page_md_lines = []
    text_blocks_with_geometry = []
    global_img_count = 1
    
    for block in blocks:
        # 1. 圖片區塊
        if block.get("type") == 1:
            try:
                image_bytes = block.get("image")
                image_ext = block.get("ext", "png")
                if image_bytes and images_dir_abs:
                    img_filename = f"img_p{page_num + 1}_{global_img_count:03d}.{image_ext}"
                    img_path = os.path.join(images_dir_abs, img_filename)
                    with open(img_path, "wb") as f_img:
                        f_img.write(image_bytes)
                    rel_link = f"./{images_dir_rel}/{img_filename}"
                    page_md_lines.append(f"![頁面 {page_num + 1} 圖片]({rel_link})\n")
                    global_img_count += 1
            except Exception:
                pass
            continue

        # 2. 文字區塊
        if block.get("type") == 0:
            block_lines = []
            raw_lines = []
            for line in block.get("lines", []):
                line_spans = []
                max_span_size = 0.0
                is_bold = False

                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    span_size = span.get("size", 10.0)
                    span_flags = span.get("flags", 0)

                    if span_size > max_span_size:
                        max_span_size = span_size
                    if span_flags & 2 != 0 or span_flags & 16 != 0 or "bold" in span.get("font", "").lower():
                        is_bold = True

                    line_spans.append(span_text)

                line_full_text = "".join(line_spans).strip()
                if not line_full_text:
                    continue
                raw_lines.append({
                    "text": line_full_text,
                    "max_size": max_span_size,
                    "is_bold": is_bold,
                    "bbox": line.get("bbox"),
                })

            for raw_line in _merge_overlapping_short_lines(raw_lines):
                line_full_text = raw_line["text"]
                max_span_size = raw_line["max_size"]
                is_bold = raw_line["is_bold"]

                # 依據字級大小判定 Header 等級
                if max_span_size >= base_font_size * 1.55:
                    block_lines.append(f"# {line_full_text}")
                elif max_span_size >= base_font_size * 1.28:
                    block_lines.append(f"## {line_full_text}")
                elif max_span_size >= base_font_size * 1.12 or (is_bold and re.match(r'^(第[0-9一二三四五六七八九十百]+[章節回篇]|Chapter\s+\d+|Section\s+\d+)', line_full_text, re.I)):
                    block_lines.append(f"### {line_full_text}")
                else:
                    block_lines.append(line_full_text)

            if block_lines:
                text_blocks_with_geometry.append((
                    block.get("bbox", (0, 0, 0, 0)),
                    "\n".join(_join_pdf_wrapped_lines(block_lines)),
                ))

    # 某些 PDF 會把每一行輸出成獨立文字區塊；依區塊的垂直間距還原段落。
    if text_blocks_with_geometry:
        # 保留 PyMuPDF 的閱讀順序；直式 PDF 的 bbox 座標不能用來重新排序。
        ordered_blocks = text_blocks_with_geometry
        sizes = [max(1.0, (box[2] - box[0]) if (box[3] - box[1]) > (box[2] - box[0]) * 3 else (box[3] - box[1])) for box, _ in ordered_blocks]
        line_gap_limit = max(2.0, sorted(sizes)[len(sizes) // 2] * 0.35)
        current_text = ""
        current_box = None
        for box, block_text in ordered_blocks:
            gap = _pdf_block_gap(box, current_box)
            if current_text and (gap > line_gap_limit or block_text.startswith("#") or current_text.startswith("#")):
                page_md_lines.append(current_text)
                current_text = ""
            if current_text:
                current_text = "\n".join(_join_pdf_wrapped_lines(current_text.splitlines() + block_text.splitlines()))
            else:
                current_text = block_text
            current_box = box
        if current_text:
            page_md_lines.append(current_text)

    # 同時提取頁面內嵌的獨立 image list (如果 dict 未涵蓋)
    if images_dir_abs:
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image.get("width", 100) < 60 or base_image.get("height", 100) < 60:
                    continue
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                img_filename = f"img_p{page_num + 1}_emb_{global_img_count:03d}.{img_ext}"
                img_path = os.path.join(images_dir_abs, img_filename)
                
                # 避免重複寫入相同大小的圖
                if not os.path.exists(img_path):
                    with open(img_path, "wb") as f_img:
                        f_img.write(img_bytes)
                    rel_link = f"./{images_dir_rel}/{img_filename}"
                    page_md_lines.append(f"![頁面 {page_num + 1} 圖片]({rel_link})\n")
                    global_img_count += 1
            except Exception:
                pass

    return "\n\n".join(page_md_lines)

def convert_pdf_direct(file_path: str, output_format: str, output_folder: str) -> str:
    """
    使用 PyMuPDF 直接提取 PDF 中的文字與圖片（不需 AI），支援輸出階層化 Markdown 或純文字 TXT。
    若輸出為 Markdown，圖片會存於 output_folder/<pdf_name>_images/。
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_base_name = sanitize_filename(base_name)
    
    images_dir_rel = f"{safe_base_name}_images"
    images_dir_abs = os.path.join(output_folder, images_dir_rel)
    
    if output_format.lower() == 'md':
        os.makedirs(images_dir_abs, exist_ok=True)
    else:
        images_dir_abs = None

    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    # 統計全書常見字型大小作為基準 (base_font_size)
    font_sizes = []
    for p_num in range(min(total_pages, 10)): # 取前 10 頁取樣
        page = doc[p_num]
        p_dict = page.get_text("dict")
        for b in p_dict.get("blocks", []):
            if b.get("type") == 0:
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        if len(s.get("text", "").strip()) > 1:
                            font_sizes.append(s.get("size", 11.0))
                            
    base_font_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 11.0
    if base_font_size < 8.0:
        base_font_size = 11.0

    page_contents = []
    for page_num in range(total_pages):
        page = doc[page_num]
        if output_format.lower() == 'md':
            page_md = extract_page_markdown(page, doc, page_num, images_dir_rel, images_dir_abs, base_font_size)
            if page_md.strip():
                page_contents.append(page_md.strip())
        else:
            # 依 PDF 文字區塊間距還原段落，移除每行尾端的版面換行。
            page_text = _merge_pdf_plain_blocks(page).strip()
            if page_text:
                page_contents.append(page_text)

    doc.close()

    # 清理可能為空的圖片目錄
    if output_format.lower() == 'md' and images_dir_abs and os.path.exists(images_dir_abs) and not os.listdir(images_dir_abs):
        try:
            os.rmdir(images_dir_abs)
        except OSError:
            pass

    combined_text = _combine_page_contents(page_contents)
    cleaned_text = clean_xml_artifacts(combined_text)
    final_text = to_traditional_chinese(cleaned_text)

    out_ext = ".md" if output_format.lower() == 'md' else ".txt"
    out_file = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_text)

    return out_file
