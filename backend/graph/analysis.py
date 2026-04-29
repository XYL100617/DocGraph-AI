import networkx as nx


BAD_CORE_NODE_NAMES = {
    "相似实体",
    "核心节点",
    "关键路径",
    "关系",
    "实体",
    "节点",
    "边",
    "图谱",
    "知识图谱"
}


def build_nx_graph(graph_data):
    """
    将 graph JSON 转成 NetworkX 图。
    """

    G = nx.DiGraph()

    for node in graph_data.get("nodes", []):
        node_id = node.get("id") or node.get("name")

        if node_id:
            G.add_node(node_id, **node)

    for edge in graph_data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")

        if not source or not target:
            continue

        weight = edge.get("weight", edge.get("confidence", 0.7))

        try:
            weight = float(weight)
        except Exception:
            weight = 0.7

        G.add_edge(
            source,
            target,
            weight=weight,
            relation=edge.get("relation", "相关")
        )

    return G


def normalize_scores(score_dict):
    """
    分数归一化到 0~1。
    """

    if not score_dict:
        return {}

    max_score = max(score_dict.values())

    if max_score == 0:
        return {k: 0 for k in score_dict}

    return {
        k: v / max_score
        for k, v in score_dict.items()
    }


def is_bad_core_node(name):
    """
    过滤“相似实体”“核心节点”这种由提示词或结构说明误抽出来的伪节点。
    """

    if not name:
        return True

    name = str(name).strip()

    if name in BAD_CORE_NODE_NAMES:
        return True

    # 太泛的结构词，不适合作为核心节点展示
    if name.endswith("实体") and len(name) <= 6:
        return True

    if name.endswith("节点") and len(name) <= 6:
        return True

    return False


def build_reason(name, degree, betweenness, pagerank):
    """
    面向前端展示的自然语言说明，不暴露太多算法细节。
    """

    if pagerank >= 0.8:
        return "该节点在图谱中被多条关系指向，是当前内容的核心主题。"

    if degree >= 0.6:
        return "该节点与多个信息点直接相连，是内容组织中的关键节点。"

    if betweenness >= 0.4:
        return "该节点连接了不同信息分支，起到桥接作用。"

    return "该节点在当前图谱中具有较高关联度。"


def analyze_graph(graph_data):
    """
    Degree + Betweenness + PageRank 多中心性融合。
    """

    G = build_nx_graph(graph_data)

    if G.number_of_nodes() == 0:
        return {
            "core_nodes": [],
            "metrics": {
                "degree": {},
                "betweenness": {},
                "pagerank": {},
                "fusion": {}
            },
            "important_paths": []
        }

    # 单节点兜底
    if G.number_of_nodes() == 1:
        node = list(G.nodes())[0]

        return {
            "core_nodes": [
                {
                    "name": node,
                    "score": 1.0,
                    "degree": 0,
                    "betweenness": 0,
                    "pagerank": 1.0,
                    "reason": "该节点是当前文本中唯一的核心主题。"
                }
            ],
            "metrics": {
                "degree": {node: 0},
                "betweenness": {node: 0},
                "pagerank": {node: 1.0},
                "fusion": {node: 1.0}
            },
            "important_paths": []
        }

    degree = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G)

    try:
        pagerank = nx.pagerank(G, weight="weight")
    except Exception:
        pagerank = {
            node: 0
            for node in G.nodes()
        }

    degree_norm = normalize_scores(degree)
    betweenness_norm = normalize_scores(betweenness)
    pagerank_norm = normalize_scores(pagerank)

    fusion = {}

    for node in G.nodes():
        fusion[node] = (
            0.3 * degree_norm.get(node, 0)
            + 0.3 * betweenness_norm.get(node, 0)
            + 0.4 * pagerank_norm.get(node, 0)
        )

    sorted_nodes = sorted(
        fusion.items(),
        key=lambda x: x[1],
        reverse=True
    )

    core_nodes = []

    for node_name, score in sorted_nodes:
        if is_bad_core_node(node_name):
            continue

        core_nodes.append({
            "name": node_name,
            "score": round(score, 4),
            "degree": round(degree_norm.get(node_name, 0), 4),
            "betweenness": round(betweenness_norm.get(node_name, 0), 4),
            "pagerank": round(pagerank_norm.get(node_name, 0), 4),
            "reason": build_reason(
                node_name,
                degree_norm.get(node_name, 0),
                betweenness_norm.get(node_name, 0),
                pagerank_norm.get(node_name, 0)
            )
        })

        if len(core_nodes) >= 5:
            break

    important_paths = find_important_paths(G, sorted_nodes)

    return {
        "core_nodes": core_nodes,
        "metrics": {
            "degree": degree_norm,
            "betweenness": betweenness_norm,
            "pagerank": pagerank_norm,
            "fusion": fusion
        },
        "important_paths": important_paths
    }


def find_important_paths(G, sorted_nodes):
    """
    在核心节点之间寻找简单关键路径。
    """

    paths = []

    top_nodes = [
        item[0]
        for item in sorted_nodes
        if not is_bad_core_node(item[0])
    ][:4]

    for i in range(len(top_nodes)):
        for j in range(i + 1, len(top_nodes)):
            source = top_nodes[i]
            target = top_nodes[j]

            try:
                path = nx.shortest_path(
                    G,
                    source=source,
                    target=target
                )

                if len(path) > 1:
                    paths.append(path)

            except Exception:
                try:
                    path = nx.shortest_path(
                        G,
                        source=target,
                        target=source
                    )

                    if len(path) > 1:
                        paths.append(path)

                except Exception:
                    continue

    return paths[:5]