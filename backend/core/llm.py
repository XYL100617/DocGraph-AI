import json
import re

from core.ocr_postprocess import clean_for_llm
from core.llm_client import call_llm_json
from core.fallback_graph_extract import fallback_graph_extract
from core.llm_client import call_summary_json
from core.local_extractor import local_extract

try:
    from ltp import LTP
except Exception:
    LTP = None


_ltp_model = None

VALID_ENTITY_TYPES = [
    "人物", "时间", "地点", "对象", "事件", "组织",
    "主题", "方法", "结果", "概念", "文件", "其他"
]
VALID_RELATIONS = ["提出", "描述", "包含", "属于", "影响", "导致", "服务于", "体现", "关联", "参与", "负责", "使用", "生成"]


def get_ltp_model():
    """
    LTP 懒加载。
    LTP 加载失败不影响主流程，自动降级。
    """
    global _ltp_model

    if LTP is None:
        return None

    if _ltp_model is None:
        try:
            _ltp_model = LTP()
        except Exception as e:
            print("LTP加载失败，跳过LTP辅助：", e)
            _ltp_model = False

    return _ltp_model if _ltp_model is not False else None


def limit_text_for_llm(text: str, max_chars: int = 5000):
    """
    限制输入长度，防止 LLM 响应慢、token 消耗过高。
    """
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return text[:2500] + "\n\n......中间内容过长，已省略......\n\n" + text[-2500:]


