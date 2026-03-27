<template>
  <div class="page-container">
    <h1 class="page-title">考核计分</h1>

    <!-- 子标签导航 -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'old' }"
        @click="activeTab = 'old'"
      >
        考核计分（原版）
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'new' }"
        @click="activeTab = 'new'"
      >
        考核计分（新版）
      </button>
    </div>

    <!-- 内容区域 -->
    <div class="content-card">
      <!-- 原版考核计分 -->
      <div v-if="activeTab === 'old'">
        <!-- 说明信息 -->
        <div class="info-box">
          <span class="info-icon">!</span>
          <div class="info-content">
            <div class="info-title">计算说明</div>
            <p>超时案件计算：结案时间 > 捆绑处置截止时间判定的，与实际超时计算有出入</p>
          </div>
        </div>

        <!-- 配置区域 -->
        <div class="config-section">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">选择部门</label>
              <select v-model="selectedDepartment" class="form-select" :disabled="loading">
                <option value="">请选择部门</option>
                <option v-for="dept in departments" :key="dept" :value="dept">{{ dept }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">选择数据表</label>
              <select v-model="selectedTable" class="form-select" :disabled="loading">
                <option value="">请选择</option>
                <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
              </select>
            </div>
          </div>

          <!-- 月份筛选 -->
          <div v-if="selectedTable === 'business_cases'" class="form-group">
            <label class="form-label">选择月份</label>
            <select v-model="selectedMonth" class="form-select month-select" :disabled="loading">
              <option value="">全部月份</option>
              <option v-for="month in availableMonths" :key="month" :value="month">{{ formatMonth(month) }}</option>
            </select>
          </div>

          <button class="btn btn-primary btn-block" @click="runAssessment" :disabled="loading || !selectedDepartment || !selectedTable">
            {{ loading ? '计算中...' : '开始计算' }}
          </button>

          <div v-if="message" class="message" :class="messageType">{{ message }}</div>
        </div>

        <!-- 考核结果 -->
        <div v-if="result" class="result-section">
          <h3 class="result-title">考核结果</h3>

          <!-- 结果摘要 -->
          <div class="stats-row">
            <div class="stat-card primary">
              <div class="stat-label">总案件数</div>
              <div class="stat-value">{{ result.total_cases }}</div>
            </div>
            <div class="stat-card secondary">
              <div class="stat-label">平均得分</div>
              <div class="stat-value">{{ result.score }} 分</div>
            </div>
          </div>

          <!-- 排名表格 -->
          <div v-if="result.team_results && result.team_results.length" class="table-wrapper">
            <h4 class="table-title">片区排名</h4>
            <table class="data-table">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>片区名称</th>
                  <th>案件总数</th>
                  <th>按期结案</th>
                  <th>超期结案</th>
                  <th>延期次数</th>
                  <th>返工次数</th>
                  <th>得分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="team in result.team_results" :key="team.department">
                  <td class="rank-cell">
                    <span class="rank-badge" :class="getRankClass(team.rank)">{{ team.rank }}</span>
                  </td>
                  <td>{{ team.department }}</td>
                  <td>{{ team.total_cases }}</td>
                  <td class="text-success">{{ team.on_time_count }}</td>
                  <td class="text-danger">{{ team.overdue_count }}</td>
                  <td class="text-warning">{{ team.delay_count }}</td>
                  <td class="text-purple">{{ team.rework_count }}</td>
                  <td>
                    <span class="score-badge">{{ team.score }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 新版考核计分 -->
      <div v-else>
        <!-- 说明信息 -->
        <div class="info-box">
          <span class="info-icon">i</span>
          <div class="info-content">
            <div class="info-title">计算说明</div>
            <p>超时案件计算：根据表中"是否超时"字段判定，为空表示不超时，不为空表示超时</p>
          </div>
        </div>

        <!-- 配置区域 -->
        <div class="config-section">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">选择部门</label>
              <select v-model="selectedDepartmentV2" class="form-select" :disabled="loadingV2">
                <option value="">请选择部门</option>
                <option v-for="dept in departments" :key="dept" :value="dept">{{ dept }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">选择数据表</label>
              <select v-model="selectedTableV2" class="form-select" :disabled="loadingV2">
                <option value="">请选择</option>
                <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
              </select>
            </div>
          </div>

          <!-- 月份筛选 -->
          <div v-if="selectedTableV2 === 'business_cases'" class="form-group">
            <label class="form-label">选择月份</label>
            <select v-model="selectedMonthV2" class="form-select month-select" :disabled="loadingV2">
              <option value="">全部月份</option>
              <option v-for="month in availableMonthsV2" :key="month" :value="month">{{ formatMonth(month) }}</option>
            </select>
          </div>

          <button class="btn btn-primary btn-block" @click="runAssessmentV2" :disabled="loadingV2 || !selectedDepartmentV2 || !selectedTableV2">
            {{ loadingV2 ? '计算中...' : '开始计算' }}
          </button>

          <div v-if="messageV2" class="message" :class="messageTypeV2">{{ messageV2 }}</div>
        </div>

        <!-- 考核结果 -->
        <div v-if="resultV2" class="result-section">
          <h3 class="result-title">考核结果</h3>

          <!-- 结果摘要 -->
          <div class="stats-row">
            <div class="stat-card primary">
              <div class="stat-label">总案件数</div>
              <div class="stat-value">{{ resultV2.total_cases }}</div>
            </div>
            <div class="stat-card secondary">
              <div class="stat-label">平均得分</div>
              <div class="stat-value">{{ resultV2.score }} 分</div>
            </div>
          </div>

          <!-- 排名表格 -->
          <div v-if="resultV2.team_results && resultV2.team_results.length" class="table-wrapper">
            <h4 class="table-title">片区排名</h4>
            <table class="data-table">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>片区名称</th>
                  <th>案件总数</th>
                  <th>按期结案</th>
                  <th>超期结案</th>
                  <th>延期次数</th>
                  <th>返工次数</th>
                  <th>得分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="team in resultV2.team_results" :key="team.department">
                  <td class="rank-cell">
                    <span class="rank-badge" :class="getRankClass(team.rank)">{{ team.rank }}</span>
                  </td>
                  <td>{{ team.department }}</td>
                  <td>{{ team.total_cases }}</td>
                  <td class="text-success">{{ team.on_time_count }}</td>
                  <td class="text-danger">{{ team.overdue_count }}</td>
                  <td class="text-warning">{{ team.delay_count }}</td>
                  <td class="text-purple">{{ team.rework_count }}</td>
                  <td>
                    <span class="score-badge">{{ team.score }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

const activeTab = ref('old')

// 部门列表
const departments = [
  '城市综合行政执法队',
  '市容环卫中心',
  '园林绿化服务中心（片区）',
  '园林绿化服务中心（公园广场）'
]

// 数据表列表
const tables = ref([])

// 原版状态
const selectedDepartment = ref('')
const selectedTable = ref('')
const selectedMonth = ref('')
const loading = ref(false)
const message = ref('')
const messageType = ref('success')
const result = ref(null)
const availableMonths = ref([])

// 新版状态
const selectedDepartmentV2 = ref('')
const selectedTableV2 = ref('')
const selectedMonthV2 = ref('')
const loadingV2 = ref(false)
const messageV2 = ref('')
const messageTypeV2 = ref('success')
const resultV2 = ref(null)
const availableMonthsV2 = ref([])

// 获取数据表列表
async function fetchTables() {
  try {
    const response = await axios.get('/api/tables')
    tables.value = response.data.tables || []
  } catch (error) {
    console.error('获取数据表列表失败:', error)
  }
}

// 获取可用月份
async function fetchAvailableMonths(tableName) {
  try {
    const response = await axios.get(`/api/tables/${tableName}/months`)
    return response.data.months || []
  } catch (error) {
    console.error('获取月份列表失败:', error)
    return []
  }
}

// 格式化月份
function formatMonth(month) {
  if (!month) return ''
  const [year, m] = month.split('-')
  return `${year}年${parseInt(m)}月`
}

// 获取排名样式类
function getRankClass(rank) {
  if (rank === 1) return 'gold'
  if (rank === 2) return 'silver'
  if (rank === 3) return 'bronze'
  return ''
}

// 原版考核计算
async function runAssessment() {
  if (!selectedDepartment.value || !selectedTable.value) return

  loading.value = true
  message.value = ''
  result.value = null

  try {
    const response = await axios.post('/api/assess', {
      table_name: selectedTable.value,
      department: selectedDepartment.value,
      month: selectedMonth.value
    })
    result.value = response.data
    message.value = '考核计算完成'
    messageType.value = 'success'
  } catch (error) {
    console.error('考核计算失败:', error)
    message.value = '计算失败: ' + (error.response?.data?.error || error.message)
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

// 新版考核计算
async function runAssessmentV2() {
  if (!selectedDepartmentV2.value || !selectedTableV2.value) return

  loadingV2.value = true
  messageV2.value = ''
  resultV2.value = null

  try {
    const response = await axios.post('/api/assess/v2', {
      table_name: selectedTableV2.value,
      department: selectedDepartmentV2.value,
      month: selectedMonthV2.value
    })
    resultV2.value = response.data
    messageV2.value = '考核计算完成'
    messageTypeV2.value = 'success'
  } catch (error) {
    console.error('考核计算失败:', error)
    messageV2.value = '计算失败: ' + (error.response?.data?.error || error.message)
    messageTypeV2.value = 'error'
  } finally {
    loadingV2.value = false
  }
}

// 监听数据表选择，获取月份
watch(selectedTable, async (table) => {
  if (table) {
    availableMonths.value = await fetchAvailableMonths(table)
  }
})

watch(selectedTableV2, async (table) => {
  if (table) {
    availableMonthsV2.value = await fetchAvailableMonths(table)
  }
})

onMounted(() => {
  fetchTables()
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
  white-space: nowrap;
}

.tab:hover { color: var(--primary-500); }
.tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.info-box {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--primary-50);
  border: 1px solid var(--primary-200);
  border-left: 4px solid var(--primary-500);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-6);
}

.info-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: white;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.info-content {
  flex: 1;
}

.info-title {
  font-weight: 600;
  color: var(--primary-500);
  margin-bottom: var(--space-1);
}

.info-content p {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.config-section {
  padding: var(--space-6);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-6);
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.form-select {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.form-select:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}

.month-select {
  max-width: 200px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.btn-primary {
  background: var(--primary-500);
  color: white;
}

.btn-primary:hover:not(:disabled) { background: var(--primary-600); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-block { width: 100%; }

.message {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: 14px;
}

.message.success {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.message.error {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
  border: 1px solid rgba(245, 108, 108, 0.3);
}

.result-section {
  padding: var(--space-6);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
}

.result-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 2px solid var(--primary-500);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.stat-card {
  padding: var(--space-6);
  border-radius: var(--radius-md);
  text-align: center;
}

.stat-card.primary {
  background: linear-gradient(135deg, var(--primary-500) 0%, #00c6fb 100%);
  color: white;
}

.stat-card.secondary {
  background: linear-gradient(135deg, #00c6fb 0%, #005bea 100%);
  color: white;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: var(--space-2);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
}

.table-wrapper {
  overflow-x: auto;
}

.table-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
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
  background: linear-gradient(135deg, var(--primary-500) 0%, #00c6fb 100%);
  color: white;
  font-weight: 600;
  white-space: nowrap;
}

.data-table tbody tr:hover {
  background: var(--fill-light);
}

.rank-cell {
  text-align: center;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-500) 0%, #00c6fb 100%);
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.rank-badge.gold {
  background: linear-gradient(135deg, #ffd700 0%, #ffb700 100%);
}

.rank-badge.silver {
  background: linear-gradient(135deg, #c0c0c0 0%, #a0a0a0 100%);
}

.rank-badge.bronze {
  background: linear-gradient(135deg, #cd7f32 0%, #a0522d 100%);
}

.text-success { color: #67c23a; font-weight: 600; }
.text-danger { color: #f56c6c; font-weight: 600; }
.text-warning { color: #e6a23c; }
.text-purple { color: #909399; }

.score-badge {
  display: inline-block;
  padding: var(--space-1) var(--space-3);
  background: linear-gradient(135deg, var(--primary-500) 0%, #00c6fb 100%);
  color: white;
  border-radius: var(--radius-full);
  font-weight: 600;
  font-size: 14px;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>