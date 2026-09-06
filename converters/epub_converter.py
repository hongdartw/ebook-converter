import os
import io
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from .base import (
    to_traditional_chinese,
    to_traditional_chinese_preserving_obsidian_embeds,
    html_to_markdown,
    html_to_text,
    sanitize_filename,
    clean_xml_artifacts,
    format_markdown_headers,
    normalize_vertical_brackets
)

def convert_epub(file_path: str, output_format: str, output_folder: str) -> str:
    """
    轉換 EPUB 檔案至 Markdown 或 TXT 格式。
    若是 Markdown 格式，會將圖片解壓到 output_folder/<book_name>_images/。
    自動清除 XML 殘留並識別章節 Header。
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_base_name = sanitize_filename(base_name)
    
    # 讀取 EPUB
    book = epub.read_epub(file_path)
    
    # 建立圖片存放子目錄 (僅在 Markdown 模式下)
    images_dir_rel = f"{safe_base_name}_images"
    images_dir_abs = os.path.join(output_folder, images_dir_rel)
    
    image_map = {}
    
    if output_format.lower() == 'md':
        os.makedirs(images_dir_abs, exist_ok=True)
        img_idx = 1
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_name = os.path.basename(item.get_name())
            ext = os.path.splitext(item_name)[1]
            if not ext:
                ext = ".jpg"
            img_filename = f"img_{img_idx:03d}{ext}"
            img_filepath = os.path.join(images_dir_abs, img_filename)
            
            with open(img_filepath, "wb") as img_f:
                img_f.write(item.get_content())
                
            rel_path = f"{images_dir_rel}/{img_filename}"
            image_map[item.get_name()] = rel_path
            image_map[item_name] = rel_path
            img_idx += 1

    # 按照書脊 (spine) 順序讀取章節
    spine_ids = [item[0] for item in book.spine if item[0] != 'nav']
    chapters = []
    
    for item_id in spine_ids:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapters.append(item.get_content().decode('utf-8', errors='ignore'))
            
    # 若 spine 找不到，退回按 ITEM_DOCUMENT 讀取
    if not chapters:
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            chapters.append(item.get_content().decode('utf-8', errors='ignore'))

    content_parts = []
    for chap_html in chapters:
        if output_format.lower() == 'md':
            part = html_to_markdown(chap_html, image_map=image_map)
        else:
            part = html_to_text(chap_html)
            
        if part.strip():
            content_parts.append(part.strip())

    combined_text = "\n\n---\n\n".join(content_parts) if output_format.lower() == 'md' else "\n\n".join(content_parts)
    
    # 全文深度過濾與標題層級最佳化
    combined_text = clean_xml_artifacts(combined_text)
    if output_format.lower() == 'md':
        combined_text = format_markdown_headers(combined_text)
        
    if output_format.lower() == 'md':
        final_text = normalize_vertical_brackets(to_traditional_chinese_preserving_obsidian_embeds(combined_text))
    else:
        final_text = normalize_vertical_brackets(to_traditional_chinese(combined_text))
    
    # 寫入輸出檔案
    out_ext = ".md" if output_format.lower() == 'md' else ".txt"
    out_file = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_text)
        
    return out_file
