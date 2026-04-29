from fastapi import APIRouter, Form

from core.llm import analyze_text_with_graphrag_lite
from core.semantic_merge import semantic_merge_result
from core.relation_refine import refine_llm_relations

from graph.build import build_graph
from graph.analysis import analyze_graph
from graph.community import add_community_to_graph

router = APIRouter()


def apply_analysis_to_graph(graph_data, analysis_result):
    """
    将中心性分析结果写回节点。
    前端根据 importance 控制节点大小。
    """

    nodes = graph_data.get("nodes", [])

    # 单节点兜底：否则中心性天然为0
    if len(nodes) == 1:
        nodes[0]["importance"] = 1
        nodes[0]["symbolSize"] = 42
        return graph_data

    fusion = analysis_result.get("metrics", {}).get("fusion", {})

    for node in nodes:
        node_id = node.get("id") or node.get("name")
        score = float(fusion.get(node_id, 0))

        node["importance"] = round(score, 4)
        node["symbolSize"] = 26 + score * 28

    return graph_data


@router.post("/analyze-text")
def analyze_text_api(text: str = Form(...)):
    """
    文本 → GraphRAG-lite/AI抽取 → 语义合并 → 关系修正
    → NetworkX建图 → 社区分组 → 多中心性分析
    """

    if not text or not text.strip():
        return {
            "success": False,
            "message": "输入文本不能为空",
            "text": text,
            "llm": {},
            "graph": {
                "nodes": [],
                "edges": []
            },
            "analysis": {
                "core_nodes": [],
                "important_paths": [],
                "metrics": {}
            }
        }

    # 1. AI / GraphRAG-lite 语义分析
    llm_result = analyze_text_with_graphrag_lite(text)

    # 2. 语义去重
    llm_result = semantic_merge_result(llm_result)

    # 3. 关系后处理，修正“人物-系统=属于”这类错误
    llm_result = refine_llm_relations(llm_result)

    # 4. NetworkX 构建知识图谱
    graph_data = build_graph(llm_result)

    # 5. 社区发现，写入 group
    graph_data = add_community_to_graph(graph_data)

    # 6. 多中心性分析
    analysis_result = analyze_graph(graph_data)

    # 7. 把 importance / symbolSize 写回节点
    graph_data = apply_analysis_to_graph(graph_data, analysis_result)

    return {
    "success": True,
    "message": "文本分析完成",
    "text": text,
    "ocr": {
        "raw_text": text,
        "structured_text": text,
        "blocks": []
    },
    "llm": llm_result,
    "graph": graph_data,
    "analysis": analysis_result
}