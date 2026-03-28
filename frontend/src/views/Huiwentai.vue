<template>
  <div class="page-container">
    <h1 class="page-title">汇问台</h1>

    <!-- 子标签导航 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'tasks' }"
        @click="activeTab = 'tasks'"
      >
        问题列表
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'reports' }"
        @click="activeTab = 'reports'"
      >
        日报数据
      </button>
    </div>

    <!-- 内容区域 -->
    <div class="content-card">
      <!-- 问题列表 -->
      <div v-if="activeTab === 'tasks'" class="tasks-section">
        <div class="filter-row">
          <select v-model="selectedMonth" class="form-select">
            <option value="">全部月份</option>
            <option v-for="month in availableMonthsTasks" :key="month" :value="month">{{ month }}</option>
          </select>
          <button class="btn btn-secondary" @click="fetchTasks" :disabled="loading">
            {{ loading ? '加载中...' : '刷新数据' }}
          </button>
        </div>

        <div v-if="error" class="error-message">
          <p>{{ error }}</p>
          <p class="error-hint">请检查CloudBase云环境配置，确保已开启匿名登录</p>
        </div>

        <div v-else class="data-table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>序号</th>
                <th>问题描述</th>
                <th>诉求</th>
                <th>联系方式</th>
                <th>来源</th>
                <th>创建时间</th>
                <th>处理结果</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(task, index) in paginatedTasks" :key="task._id || task.taskId || index">
                <td>{{ (currentPage - 1) * pageSize + index + 1 }}</td>
                <td>{{ task.description || '-' }}</td>
                <td>{{ task.request || '-' }}</td>
                <td>{{ task.contact || '-' }}</td>
                <td>{{ task.source || '-' }}</td>
                <td>{{ formatDate(task.createdAt) }}</td>
                <td>{{ task.processResult || '-' }}</td>
              </tr>
              <tr v-if="filteredTasks.length === 0">
                <td colspan="7" class="empty-text">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pagination" v-if="totalPages > 1">
          <button class="pagination-btn" :disabled="currentPage === 1" @click="currentPage--">上一页</button>
          <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
          <button class="pagination-btn" :disabled="currentPage === totalPages" @click="currentPage++">下一页</button>
        </div>
      </div>

      <!-- 日报数据 -->
      <div v-else class="reports-section">
        <div class="filter-row">
          <select v-model="selectedReportMonth" class="form-select">
            <option value="">全部月份</option>
            <option v-for="month in availableMonthsReports" :key="month" :value="month">{{ month }}</option>
          </select>
          <button class="btn btn-secondary" @click="fetchDailyReports" :disabled="loading">
            {{ loading ? '加载中...' : '刷新数据' }}
          </button>
        </div>

        <!-- 本月统计 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-value">{{ currentMonthStats.reported }}</div>
            <div class="stat-label">本月上报</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ currentMonthStats.accepted }}</div>
            <div class="stat-label">本月受理</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ currentMonthStats.completed }}</div>
            <div class="stat-label">本月完成</div>
          </div>
        </div>

        <div v-if="error" class="error-message">
          <p>{{ error }}</p>
        </div>

        <div v-else class="data-table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>值班人员</th>
                <th>班次</th>
                <th>上报</th>
                <th>受理</th>
                <th>完成</th>
                <th>12345系统</th>
                <th>民呼我应</th>
                <th>视频监控</th>
                <th>市民上报</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="report in paginatedReports" :key="report._id || report.reportDate">
                <td>{{ report.reportDate || '-' }}</td>
                <td>{{ report.dutyStaff || '-' }}</td>
                <td>{{ report.shiftName || '-' }}</td>
                <td>{{ report.reported || 0 }}</td>
                <td>{{ report.accepted || 0 }}</td>
                <td>{{ report.completed || 0 }}</td>
                <td>{{ report.system12345 || 0 }}</td>
                <td>{{ report.minhuWoYing || 0 }}</td>
                <td>{{ report.videoMonitor || 0 }}</td>
                <td>{{ report.citizenReport || 0 }}</td>
              </tr>
              <tr v-if="filteredReports.length === 0">
                <td colspan="10" class="empty-text">暂无数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pagination" v-if="reportTotalPages > 1">
          <button class="pagination-btn" :disabled="reportCurrentPage === 1" @click="reportCurrentPage--">上一页</button>
          <span class="page-info">{{ reportCurrentPage }} / {{ reportTotalPages }}</span>
          <button class="pagination-btn" :disabled="reportCurrentPage === reportTotalPages" @click="reportCurrentPage++">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import cloudbase from '@cloudbase/js-sdk'

// CloudBase 配置
const CLOUDBASE_ENV = 'cloud1-2g359sgd56ce6c79'

const activeTab = ref('tasks')
const loading = ref(false)
const error = ref('')

// 问题列表数据
const tasks = ref([])
const selectedMonth = ref('')
const currentPage = ref(1)
const pageSize = 10

// 日报数据
const dailyReports = ref([])
const selectedReportMonth = ref('')
const reportCurrentPage = ref(1)
const reportPageSize = 15

