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

    <!-- 核心数据卡片 -->
    <div class="stats-section">
      <div class="stats-card">
        <div class="stats-icon primary">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
            <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
            <path d="M10 9H8"/>
            <path d="M16 13H8"/>
            <path d="M16 17H8"/>
          </svg>
        </div>
        <div class="stats-content">
          <div class="stats-value">{{ stats.totalCases }}</div>
          <div class="stats-label">案件总数</div>
        </div>
      </div>

      <div class="stats-card">
        <div class="stats-icon success">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
        </div>
        <div class="stats-content">
          <div class="stats-value">{{ stats.completedCases }}</div>
          <div class="stats-label">已结案</div>
        </div>
      </div>

      <div class="stats-card">
        <div class="stats-icon warning">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <div class="stats-content">
          <div class="stats-value">{{ stats.pendingCases }}</div>
          <div class="stats-label">跟进中</div>
        </div>
      </div>

      <div class="stats-card">
        <div class="stats-icon danger">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <div class="stats-content">
          <div class="stats-value">{{ stats.expiringCases }}</div>
          <div class="stats-label">即将到期</div>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="quick-actions">
      <h2 class="section-title">快捷操作</h2>
      <div class="actions-grid">
        <router-link to="/cases" class="action-card">
          <span class="action-icon cases">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>
              <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
            </svg>
          </span>
          <span class="action-text">案件录入</span>
        </router-link>
        <router-link to="/ai-apps" class="action-card">
          <span class="action-icon ai">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 8V4H8"/>
              <rect width="16" height="12" x="4" y="8" rx="2"/>
              <path d="M2 14h2"/>
              <path d="M20 14h2"/>
              <path d="M15 13v2"/>
              <path d="M9 13v2"/>
            </svg>
          </span>
          <span class="action-text">AI分析</span>
        </router-link>
        <router-link to="/huiwentai" class="action-card">
          <span class="action-icon huiwentai">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="2"/>
              <path d="M7 7h10"/>
              <path d="M7 12h10"/>
              <path d="M7 17h10"/>
            </svg>
          </span>
          <span class="action-text">汇问台</span>
        </router-link>
        <router-link to="/assessment" class="action-card">
          <span class="action-icon assessment">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 3v18h18"/>
              <path d="m19 9-5 5-4-4-3 3"/>
            </svg>
          </span>
          <span class="action-text">考核计分</span>
        </router-link>
        <router-link to="/map" class="action-card">
          <span class="action-icon map">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
              <line x1="8" y1="2" x2="8" y2="18"/>
              <line x1="16" y1="6" x2="16" y2="22"/>
            </svg>
          </span>
          <span class="action-text">地图服务</span>
        </router-link>
        <router-link to="/business" class="action-card">
          <span class="action-icon business">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>
              <path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/>
              <path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/>
              <path d="M10 6h4"/>
              <path d="M10 10h4"/>
              <path d="M10 14h4"/>
              <path d="M10 18h4"/>
            </svg>
          </span>
          <span class="action-text">业务平台</span>
        </router-link>
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

// 当前时间
const currentTime = ref('')
const currentDate = ref('')
let timeInterval = null

// 统计数据
const stats = ref({
  totalCases: 0,
  completedCases: 0,
  pendingCases: 0,
  expiringCases: 0
})

// 栏目文章
const columns = ref([])

// 更新时间
function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  currentDate.value = now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
}

// 获取统计数据
async function fetchStats() {
  try {
    const response = await axios.get('/api/cases/stats')
    const data = response.data || {}
    // 映射后端字段到前端
    stats.value = {
      totalCases: data.total || 0,
      completedCases: data.closed || 0,
      pendingCases: data.follow_up || 0,
      expiringCases: data.expiring_soon || 0
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

// 获取栏目文章
async function fetchColumns() {
  try {
    const response = await axios.get('/api/cms/home-columns')
    columns.value = response.data || []
  } catch (error) {
    console.error('获取栏目文章失败:', error)
  }
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}-${date.getDate()}`
}

// 查看文章
function viewArticle(article) {
  router.push(`/article/${article.id}`)
}

// 查看更多
function viewMore(column) {
  router.push(`/category/${column.id}`)
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)

  fetchStats()
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

/* 欢迎横幅 */
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

/* 统计卡片 */
.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.stats-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  transition: all var(--transition-fast);
}

.stats-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.stats-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
}

.stats-icon.primary {
  background: rgba(64, 158, 255, 0.1);
  color: var(--primary-500);
}

.stats-icon.success {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
}

.stats-icon.warning {
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
}

.stats-icon.danger {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
}

.stats-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.stats-label {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* 快捷操作 */
.quick-actions {
  margin-bottom: var(--space-6);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-3);
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  text-decoration: none;
  transition: all var(--transition-fast);
}

.action-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--primary-200);
}

.action-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.action-icon.cases { background: rgba(64, 158, 255, 0.1); color: #409eff; }
.action-icon.ai { background: rgba(144, 147, 153, 0.1); color: #909399; }
.action-icon.huiwentai { background: rgba(103, 194, 58, 0.1); color: #67c23a; }
.action-icon.assessment { background: rgba(230, 162, 60, 0.1); color: #e6a23c; }
.action-icon.map { background: rgba(64, 158, 255, 0.1); color: #409eff; }
.action-icon.business { background: rgba(103, 194, 58, 0.1); color: #67c23a; }

.action-card:hover .action-icon.cases { background: rgba(64, 158, 255, 0.2); }
.action-card:hover .action-icon.ai { background: rgba(144, 147, 153, 0.2); }
.action-card:hover .action-icon.huiwentai { background: rgba(103, 194, 58, 0.2); }
.action-card:hover .action-icon.assessment { background: rgba(230, 162, 60, 0.2); }
.action-card:hover .action-icon.map { background: rgba(64, 158, 255, 0.2); }
.action-card:hover .action-icon.business { background: rgba(103, 194, 58, 0.2); }

.action-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

/* 栏目文章区域 */
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

/* 响应式 */
@media (max-width: 768px) {
  .welcome-banner {
    flex-direction: column;
    text-align: center;
    gap: var(--space-4);
  }

  .welcome-time {
    text-align: center;
  }

  .stats-section {
    grid-template-columns: repeat(2, 1fr);
  }

  .actions-grid {
    grid-template-columns: repeat(4, 1fr);
  }

  .cms-columns {
    grid-template-columns: 1fr;
  }
}
</style>