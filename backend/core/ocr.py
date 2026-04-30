import os
import re
import cv2

from paddleocr import PaddleOCR
from core.ecla import ecla_enhance

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
    det_db_box_thresh=0.30,
    det_db_unclip_ratio=1.5,
    rec_batch_num=8
)


def normalize_box(box):
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]

    return {
        "x1": float(min(xs)),
        "y1": float(min(ys)),
        "x2": float(max(xs)),
        "y2": float(max(ys))
    }


def rect_to_ecla_bbox(rect):
    """
    当前项目 bbox:
    {"x1":..., "y1":..., "x2":..., "y2":...}

    ECLA bbox:
    [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
    """
    if isinstance(rect, list):
        return rect

    x1 = float(rect.get("x1", 0))
    y1 = float(rect.get("y1", 0))
    x2 = float(rect.get("x2", 0))
    y2 = float(rect.get("y2", 0))

    return [
        [x1, y1],
        [x2, y1],
        [x2, y2],
        [x1, y2]
    ]


def blocks_to_ecla_blocks(blocks, page=1):
    ecla_blocks = []

    for block in blocks:
        text = clean_table_prefix(block.get("text", ""))
        if not text:
            continue

        bbox = block.get("bbox")
        if not bbox:
            continue

        confidence = block.get("confidence", block.get("score", 1.0))

        try:
            confidence = float(confidence)
        except Exception:
            confidence = 1.0

        ecla_blocks.append({
            "text": text,
            "bbox": rect_to_ecla_bbox(bbox),
            "score": confidence,
            "page": int(block.get("page", page))
        })

    return ecla_blocks


def apply_ecla_to_result(ocr_result, page=1):
    """
    ECLA 统一入口：
    OCR / PP-StructureV2 之后执行。
    """
    if not ocr_result:
        return {
            "raw_text": "",
            "structured_text": "",
            "layout_type": "unknown",
            "modules": [],
            "blocks": [],
            "lines": [],
            "ecla_enabled": False
        }

    blocks = ocr_result.get("blocks", [])
    if not blocks:
        ocr_result["ecla_enabled"] = False
        return ocr_result

    try:
        ecla_blocks = blocks_to_ecla_blocks(blocks, page=page)
        ecla_result = ecla_enhance(ecla_blocks)

        ecla_raw_text = clean_table_prefix(ecla_result.get("raw_text", ""))
        ecla_structured_text = clean_table_prefix(ecla_result.get("structured_text", ""))

        if ecla_raw_text:
            ocr_result["raw_text"] = ecla_raw_text

        title_texts = [
            b.get("text", "")
            for b in blocks
            if is_title_block(b) and b.get("text")
        ]

        # 去重，避免标题重复
        title_texts = list(dict.fromkeys(title_texts))

        if title_texts:
            title_part = "【标题】\n" + "\n".join(title_texts)

            if ecla_structured_text:
                if title_texts[0] not in ecla_structured_text:
                    ecla_structured_text = title_part + "\n\n" + ecla_structured_text
            else:
                ecla_structured_text = title_part

        if ecla_structured_text:
            ocr_result["structured_text"] = ecla_structured_text

        ocr_result["lines"] = ecla_result.get("lines", [])
        ocr_result["modules"] = ecla_result.get("modules", ocr_result.get("modules", []))
        ocr_result["layout_type"] = "ecla_enhanced"
        ocr_result["ecla_enabled"] = True

        return ocr_result

    except Exception as e:
        print("ECLA版面增强失败，保留原OCR结果：", e)
        ocr_result["ecla_enabled"] = False
        return ocr_result

def is_title_block(block):
    return block.get("type") in ["title_candidate", "top_title"]

def clean_table_prefix(text: str):
    if not text:
        return ""

    text = str(text)

    text = re.sub(r"【\s*表格\s*】", "", text)
    text = re.sub(r"【?\s*表格表头\s*】?", "", text)
    text = re.sub(r"【?\s*表格内容行\d+\s*】?", "", text)
    text = re.sub(r"【?\s*文本区域\d*\s*】?", "", text)
    text = re.sub(r"【?\s*识别内容\s*】?", "", text)

    text = re.sub(r"^\s*表格\s*[:：]\s*", "", text)
    text = re.sub(r"^\s*表格表头\s*[:：]?\s*", "", text)
    text = re.sub(r"^\s*表格内容行\d+\s*[:：]?\s*", "", text)
    text = re.sub(r"^\s*文本区域\d*\s*[:：]?\s*", "", text)

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

        blocks.append({
            "text": text,
            "confidence": confidence,
            "bbox": normalize_box(box),
            "type": "text"
        })

    return blocks

