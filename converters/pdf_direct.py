import os
import re
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from .base import to_traditional_chinese, sanitize_filename, clean_xml_artifacts

def extract_page_markdown(page, doc, page_num, images_dir_rel, images_dir_abs, base_font_size=11.0):
    """
    從 PDF 單頁結構中根據字型大小與排版智慧識別不同層級的標題 (#, ##, ###) 與文字段落。
    """
    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])
    
    page_md_lines = []
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
                page_md_lines.append("\n".join(block_lines))

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
            page_text = page.get_text("text").strip()
            if page_text:
                page_contents.append(page_text)

    doc.close()

    # 清理可能為空的圖片目錄
    if output_format.lower() == 'md' and images_dir_abs and os.path.exists(images_dir_abs) and not os.listdir(images_dir_abs):
        try:
            os.rmdir(images_dir_abs)
        except OSError:
            pass

    separator = "\n\n---\n\n" if output_format.lower() == 'md' else "\n\n"
    combined_text = separator.join(page_contents)
    cleaned_text = clean_xml_artifacts(combined_text)
    final_text = to_traditional_chinese(cleaned_text)

    out_ext = ".md" if output_format.lower() == 'md' else ".txt"
    out_file = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_text)

    return out_file
