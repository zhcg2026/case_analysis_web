<template>
  <div class="page-container">
    <h1 class="page-title">AI应用</h1>

    <!-- 子标签导航 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 数据分析 -->
    <div v-if="activeTab === 'analysis'" class="content-card">
      <div class="config-section">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">选择数据表</label>
            <select v-model="selectedTable" class="form-select" :disabled="loading">
              <option value="">请选择</option>
              <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">分析类型</label>
            <select v-model="selectedAnalysisType" class="form-select" :disabled="loading">
              <option value="">请选择</option>
              <option v-for="type in analysisTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="selectedTable === 'business_cases'" class="form-group">
          <label class="form-label">选择月份</label>
          <select v-model="selectedMonth" class="form-select month-select" :disabled="loading">
            <option value="">全部月份</option>
            <option v-for="month in availableMonths" :key="month" :value="month">{{ formatMonth(month) }}</option>
          </select>
        </div>

        <button class="btn btn-primary btn-block" @click="runAnalysis" :disabled="loading || !selectedTable || !selectedAnalysisType">
          {{ loading ? '分析中...' : '开始分析' }}
        </button>

        <!-- 进度显示 -->
        <div v-if="loading" class="progress-section">
          <div class="progress-title">分析进度</div>
          <div v-for="(step, index) in analysisSteps" :key="index" class="progress-step" :class="step.status">
            <div class="step-icon">
              <span v-if="step.status === 'completed'">✓</span>
              <span v-else>{{ step.icon }}</span>
            </div>
            <span class="step-text">{{ step.text }}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- 分析结果 -->
      <div v-if="analysisResult" class="result-section">
        <div class="result-header">
          <h3>{{ analysisResult.table_name }} - {{ getAnalysisTypeName(analysisResult.analysis_type) }}</h3>
          <p>{{ analysisResult.data_summary }}</p>
        </div>

        <!-- 图表 -->
        <div v-if="analysisResult.chart_data" class="charts-grid">
          <div v-for="(chartConfig, chartKey) in chartConfigs" :key="chartKey" class="chart-card">
            <h4>{{ chartConfig.title }}</h4>
            <div :ref="el => chartRefs[chartKey] = el" class="chart-container"></div>
          </div>
        </div>

        <!-- AI分析 -->
        <div v-if="analysisResult.analysis" class="ai-result">
          <div class="ai-header">
            <span class="ai-icon">🤖</span>
            <h4>AI智能分析</h4>
          </div>
          <div class="ai-content" v-html="formatAnalysis(analysisResult.analysis)"></div>
        </div>
      </div>
    </div>

    <!-- 数据分析V2 -->
    <div v-else-if="activeTab === 'analysis-v2'" class="content-card">
      <div class="config-section">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">选择数据表</label>
            <select v-model="selectedTableV2" class="form-select" :disabled="loadingV2">
              <option value="">请选择</option>
              <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">选择大模型</label>
            <select v-model="selectedModel" class="form-select" :disabled="loadingV2">
              <option value="volcengine">火山引擎（豆包）</option>
              <option value="bailian">阿里云百炼（通义千问）</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">分析提示词</label>
          <textarea v-model="analysisPrompt" class="form-textarea" rows="4" placeholder="请输入分析需求，例如：分析案件来源分布情况" :disabled="loadingV2"></textarea>
        </div>

        <button class="btn btn-primary btn-block" @click="runAnalysisV2" :disabled="loadingV2 || !selectedTableV2 || !analysisPrompt">
          {{ loadingV2 ? '分析中...' : '开始分析' }}
        </button>
      </div>

      <!-- V2分析结果 -->
      <div v-if="analysisV2Result" class="result-section">
        <div class="result-header">
          <h3>{{ analysisV2Result.table_name }} - 智能分析报告</h3>
          <p v-if="analysisV2Result.filtered_count">共分析 {{ analysisV2Result.filtered_count }} 条数据</p>
        </div>

        <!-- 图表 -->
        <div v-if="analysisV2Result.charts && analysisV2Result.charts.length" class="charts-grid">
          <div v-for="(chart, index) in analysisV2Result.charts" :key="index" class="chart-card">
            <h4>{{ chart.title }}</h4>
            <div v-if="chart.type === 'image'" class="chart-image">
              <img :src="chart.data" :alt="chart.title" />
            </div>
            <div v-else :ref="el => chartV2Refs[index] = el" class="chart-container"></div>
          </div>
        </div>

        <!-- 分析报告 -->
        <div v-if="analysisV2Result.report" class="ai-result">
          <div class="ai-header">
            <span class="ai-icon">🤖</span>
            <h4>AI智能分析报告</h4>
            <button class="btn btn-secondary btn-sm" @click="copyReport">复制报告</button>
          </div>
          <div class="ai-content" v-html="formatAnalysis(analysisV2Result.report)"></div>
        </div>
      </div>
    </div>

    <!-- 图表分析 -->
    <div v-else-if="activeTab === 'chart'" class="content-card">
      <div class="config-section">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">选择数据表</label>
            <select v-model="chartTable" class="form-select" :disabled="chartLoading">
              <option value="">请选择</option>
              <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">选择月份</label>
            <select v-model="chartMonth" class="form-select" :disabled="chartLoading">
              <option value="">全部月份</option>
              <option v-for="month in chartAvailableMonths" :key="month" :value="month">{{ formatMonth(month) }}</option>
            </select>
          </div>
        </div>

        <button class="btn btn-primary btn-block" @click="runChartAnalysis" :disabled="chartLoading || !chartTable">
          {{ chartLoading ? '生成中...' : '生成仪表盘' }}
        </button>
      </div>

      <!-- 图表仪表盘 -->
      <div v-if="chartResult" class="dashboard">
        <div class="dashboard-header">
          <h3>{{ chartTable }} 数据仪表盘</h3>
          <p>共 {{ chartResult.total_count }} 条数据</p>
        </div>

        <div class="dashboard-charts">
          <div v-for="(chart, key) in chartResult.charts" :key="key" class="dashboard-chart">
            <h4>{{ chart.title }}</h4>
            <div :ref="el => dashboardChartRefs[key] = el" class="chart-container"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 案件抽查 -->
    <div v-else-if="activeTab === 'spotcheck'" class="content-card">
      <div class="config-section">
        <div class="upload-area" @click="$refs.spotcheckFile.click()">
          <input ref="spotcheckFile" type="file" accept=".docx,.xlsx" @change="handleSpotcheckFile" hidden />
          <div class="upload-icon">📄</div>
          <div class="upload-text">点击上传案件文件</div>
          <div class="upload-hint">支持 .docx、.xlsx 格式</div>
        </div>

        <div v-if="spotcheckLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>AI分析中，请稍候...</span>
        </div>

        <div v-if="spotcheckResult" class="spotcheck-result">
          <h4>分析结果</h4>
          <div class="result-content" v-html="formatAnalysis(spotcheckResult.analysis)"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const tabs = [
  { key: 'analysis', label: '数据分析' },
  { key: 'analysis-v2', label: '数据分析V2' },
  { key: 'chart', label: '图表分析' },
  { key: 'spotcheck', label: '案件抽查' }
]