def run_top_title_ocr(image_path: str, top_ratio: float = 0.12):
    """
    强制识别原图顶部区域。
    规则：
    1. 使用原始 image_path，不使用 padded_path。
    2. 顶部区域 OCR 后，最上方一行标记为 top_title。
    3. 其余内容保留为 text，不删除表格表头。
    """
    print("进入 run_top_title_ocr，image_path =", image_path)

    img = cv2.imread(image_path)

    if img is None:
        print("顶部标题OCR读取图片失败：", image_path)
        return []

    h, w = img.shape[:2]

    # 裁剪原图顶部区域
    top_h = max(int(h * top_ratio), 90)
    top_img = img[:top_h, :]

    # 放大顶部区域
    top_img = cv2.resize(
        top_img,
        None,
        fx=3.0,
        fy=3.0,
        interpolation=cv2.INTER_CUBIC
    )

    # 灰度 + 增强
    gray = cv2.cvtColor(top_img, cv2.COLOR_BGR2GRAY)

    # 对比度增强
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 轻微锐化
    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    sharp = cv2.addWeighted(gray, 1.6, blur, -0.6, 0)

    # 加白边
    sharp = cv2.copyMakeBorder(
        sharp,
        80,
        80,
        80,
        80,
        cv2.BORDER_CONSTANT,
        value=255
    )

    base, _ = os.path.splitext(image_path)
    top_path = base + "_top_title_debug.jpg"
    cv2.imwrite(top_path, sharp)

    print("顶部标题调试图已保存：", top_path)

    result = ocr_engine.ocr(top_path, cls=True)

    if not result or not result[0]:
        print("顶部标题OCR没有检测到文本")
        return []

    temp_blocks = []

    for line in result[0]:
        try:
            box = line[0]
            text = clean_table_prefix(line[1][0].strip())
            confidence = float(line[1][1])
        except Exception:
            continue

        print("顶部标题OCR检测到：", text, confidence)

        if not text or confidence < 0.15:
            continue

        bbox = normalize_box(box)

        # 坐标映射回原图
        # 原图顶部区域放大了3倍，又额外加了80白边
        bbox = {
            "x1": max((bbox["x1"] - 80) / 3.0, 0),
            "y1": max((bbox["y1"] - 80) / 3.0, 0),
            "x2": max((bbox["x2"] - 80) / 3.0, 0),
            "y2": max((bbox["y2"] - 80) / 3.0, 0),
        }

        temp_blocks.append({
            "text": text,
            "confidence": confidence,
            "bbox": bbox,
            "type": "text"
        })

    if not temp_blocks:
        return []

    # 找顶部 OCR 结果中的最上方一行
    min_y = min(b["bbox"]["y1"] for b in temp_blocks)
    line_threshold = 18

    final_blocks = []

    for b in temp_blocks:
        # 最上方一行 = 表格外标题
        if abs(b["bbox"]["y1"] - min_y) <= line_threshold:
            b["type"] = "top_title"
        else:
            # 其余内容继续保留，表格表头不能删
            b["type"] = "text"

        final_blocks.append(b)

    print("顶部标题OCR最终返回：")
    for b in final_blocks:
        print(b.get("type"), b.get("text"))

    return final_blocks
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

    meaningful_blocks = [
        b for b in blocks
        if is_meaningful_text(b.get("text", ""))
    ]

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
            same_area = box_iou(block["bbox"], old["bbox"]) > 0.65
            same_text = block["text"] == old["text"]

            if is_title_block(block) or is_title_block(old):
                same_area = False
            
            if same_area or same_text:
                matched = True

                if (
                    block["confidence"] > old["confidence"]
                    or len(block["text"]) > len(old["text"])
                ):
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

    padded = cv2.copyMakeBorder(
        img,
        padding,
        padding,
        padding,
        padding,
        cv2.BORDER_CONSTANT,
        value=[255, 255, 255]
    )

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
            confidence = float(block.get("confidence", block.get("score", 1.0)))
        except Exception:
            confidence = 1.0

        block_type = block.get("type", "")

        # 顶部标题候选区域放宽过滤条件
        if is_title_block(block):
            if not text or confidence < 0.15:
                continue
        else:
            if is_noise_text(text, confidence, keep_numbers=keep_numbers):
                continue

        block["text"] = text
        block["confidence"] = confidence
        clean_blocks.append(block)

    # 注意：排序必须放在 for 循环结束后
    clean_blocks = sorted(
        clean_blocks,
        key=lambda b: (
            0 if b.get("type") == "title_candidate" else 1,
            b.get("bbox", {}).get("y1", 0),
            b.get("bbox", {}).get("x1", 0)
        )
    )

    ocr_result["blocks"] = clean_blocks

    clean_text = build_clean_text(clean_blocks)
    ocr_result["raw_text"] = clean_text

    if not ocr_result.get("structured_text"):
        ocr_result["structured_text"] = clean_text
    else:
        ocr_result["structured_text"] = clean_table_prefix(
            ocr_result["structured_text"]
        )

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
        return {
            "raw_text": "",
            "structured_text": "",
            "layout_type": "unknown",
            "modules": [],
            "blocks": [],
            "lines": [],
            "ecla_enabled": False
        }

    merged_blocks = merge_blocks(all_blocks)
    clean_blocks = postprocess_ocr_blocks(merged_blocks)

    for b in clean_blocks:
        b["text"] = clean_table_prefix(b.get("text", ""))

    layout_result = analyze_layout(clean_blocks)
    raw_text = build_clean_text(clean_blocks)

    return {
        "raw_text": raw_text,
        "structured_text": clean_table_prefix(
            layout_result.get("structured_text", "")
        ),
        "layout_type": layout_result.get("layout_type", "plain_ocr"),
        "modules": layout_result.get("modules", []),
        "blocks": layout_result.get("sorted_blocks", clean_blocks),
        "lines": [],
        "ecla_enabled": False
    }

