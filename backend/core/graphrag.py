def build_graph_context(llm_result):
    """
    将第一次LLM抽取结果整理成图谱上下文。
    """

    entities = llm_result.get("entities", [])
    relations = llm_result.get("relations", [])

    entity_lines = []

    for e in entities:
        if not isinstance(e, dict):
            continue

        name = e.get("name", "")
        node_type = e.get("type", "概念")
        desc = e.get("description", "")

        if name:
            entity_lines.append(f"- {name}（{node_type}）：{desc}")

    relation_lines = []

    for r in relations:
        if not isinstance(r, dict):
            continue

        source = r.get("source", "")
        target = r.get("target", "")
        relation = r.get("relation", "相关")

        if source and target:
            relation_lines.append(f"- {source} --{relation}--> {target}")

    return f"""
已有实体：
{chr(10).join(entity_lines)}

已有关系：
{chr(10).join(relation_lines)}
"""


def build_graphrag_prompt(text, llm_result):
    """
    GraphRAG-lite增强Prompt：
    原始文本 + 初始图谱上下文 → 二次关系补全。
    """

    graph_context = build_graph_context(llm_result)

    return f"""
你需要基于【原始文本】和【已有图谱上下文】补充遗漏的实体与关系。

【原始文本】
{text}

【已有图谱上下文】
{graph_context}

要求：
1. 只输出JSON，不要输出解释。
2. 不要重复已有关系。
3. 重点补充：包含、依赖、导致、组成、影响、输入到、生成、用于 等关系。
4. entities 和 relations 必须是数组。

JSON格式：
{{
  "summary": "不超过100字摘要",
  "entities": [
    {{
      "name": "实体名",
      "type": "概念/技术/方法/问题/结果/模块/人物/其他",
      "description": "简短说明"
    }}
  ],
  "relations": [
    {{
      "source": "实体A",
      "target": "实体B",
      "relation": "包含/依赖/导致/相关/组成/影响/输入到/生成/用于",
      "confidence": 0.8
    }}
  ],
  "keywords": ["关键词1", "关键词2"]
}}
"""


def merge_llm_results(base_result, enhanced_result):
    """
    合并第一次LLM和GraphRAG-lite增强后的结果。
    """

    entity_map = {}

    for e in base_result.get("entities", []):
        if isinstance(e, dict) and e.get("name"):
            entity_map[e["name"]] = e

    for e in enhanced_result.get("entities", []):
        if isinstance(e, dict) and e.get("name"):
            entity_map[e["name"]] = e

    relation_set = set()
    relations = []

    all_relations = base_result.get("relations", []) + enhanced_result.get("relations", [])

    for r in all_relations:
        if not isinstance(r, dict):
            continue

        source = r.get("source")
        target = r.get("target")
        relation = r.get("relation", "相关")

        if not source or not target:
            continue

        key = (source, target, relation)

        if key in relation_set:
            continue

        relation_set.add(key)

        try:
            confidence = float(r.get("confidence", 0.7))
        except Exception:
            confidence = 0.7

        relations.append({
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": confidence
        })

    keywords = list(set(
        base_result.get("keywords", []) + enhanced_result.get("keywords", [])
    ))

    return {
        "summary": enhanced_result.get("summary") or base_result.get("summary", ""),
        "entities": list(entity_map.values()),
        "relations": relations,
        "keywords": keywords
    }