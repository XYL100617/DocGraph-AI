import re
from difflib import SequenceMatcher


VALID_TYPES = {"人物", "组织", "地点", "时间", "事件", "对象", "主题", "其他"}

TYPE_MAP = {
    "技术": "主题",
    "方法": "主题",
    "概念": "主题",
    "问题": "事件",
    "结果": "主题",
    "模块": "对象",
    "文件": "对象",
}

TYPE_PRIORITY = {
    "人物": 8,
    "组织": 7,
    "地点": 6,
    "时间": 6,
    "事件": 5,
    "对象": 4,
    "主题": 3,
    "其他": 1,
}


def normalize_type(t):
    t = str(t or "主题").strip()
    t = TYPE_MAP.get(t, t)
    return t if t in VALID_TYPES else "主题"


def normalize_name(name: str):
    if not name:
        return ""

    name = str(name).strip()
    name = name.lower()
    name = re.sub(r"\s+", "", name)
    name = name.replace("（", "(").replace("）", ")")
    name = name.replace("-", "")
    name = name.replace("_", "")

    return name


def is_bad_name(name):
    name = str(name or "").strip()

    if not name:
        return True

    if len(name) <= 1:
        return True

    if len(name) > 30:
        return True

    if re.fullmatch(r"\d+", name):
        return True

    if re.fullmatch(r"[^\u4e00-\u9fa5A-Za-z0-9]+", name):
        return True

    return False


def text_similarity(a: str, b: str):
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 1.0

    min_len = min(len(a_norm), len(b_norm))

    # 只有长度足够时才允许包含式合并，避免“心”合并到“立心”
    if min_len >= 3 and (a_norm in b_norm or b_norm in a_norm):
        return 0.9

    return SequenceMatcher(None, a_norm, b_norm).ratio()


def choose_better_type(old_type, new_type):
    old_type = normalize_type(old_type)
    new_type = normalize_type(new_type)

    if TYPE_PRIORITY.get(new_type, 0) > TYPE_PRIORITY.get(old_type, 0):
        return new_type

    return old_type


def merge_entities(entities, threshold=0.88):
    if not entities:
        return [], {}

    merged = []
    name_map = {}

    for entity in entities:
        if isinstance(entity, str):
            entity = {
                "name": entity,
                "type": "主题",
                "description": ""
            }

        if not isinstance(entity, dict):
            continue

        name = str(entity.get("name", "")).strip()

        if is_bad_name(name):
            continue

        entity_type = normalize_type(entity.get("type", "主题"))
        description = entity.get("description", "")
        source = entity.get("source", "unknown")

        matched = None

        for old in merged:
            old_name = old.get("name", "")
            sim = text_similarity(name, old_name)

            if sim >= threshold:
                matched = old
                break

        if matched:
            name_map[name] = matched["name"]

            matched["type"] = choose_better_type(matched.get("type"), entity_type)

            if not matched.get("description") and description:
                matched["description"] = description

            aliases = matched.get("aliases", [])
            if name not in aliases:
                aliases.append(name)
            matched["aliases"] = aliases

            sources = matched.get("sources", [])
            if source not in sources:
                sources.append(source)
            matched["sources"] = sources

        else:
            new_entity = {
                "name": name,
                "type": entity_type,
                "category": entity_type,
                "description": description,
                "aliases": [name],
                "sources": [source]
            }

            merged.append(new_entity)
            name_map[name] = name

    return merged, name_map


def normalize_relation_name(relation):
    relation = str(relation or "关联").strip()

    relation_map = {
        "相关": "关联",
        "related_to": "关联",
        "用于": "使用",
        "用来": "使用",
        "应用于": "使用",
        "依赖": "使用",
        "基于": "使用",
        "组成": "包含",
        "包括": "包含",
        "表达": "体现",
        "反映": "体现",
        "象征": "体现",
    }

    return relation_map.get(relation, relation)


