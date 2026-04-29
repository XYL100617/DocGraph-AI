import os
import re
import cv2

from paddleocr import PaddleOCR

from utils.image_preprocess import create_ocr_variants
from utils.pdf_utils import is_pdf, pdf_to_images
from core.ocr_postprocess import postprocess_ocr_blocks, build_clean_text
from core.layout_analyzer import analyze_layout
from core.structure_ocr import looks_like_table_image, run_structure_ocr

ocr_engine = PaddleOCR(
    use_angle_cls=True,
    lang="ch",
    use_gpu=False,
    show_log=False,
    det_db_box_thresh=0.35,
    det_db_unclip_ratio=1.5,
    rec_batch_num=8
)


def normalize_box(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return {"x1": float(min(xs)), "y1": float(min(ys)), "x2": float(max(xs)), "y2": float(max(ys))}


def clean_table_prefix(text: str):
    if not text:
        return ""

    text = str(text)

    # 去掉各种表格/区域标签
    text = re.sub(r"【\s*表格\s*】", "", text)
    text = re.sub(r"【?\s*表格表头\s*】?", "", text)
    text = re.sub(r"【?\s*表格内容行\d+\s*】?", "", text)
    text = re.sub(r"【?\s*文本区域\d*\s*】?", "", text)
    text = re.sub(r"【?\s*识别内容\s*】?", "", text)

    # 有些会识别成普通文字“表格：xxx”，只删开头标签，不删正文里的“表格”
    text = re.sub(r"^\s*表格\s*[:：]\s*", "", text)
    text = re.sub(r"^\s*表格表头\s*[:：]?\s*", "", text)
    text = re.sub(r"^\s*表格内容行\d+\s*[:：]?\s*", "", text)
    text = re.sub(r"^\s*文本区域\d*\s*[:：]?\s*", "", text)

    # 清理多余空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def is_noise_text(text: str, confidence: float, keep_numbers=False):
    if not text:
        return True
    text = clean_table_prefix(text).strip()
    if not text:
        return True
    if re.fullmatch(r"[\.\,\:\;\|\+\-\*/\\、，。：；\s_]+", text):
        return True
    if not keep_numbers:
        compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"\d{1,4}", compact):
            return True
        if re.fullmatch(r"[\d\.\?\s]+", text) and len(compact) <= 5:
            return True
    if confidence < 0.50:
        return True
    if len(text) <= 1 and confidence < 0.75:
        return True
    if len(text) <= 2 and not re.search(r"[\u4e00-\u9fa5]", text):
        return True
    return False


def run_single_ocr(image_path):
    result = ocr_engine.ocr(image_path, cls=True)
    if not result or not result[0]:
        return []
    blocks = []
    for line in result[0]:
        try:
            box = line[0]
            text = clean_table_prefix(line[1][0].strip())
            confidence = float(line[1][1])
        except Exception:
            continue
        if is_noise_text(text, confidence, keep_numbers=False):
            continue
        blocks.append({"text": text, "confidence": confidence, "bbox": normalize_box(box), "type": "text"})
    return blocks


def average_confidence(blocks):
    if not blocks:
        return 0.0
    return sum(float(b.get("confidence", 0)) for b in blocks) / len(blocks)


def is_meaningful_text(text: str):
    if not text:
        return False
    text = text.strip()
    if len(re.findall(r"[\u4e00-\u9fa5]", text)) >= 4:
        return True
    if re.search(r"[A-Za-z]", text) and len(text) >= 5:
        return True
    return False


def should_use_enhanced_ocr(blocks):
    if not blocks:
        return True
    meaningful_blocks = [b for b in blocks if is_meaningful_text(b.get("text", ""))]
    if meaningful_blocks:
        return False
    avg_conf = average_confidence(blocks)
    if avg_conf < 0.45 and len(blocks) <= 2:
        return True
    return False


def box_iou(a, b):
    x1 = max(a["x1"], b["x1"])
    y1 = max(a["y1"], b["y1"])
    x2 = min(a["x2"], b["x2"])
    y2 = min(a["y2"], b["y2"])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(1, (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]))
    area_b = max(1, (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]))
    return inter / (area_a + area_b - inter + 1e-6)


def merge_blocks(all_blocks):
    merged = []
    for block in all_blocks:
        block["text"] = clean_table_prefix(block.get("text", ""))
        if not block["text"]:
            continue
        matched = False
        for i, old in enumerate(merged):
            same_area = box_iou(block["bbox"], old["bbox"]) > 0.45
            same_text = block["text"] == old["text"]
            if same_area or same_text:
                matched = True
                if block["confidence"] > old["confidence"] or len(block["text"]) > len(old["text"]):
                    merged[i] = block
                break
        if not matched:
            merged.append(block)
    return merged


