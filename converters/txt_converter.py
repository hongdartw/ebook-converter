import os
from .base import to_traditional_chinese, sanitize_filename

def read_text_file_with_detection(file_path: str) -> str:
    """自動偵測編碼並讀取純文字檔案。"""
    try:
        import charset_normalizer
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        detected = charset_normalizer.from_bytes(raw_data).best()
        if detected:
            return str(detected)
    except Exception:
        pass

    # 備用編碼嘗試
    encodings = ['utf-8', 'utf-8-sig', 'big5', 'cp950', 'gb18030', 'gbk', 'utf-16', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
            
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def convert_txt(file_path: str, output_format: str, output_folder: str) -> str:
    """
    轉換 TXT 檔案至 Markdown 或 TXT 格式，並轉換為台灣繁體中文。
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    safe_base_name = sanitize_filename(base_name)
    
    raw_text = read_text_file_with_detection(file_path)
    final_text = to_traditional_chinese(raw_text)
    
    out_ext = ".md" if output_format.lower() == 'md' else ".txt"
    out_file = os.path.join(output_folder, f"{safe_base_name}{out_ext}")
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_text)
        
    return out_file
