<template>
  <div class="upload-card">
    <div class="tabs">
      <button :class="{ active: mode === 'image' }" @click="switchMode('image')">
        图片上传
      </button>
      <button :class="{ active: mode === 'pdf' }" @click="switchMode('pdf')">
        PDF上传
      </button>
      <button :class="{ active: mode === 'text' }" @click="switchMode('text')">
        文本输入
      </button>
    </div>

    <div
      v-if="mode !== 'text'"
      class="drop-zone"
      :class="{ active: isDragging }"
      @drop.prevent="onDrop"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @click="fileInput?.click()"
    >
      <div class="upload-icon">
        <svg viewBox="0 0 24 24">
          <path d="M12 16V7" />
          <path d="M8 11l4-4 4 4" />
          <path d="M20 16.5A4.5 4.5 0 0 0 15.5 12H15a6 6 0 1 0-11 3.5" />
          <path d="M4 17h16" />
        </svg>
      </div>

      <p v-if="!isDragging">拖拽文件到此处，或点击上传</p>
      <p v-else>释放以上传</p>
      <span v-if="mode === 'image'">支持 JPG / PNG / BMP / WEBP</span>
      <span v-else>支持 PDF 文档上传</span>
    </div>

    <textarea
      v-else
      class="text-zone"
      :value="textValue"
      placeholder="请输入需要分析的文本内容..."
      @input="$emit('update:textValue', $event.target.value)"
    />

    <input
      ref="fileInput"
      class="hidden-input"
      type="file"
      :accept="acceptType"
      @change="handleFileChange"
    />

    <div class="file-box">
      <span>{{ currentFileName }}</span>
      <b v-if="fileName">✅</b>
    </div>

    <div v-if="msg" class="msg">
      {{ msg }}
      <button @click.stop="msg = ''">×</button>
    </div>

    <div class="actions">
      <button class="start" @click.stop="$emit('upload')" :disabled="loading">
        {{ loading ? "分析中..." : "▶ 开始智能分析" }}
      </button>

      <button
        class="generate"
        @click.stop="$emit('generate-graph')"
        :disabled="!canGenerateGraph || graphLoading"
      >
        {{ graphLoading ? "生成中..." : (graphReady ? "查看图谱" : "生成图谱") }}
      </button>

      <button class="clear" @click.stop="resetUI">清空</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue"

const props = defineProps({
  loading: Boolean,
  graphLoading: Boolean,
  graphReady: Boolean,
  canGenerateGraph: Boolean,
  fileName: {
    type: String,
    default: ""
  },
  textValue: {
    type: String,
    default: ""
  }
})

const emit = defineEmits([
  "file-change",
  "clear",
  "mode-change",
  "generate-graph",
  "update:textValue",
  "upload"
])

const fileInput = ref(null)
const isDragging = ref(false)
const msg = ref("")
const mode = ref("image")
const acceptType = ref("image/*")

const currentFileName = computed(() => {
  if (mode.value === "text") return props.textValue ? "已输入文本内容" : "未输入文本"
  if (!props.fileName) return "未选择文件"
  return formatFileName(props.fileName)
})

const formatFileName = (name) => {
  if (!name) return ""
  return name.length > 30 ? `${name.slice(0, 14)}...${name.slice(-9)}` : name
}

const switchMode = (nextMode) => {
  mode.value = nextMode

  if (nextMode === "image") acceptType.value = "image/*"
  if (nextMode === "pdf") acceptType.value = ".pdf,application/pdf"
  if (nextMode === "text") acceptType.value = ""

  emit("mode-change", nextMode)

  if (fileInput.value) {
    fileInput.value.value = ""
  }
}

const showMsg = (t) => {
  msg.value = t
  setTimeout(() => {
    msg.value = ""
  }, 2000)
}

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (!file) return

  if (mode.value === "image" && file.type.includes("pdf")) {
    showMsg("当前为图片模式，请切换到PDF上传")
    return
  }

  if (mode.value === "pdf" && !file.type.includes("pdf")) {
    showMsg("当前为PDF模式，请上传PDF文件")
    return
  }

  emit("file-change", file)
  showMsg("文件选择成功")
}

