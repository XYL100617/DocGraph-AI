export function normalizeGraph(raw) {
  if (!raw) {
    return { nodes: [], edges: [] }
  }

  const nodes = (raw.nodes || []).map(n => ({
    id: n.id || n.name,
    name: n.name || n.id,
    type: n.type || "概念",
    category: n.category || n.type || "概念",
    description: n.description || "",
    importance: n.importance || 0,
    symbolSize: n.symbolSize || 36,
    group: n.group ?? 0
  }))

  const edges = (raw.edges || raw.links || []).map(e => ({
    source: e.source,
    target: e.target,
    relation: e.relation || e.label || "相关",
    label: e.label || e.relation || "相关",
    weight: e.weight || e.confidence || 0.7,
    confidence: e.confidence || 0.7
  }))

  return { nodes, edges }
}