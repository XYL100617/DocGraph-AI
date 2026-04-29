import re


VALID_RELATIONS = {
    "提出", "描述", "包含", "属于", "影响", "导致",
    "服务于", "体现", "关联", "参与", "负责", "使用", "生成"
}

WEAK_RELATIONS = {"关联", "相关", "描述", "属于"}

TRIGGER_RELATIONS = {
    "导致": "导致",
    "造成": "导致",
    "引起": "导致",
    "使得": "导致",

    "影响": "影响",
    "推动": "影响",
    "促进": "影响",

    "使用": "使用",
    "采用": "使用",
    "运用": "使用",
    "通过": "使用",
    "基于": "使用",
    "利用": "使用",

    "生成": "生成",
    "输出": "生成",
    "形成": "生成",
    "构建": "生成",
    "产生": "生成",

    "体现": "体现",
    "表达": "体现",
    "反映": "体现",
    "象征": "体现",
    "彰显": "体现",

    "包含": "包含",
    "包括": "包含",
    "组成": "包含",

    "参加": "参与",
    "参与": "参与",
    "投身": "参与",

    "负责": "负责",
    "领导": "负责",
    "组织": "负责",

    "提出": "提出",
    "主张": "提出",
    "认为": "提出",
    "强调": "提出",
}


def clean_name(name):
    return str(name or "").strip(" \n\t，。；;：:、【】[]()（）")


