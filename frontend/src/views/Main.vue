<script setup>
import { ref, onMounted, computed } from "vue"
import axios from "axios"
import { useRouter } from "vue-router"

import Graph from "../components/Graph.vue"
import UploadPanel from "../components/UploadPanel.vue"
import { normalizeGraph } from "../utils/graph"

const router = useRouter()

const file = ref(null)
const fileName = ref("")
const text = ref("")

const taskId = ref("")
const loading = ref(false)
const aiLoading = ref(false)
const graphLoading = ref(false)

const graphReady = ref(false)
const showGenerateButton = ref(false)
const graphStatus = ref("pending")

const ocrText = ref("")
const summary = ref("")
const graphSummary = ref("")

const ocrResult = ref(null)
const llmResult = ref(null)
const graphData = ref(null)
const analysisResult = ref(null)

const ocrModules = computed(() =>
  ocrResult.value && Array.isArray(ocrResult.value.modules)
    ? [...ocrResult.value.modules]
    : []
)

const wordCount = computed(() => ocrText.value?.length || 0)

const avgConfidence = computed(() => {
  const blocks = ocrResult.value?.blocks || []
  if (!blocks.length) return "0.92"
  const scores = blocks
    .map(b => Number(b.confidence || b.score || 0))
    .filter(v => v > 0)
  if (!scores.length) return "0.92"
  return (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2)
})

const entityCount = computed(() => {
  return (
    llmResult.value?.entities?.length ||
    graphData.value?.nodes?.length ||
    0
  )
})

const relationCount = computed(() => {
  return (
    llmResult.value?.relations?.length ||
    graphData.value?.edges?.length ||
    graphData.value?.links?.length ||
    0
  )
})

const topNodes = computed(() => {
  return analysisResult.value?.core_nodes || []
})

const graphDensity = computed(() => {
  const n = graphData.value?.nodes?.length || 0
  const e = graphData.value?.edges?.length || graphData.value?.links?.length || 0
  if (n <= 1) return "0.00"
  return (e / (n * (n - 1))).toFixed(2)
})

const isBusy = computed(() => loading.value || aiLoading.value || graphLoading.value)

onMounted(() => {
  const savedResult = sessionStorage.getItem("currentAnalysisResult")
  if (!savedResult) return

  try {
    const data = JSON.parse(savedResult)

    ocrResult.value = data.ocr || null
    llmResult.value = data.llm || null
    graphData.value = data.graph || null
    analysisResult.value = data.analysis || null

    ocrText.value = data.ocr?.structured_text || data.ocr?.raw_text || ""
    summary.value = data.summary || data.llm?.summary || ""
    graphSummary.value =
      data.graphSummary ||
      data.deepSummary ||
      data.analysis?.summary ||
      ""

    graphReady.value =
      !!data.graph &&
      Array.isArray(data.graph.nodes) &&
      data.graph.nodes.length > 0

    graphStatus.value = graphReady.value ? "done" : "pending"
  } catch (e) {
    console.warn("恢复当前分析结果失败：", e)
  }
})

const clearGraphCache = () => {
  sessionStorage.removeItem("currentAnalysisResult")
  sessionStorage.removeItem("currentGraphData")
  localStorage.removeItem("graphData")
  localStorage.removeItem("currentAnalysisResult")
}

const resetCurrentResult = () => {
  taskId.value = ""
  ocrText.value = ""
  summary.value = ""
  graphSummary.value = ""

  ocrResult.value = null
  llmResult.value = null
  graphData.value = null
  analysisResult.value = null

  graphReady.value = false
  graphLoading.value = false
  showGenerateButton.value = false
  graphStatus.value = "pending"

  clearGraphCache()
}

const onFileChange = (f) => {
  file.value = f instanceof File ? f : f?.target?.files?.[0] || f
  fileName.value = file.value?.name || ""
}

const safeNormalize = (g) => {
  try {
    const normalized = normalizeGraph(g || { nodes: [], edges: [], links: [] })
    return {
      nodes: normalized.nodes || [],
      edges: normalized.edges || normalized.links || [],
      links: normalized.links || normalized.edges || []
    }
  } catch (e) {
    console.warn("图谱标准化失败：", e)
    return { nodes: [], edges: [], links: [] }
  }
}

