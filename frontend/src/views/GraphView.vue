<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import Graph from "../components/Graph.vue"

const router = useRouter()

const graphData = ref({
  nodes: [],
  edges: []
})

const analysisResult = ref({
  core_nodes: [],
  important_paths: [],
  metrics: {}
})

const loadGraphData = () => {
  graphData.value = {
    nodes: [],
    edges: []
  }

  analysisResult.value = {
    core_nodes: [],
    important_paths: [],
    metrics: {}
  }

  const savedResult = sessionStorage.getItem("currentAnalysisResult")

  if (!savedResult) {
    return
  }

  try {
    const result = JSON.parse(savedResult)

    if (result.graph && result.graph.nodes && result.graph.nodes.length > 0) {
      graphData.value = {
        nodes: result.graph.nodes || [],
        edges: result.graph.edges || result.graph.links || []
      }
    }

    if (result.analysis) {
      analysisResult.value = {
        core_nodes: result.analysis.core_nodes || [],
        important_paths: result.analysis.important_paths || [],
        metrics: result.analysis.metrics || {}
      }
    }
  } catch (err) {
    console.error("解析 currentAnalysisResult 失败", err)
  }
}

const formatScore = (value) => {
  const num = Number(value || 0)
  return num.toFixed(3)
}

const goBack = () => {
  router.push("/main")
}

onMounted(() => {
  loadGraphData()
})
</script>

<template>
  <div class="graph-page">
    <div class="topbar">
      <button class="back-btn" @click="goBack">
        ← 返回首页
      </button>

      <div>
        <h2>知识图谱可视化分析</h2>
        <p>节点大小根据综合重要性自动调整，关系标签展示实体之间的语义联系。</p>
      </div>
    </div>

    <div
      v-if="graphData && graphData.nodes && graphData.nodes.length > 0"
      class="content"
    >
      <div class="graph-card">
        <Graph :graphData="graphData" />
      </div>

      <div class="side-panel">
        <div class="panel-card">
          <h3>核心内容分析</h3>

          <div
            v-if="analysisResult.core_nodes && analysisResult.core_nodes.length > 0"
            class="core-list"
          >
            <div
              v-for="node in analysisResult.core_nodes"
              :key="node.name"
              class="core-item"
            >
              <div class="core-name">
                {{ node.name }}
              </div>

              <div class="core-score">
                重要性：{{ formatScore(node.score) }}
              </div>

              <div class="core-reason">
                {{ node.reason || "该节点在当前图谱中具有较高关联度。" }}
              </div>
            </div>
          </div>

          <div v-else class="empty-small">
            暂无核心内容分析
          </div>
        </div>

        <div class="panel-card">
          <h3>关键关系路径</h3>

          <div
            v-if="analysisResult.important_paths && analysisResult.important_paths.length > 0"
            class="path-list"
          >
            <div
              v-for="(path, index) in analysisResult.important_paths"
              :key="index"
              class="path-item"
            >
              {{ path.join(" → ") }}
            </div>
          </div>

          <div v-else class="empty-small">
            暂无明显关键路径
          </div>
        </div>

        <div class="panel-card">
          <h3>图谱统计</h3>
          <p>节点数量：{{ graphData.nodes.length }}</p>
          <p>关系数量：{{ graphData.edges.length }}</p>
        </div>

        <div class="panel-card tip-card">
          <h3>说明</h3>
          <p>节点越大，表示其在当前图谱中的综合重要性越高。</p>
          <p>边上的文字表示实体之间的关系类型。</p>
        </div>
      </div>
    </div>

    <div v-else class="empty-page">
      <h3>暂无图谱数据</h3>
      <p>请先返回首页上传图片或输入文本，并完成分析。</p>
      <button @click="router.push('/main')">
        返回首页
      </button>
    </div>
  </div>
</template>

<style scoped>
.graph-page {
  min-height: 100vh;
  background: #f4f6fb;
  padding: 24px;
  box-sizing: border-box;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 20px;
}

.topbar h2 {
  margin: 0;
  font-size: 24px;
  color: #111827;
}

.topbar p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 14px;
}

.back-btn {
  border: none;
  background: #111827;
  color: white;
  padding: 9px 16px;
  border-radius: 10px;
  cursor: pointer;
}

.content {
  display: grid;
  grid-template-columns: 1fr 330px;
  gap: 20px;
}

.graph-card {
  height: calc(100vh - 130px);
  min-height: 560px;
  background: white;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  background: white;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.panel-card h3 {
  margin: 0 0 12px;
  font-size: 17px;
  color: #111827;
}

.core-item {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px 0;
}

.core-item:last-child {
  border-bottom: none;
}

.core-name {
  font-weight: 700;
  color: #111827;
}

.core-score {
  margin-top: 4px;
  color: #2563eb;
  font-size: 14px;
}

.core-reason {
  margin-top: 6px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.6;
}

.path-item {
  background: #f3f4f6;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
  color: #374151;
  font-size: 14px;
  line-height: 1.5;
}

.empty-small {
  color: #9ca3af;
  font-size: 14px;
}

.tip-card p {
  margin: 6px 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.5;
}

.empty-page {
  background: white;
  border-radius: 18px;
  padding: 60px;
  text-align: center;
  color: #6b7280;
}

.empty-page h3 {
  color: #111827;
}

.empty-page button {
  margin-top: 18px;
  border: none;
  background: #2563eb;
  color: white;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
}
</style>