const activeTab = ref('analysis')
const tables = ref([])

// ===== 数据分析 =====
const selectedTable = ref('')
const selectedAnalysisType = ref('')
const selectedMonth = ref('')
const loading = ref(false)
const analysisResult = ref(null)
const availableMonths = ref([])
const chartRefs = ref({})

const analysisTypes = [
  { value: 'time_analysis', label: '时间分析' },
  { value: 'space_analysis', label: '空间分析' },
  { value: 'source_analysis', label: '来源分析' },
  { value: 'type_analysis', label: '类型分析' },
  { value: 'duplicate_analysis', label: '重复案件分析' },
  { value: 'monthly_comparison', label: '对比上月' }
]

const analysisSteps = ref([
  { icon: '1', text: '读取数据表', status: 'pending' },
  { icon: '2', text: '数据预处理', status: 'pending' },
  { icon: '3', text: '执行分析', status: 'pending' },
  { icon: '4', text: '生成图表', status: 'pending' },
  { icon: '5', text: 'AI智能分析', status: 'pending' }
])

const currentStep = ref(0)

const progressPercent = computed(() => ((currentStep.value + 1) / analysisSteps.value.length) * 100)

const chartConfigs = computed(() => {
  if (!analysisResult.value?.chart_data) return {}
  const configs = {}
  const data = analysisResult.value.chart_data
  const type = analysisResult.value.analysis_type

  if (type === 'time_analysis') {
    if (data.daily) configs.daily = { title: '日案件量趋势', data: data.daily, type: 'line' }
    if (data.hourly) configs.hourly = { title: '小时级高峰时段', data: data.hourly, type: 'bar' }
  } else if (type === 'space_analysis') {
    if (data.street) configs.street = { title: '各街道案件密度', data: data.street, type: 'bar' }
    if (data.community) configs.community = { title: '各社区案件密度', data: data.community, type: 'bar' }
  } else if (type === 'source_analysis') {
    if (data.source) configs.source = { title: '案件来源分布', data: data.source, type: 'pie' }
  } else if (type === 'type_analysis') {
    if (data.type) configs.type = { title: '案件类型分布', data: data.type, type: 'pie' }
  } else if (type === 'duplicate_analysis') {
    if (data.problem_duplicates) configs.problem = { title: '问题描述重复TOP10', data: data.problem_duplicates, type: 'bar' }
    if (data.address_duplicates) configs.address = { title: '地址描述重复TOP10', data: data.address_duplicates, type: 'bar' }
  } else if (type === 'monthly_comparison') {
    if (data.monthly_comparison) configs.monthly = { title: '上月vs本月案件量对比', data: data.monthly_comparison, type: 'bar' }
  }
  return configs
})