def inject_title_candidates_to_result(ocr_result):
    if not ocr_result:
        return ocr_result

    blocks = ocr_result.get("blocks", [])

    title_blocks = [
        b for b in blocks
        if is_title_block(b) and b.get("text")
    ]

    if not title_blocks:
        return ocr_result

    title_blocks = sorted(
        title_blocks,
        key=lambda b: (
            b.get("bbox", {}).get("y1", 0),
            b.get("bbox", {}).get("x1", 0)
        )
    )

    title_texts = []
    for b in title_blocks:
        text = clean_table_prefix(b.get("text", ""))
        if text and text not in title_texts:
            title_texts.append(text)

    if not title_texts:
        return ocr_result

    title_section = "【标题】\n" + "\n".join(title_texts)

    raw_text = ocr_result.get("raw_text", "")
    structured_text = ocr_result.get("structured_text", "")

    if title_texts[0] not in raw_text:
        ocr_result["raw_text"] = title_section + "\n\n" + raw_text

    if title_texts[0] not in structured_text:
        ocr_result["structured_text"] = title_section + "\n\n" + structured_text

    modules = ocr_result.get("modules", [])
    modules.insert(0, {
        "module": "标题",
        "type": "title",
        "text": "\n".join(title_texts),
        "blocks": title_blocks
    })
    ocr_result["modules"] = modules

    return ocr_result
def inject_top_title_to_result(ocr_result):
    """
    将表格外顶部标题强制写入 raw_text / structured_text。
    不删除表格表头。
    """
    if not ocr_result:
        return ocr_result

    blocks = ocr_result.get("blocks", [])

    title_blocks = [
        b for b in blocks
        if b.get("type") == "top_title"
        and b.get("text")
    ]

    if not title_blocks:
        return ocr_result

    title_blocks = sorted(
        title_blocks,
        key=lambda b: (
            b.get("bbox", {}).get("y1", 0),
            b.get("bbox", {}).get("x1", 0)
        )
    )

    title_texts = []
    for b in title_blocks:
        text = clean_table_prefix(b.get("text", ""))
        if text and text not in title_texts:
            title_texts.append(text)

    if not title_texts:
        return ocr_result

    title_section = "【标题】\n" + "\n".join(title_texts)

    raw_text = ocr_result.get("raw_text", "")
    structured_text = ocr_result.get("structured_text", "")

    if title_texts[0] not in raw_text:
        ocr_result["raw_text"] = title_section + "\n\n" + raw_text

    if title_texts[0] not in structured_text:
        ocr_result["structured_text"] = title_section + "\n\n" + structured_text

    modules = ocr_result.get("modules", [])
    modules.insert(0, {
        "module": "标题",
        "type": "title",
        "text": "\n".join(title_texts),
        "blocks": title_blocks
    })
    ocr_result["modules"] = modules

    return ocr_result

