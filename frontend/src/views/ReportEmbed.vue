<template>
  <div class="embed-page">
    <header class="embed-header">
      <button class="btn-back" @click="$router.back()">
        ← 返回
      </button>
      <h1 class="embed-title">{{ reportTitle }}</h1>
    </header>
    <div class="embed-container">
      <iframe
        :src="reportUrl"
        class="report-iframe"
        frameborder="0"
        allowfullscreen
      ></iframe>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const filename = computed(() => route.params.filename)
const reportUrl = computed(() => `/reports/${filename.value}`)
const reportTitle = computed(() => {
  const name = filename.value.replace('.html', '')
  const titleMap = {
    'sanitation-july-report': '环卫部门7月案件分析报告'
  }
  return titleMap[name] || '报告查看'
})
</script>

<style scoped>
.embed-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
}

.embed-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-lighter);
  flex-shrink: 0;
}

.btn-back {
  background: none;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.btn-back:hover {
  background: var(--primary-50);
  border-color: var(--primary-500);
  color: var(--primary-500);
}

.embed-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.embed-container {
  flex: 1;
  overflow: hidden;
}

.report-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
