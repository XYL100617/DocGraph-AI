<script setup>
import { computed, ref, onMounted } from "vue"
import { useRouter } from "vue-router"

const router = useRouter()
const data = ref({})

const safeParse = (key) => {
  try {
    return JSON.parse(sessionStorage.getItem(key) || "{}")
  } catch {
    return {}
  }
}

onMounted(() => {
  const current = safeParse("currentAnalysisResult")
  const report = safeParse("reportData")

  data.value = {
    ...current,
    ...report
  }
})

const graph = computed(() => data.value?.graph || { nodes: [], edges: [], links: [] })

const analysis = computed(() => {
  return data.value?.analysis || {
    core_nodes: [],
    important_paths: []
  }
})

const edgeCount = computed(() => {
  return graph.value?.edges?.length || graph.value?.links?.length || 0
})

const density = computed(() => {
  const n = graph.value?.nodes?.length || 0
  const e = edgeCount.value
  if (n <= 1) return "0.00"
  return (e / (n * (n - 1))).toFixed(2)
})

const graphEnhancedSummary = computed(() => {
  return (
    data.value?.graphSummary ||
    data.value?.deepSummary ||
    data.value?.analysis?.summary ||
    data.value?.analysis?.deep_summary ||
    data.value?.llm?.deep_summary ||
    data.value?.llm?.analysis ||
    "暂无图谱增强AI总结"
  )
})

const hasData = computed(() => {
  return (
    data.value?.summary ||
    data.value?.ocrText ||
    graph.value?.nodes?.length ||
    graphEnhancedSummary.value !== "暂无图谱增强AI总结"
  )
})

const formatPath = (path) => {
  if (Array.isArray(path)) return path.join(" -> ")
  return String(path || "")
}
</script>

<template>
  <div class="report-page">
    <header class="head">
      <div>
        <h1>分析报告</h1>
        <p>汇总 OCR 识别、AI总结、图谱增强分析与知识结构结果</p>
      </div>

      <div class="actions">
        <button @click="router.push('/main')">返回主页</button>
        <button class="primary" @click="router.push('/graph')">打开图谱</button>
      </div>
    </header>

    <main v-if="hasData" class="body">
      <section class="card metrics">
        <h3>关键指标</h3>
        <div class="grid">
          <div><b>{{ graph.nodes?.length || 0 }}</b><span>实体数量</span></div>
          <div><b>{{ edgeCount }}</b><span>关系数量</span></div>
          <div><b>{{ density }}</b><span>图密度</span></div>
          <div>
            <b>{{ data.ocrText?.length || data.ocr?.structured_text?.length || data.ocr?.raw_text?.length || 0 }}</b>
            <span>识别字数</span>
          </div>
        </div>
      </section>

      <section class="card">
        <h3>AI总结</h3>
        <p>{{ data.summary || data.llm?.summary || "暂无AI总结" }}</p>
      </section>

      <section class="card wide">
        <h3>图谱增强AI总结</h3>
        <p class="summary-text">{{ graphEnhancedSummary }}</p>
      </section>

      <section class="card">
        <h3>核心节点</h3>
        <ul>
          <li v-for="item in analysis.core_nodes || []" :key="item.name">
            <span>{{ item.name }}</span>
            <b>{{ item.score }}</b>
          </li>
          <li v-if="!(analysis.core_nodes || []).length">暂无核心节点</li>
        </ul>
      </section>

      <section class="card">
        <h3>关键路径</h3>
        <ul>
          <li v-for="(path, idx) in analysis.important_paths || []" :key="idx">
            {{ formatPath(path) }}
          </li>
          <li v-if="!(analysis.important_paths || []).length">暂无关键路径</li>
        </ul>
      </section>
    </main>

    <div v-else class="empty">
      当前没有可用分析结果，请先在主页完成一次分析。
    </div>
  </div>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  background: var(--bg-main);
  color: var(--text-main);
  padding: 18px;
  box-sizing: border-box;
  overflow-y: auto;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--border);
  background: var(--bg-header);
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 0 22px rgba(0, 94, 255, 0.12);
}

.head h1 {
  margin: 0;
  font-size: 24px;
  color: var(--text-main);
}

.head p {
  margin: 5px 0 0;
  color: var(--text-sub);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 10px;
}

button {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  color: var(--text-main);
  background: var(--button-bg);
}

button:hover,
button.primary {
  background: linear-gradient(135deg, #0d7cff, #005ec9);
  color: white;
}

.body {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
  gap: 12px;
}

.card {
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 12px;
  padding: 14px;
  box-shadow: inset 0 0 22px rgba(20, 95, 190, 0.08);
}

.card.wide {
  grid-column: 1 / -1;
}

.card h3 {
  margin-top: 0;
  color: var(--text-main);
}

.card p {
  margin: 0;
  line-height: 1.7;
  color: var(--text-sub);
}

.summary-text {
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.65) rgba(6, 24, 46, 0.55);
}

.summary-text::-webkit-scrollbar {
  width: 6px;
}

.summary-text::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.7);
  border-radius: 99px;
}

.summary-text::-webkit-scrollbar-track {
  background: rgba(6, 24, 46, 0.45);
  border-radius: 99px;
}

.metrics .grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.metrics .grid div {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  background: var(--bg-box);
  text-align: center;
}

.metrics b {
  display: block;
  color: #45e6a9;
  font-size: 20px;
}

.metrics span {
  color: var(--text-sub);
  font-size: 12px;
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

li {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-box);
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-main);
}

li span {
  color: var(--text-main);
}

li b {
  color: #45e6a9;
}

.empty {
  margin-top: 20px;
  height: 320px;
  border-radius: 14px;
  border: 1px dashed var(--border);
  background: var(--bg-card);
  display: grid;
  place-items: center;
  color: var(--text-sub);
}

@media (max-width: 1100px) {
  .body {
    grid-template-columns: 1fr;
  }

  .metrics .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 720px) {
  .head {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .actions {
    width: 100%;
  }

  .actions button {
    flex: 1;
  }
}
</style>