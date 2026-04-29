<script setup>
import { ref, onMounted, computed } from "vue"
import axios from "axios"

import Graph from "../components/Graph.vue"
import UploadPanel from "../components/UploadPanel.vue"
import ResultPanel from "../components/ResultPanel.vue"
import { normalizeGraph } from "../utils/graph"
import { useRouter } from "vue-router"

const router = useRouter()

const file = ref(null)
const fileName = ref("")
const text = ref("")

const taskId = ref("")
const graphReady = ref(false)
const graphLoading = ref(false)
const showGenerateButton = ref(false)

const graphData = ref(null)
const analysisResult = ref(null)

const loading = ref(false)
const aiLoading = ref(false)

const ocrText = ref("")
const summary = ref("")
const graphSummary = ref("")
const ocrResult = ref(null)
const llmResult = ref(null)

const history = ref([])
const graphStatus = ref("pending")
const showGraph = ref(false)

const ocrModules = computed(() => {
  return ocrResult.value && Array.isArray(ocrResult.value.modules)
    ? [...ocrResult.value.modules]
    : []
})

onMounted(() => {
  const savedHistory = localStorage.getItem("history")
  if (savedHistory) {
    try {
      history.value = JSON.parse(savedHistory)
    } catch {
      history.value = []
    }
  }

  // 从图谱页返回时恢复当前结果，不清空
  const savedResult = sessionStorage.getItem("currentAnalysisResult")

  if (savedResult) {
    try {
      const data = JSON.parse(savedResult)

      ocrResult.value = data.ocr || null
      llmResult.value = data.llm || null
      graphData.value = data.graph || null
      analysisResult.value = data.analysis || null

      ocrText.value =
        data.ocr?.structured_text ||
        data.ocr?.raw_text ||
        ""

      summary.value =
      data.summary ||
      data.llm?.summary ||
      ""
      graphStatus.value = "running"

      graphSummary.value =
      data.graphSummary ||
      ""
      graphReady.value =
        !!data.graph &&
        Array.isArray(data.graph.nodes) &&
        data.graph.nodes.length > 0
    } catch (e) {
      console.warn("恢复当前分析结果失败：", e)
    }
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
  showGraph.value = false

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
    return {
      nodes: [],
      edges: [],
      links: []
    }
  }
}

const saveCurrentResult = () => {
  const fullResult = {
  ocr: ocrResult.value,
  llm: {
    ...(llmResult.value || {}),
    summary: summary.value   // 快速AI总结固定存在 llm.summary
  },
  graph: graphData.value,
  analysis: analysisResult.value,
  summary: summary.value,
  graphSummary: graphSummary.value
}

  sessionStorage.setItem(
    "currentAnalysisResult",
    JSON.stringify(fullResult)
  )

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

  // 新分析前清掉旧结果，避免失败后显示上一次
  resetCurrentResult()

  loading.value = true
  aiLoading.value = false
  graphLoading.value = false

  try {
    const formData = new FormData()

    if (file.value) formData.append("file", file.value)
    if (text.value.trim()) formData.append("text", text.value)

    // 1. OCR
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

    // 2. AI总结
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

    // 不在这里同步生成图谱：后端已在 /upload 接口或 /upload 自动触发后台生成
    // 前端在收到 AI 总结后立即显示，并提供按钮让用户手动请求或轮询图谱。
    showGenerateButton.value = !!taskId.value
  } catch (e) {
    console.error("请求失败：", e)
    resetCurrentResult()
    alert("分析失败，请检查后端")
  } finally {
    loading.value = false
    aiLoading.value = false
    graphLoading.value = false
  }
}

const saveHistory = (data) => {
  const record = {
    time: new Date().toLocaleString(),
    summary: data?.result?.summary || "",
    ocr:
      data?.ocr?.structured_text ||
      data?.ocr?.raw_text ||
      "",
    graph: data?.graph || null,
    analysis: data?.analysis || null
  }

  history.value.push(record)
  localStorage.setItem("history", JSON.stringify(history.value))
}

const generateGraph = () => {
  if (
    !graphReady.value ||
    !graphData.value ||
    !Array.isArray(graphData.value.nodes) ||
    graphData.value.nodes.length === 0
  ) {
    alert("请先完成分析，再查看知识图谱")
    return
  }

  saveCurrentResult()
  router.push("/graph")
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

    const rawGraph = res.data.graph || { nodes: [], edges: [] }
    graphData.value = safeNormalize(rawGraph)

    analysisResult.value = res.data.analysis || null

    if (res.data.llm) {
      llmResult.value = {
        ...(res.data.llm || {}),
        summary: summary.value
      }

      graphSummary.value =
        res.data.llm?.summary ||
        graphSummary.value ||
        ""
    }

    graphReady.value =
      graphData.value &&
      Array.isArray(graphData.value.nodes) &&
      graphData.value.nodes.length > 0

    saveCurrentResult()

    if (graphReady.value) {
      router.push("/graph")
    } else {
      alert("图谱生成完成，但没有有效节点")
    }
  } catch (e) {
    console.error("获取图谱失败：", e)
    alert("获取图谱失败，请检查后端")
  } finally {
    graphLoading.value = false
  }
}

