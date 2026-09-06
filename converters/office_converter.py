"""Microsoft Office 文件轉換器，透過本機 officecli 擷取文字。"""

import os
import re
import shutil
import subprocess

from .base import to_traditional_chinese, sanitize_filename

OFFICE_EXTENSIONS = (".docx", ".xlsx")


def _officecli_command():
    """找到 officecli；Windows 上優先使用 PATH 中的可執行檔。"""
    command = shutil.which("officecli")
    if command:
        return command
    raise RuntimeError(
        "找不到 officecli，請確認已安裝 officecli 並加入 PATH。"
    )


def convert_office(file_path: str, output_format: str, output_folder: str) -> str:
    """使用 officecli view text 將 Office 文件輸出為 Markdown 或純文字。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in OFFICE_EXTENSIONS:
        raise ValueError(f"不支援的 Office 副檔名: {ext}")

    command = _officecli_command()
    result = subprocess.run(
        [command, "view", file_path, "text", "--max-lines", "1000000"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"officecli 無法讀取 {os.path.basename(file_path)}。"
            f"{(' ' + detail) if detail else ''}"
        )

    raw_content = result.stdout.strip()
    # officecli 的 docx text view 會在每段文字前附上節點路徑，輸出文件不需要此標記。
    if ext == ".docx":
        raw_content = re.sub(r"^\[[^\]]+\]\s?", "", raw_content, flags=re.MULTILINE)
    content = to_traditional_chinese(raw_content)
    base_name = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])
    out_ext = ".md" if output_format.lower() == "md" else ".txt"
    output_path = os.path.join(output_folder, f"{base_name}{out_ext}")
    os.makedirs(output_folder, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(content + ("\n" if content else ""))
    return output_path