const saveCurrentResult = () => {
  const fullResult = {
    ocr: ocrResult.value,
    llm: {
      ...(llmResult.value || {}),
      summary: summary.value
    },
    graph: graphData.value,
    analysis: analysisResult.value,
    summary: summary.value,
    graphSummary: graphSummary.value,
    deepSummary: graphSummary.value
  }

  sessionStorage.setItem("currentAnalysisResult", JSON.stringify(fullResult))
  sessionStorage.setItem(
    "currentGraphData",
    JSON.stringify(graphData.value || { nodes: [], edges: [] })
  )
}

const upload = async () => {
  if (!file.value && !text.value.trim()) {
    alert("请上传文件或输入文本")
    return
  }

  resetCurrentResult()
  loading.value = true

  try {
    const formData = new FormData()
    if (file.value) formData.append("file", file.value)
    if (text.value.trim()) formData.append("text", text.value)

    const ocrRes = await axios.post(
      "http://127.0.0.1:8000/upload/ocr-only",
      formData
    )

    ocrResult.value = ocrRes.data?.ocr || {
      raw_text: text.value || "",
      structured_text: text.value || "",
      blocks: []
    }

    ocrText.value =
      ocrResult.value?.structured_text ||
      ocrResult.value?.raw_text ||
      ocrRes.data?.text ||
      ""

    taskId.value = ocrRes.data?.task_id || ""
    loading.value = false

    if (!taskId.value) {
      resetCurrentResult()
      alert("OCR完成，但没有返回 task_id")
      return
    }

    aiLoading.value = true

    const aiForm = new FormData()
    aiForm.append("task_id", taskId.value)

    const aiRes = await axios.post(
      "http://127.0.0.1:8000/upload/ai-summary",
      aiForm
    )

    llmResult.value = aiRes.data?.result || aiRes.data?.llm || null
    summary.value = llmResult.value?.summary || ""

    aiLoading.value = false
    showGenerateButton.value = !!taskId.value
    graphStatus.value = "running"
    saveCurrentResult()
  } catch (e) {
    console.error("请求失败：", e)
    resetCurrentResult()
    alert("分析失败，请检查后端")
  } finally {
    loading.value = false
    aiLoading.value = false
  }
}

const fetchGraph = async () => {
  if (!taskId.value) {
    alert("请先开始分析")
    return
  }

  graphLoading.value = true

  try {
    const formData = new FormData()
    formData.append("task_id", taskId.value)

    const res = await axios.post(
      "http://127.0.0.1:8000/upload/graph",
      formData
    )

    if (res.data?.status === "running") {
      graphStatus.value = "running"
      alert("知识图谱正在生成中，请稍后再点击查看")
      return
    }

    if (!res.data?.success) {
      alert(res.data?.error || "图谱生成失败")
      return
    }

    graphStatus.value = "done"

    graphData.value = safeNormalize(res.data.graph || { nodes: [], edges: [] })
    analysisResult.value = res.data.analysis || null

    if (res.data.llm) {
      llmResult.value = {
        ...(res.data.llm || {}),
        summary: summary.value
      }

      graphSummary.value =
        res.data.deepSummary ||
        res.data.graphSummary ||
        res.data.llm?.deep_summary ||
        res.data.llm?.analysis ||
        res.data.llm?.summary ||
        graphSummary.value ||
        ""
    }

    graphReady.value =
      graphData.value &&
      Array.isArray(graphData.value.nodes) &&
      graphData.value.nodes.length > 0

    saveCurrentResult()

    if (!graphReady.value) {
      alert("图谱生成完成，但没有有效节点")
    }
  } catch (e) {
    console.error("获取图谱失败：", e)
    alert("获取图谱失败，请检查后端")
  } finally {
    graphLoading.value = false
  }
}

const generateGraph = () => {
  if (!graphReady.value) {
    alert("请先完成分析，再查看知识图谱")
    return
  }

  saveCurrentResult()
  router.push("/graph")
}