def remap_relations(relations, name_map):
    new_relations = []
    seen = set()

    for r in relations:
        if not isinstance(r, dict):
            continue

        source = r.get("source") or r.get("from")
        target = r.get("target") or r.get("to")

        if not source or not target:
            continue

        source = name_map.get(str(source).strip(), str(source).strip())
        target = name_map.get(str(target).strip(), str(target).strip())

        if source == target:
            continue

        raw_relation = r.get("relation") or r.get("type") or "关联"

        relation = None
        for part in re.split(r"[\/,;，；|]", str(raw_relation)):
            part = part.strip()
            if part:
                relation = normalize_relation_name(part)
                break

        if not relation:
            relation = "关联"

        key = (source, target, relation)

        if key in seen:
            continue

        seen.add(key)

        try:
            confidence = float(r.get("confidence", 0.7))
        except Exception:
            confidence = 0.7

        confidence = max(0.0, min(confidence, 1.0))

        new_relations.append({
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": confidence,
            "raw_relation": r.get("raw_relation", raw_relation)
        })

    return new_relations


def get_source_text(llm_result):
    text = (
        llm_result.get("repaired_text")
        or llm_result.get("text")
        or ""
    )

    if text:
        return text

    modules = llm_result.get("modules", [])

    if isinstance(modules, list):
        parts = []
        for m in modules:
            if isinstance(m, dict) and m.get("text"):
                parts.append(str(m.get("text")))
        text = "\n".join(parts)

    return text or llm_result.get("summary", "")


def choose_main_entity(entities, text):
    candidates = []

    for e in entities:
        name = e.get("name", "")
        etype = e.get("type", "主题")

        score = 0

        if etype in {"事件", "主题"}:
            score += 3

        if name in text:
            score += text.count(name) * 2

        if 3 <= len(name) <= 14:
            score += 1

        if any(k in name for k in ["战争", "精神", "系统", "项目", "图谱", "识别", "分析", "主题"]):
            score += 2

        candidates.append((score, name))

    if not candidates:
        return ""

    candidates.sort(reverse=True)
    return candidates[0][1]


def relation_to_main(entity):
    name = entity.get("name", "")
    etype = entity.get("type", "主题")

    if etype in {"人物", "组织"}:
        return "参与"

    if etype in {"时间", "地点"}:
        return "描述"

    if etype == "事件":
        return "包含"

    if any(k in name for k in ["精神", "主义", "忠诚", "勇敢", "信念", "理想", "意象", "情绪"]):
        return "体现"

    return "关联"


def add_missing_center_edges(entities, relations, text):
    if not text or not entities:
        return relations

    main = choose_main_entity(entities, text)

    if not main:
        return relations

    existing_nodes = set()
    seen_edges = set()

    for r in relations:
        existing_nodes.add(r.get("source"))
        existing_nodes.add(r.get("target"))
        seen_edges.add((r.get("source"), r.get("target"), r.get("relation")))

    for e in entities:
        name = e.get("name", "")

        if not name or name == main:
            continue

        if name in existing_nodes:
            continue

        if name not in text:
            continue

        rel = relation_to_main(e)

        if rel in {"参与", "描述"}:
            source, target = name, main
        elif rel in {"包含", "体现"}:
            source, target = main, name
        else:
            source, target = main, name

        key = (source, target, rel)

        if key in seen_edges:
            continue

        relations.append({
            "source": source,
            "target": target,
            "relation": rel,
            "confidence": 0.55,
            "raw_relation": "semantic_merge_center_repair"
        })

        seen_edges.add(key)

    return relations


def semantic_merge_result(llm_result):
    if not isinstance(llm_result, dict):
        return {
            "summary": "",
            "entities": [],
            "relations": [],
            "keywords": []
        }

    entities = llm_result.get("entities", [])
    relations = llm_result.get("relations", [])

    merged_entities, name_map = merge_entities(entities)
    merged_relations = remap_relations(relations, name_map)

    text = get_source_text(llm_result)
    # 只有关系太少时才补中心边，避免“该不连的也乱连”
    if len(merged_relations) < max(2, len(merged_entities) // 4):
        merged_relations = add_missing_center_edges(
            merged_entities,
            merged_relations,
            text
    )

    llm_result["entities"] = merged_entities
    llm_result["relations"] = merged_relations

    keywords = []

    for e in merged_entities:
        name = e.get("name")
        if name and name not in keywords:
            keywords.append(name)

    llm_result["keywords"] = keywords[:12]

    return llm_result