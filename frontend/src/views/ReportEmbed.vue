<template>
  <div class="embed-page" ref="pageRef">
    <header class="embed-header">
      <button class="btn-back" @click="$router.back()">
        ← 返回
      </button>
      <h1 class="embed-title">{{ reportTitle }}</h1>
      <button class="btn-fullscreen" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏 (Esc)' : '全屏查看'">
        {{ isFullscreen ? '退出全屏' : '全屏' }}
      </button>
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
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageRef = ref(null)
const isFullscreen = ref(false)

const filename = computed(() => route.params.filename)
const reportUrl = computed(() => `/reports/${filename.value}`)
const reportTitle = computed(() => {
  const name = filename.value.replace('.html', '')
  const m = name.match(/^(\d{4})(\d{2})$/)
  if (m) return `${m[1]}年${parseInt(m[2])}月城市管理案件数据分析报告`
  const titleMap = {
    'sanitation-july-report': '环卫部门7月案件分析报告'
  }
  return titleMap[name] || '报告查看'
})

function toggleFullscreen() {
  const el = pageRef.value
  if (!el) return
  if (!document.fullscreenElement && !document.webkitFullscreenElement) {
    const req = el.requestFullscreen || el.webkitRequestFullscreen
    if (req) req.call(el)
  } else {
    const exit = document.exitFullscreen || document.webkitExitFullscreen
    if (exit) exit.call(document)
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!(document.fullscreenElement || document.webkitFullscreenElement)
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
})
</script>

<style scoped>
.embed-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
}
.embed-page:fullscreen {
  width: 100vw;
  height: 100vh;
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

.btn-fullscreen {
  margin-left: auto;
  background: none;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  white-space: nowrap;
}
.btn-fullscreen:hover {
  background: var(--primary-50);
  border-color: var(--primary-500);
  color: var(--primary-500);
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
