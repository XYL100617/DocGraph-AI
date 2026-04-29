import cv2
import os


def estimate_text_area_ratio(ocr_blocks, image_path):
    """
    估算 OCR 文本框覆盖面积比例。
    """

    img = cv2.imread(image_path)

    if img is None:
        return 0.0

    h, w = img.shape[:2]
    image_area = max(h * w, 1)

    text_area = 0

    for block in ocr_blocks:
        bbox = block.get("bbox", {})
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)
        x2 = bbox.get("x2", 0)
        y2 = bbox.get("y2", 0)

        text_area += max(0, x2 - x1) * max(0, y2 - y1)

    return text_area / image_area


def estimate_non_white_ratio(image_path):
    """
    估算非白色区域比例。
    校徽、地图、图表、照片通常会带来较高非白区域。
    """

    img = cv2.imread(image_path)

    if img is None:
        return 0.0

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 小于245认为不是纯白背景
    non_white = (gray < 245).sum()
    total = gray.shape[0] * gray.shape[1]

    return non_white / max(total, 1)


def detect_visual_element(image_path, ocr_blocks):
    """
    判断是否存在明显非文字图像元素。

    返回：
    {
        "has_visual": bool,
        "reason": "...",
        "text_area_ratio": float,
        "non_white_ratio": float
    }
    """

    if not image_path or not os.path.exists(image_path):
        return {
            "has_visual": False,
            "reason": "未找到图片，默认按纯文本处理",
            "text_area_ratio": 0,
            "non_white_ratio": 0
        }

    text_area_ratio = estimate_text_area_ratio(ocr_blocks, image_path)
    non_white_ratio = estimate_non_white_ratio(image_path)

    # 文本覆盖很少，但非白区域明显，说明可能有图像
    if text_area_ratio < 0.25 and non_white_ratio > 0.18:
        return {
            "has_visual": True,
            "reason": "检测到较大非文本区域，可能包含校徽、地图、图表或图片",
            "text_area_ratio": round(text_area_ratio, 4),
            "non_white_ratio": round(non_white_ratio, 4)
        }

    # 文字不多，非白区域很多，也可能是图像
    if text_area_ratio < 0.4 and non_white_ratio > 0.35:
        return {
            "has_visual": True,
            "reason": "图片中非白区域较多，可能存在图像元素",
            "text_area_ratio": round(text_area_ratio, 4),
            "non_white_ratio": round(non_white_ratio, 4)
        }

    return {
        "has_visual": False,
        "reason": "主要内容为文字，使用文本模型分析",
        "text_area_ratio": round(text_area_ratio, 4),
        "non_white_ratio": round(non_white_ratio, 4)
    }