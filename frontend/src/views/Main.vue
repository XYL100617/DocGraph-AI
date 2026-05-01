<script setup>
import { ref, onMounted, computed } from "vue"
import axios from "axios"
import { useRouter } from "vue-router"

import Graph from "../components/Graph.vue"
import UploadPanel from "../components/UploadPanel.vue"
import { normalizeGraph } from "../utils/graph"

const router = useRouter()
const API_BASE = "http://127.0.0.1:8000"

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

const taskStartedAt = ref(0)
const finishedAt = ref(0)
const uploadMode = ref("image")

const markTime = (phase) => {
  timeline.value[phase] = new Date().toLocaleTimeString("zh-CN", {
    hour12: false
  })
}

const timeline = ref({
  upload: "",
  ocr: "",
  ai: "",
  graph: "",
  analysis: ""
})

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
    .map((b) => Number(b.confidence || b.score || 0))
    .filter((v) => v > 0)

  if (!scores.length) return "0.92"
  return (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2)
})

const entityCount = computed(() => {
  return graphData.value?.nodes?.length || llmResult.value?.entities?.length || 0
})

const relationCount = computed(() => {
  return (
    graphData.value?.edges?.length ||
    graphData.value?.links?.length ||
    llmResult.value?.relations?.length ||
    0
  )
})

const topNodes = computed(() => {
  return analysisResult.value?.core_nodes || []
})

const centralityRadar = computed(() => {
  const list = topNodes.value.slice(0, 5)

  if (!list.length) {
    return {
      points: "90,20 150,60 128,130 52,130 30,60",
      items: []
    }
  }

  const base = [
    [90, 20],
    [150, 60],
    [128, 130],
    [52, 130],
    [30, 60]
  ]

  const center = [90, 82]
  const maxScore = Math.max(...list.map(n => Number(n.score || 0)), 1)

  const points = base.map(([x, y], i) => {
    const score = Number(list[i]?.score || 0) / maxScore
    const px = center[0] + (x - center[0]) * score
    const py = center[1] + (y - center[1]) * score
    return `${px},${py}`
  }).join(" ")

  return { points, items: list }
})

const graphDensity = computed(() => {
  const n = graphData.value?.nodes?.length || 0
  const e = graphData.value?.edges?.length || graphData.value?.links?.length || 0
  if (n <= 1) return "0.00"
  return (e / (n * (n - 1))).toFixed(2)
})

const processingSeconds = computed(() => {
  if (!taskStartedAt.value) return "0.00"
  const end = finishedAt.value || Date.now()
  return ((end - taskStartedAt.value) / 1000).toFixed(2)
})

const displayedKeywords = computed(() => {
  if (graphReady.value && graphData.value?.nodes?.length) {
    return graphData.value.nodes
      .map((n) => n.name || n.id)
      .filter(Boolean)
      .slice(0, 8)
  }

  return llmResult.value?.keywords || []
})

const deepSummaryText = computed(() => {
  if (!graphReady.value) {
    return "知识图谱生成后并结合实体关系、核心节点与图谱结构生成深度总结。"
  }

  if (graphSummary.value && graphSummary.value.length > 20) {
    return graphSummary.value
  }

  const entity = entityCount.value
  const relation = relationCount.value
  const density = graphDensity.value
  const core = topNodes.value.slice(0, 3).map(n => n.name).join("、")
  const path = analysisResult.value?.important_paths?.[0]

  return core
      ? `核心语义集中在 ${core}，存在一定的语义关联与结构关系。`
      : `当前图谱核心节点尚不明显，知识结构仍以分散表达为主。`
    
})

const processList = computed(() => [
  { name: "文件上传", done: !!timeline.value.upload, time: timeline.value.upload || "--:--:--" },
  { name: "OCR识别", done: !!timeline.value.ocr, time: timeline.value.ocr || "--:--:--" },
  { name: "语义分析", done: !!timeline.value.ai, time: timeline.value.ai || "--:--:--" },
  { name: "知识抽取", done: !!entityCount.value, time: timeline.value.graph || "--:--:--" },
  { name: "图谱构建", done: graphReady.value, time: timeline.value.graph || "--:--:--" },
  { name: "分析计算", done: !!analysisResult.value, time: timeline.value.analysis || "--:--:--" }
])

const systemInfo = computed(() => [
  { label: "处理时长", value: `${processingSeconds.value}s` },
  { label: "OCR引擎", value: "PaddleOCR" },
  { label: "语义模型", value: "qwen-plus / qwen-vl-plus" },
  { label: "图算法", value: "NetworkX 3.2 + 多中心性融合" }
])

const insightCards = computed(() => {
  const path = (analysisResult.value?.important_paths || [])[0]

  return [
    {
      title: "应用价值",
      content: path ? `关键路径：${path.join(" -> ")}。` : "图谱生成后将自动提取关键路径。"
    },
    {
      title: "发展趋势",
      content: graphReady.value
        ? "系统可继续扩展为课堂知识追踪、学习路径推荐和知识点复习辅助模块。"
        : "完成图谱生成后，将进一步分析知识结构与应用价值。"
    }
  ]
})

const isBusy = computed(() => loading.value || aiLoading.value || graphLoading.value)

