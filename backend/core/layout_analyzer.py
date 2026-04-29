import math


def get_bbox(block):
    return block.get("bbox", {})


def block_center(block):
    bbox = get_bbox(block)
    return (
        (bbox.get("x1", 0) + bbox.get("x2", 0)) / 2,
        (bbox.get("y1", 0) + bbox.get("y2", 0)) / 2
    )


def block_size(block):
    bbox = get_bbox(block)
    return (
        max(1, bbox.get("x2", 0) - bbox.get("x1", 0)),
        max(1, bbox.get("y2", 0) - bbox.get("y1", 0))
    )


def union_bbox(blocks):
    if not blocks:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}

    return {
        "x1": min(get_bbox(b).get("x1", 0) for b in blocks),
        "y1": min(get_bbox(b).get("y1", 0) for b in blocks),
        "x2": max(get_bbox(b).get("x2", 0) for b in blocks),
        "y2": max(get_bbox(b).get("y2", 0) for b in blocks)
    }


def avg_height(blocks):
    if not blocks:
        return 20
    return sum(block_size(b)[1] for b in blocks) / len(blocks)


def vertical_overlap_ratio(a, b):
    """
    判断两个文本框是否在同一行。
    用纵向重叠率，比单纯 y 坐标准。
    """

    abox = get_bbox(a)
    bbox = get_bbox(b)

    y1 = max(abox.get("y1", 0), bbox.get("y1", 0))
    y2 = min(abox.get("y2", 0), bbox.get("y2", 0))

    overlap = max(0, y2 - y1)

    ah = max(1, abox.get("y2", 0) - abox.get("y1", 0))
    bh = max(1, bbox.get("y2", 0) - bbox.get("y1", 0))

    return overlap / min(ah, bh)


def same_line(a, b):
    """
    是否属于同一行：
    1. 纵向重叠明显
    2. 或中心 y 差距很小
    """

    if vertical_overlap_ratio(a, b) >= 0.45:
        return True

    _, ay = block_center(a)
    _, by = block_center(b)

    h = (block_size(a)[1] + block_size(b)[1]) / 2

    return abs(ay - by) <= max(10, h * 0.45)


def group_rows_by_overlap(blocks):
    """
    用纵向重叠率分行。
    适合表格、PPT、多区域截图。
    """

    if not blocks:
        return []

    blocks = sorted(blocks, key=lambda b: get_bbox(b).get("y1", 0))

    rows = []

    for block in blocks:
        placed = False

        for row in rows:
            # 和该行任意一个块属于同一行，就放入
            if any(same_line(block, r) for r in row):
                row.append(block)
                placed = True
                break

        if not placed:
            rows.append([block])

    # 每行内部从左到右
    rows = [
        sorted(row, key=lambda b: get_bbox(b).get("x1", 0))
        for row in rows
    ]

    # 行整体从上到下
    rows = sorted(
        rows,
        key=lambda row: union_bbox(row)["y1"]
    )

    return rows


def row_text(row):
    return " ".join([
        b.get("text", "").strip()
        for b in row
        if b.get("text", "").strip()
    ]).strip()


def detect_table_layout(blocks):
    """
    表格判断增强版：
    支持单元格内部多行文本的表格。
    """

    if not blocks or len(blocks) < 8:
        return False

    small_rows = group_rows_by_overlap(blocks)

    if len(small_rows) < 4:
        return False

    bbox = union_bbox(blocks)
    width = bbox["x2"] - bbox["x1"]

    if width < 400:
        return False

    # 多个小行中有多文本块，说明很可能是表格或多列表
    multi_cell_rows = [r for r in small_rows if len(r) >= 3]

    if len(multi_cell_rows) >= 3:
        return True

    # 如果 x 方向跨度大，且文本块数量多，也可能是无明显表格线的表格
    xs = [block_center(b)[0] for b in blocks]
    x_span = max(xs) - min(xs)

    if x_span > 500 and len(blocks) >= 15:
        return True

    return False

