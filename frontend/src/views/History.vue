<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"

const router = useRouter()
const history = ref([])

const loadHistory = () => {
  history.value = JSON.parse(localStorage.getItem("history") || "[]")
}

const openRecord = (item) => {
  sessionStorage.setItem("currentAnalysisResult", JSON.stringify(item))
  if (item.graph) {
    sessionStorage.setItem("currentGraphData", JSON.stringify(item.graph))
  }
  router.push("/main")
}

const openGraph = (item) => {
  sessionStorage.setItem("currentAnalysisResult", JSON.stringify(item))
  if (item.graph) {
    sessionStorage.setItem("currentGraphData", JSON.stringify(item.graph))
    router.push("/graph")
  } else {
    alert("该记录暂未生成知识图谱")
  }
}

const clearHistory = () => {
  if (!confirm("确定清空所有历史记录吗？")) return
  localStorage.removeItem("history")
  history.value = []
}

onMounted(loadHistory)
</script>

<template>
  <div class="history-page">
    <header class="history-header">
      <div>
        <h1>历史记录</h1>
        <p>查看过往 OCR 识别、AI总结、知识图谱与深度分析结果</p>
      </div>

      <div class="actions">
        <button @click="router.push('/main')">返回主页</button>
        <button class="danger" @click="clearHistory">清空记录</button>
      </div>
    </header>

    <main class="history-list">
      <div v-if="!history.length" class="empty">
        暂无历史记录
      </div>

      <article
        v-for="item in history"
        :key="item.id"
        class="history-card"
      >
        <div class="card-left">
          <div class="card-top">
            <h3>{{ item.fileName || "历史任务" }}</h3>
            <span>{{ item.status || "已保存" }}</span>
          </div>

          <p class="time">{{ item.time }}</p>

          <div class="summary">
            {{ item.summary || item.ocrText || "暂无识别/总结内容" }}
          </div>

          <div class="deep">
            <b>深度总结：</b>
            <span>{{ item.graphSummary || item.deepSummary || "图谱生成后显示深度总结" }}</span>
          </div>
        </div>

        <div class="card-right">
          <div class="stats">
            <div>
              <b>{{ item.ocrText?.length || item.ocr?.structured_text?.length || item.ocr?.raw_text?.length || 0 }}</b>
              <span>识别字数</span>
            </div>
            <div>
              <b>{{ item.graph?.nodes?.length || 0 }}</b>
              <span>节点</span>
            </div>
            <div>
              <b>{{ item.graph?.edges?.length || item.graph?.links?.length || 0 }}</b>
              <span>关系</span>
            </div>
          </div>

          <div class="card-actions">
            <button @click="openRecord(item)">查看识别结果</button>
            <button
              class="primary"
              @click="openGraph(item)"
              :disabled="!item.graph || !item.graph.nodes || !item.graph.nodes.length"
            >
              查看知识图谱
            </button>
          </div>
        </div>
      </article>
    </main>
  </div>
</template>

<style scoped>
.history-page {
  height: 100vh;
  overflow: hidden;
  background: var(--bg-main);
  color: var(--text-main);
  padding: 16px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.history-header {
  height: 76px;
  flex: 0 0 76px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-header);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  margin-bottom: 14px;
  box-sizing: border-box;
  box-shadow: 0 0 22px rgba(0, 94, 255, 0.12);
}

.history-header h1 {
  margin: 0;
  font-size: 22px;
  color: var(--text-main);
}

.history-header p {
  margin: 5px 0 0;
  color: var(--text-sub);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 10px;
}

.actions button,
.card-actions button {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 15px;
  cursor: pointer;
  color: var(--text-main);
  background: var(--button-bg);
  white-space: nowrap;
}

.actions button:hover,
.card-actions button:hover {
  background: linear-gradient(135deg, #0d7cff, #005ec9);
  color: white;
}

.actions .danger {
  background: rgba(220, 38, 38, 0.78);
  color: white;
  border-color: rgba(248, 113, 113, 0.35);
}

.history-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 0 8px 28px 0;
  box-sizing: border-box;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.65) rgba(6, 24, 46, 0.55);
}

.history-list::-webkit-scrollbar,
.summary::-webkit-scrollbar,
.deep::-webkit-scrollbar {
  width: 6px;
}

.history-list::-webkit-scrollbar-thumb,
.summary::-webkit-scrollbar-thumb,
.deep::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.7);
  border-radius: 99px;
}

.history-list::-webkit-scrollbar-track,
.summary::-webkit-scrollbar-track,
.deep::-webkit-scrollbar-track {
  background: rgba(6, 24, 46, 0.45);
  border-radius: 99px;
}

.history-card {
  width: 100%;
  min-height: 210px;
  flex: 0 0 auto;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 14px;
  padding: 16px;
  box-shadow: inset 0 0 24px rgba(20, 95, 190, 0.08);
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 1fr 310px;
  gap: 18px;
}

.card-left,
.card-right {
  min-width: 0;
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.card-top h3 {
  margin: 0;
  font-size: 17px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
}

.card-top span {
  color: #2fe49d;
  font-size: 13px;
  white-space: nowrap;
}

.time {
  color: var(--text-sub);
  font-size: 13px;
  margin: 8px 0;
}

.summary {
  height: 82px;
  overflow-y: auto;
  line-height: 1.55;
  color: var(--text-main);
  background: var(--bg-box);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px;
  box-sizing: border-box;
  font-size: 13px;
}

.deep {
  margin-top: 10px;
  color: var(--text-sub);
  font-size: 13px;
  line-height: 1.55;
  height: 48px;
  overflow-y: auto;
}

.deep b {
  color: var(--text-main);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.stats div {
  background: var(--bg-box);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 13px 6px;
  text-align: center;
  min-width: 0;
}

.stats b {
  display: block;
  color: #45e6a9;
  font-size: 20px;
}

.stats span {
  color: var(--text-sub);
  font-size: 12px;
}

.card-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.card-actions button {
  flex: 1;
  min-width: 0;
}

.card-actions .primary {
  background: linear-gradient(135deg, #0d7cff, #005ec9);
  color: white;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty {
  min-height: 360px;
  display: grid;
  place-items: center;
  color: var(--text-sub);
  border: 1px dashed var(--border);
  border-radius: 14px;
  background: var(--bg-card);
}

@media (max-width: 980px) {
  .history-card {
    grid-template-columns: 1fr;
  }

  .card-right {
    display: grid;
    gap: 12px;
  }
}

@media (max-width: 760px) {
  .history-header {
    height: auto;
    flex: 0 0 auto;
    padding: 12px;
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