onMounted(() => {

  const savedResult = sessionStorage.getItem("currentAnalysisResult")
  if (!savedResult) return

  try {
    const data = JSON.parse(savedResult)

    taskId.value = data.taskId || ""
    ocrResult.value = data.ocr || null
    llmResult.value = data.llm || null
    graphData.value = data.graph || null
    analysisResult.value = data.analysis || null
    timeline.value = data.timeline || timeline.value
    taskStartedAt.value = data.taskStartedAt || 0
    finishedAt.value = data.finishedAt || 0

    ocrText.value = data.ocr?.structured_text || data.ocr?.raw_text || data.ocrText || ""
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

    showGenerateButton.value = !!taskId.value
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
  taskStartedAt.value = 0
  finishedAt.value = 0

  timeline.value = {
    upload: "",
    ocr: "",
    ai: "",
    graph: "",
    analysis: ""
  }

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
    taskId: taskId.value,
    taskStartedAt: taskStartedAt.value,
    finishedAt: finishedAt.value,
    timeline: timeline.value,
    inputText: text.value,
    fileName: fileName.value || "文本输入",
    ocr: ocrResult.value,
    ocrText: ocrText.value,
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
  taskStartedAt.value = Date.now()
  markTime("upload")

  try {
    const formData = new FormData()
    if (file.value) formData.append("file", file.value)
    if (text.value.trim()) formData.append("text", text.value)

    const ocrRes = await axios.post(`${API_BASE}/upload/ocr-only`, formData)

    ocrResult.value = ocrRes.data?.ocr || {
      raw_text: text.value || "",
      structured_text: text.value || "",
      blocks: []
    }

    ocrText.value =
      ocrResult.value?.structured_text ||
      ocrResult.value?.raw_text ||
      ocrRes.data?.text ||
      text.value ||
      ""

    taskId.value = ocrRes.data?.task_id || ""
    markTime("ocr")
    loading.value = false

    if (!taskId.value) {
      resetCurrentResult()
      alert("OCR完成，但没有返回 task_id")
      return
    }

    aiLoading.value = true

    const aiForm = new FormData()
    aiForm.append("task_id", taskId.value)

    const aiRes = await axios.post(`${API_BASE}/upload/ai-summary`, aiForm)

    llmResult.value = aiRes.data?.result || aiRes.data?.llm || null
    summary.value = llmResult.value?.summary || ""
    markTime("ai")

    aiLoading.value = false
    showGenerateButton.value = !!taskId.value
    graphStatus.value = "pending"
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

const saveFullHistory = () => {
  const deepCopy = (obj) => {
  try {
    return JSON.parse(JSON.stringify(obj))
  } catch {
    return null
  }
}

const record = {
  id: Date.now(),
  time: new Date().toLocaleString(),
  taskId: taskId.value,

  taskStartedAt: taskStartedAt.value,
  finishedAt: finishedAt.value,
  timeline: deepCopy(timeline.value),

  fileName: fileName.value || "文本输入",
  inputText: text.value,

  ocr: deepCopy(ocrResult.value),
  ocrText: ocrText.value,

  llm: deepCopy(llmResult.value),
  summary: summary.value,

  graphSummary: graphSummary.value,
  deepSummary: graphSummary.value,

  graph: deepCopy(graphData.value),
  analysis: deepCopy(analysisResult.value),

  entityCount: entityCount.value,
  relationCount: relationCount.value,
  status: graphReady.value ? "已生成图谱" : "仅AI总结"
}

  const old = JSON.parse(localStorage.getItem("history") || "[]")
  const next = [record, ...old].slice(0, 100)
  localStorage.setItem("history", JSON.stringify(next))
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

    const res = await axios.post(`${API_BASE}/upload/graph`, formData)

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
    markTime("graph")

    const rawGraph = res.data.graph || { nodes: [], edges: [] }
    graphData.value = safeNormalize(rawGraph)

    analysisResult.value = res.data.analysis || null
    if (analysisResult.value) markTime("analysis")

    graphSummary.value =
      res.data.graphSummary ||
      res.data.deepSummary ||
      res.data.analysis?.summary ||
      res.data.analysis?.deep_summary ||
      res.data.llm?.deep_summary ||
      res.data.llm?.analysis ||
      ""

    if (res.data.llm) {
      llmResult.value = {
        ...(res.data.llm || {}),
        summary: summary.value
      }
    }

    graphReady.value =
      graphData.value &&
      Array.isArray(graphData.value.nodes) &&
      graphData.value.nodes.length > 0

    finishedAt.value = Date.now()

    saveCurrentResult()
    saveFullHistory()

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

const generateGraph = () => {
  if (!graphReady.value) {
    alert("请先完成分析，再查看知识图谱")
    return
  }

  saveCurrentResult()
  router.push("/graph")
}

const goReport = () => {
  if (!summary.value && !graphReady.value) {
    alert("请先完成分析再查看报告")
    return
  }

  const enhancedSummary =
    graphSummary.value ||
    deepSummaryText.value ||
    ""

  sessionStorage.setItem(
    "reportData",
    JSON.stringify({
      time: new Date().toLocaleString(),
      taskId: taskId.value,
      fileName: fileName.value || "文本输入",
      inputText: text.value,

      ocrText: ocrText.value,
      summary: summary.value,

      // ⭐ 关键：报告页就靠这两个字段显示模块4内容
      graphSummary: enhancedSummary,
      deepSummary: enhancedSummary,

      graph: graphData.value,
      analysis: analysisResult.value,
      entityCount: entityCount.value,
      relationCount: relationCount.value,
      graphDensity: graphDensity.value,
      topNodes: topNodes.value,
      timeline: timeline.value,
      systemInfo: systemInfo.value
    })
  )

  router.push("/report")
}

const showOcrModal = ref(false)

const showDeepModal = ref(false)

const copyDeepSummary = async () => {
  if (!deepSummaryText.value) {
    alert("暂无图谱增强AI总结可复制")
    return
  }

  try {
    await navigator.clipboard.writeText(deepSummaryText.value)
    alert("图谱增强AI总结已复制")
  } catch (e) {
    console.error("复制失败：", e)
    alert("复制失败，请手动选择文本复制")
  }
}

const copyOcrText = async () => {
  if (!ocrText.value) {
    alert("暂无OCR内容可复制")
    return
  }

  try {
    await navigator.clipboard.writeText(ocrText.value)
    alert("OCR结果已复制")
  } catch (e) {
    console.error("复制失败：", e)
    alert("复制失败，请手动选择文本复制")
  }
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

const onModeChange = (mode) => {
  uploadMode.value = mode

  if (mode !== "text") {
    text.value = ""
  }

  if (mode === "text") {
    file.value = null
    fileName.value = ""
  }
}
</script>

<template>
  <div class="dash">
    <header class="dash-header">
      <div class="brand">
        <div class="logo sys-logo">
          <svg viewBox="0 0 64 64" class="sys-logo-svg">
            <!-- 上方知识图谱网络：按图片样式重画 -->
            <circle cx="32" cy="7" r="2.2" />
            <circle cx="20" cy="13" r="2" />
            <circle cx="44" cy="13" r="2" />
            <circle cx="16" cy="26" r="2" />
            <circle cx="26" cy="32" r="2" />
            <circle cx="38" cy="32" r="2" />
            <circle cx="48" cy="26" r="2" />
            <circle cx="32" cy="21" r="2.3" />

            <!-- 外轮廓连线 -->
            <path d="M32 7 L20 13 L16 26 L26 32 L38 32 L48 26 L44 13 L32 7" />

            <!-- 中心辐射连线 -->
            <path d="M32 21 L32 7" />
            <path d="M32 21 L20 13" />
            <path d="M32 21 L44 13" />
            <path d="M32 21 L16 26" />
            <path d="M32 21 L26 32" />
            <path d="M32 21 L38 32" />
            <path d="M32 21 L48 26" />

            <!-- 交叉关系连线 -->
            <path d="M20 13 L38 32" />
            <path d="M44 13 L26 32" />
            <path d="M16 26 L44 13" />
            <path d="M48 26 L20 13" />

            <!-- 打开的书：左页 -->
            <path d="M10 54 C16 47 24 45 32 51" />
            <path d="M10 54 L10 39 C17 35 25 37 32 44 L32 51" />
            <path d="M15 43 C20 40 25 41 29 45" />
            <path d="M15 48 C20 45 25 46 29 49" />

            <!-- 打开的书：右页 -->
            <path d="M54 54 C48 47 40 45 32 51" />
            <path d="M54 54 L54 39 C47 35 39 37 32 44 L32 51" />
            <path d="M49 43 C44 40 39 41 35 45" />
            <path d="M49 48 C44 45 39 46 35 49" />

            <!-- 底部书托 -->
            <path d="M9 58 C17 53 25 54 32 59 C39 54 47 53 55 58" />
          </svg>
        </div>

        <div>
          <h1>多模态AI信息解析与知识图谱系统</h1>
          <p>从非结构化信息到结构化知识的智能分析平台</p>
        </div>
      </div>

      <nav class="nav">
        <button class="nav-active" @click="router.push('/main')">主页</button>
        <button @click="generateGraph">知识图谱</button>
        <button @click="goReport">分析报告</button>
        <button @click="router.push('/history')">历史记录</button>
        <button @click="router.push('/about')">关于项目</button>
      </nav>

      <div class="tools">
        <button class="user-pill" type="button">
          <span class="user-avatar">
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21c1.6-4.2 4.4-6 8-6s6.4 1.8 8 6" />
            </svg>
          </span>
          <span>本地用户</span>
        </button>
      </div>
    </header>

    <section class="pipeline">
      <div class="pipe-card step-blue">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <rect x="4" y="5" width="16" height="14" rx="3" />
            <path d="M8 13l2.5-3 3 4 2-2.5L20 17" />
            <circle cx="8" cy="9" r="1.5" />
          </svg>
        </div>
        <div class="text">
          <b>多模态输入</b>
          <span>图片/文本/PDF</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-cyan">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <path d="M4 7V5a1 1 0 0 1 1-1h2" />
            <path d="M17 4h2a1 1 0 0 1 1 1v2" />
            <path d="M20 17v2a1 1 0 0 1-1 1h-2" />
            <path d="M7 20H5a1 1 0 0 1-1-1v-2" />
            <path d="M8 12h8" />
            <path d="M8 9h8" />
            <path d="M8 15h5" />
          </svg>
        </div>
        <div class="text">
          <b>OCR解析</b>
          <span>文字识别</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-purple">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <path d="M12 3a6 6 0 0 0-6 6v2a6 6 0 0 0 12 0V9a6 6 0 0 0-6-6Z" />
            <path d="M8 14v3" />
            <path d="M16 14v3" />
            <path d="M9 21h6" />
            <path d="M12 15v6" />
          </svg>
        </div>
        <div class="text">
          <b>AI语义分析</b>
          <span>摘要关键词</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-violet">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <circle cx="6" cy="7" r="3" />
            <circle cx="18" cy="7" r="3" />
            <circle cx="12" cy="17" r="3" />
            <path d="M8.5 8.5 10.5 15" />
            <path d="M15.5 8.5 13.5 15" />
            <path d="M9 17h6" />
          </svg>
        </div>
        <div class="text">
          <b>知识抽取</b>
          <span>实体关系</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-blue">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="3" />
            <circle cx="5" cy="6" r="2" />
            <circle cx="19" cy="6" r="2" />
            <circle cx="5" cy="18" r="2" />
            <circle cx="19" cy="18" r="2" />
            <path d="M7 7.5 10 10" />
            <path d="M17 7.5 14 10" />
            <path d="M7 16.5 10 14" />
            <path d="M17 16.5 14 14" />
          </svg>
        </div>
        <div class="text">
          <b>图谱构建</b>
          <span>网络生成</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-gold">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <path d="M4 19V5" />
            <path d="M4 19h16" />
            <rect x="7" y="11" width="3" height="5" rx="1" />
            <rect x="12" y="7" width="3" height="9" rx="1" />
            <rect x="17" y="4" width="3" height="12" rx="1" />
          </svg>
        </div>
        <div class="text">
          <b>分析计算</b>
          <span>图分析洞察</span>
        </div>
      </div>

      <div class="arrow">→</div>

      <div class="pipe-card step-orange">
        <div class="icon">
          <svg viewBox="0 0 24 24">
            <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </div>
        <div class="text">
          <b>可视化展示</b>
          <span>图谱交互</span>
        </div>
      </div>
    </section>

    <main class="grid">
      <section class="panel input-panel">
        <div class="panel-title"><span>1</span> 多模态输入</div>

        <UploadPanel
          @file-change="onFileChange"
          @mode-change="onModeChange"
          @upload="upload"
          @generate-graph="fetchGraph"
          @clear="clearAll"
          v-model:textValue="text"
          :loading="isBusy"
          :graphLoading="graphLoading"
          :graphReady="graphReady"
          :canGenerateGraph="showGenerateButton || graphReady"
          :fileName="fileName"
        />

        <div class="status-card">
          <p v-if="loading">🔎 OCR识别中，请稍候...</p>
          <p v-else-if="aiLoading">🧠 OCR已完成，正在进行AI总结...</p>
          <p v-else-if="graphLoading">🌐 正在生成知识图谱与深度总结...</p>
          <p v-else-if="graphReady">✅ 知识图谱已生成，可进入图谱页查看。</p>
          <p v-else-if="summary">✨ AI总结已完成，可继续生成知识图谱。</p>
          <p v-else>💡 请上传图片/PDF，或切换到“文本输入”粘贴内容。</p>
        </div>
      </section>

      <section class="panel ocr-panel">
        <div class="panel-title panel-title-between">
          <div><span>2</span> OCR解析结果</div>

          <div class="ocr-actions">
            <button @click="copyOcrText" title="复制OCR结果">复制</button>
            <button @click="showOcrModal = true" title="放大查看OCR结果">放大</button>
          </div>
        </div>
        <div class="mini-stats">
          <div>识别字数：<b>{{ wordCount }}</b></div>
          <div>置信度：<b>{{ avgConfidence }}</b></div>
          <div>模块数：<b>{{ ocrModules.length }}</b></div>
        </div>
        <div class="content-box">
          {{ ocrText || "暂无OCR结果" }}
        </div>
      </section>

      <section class="panel ai-panel">
        <div class="panel-title"><span>3</span> AI语义分析</div>
        <h4>快速总结</h4>
        <p>{{ summary || "暂无AI总结" }}</p>

        <h4>关键词</h4>
        <div class="tags">
          <span v-for="kw in displayedKeywords" :key="kw">{{ kw }}</span>
          <span v-if="!displayedKeywords.length">AI总结后生成基础关键词，图谱生成后更新为结构化关键词</span>
        </div>

        <div class="ai-foot">
          <span>特点：快速生成</span>
          <span>质量：基础摘要</span>
        </div>
      </section>

      <section class="panel extract-panel">
        <div class="panel-title panel-title-between">
          <div><span>4</span> 图谱增强AI总结</div>

          <div class="ocr-actions">
            <button @click="copyDeepSummary" title="复制图谱增强AI总结">复制</button>
            <button @click="showDeepModal = true" title="放大查看图谱增强AI总结">放大</button>
          </div>
        </div>

        <div class="deep-hint">
          图谱生成后进行高质量AI总结 · 结合实体关系与中心性分析
        </div>

        <div class="deep-summary-box">
          {{ deepSummaryText }}
        </div>
      </section>

      <section class="panel analysis-panel">
        <div class="panel-title"><span>5</span> 图谱分析结果</div>

        <div class="circle-stats">
          <div><b>{{ entityCount }}</b><span>实体数量</span></div>
          <div><b>{{ relationCount }}</b><span>关系数量</span></div>
          <div><b>{{ graphDensity }}</b><span>图密度</span></div>
        </div>

        <div class="rank-block">
          <h4>重要节点 Top 5 · 综合中心性得分</h4>

          <div class="node-score-list">
            <div
              v-for="node in topNodes.slice(0, 5)"
              :key="node.name"
              class="node-score-row"
            >
              <div class="node-score-head">
                <span>{{ node.name }}</span>
                <b>{{ Number(node.score || 0).toFixed(4) }}</b>
              </div>

              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: `${Math.min(Number(node.score || 0) * 100, 100)}%` }"
                ></div>
              </div>
            </div>

            <p v-if="!topNodes.length" class="muted">图谱生成后显示核心节点及综合中心性得分。</p>
          </div>
        </div>

        <div class="radar-block">
          <div class="radar-title">
            <h4>中心性分析图</h4>
            <span>Rank-1 至 Rank-5 对应上方 Top 节点</span>
          </div>

          <svg class="radar-chart" viewBox="0 0 180 155">
            <polygon points="90,20 150,60 128,130 52,130 30,60" class="radar-grid" />
            <polygon points="90,43 126,67 113,110 67,110 54,67" class="radar-grid inner" />

            <line x1="90" y1="82" x2="90" y2="20" />
            <line x1="90" y1="82" x2="150" y2="60" />
            <line x1="90" y1="82" x2="128" y2="130" />
            <line x1="90" y1="82" x2="52" y2="130" />
            <line x1="90" y1="82" x2="30" y2="60" />

            <text x="90" y="13" text-anchor="middle">
              {{ topNodes[0]?.name || "Rank-1" }}
            </text>
            <text x="156" y="60" text-anchor="start">
              {{ topNodes[1]?.name || "Rank-2" }}
            </text>
            <text x="132" y="145" text-anchor="middle">
              {{ topNodes[2]?.name || "Rank-3" }}
            </text>
            <text x="48" y="145" text-anchor="middle">
              {{ topNodes[3]?.name || "Rank-4" }}
            </text>
            <text x="24" y="60" text-anchor="end">
              {{ topNodes[4]?.name || "Rank-5" }}
            </text>

            <polygon :points="centralityRadar.points" class="radar-value" />

            <circle
              v-for="p in centralityRadar.points.split(' ')"
              :key="p"
              :cx="p.split(',')[0]"
              :cy="p.split(',')[1]"
              r="3"
              class="radar-dot"
            />
          </svg>

          <p class="radar-note">
            图中每个顶点表示一个核心节点，面积越大表示节点综合中心性越高。
          </p>
        </div>
      </section>

      <section class="panel graph-panel">
        <div class="panel-title graph-head">
          <div class="graph-title-left">
            <span>6</span>
            知识图谱可视化
          </div>

          <div class="graph-tools">
            <button @click="generateGraph" :disabled="!graphReady" title="放大查看">
              ⤢
            </button>
          </div>
        </div>

        <div v-if="graphReady && graphData" class="graph-box">
          <Graph :graphData="graphData" mode="compact" />
        </div>

        <div v-else class="empty-graph">
          {{
            graphStatus === "running"
              ? "知识图谱正在后台生成中"
              : "知识图谱生成后将在此处展示"
          }}
        </div>
      </section>

      <section class="panel status-panel">
        <div class="panel-title"><span>7</span> 处理状态</div>
        <div class="timeline-list">
          <div
            v-for="item in processList"
            :key="item.name"
            class="timeline-item"
            :class="{ done: item.done }"
          >
            <span>{{ item.name }}</span>
            <b>{{ item.time }}</b>
          </div>
        </div>
      </section>

      <section class="panel system-panel">
        <div class="panel-title"><span>8</span> 系统信息</div>
        <div class="sys-list">
          <div v-for="row in systemInfo" :key="row.label">
            <span>{{ row.label }}</span>
            <b>{{ row.value }}</b>
          </div>
        </div>
      </section>

      <section class="panel deep-panel">
        <div class="panel-title"><span>9</span> 深度洞察</div>
        <div class="insight-grid">
          <article v-for="card in insightCards" :key="card.title" class="insight-card">
            <h4>{{ card.title }}</h4>
            <p>{{ card.content }}</p>
          </article>
        </div>
      </section>
    </main>

    <div v-if="showDeepModal" class="ocr-modal-mask" @click.self="showDeepModal = false">
      <div class="ocr-modal">
        <div class="ocr-modal-head">
          <h3>图谱增强AI总结</h3>
          <div>
            <button @click="copyDeepSummary">复制</button>
            <button @click="showDeepModal = false">关闭</button>
          </div>
        </div>

        <pre>{{ deepSummaryText || "暂无图谱增强AI总结" }}</pre>
      </div>
    </div>

    <div v-if="showOcrModal" class="ocr-modal-mask" @click.self="showOcrModal = false">
      <div class="ocr-modal">
        <div class="ocr-modal-head">
          <h3>OCR解析结果</h3>
          <div>
            <button @click="copyOcrText">复制</button>
            <button @click="showOcrModal = false">关闭</button>
          </div>
        </div>

        <pre>{{ ocrText || "暂无OCR结果" }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dash {
  height: 100vh;
  background: var(--bg-main);
  color: var(--text-main);
  padding: 8px 10px 12px;
  box-sizing: border-box;
  overflow: visible;
}

.rank-block {
  margin-top: 4px;
}

.node-score-list {
  display: grid;
  gap: 6px;
}

.node-score-row {
  display: grid;
  gap: 3px;
}

.node-score-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 11.5px;
  color: #dbeafe;
}

.node-score-head span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-score-head b {
  color: #eaf2ff;
  font-weight: 700;
}

.bar-track {
  height: 7px;
  border-radius: 99px;
  background: rgba(65, 142, 255, 0.16);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #2d8cff, #45e6a9);
}

.radar-block {
  margin-top: 10px;
  border-top: 1px solid rgba(65, 142, 255, 0.16);
  padding-top: 8px;
}

.radar-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.radar-title h4 {
  margin: 0 0 4px;
  font-size: 13px;
}

.radar-title span {
  color: #8fa7c8;
  font-size: 11px;
}

.radar-chart {
  width: 100%;
  height: 150px;
  margin-top: 2px;
}

.radar-chart line {
  stroke: rgba(96, 165, 250, 0.26);
  stroke-width: 1;
}

.radar-chart text {
  fill: #8fa7c8;
  font-size: 8.5px;
}

.radar-grid {
  fill: rgba(45, 140, 255, 0.05);
  stroke: rgba(96, 165, 250, 0.34);
  stroke-width: 1;
}

.radar-grid.inner {
  fill: rgba(45, 140, 255, 0.04);
  stroke: rgba(96, 165, 250, 0.22);
}

.radar-value {
  fill: rgba(45, 230, 169, 0.26);
  stroke: #45e6a9;
  stroke-width: 2;
  filter: drop-shadow(0 0 6px rgba(69, 230, 169, 0.35));
}

.radar-dot {
  fill: #45e6a9;
  stroke: #dbeafe;
  stroke-width: 1;
}

.radar-note {
  margin: 2px 0 0;
  color: #8fa7c8;
  font-size: 10.5px;
  line-height: 1.4;
}

.muted {
  color: #8fa7c8;
  font-size: 12px;
}

.centrality-bars {
  margin-top: 6px;
  display: grid;
  gap: 5px;
}

.bar-row {
  display: grid;
  grid-template-columns: 82px 1fr;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #a8bbd5;
}

.bar-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-track {
  height: 7px;
  border-radius: 99px;
  background: rgba(65, 142, 255, 0.16);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #2d8cff, #45e6a9);
}

.dash-header {
  height: 50px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 10px;
  background: var(--bg-header);
  color: var(--text-main);
  border: 1px solid var(--border);
  border-radius: 13px;
  padding: 0 16px;
  box-shadow: 0 0 22px rgba(0, 94, 255, 0.14);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  justify-self: start;
}

.sys-logo {
  width: 48px;
  height: 48px;
  border-radius: 0;
  display: grid;
  place-items: center;
  background: transparent;
  box-shadow: none;
}

.sys-logo-svg {
  width: 46px;
  height: 46px;
  fill: none;
  stroke: #5ee7ff;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter:
    drop-shadow(0 0 5px rgba(56, 189, 248, 0.95))
    drop-shadow(0 0 12px rgba(37, 99, 235, 0.75));
}

.brand h1 {
  margin: 0;
  font-size: 18px;
  line-height: 1.2;
}

.brand p {
  margin: 2px 0 0;
  color: #8fa7c8;
  font-size: 11px;
}

.panel-title-between {
  justify-content: space-between;
}

.panel-title-between > div:first-child {
  display: flex;
  align-items: center;
  gap: 7px;
}

.ocr-actions {
  display: flex;
  gap: 6px;
}

.ocr-actions button {
  border: 1px solid rgba(88, 166, 255, 0.32);
  border-radius: 7px;
  background: rgba(7, 24, 46, 0.85);
  color: #cde3ff;
  font-size: 11px;
  padding: 4px 7px;
  cursor: pointer;
}

.ocr-actions button:hover {
  background: rgba(13, 124, 255, 0.35);
}

.ocr-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 8, 20, 0.72);
  z-index: 999;
  display: grid;
  place-items: center;
}

.ocr-modal {
  width: min(900px, 88vw);
  height: min(680px, 82vh);
  border-radius: 16px;
  background: rgba(8, 23, 43, 0.97);
  border: 1px solid rgba(88, 166, 255, 0.35);
  box-shadow: 0 0 40px rgba(0, 120, 255, 0.28);
  padding: 16px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.ocr-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ocr-modal-head h3 {
  margin: 0;
}

.ocr-modal-head div {
  display: flex;
  gap: 8px;
}

.ocr-modal-head button {
  border: 1px solid rgba(88, 166, 255, 0.32);
  border-radius: 8px;
  background: rgba(7, 24, 46, 0.9);
  color: #dbeafe;
  padding: 7px 12px;
  cursor: pointer;
}

.ocr-modal pre {
  flex: 1;
  margin: 0;
  white-space: pre-wrap;
  overflow: auto;
  padding: 14px;
  border-radius: 12px;
  background: rgba(4, 14, 27, 0.72);
  border: 1px solid rgba(65, 142, 255, 0.2);
  color: #dbeafe;
  line-height: 1.65;
  font-family: inherit;
  font-size: 13px;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.65) rgba(6, 24, 46, 0.55);
}

.ocr-modal pre::-webkit-scrollbar {
  width: 6px;
}

.ocr-modal pre::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.7);
  border-radius: 99px;
}

.ocr-modal pre::-webkit-scrollbar-track {
  background: rgba(6, 24, 46, 0.45);
  border-radius: 99px;
}

.nav {
  display: flex;
  gap: 7px;
  justify-self: center;
}

.nav button {
  border: 1px solid transparent;
  background: transparent;
  color: #b9c8df;
  padding: 7px 13px;
  border-radius: 9px;
  cursor: pointer;
  font-size: 13px;
}

.nav .nav-active,
.nav button:hover {
  background: linear-gradient(135deg, #0b63ce, #0a3f86);
  color: white;
  border-color: rgba(88, 166, 255, 0.4);
}

.tools {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-self: end;
}

.icon-btn {
  width: 34px;
  height: 32px;
  border-radius: 9px;
  border: 1px solid rgba(88, 166, 255, 0.32);
  background: rgba(7, 24, 46, 0.92);
  color: #cde3ff;
  cursor: pointer;
  font-size: 16px;
}

.user-pill {
  padding: 6px 10px;
  border-radius: 11px;
  border: 1px solid rgba(88, 166, 255, 0.32);
  background: linear-gradient(135deg, rgba(22, 63, 118, 0.95), rgba(8, 30, 62, 0.95));
  color: #e5efff;
  font-size: 12px;
  cursor: default;
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-avatar {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(88, 166, 255, 0.18);
  border: 1px solid rgba(147, 197, 253, 0.35);
}

.user-avatar svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.pipeline {
  width: 100%;
  margin: 6px 0;
  padding: 7px 10px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns:
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr) 15px
    minmax(132px, 1fr);
  align-items: center;
  gap: 7px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 13px;
}

.pipe-card {
  height: 46px;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 8px;
  border-radius: 11px;
  background: linear-gradient(135deg, rgba(13, 42, 76, 0.92), rgba(5, 22, 43, 0.92));
}

.pipe-card .icon {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #dbeafe;
  background:
    radial-gradient(circle at 30% 20%, rgba(255,255,255,0.18), transparent 35%),
    rgba(30, 118, 255, 0.18);
}

.pipe-card .icon svg {
  width: 21px;
  height: 21px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.step-cyan .icon { color: #67e8f9; }
.step-purple .icon { color: #c084fc; }
.step-violet .icon { color: #a78bfa; }
.step-gold .icon { color: #fde68a; }
.step-orange .icon { color: #fdba74; }

.pipe-card .text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.pipe-card b {
  font-size: 12.5px;
  color: #f2f7ff;
  white-space: nowrap;
}

.pipe-card span {
  font-size: 10px;
  color: #8fa7c8;
  white-space: nowrap;
}

.arrow {
  width: 15px;
  text-align: center;
  color: #68a9ff;
  font-size: 15px;
}

.step-blue {
  border: 1.5px solid rgba(59, 130, 246, 0.9);
  box-shadow: 0 0 16px rgba(59, 130, 246, 0.38), inset 0 0 16px rgba(59, 130, 246, 0.12);
}

.step-cyan {
  border: 1.5px solid rgba(34, 211, 238, 0.9);
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.38), inset 0 0 16px rgba(34, 211, 238, 0.12);
}

.step-purple {
  border: 1.5px solid rgba(168, 85, 247, 0.9);
  box-shadow: 0 0 16px rgba(168, 85, 247, 0.38), inset 0 0 16px rgba(168, 85, 247, 0.12);
}

.step-violet {
  border: 1.5px solid rgba(139, 92, 246, 0.9);
  box-shadow: 0 0 16px rgba(139, 92, 246, 0.38), inset 0 0 16px rgba(139, 92, 246, 0.12);
}

.step-gold {
  border: 1.5px solid rgba(255, 210, 90, 0.9);
  box-shadow: 0 0 16px rgba(255, 199, 86, 0.38), inset 0 0 16px rgba(255, 199, 86, 0.12);
}

.step-gold b {
  color: #ffe08a;
}

.step-orange {
  border: 1.5px solid rgba(251, 146, 60, 0.9);
  box-shadow: 0 0 16px rgba(251, 146, 60, 0.38), inset 0 0 16px rgba(251, 146, 60, 0.12);
}

.grid {
  display: grid;
  grid-template-columns: 315px 350px 350px 1fr;
  grid-template-rows: 210px 245px minmax(205px, 1fr);
  gap: 8px;
  height: calc(100vh - 170px);
  min-height: 0;
  padding-bottom: 20px;
  box-sizing: border-box;
}

.panel {
  border: 1px solid rgba(58, 137, 255, 0.25);
  background: rgba(8, 23, 43, 0.82);
  border-radius: 12px;
  padding: 8px;
  box-shadow: inset 0 0 22px rgba(20, 95, 190, 0.08);
  overflow: hidden;
}

.input-panel {
  grid-column: 1;
  grid-row: 1 / span 2;
  height: 420px;
  overflow: hidden;
}

.ocr-panel {
  grid-column: 2;
  grid-row: 1;
}

.ai-panel {
  grid-column: 3;
  grid-row: 1;
}

.extract-panel {
  grid-column: 2;
  grid-row: 2;
}

.analysis-panel {
  grid-column: 3;
  grid-row: 2/span 2;
}

.graph-panel {
  grid-column: 4;
  grid-row: 1 / span 2;
  height: 475px;
}

.status-panel {
  grid-column: 1;
  grid-row: 3;
  margin-top: -38px;
  height: 243px; 
}

.system-panel {
  grid-column: 2;
  grid-row: 3;
  height: 205px;
}

.deep-panel {
  grid-column:4;
  grid-row: 3;
  height: 188px;
  align-self: end;
}

.status-panel,
.system-panel,
.deep-panel {
  min-height: 0;
  overflow: hidden;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-weight: 700;
  margin-bottom: 7px;
  font-size: 15px;
}

.panel-title span {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: linear-gradient(135deg, #2d8cff, #7457ff);
}

.status-card {
  margin-top: 7px;
  padding: 8px;
  border-radius: 9px;
  background: var(--bg-box);
  color: var(--text-sub);
  font-size: 12px;
}

.status-card p {
  margin: 0;
}

.mini-stats,
.tabs,
.circle-stats {
  display: flex;
  gap: 8px;
  color: #a8bbd5;
  font-size: 12px;
  margin-bottom: 7px;
}

.content-box {
  height: calc(100% - 48px);
  min-height: 0;
  overflow: auto;
  padding: 10px 12px 22px;
  box-sizing: border-box;
  white-space: pre-wrap;
  line-height: 1.65;
  background: rgba(4, 14, 27, 0.6);
  border: 1px solid rgba(65, 142, 255, 0.18);
  border-radius: 9px;
  color: #dbeafe;
  font-size: 12.5px;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.65) rgba(6, 24, 46, 0.55);
}

.content-box::-webkit-scrollbar,
.ai-panel p::-webkit-scrollbar,
.deep-summary-box::-webkit-scrollbar,
.insight-card p::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.content-box::-webkit-scrollbar-thumb,
.ai-panel p::-webkit-scrollbar-thumb,
.deep-summary-box::-webkit-scrollbar-thumb,
.insight-card p::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.7);
  border-radius: 99px;
}

.content-box::-webkit-scrollbar-track,
.ai-panel p::-webkit-scrollbar-track,
.deep-summary-box::-webkit-scrollbar-track,
.insight-card p::-webkit-scrollbar-track {
  background: rgba(6, 24, 46, 0.45);
  border-radius: 99px;
}

.ai-panel p {
  line-height: 1.55;
  color: #d7e4f7;
  font-size: 12.5px;
  max-height: 68px;
  overflow-y: auto;
}

.ai-panel h4,
.analysis-panel h4 {
  margin: 5px 0 4px;
  font-size: 13px;
}

.ai-foot {
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
  color: #8fa7c8;
  font-size: 11px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.tags span {
  padding: 4px 7px;
  border-radius: 7px;
  background: rgba(124, 58, 237, 0.25);
  color: #d8c4ff;
  font-size: 11px;
}

.deep-hint {
  font-size: 11px;
  color: #45e6a9;
  margin-bottom: 6px;
}

.deep-summary-box {
  height: calc(100% - 54px);
  overflow-y: auto;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(4, 14, 27, 0.62);
  border: 1px solid rgba(65, 142, 255, 0.2);
  line-height: 1.65;
  color: #dbeafe;
  font-size: 12.5px;
  box-sizing: border-box;
}

.circle-stats > div {
  flex: 1;
  height: 48px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  background: rgba(6, 27, 52, 0.78);
  border: 1px solid rgba(48, 130, 255, 0.22);
}

.circle-stats b {
  font-size: 18px;
  color: #45e6a9;
}

.circle-stats span {
  font-size: 11px;
  color: #a8bbd5;
}

.analysis-split {
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 7px;
}

.analysis-split h4 {
  margin: 4px 0 5px;
  font-size: 13px;
}

.rank {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.rank div {
  display: flex;
  justify-content: space-between;
  color: #d7e4f7;
}

.centrality-bars {
  margin-top: 4px;
  display: grid;
  gap: 5px;
}

.bar-row {
  display: grid;
  grid-template-columns: 74px 1fr;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #a8bbd5;
}

.bar-track {
  height: 7px;
  border-radius: 99px;
  background: rgba(65, 142, 255, 0.16);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #2d8cff, #45e6a9);
}

.muted {
  color: #8fa7c8;
  font-size: 12px;
}

.graph-box {
  height: calc(100% - 36px);
}

.empty-graph {
  height: calc(100% - 36px);
  display: grid;
  place-items: center;
  color: #8fa7c8;
  border-radius: 11px;
  border: 1px dashed rgba(78, 154, 255, 0.28);
}

.graph-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.graph-title-left {
  display: flex;
  align-items: center;
  gap: 7px;
}

.graph-tools {
  display: flex;
  gap: 6px;
}

.graph-tools button {
  width: 28px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid rgba(88, 166, 255, 0.35);
  background: rgba(7, 24, 46, 0.9);
  color: #cde3ff;
  cursor: pointer;
}

.timeline-list {
  display: grid;
  gap: 6px;
  overflow: visible;
  height: auto;
}

.timeline-item {
  display: flex;
  justify-content: space-between;
  padding: 5px 8px;
  background: rgba(4, 14, 27, 0.62);
  border: 1px solid rgba(65, 142, 255, 0.2);
  border-radius: 8px;
  color: #8fa7c8;
  font-size: 11.5px;
}

.timeline-item.done {
  color: #2fe49d;
  border-color: rgba(47, 228, 157, 0.3);
}

.sys-list {
  height: auto;
  display: grid;
  gap: 5px;
}

.sys-list div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-radius: 9px;
  padding: 5px 7px;
  border: 1px solid rgba(65, 142, 255, 0.2);
  background: rgba(4, 14, 27, 0.62);
  font-size: 11.5px;
}

.sys-list span {
  color: #8fa7c8;
}

.sys-list b {
  color: #dbeafe;
  text-align: right;
}

.insight-grid {
  height: auto;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.insight-card {
  min-height: 78px;
  max-height: 90px;
  box-sizing: border-box;
  border-radius: 10px;
  padding: 8px;
  border: 1px solid rgba(65, 142, 255, 0.2);
  background: rgba(4, 14, 27, 0.62);
  overflow: hidden;
}

.insight-card h4 {
  margin: 0 0 5px;
  font-size: 12px;
  color: #dbeafe;
}

.insight-card p {
  margin: 0;
  color: #a8bbd5;
  font-size: 11.2px;
  line-height: 1.45;
  max-height: 100%;
  overflow-y: auto;
}

@media (max-width: 1300px) {
  .dash {
    overflow-y: auto;
  }

  .dash-header {
    grid-template-columns: 1fr;
    height: auto;
    padding: 8px;
  }

  .pipeline {
    grid-template-columns: repeat(7, minmax(120px, 1fr));
    overflow-x: auto;
  }

  .arrow {
    display: none;
  }

  .grid {
    grid-template-columns: 270px 1fr 1fr;
    grid-template-rows: auto;
    height: auto;
  }

  .ocr-panel {
    grid-column: 2;
    grid-row: 1;
  }

  .ai-panel {
    grid-column: 3;
    grid-row: 1;
  }

  .extract-panel {
    grid-column: 2;
    grid-row: 2;
  }

  .analysis-panel {
    grid-column: 3;
    grid-row: 2;
  }

  .graph-panel,
  .status-panel,
  .system-panel,
  .deep-panel {
    grid-column: 1 / span 3;
    grid-row: auto;
  }

  .insight-grid {
    grid-template-columns: 1fr;
  }
}

button {
  position: relative;
  z-index: 5;
  pointer-events: auto;
}

.dash-header,
.pipeline,
.grid,
.panel {
  position: relative;
}

.dash-header {
  z-index: 20;
}

.pipeline {
  z-index: 10;
}

.grid {
  z-index: 5;
}

</style>