def group_table_rows_with_multiline_cells(blocks):
    """
    表格行分组增强版：
    解决一个表格行中，某些单元格内部有多行文字，导致被误拆成多行的问题。

    核心逻辑：
    1. 先用普通行聚类得到小行
    2. 再根据纵向距离和横向重叠关系，把属于同一个表格大行的小行合并
    """

    small_rows = group_rows_by_overlap(blocks)

    if not small_rows:
        return []

    row_infos = []

    for row in small_rows:
        bbox = union_bbox(row)
        row_infos.append({
            "blocks": row,
            "bbox": bbox,
            "height": bbox["y2"] - bbox["y1"],
            "center_y": (bbox["y1"] + bbox["y2"]) / 2
        })

    avg_row_h = sum(r["height"] for r in row_infos) / max(len(row_infos), 1)

    merged_rows = []
    current = row_infos[0]["blocks"][:]
    current_bbox = row_infos[0]["bbox"]

    for i in range(1, len(row_infos)):
        row = row_infos[i]
        bbox = row["bbox"]

        vertical_gap = bbox["y1"] - current_bbox["y2"]

        # 横向覆盖范围
        current_width = current_bbox["x2"] - current_bbox["x1"]
        row_width = bbox["x2"] - bbox["x1"]

        x_overlap = max(
            0,
            min(current_bbox["x2"], bbox["x2"]) - max(current_bbox["x1"], bbox["x1"])
        )

        min_width = max(1, min(current_width, row_width))
        x_overlap_ratio = x_overlap / min_width

        # 判断是否应合并为同一个表格大行：
        # 1. 两个小行垂直距离很近
        # 2. 横向范围有明显重叠
        # 3. 当前小行不是明显的新完整表格行
        should_merge = (
            vertical_gap <= avg_row_h * 0.75
            and x_overlap_ratio >= 0.45
        )

        if should_merge:
            current.extend(row["blocks"])
            current_bbox = union_bbox(current)
        else:
            merged_rows.append(current)
            current = row["blocks"][:]
            current_bbox = bbox

    if current:
        merged_rows.append(current)

    # 每个大行内部仍然从左到右排序
    final_rows = []

    for row in merged_rows:
        final_rows.append(
            sorted(row, key=lambda b: get_bbox(b).get("x1", 0))
        )

    return final_rows

def build_table_modules(blocks):
    """
    表格版面增强：
    支持一个单元格内多行文本。
    不再把单元格内部换行误判为新的表格行。
    """

    rows = group_table_rows_with_multiline_cells(blocks)

    # 将所有行合并为单个表格模块，避免生成机械命名的行模块名
    row_texts = []
    row_bboxes = []

    for i, row in enumerate(rows):
        if not row:
            continue

        # 按 x 排序
        row = sorted(row, key=lambda b: get_bbox(b).get("x1", 0))

        cells = []
        for b in row:
            text = b.get("text", "").strip()
            if text:
                cells.append(text)

        if not cells:
            continue

        row_texts.append(" | ".join(cells))
        row_bboxes.append(union_bbox(row))

    if not row_texts:
        return []

    # 合并为单个表格模块，文本按行换行
    combined_text = "\n".join(row_texts)

    modules = [{
        "module": "表格",
        "text": combined_text,
        "rows": row_texts,
        "row_bboxes": row_bboxes,
        "bbox": union_bbox(blocks),
        "blocks": blocks
    }]

    return modules


def bbox_distance(a, b):
    abox = get_bbox(a)
    bbox = get_bbox(b)

    dx = max(
        abox.get("x1", 0) - bbox.get("x2", 0),
        bbox.get("x1", 0) - abox.get("x2", 0),
        0
    )

    dy = max(
        abox.get("y1", 0) - bbox.get("y2", 0),
        bbox.get("y1", 0) - abox.get("y2", 0),
        0
    )

    return math.sqrt(dx * dx + dy * dy)


def estimate_region_threshold(blocks):
    h = avg_height(blocks)
    return max(70, h * 4.5)


