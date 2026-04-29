import networkx as nx


def add_community_to_graph(graph_data):
    """
    用NetworkX社区发现给节点分组。
    比Node2Vec/HDBSCAN更稳，短时间更适合。
    """
    G = nx.Graph()

    for node in graph_data.get("nodes", []):
        node_id = node.get("id") or node.get("name")
        if node_id:
            G.add_node(node_id)

    for edge in graph_data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        weight = edge.get("weight", 1.0)

        if source and target:
            G.add_edge(source, target, weight=weight)

    if G.number_of_nodes() == 0:
        return graph_data

    communities = nx.algorithms.community.greedy_modularity_communities(G)

    group_map = {}
    for group_id, community in enumerate(communities):
        for node in community:
            group_map[node] = group_id

    for node in graph_data.get("nodes", []):
        node_id = node.get("id") or node.get("name")
        node["group"] = group_map.get(node_id, 0)

    return graph_data