const onDragOver = () => {
  isDragging.value = true
}

const onDragLeave = () => {
  isDragging.value = false
}

const onDrop = (e) => {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (!file) return

  if (mode.value === "image" && file.type.includes("pdf")) {
    showMsg("当前为图片模式，请切换到PDF上传")
    return
  }

  if (mode.value === "pdf" && !file.type.includes("pdf")) {
    showMsg("当前为PDF模式，请上传PDF文件")
    return
  }

  emit("file-change", file)
  showMsg("文件已拖拽上传")
}

const resetUI = () => {
  emit("update:textValue", "")
  emit("file-change", null)
  emit("clear")
  msg.value = ""
  isDragging.value = false
  if (fileInput.value) fileInput.value.value = ""
}
</script>

<style scoped>
.upload-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.tabs button {
  border: none;
  border-radius: 8px;
  padding: 8px 4px;
  color: #93a9c8;
  background: rgba(6, 24, 46, 0.88);
  cursor: pointer;
  font-size: 12px;
}

.tabs .active {
  color: white;
  background: linear-gradient(135deg, #0d7cff, #005ec9);
}

.drop-zone,
.text-zone {
  height: 185px;
  border: 1.5px dashed rgba(69, 152, 255, 0.55);
  border-radius: 12px;
  background: rgba(4, 14, 27, 0.68);
  box-sizing: border-box;
}

.drop-zone {
  display: grid;
  place-items: center;
  text-align: center;
  cursor: pointer;
  transition: 0.2s;
  padding: 10px;
}

.drop-zone.active,
.drop-zone:hover {
  border-color: #4aa3ff;
  background: rgba(14, 76, 145, 0.28);
}

.upload-icon {
  width: 46px;
  height: 46px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 35% 25%, rgba(96, 165, 250, 0.28), transparent 42%),
    rgba(30, 118, 255, 0.14);
  border: 1px solid rgba(96, 165, 250, 0.28);
  box-shadow:
    0 0 18px rgba(59, 130, 246, 0.22),
    inset 0 0 12px rgba(96, 165, 250, 0.08);
}

.upload-icon svg {
  width: 25px;
  height: 25px;
  fill: none;
  stroke: #cfe8ff;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.drop-zone p {
  margin: 0;
  color: #dbeafe;
  font-size: 13px;
}

.drop-zone span {
  color: #8198b8;
  font-size: 11px;
}

.text-zone {
  width: 100%;
  resize: none;
  color: #eaf2ff;
  padding: 12px;
  outline: none;
  font-size: 13px;
  line-height: 1.6;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.65) rgba(6, 24, 46, 0.55);
}

.text-zone::-webkit-scrollbar {
  width: 6px;
}

.text-zone::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.7);
  border-radius: 99px;
}

.text-zone::-webkit-scrollbar-track {
  background: rgba(6, 24, 46, 0.45);
  border-radius: 99px;
}

.hidden-input {
  display: none;
}

.file-box {
  height: 34px;
  border-radius: 9px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(4, 14, 27, 0.7);
  border: 1px solid rgba(65, 142, 255, 0.18);
  color: #b9c8df;
  font-size: 12px;
}

.msg {
  padding: 7px 9px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.msg button {
  border: none;
  background: transparent;
  color: #6ee7b7;
  cursor: pointer;
}

.actions {
  display: grid;
  grid-template-columns: 1.08fr 0.9fr 56px;
  gap: 7px;
}

.actions button {
  border: none;
  border-radius: 9px;
  padding: 9px 5px;
  cursor: pointer;
  font-weight: 700;
  font-size: 12px;
}

.start {
  color: white;
  background: linear-gradient(135deg, #0d7cff, #0066d6);
}

.generate {
  color: #e8f0ff;
  background: linear-gradient(135deg, #0b2f6b, #1557b8);
}

.clear {
  color: #cbd5e1;
  background: rgba(15, 31, 52, 0.9);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>