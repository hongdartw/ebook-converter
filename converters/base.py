import os
import re
import html as html_lib
from bs4 import BeautifulSoup, NavigableString
from opencc import OpenCC
import markdownify

# 初始化台灣繁體中文轉換器 (含詞彙轉換)
cc_s2twp = OpenCC('s2twp')

def to_traditional_chinese(text: str) -> str:
    """將文字轉換為台灣常用繁體中文 (s2twp)。"""
    if not text:
        return ""
    return cc_s2twp.convert(text)


def to_traditional_chinese_preserving_obsidian_embeds(text: str) -> str:
    """轉換正文繁簡，但保留 Obsidian 圖片/資源嵌入路徑原字元不變。"""
    if not text:
        return ""
    embeds = []

    def keep_embed(match):
        embeds.append(match.group(0))
        return f"@@OBSIDIAN_EMBED_{len(embeds) - 1}@@"

    protected = re.sub(r'!\[\[[^\]]+\]\]', keep_embed, text)
    converted = to_traditional_chinese(protected)
    for idx, embed in enumerate(embeds):
        converted = converted.replace(f"@@OBSIDIAN_EMBED_{idx}@@", embed)
    return converted


def obsidian_embed(path: str) -> str:
    """產生 Obsidian 原生嵌入語法，路徑不可做繁簡轉換且不使用 ./ 前綴。"""
    normalized = (path or "").replace('\\', '/').lstrip('./')
    return f"![[{normalized}]]"


def _unescape_obsidian_path(path: str) -> str:
    """還原 markdownify 在 Obsidian 路徑中加入的跳脫字元。"""
    return re.sub(r'\\([_\[\]()*.!#/+\-])', r'\1', path or "")


def normalize_obsidian_embeds(md_text: str) -> str:
    """確保 Obsidian 嵌入語法與 callout 不被 Markdown 跳脫破壞。"""
    if not md_text:
        return ""
    md_text = re.sub(
        r'!\[\[([^\]]+)\]\]',
        lambda m: obsidian_embed(_unescape_obsidian_path(m.group(1))),
        md_text,
    )
    md_text = md_text.replace('> \\*\\*【注】\\*\\*', '> **【注】**')
    return md_text


def markdown_images_to_obsidian(md_text: str) -> str:
    """將傳統 Markdown 圖片語法轉為 Obsidian Wikilink 嵌入語法。"""
    if not md_text:
        return ""

    # 先處理 EPUB 常見的圖片註腳跳轉：[![長註腳](icon.png) 1](#footnote-x)
    md_text = re.sub(
        r'\[!\[([^\]]*)\]\(([^\n)]*)\)\s*([^\]]*)\]\((#[^\n)]*)\)',
        lambda m: f"> **【注】** {(m.group(1) or m.group(3) or '').strip()}",
        md_text,
    )

    md_text = re.sub(
        r'!\[([^\]]*)\]\(([^\n)]*)\)',
        lambda m: obsidian_embed(_unescape_obsidian_path(m.group(2))),
        md_text,
    )
    return normalize_obsidian_embeds(md_text)


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

def clean_ai_ocr_artifacts(text: str) -> str:
    """清除 AI OCR 常見的回答包裝、程式碼圍欄、頁碼與 PDF 浮水印雜訊。"""
    if not text:
        return ""

    # 移除 AI 回答常見前導語，避免「以下是...Markdown...」混入正文。
    text = re.sub(r'^\s*(以下是|這是|这是).{0,80}?(Markdown|markdown).{0,40}[:：]\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*(好的|當然|当然)[，,。！!\s]*(以下是|我將).{0,80}$', '', text, flags=re.MULTILINE)

    # 移除 Markdown 程式碼圍欄；OCR 結果本身不應被包在 ```markdown 裡。
    text = re.sub(r'^\s*```(?:markdown|md|text)?\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*```\s*$', '', text, flags=re.MULTILINE)

    text = html_lib.unescape(text).replace('\u2003', ' ')
    # 移除 OCR 偶爾產生的 HTML 換行/置中標籤，但保留其中正文。
    text = re.sub(r'<br\s*/?>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*<center>\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*</center>\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'<center>\s*(.*?)\s*</center>', lambda m: m.group(1).strip(), text, flags=re.IGNORECASE | re.DOTALL)

    # 移除 pdfFactory 試用版浮水印與其可能被 OCR 成的連結/HTML 下標。
    text = re.sub(r'^\s*(?:[*_`~]*\s*)?(?:<sub>)?PDF\s+created\s+with\s+pdfFactory\s+Pro\s+trial\s+version(?:\s+(?:\[[^\]]+\]\([^\)]+\)|\S+))?(?:</sub>)?(?:\s*[*_`~]*)?\s*$', '', text, flags=re.IGNORECASE | re.MULTILINE)

    # 只移除 AI 產生的置中/靠右 HTML 包裝，保留頁碼文字本身，例如：<p align="center">— 28 —</p> -> — 28 —。
    page_marker_re = r'[〔\[（(【]?\s*[-—–―━－_一二三四五六七八九十百千〇零○\d\s]+\s*[〕\]）)】]?'
    text = re.sub(
        rf'^\s*<(?:p|div|center)\b[^>]*>\s*({page_marker_re})\s*</(?:p|div|center)>\s*$',
        lambda m: m.group(1).strip(),
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r'^\s*(?:Page|PAGE|page)\s*\d{1,4}\s*(?:/\s*\d{1,4})?\s*$', '', text, flags=re.MULTILINE)

    # 移除 AI/OCR 造成的空分隔線。
    text = re.sub(r'^\s*---\s*$', '', text, flags=re.MULTILINE)

    return re.sub(r'\n{3,}', '\n\n', text).strip()


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

    def resolve_image_path(src: str) -> str:
        if not image_map:
            return src
        basename_src = os.path.basename(src)
        if src in image_map:
            return image_map[src]
        if basename_src in image_map:
            return image_map[basename_src]
        for k, v in image_map.items():
            if src.endswith(k) or k.endswith(src):
                return v
        return src

    # 清理 EPUB 常見的「註腳連結包圖片」：避免產生超長 alt 圖片與無效跳轉圖標。
    for link in soup.find_all('a'):
        img = link.find('img')
        if not img:
            continue
        href = link.get('href', '')
        alt_text = (img.get('alt') or img.get('title') or '').strip()
        link_text = link.get_text(' ', strip=True)
        note_text = alt_text or link_text
        if href.startswith('#') or 'footnote' in href.lower() or len(note_text) > 20:
            link.replace_with(NavigableString(f"\n> **【注】** {note_text}\n"))

    # 圖片強制使用 Obsidian Wikilink 嵌入，避免 ()、空格造成傳統 Markdown 路徑截斷。
    for img in soup.find_all('img'):
        src = img.get('src', '')
        img.replace_with(NavigableString(obsidian_embed(resolve_image_path(src))))

    cleaned_html = str(soup)
    md_text = markdownify.markdownify(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        strip=['script', 'style', 'head', 'meta', 'link']
    )
    
    # 清理 XML 與標頭殘留
    md_text = clean_xml_artifacts(md_text)
    md_text = markdown_images_to_obsidian(md_text)
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
