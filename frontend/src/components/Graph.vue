<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue"
import * as echarts from "echarts"

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({
      nodes: [],
      edges: []
    })
  },
  mode: {
    type: String,
    default: "compact"
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

const mergeDuplicateNodes = (nodes, edges) => {
  const idToName = {}
  const nameMap = {}
  const mergedNodes = []

  nodes.forEach((node) => {
    const oldId = String(node.id || node.name || "").trim()
    const name = String(node.name || node.id || "").trim()
    if (!oldId || !name) return

    idToName[oldId] = name

    if (!nameMap[name]) {
      nameMap[name] = {
        ...node,
        id: name,
        name
      }
      mergedNodes.push(nameMap[name])
    } else {
      const oldImportance = Number(nameMap[name].importance || nameMap[name].score || 0)
      const newImportance = Number(node.importance || node.score || 0)

      if (newImportance > oldImportance) {
        Object.assign(nameMap[name], {
          ...node,
          id: name,
          name
        })
      }
    }
  })

  const validIds = new Set(mergedNodes.map((n) => n.id))

  const fixedEdges = edges
    .map((edge) => {
      const sourceRaw = String(edge.source || "").trim()
      const targetRaw = String(edge.target || "").trim()

      return {
        ...edge,
        source: idToName[sourceRaw] || sourceRaw,
        target: idToName[targetRaw] || targetRaw
      }
    })
    .filter((edge) => validIds.has(edge.source) && validIds.has(edge.target))

  return {
    nodes: mergedNodes,
    edges: fixedEdges
  }
}

const getStyleByMode = () => {
  const isLarge = props.mode === "large"

  return {
    isLarge,
    textColor: isLarge ? "#0f172a" : "#eaf2ff",
    subTextColor: isLarge ? "#334155" : "#9fb7d8",
    edgeColor: isLarge
      ? "rgba(71, 85, 105, 0.88)"
      : "rgba(220, 235, 255, 0.62)",
    legendFontSize: isLarge ? 17 : 11,
    legendItemWidth: isLarge ? 24 : 12,
    legendItemHeight: isLarge ? 15 : 8,
    legendGap: isLarge ? 18 : 8,
    nodeLabelSize: isLarge ? 15 : 11,
    edgeLabelSize: isLarge ? 12 : 9,

    // 只缩小小模块节点；大图不变
    nodeBaseSize: isLarge ? 42 : 8,
    nodeScaleSize: isLarge ? 44 : 10,

    top: isLarge ? 88 : 46,
    bottom: isLarge ? 36 : 22,
    left: isLarge ? 34 : 12,
    right: isLarge ? 34 : 12,
    repulsion: isLarge ? 520 : 320,
    edgeLength: isLarge ? 170 : 130,
    gravity: isLarge ? 0.04 : 0.06
  }
}

const renderGraph = async () => {
  await nextTick()
  if (!chartRef.value) return

  const rawNodes = props.graphData?.nodes || []
  const rawEdges = props.graphData?.edges || props.graphData?.links || []

  if (!rawNodes.length) return

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const s = getStyleByMode()
  const mergedGraph = mergeDuplicateNodes(rawNodes, rawEdges)

  const nodes = mergedGraph.nodes.map((node) => {
    const type = node.type || node.category || "概念"
    const importance = Number(node.importance || node.score || 0)

    return {
      id: node.id || node.name,
      name: node.name || node.id,
      category: categoryMap[type] ?? 11,
      symbolSize: node.symbolSize || s.nodeBaseSize + importance * s.nodeScaleSize,
      value: importance,
      draggable: true,
      label: {
        show: true
      },
      tooltip: {
        formatter: `
          <b>${node.name || node.id}</b><br/>
          类型：${type}<br/>
          重要性：${importance.toFixed(3)}<br/>
          ${node.description || ""}
        `
      }
    }
  })

  const links = mergedGraph.edges.map((edge) => {
    const relation = edge.relation || edge.label || "相关"
    const weight = Number(edge.weight || edge.confidence || 0.7)

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
        color: s.edgeColor,
        opacity: s.isLarge ? 0.95 : 0.9,
        width: s.isLarge ? 2.2 + weight * 2.2 : 1.2 + weight * 2,
        curveness: 0.15
      }
    }
  })

  const option = {
    backgroundColor: "transparent",
    tooltip: { trigger: "item" },
    legend: {
      data: categories.map((item) => item.name),
      selectedMode: false,
      top: s.isLarge ? 14 : 4,
      left: "center",
      orient: "horizontal",
      itemGap: s.legendGap,
      textStyle: {
        color: s.textColor,
        fontSize: s.legendFontSize,
        fontWeight: s.isLarge ? 600 : 400
      },
      inactiveColor: s.textColor,
      itemWidth: s.legendItemWidth,
      itemHeight: s.legendItemHeight,
      pageIconColor: s.textColor,
      pageTextStyle: {
        color: s.textColor,
        fontSize: s.legendFontSize
      }
    },
    series: [
      {
        type: "graph",
        layout: "force",
        top: s.top,
        bottom: s.bottom,
        left: s.left,
        right: s.right,
        data: nodes,
        links,
        categories,
        roam: true,
        draggable: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: s.isLarge ? 10 : 8,
        label: {
          show: true,
          position: "right",
          formatter: "{b}",
          color: s.textColor,
          fontSize: s.nodeLabelSize,
          fontWeight: s.isLarge ? 600 : 500
        },
        edgeLabel: {
          show: true,
          fontSize: s.edgeLabelSize,
          color: s.subTextColor,
          fontWeight: s.isLarge ? 600 : 500,
          formatter: (params) => params.data.relation || ""
        },
        lineStyle: {
          color: s.edgeColor,
          opacity: s.isLarge ? 0.95 : 0.9
        },
        force: {
          repulsion: s.repulsion,
          edgeLength: s.edgeLength,
          gravity: s.gravity
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: {
            width: s.isLarge ? 4.5 : 4,
            color: s.isLarge ? "#334155" : "#ffffff"
          }
        }
      }
    ]
  }

  chart.clear()
  chart.setOption(option, true)

  setTimeout(() => {
    chart?.resize()
  }, 50)
}

const resizeChart = () => {
  chart?.resize()
}

const resetGraph = () => {
  renderGraph()
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

watch(
  () => props.mode,
  () => renderGraph()
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
  <div class="graph-container" :class="`graph-${props.mode}`">
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
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 420px;
  position: relative;
  background: transparent;
  border-radius: 16px;
  overflow: hidden;
}

.chart-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 420px;
}

.chart {
  width: 100%;
  height: 100%;
  min-height: 420px;
}

.graph-large {
  min-height: 680px;
}

.graph-large .chart-wrap,
.graph-large .chart {
  min-height: 680px;
}

.zoom-tools {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 10;
}

.zoom-tools button {
  border: 1px solid rgba(88, 166, 255, 0.35);
  background: rgba(7, 24, 46, 0.88);
  color: #dbeafe;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
}

.graph-large .zoom-tools button {
  background: rgba(255, 255, 255, 0.96);
  color: #1f2937;
  border-color: rgba(80, 100, 130, 0.35);
}

.empty {
  height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8fa7c8;
  font-size: 15px;
}
</style>