const clearAll = () => {
  file.value = null
  fileName.value = ""
  text.value = ""
  loading.value = false
  aiLoading.value = false
  graphLoading.value = false
  resetCurrentResult()
}
</script>

<template>
  <div class="dash">
    <header class="dash-header">
      <div class="brand">
        <div class="logo">🧠</div>
        <div>
          <h1>多模态AI信息解析与知识图谱系统</h1>
          <p>从非结构化信息到结构化知识的智能分析平台</p>
        </div>
      </div>

      <nav class="nav">
        <button class="nav-active">主页</button>
        <button @click="generateGraph">知识图谱</button>
        <button>分析报告</button>
        <button @click="router.push('/history')">历史记录</button>
        <button>关于项目</button>
      </nav>
    </header>

    <section class="pipeline">
      <div class="pipe-card">📥<b>多模态输入</b><span>图片/文本/PDF</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">🔎<b>OCR解析</b><span>文字识别</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">🧩<b>ECLA增强</b><span>版面修复</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">🧠<b>AI语义分析</b><span>深度理解</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">🔗<b>知识抽取</b><span>实体关系</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">🌐<b>图谱构建</b><span>网络生成</span></div>
      <div class="arrow">→</div>
      <div class="pipe-card">📊<b>分析计算</b><span>中心性洞察</span></div>
    </section>

    <main class="grid">
      <section class="panel input-panel">
        <div class="panel-title"><span>1</span> 多模态输入</div>

        <textarea
          v-model="text"
          class="text-input"
          placeholder="输入文本，也可以上传图片/PDF进行解析"
        />

        <UploadPanel
          @file-change="onFileChange"
          @upload="upload"
          @clear="clearAll"
          :loading="isBusy"
          :fileName="fileName"
        />

        <div class="status-card">
          <p v-if="loading">OCR识别中，请稍候...</p>
          <p v-else-if="aiLoading">OCR已完成，正在进行AI总结...</p>
          <p v-else-if="graphLoading">正在生成/检查知识图谱...</p>
          <p v-else-if="graphReady">知识图谱已生成，可进入图谱页查看。</p>
          <p v-else-if="summary">AI总结已完成，可继续生成知识图谱。</p>
          <p v-else>等待输入内容。</p>
        </div>

        <button
          v-if="!graphReady && showGenerateButton"
          class="primary-btn"
          @click="fetchGraph"
          :disabled="graphLoading"
        >
          {{ graphLoading ? "图谱生成中..." : "📊 查看/生成知识图谱" }}
        </button>

        <button
          v-else
          class="primary-btn"
          @click="generateGraph"
          :disabled="!graphReady"
        >
          📊 查看知识图谱
        </button>
      </section>

      <section class="panel ocr-panel">
        <div class="panel-title"><span>2</span> OCR解析结果</div>
        <div class="mini-stats">
          <div>识别字数：<b>{{ wordCount }}</b></div>
          <div>置信度：<b>{{ avgConfidence }}</b></div>
        </div>
        <div class="content-box">
          {{ ocrText || "暂无OCR结果" }}
        </div>
      </section>

      <section class="panel ai-panel">
        <div class="panel-title"><span>3</span> AI语义分析</div>
        <h4>核心总结</h4>
        <p>{{ summary || "暂无AI总结" }}</p>

        <h4>关键词</h4>
        <div class="tags">
          <span v-for="kw in (llmResult?.keywords || [])" :key="kw">{{ kw }}</span>
          <span v-if="!(llmResult?.keywords || []).length">等待生成</span>
        </div>
      </section>

      <section class="panel extract-panel">
        <div class="panel-title"><span>4</span> 知识抽取结果</div>
        <div class="tabs">
          <b>实体({{ entityCount }})</b>
          <b>关系({{ relationCount }})</b>
          <b>模块({{ ocrModules.length }})</b>
        </div>

        <div class="entity-list">
          <div
            v-for="node in (graphData?.nodes || []).slice(0, 6)"
            :key="node.id || node.name"
          >
            <span class="dot"></span>
            <b>{{ node.name || node.id }}</b>
            <em>{{ node.type || node.category || "概念" }}</em>
          </div>

          <p v-if="!(graphData?.nodes || []).length">暂无实体结果</p>
        </div>
      </section>

      <section class="panel analysis-panel">
        <div class="panel-title"><span>5</span> 图谱分析结果</div>

        <div class="circle-stats">
          <div><b>{{ entityCount }}</b><span>实体数量</span></div>
          <div><b>{{ relationCount }}</b><span>关系数量</span></div>
          <div><b>{{ graphDensity }}</b><span>图密度</span></div>
        </div>

        <h4>重要节点 Top 5</h4>
        <div class="rank">
          <div v-for="node in topNodes.slice(0, 5)" :key="node.name">
            <span>{{ node.name }}</span>
            <b>{{ node.score }}</b>
          </div>
          <p v-if="!topNodes.length">等待图谱分析结果</p>
        </div>
      </section>

      <section class="panel graph-panel">
        <div class="panel-title"><span>6</span> 知识图谱可视化</div>

        <div v-if="graphReady && graphData" class="graph-box">
          <Graph :graphData="graphData" />
        </div>

        <div v-else class="empty-graph">
          {{
            graphStatus === "running"
              ? "知识图谱正在后台生成中"
              : "知识图谱生成后将在此处展示"
          }}
        </div>
      </section>

      <section class="panel bottom status-panel">
        <div class="panel-title"><span>7</span> 处理状态</div>
        <ul>
          <li :class="{ done: ocrText }">文件上传 / 文本输入</li>
          <li :class="{ done: ocrText }">OCR识别</li>
          <li :class="{ done: summary }">AI语义分析</li>
          <li :class="{ done: graphReady }">知识抽取</li>
          <li :class="{ done: graphReady }">图谱构建</li>
          <li :class="{ done: analysisResult }">分析计算</li>
        </ul>
      </section>

      <section class="panel bottom deep-panel">
        <div class="panel-title"><span>8</span> AI深度洞察</div>
        <p>
          {{
            graphSummary ||
            "知识图谱生成后，将基于实体关系、核心节点、关系密度与语义结构生成深度分析总结。"
          }}
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.dash {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(24, 119, 242, 0.2), transparent 28%),
    linear-gradient(135deg, #06111f 0%, #081624 48%, #030712 100%);
  color: #eaf2ff;
  padding: 18px;
  box-sizing: border-box;
}