// 初始化 CloudBase
async function initCloudBase() {
  const app = cloudbase.init({
    env: CLOUDBASE_ENV
  })
  await app.auth().signInAnonymously()
  return app.database()
}

// 获取问题列表
async function fetchTasks() {
  loading.value = true
  error.value = ''
  currentPage.value = 1

  try {
    const db = await initCloudBase()
    const result = await db.collection('tasks').get()
    tasks.value = result.data || []
  } catch (e) {
    console.error('获取问题列表失败:', e)
    error.value = `读取数据失败: ${e.message || '未知错误'}`
    tasks.value = []
  } finally {
    loading.value = false
  }
}

// 获取日报数据
async function fetchDailyReports() {
  loading.value = true
  error.value = ''
  reportCurrentPage.value = 1

  try {
    const db = await initCloudBase()
    const result = await db.collection('daily-reports').get()
    dailyReports.value = result.data || []
  } catch (e) {
    console.error('获取日报数据失败:', e)
    error.value = `读取数据失败: ${e.message || '未知错误'}`
    dailyReports.value = []
  } finally {
    loading.value = false
  }
}

// 计算属性：可用月份（问题列表）
const availableMonthsTasks = computed(() => {
  const months = new Set()
  tasks.value.forEach(task => {
    if (task.createdAt) {
      const date = new Date(task.createdAt)
      months.add(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    }
  })
  return Array.from(months).sort().reverse()
})

// 计算属性：可用月份（日报）
const availableMonthsReports = computed(() => {
  const months = new Set()
  dailyReports.value.forEach(report => {
    if (report.reportDate) {
      const date = new Date(report.reportDate)
      months.add(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    }
  })
  return Array.from(months).sort().reverse()
})

// 计算属性：过滤后的问题列表（按创建时间倒序）
const filteredTasks = computed(() => {
  let data = tasks.value

  if (selectedMonth.value) {
    data = data.filter(task => {
      if (!task.createdAt) return false
      const date = new Date(task.createdAt)
      const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
      return month === selectedMonth.value
    })
  }

  return [...data].sort((a, b) => {
    const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0
    const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0
    return dateB - dateA
  })
})

// 计算属性：过滤后的日报数据（按日期倒序）
const filteredReports = computed(() => {
  let data = dailyReports.value

  if (selectedReportMonth.value) {
    data = data.filter(report => {
      if (!report.reportDate) return false
      const date = new Date(report.reportDate)
      const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
      return month === selectedReportMonth.value
    })
  }

  return [...data].sort((a, b) => {
    const dateA = a.reportDate ? new Date(a.reportDate).getTime() : 0
    const dateB = b.reportDate ? new Date(b.reportDate).getTime() : 0
    return dateB - dateA
  })
})

// 计算属性：分页后的问题列表
const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})

// 计算属性：问题列表总页数
const totalPages = computed(() => Math.ceil(filteredTasks.value.length / pageSize) || 1)

// 计算属性：分页后的日报数据
const paginatedReports = computed(() => {
  const start = (reportCurrentPage.value - 1) * reportPageSize
  return filteredReports.value.slice(start, start + reportPageSize)
})

// 计算属性：日报总页数
const reportTotalPages = computed(() => Math.ceil(filteredReports.value.length / reportPageSize) || 1)

// 计算属性：本月统计
const currentMonthStats = computed(() => {
  const now = new Date()
  const currentMonthStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

  let reported = 0
  let accepted = 0
  let completed = 0

  dailyReports.value.forEach(report => {
    if (report.reportDate) {
      const date = new Date(report.reportDate)
      const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
      if (month === currentMonthStr) {
        reported += report.reported || 0
        accepted += report.accepted || 0
        completed += report.completed || 0
      }
    }
  })

  return { reported, accepted, completed }
})

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

// 监听标签切换
watch(activeTab, (tab) => {
  if (tab === 'tasks' && tasks.value.length === 0) {
    fetchTasks()
  } else if (tab === 'reports' && dailyReports.value.length === 0) {
    fetchDailyReports()
  }
})

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-6);
}

.tabs {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.tab {
  padding: var(--space-3) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover { color: var(--primary-500); }
.tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.filter-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  align-items: center;
}

.form-select {
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  min-width: 150px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-secondary {
  background: var(--bg-card);
  color: var(--text-primary);
  border-color: var(--border-lighter);
  white-space: nowrap;
}

.btn-secondary:hover { border-color: var(--primary-300); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4);
  background: var(--fill-light);
  border-radius: var(--radius-lg);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--primary-500);
}

.stat-label {
  font-size: 14px;
  color: var(--text-tertiary);
}

.data-table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  border-bottom: 1px solid var(--border-lighter);
}

.data-table th {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  white-space: nowrap;
}

.data-table td {
  color: var(--text-primary);
}

.error-message {
  text-align: center;
  padding: var(--space-8);
  color: var(--danger);
}

.error-hint {
  color: var(--text-tertiary);
  font-size: 14px;
  margin-top: var(--space-2);
}

.empty-text {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-4);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.pagination-btn {
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.pagination-btn:hover:not(:disabled) { border-color: var(--primary-500); color: var(--primary-500); }
.pagination-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.page-info { color: var(--text-secondary); font-size: 14px; }

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>