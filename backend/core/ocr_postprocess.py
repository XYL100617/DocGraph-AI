import re


def chinese_ratio(text: str) -> float:
    if not text:
        return 0.0

    chinese_chars = re.findall(r"[\u4e00-\u9fa5]", text)
    return len(chinese_chars) / max(len(text), 1)


def symbol_ratio(text: str) -> float:
    if not text:
        return 0.0

    symbols = re.findall(r"[^\u4e00-\u9fa5A-Za-z0-9]", text)
    return len(symbols) / max(len(text), 1)


def is_noise_block(block: dict) -> bool:
    """
    更保守的噪声过滤：
    不轻易删除中文、英文单词、数字编号。
    只删除明显乱码。
    """

    text = block.get("text", "").strip()
    confidence = float(block.get("confidence", 0))

    if not text:
        return True

    # 有中文，尽量保留，即使置信度偏低
    if chinese_ratio(text) > 0:
        return False

    # 有较长英文/数字内容，保留，比如 URL、API、Step、Python
    if len(text) >= 3 and re.search(r"[A-Za-z0-9]", text):
        return False

    # 纯标点符号，删除
    if re.fullmatch(r"[\.\,\:\;\+\-\*\/\?\!\|\s、，。：；]+", text):
        return True

    # 单个非中文字符，且置信度低，删除
    if len(text) == 1 and confidence < 0.75:
        return True

    # 符号占比过高，且没有明显字母数字，删除
    if symbol_ratio(text) > 0.6 and not re.search(r"[A-Za-z0-9]", text):
        return True

    return False


def clean_text(text: str) -> str:
    text = text.strip()

    # 合并多余空格
    text = re.sub(r"\s+", " ", text)

    # 删除连续无意义符号
    text = re.sub(r"[\.\,\:\;\|\+\*\/]{2,}", " ", text)

    return text.strip()


def mark_text_type(block: dict) -> dict:
    text = block.get("text", "")
    confidence = float(block.get("confidence", 0))

    if chinese_ratio(text) > 0.6 and len(text) <= 20:
        block["text_type"] = "handwriting_or_short_chinese"
    elif re.search(r"[=+\-*/×÷]", text):
        block["text_type"] = "formula_or_symbol"
    elif confidence < 0.7:
        block["text_type"] = "low_confidence"
    else:
        block["text_type"] = "normal_text"

    block["low_confidence"] = confidence < 0.7

    return block


def postprocess_ocr_blocks(blocks: list) -> list:
    """
    OCR后处理：
    1. 过滤乱码噪声
    2. 清洗文本
    3. 标记低置信度和文本类型
    """

    processed = []

    for block in blocks:
        if is_noise_block(block):
            continue

        block["text"] = clean_text(block.get("text", ""))

        if not block["text"]:
            continue

        block = mark_text_type(block)
        processed.append(block)

    return processed


def build_clean_text(blocks: list) -> str:
    return "\n".join([
        b.get("text", "")
        for b in blocks
        if b.get("text")
    ])

def clean_for_llm(text: str):
    text = text or ""

    lines = text.split("\n")
    clean_lines = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # 过滤纯数字/乱码行
        if re.fullmatch(r"[0-9\.\,\?\!\s]+", line):
            continue

        # 过滤过短噪声
        if len(line) <= 1:
            continue

        clean_lines.append(line)

    text = "\n".join(clean_lines)

    # 恢复部分断裂空格
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" ，", "，").replace(" 。", "。")

    return text.strip()