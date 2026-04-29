<template>
  <div class="result-panel">
    <h3>OCR结果</h3>

    <div v-if="displayModules && displayModules.length">
      <div
        v-for="(m, index) in displayModules"
        :key="index"
        class="module-box"
      >
        <div class="module-title">
          
        </div>
        <pre class="ocr-text">{{ m.text || "" }}</pre>
      </div>
    </div>

    <pre v-else class="box ocr-text">{{ ocr || "暂无数据" }}</pre>

    <h3>AI总结</h3>
    <div class="box summary-text">
      {{ summary || "暂无数据" }}
    </div>
    <h3>深度分析总结</h3>
    <div class="box summary-text">
    {{ graphSummary || "生成知识图谱后显示" }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  ocr: {
    type: String,
    default: ""
  },
  summary: {
    type: String,
    default: ""
  },
  graphSummary: {
  type: String,
  default: ""
  },
  modules: {
    type: Array,
    default: () => []
  }
})

const parseStructuredText = (text) => {
  if (!text || !text.includes("【")) {
    return []
  }

  const result = []
  const regex = /【([^】]+)】\s*([\s\S]*?)(?=\n\s*【[^】]+】|$)/g

  let match
  while ((match = regex.exec(text)) !== null) {
    const moduleName = match[1]?.trim()
    const moduleText = match[2]?.trim()

    if (moduleName && moduleText) {
      result.push({
        module: moduleName,
        text: moduleText
      })
    }
  }

  return result
}

const displayModules = computed(() => {
  // 最关键：优先使用 ocr/structured_text 解析出来的结果
  // 因为后端已经把【顶部第一行】写进 structured_text
  const parsed = parseStructuredText(props.ocr)

  if (parsed.length) {
    return parsed
  }

  // structured_text 没有模块时，才退回 modules
  if (props.modules && props.modules.length) {
    return props.modules
  }

  return []
})
</script>

<style scoped>
.result-panel {
  height: 100%;
  overflow-y: auto;
}

.box {
  border: 1px solid #ddd;
  padding: 10px;
  min-height: 120px;
  border-radius: 6px;
  background: #fff;
}

.ocr-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  line-height: 1.7;
  font-size: 14px;
  margin: 0;
}

.module-box {
  border: 1px solid #ddd;
  margin-bottom: 10px;
  padding: 10px;
  background: #fafafa;
  border-radius: 6px;
}

.module-title {
  font-weight: bold;
  margin-bottom: 6px;
  color: #333;
}

.summary-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
</style>