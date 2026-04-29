import json
import re
from core.llm_client import call_llm_json


def should_use_vl_layout_repair(ocr_result: dict, visual_detection: dict = None):
    """
    判断是否需要调用 qwen-vl-plus 做版面重建。

    只在复杂表格/复杂排版时调用，避免所有图片都变慢。
    """

    layout_type = ocr_result.get("layout_type", "")
    modules = ocr_result.get("modules", [])
    blocks = ocr_result.get("blocks", [])

    # PP-Structure 或普通算法已经判断为表格，优先修复
    if layout_type in ["table_like", "pp_structure"]:
        return True

    # 模块很多，说明排版复杂
    if len(modules) >= 8:
        return True

    # OCR块很多，且目前模块划分很多，也可能是复杂表格/PDF截图
    if len(blocks) >= 25:
        return True

    # 检测到视觉元素，也可以让视觉模型辅助
    if visual_detection and visual_detection.get("has_visual"):
        return True

    return False


def build_structured_text(modules):
    parts = []

    for m in modules:
        module = m.get("module", "识别内容")
        text = m.get("text", "")

        # 规范化机械的表格行模块名，避免输出类似【表格内容行8】这种名字
        if isinstance(module, str):
            if re.search(r"表格.*行\s*\d+|表格内容行\s*\d+|表格行\s*\d+", module):
                module = "表格"

        if text:
            parts.append(f"【{module}】\n{text}")

    return "\n\n".join(parts)


def repair_layout_with_vl(image_path: str, ocr_result: dict):
    """
    使用 qwen-vl-plus 结合图片和 OCR 文本重建排版。

    重点：
    1. 不让它自由发挥
    2. 要求保留原图文字
    3. 表格必须按行列输出
    4. 普通内容按语义模块输出
    """

    raw_text = ocr_result.get("raw_text", "")
    structured_text = ocr_result.get("structured_text", "")
    layout_type = ocr_result.get("layout_type", "")
    modules = ocr_result.get("modules", [])

    prompt = f"""
你是一个OCR版面重建助手。请结合图片视觉布局和OCR识别文本，重建正确排版。

任务：
1. 如果图片是表格，请恢复为按行列排列的表格内容。
2. 如果表格中某个单元格有多行文字，请合并到同一个单元格，不要拆成新的表格行。
3. 如果图片不是表格，请按照真实空间区域和语义模块输出。
4. 不要把全部内容合成一整段。
5. 不要输出“表格内容行1、表格内容行2”这种机械模块名，除非确实是表格行。
6. 不要凭空添加图片中没有的信息。
7. 如果某些文字不清楚，可以写“疑似：xxx”。
8. 输出要适合前端 OCR 区域展示。
9. 只输出 JSON，不要输出解释。

如果是表格，请优先输出这种模块：
{{
  "module": "表格",
  "text": "用 Markdown 表格输出，包含表头和每一行"
}}

如果是普通版面，请输出：
{{
  "module": "模块名称",
  "text": "该模块内容，保留换行"
}}

最终 JSON 格式：
{{
  "layout_type": "table_rebuilt / semantic_layout / mixed_layout",
  "modules": [
    {{
      "module": "模块名称",
      "text": "模块内容"
    }}
  ],
  "structured_text": "最终用于OCR展示的结构化文本"
}}

当前OCR版面类型：
{layout_type}

当前OCR初步模块：
{json.dumps(modules, ensure_ascii=False)}

当前OCR原始文本：
{raw_text}

当前OCR结构化文本：
{structured_text}
"""

    fallback_modules = modules if modules else [
        {
            "module": "OCR识别内容",
            "text": structured_text or raw_text
        }
    ]

    fallback = {
        "layout_type": layout_type or "ocr_layout",
        "modules": fallback_modules,
        "structured_text": build_structured_text(fallback_modules)
    }

    data = call_llm_json(
        prompt=prompt,
        fallback=fallback,
        image_path=image_path
    )

    if not isinstance(data, dict):
        return fallback

    result_modules = data.get("modules", fallback_modules)

    if not isinstance(result_modules, list) or not result_modules:
        result_modules = fallback_modules

    # 如果 LLM 把表格以多个行模块返回（模块名类似“表格内容行1”），合并为单个表格模块
    # 合并所有机械命名的表格模块（例如：表格标题、表格内容行1、表格内容行2）为单个表格模块
    try:
        table_pattern = re.compile(r"表格.*(标题|内容行|行|单元格)\s*\d*$|^表格$", re.I)

        table_parts = []
        table_positions = []

        for i, m in enumerate(result_modules):
            module_name = str(m.get("module", ""))
            if table_pattern.search(module_name):
                table_parts.append(m.get("text", ""))
                table_positions.append(i)

        if table_parts:
            combined_text = "\n".join([p for p in table_parts if p])

            # 构建 new_modules，排除原来的表格分片
            new_modules = [m for idx, m in enumerate(result_modules) if idx not in table_positions]

            # 插入合并后的表格模块，位置选择为第一个表格片段原来的位置或末尾
            insert_pos = table_positions[0] if table_positions else len(new_modules)
            new_modules.insert(insert_pos, {"module": "表格", "text": combined_text})

            result_modules = new_modules
    except Exception:
        pass

    structured = data.get("structured_text")

    if not structured:
        structured = build_structured_text(result_modules)

    return {
        "layout_type": data.get("layout_type", "vl_layout_rebuilt"),
        "modules": result_modules,
        "structured_text": structured
    }