// ===== 数据分析V2 =====
const selectedTableV2 = ref('')
const selectedModel = ref('volcengine')
const analysisPrompt = ref('')
const loadingV2 = ref(false)
const analysisV2Result = ref(null)
const chartV2Refs = ref({})

// ===== 图表分析 =====
const chartTable = ref('')
const chartMonth = ref('')
const chartLoading = ref(false)
const chartResult = ref(null)
const chartAvailableMonths = ref([])
const dashboardChartRefs = ref({})

// ===== 案件抽查 =====
const spotcheckLoading = ref(false)
const spotcheckResult = ref(null)

// ===== 方法定义 =====

async function fetchTables() {
  try {
    const response = await axios.get('/api/tables')
    tables.value = response.data.tables || []
  } catch (error) {
    console.error('获取表列表失败:', error)
  }
}

async function fetchAvailableMonths(tableName) {
  try {
    const response = await axios.get(`/api/tables/${tableName}/months`)
    return response.data.months || []
  } catch (error) {
    console.error('获取月份列表失败:', error)
    return []
  }
}

function formatMonth(month) {
  if (!month) return ''
  const [year, m] = month.split('-')
  return `${year}年${parseInt(m)}月`
}

function getAnalysisTypeName(type) {
  const map = {
    time_analysis: '时间分析',
    space_analysis: '空间分析',
    source_analysis: '来源分析',
    type_analysis: '类型分析',
    duplicate_analysis: '重复案件分析',
    monthly_comparison: '对比上月'
  }
  return map[type] || type
}

function formatAnalysis(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br>')
}

function resetSteps() {
  analysisSteps.value.forEach(step => step.status = 'pending')
  currentStep.value = 0
}

function updateStep(index, status) {
  analysisSteps.value[index].status = status
  if (status === 'active' || status === 'completed') {
    currentStep.value = index
  }
}

