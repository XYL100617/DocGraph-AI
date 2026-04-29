import os
import fitz


def is_pdf(file_path: str) -> bool:
    return file_path.lower().endswith(".pdf")


def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 180, max_pages: int = 20):
    """
    PDF转图片。
    默认最多处理20页，避免比赛演示时卡死。
    如果想全部处理，把 max_pages 改成 None。
    """

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    image_paths = []

    total_pages = len(doc)

    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    for page_index in range(total_pages):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        image_path = os.path.join(
            output_dir,
            f"{os.path.basename(pdf_path)}_page_{page_index + 1}.jpg"
        )

        pix.save(image_path)
        image_paths.append(image_path)

    doc.close()

    return image_paths