def run_ocr(image_path: str):
    """
    ECLA增强版流程：
    1. 边缘补偿
    2. PP-Structure识别表格/版面
    3. 普通OCR补充全文文字
    4. 顶部标题区域强制OCR
    5. 合并去重
    6. 去噪
    7. ECLA版面对齐重组
    """
    padded_path = add_padding_for_full_image(image_path, padding=150)
    table_like = looks_like_table_image(padded_path)

    structure_result = None
    structure_blocks = []
    plain_blocks = []
    top_blocks = []

    # 1. 表格/复杂版面：先跑 PP-StructureV2
    if table_like:
        try:
            structure_result = run_structure_ocr(padded_path)
        except Exception as e:
            print("PP-Structure失败，回退普通OCR：", e)
            structure_result = None

        if structure_result:
            print("使用 PP-StructureV2 表格/版面识别")
            structure_blocks = structure_result.get("blocks", [])

    # 2. 无论是不是表格，都跑普通OCR补充
    try:
        print("执行普通 PaddleOCR 补充识别")
        plain_blocks = run_single_ocr(padded_path)
    except Exception as e:
        print("普通OCR补充识别失败：", e)
        plain_blocks = []

    # 3. 强制识别顶部标题区域
    try:
        print("执行顶部标题区域 OCR")
        top_blocks = run_top_title_ocr(image_path)
    except Exception as e:
        print("顶部标题OCR失败：", e)
        top_blocks = []

    # 4. 合并三路 OCR 结果
    all_blocks = []

    if structure_blocks:
        all_blocks.extend(structure_blocks)

    if plain_blocks:
        all_blocks.extend(plain_blocks)

    if top_blocks:
        all_blocks.extend(top_blocks)

    if not all_blocks:
        result = {
            "raw_text": "",
            "structured_text": "",
            "layout_type": "unknown",
            "modules": [],
            "blocks": [],
            "lines": [],
            "ecla_enabled": False
        }
        return result

    # 5. 去重合并
    merged_blocks = merge_blocks(all_blocks)

    result = {
        "raw_text": build_clean_text(merged_blocks),
        "structured_text": "",
        "layout_type": "structure_plain_top_fusion" if table_like else "plain_top_fusion",
        "modules": structure_result.get("modules", []) if structure_result else [],
        "blocks": merged_blocks,
        "lines": [],
        "ecla_enabled": False
    }

    # 6. 先去噪
    result = filter_ocr_result_noise(result, keep_numbers=table_like)

    # 7. 再 ECLA 结构增强
    result = apply_ecla_to_result(result, page=1)

    # 8. 最后强制把顶部标题候选写入最终返回字段
    result = inject_title_candidates_to_result(result)

    return result


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

        raw_text = clean_table_prefix(page_result.get("raw_text", ""))
        structured_text = clean_table_prefix(
            page_result.get("structured_text", "") or raw_text
        )

        if raw_text.strip():
            raw_parts.append(f"【第{page_no}页原始OCR】\n{raw_text.strip()}")

        if structured_text.strip():
            structured_parts.append(f"【第{page_no}页ECLA增强结果】\n{structured_text.strip()}")

        for block in page_result.get("blocks", []):
            block["page"] = page_no
            all_blocks.append(block)

    raw_text = clean_table_prefix("\n\n".join(raw_parts))
    structured_text = clean_table_prefix("\n\n".join(structured_parts))

    final_result = {
        "raw_text": raw_text,
        "structured_text": structured_text,
        "layout_type": "pdf_document",
        "modules": [
            {
                "module": "PDF识别内容",
                "text": structured_text,
                "blocks": all_blocks
            }
        ],
        "blocks": all_blocks,
        "lines": [],
        "ecla_enabled": False
    }

    # PDF汇总后先去噪
    final_result = filter_ocr_result_noise(final_result, keep_numbers=True)

    # 再对整个 PDF 的所有页面统一做一次 ECLA
    final_result = apply_ecla_to_result(final_result, page=1)
    final_result["layout_type"] = "pdf_document_ecla_enhanced"

    return final_result

