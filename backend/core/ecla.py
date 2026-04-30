import math
from collections import defaultdict


def _bbox_to_rect(bbox):
    """
    PaddleOCR bbox:
    [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    转成 x1,y1,x2,y2,w,h,cx,cy
    """
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]

    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)

    w = max(x2 - x1, 1)
    h = max(y2 - y1, 1)

    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "w": w,
        "h": h,
        "cx": (x1 + x2) / 2,
        "cy": (y1 + y2) / 2,
    }


def normalize_ocr_blocks(raw_blocks):
    """
    统一 OCR block 格式。
    输入 block 至少包含：
    {
        text,
        bbox,
        score,
        page
    }
    """
    blocks = []

    for i, item in enumerate(raw_blocks):
        text = str(item.get("text", "")).strip()
        bbox = item.get("bbox")
        score = float(item.get("score", 1.0))
        page = int(item.get("page", 1))

        if not text or not bbox:
            continue

        rect = _bbox_to_rect(bbox)

        blocks.append({
            "id": i,
            "text": text,
            "bbox": bbox,
            "score": score,
            "page": page,
            **rect
        })

    return blocks


def group_lines(blocks, y_threshold_ratio=0.6):
    """
    按 y 坐标把 OCR 文本块合并成行。
    解决同一行文字被 PaddleOCR 拆成多个块的问题。
    """
    if not blocks:
        return []

    blocks = sorted(blocks, key=lambda b: (b["page"], b["cy"], b["x1"]))

    pages = defaultdict(list)
    for b in blocks:
        pages[b["page"]].append(b)

    all_lines = []

    for page, page_blocks in pages.items():
        lines = []

        for block in page_blocks:
            placed = False
            block_h = block["h"]

            for line in lines:
                line_cy = line["cy"]
                line_h = line["avg_h"]
                threshold = max(block_h, line_h) * y_threshold_ratio

                if abs(block["cy"] - line_cy) <= threshold:
                    line["blocks"].append(block)
                    line["cy"] = sum(x["cy"] for x in line["blocks"]) / len(line["blocks"])
                    line["avg_h"] = sum(x["h"] for x in line["blocks"]) / len(line["blocks"])
                    placed = True
                    break

            if not placed:
                lines.append({
                    "page": page,
                    "cy": block["cy"],
                    "avg_h": block["h"],
                    "blocks": [block]
                })

        for line in lines:
            line_blocks = sorted(line["blocks"], key=lambda b: b["x1"])
            text = " ".join(b["text"] for b in line_blocks)

            x1 = min(b["x1"] for b in line_blocks)
            y1 = min(b["y1"] for b in line_blocks)
            x2 = max(b["x2"] for b in line_blocks)
            y2 = max(b["y2"] for b in line_blocks)

            all_lines.append({
                "page": page,
                "text": text.strip(),
                "blocks": line_blocks,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "w": x2 - x1,
                "h": y2 - y1,
                "cx": (x1 + x2) / 2,
                "cy": (y1 + y2) / 2,
                "score": sum(b["score"] for b in line_blocks) / len(line_blocks)
            })

    return sorted(all_lines, key=lambda l: (l["page"], l["y1"], l["x1"]))


def detect_columns(lines):
    """
    简单判断单栏/双栏。
    如果页面中文字 x 分布明显分成左右两组，则按栏排序。
    """
    if not lines:
        return lines

    pages = defaultdict(list)
    for line in lines:
        pages[line["page"]].append(line)

    ordered = []

    for page, page_lines in pages.items():
        if len(page_lines) < 6:
            ordered.extend(sorted(page_lines, key=lambda l: (l["y1"], l["x1"])))
            continue

        min_x = min(l["x1"] for l in page_lines)
        max_x = max(l["x2"] for l in page_lines)
        page_width = max(max_x - min_x, 1)
        mid_x = min_x + page_width / 2

        left = [l for l in page_lines if l["cx"] < mid_x]
        right = [l for l in page_lines if l["cx"] >= mid_x]

        # 双栏判断：左右都有较多内容
        if len(left) >= 3 and len(right) >= 3:
            left_sorted = sorted(left, key=lambda l: (l["y1"], l["x1"]))
            right_sorted = sorted(right, key=lambda l: (l["y1"], l["x1"]))
            ordered.extend(left_sorted + right_sorted)
        else:
            ordered.extend(sorted(page_lines, key=lambda l: (l["y1"], l["x1"])))

    return ordered


