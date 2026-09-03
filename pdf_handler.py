try:
    import pymupdf as fitz
except ImportError:
    import fitz
import os
from PIL import Image

def convert_pdf_to_images(pdf_path, output_folder):
    """
    將單一 PDF 檔案的每一頁轉換為 PNG 圖片。

    :param pdf_path: PDF 檔案的路徑。
    :param output_folder: 儲存圖片的資料夾。
    :return: 包含所有圖片路徑的列表。
    """
    image_paths = []
    try:
        pdf_document = fitz.open(pdf_path)
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap()
            image_path = os.path.join(output_folder, f"{os.path.basename(pdf_path)}_page_{page_num + 1}.png")
            pix.save(image_path)
            image_paths.append(image_path)
        pdf_document.close()
        print(f"成功將 {pdf_path} 轉換為 {len(image_paths)} 張圖片。")
        return image_paths
    except Exception as e:
        print(f"處理 PDF {pdf_path} 時發生錯誤: {e}")
        return []
