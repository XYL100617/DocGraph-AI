import cv2
import os
from bs4 import BeautifulSoup

try:
    from paddleocr import PPStructure
except Exception:
    PPStructure = None


_structure_engine = None


def get_structure_engine():
    global _structure_engine

    if PPStructure is None:
        return None

    if _structure_engine is None:
        _structure_engine = PPStructure(
            show_log=False,
            image_orientation=False,
            lang="ch",
            layout=True,
            table=True,
            ocr=True
        )

    return _structure_engine


def ensure_3_channel_image(image_path: str):
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return image_path

    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        base, _ = os.path.splitext(image_path)
        new_path = base + "_3ch.jpg"
        cv2.imwrite(new_path, img)
        return new_path

    return image_path

def looks_like_table_image(image_path: str) -> bool:
    """
    兼容旧版 ocr.py 的导入。
    当前不再强制给表格加标签，只做是否疑似表格的轻量判断。
    """
    if not image_path or not os.path.exists(image_path):
        return False

    img = cv2.imread(image_path)
    if img is None:
        return False

    h, w = img.shape[:2]

    if w < 500 or h < 400:
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(30, w // 25), 1)
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (1, max(30, h // 25))
    )
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

    h_ratio = horizontal.sum() / 255 / (w * h)
    v_ratio = vertical.sum() / 255 / (w * h)

    return h_ratio > 0.0015 or v_ratio > 0.001

def html_table_to_rows(html: str):
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    rows = []

    for tr in soup.find_all("tr"):
        cells = []
        for cell in tr.find_all(["td", "th"]):
            text = cell.get_text(" ", strip=True)
            if text:
                cells.append(text)
        if cells:
            rows.append(cells)

    return rows


def rows_to_plain_lines(rows):
    """
    表格只转成普通文本行。
    不再输出【表格】、表格表头、表格内容行。
    """
    lines = []
    for row in rows:
        line = " | ".join(row).strip()
        if line:
            lines.append(line)
    return lines


def table_score(rows):
    if not rows:
        return 0

    row_count = len(rows)
    max_cols = max(len(r) for r in rows)
    text_len = sum(len("".join(r)) for r in rows)

    return row_count * 1000 + max_cols * 100 + text_len


def pick_best_table(table_groups):
    if not table_groups:
        return []

    return sorted(
        table_groups,
        key=lambda rows: table_score(rows),
        reverse=True
    )[0]


def extract_text_from_structure_res(res):
    if not res:
        return ""

    if isinstance(res, str):
        return res.strip()

    if isinstance(res, dict):
        if "text" in res:
            return str(res.get("text", "")).strip()
        if "html" in res:
            return ""

    if isinstance(res, list):
        texts = []

        for item in res:
            if isinstance(item, dict):
                if "text" in item:
                    texts.append(str(item.get("text", "")).strip())
                elif "res" in item:
                    t = extract_text_from_structure_res(item.get("res"))
                    if t:
                        texts.append(t)

            elif isinstance(item, (list, tuple)):
                try:
                    if len(item) >= 2 and isinstance(item[1], (list, tuple)):
                        texts.append(str(item[1][0]).strip())
                except Exception:
                    pass

            elif isinstance(item, str):
                texts.append(item.strip())

        return "\n".join([t for t in texts if t])

    return ""


def is_duplicate_text(text, existing_texts):
    if not text:
        return True

    compact = text.replace(" ", "").replace("\n", "")
    if len(compact) < 3:
        return True

    for old in existing_texts:
        old_compact = old.replace(" ", "").replace("\n", "")

        if compact in old_compact:
            return True

        if old_compact in compact and len(old_compact) > 8:
            return True

    return False


def run_structure_ocr(image_path: str):
    engine = get_structure_engine()

    if engine is None:
        return None

    try:
        safe_image_path = ensure_3_channel_image(image_path)
        result = engine(safe_image_path)
    except Exception as e:
        print("PP-Structure识别失败：", e)
        return None

    table_groups = []
    text_lines = []

    for item in result:
        item_type = item.get("type", "text")
        res = item.get("res", "")

        if item_type == "table":
            html = ""
            if isinstance(res, dict):
                html = res.get("html", "")

            rows = html_table_to_rows(html)
            if rows:
                table_groups.append(rows)

        elif item_type in ["figure", "image"]:
            continue

        else:
            text = extract_text_from_structure_res(res)
            if text:
                text_lines.append(text)

    final_lines = []

    if table_groups:
        best_rows = pick_best_table(table_groups)
        table_lines = rows_to_plain_lines(best_rows)

        final_lines.extend(table_lines)

        for text in text_lines:
            if not is_duplicate_text(text, table_lines):
                final_lines.append(text)
    else:
        final_lines.extend(text_lines)

    final_lines = [line.strip() for line in final_lines if line.strip()]

    if not final_lines:
        return None

    structured_text = "\n".join(final_lines)
    raw_text = structured_text

    return {
        "raw_text": raw_text,
        "structured_text": structured_text,
        "layout_type": "pp_structure",
        "modules": [
            {
                "module": "识别内容",
                "text": structured_text,
                "blocks": []
            }
        ],
        "blocks": []
    }