def cluster_blocks_by_space(blocks):
    """
    空间区域聚类。
    适合：
    - 左上角一块
    - 右上角一块
    - 中间一块
    - 底部一块
    """

    if not blocks:
        return []

    threshold = estimate_region_threshold(blocks)

    n = len(blocks)
    visited = [False] * n
    regions = []

    for i in range(n):
        if visited[i]:
            continue

        queue = [i]
        visited[i] = True
        region = []

        while queue:
            idx = queue.pop(0)
            region.append(blocks[idx])

            for j in range(n):
                if visited[j]:
                    continue

                if bbox_distance(blocks[idx], blocks[j]) <= threshold:
                    visited[j] = True
                    queue.append(j)

        regions.append(region)

    return regions


def split_columns_if_needed(region):
    """
    如果一个区域明显是左右两栏，拆成左右栏。
    """

    if len(region) < 6:
        return [region]

    bbox = union_bbox(region)
    width = bbox["x2"] - bbox["x1"]

    if width < 500:
        return [region]

    centers = sorted([block_center(b)[0] for b in region])

    gaps = []
    for i in range(len(centers) - 1):
        gaps.append((centers[i + 1] - centers[i], i))

    if not gaps:
        return [region]

    max_gap, idx = max(gaps, key=lambda x: x[0])

    # 最大横向空隙足够大，认为是两栏
    if max_gap < width * 0.18:
        return [region]

    split_x = (centers[idx] + centers[idx + 1]) / 2

    left = [b for b in region if block_center(b)[0] < split_x]
    right = [b for b in region if block_center(b)[0] >= split_x]

    if len(left) < 2 or len(right) < 2:
        return [region]

    return [left, right]


def sort_regions(regions):
    """
    区域排序：
    先上后下，同一高度左到右。
    """

    return sorted(
        regions,
        key=lambda r: (
            union_bbox(r)["y1"],
            union_bbox(r)["x1"]
        )
    )


def detect_region_type(region):
    text = "\n".join([b.get("text", "") for b in region])
    count = len(region)
    bbox = union_bbox(region)

    width = bbox["x2"] - bbox["x1"]
    height = bbox["y2"] - bbox["y1"]

    if count == 1 and len(text) <= 35:
        return "标题/短文本区域"

    if width > height * 2 and count <= 3:
        return "横向信息区域"

    return "文本内容区域"


def build_region_modules(blocks):
    """
    普通/多区域版面恢复。
    """

    regions = cluster_blocks_by_space(blocks)

    # 如果聚类过碎，说明它可能是连续文本
    if len(regions) > len(blocks) * 0.7:
        regions = [blocks]

    # 二次处理：大区域可能是左右栏
    final_regions = []

    for region in regions:
        final_regions.extend(split_columns_if_needed(region))

    modules = []

    for i, region in enumerate(sort_regions(final_regions)):
        rows = group_rows_by_overlap(region)

        text_lines = []

        sorted_blocks = []

        for row in rows:
            t = row_text(row)
            if t:
                text_lines.append(t)
            sorted_blocks.extend(row)

        region_text = "\n".join(text_lines)

        if not region_text.strip():
            continue

        module_type = detect_region_type(sorted_blocks)

        modules.append({
            "module": f"{module_type}{i + 1}",
            "text": region_text,
            "blocks": sorted_blocks,
            "bbox": union_bbox(sorted_blocks)
        })

    return modules


def build_structured_text(modules):
    parts = []

    for module in modules:
        name = module.get("module", "识别区域")
        text = module.get("text", "").strip()

        if text:
            parts.append(f"【{name}】\n{text}")

    return "\n\n".join(parts)


def analyze_layout(blocks):
    """
    OCR版面恢复主函数。
    """

    if not blocks:
        return {
            "layout_type": "unknown",
            "sorted_blocks": [],
            "modules": [],
            "structured_text": ""
        }

    # 1. 表格优先
    if detect_table_layout(blocks):
        modules = build_table_modules(blocks)
        layout_type = "table_like"
    else:
        modules = build_region_modules(blocks)
        layout_type = "region_cluster"

    sorted_blocks = []

    for m in modules:
        sorted_blocks.extend(m.get("blocks", []))

    structured_text = build_structured_text(modules)

    return {
        "layout_type": layout_type,
        "sorted_blocks": sorted_blocks,
        "modules": modules,
        "structured_text": structured_text
    }