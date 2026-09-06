import os
import re
import shutil
import tempfile
import mobi
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
from .epub_converter import convert_epub
from .txt_converter import read_text_file_with_detection

def convert_mobi_family(file_path: str, output_format: str, output_folder: str) -> str:
    """
    轉換 MOBI / AZW / AZW3 檔案至 Markdown 或 TXT 格式。
    使用 mobi (KindleUnpack) 深度解壓與解析，支援 KF8/AZW3 與舊版 MOBI7。
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_base_name = sanitize_filename(base_name)
    
    temp_extract_dir = None
    try:
        # 解壓 mobi / azw / azw3
        # mobi.extract 回傳 (tempdir, filepath)
        ret = mobi.extract(file_path)
        if isinstance(ret, tuple) and len(ret) >= 2:
            if os.path.isdir(ret[0]):
                temp_extract_dir, extracted_filepath = ret[0], ret[1]
            else:
                extracted_filepath, temp_extract_dir = ret[0], ret[1]
        else:
            temp_extract_dir = str(ret)
            extracted_filepath = ""

        # 1. 搜尋是否有解壓產生的 .epub 檔案 (KF8/AZW3 解壓最常見結構)
        epub_files = []
        if extracted_filepath and extracted_filepath.lower().endswith(".epub") and os.path.isfile(extracted_filepath):
            epub_files.append(extracted_filepath)
        elif temp_extract_dir and os.path.isdir(temp_extract_dir):
            for root, _, files in os.walk(temp_extract_dir):
                for f in files:
                    if f.lower().endswith(".epub"):
                        epub_files.append(os.path.join(root, f))

        if epub_files:
            # 使用第一個找到的 epub 進行轉換
            result = convert_epub(epub_files[0], output_format, output_folder)
            out_ext = ".md" if output_format.lower() == 'md' else ".txt"
            target_out = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
            if os.path.exists(result) and os.path.abspath(result) != os.path.abspath(target_out):
                if os.path.exists(target_out):
                    os.remove(target_out)
                os.rename(result, target_out)
            return target_out

        # 2. 若無 epub，直接處理解壓出的 HTML / XHTML 結構
        images_dir_rel = f"{safe_base_name}_images"
        images_dir_abs = os.path.join(output_folder, images_dir_rel)
        image_map = {}

        if output_format.lower() == 'md':
            os.makedirs(images_dir_abs, exist_ok=True)

        # 收集所有解壓出來的圖片並建立 image_map
        img_idx = 1
        if temp_extract_dir and os.path.isdir(temp_extract_dir):
            for root, _, files in os.walk(temp_extract_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
                        src_img_path = os.path.join(root, f)
                        if output_format.lower() == 'md':
                            dest_img_name = f"img_{img_idx:03d}{ext}"
                            dest_img_path = os.path.join(images_dir_abs, dest_img_name)
                            shutil.copy2(src_img_path, dest_img_path)
                            rel_path = f"{images_dir_rel}/{dest_img_name}"
                            image_map[f] = rel_path
                            image_map[os.path.basename(f)] = rel_path
                            img_idx += 1

        # 搜尋所有 HTML / XHTML / HTM / TXT 檔案
        html_files = []
        if extracted_filepath and os.path.isfile(extracted_filepath) and extracted_filepath.lower().endswith(('.html', '.htm', '.xhtml')):
            html_files.append(extracted_filepath)
        elif temp_extract_dir and os.path.isdir(temp_extract_dir):
            # 優先尋找 mobi8 (KF8) 子目錄，次選 mobi7
            mobi8_files = []
            mobi7_files = []
            other_files = []
            
            for root, _, files in os.walk(temp_extract_dir):
                for f in sorted(files):
                    if f.lower().endswith(('.html', '.htm', '.xhtml')):
                        full_p = os.path.join(root, f)
                        if "mobi8" in root.lower():
                            mobi8_files.append(full_p)
                        elif "mobi7" in root.lower():
                            mobi7_files.append(full_p)
                        else:
                            other_files.append(full_p)
                            
            if mobi8_files:
                html_files = mobi8_files
            elif mobi7_files:
                html_files = mobi7_files
            else:
                html_files = other_files

        content_parts = []
        for h_file in html_files:
            h_content = read_text_file_with_detection(h_file)
            if not h_content:
                continue

            if output_format.lower() == 'md':
                part = html_to_markdown(h_content, image_map=image_map)
            else:
                part = html_to_text(h_content)
                
            if part.strip():
                content_parts.append(part.strip())

        # 清理若完全無圖片的目錄
        if output_format.lower() == 'md' and os.path.exists(images_dir_abs) and not os.listdir(images_dir_abs):
            try:
                os.rmdir(images_dir_abs)
            except OSError:
                pass

        combined_text = "\n\n---\n\n".join(content_parts) if output_format.lower() == 'md' else "\n\n".join(content_parts)
        
        # 全文過濾與標題強化
        combined_text = clean_xml_artifacts(combined_text)
        if output_format.lower() == 'md':
            combined_text = format_markdown_headers(combined_text)
            
        if output_format.lower() == 'md':
            final_text = normalize_vertical_brackets(to_traditional_chinese_preserving_obsidian_embeds(combined_text))
        else:
            final_text = normalize_vertical_brackets(to_traditional_chinese(combined_text))
        
        out_ext = ".md" if output_format.lower() == 'md' else ".txt"
        out_file = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(final_text)
            
        return out_file

    finally:
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
