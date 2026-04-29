<template>
  <div class="page">
    <h2>历史记录</h2>

    <div v-for="(item, index) in history" :key="index" class="card">
      <p><b>时间：</b>{{ item.time }}</p>
      <p><b>总结：</b>{{ item.summary }}</p>
    </div>

    <router-link to="/">返回主页</router-link>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"

const history = ref([])

onMounted(() => {
  history.value = JSON.parse(localStorage.getItem("history") || "[]")
})
</script>