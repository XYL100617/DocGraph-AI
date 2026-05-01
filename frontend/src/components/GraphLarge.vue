<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue"
import * as echarts from "echarts"

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({
      nodes: [],
      edges: [],
      links: []
    })
  }
})

const chartRef = ref(null)
let chart = null

const categoryMap = {
  人物: 0,
  时间: 1,
  地点: 2,
  对象: 3,
  事件: 4,
  组织: 5,
  主题: 6,
  方法: 7,
  结果: 8,
  概念: 9,
  文件: 10,
  其他: 11
}

const categories = [
  { name: "人物", itemStyle: { color: "#f06767" } },
  { name: "时间", itemStyle: { color: "#16c7c7" } },
  { name: "地点", itemStyle: { color: "#4d96ff" } },
  { name: "对象", itemStyle: { color: "#f0c267" } },
  { name: "事件", itemStyle: { color: "#c076f5" } },
  { name: "组织", itemStyle: { color: "#45e6a9" } },
  { name: "主题", itemStyle: { color: "#91cc75" } },
  { name: "方法", itemStyle: { color: "#2d6a4f" } },
  { name: "结果", itemStyle: { color: "#f77f00" } },
  { name: "概念", itemStyle: { color: "#6aa6ff" } },
  { name: "文件", itemStyle: { color: "#fca2c7" } },
  { name: "其他", itemStyle: { color: "#adb5bd" } }
]

const normalizeNodes = (rawNodes) => {
  const map = new Map()

  rawNodes.forEach((node) => {
    const id = node.id || node.name
    if (!id) return

    const type = node.type || node.category || "概念"
    const importance = Number(node.importance || node.score || 0)

    if (!map.has(id)) {
      map.set(id, {
        ...node,
        id,
        name: node.name || id,
        type,
        category: categoryMap[type] ?? 11,
        value: importance,
        importance
      })
    } else {
      const old = map.get(id)
      old.importance = Math.max(Number(old.importance || 0), importance)
      old.value = old.importance
    }
  })

  return Array.from(map.values())
}

const normalizeEdges = (rawEdges, nodeSet) => {
  const seen = new Set()
  const edges = []

  rawEdges.forEach((edge) => {
    const source = edge.source
    const target = edge.target
    if (!source || !target) return
    if (!nodeSet.has(source) || !nodeSet.has(target)) return

    const relation = edge.relation || edge.label || "相关"
    const key = `${source}->${target}->${relation}`
    if (seen.has(key)) return
    seen.add(key)

    edges.push({
      ...edge,
      source,
      target,
      relation,
      value: Number(edge.weight || edge.confidence || 0.7)
    })
  })

  return edges
}

const renderGraph = async () => {
  await nextTick()
  if (!chartRef.value) return

  const rawNodes = props.graphData?.nodes || []
  const rawEdges = props.graphData?.edges || props.graphData?.links || []
  if (!rawNodes.length) return

  if (!chart) chart = echarts.init(chartRef.value)

  const normalizedNodes = normalizeNodes(rawNodes)
  const nodeSet = new Set(normalizedNodes.map((n) => n.id))
  const normalizedEdges = normalizeEdges(rawEdges, nodeSet)

  const nodes = normalizedNodes.map((node) => {
    const importance = Number(node.importance || 0)
    const type = node.type || "概念"

    return {
      id: node.id,
      name: node.name,
      category: categoryMap[type] ?? 11,
      symbolSize: node.symbolSize || 52 + importance * 55,
      value: importance,
      draggable: true,
      label: {
        show: true
      },
      tooltip: {
        formatter: `
          <b>${node.name}</b><br/>
          类型：${type}<br/>
          重要性：${importance.toFixed(3)}<br/>
          ${node.description || ""}
        `
      }
    }
  })

  const links = normalizedEdges.map((edge) => {
    const relation = edge.relation || "相关"
    const weight = Number(edge.value || 0.7)

    return {
      source: edge.source,
      target: edge.target,
      relation,
      value: weight,
      label: {
        show: true,
        formatter: relation
      },
      tooltip: {
        formatter: `
          <b>${edge.source}</b> → <b>${edge.target}</b><br/>
          关系：${relation}<br/>
          权重：${weight.toFixed(2)}
        `
      },
      lineStyle: {
        color: "rgba(82, 92, 110, 0.72)",
        width: 1.1 + weight * 1.3,
        opacity: 0.82,
        curveness: 0.15
      }
    }
  })

  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item"
    },
    legend: {
      data: categories.map((item) => item.name),
      top: 14,
      left: "center",
      orient: "horizontal",
      selectedMode: "multiple",
      itemGap: 16,
      itemWidth: 20,
      itemHeight: 13,
      textStyle: {
        color: "#111827",
        fontSize: 15,
        fontWeight: 600
      },
      inactiveColor: "#cbd5e1"
    },
    series: [
      {
        type: "graph",
        layout: "force",
        top: 82,
        bottom: 36,
        left: 36,
        right: 36,
        data: nodes,
        links,
        categories,
        roam: true,
        draggable: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 9,
        label: {
          show: true,
          position: "right",
          formatter: "{b}",
          color: "#111827",
          fontSize: 14,
        },
        edgeLabel: {
          show: true,
          fontSize: 11,
          color: "#475569",
          fontWeight: 500,
          formatter: (params) => params.data.relation || ""
        },
        lineStyle: {
          color: "rgba(82, 92, 110, 0.72)",
          width: 1.6,
          opacity: 0.82
        },
        force: {
          repulsion: 480,
          edgeLength: 155,
          gravity: 0.045
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: {
            width: 3.6,
            color: "#334155"
          }
        }
      }
    ]
  }

  chart.clear()
  chart.setOption(option, true)
  setTimeout(() => chart?.resize(), 50)
}

const resetGraph = () => {
  renderGraph()
}

const resizeChart = () => {
  chart?.resize()
}

onMounted(() => {
  renderGraph()
  window.addEventListener("resize", resizeChart)
})

watch(
  () => props.graphData,
  () => renderGraph(),
  { deep: true }
)

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <div class="graph-large-container">
    <div
      v-if="!props.graphData || !props.graphData.nodes || props.graphData.nodes.length === 0"
      class="empty"
    >
      暂无图谱数据
    </div>

    <div v-else class="chart-wrap">
      <div ref="chartRef" class="chart"></div>

      <div class="zoom-tools">
        <button @click="resetGraph">复位</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-large-container {
  width: 100%;
  height: 100%;
  min-height: 680px;
  position: relative;
  background: transparent;
  border-radius: 16px;
  overflow: hidden;
}

.chart-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 680px;
}

.chart {
  width: 100%;
  height: 100%;
  min-height: 680px;
}

.zoom-tools {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 10;
}

.zoom-tools button {
  border: 1px solid rgba(80, 100, 130, 0.35);
  background: rgba(255, 255, 255, 0.96);
  color: #1f2937;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.empty {
  height: 680px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 15px;
}
</style>