async function runAnalysis() {
  if (!selectedTable.value || !selectedAnalysisType.value) return

  loading.value = true
  analysisResult.value = null
  resetSteps()

  try {
    // 步骤1：读取数据
    updateStep(0, 'active')
    await new Promise(r => setTimeout(r, 500))
    updateStep(0, 'completed')

    // 步骤2：预处理
    updateStep(1, 'active')
    await new Promise(r => setTimeout(r, 300))
    updateStep(1, 'completed')

    // 步骤3：执行分析
    updateStep(2, 'active')
    const response = await axios.post('/api/analyze', {
      table_name: selectedTable.value,
      analysis_type: selectedAnalysisType.value,
      month: selectedMonth.value
    })
    updateStep(2, 'completed')

    // 步骤4：生成图表
    updateStep(3, 'active')
    analysisResult.value = response.data
    await nextTick()
    renderCharts()
    updateStep(3, 'completed')

    // 步骤5：AI分析（如果有的话）
    if (response.data.analysis) {
      updateStep(4, 'active')
      await new Promise(r => setTimeout(r, 300))
      updateStep(4, 'completed')
    }

  } catch (error) {
    console.error('分析失败:', error)
    alert('分析失败: ' + (error.response?.data?.error || error.message))
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  Object.keys(chartConfigs.value).forEach(key => {
    const chartEl = chartRefs.value[key]
    if (!chartEl) return

    const config = chartConfigs.value[key]
    const chart = echarts.init(chartEl)

    let option = {}
    const chartData = config.data

    if (config.type === 'pie') {
      option = {
        tooltip: { trigger: 'item' },
        legend: { type: 'scroll', bottom: 0 },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: chartData.data || chartData,
          label: { show: false }
        }]
      }
    } else if (config.type === 'bar') {
      const data = chartData.data || chartData
      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.categories || data.map((_, i) => i + 1), axisLabel: { rotate: 45 } },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: data.values || data }]
      }
    } else if (config.type === 'line') {
      const data = chartData.data || chartData
      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.categories || data.map((_, i) => i + 1) },
        yAxis: { type: 'value' },
        series: [{ type: 'line', data: data.values || data, smooth: true }]
      }
    }

    chart.setOption(option)
  })
}

async function runAnalysisV2() {
  if (!selectedTableV2.value || !analysisPrompt.value) return

  loadingV2.value = true
  analysisV2Result.value = null

  try {
    const response = await axios.post('/api/analyze-v2', {
      table_name: selectedTableV2.value,
      prompt: analysisPrompt.value,
      model: selectedModel.value
    })
    analysisV2Result.value = response.data

    await nextTick()
    renderV2Charts()
  } catch (error) {
    console.error('分析失败:', error)
    alert('分析失败: ' + (error.response?.data?.error || error.message))
  } finally {
    loadingV2.value = false
  }
}

function renderV2Charts() {
  if (!analysisV2Result.value?.charts) return

  analysisV2Result.value.charts.forEach((chart, index) => {
    if (chart.type === 'image') return

    const chartEl = chartV2Refs.value[index]
    if (!chartEl) return

    const echartsChart = echarts.init(chartEl)
    // 根据图表数据渲染
    echartsChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: chart.type || 'pie',
        data: chart.data
      }]
    })
  })
}

function copyReport() {
  if (analysisV2Result.value?.report) {
    navigator.clipboard.writeText(analysisV2Result.value.report)
    alert('报告已复制到剪贴板')
  }
}

async function runChartAnalysis() {
  if (!chartTable.value) return

  chartLoading.value = true
  chartResult.value = null

  try {
    const response = await axios.post('/api/chart-analysis', {
      table_name: chartTable.value,
      month: chartMonth.value
    })
    chartResult.value = response.data

    await nextTick()
    renderDashboardCharts()
  } catch (error) {
    console.error('图表分析失败:', error)
    alert('图表分析失败: ' + (error.response?.data?.error || error.message))
  } finally {
    chartLoading.value = false
  }
}

function renderDashboardCharts() {
  if (!chartResult.value?.charts) return

  Object.keys(chartResult.value.charts).forEach(key => {
    const chartEl = dashboardChartRefs.value[key]
    if (!chartEl) return

    const chartData = chartResult.value.charts[key]
    const chart = echarts.init(chartEl)

    let option = {}
    if (chartData.type === 'pie') {
      option = {
        tooltip: { trigger: 'item' },
        legend: { type: 'scroll', bottom: 0 },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: chartData.data,
          label: { show: false }
        }]
      }
    } else if (chartData.type === 'bar') {
      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: chartData.data.map(d => d.name), axisLabel: { rotate: 45, interval: 0 } },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: chartData.data.map(d => d.value) }]
      }
    }

    chart.setOption(option)
  })
}

