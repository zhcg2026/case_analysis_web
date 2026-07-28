<template>
  <div class="home-page">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-content">
        <h1 class="welcome-title">欢迎回来，{{ userStore.username }}</h1>
        <p class="welcome-subtitle">智慧平台一站通 v2.0 - 智能数据分析平台</p>
      </div>
      <div class="welcome-time">
        <div class="time-display">{{ currentTime }}</div>
        <div class="date-display">{{ currentDate }}</div>
      </div>
    </div>

    <!-- 栏目文章区域 -->
    <div class="cms-section">
      <div class="cms-columns">
        <div v-for="column in columns" :key="column.id" class="cms-column">
          <div class="column-header">
            <div class="column-title-wrapper">
              <h3 class="column-title">{{ column.name }}</h3>
            </div>
            <a class="more-link" @click="viewMore(column)">
              更多 <span>›</span>
            </a>
          </div>
          <div class="column-articles">
            <div
              v-for="(article, index) in column.articles"
              :key="article.id"
              class="article-item"
              @click="viewArticle(article)"
            >
              <span class="article-index">{{ index + 1 }}</span>
              <span class="article-title">{{ article.title }}</span>
              <span class="article-date">{{ formatDate(article.created_at) }}</span>
            </div>
            <div v-if="!column.articles || column.articles.length === 0" class="empty-column">
              暂无文章
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import axios from 'axios'

const userStore = useUserStore()
const router = useRouter()

const currentTime = ref('')
const currentDate = ref('')
let timeInterval = null

const columns = ref([])

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  currentDate.value = now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
}

async function fetchColumns() {
  try {
    const response = await axios.get('/api/cms/home-columns')
    columns.value = response.data || []
  } catch (error) {
    console.error('获取栏目文章失败:', error)
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}-${date.getDate()}`
}

function viewArticle(article) {
  router.push(`/article/${article.id}`)
}

function viewMore(column) {
  router.push(`/category/${column.id}`)
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  fetchColumns()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.home-page {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.welcome-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-6);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  margin-bottom: var(--space-6);
}

.welcome-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 var(--space-1);
  color: var(--text-primary);
}

.welcome-subtitle {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0;
}

.welcome-time {
  text-align: right;
}

.time-display {
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

.date-display {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.cms-section {
  margin-bottom: var(--space-6);
}

.cms-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-4);
}

.cms-column {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-lighter);
}

.column-title-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.column-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.more-link {
  color: var(--primary-500);
  text-decoration: none;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.more-link:hover {
  color: var(--primary-600);
}

.column-articles {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.article-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.article-item:hover {
  background: var(--fill-light);
}

.article-index {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.article-title {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.article-date {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.empty-column {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-4);
  font-size: 14px;
}

@media (max-width: 768px) {
  .welcome-banner {
    flex-direction: column;
    text-align: center;
    gap: var(--space-4);
  }

  .welcome-time {
    text-align: center;
  }

  .cms-columns {
    grid-template-columns: 1fr;
  }
}
</style>