def classify_line(line, avg_h):
    """
    轻量版面语义分类：
    title / heading / paragraph / list / table_like / note
    """
    text = line["text"].strip()
    h = line["h"]

    if not text:
        return "empty"

    if len(text) <= 30 and h >= avg_h * 1.35:
        return "title"

    if text.startswith(("一、", "二、", "三、", "四、", "五、", "1.", "2.", "3.", "（1）", "(1)", "1、")):
        return "heading"

    if text.startswith(("-", "·", "•", "*", "①", "②", "③")):
        return "list"

    # 表格类：短文本、多数字、符号密集
    digit_count = sum(c.isdigit() for c in text)
    symbol_count = sum(c in "|:-—_.,，。;；/\\%" for c in text)
    if digit_count >= 3 and symbol_count >= 2:
        return "table_like"

    if any(k in text for k in ["备注", "说明", "注：", "注意", "提示"]):
        return "note"

    return "paragraph"


def build_modules(lines):
    """
    将行进一步组织成模块。
    """
    if not lines:
        return []

    avg_h = sum(l["h"] for l in lines) / max(len(lines), 1)

    modules = []
    current = None

    for line in lines:
        line_type = classify_line(line, avg_h)
        line["type"] = line_type

        # 标题/小标题单独开模块
        if line_type in ["title", "heading"]:
            if current:
                modules.append(current)

            current = {
                "type": line_type,
                "title": line["text"],
                "page": line["page"],
                "lines": [line]
            }
            continue

        # 表格类单独聚合
        if line_type == "table_like":
            if current and current["type"] == "table_like":
                current["lines"].append(line)
            else:
                if current:
                    modules.append(current)
                current = {
                    "type": "table_like",
                    "title": "表格/数据区域",
                    "page": line["page"],
                    "lines": [line]
                }
            continue

        # 普通正文
        if current is None:
            current = {
                "type": "paragraph",
                "title": "正文内容",
                "page": line["page"],
                "lines": [line]
            }
        else:
            current["lines"].append(line)

    if current:
        modules.append(current)

    return modules


def modules_to_structured_text(modules):
    """
    输出结构化文本，给 AI 总结和知识图谱使用。
    """
    parts = []

    for i, module in enumerate(modules, start=1):
        mtype = module.get("type", "paragraph")
        title = module.get("title", f"模块{i}")
        page = module.get("page", 1)

        if mtype == "title":
            header = f"【第{page}页-标题】"
        elif mtype == "heading":
            header = f"【第{page}页-章节】"
        elif mtype == "table_like":
            header = f"【第{page}页-表格/数据区域】"
        elif mtype == "note":
            header = f"【第{page}页-说明】"
        else:
            header = f"【第{page}页-正文模块{i}】"

        content = "\n".join(line["text"] for line in module["lines"] if line["text"].strip())

        parts.append(f"{header}\n{content}")

    return "\n\n".join(parts).strip()


def ecla_enhance(raw_blocks):
    """
    ECLA 主入口：
    OCR blocks -> 行合并 -> 多栏排序 -> 模块构建 -> 结构化文本
    """
    blocks = normalize_ocr_blocks(raw_blocks)
    lines = group_lines(blocks)
    ordered_lines = detect_columns(lines)
    modules = build_modules(ordered_lines)
    structured_text = modules_to_structured_text(modules)

    raw_text = "\n".join(line["text"] for line in ordered_lines)

    return {
        "raw_text": raw_text,
        "structured_text": structured_text,
        "blocks": blocks,
        "lines": ordered_lines,
        "modules": modules
    }