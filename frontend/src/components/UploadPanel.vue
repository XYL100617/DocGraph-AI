<template>
  <div>
    <h3>输入区</h3>

    <div
      class="drop-zone"
      :class="{ active: isDragging }"
      @drop.prevent="onDrop"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
    >
      <p v-if="!isDragging">拖拽图片到这里</p>
      <p v-else>释放以上传</p>
    </div>

    <!-- ⭐修复：文件状态真实 -->
    <p v-if="fileName" class="file-name">
      📄 已选择：{{ formatFileName(fileName) }}
    </p>
    <p v-else>未选择文件</p>

    <input type="file" @change="handleFileChange" />

    <!-- ⭐提示自动消失 -->
    <div v-if="msg" class="msg">
      {{ msg }}
      <button @click="msg = ''">×</button>
    </div>

    <div>
      <button @click="$emit('upload')">
        {{ loading ? "分析中..." : "开始分析" }}
      </button>

      <button @click="resetUI">清空</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue"
const formatFileName = (name) => {
  if (!name) return ""

  // 超过40字符截断
  if (name.length > 40) {
    return name.slice(0, 18) + "..." + name.slice(-10)
  }

  return name
}

const emit = defineEmits(["file-change", "clear"])

const props = defineProps({
  loading: Boolean,
  fileName: String
})

const isDragging = ref(false)
const msg = ref("")

const showMsg = (t) => {
  msg.value = t
  setTimeout(() => msg.value = "", 2000)
}

// ⭐文件变化
const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file) {
    emit("file-change", file)
    showMsg("文件选择成功")
  }
}

// ⭐拖拽
const onDragOver = () => isDragging.value = true
const onDragLeave = () => isDragging.value = false

const onDrop = (e) => {
  isDragging.value = false
  const file = e.dataTransfer.files[0]

  if (file) {
    emit("file-change", file)
    showMsg("文件已拖拽上传")
  }
}

// ⭐清空修复
const resetUI = () => {
  emit("file-change", null)
  emit("clear")
  msg.value = ""
  isDragging.value = false
}
</script>

<style>
.drop-zone {
  border: 2px dashed #aaa;
  padding: 20px;
  text-align: center;
}

.drop-zone.active {
  border-color: #409eff;
  background: #eef6ff;
}

.msg {
  margin-top: 8px;
  padding: 6px;
  background: #e6ffed;
  border: 1px solid #b7eb8f;
}
.file-name {
  max-width: 100%;
  word-break: break-all;     /* 强制换行 */
  white-space: normal;       /* 允许换行 */
  overflow-wrap: break-word;

  font-size: 14px;
  color: #333;
  margin-top: 8px;
}
</style>