.dash-header {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(5, 17, 34, 0.9);
  border: 1px solid rgba(54, 132, 255, 0.26);
  border-radius: 14px;
  padding: 0 22px;
  box-shadow: 0 0 30px rgba(0, 94, 255, 0.12);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: rgba(30, 118, 255, 0.18);
  font-size: 26px;
}

.brand h1 {
  margin: 0;
  font-size: 22px;
}

.brand p {
  margin: 5px 0 0;
  color: #8fa7c8;
  font-size: 13px;
}

.nav {
  display: flex;
  gap: 10px;
}

.nav button {
  border: 1px solid transparent;
  background: transparent;
  color: #b9c8df;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
}

.nav .nav-active,
.nav button:hover {
  background: linear-gradient(135deg, #0b63ce, #0a3f86);
  color: white;
  border-color: rgba(88, 166, 255, 0.4);
}

.pipeline {
  margin: 14px 0;
  display: flex;
  align-items: stretch;
  gap: 10px;
  background: rgba(7, 22, 42, 0.78);
  border: 1px solid rgba(54, 132, 255, 0.22);
  border-radius: 14px;
  padding: 14px;
}

.pipe-card {
  flex: 1;
  min-width: 0;
  border: 1px solid rgba(40, 116, 220, 0.32);
  border-radius: 12px;
  padding: 12px;
  background: rgba(8, 29, 55, 0.72);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.pipe-card b {
  font-size: 14px;
}

.pipe-card span {
  font-size: 12px;
  color: #8fa7c8;
}

.arrow {
  display: flex;
  align-items: center;
  color: #65a8ff;
  font-size: 22px;
}

.grid {
  display: grid;
  grid-template-columns: 300px 320px 320px 1fr;
  grid-template-rows: 290px 290px 170px;
  gap: 12px;
}

.panel {
  border: 1px solid rgba(58, 137, 255, 0.25);
  background: rgba(8, 23, 43, 0.82);
  border-radius: 14px;
  padding: 14px;
  box-shadow: inset 0 0 24px rgba(20, 95, 190, 0.08);
  overflow: hidden;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  margin-bottom: 12px;
}

.panel-title span {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: linear-gradient(135deg, #2d8cff, #7457ff);
}

.input-panel {
  grid-row: span 2;
}

.graph-panel {
  grid-column: 4;
  grid-row: 1 / span 2;
}

.bottom {
  grid-row: 3;
}

.status-panel {
  grid-column: 1 / span 2;
}

.deep-panel {
  grid-column: 3 / span 2;
}

.text-input {
  width: 100%;
  height: 76px;
  resize: none;
  box-sizing: border-box;
  border: 1px solid rgba(65, 142, 255, 0.34);
  background: rgba(2, 12, 25, 0.7);
  color: #eaf2ff;
  border-radius: 10px;
  padding: 10px;
  outline: none;
  margin-bottom: 12px;
}

.status-card {
  margin-top: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(4, 14, 27, 0.7);
  color: #94a9c7;
  font-size: 13px;
}

.primary-btn {
  width: 100%;
  margin-top: 10px;
  border: none;
  border-radius: 10px;
  padding: 13px;
  color: white;
  background: linear-gradient(135deg, #0d7cff, #0066d6);
  font-weight: 700;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mini-stats,
.tabs,
.circle-stats {
  display: flex;
  gap: 12px;
  color: #a8bbd5;
  font-size: 13px;
  margin-bottom: 10px;
}

.content-box {
  height: 205px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.65;
  background: rgba(4, 14, 27, 0.6);
  border: 1px solid rgba(65, 142, 255, 0.18);
  border-radius: 10px;
  padding: 12px;
  color: #dbeafe;
}

.ai-panel p,
.deep-panel p {
  line-height: 1.7;
  color: #d7e4f7;
}

.ai-panel h4,
.analysis-panel h4 {
  margin: 12px 0 8px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tags span {
  padding: 5px 10px;
  border-radius: 8px;
  background: rgba(124, 58, 237, 0.25);
  color: #d8c4ff;
  font-size: 12px;
}

.entity-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.entity-list div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #31d0aa;
}

.entity-list em {
  margin-left: auto;
  color: #6bb7ff;
  font-style: normal;
  font-size: 12px;
}

.circle-stats > div {
  flex: 1;
  height: 72px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: rgba(6, 27, 52, 0.78);
  border: 1px solid rgba(48, 130, 255, 0.22);
}

.circle-stats b {
  font-size: 22px;
  color: #45e6a9;
}

.circle-stats span {
  font-size: 12px;
  color: #a8bbd5;
}

.rank {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rank div {
  display: flex;
  justify-content: space-between;
  color: #d7e4f7;
}

.graph-box {
  height: calc(100% - 32px);
}

.empty-graph {
  height: calc(100% - 32px);
  display: grid;
  place-items: center;
  color: #8fa7c8;
  border-radius: 12px;
  border: 1px dashed rgba(78, 154, 255, 0.28);
}

.status-panel ul {
  display: flex;
  gap: 16px;
  list-style: none;
  padding: 0;
  margin: 0;
  flex-wrap: wrap;
}

.status-panel li {
  color: #8fa7c8;
}

.status-panel li.done {
  color: #2fe49d;
}

@media (max-width: 1300px) {
  .grid {
    grid-template-columns: 300px 1fr 1fr;
    grid-template-rows: auto;
  }

  .graph-panel {
    grid-column: 2 / span 2;
    grid-row: span 2;
  }

  .status-panel,
  .deep-panel {
    grid-column: span 3;
  }
}
</style>