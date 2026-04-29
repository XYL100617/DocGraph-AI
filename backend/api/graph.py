import networkx as nx

def build_graph(result):
    G = nx.Graph()

    entities = result.get("entities", [])
    relations = result.get("relations", [])

    # 1. 加节点
    for e in entities:
        G.add_node(e)

    # 2. 加边（关键修复）
    for r in relations:
        if len(r) == 3:
            src, rel, dst = r
            G.add_edge(src, dst, type=rel)

    return nx.node_link_data(G)