const clearAll = () => {
  file.value = null
  fileName.value = ""
  text.value = ""

  loading.value = false
  aiLoading.value = false
  graphLoading.value = false

  // 清空所有结果（你已有）
  resetCurrentResult()

  // ⭐ 确保图谱状态彻底重置
  graphStatus.value = "pending"
  graphSummary.value = ""

  // ⭐ 建议补这两个（防止残留）
  showGraph.value = false
  graphReady.value = false
}
</script>

<template>
  <div class="app">
    <header class="header">
      <h2>多模态AI信息解析系统</h2>

      <div class="topbar">
        <button class="history-btn" @click="router.push('/history')">
          历史记录
        </button>
      </div>
    </header>

    <div class="container">
      <div class="left">
        <textarea
          v-model="text"
          class="text-input"
          placeholder="输入文本"
        />

        <UploadPanel
          @file-change="onFileChange"
          @upload="upload"
          @clear="clearAll"
          :loading="loading || aiLoading || graphLoading"
          :fileName="fileName"
        />

        <div class="status">
          <p v-if="loading">正在识别OCR，请稍候...</p>
          <p v-else-if="aiLoading">OCR已完成，正在进行AI总结...</p>
          <p v-else-if="graphLoading">正在检查/生成知识图谱...</p>
          <p v-else-if="graphReady">知识图谱已生成，可以点击查看。</p>
          <p v-else-if="graphStatus === 'running'">
            AI总结已完成，知识图谱正在后台生成中。
          </p>
          <p v-else-if="summary">
            AI总结已完成，可点击下方按钮查看知识图谱。
          </p>
        </div>

        <div class="topbar">
          <button
            v-if="!graphReady && showGenerateButton"
            class="nav-btn primary"
            @click="fetchGraph"
            :disabled="graphLoading"
          >
            {{
              graphLoading
                ? "图谱检查中..."
                : graphStatus === "running"
                  ? "⏳ 图谱生成中，点击查看进度"
                  : "📊 查看/生成知识图谱"
            }}
          </button>

          <button
            v-else
            class="nav-btn primary"
            @click="generateGraph"
            :disabled="!graphReady"
          >
            📊 查看知识图谱
          </button>
        </div>
      </div>

      <div class="middle">
        <ResultPanel
          :ocr="ocrText"
          :summary="summary"
          :graphSummary="graphSummary"
          :modules="ocrModules"
          :analysis="analysisResult"
        />
      </div>

      <div class="right">
        <div v-if="showGraph && graphData">
          <Graph :graphData="graphData" />
        </div>

        <div v-else class="empty-graph">
          <p>
            {{
              graphReady
                ? "知识图谱已生成，点击“查看知识图谱”进入图谱页"
                : graphStatus === "running"
                  ? "知识图谱正在后台生成中"
                  : "点击“查看/生成知识图谱”查看结构"
            }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.container {
  display: flex;
  height: calc(100vh - 60px);
}

.left,
.middle,
.right {
  padding: 10px;
}

.left {
  width: 30%;
  border-right: 1px solid #eee;
}

.middle {
  width: 50%;
  border-right: 1px solid #eee;
  overflow-y: auto;
}

.right {
  width: 20%;
}

.text-input {
  width: 100%;
  height: 120px;
}

.header {
  height: 60px;
  background: #111;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.graph-btn {
  margin-top: 10px;
  padding: 8px 12px;
  background: #409eff;
  color: white;
  border: none;
  cursor: pointer;
}

.graph-btn:disabled {
  background: #ccc;
}

.empty-graph {
  color: #999;
  text-align: center;
  margin-top: 50px;
}

.status {
  font-size: 14px;
  color: #666;
  margin-top: 8px;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>