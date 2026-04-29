import cv2
import os


def create_ocr_variants(image_path: str):
    """
    生成多个OCR增强版本：
    1. 原图
    2. 灰度增强图
    3. 锐化图
    4. 二值化图

    作用：
    - 提高手写/模糊文字识别概率
    - 减少边缘漏识别
    """

    img = cv2.imread(image_path)

    if img is None:
        return [image_path]

    variants = [image_path]

    # 增加白边，防止边缘文字漏识别
    img = cv2.copyMakeBorder(
        img,
        40, 40, 40, 40,
        cv2.BORDER_CONSTANT,
        value=[255, 255, 255]
    )

    # 放大图片
    h, w = img.shape[:2]
    if max(h, w) < 1800:
        img = cv2.resize(
            img,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC
        )

    base, _ = os.path.splitext(image_path)

    # 灰度 + 对比度增强
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )
    enhanced = clahe.apply(gray)

    enhanced_path = base + "_ocr_enhanced.jpg"
    cv2.imwrite(enhanced_path, enhanced)
    variants.append(enhanced_path)

    # 锐化，适合手写边缘较虚的情况
    blur = cv2.GaussianBlur(enhanced, (0, 0), 3)
    sharpened = cv2.addWeighted(enhanced, 1.6, blur, -0.6, 0)

    sharpened_path = base + "_ocr_sharpened.jpg"
    cv2.imwrite(sharpened_path, sharpened)
    variants.append(sharpened_path)

    # 自适应二值化，适合黑白手写、拍照阴影
    binary = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10
    )

    binary_path = base + "_ocr_binary.jpg"
    cv2.imwrite(binary_path, binary)
    variants.append(binary_path)

    return variants



def add_safe_padding(image_path: str, padding: int = 60):
    """
    给图片四周加白边，解决顶部/边缘文字漏识别问题。
    不改变原图内容，只生成一个临时 padded 图片。
    """

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)

    if img is None:
        return image_path

    # 4通道转3通道
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
    out_path = base + "_padded.jpg"

    cv2.imwrite(out_path, padded)

    return out_path