def add_padding_for_full_image(image_path: str, padding: int = 80):
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return image_path
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    padded = cv2.copyMakeBorder(img, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=[255, 255, 255])
    base, _ = os.path.splitext(image_path)
    out_path = base + "_padded_full.jpg"
    cv2.imwrite(out_path, padded)
    return out_path


def filter_ocr_result_noise(ocr_result, keep_numbers=False):
    if not ocr_result:
        return ocr_result
    blocks = ocr_result.get("blocks", [])
    clean_blocks = []
    for block in blocks:
        text = clean_table_prefix(block.get("text", ""))
        try:
            confidence = float(block.get("confidence", 1.0))
        except Exception:
            confidence = 1.0
        if is_noise_text(text, confidence, keep_numbers=keep_numbers):
            continue
        block["text"] = text
        block["confidence"] = confidence
        clean_blocks.append(block)
    ocr_result["blocks"] = clean_blocks
    clean_text = build_clean_text(clean_blocks)
    ocr_result["raw_text"] = clean_text
    if not ocr_result.get("structured_text"):
        ocr_result["structured_text"] = clean_text
    else:
        ocr_result["structured_text"] = clean_table_prefix(ocr_result["structured_text"])
    return ocr_result


def run_plain_ocr(image_path: str):
    blocks = run_single_ocr(image_path)
    all_blocks = blocks[:]
    if should_use_enhanced_ocr(blocks):
        image_variants = create_ocr_variants(image_path)
        for img in image_variants:
            if img == image_path:
                continue
            try:
                all_blocks.extend(run_single_ocr(img))
            except Exception as e:
                print("增强OCR失败：", e)
    if not all_blocks:
        return {"raw_text": "", "structured_text": "", "layout_type": "unknown", "modules": [], "blocks": []}
    merged_blocks = merge_blocks(all_blocks)
    clean_blocks = postprocess_ocr_blocks(merged_blocks)
    for b in clean_blocks:
        b["text"] = clean_table_prefix(b.get("text", ""))
    layout_result = analyze_layout(clean_blocks)
    raw_text = build_clean_text(clean_blocks)
    return {
        "raw_text": raw_text,
        "structured_text": clean_table_prefix(layout_result.get("structured_text", "")),
        "layout_type": layout_result.get("layout_type", "plain_ocr"),
        "modules": layout_result.get("modules", []),
        "blocks": layout_result.get("sorted_blocks", clean_blocks)
    }


def run_ocr(image_path: str):
    padded_path = add_padding_for_full_image(image_path, padding=80)
    table_like = looks_like_table_image(padded_path)
    result = None
    if table_like:
        try:
            structure_result = run_structure_ocr(padded_path)
        except Exception as e:
            print("PP-Structure失败，回退普通OCR：", e)
            structure_result = None
        if structure_result:
            print("使用 PP-Structure 表格/版面识别")
            result = structure_result
    if result is None:
        print("使用普通 PaddleOCR 识别")
        result = run_plain_ocr(padded_path)
    return filter_ocr_result_noise(result, keep_numbers=table_like)


def run_ocr_document(file_path: str):
    if not is_pdf(file_path):
        return run_ocr(file_path)

    output_dir = os.path.join(os.path.dirname(file_path), "pdf_pages")
    page_images = pdf_to_images(
        pdf_path=file_path,
        output_dir=output_dir,
        dpi=180,
        max_pages=20
    )

    all_blocks = []
    raw_parts = []
    structured_parts = []

    for page_index, image_path in enumerate(page_images):
        page_no = page_index + 1

        page_result = run_ocr(image_path)

        raw_text = page_result.get("raw_text", "")
        structured_text = page_result.get("structured_text", "") or raw_text

        if raw_text.strip():
            raw_parts.append(raw_text.strip())

        if structured_text.strip():
            structured_parts.append(structured_text.strip())

        for block in page_result.get("blocks", []):
            block["page"] = page_no
            all_blocks.append(block)

    raw_text = "\n\n".join(raw_parts)
    structured_text = "\n\n".join(structured_parts)

    raw_text = clean_table_prefix(raw_text)
    structured_text = clean_table_prefix(structured_text)
    
    return {
        "raw_text": raw_text,
        "structured_text": structured_text,
        "layout_type": "pdf_document",
        "modules": [
            {
                "module": "识别内容",
                "text": structured_text,
                "blocks": all_blocks
            }
        ],
        "blocks": all_blocks
    }