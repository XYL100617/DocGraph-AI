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
  { name: "时间", itemStyle: { color: "#7ae6de" } },
  { name: "地点", itemStyle: { color: "#7abae6" } },
  { name: "对象", itemStyle: { color: "#f0c267" } },
  { name: "事件", itemStyle: { color: "#c076f5" } },
  { name: "组织", itemStyle: { color: "#8aeda9" } },
  { name: "主题", itemStyle: { color: "#91cc75" } },
  { name: "方法", itemStyle: { color: "#2d6a4f" } },
  { name: "结果", itemStyle: { color: "#f77f00" } },
  { name: "概念", itemStyle: { color: "#fcdcae" } },
  { name: "文件", itemStyle: { color: "#fca2c7" } },
  { name: "其他", itemStyle: { color: "#adb5bd" } }
]

const renderGraph = async () => {
  await nextTick()

  if (!chartRef.value) return

  const rawNodes = props.graphData?.nodes || []
  const rawEdges = props.graphData?.edges || props.graphData?.links || []

  if (!rawNodes.length) return

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const nodes = rawNodes.map((node) => {
    const type = node.type || node.category || "概念"
    const importance = Number(node.importance || 0)

    return {
      id: node.id || node.name,
      name: node.name || node.id,
      category: categoryMap[type] ?? 11,
      symbolSize: node.symbolSize || 30 + importance * 40,
      value: importance,
      draggable: true,
      label: {
        show: true
      },
      tooltip: {
        formatter: `
          <b>${node.name || node.id}</b><br/>
          类型：${type}<br/>
          ${node.group !== undefined && node.group !== null && node.group !== 0 ? `分组：${node.group}<br/>` : ""}
          重要性：${importance.toFixed(3)}<br/>
          ${node.description || ""}
        `
      }
    }
  })

  const links = rawEdges.map((edge) => {
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
        关系权重/置信度：${weight.toFixed(2)}
      `
    },
      lineStyle: {
        width: 1 + weight * 2,
        curveness: 0.15
      }
    }
  })

  const option = {
    tooltip: {
      trigger: "item"
    },
    legend: {
      data: categories.map((item) => item.name),
      top: 10
    },
    series: [
      {
        type: "graph",
        layout: "force",
        data: nodes,
        links,
        categories,
        roam: true,
        draggable: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 8,
        label: {
          show: true,
          position: "right",
          formatter: "{b}"
        },
        edgeLabel: {
          show: true,
          fontSize: 10,
          formatter: (params) => {
            return params.data.relation || ""
          }
        },
        force: {
          repulsion: 300,
          edgeLength: 130,
          gravity: 0.08
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: {
            width: 4
          }
        }
      }
    ]
  }

  chart.setOption(option, true)
}

const resizeChart = () => {
  if (chart) {
    chart.resize()
  }
}

onMounted(() => {
  renderGraph()
  window.addEventListener("resize", resizeChart)
})

watch(
  () => props.graphData,
  () => {
    renderGraph()
  },
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
  <div class="graph-container">
    <div
      v-if="!props.graphData || !props.graphData.nodes || props.graphData.nodes.length === 0"
      class="empty"
    >
      暂无图谱数据
    </div>

    <div
      v-else
      ref="chartRef"
      class="chart"
    ></div>
  </div>
</template>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 520px;
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
}

.chart {
  width: 100%;
  height: 100%;
  min-height: 520px;
}

.empty {
  height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #777;
  font-size: 15px;
}
</style>