def split_sentences(text):
    parts = re.split(r"[。！？；;\n]+", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def normalize_relation(rel):
    rel = str(rel or "关联").strip()

    mapping = {
        "相关": "关联",
        "related_to": "关联",
        "用于": "使用",
        "用来": "使用",
        "应用于": "使用",
        "依赖": "使用",
        "基于": "使用",
        "包括": "包含",
        "组成": "包含",
        "表达": "体现",
        "反映": "体现",
        "象征": "体现",
    }

    rel = mapping.get(rel, rel)
    return rel if rel in VALID_RELATIONS else "关联"


def get_source_text(llm_result):
    text = (
        llm_result.get("source_text")
        or llm_result.get("repaired_text")
        or llm_result.get("text")
        or ""
    )

    if text:
        return text

    modules = llm_result.get("modules", [])
    if isinstance(modules, list):
        return "\n".join([
            str(m.get("text", ""))
            for m in modules
            if isinstance(m, dict) and m.get("text")
        ])

    return llm_result.get("summary", "")


def get_entity_map(llm_result):
    entity_map = {}

    for e in llm_result.get("entities", []):
        if not isinstance(e, dict):
            continue

        name = clean_name(e.get("name", ""))
        if not name:
            continue

        entity_map[name] = e

    return entity_map


def relation_by_type(source_type, target_type):
    if source_type in {"人物", "组织"} and target_type == "事件":
        return "参与"
    
    if source_type == "人物" and target_type == "地点":
        return "参与"

    if source_type == "人物" and target_type == "对象":
        return "使用"

    if source_type == "事件" and target_type == "地点":
        return "描述"

    if source_type == "事件" and target_type == "对象":
        return "使用"

    if source_type == "时间" and target_type == "事件":
        return "描述"

    if source_type == "地点" and target_type == "事件":
        return "描述"

    if source_type == "方法" and target_type == "结果":
        return "生成"

    if source_type == "方法" and target_type in {"事件", "对象"}:
        return "服务于"

    if source_type in {"时间", "地点"} and target_type in {"事件", "主题", "概念"}:
        return "描述"

    if source_type == "对象" and target_type in {"方法", "概念"}:
        return "使用"

    if source_type == "方法" and target_type in {"对象", "事件", "结果"}:
        return "服务于"

    if source_type in {"文件", "对象"} and target_type == "结果":
        return "生成"

    if source_type == "事件" and target_type in {"结果", "事件"}:
        return "影响"

    if source_type in {"事件", "主题"} and target_type in {"主题", "概念"}:
        return "体现"

    if source_type == "概念" and target_type == "概念":
        return "关联"

    if source_type == "主题" and target_type == "概念":
        return "体现"

    if source_type == "概念" and target_type == "主题":
        return "关联"

    return "关联"


def relation_from_sentence(source, target, text):
    for sent in split_sentences(text):
        if source not in sent or target not in sent:
            continue

        for trigger, rel in TRIGGER_RELATIONS.items():
            if trigger in sent:
                return rel

    return ""


def add_relation(relations, seen, source, target, relation, confidence=0.65, raw_relation=None):
    source = clean_name(source)
    target = clean_name(target)
    relation = normalize_relation(relation)

    if not source or not target or source == target:
        return

    key = (source, target, relation)
    if key in seen:
        return

    seen.add(key)
    relations.append({
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": confidence,
        "raw_relation": raw_relation or relation
    })


def refine_existing_relations(llm_result, entity_map, text):
    new_relations = []
    seen = set()

    for r in llm_result.get("relations", []):
        if not isinstance(r, dict):
            continue

        source = clean_name(r.get("source") or r.get("from") or "")
        target = clean_name(r.get("target") or r.get("to") or "")

        if not source or not target or source == target:
            continue

        if source not in entity_map or target not in entity_map:
            continue

        s_type = entity_map[source].get("type", "主题")
        t_type = entity_map[target].get("type", "主题")

        old_relation = normalize_relation(r.get("relation") or r.get("type") or "关联")

        context_relation = relation_from_sentence(source, target, text)

        if context_relation:
            relation = context_relation
        elif old_relation in WEAK_RELATIONS:
            relation = relation_by_type(s_type, t_type)
        else:
            relation = old_relation

        try:
            confidence = float(r.get("confidence", 0.7))
        except Exception:
            confidence = 0.7

        add_relation(
            new_relations,
            seen,
            source,
            target,
            relation,
            confidence,
            r.get("raw_relation", old_relation)
        )

    return new_relations, seen


def add_sentence_trigger_relations(relations, seen, entity_map, text):
    entity_names = list(entity_map.keys())

    for sent in split_sentences(text):
        appeared = [name for name in entity_names if name in sent]

        if len(appeared) < 2:
            continue

        # 同一句中最多取前6个，避免过密
        appeared = appeared[:6]

        trigger_relation = ""

        for trigger, rel in TRIGGER_RELATIONS.items():
            if trigger in sent:
                trigger_relation = rel
                break

        # 有触发词时按触发词补边
        if trigger_relation:
            for i in range(len(appeared) - 1):
                source = appeared[i]
                target = appeared[i + 1]
                add_relation(
                    relations,
                    seen,
                    source,
                    target,
                    trigger_relation,
                    0.68,
                    "sentence_trigger"
                )
        else:
            # 没触发词时，只补少量弱关联
            for i in range(len(appeared) - 1):
                source = appeared[i]
                target = appeared[i + 1]

                s_type = entity_map[source].get("type", "主题")
                t_type = entity_map[target].get("type", "主题")
                rel = relation_by_type(s_type, t_type)

                if rel == "关联":
                    conf = 0.45
                else:
                    conf = 0.58

                add_relation(
                    relations,
                    seen,
                    source,
                    target,
                    rel,
                    conf,
                    "sentence_cooccurrence"
                )


def is_graph_weak(entities, relations):
    if len(entities) <= 3:
        return True

    if len(relations) < max(2, len(entities) // 4):
        return True

    if relations:
        weak_count = sum(1 for r in relations if r.get("relation") in {"关联", "描述"})
        if weak_count / max(len(relations), 1) > 0.75:
            return True

    return False


def choose_main_entity(entity_map, text):
    scored = []

    for name, e in entity_map.items():
        etype = e.get("type", "主题")
        score = 0

        if etype in {"事件", "主题", "概念"}:
            score += 4

        if text and name in text:
            score += text.count(name) * 2

        if 3 <= len(name) <= 14:
            score += 2

        if any(k in name for k in ["战争", "运动", "精神", "主义", "系统", "图谱", "识别", "分析"]):
            score += 3

        scored.append((score, name))

    if not scored:
        return ""

    scored.sort(reverse=True)
    return scored[0][1]


def add_weak_graph_center_relations(relations, seen, entity_map, text):
    main = choose_main_entity(entity_map, text)

    if not main:
        return

    main_type = entity_map[main].get("type", "主题")

    linked = set()
    for r in relations:
        linked.add(r.get("source"))
        linked.add(r.get("target"))

    for name, e in entity_map.items():
        if name == main:
            continue

        if name in linked:
            continue

        if text and name not in text:
            continue

        etype = e.get("type", "主题")

        if etype in {"人物", "组织", "时间", "地点"}:
            source, target = name, main
            rel = relation_by_type(etype, main_type)
        elif etype == "事件":
            source, target = main, name
            rel = "包含"
        elif etype in {"主题", "概念"}:
            source, target = main, name
            rel = "体现"
        elif etype == "方法":
            source, target = name, main
            rel = "服务于"
        elif etype == "结果":
            source, target = main, name
            rel = "生成"
        else:
            source, target = main, name
            rel = "关联"

        add_relation(
            relations,
            seen,
            source,
            target,
            rel,
            0.55,
            "weak_graph_center_repair"
        )


def refine_llm_relations(llm_result):
    if not isinstance(llm_result, dict):
        return llm_result

    entity_map = get_entity_map(llm_result)
    text = get_source_text(llm_result)

    if not entity_map:
        llm_result["relations"] = []
        return llm_result

    relations, seen = refine_existing_relations(llm_result, entity_map, text)

    add_sentence_trigger_relations(relations, seen, entity_map, text)

    if is_graph_weak(list(entity_map.values()), relations):
        add_weak_graph_center_relations(relations, seen, entity_map, text)

    llm_result["relations"] = relations
    return llm_result