import os
import re
from bs4 import BeautifulSoup
from opencc import OpenCC
import markdownify

# 初始化台灣繁體中文轉換器 (含詞彙轉換)
cc_s2twp = OpenCC('s2twp')

def to_traditional_chinese(text: str) -> str:
    """將文字轉換為台灣常用繁體中文 (s2twp)。"""
    if not text:
        return ""
    return cc_s2twp.convert(text)


def normalize_vertical_brackets(text: str) -> str:
    """將直式排版使用的 Unicode 括號轉為橫式括號。"""
    if not text:
        return ""
    vertical_to_horizontal = str.maketrans({
        "︵": "（", "︶": "）", "︷": "｛", "︸": "｝",
        "︹": "〔", "︺": "〕", "︻": "【", "︼": "】",
        "︽": "《", "︾": "》", "︿": "〈", "﹀": "〉",
        "﹁": "「", "﹂": "」", "﹃": "『", "﹄": "』",
        "﹇": "［", "﹈": "］",
    })
    return text.translate(vertical_to_horizontal)

def sanitize_filename(name: str) -> str:
    """清理檔案名稱中的非法字元。"""
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def clean_xml_artifacts(text: str) -> str:
    """徹底清除殘留的 XML 宣告、DOCTYPE、HTML 中繼與標頭標籤字串。"""
    if not text:
        return ""
    # 移除 <?xml ... ?> 或 xml version='1.0' ... ? 殘留 (包含多行、編碼宣告、問號等變體)
    text = re.sub(r'<\?xml[^>]*\?>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<\?xml[^\n]*\??', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*xml\s+version=[^\n]*\??\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*version=[\'"][0-9.]+[\'"][^\n]*\??\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'<!DOCTYPE[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<html[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</html>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<body[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</body>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<head>.*?</head>', '', text, flags=re.IGNORECASE | re.DOTALL)
    return text

def format_markdown_headers(md_text: str) -> str:
    """
    智能識別內文中的章節、序言、附錄與標題樣式，自動套用標準 Markdown Header (#, ##, ###)。
    相容中英文電子書常見命名慣例（如「第１章」、「推薦序」、「前言」、「Chapter 1」等）。
    """
    if not md_text:
        return ""

    lines = md_text.split('\n')
    formatted_lines = []
    i = 0
    
    # 常見獨立章節/結構關鍵詞 (長度短於 40 字)
    major_section_re = re.compile(
        r'^(推薦序|自序|原序|譯者序|編者序|序言|序|前\s*言|導\s*讀|引\s*言|目\s*次|目\s*錄|後\s*記|跋|結\s*語|總\s*結|附\s*錄|致\s*謝|作者簡介|譯者簡介|繪者簡介|各界好評推薦|版權頁|Prologue|Epilogue|Acknowledgements?)(\s*[:：].*)?$',
        re.I
    )
    # 常見章節序號 (如: 第1章, 第１章, 第一章, 第十篇, Chapter 1, Part 2)
    chapter_num_re = re.compile(
        r'^(第[0-9０-９一二三四五六七八九十百千萬]+[章節回篇部集卷冊]|Chapter\s+[0-9IVXLCDM]+|Part\s+[0-9IVXLCDM]+|Section\s+[0-9IVXLCDM]+)(\s*.*)?$',
        re.I
    )

    while i < len(lines):
        line = lines[i].strip()
        
        # 跳過空行、分隔線或已經是 Markdown Header 的行
        if not line or line.startswith('#') or line.startswith('---') or line.startswith('!['):
            formatted_lines.append(lines[i])
            i += 1
            continue

        # 情況 A: 匹配章節序號 (如 "第１章" 或 "第１章　覺察")
        chap_match = chapter_num_re.match(line)
        if chap_match and len(line) <= 50:
            rest_of_match = (chap_match.group(2) or '').strip()
            
            # 如果這一行只有 "第１章"，且下一行是副標題 (如 "覺察")
            if not rest_of_match and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('#') and not next_line.startswith('---') and not next_line.startswith('![') and len(next_line) <= 40:
                    formatted_lines.append(f"## {line}　{next_line}")
                    i += 2
                    continue
            
            formatted_lines.append(f"## {line}")
            i += 1
            continue

        # 情況 B: 匹配重要獨立區塊 (如 "推薦序", "前言", "目次")
        major_match = major_section_re.match(line)
        if major_match and len(line) <= 50:
            # 檢查下一行是否為副標題 (例如 "一本飽含穿透力且深具指引作用的智慧之作")
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('#') and not next_line.startswith('---') and not next_line.startswith('![') and len(next_line) <= 50 and not major_section_re.match(next_line):
                    formatted_lines.append(f"## {line}")
                    formatted_lines.append(f"### {next_line}")
                    i += 2
                    continue
                    
            formatted_lines.append(f"## {line}")
            i += 1
            continue

        formatted_lines.append(lines[i])
        i += 1

    return '\n'.join(formatted_lines)

def preprocess_html_headings(soup: BeautifulSoup):
    """
    識別電子書 HTML 中常見的非標準標題標籤 (如 class 含有 title, chapter, heading 等)，
    轉換為標準 h1, h2, h3 標籤。
    """
    h1_patterns = re.compile(r'(book[-_]?title|main[-_]?title|volume[-_]?title)', re.I)
    h2_patterns = re.compile(r'(chapter[-_]?title|chap[-_]?title|section[-_]?title|heading1)', re.I)
    h3_patterns = re.compile(r'(sub[-_]?title|subtitle|heading2|subheading)', re.I)

    for tag in soup.find_all(['p', 'div', 'span', 'b', 'strong']):
        classes = ' '.join(tag.get('class', []))
        tag_id = tag.get('id', '')
        combined_attr = f"{classes} {tag_id}"

        if tag.find_parent(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            continue

        if h1_patterns.search(combined_attr):
            tag.name = 'h1'
        elif h2_patterns.search(combined_attr):
            tag.name = 'h2'
        elif h3_patterns.search(combined_attr):
            tag.name = 'h3'

def html_to_markdown(html_content: str, image_map: dict = None) -> str:
    """
    將 HTML / XHTML 內容轉換為乾淨、標題分級 (#, ##, ###) 的 Markdown 格式。
    徹底清除 XML 宣告與標頭雜訊。
    """
    if not html_content:
        return ""

    html_content = clean_xml_artifacts(html_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 移除 script, style, head, meta, link 等無關標籤
    for tag in soup(['script', 'style', 'head', 'meta', 'link', 'nav']):
        tag.decompose()

    preprocess_html_headings(soup)

    # 替換圖片 src
    if image_map:
        for img in soup.find_all('img'):
            src = img.get('src', '')
            basename_src = os.path.basename(src)
            if src in image_map:
                img['src'] = image_map[src]
            elif basename_src in image_map:
                img['src'] = image_map[basename_src]
            else:
                for k, v in image_map.items():
                    if src.endswith(k) or k.endswith(src):
                        img['src'] = v
                        break

    cleaned_html = str(soup)
    md_text = markdownify.markdownify(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        strip=['script', 'style', 'head', 'meta', 'link']
    )
    
    # 清理 XML 與標頭殘留
    md_text = clean_xml_artifacts(md_text)
    # 智能加強標題格式
    md_text = format_markdown_headers(md_text)
    
    md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()
    return md_text

def html_to_text(html_content: str) -> str:
    """將 HTML 內容轉換為乾淨純文字，並移除 XML 與標頭噪點。"""
    if not html_content:
        return ""
    
    html_content = clean_xml_artifacts(html_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'head', 'meta', 'link', 'nav']):
        tag.decompose()
        
    text = soup.get_text(separator='\n\n')
    text = clean_xml_artifacts(text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text
