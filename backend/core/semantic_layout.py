import json
from core.llm_client import call_llm_json


def fallback_modules(region_texts: list):
    modules = []

    for i, text in enumerate(region_texts):
        modules.append({
            "module": f"识别区域{i + 1}",
            "text": text
        })

    return modules


def auto_classify_modules(layout_type: str, region_texts: list):
    """
    使用千问自动识别 OCR 区域模块。
    """

    if not region_texts:
        return []

    prompt = f"""
你是一个OCR版面结构分析助手。

请根据OCR识别得到的多个文本区域，自动判断每个区域属于什么模块，并重新组织输出。

要求：
1. 根据内容语义自动命名模块。
2. 不要使用固定模板，不要输出“表格第几行”。
3. 不要把所有内容合并成一整段。
4. 不要删除有效信息。
5. 模块名要简洁，例如“标题”“知识点”“公式”“步骤”“结论”等，但不要局限于这些。
6. 如果无法判断，使用“未分类内容”。
7. 只输出JSON。

输出格式：
{{
  "modules": [
    {{
      "module": "模块名称",
      "text": "模块内容"
    }}
  ]
}}

版面类型：
{layout_type}

OCR区域文本：
{json.dumps(region_texts, ensure_ascii=False)}
"""

    fallback = {
        "modules": fallback_modules(region_texts)
    }

    data = call_llm_json(prompt, fallback=fallback)

    modules = data.get("modules", [])

    if isinstance(modules, list) and modules:
        return modules

    return fallback_modules(region_texts)