def split_sentences(text: str):
    text = text or ""
    parts = re.split(r"[。！？；;\n]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def is_short_text(text: str, max_len: int = 60):
    pure = re.sub(r"[，,。！？；;\n\s]+", "", text or "")
    return bool(pure) and len(pure) <= max_len


def get_text_profile(text: str):
    """
    给 LLM 的文本特征提示，不直接决定结果。
    """
    text = text or ""
    pure = re.sub(r"[，,。！？；;\n\s]+", "", text)

    profile = {
        "is_short_text": len(pure) <= 60 if pure else False,
        "pure_length": len(pure),
        "line_count": len([l for l in text.split("\n") if l.strip()]),
        "has_chinese": bool(re.search(r"[\u4e00-\u9fa5]", text)),
        "has_punctuation": bool(re.search(r"[，,。！？；;]", text)),
    }

    return profile


def extract_ltp_entities(text: str):
    """
    LTP 只做基础候选实体，不负责最终语义关系。
    """
    model = get_ltp_model()

    if model is None:
        return []

    sentences = split_sentences(text)[:20]

    if not sentences:
        return []

    try:
        seg, hidden = model.seg(sentences)
        ner = model.ner(hidden)
    except Exception as e:
        print("LTP识别失败：", e)
        return []

    tag_map = {
        "Nh": "人物",
        "Ni": "组织",
        "Ns": "地点"
    }

    entity_map = {}

    for sent_index, items in enumerate(ner):
        words = seg[sent_index]

        for item in items:
            try:
                tag, start, end = item
                name = "".join(words[start:end + 1]).strip()
                etype = tag_map.get(tag, "主题")
            except Exception:
                continue

            if len(name) < 2:
                continue

            entity_map[name] = {
                "name": name,
                "type": etype,
                "description": f"LTP识别的{etype}候选实体",
                "source": "ltp"
            }

    return list(entity_map.values())


def extract_ltp_words(text: str, max_words: int = 30):
    """
    LTP 分词候选。
    用于短句、歌词、标题、格言等输入时给 LLM 参考。
    """
    model = get_ltp_model()

    if model is None:
        return []

    sentences = split_sentences(text)[:10]

    if not sentences:
        return []

    try:
        seg, _ = model.seg(sentences)
    except Exception as e:
        print("LTP分词失败：", e)
        return []

    words = []

    for sent_words in seg:
        for w in sent_words:
            w = str(w).strip()
            if len(w) >= 2 and w not in words:
                words.append(w)

            if len(words) >= max_words:
                break

        if len(words) >= max_words:
            break

    return words


def build_ltp_context(ltp_entities, ltp_words=None):
    lines = []

    if ltp_entities:
        lines.append("LTP候选实体：")
        for e in ltp_entities:
            lines.append(f"- {e.get('name')}：{e.get('type', '主题')}")

    if ltp_words:
        lines.append("LTP候选词语：")
        lines.append("、".join(ltp_words))

    return "\n".join(lines) if lines else "无"


def fallback_analyze_text(text: str):
    fallback = fallback_graph_extract(text or "")
    fallback.setdefault("repaired_text", text or "")
    fallback.setdefault("modules", [{"module": "识别内容", "text": text or ""}])
    fallback.setdefault("visual_notes", [])
    return fallback


def build_ai_prompt(
    text: str,
    ltp_entities=None,
    ltp_words=None,
    is_ocr=False,
    has_visual=False,
    visual_reason="",
    layout_type="",
    modules=None
):
    ltp_context = build_ltp_context(ltp_entities or [], ltp_words or [])
    text_profile = get_text_profile(text)

    ocr_note = (
        "输入可能来自OCR，可能存在错别字、漏字、断句错误，请先在 repaired_text 中修复明显错误，再基于 repaired_text 分析。"
        if is_ocr else ""
    )

    visual_note = (
        "如存在非文字视觉元素，OCR文本为主，视觉元素只作为补充，不要覆盖文字内容。"
        if has_visual else ""
    )

    return f"""
你是一个结合 LTP 候选词、候选实体与大模型语义理解的知识图谱抽取助手。

任务：从文本中输出可用于知识图谱的 JSON。

重要规则：
1. 只输出 JSON，不要解释。
2. LTP 结果只是候选信息，不一定完全正确。你要结合原文语义判断。
3. LTP 已识别的人物/组织/地点应优先保留，除非明显错误。
4. 实体类型只能从以下8类选择：
人物、组织、地点、时间、事件、对象、主题、其他

实体分类规则：
1. 人名、作者、角色、行为主体 → 人物
2. 日期、年代、时间段、上午、下午 → 时间
3. 国家、城市、地区、地点、场所 → 地点
4. 系统、平台、模块、组件、工具、设备、物品 → 对象
5. 动作、行为、任务、会议、活动、问题、错误、异常、过程、现象 → 事件
6. 公司、学校、团队、机构、部门、组织名称 → 组织
7. 思想、观点、精神、价值、主题、情绪、意象、主义 → 主题
8. 方法、算法、技术路线、策略、机制、流程、方案 → 方法
9. 结果、输出、结论、效果、成果、报告、摘要 → 结果
10. 概念、理论、原理、定义、知识点、学科术语 → 概念
11. 文件、文档、图片、PDF、表格、代码文件、数据文件 → 文件
12. 无法判断 → 其他

关系类型只能从以下选择：
提出、描述、包含、属于、影响、导致、服务于、体现、关联、参与、负责、使用、生成

关系规则：
1. “使用、采用、用于、应用于”必须归为“使用”，不要归为“包含”。
2. “因为、导致、造成、引起、使得”优先归为“导致”。
3. “体现、反映、表达、象征”优先归为“体现”或“描述”。
4. “由……组成、包括、包含”归为“包含”。
5. “某人做某事”优先抽取为：人物 --参与--> 事件。
6. relations 中的 source 和 target 必须来自 entities.name。
7. 如果关系不确定，使用“关联”，不要滥用“属于/包含”。

短文本专门规则：
如果输入文本较短，例如普通短句、名言、诗句、歌词、口号、标题、课堂笔记短语，不要只生成一个整体节点。
你必须先判断文本类型，再抽取对应结构：

A. 普通行为句：
例如“小红喝水”“学生学习算法”“老师讲课”
应抽取人物/对象/行为/动作关系。
示例：小红 --参与--> 喝水。

B. 名言/格言/口号：
例如“厚德载物”“知行合一”“为天地立心”
应抽取核心意象、行为、抽象主题，但不要强行拔高每个普通句子。
示例：厚德、载物、道德修养、包容承载。

C. 歌词/诗句：
应抽取意象、情绪、人物、事件、主题，不要逐字机械建图。
示例：月亮、思念、离别、故乡。

D. 标题/短语：
应抽取主题、对象、方法、结果等结构化节点。

E. 如果短文本只有一个明显实体，也要补充其动作、属性、主题或语义类别。
短文本尽量输出至少 3 个实体和 2 条关系，但不要编造与原文完全无关的内容。

summary 规则：
1. summary 必须根据文本真实含义生成。
2. 不要固定写“价值追求”“核心主题”等套话。
3. 普通行为句就描述行为。
4. 名言/诗句/歌词才总结其意象、情绪或思想。
5. 技术文本就总结技术内容。

{ocr_note}
{visual_note}

文本特征：
{json.dumps(text_profile, ensure_ascii=False)}

LTP候选：
{ltp_context}

版面类型：
{layout_type}

OCR/版面模块：
{json.dumps(modules or [], ensure_ascii=False)}

输出JSON格式：
{{
  "repaired_text": "纠错或整理后的文本",
  "modules": [
    {{"module": "模块名称", "text": "模块内容"}}
  ],
  "summary": "不超过150字摘要",
  "text_type": "普通行为句/名言格言/诗句歌词/标题短语/技术说明/文档内容/其他",
  "entities": [
    {{"name": "实体名称", "type": "人物/组织/地点/时间/事件/对象/主题/其他", "description": "简短说明"}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型", "confidence": 0.85}}
  ],
  "keywords": ["关键词1", "关键词2"],
  "visual_notes": ["视觉补充说明"]
}}

文本内容：
{text}
"""


def is_bad_result(result):
    entities = result.get("entities", [])
    relations = result.get("relations", [])

    if not entities:
        return True

    valid_entities = [
        e for e in entities
        if isinstance(e, dict) and e.get("name")
    ]

    if not valid_entities:
        return True

    types = {str(e.get("type", "")).strip() for e in valid_entities}

    if types and types.issubset({"其他"}):
        return True

    return False


def is_weak_short_text_graph(result, source_text):
    """
    判断短文本图谱是否过弱。
    如果 LLM 只给了一个整体节点，或者实体少但没有关系，就用 fallback 补。
    """
    pure = re.sub(r"[，,。！？；;\n\s]+", "", source_text or "")

    if not pure or len(pure) > 60:
        return False

    entities = [
        e for e in result.get("entities", [])
        if isinstance(e, dict) and e.get("name")
    ]

    relations = [
        r for r in result.get("relations", [])
        if isinstance(r, dict) and r.get("source") and r.get("target")
    ]

    if len(entities) <= 1:
        return True

    if len(entities) <= 2 and len(relations) == 0:
        return True

    # 只有一个整体节点 + 一个无意义片段，也算弱
    names = [e["name"] for e in entities]
    if pure in names and len(entities) <= 2 and len(relations) <= 1:
        return True

    return False


def normalize_entity_item(e):
    if isinstance(e, str):
        name = e.strip()
        return {
            "name": name,
            "type": "主题",
            "description": "",
            "source": "ai"
        } if name else None

    if not isinstance(e, dict):
        return None

    name = str(e.get("name") or e.get("id") or "").strip()

    if not name:
        return None

    etype = str(e.get("type", "主题")).strip()

    if etype not in VALID_ENTITY_TYPES:
        etype = "主题"

    return {
        "name": name,
        "type": etype,
        "description": e.get("description", ""),
        "source": e.get("source", "ai")
    }


def normalize_relation_item(r):
    if not isinstance(r, dict):
        return None

    source = r.get("source") or r.get("from")
    target = r.get("target") or r.get("to")

    if not source or not target:
        return None

    source = str(source).strip()
    target = str(target).strip()

    if not source or not target or source == target:
        return None

    relation = str(r.get("relation") or r.get("type") or "关联").strip()

    if relation not in VALID_RELATIONS:
        relation = "关联"

    try:
        confidence = float(r.get("confidence", 0.7))
    except Exception:
        confidence = 0.7

    confidence = max(0.0, min(confidence, 1.0))

    return {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": confidence,
        "raw_relation": r.get("raw_relation") or r.get("relation") or r.get("type") or "关联"
    }


def merge_extract_results(local_result, ai_result):
    """
    合并 fallback 和 AI 结果。
    AI 优先，fallback 补充弱图谱。
    """
    entity_map = {}

    for e in local_result.get("entities", []) + ai_result.get("entities", []):
        item = normalize_entity_item(e)
        if not item:
            continue

        old = entity_map.get(item["name"])

        if not old:
            entity_map[item["name"]] = item
        else:
            # 更具体的类型覆盖宽泛类型
            if old.get("type") in {"对象", "主题", "其他"} and item.get("type") not in {"对象", "主题", "其他"}:
                old["type"] = item["type"]

            # AI 描述优先补充
            if not old.get("description") and item.get("description"):
                old["description"] = item["description"]

            # 来源保留
            if old.get("source") != "ai" and item.get("source") == "ai":
                old["source"] = "ai"

    relations = []
    seen = set()

    for r in local_result.get("relations", []) + ai_result.get("relations", []):
        item = normalize_relation_item(r)
        if not item:
            continue

        key = (item["source"], item["target"], item["relation"])

        if key in seen:
            continue

        # 关系两端必须在实体中，不在就补实体
        if item["source"] not in entity_map:
            entity_map[item["source"]] = {
                "name": item["source"],
                "type": "主题",
                "description": "由关系自动补充的实体",
                "source": "relation_auto"
            }

        if item["target"] not in entity_map:
            entity_map[item["target"]] = {
                "name": item["target"],
                "type": "主题",
                "description": "由关系自动补充的实体",
                "source": "relation_auto"
            }

        seen.add(key)
        relations.append(item)

    keywords = []

    for k in local_result.get("keywords", []) + ai_result.get("keywords", []):
        if isinstance(k, str) and k.strip() and k.strip() not in keywords:
            keywords.append(k.strip())

    return {
        "repaired_text": ai_result.get("repaired_text") or local_result.get("repaired_text", ""),
        "modules": ai_result.get("modules") or local_result.get("modules", []),
        "summary": ai_result.get("summary") or local_result.get("summary", ""),
        "text_type": ai_result.get("text_type") or local_result.get("text_type", "其他"),
        "entities": list(entity_map.values()),
        "relations": relations,
        "keywords": keywords,
        "visual_notes": ai_result.get("visual_notes") or local_result.get("visual_notes", []),
        "source": "ltp_ai_fallback_merge"
    }


def normalize_ai_result(data, fallback, source_text=None, ltp_entities=None):
    if not isinstance(data, dict):
        result = fallback_graph_extract(source_text or "")
        result["ltp_entities"] = ltp_entities or []
        return result

    entities = []

    for e in data.get("entities", fallback.get("entities", [])):
        item = normalize_entity_item(e)
        if item:
            entities.append(item)

    # LTP 候选实体补充进去
    name_set = {e["name"] for e in entities}

    for e in ltp_entities or []:
        if e.get("name") and e["name"] not in name_set:
            entities.append(e)
            name_set.add(e["name"])

    relations = []

    for r in data.get("relations", fallback.get("relations", [])):
        item = normalize_relation_item(r)
        if item:
            relations.append(item)

    modules = data.get("modules", fallback.get("modules", []))
    if not isinstance(modules, list):
        modules = fallback.get("modules", [])

    keywords = data.get("keywords", fallback.get("keywords", []))
    if not isinstance(keywords, list):
        keywords = fallback.get("keywords", [])

    visual_notes = data.get("visual_notes", fallback.get("visual_notes", []))
    if not isinstance(visual_notes, list):
        visual_notes = []

    result = {
        "repaired_text": data.get("repaired_text", fallback.get("repaired_text", source_text or "")),
        "modules": modules,
        "summary": str(data.get("summary", fallback.get("summary", "")))[:200],
        "text_type": data.get("text_type", fallback.get("text_type", "其他")),
        "entities": entities,
        "relations": relations,
        "keywords": keywords,
        "visual_notes": visual_notes,
        "ltp_entities": ltp_entities or [],
        "source": "ai"
    }

    if is_bad_result(result):
        print("⚠️ AI抽取质量低，使用 fallback_graph_extract")
        fallback_result = fallback_graph_extract(source_text or "")
        fallback_result["ltp_entities"] = ltp_entities or []
        return fallback_result

    if is_weak_short_text_graph(result, source_text):
        print("⚠️ 短文本图谱过弱，使用 fallback 补充")
        fallback_result = fallback_graph_extract(source_text or "")
        result = merge_extract_results(fallback_result, result)
        result["ltp_entities"] = ltp_entities or []

    return result


def analyze_text(text: str):
    text = clean_for_llm(text or "")
    text = limit_text_for_llm(text)

    ltp_entities = extract_ltp_entities(text)
    ltp_words = extract_ltp_words(text)

    prompt = build_ai_prompt(
        text,
        ltp_entities=ltp_entities,
        ltp_words=ltp_words,
        is_ocr=False
    )

    fallback = fallback_analyze_text(text)
    data = call_llm_json(prompt, fallback=fallback)
    ai_result = normalize_ai_result(
        data,
        fallback,
        text,
        ltp_entities=ltp_entities
    )

    # 保留原文，给后面的关系修正使用
    ai_result["repaired_text"] = ai_result.get("repaired_text") or text
    ai_result["source_text"] = text

    # 只有图谱太弱时才启用本地补图，避免本地共现关系乱连
    if is_graph_weak(ai_result):
        print("⚠️ 图谱较弱，启用 local_extractor 补充")
        local_result = local_extract(text)
        merged = merge_extract_results(local_result, ai_result)
        merged["repaired_text"] = text
        merged["source_text"] = text
        return merged

    return ai_result

def graph_deep_extract(text: str):
    """
    图谱专用深度抽取：
    只做深度总结 + 实体关系抽取。
    不做OCR版面修复、不做视觉理解、不做长篇版面重建。
    用于 /upload/graph 或后台图谱生成。
    """
    text = clean_for_llm(text or "")
    text = limit_text_for_llm(text, max_chars=3500)

    if not text:
        return fallback_analyze_text("")

    ltp_entities = extract_ltp_entities(text)
    ltp_words = extract_ltp_words(text)

    prompt = f"""
你是一个知识图谱深度抽取助手。

任务：根据文本生成“深度总结 + 实体 + 关系”，只输出 JSON。
不要做OCR版面修复，不要做视觉理解，不要输出长篇解释。

实体类型只能从以下12类选择：
人物、时间、地点、对象、事件、组织、主题、方法、结果、概念、文件、其他

类型区分规则：
1. 人物：人名、角色、行为主体、群体，如小红、老师、学生、人民、青年。
2. 时间：明确日期、年代、时间段，如2024年、5月4日、明天、上午。
3. 地点：国家、城市、地区、地点、场所，如北京、杭州、学校、战场、高地。
4. 对象：系统、平台、模块、工具、设备、具体物品，如系统、按钮、汉堡、机票。
5. 事件：动作、行为、任务、会议、战争、问题、错误、异常、过程，如喝水、买机票、识别失败。
6. 组织：公司、学校、机构、团队、政府、军队等组织名称。
7. 主题：思想、精神、价值、情绪、意象、宏观主题，如爱国主义精神、人民力量。
8. 方法：方法、算法、策略、流程、方案、机制、技术路线、模型方法。
9. 结果：结果、输出、结论、效果、成果、报告、摘要、提升、降低、改善。
10. 概念：理论、原理、定义、术语、学术概念，如马克思主义、社会主义、辩证法、唯物论。
11. 文件：文件、文档、PDF、图片、表格、代码文件、数据文件。
12. 其他：无法判断。

关系类型只能从以下选择：
提出、描述、包含、属于、影响、导致、服务于、体现、关联、参与、负责、使用、生成

关系规则：
1. 人物/组织 做某事 → 参与。
2. 时间/地点 与事件相关 → 描述。
3. 方法 用于对象/事件/结果 → 服务于。
4. 对象 使用 方法/概念 → 使用。
5. 文件/对象 产生结果 → 生成。
6. 事件 造成结果/事件 → 导致 或 影响。
7. 主题 表达 概念/精神/价值 → 体现。
8. 整体与部分 → 包含。
9. 不确定才用 关联，少用 属于。

方法-结果句式要重点抽取：
- “通过A实现B”：A 是方法，B 是结果，A --生成/服务于--> B
- “基于A生成B”：A 是方法，B 是结果
- “采用A提升B”：A 是方法，B 是结果
- “利用A解决B”：A 是方法，B 是结果

短文本也不要只输出一个节点。
如果是“小红明天去杭州吃汉堡买机票”，应抽取：
小红/人物、明天/时间、杭州/地点、吃汉堡/事件、汉堡/对象、买机票/事件、机票/对象。

LTP候选：
{build_ltp_context(ltp_entities, ltp_words)}

输出格式：
{{
  "repaired_text": "整理后的文本",
  "summary": "150字以内深度总结",
  "text_type": "普通行为句/名言格言/诗句歌词/标题短语/技术说明/文档内容/其他",
  "entities": [
    {{"name": "实体名称", "type": "人物/时间/地点/对象/事件/组织/主题/方法/结果/概念/文件/其他", "description": "简短说明"}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型", "confidence": 0.85}}
  ],
  "keywords": ["关键词1", "关键词2"],
  "modules": [
    {{"module": "识别内容", "text": "文本内容"}}
  ],
  "visual_notes": []
}}

文本内容：
{text}
"""

    fallback = fallback_analyze_text(text)
    data = call_llm_json(prompt, fallback=fallback)

    ai_result = normalize_ai_result(
        data,
        fallback,
        text,
        ltp_entities=ltp_entities
    )

    ai_result["repaired_text"] = ai_result.get("repaired_text") or text
    ai_result["source_text"] = text

    # 只有图谱太弱时才启用本地补图，避免共现关系乱连
    if is_graph_weak(ai_result):
        print("⚠️ 图谱较弱，启用 local_extractor 补充")
        local_result = local_extract(text)
        merged = merge_extract_results(local_result, ai_result)
        merged["repaired_text"] = text
        merged["source_text"] = text
        return merged

    return ai_result

def quick_graph_extract(text: str):
    """
    兼容旧代码命名。
    """
    return graph_deep_extract(text)

def is_graph_weak(result):
    entities = result.get("entities", [])
    relations = result.get("relations", [])

    if len(entities) < 3:
        return True

    if len(relations) < 2:
        return True

    weak_relations = {"关联", "相关", "描述"}

    weak_count = sum(
        1 for r in relations
        if r.get("relation") in weak_relations
    )

    if weak_count / max(len(relations), 1) > 0.7:
        return True

    return False

def analyze_ocr_with_qwen(ocr_result: dict, image_path: str = None, visual_detection: dict = None):
    raw_text = ocr_result.get("raw_text", "")
    structured_text = ocr_result.get("structured_text", "")
    layout_type = ocr_result.get("layout_type", "")
    modules = ocr_result.get("modules", [])

    has_visual = False
    visual_reason = ""

    if visual_detection:
        has_visual = bool(visual_detection.get("has_visual", False))
        visual_reason = visual_detection.get("reason", "")

    # PDF/图片：用于AI分析时优先使用 raw_text，展示仍可用 structured_text/modules。
    ocr_text = raw_text or structured_text
    ocr_text = clean_for_llm(ocr_text)
    text_for_llm = limit_text_for_llm(ocr_text)

    if not text_for_llm:
        fallback = fallback_analyze_text("")
        return normalize_ai_result(fallback, fallback, "")

    ltp_entities = extract_ltp_entities(text_for_llm)
    ltp_words = extract_ltp_words(text_for_llm)

    prompt = build_ai_prompt(
        text_for_llm,
        ltp_entities=ltp_entities,
        ltp_words=ltp_words,
        is_ocr=True,
        has_visual=has_visual,
        visual_reason=visual_reason,
        layout_type=layout_type,
        modules=modules
    )

    fallback = fallback_analyze_text(text_for_llm)

    data = call_llm_json(
        prompt,
        fallback=fallback,
        image_path=image_path if has_visual else None
    )

    return normalize_ai_result(
        data,
        fallback,
        text_for_llm,
        ltp_entities=ltp_entities
    )


# 兼容旧 analyze.py 调用
def analyze_text_with_graphrag_lite(text: str):
    return analyze_text(text)



def quick_summary_text(text: str):
    """
    快速总结接口：
    只用于前端立即展示AI总结，不做图谱抽取。
    """
    text = clean_for_llm(text or "")
    text = limit_text_for_llm(text, max_chars=2500)

    if not text:
        return {
            "summary": "",
            "text_type": "其他",
            "repaired_text": "",
            "entities": [],
            "relations": [],
            "keywords": [],
            "modules": [],
            "visual_notes": []
        }

    data = call_summary_json(text)

    return {
        "summary": data.get("summary", text[:120]),
        "text_type": data.get("text_type", "其他"),
        "repaired_text": text,
        "entities": [],
        "relations": [],
        "keywords": [],
        "modules": [{"module": "识别内容", "text": text}],
        "visual_notes": [],
        "source": "quick_summary"
    }


def quick_summary_ocr(ocr_result: dict):
    text = (
        ocr_result.get("structured_text")
        or ocr_result.get("raw_text")
        or ""
    )
    return quick_summary_text(text)