async function handleSpotcheckFile(e) {
  const file = e.target.files[0]
  if (!file) return

  spotcheckLoading.value = true
  spotcheckResult.value = null

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/spotcheck', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000
    })
    spotcheckResult.value = response.data
  } catch (error) {
    console.error('案件抽查失败:', error)
    alert('分析失败: ' + (error.response?.data?.error || error.message))
  } finally {
    spotcheckLoading.value = false
    e.target.value = ''
  }
}

// 监听数据表选择，获取月份
watch(selectedTable, async (table) => {
  if (table) {
    availableMonths.value = await fetchAvailableMonths(table)
  }
})

watch(chartTable, async (table) => {
  if (table) {
    chartAvailableMonths.value = await fetchAvailableMonths(table)
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

.config-section {
  max-width: 800px;
  margin: 0 auto;
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
  margin-bottom: var(--space-2);
  font-weight: 500;
  color: var(--text-primary);
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

.month-select {
  max-width: 200px;
}

.form-textarea {
  width: 100%;
  padding: var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  resize: vertical;
  min-height: 100px;
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

.btn-secondary {
  background: var(--bg-card);
  color: var(--text-primary);
  border-color: var(--border-lighter);
}

.btn-block {
  width: 100%;
}

.btn-sm {
  padding: var(--space-1) var(--space-3);
  font-size: 12px;
}

.progress-section {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.progress-title {
  font-weight: 600;
  color: var(--primary-500);
  margin-bottom: var(--space-4);
}

.progress-step {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2);
  margin-bottom: var(--space-2);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.progress-step.pending { opacity: 0.5; }
.progress-step.active { background: var(--primary-50); }
.progress-step.completed { background: rgba(103, 194, 58, 0.1); }

.step-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.pending .step-icon { background: var(--neutral-200); color: var(--text-tertiary); }
.active .step-icon { background: var(--primary-500); color: white; }
.completed .step-icon { background: #67c23a; color: white; }

.step-text {
  font-size: 14px;
  color: var(--text-secondary);
}

.active .step-text { color: var(--primary-500); font-weight: 500; }

.progress-bar {
  height: 4px;
  background: var(--neutral-200);
  border-radius: 2px;
  overflow: hidden;
  margin-top: var(--space-4);
}

.progress-fill {
  height: 100%;
  background: var(--primary-500);
  transition: width 0.3s ease;
}

.result-section {
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid var(--border-lighter);
}

.result-header {
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 2px solid var(--primary-500);
}

.result-header h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.result-header p {
  color: var(--text-secondary);
  margin: 0;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.chart-card {
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.chart-card h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.chart-container {
  height: 300px;
}

.chart-image {
  text-align: center;
}

.chart-image img {
  max-width: 100%;
  max-height: 300px;
  border-radius: var(--radius-sm);
}

.ai-result {
  padding: var(--space-6);
  background: linear-gradient(135deg, var(--primary-50) 0%, var(--bg-secondary) 100%);
  border-radius: var(--radius-lg);
  border-left: 4px solid var(--primary-500);
}

.ai-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.ai-icon {
  font-size: 24px;
}

.ai-header h4 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
}

.ai-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-8);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.upload-area:hover {
  border-color: var(--primary-400);
  background: var(--fill-light);
}

.upload-icon {
  font-size: 48px;
  margin-bottom: var(--space-2);
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.upload-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8);
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spotcheck-result {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.spotcheck-result h4 {
  margin: 0 0 var(--space-4);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.result-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.dashboard {
  margin-top: var(--space-6);
}

.dashboard-header {
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 2px solid var(--primary-500);
}

.dashboard-header h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.dashboard-header p {
  color: var(--text-secondary);
  margin: 0;
}

.dashboard-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: var(--space-4);
}

.dashboard-chart {
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.dashboard-chart h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .charts-grid,
  .dashboard-charts {
    grid-template-columns: 1fr;
  }
}
</style>