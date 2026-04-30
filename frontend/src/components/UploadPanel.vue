<template>
  <div class="upload-card">
    <div class="tabs">
      <button class="active">图片上传</button>
      <button>PDF上传</button>
      <button>文本输入</button>
    </div>

    <div
      class="drop-zone"
      :class="{ active: isDragging }"
      @drop.prevent="onDrop"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @click="fileInput?.click()"
    >
      <div class="cloud">☁️</div>
      <p v-if="!isDragging">拖拽文件到此处，或点击上传</p>
      <p v-else>释放以上传</p>
      <span>支持 JPG / PNG / BMP / PDF</span>
    </div>

    <input
      ref="fileInput"
      class="hidden-input"
      type="file"
      accept="image/*,.pdf"
      @change="handleFileChange"
    />

    <div class="file-box">
      <span>{{ fileName ? formatFileName(fileName) : "未选择文件" }}</span>
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

      <button class="clear" @click.stop="resetUI">清空</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"

defineProps({
  loading: Boolean,
  fileName: String
})

const emit = defineEmits(["file-change", "clear"])

const fileInput = ref(null)
const isDragging = ref(false)
const msg = ref("")

const formatFileName = (name) => {
  if (!name) return ""
  return name.length > 34 ? name.slice(0, 16) + "..." + name.slice(-10) : name
}

const showMsg = (t) => {
  msg.value = t
  setTimeout(() => {
    msg.value = ""
  }, 2000)
}

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file) {
    emit("file-change", file)
    showMsg("文件选择成功")
  }
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
  if (file) {
    emit("file-change", file)
    showMsg("文件已拖拽上传")
  }
}

const resetUI = () => {
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
  gap: 12px;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.tabs button {
  border: none;
  border-radius: 8px;
  padding: 9px 4px;
  color: #93a9c8;
  background: rgba(6, 24, 46, 0.88);
  cursor: pointer;
}

.tabs .active {
  color: white;
  background: linear-gradient(135deg, #0d7cff, #005ec9);
}

.drop-zone {
  height: 145px;
  border: 1.5px dashed rgba(69, 152, 255, 0.55);
  border-radius: 13px;
  display: grid;
  place-items: center;
  text-align: center;
  cursor: pointer;
  background: rgba(4, 14, 27, 0.68);
  transition: 0.2s;
}

.drop-zone.active,
.drop-zone:hover {
  border-color: #4aa3ff;
  background: rgba(14, 76, 145, 0.28);
}

.cloud {
  font-size: 32px;
}

.drop-zone p {
  margin: 0;
  color: #dbeafe;
}

.drop-zone span {
  color: #8198b8;
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.file-box {
  height: 42px;
  border-radius: 10px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(4, 14, 27, 0.7);
  border: 1px solid rgba(65, 142, 255, 0.18);
  color: #b9c8df;
  font-size: 13px;
}

.msg {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
  display: flex;
  justify-content: space-between;
}

.msg button {
  border: none;
  background: transparent;
  color: #6ee7b7;
  cursor: pointer;
}

.actions {
  display: grid;
  grid-template-columns: 1fr 76px;
  gap: 8px;
}

.actions button {
  border: none;
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  font-weight: 700;
}

.start {
  color: white;
  background: linear-gradient(135deg, #0d7cff, #0066d6);
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