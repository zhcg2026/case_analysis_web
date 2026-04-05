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
      <!-- 模块说明 -->
      <div class="module-guide">
        <div class="guide-header" @click="guideExpanded.analysis = !guideExpanded.analysis">
          <span class="guide-icon">📋</span>
          <span class="guide-title">功能说明</span>
          <span class="guide-toggle">{{ guideExpanded.analysis ? '收起' : '展开' }}</span>
        </div>
        <div v-if="guideExpanded.analysis" class="guide-content">
          <p><strong>数据分析</strong>模块提供预设的分析类型，快速生成专业分析报告。</p>
          <div class="guide-steps">
            <div class="guide-step"><span class="step-num">1</span>选择要分析的数据表</div>
            <div class="guide-step"><span class="step-num">2</span>选择分析类型（时间/空间/来源/类型/重复案件）</div>
            <div class="guide-step"><span class="step-num">3</span>点击开始分析，等待AI生成报告</div>
          </div>
          <div class="guide-tips">
            <strong>分析类型说明：</strong>
            <span>时间分析-案件时间趋势</span>
            <span>空间分析-区域分布</span>
            <span>来源分析-来源渠道</span>
            <span>类型分析-案件类型分布</span>
            <span>重复案件-重复投诉识别</span>
          </div>
        </div>
      </div>

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
            <span class="ai-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 8V4H8"/>
                <rect width="16" height="12" x="4" y="8" rx="2"/>
                <path d="M2 14h2"/>
                <path d="M20 14h2"/>
                <path d="M15 13v2"/>
                <path d="M9 13v2"/>
              </svg>
            </span>
            <h4>AI智能分析</h4>
          </div>
          <div class="ai-content" v-html="formatAnalysis(analysisResult.analysis)"></div>
        </div>
      </div>
    </div>

    <!-- 数据分析V2 -->
    <div v-else-if="activeTab === 'analysis-v2'" class="content-card">
      <!-- 模块说明 -->
      <div class="module-guide">
        <div class="guide-header" @click="guideExpanded.analysisV2 = !guideExpanded.analysisV2">
          <span class="guide-icon">🤖</span>
          <span class="guide-title">功能说明</span>
          <span class="guide-toggle">{{ guideExpanded.analysisV2 ? '收起' : '展开' }}</span>
        </div>
        <div v-if="guideExpanded.analysisV2" class="guide-content">
          <p><strong>数据分析V2</strong>支持自由输入分析需求，AI将根据您的提示词进行智能分析。</p>
          <div class="guide-steps">
            <div class="guide-step"><span class="step-num">1</span>选择数据表</div>
            <div class="guide-step"><span class="step-num">2</span>选择大模型（豆包/通义千问）</div>
            <div class="guide-step"><span class="step-num">3</span>输入分析需求，如"分析案件来源分布情况"</div>
            <div class="guide-step"><span class="step-num">4</span>点击开始分析</div>
          </div>
          <div class="guide-tips">
            <strong>提示词示例：</strong>
            <span>"分析各街道案件数量排名"</span>
            <span>"统计各类型案件的平均处理时长"</span>
            <span>"找出重复投诉次数最多的地址"</span>
          </div>
        </div>
      </div>

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
            <div v-else :ref="el => { if (el) chartV2Refs[index] = el }" class="chart-container"></div>
          </div>
        </div>

        <!-- 分析报告 -->
        <div v-if="analysisV2Result.report" class="ai-result">
          <div class="ai-header">
            <span class="ai-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 8V4H8"/>
                <rect width="16" height="12" x="4" y="8" rx="2"/>
                <path d="M2 14h2"/>
                <path d="M20 14h2"/>
                <path d="M15 13v2"/>
                <path d="M9 13v2"/>
              </svg>
            </span>
            <h4>AI智能分析报告</h4>
            <button class="btn btn-secondary btn-sm" @click="copyReport">复制报告</button>
          </div>
          <div class="ai-content" v-html="formatAnalysis(analysisV2Result.report)"></div>
        </div>
      </div>
    </div>

    <!-- 智能报告 -->
    <div v-else-if="activeTab === 'smart-report'" class="content-card">
      <!-- 模块说明 -->
      <div class="module-guide">
        <div class="guide-header" @click="guideExpanded.smartReport = !guideExpanded.smartReport">
          <span class="guide-icon">📊</span>
          <span class="guide-title">功能说明</span>
          <span class="guide-toggle">{{ guideExpanded.smartReport ? '收起' : '展开' }}</span>
        </div>
        <div v-if="guideExpanded.smartReport" class="guide-content">
          <p><strong>智能报告</strong>模块根据模板生成可视化分析报告，支持导出为视频报告。</p>
          <div class="guide-steps">
            <div class="guide-step"><span class="step-num">1</span>选择数据表和分析模板</div>
            <div class="guide-step"><span class="step-num">2</span>设置筛选条件（月份/年份/维度）</div>
            <div class="guide-step"><span class="step-num">3</span>点击"生成报告"查看HTML报告</div>
            <div class="guide-step"><span class="step-num">4</span>点击"生成视频报告"下载MP4视频</div>
          </div>
          <div class="guide-tips">
            <strong>模板类型：</strong>
            <span>月度对比-对比两个月数据变化</span>
            <span>年度总结-年度数据汇总分析</span>
            <span>专项分析-特定维度深入分析</span>
            <span>全量分析-全部数据综合分析</span>
          </div>
        </div>
      </div>

      <div class="config-section">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">选择数据表</label>
            <select v-model="reportTable" class="form-select" :disabled="reportLoading">
              <option value="">请选择</option>
              <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">分析模板</label>
            <select v-model="reportTemplate" class="form-select" :disabled="reportLoading">
              <option v-for="t in reportTemplates" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
        </div>

        <!-- 月度对比参数 -->
        <div v-if="reportTemplate === 'monthly_comparison'" class="param-section">
          <label class="form-label">选择对比月份（可多选）</label>
          <div class="checkbox-group">
            <label v-for="month in reportAvailableMonths" :key="month" class="checkbox-item">
              <input type="checkbox" :value="month" v-model="reportMonths" :disabled="reportLoading">
              <span>{{ formatMonth(month) }}</span>
            </label>
          </div>
          <div v-if="reportMonths.length > 0" class="selected-info">
            已选择: {{ reportMonths.map(m => formatMonth(m)).join('、') }}
          </div>
        </div>

        <!-- 年度总结参数 -->
        <div v-else-if="reportTemplate === 'yearly_summary'" class="param-section">
          <label class="form-label">选择年份</label>
          <select v-model="reportYear" class="form-select" :disabled="reportLoading">
            <option value="">请选择</option>
            <option value="2026">2026年</option>
            <option value="2025">2025年</option>
          </select>
        </div>

        <!-- 专项分析参数 -->
        <div v-else-if="reportTemplate === 'special_analysis'" class="param-section">
          <div class="form-group">
            <label class="form-label">分析维度</label>
            <select v-model="reportDimension" class="form-select" :disabled="reportLoading">
              <option value="">请选择维度</option>
              <option v-for="opt in reportDimensionOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div v-if="reportDimension" class="form-group">
            <label class="form-label">选择类型（可多选）</label>
            <div class="checkbox-group scrollable">
              <label v-for="opt in reportDimensionValueOptions" :key="opt.value" class="checkbox-item">
                <input type="checkbox" :value="opt.value" v-model="reportDimensionValues" :disabled="reportLoading">
                <span>{{ opt.label }}</span>
              </label>
            </div>
            <div v-if="reportDimensionValues.length > 0" class="selected-info">
              已选择: {{ reportDimensionValues.join('、') }}
            </div>
          </div>
        </div>

        <button class="btn btn-primary btn-block" @click="generateSmartReport" :disabled="reportLoading || !reportTable">
          {{ reportLoading ? '生成中...' : '一键生成精美报告' }}
        </button>

        <!-- 报告生成成功后显示操作按钮 -->
        <div v-if="reportDataUrl" class="report-actions">
          <button class="btn btn-success" @click="openReport">
            查看报告
          </button>
          <button class="btn btn-info" @click="generateVideoReport" :disabled="videoLoading">
            {{ videoLoading ? '生成中...' : '生成视频报告' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 图表分析 -->
    <div v-else-if="activeTab === 'chart'" class="content-card">
      <!-- 模块说明 -->
      <div class="module-guide">
        <div class="guide-header" @click="guideExpanded.chart = !guideExpanded.chart">
          <span class="guide-icon">📈</span>
          <span class="guide-title">功能说明</span>
          <span class="guide-toggle">{{ guideExpanded.chart ? '收起' : '展开' }}</span>
        </div>
        <div v-if="guideExpanded.chart" class="guide-content">
          <p><strong>图表分析</strong>模块快速生成数据可视化仪表盘，直观展示数据分布。</p>
          <div class="guide-steps">
            <div class="guide-step"><span class="step-num">1</span>选择数据表</div>
            <div class="guide-step"><span class="step-num">2</span>可选择特定月份或全部月份</div>
            <div class="guide-step"><span class="step-num">3</span>点击"生成仪表盘"查看可视化图表</div>
          </div>
          <div class="guide-tips">
            <strong>生成内容：</strong>
            <span>案件总量统计</span>
            <span>结案率分析</span>
            <span>问题类型分布</span>
            <span>片区/街道分布</span>
            <span>问题来源分析</span>
          </div>
        </div>
      </div>

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
          <p>共 {{ chartResult.filtered_count || chartResult.total_count }} 条数据{{ chartResult.month ? `（${formatMonth(chartResult.month)}）` : '' }}</p>
        </div>

        <div class="dashboard-charts">
          <div v-for="(chart, key) in chartResult.charts" :key="key" class="dashboard-chart">
            <h4>{{ chart.title }}</h4>
            <div :ref="el => setDashboardChartRef(key, el)" class="chart-container"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 案件抽查 -->
    <div v-else-if="activeTab === 'spotcheck'" class="content-card">
      <!-- 模块说明 -->
      <div class="module-guide">
        <div class="guide-header" @click="guideExpanded.spotcheck = !guideExpanded.spotcheck">
          <span class="guide-icon">🔍</span>
          <span class="guide-title">功能说明</span>
          <span class="guide-toggle">{{ guideExpanded.spotcheck ? '收起' : '展开' }}</span>
        </div>
        <div v-if="guideExpanded.spotcheck" class="guide-content">
          <p><strong>案件抽查</strong>模块对案件全流程质量进行分析，评估处置规范性并给出评价意见。</p>
          <div class="guide-steps">
            <div class="guide-step"><span class="step-num">1</span>上传案件文件（支持.docx、.xlsx格式）</div>
            <div class="guide-step"><span class="step-num">2</span>点击"开始分析"</div>
            <div class="guide-step"><span class="step-num">3</span>查看全流程质量评价和改进建议</div>
          </div>
          <div class="guide-tips">
            <strong>评估内容：</strong>
            <span>案件受理规范性</span>
            <span>处置流程合规性</span>
            <span>办理时效评价</span>
            <span>结果满意度分析</span>
            <span>改进建议</span>
          </div>
        </div>
      </div>

      <div class="config-section">
        <div class="form-group">
          <label class="form-label">上传案件文件</label>
          <div class="file-upload-row">
            <input ref="spotcheckFile" type="file" accept=".docx,.xlsx" @change="onSpotcheckFileSelect" hidden />
            <button class="btn btn-secondary" @click="$refs.spotcheckFile.click()">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              选择文件
            </button>
            <span v-if="spotcheckFileName" class="file-name">{{ spotcheckFileName }}</span>
            <span v-else class="file-hint">支持 .docx、.xlsx 格式</span>
          </div>
        </div>

        <button class="btn btn-primary btn-block" @click="runSpotcheck" :disabled="spotcheckLoading || !spotcheckFileName">
          {{ spotcheckLoading ? '分析中...' : '开始分析' }}
        </button>

        <div v-if="spotcheckLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>AI分析中，请稍候...</span>
        </div>

        <div v-if="spotcheckResult" class="result-section">
          <h3 class="result-title">分析结果</h3>
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
  { key: 'smart-report', label: '智能报告' },
  { key: 'chart', label: '图表分析' },
  { key: 'spotcheck', label: '案件抽查' }
]

const activeTab = ref('analysis')
const tables = ref([])

// 模块说明展开状态
const guideExpanded = ref({
  analysis: false,
  analysisV2: false,
  smartReport: true,  // 智能报告默认展开
  chart: false,
  spotcheck: false
})

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
  { value: 'duplicate_analysis', label: '重复案件分析' }
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
  }
  return configs
})

// ===== 数据分析V2 =====
const selectedTableV2 = ref('')
const selectedModel = ref('volcengine')
const analysisPrompt = ref('')
const loadingV2 = ref(false)
const analysisV2Result = ref(null)
const chartV2Refs = ref([])

// ===== 图表分析 =====
const chartTable = ref('')
const chartMonth = ref('')
const chartLoading = ref(false)
const chartResult = ref(null)
const chartAvailableMonths = ref([])
const dashboardChartRefs = ref({})

// ===== 案件抽查 =====
const spotcheckFile = ref(null)
const spotcheckFileName = ref('')
const spotcheckLoading = ref(false)
const spotcheckResult = ref(null)

// ===== 智能报告 =====
const reportTable = ref('')
const reportTemplate = ref('monthly_comparison')
const reportMonths = ref([])
const reportYear = ref('')
const reportDimension = ref('')
const reportDimensionValues = ref([])
const reportLoading = ref(false)
const reportDataUrl = ref('')  // 存储生成的报告URL
const reportAvailableMonths = ref([])
const reportAvailableYears = ref([])
const reportDimensionOptions = ref([])
const reportDimensionValueOptions = ref([])
const videoLoading = ref(false)  // 视频报告生成状态

const reportTemplates = [
  { value: 'monthly_comparison', label: '月度对比' },
  { value: 'yearly_summary', label: '年度总结' },
  { value: 'special_analysis', label: '专项分析' },
  { value: 'full_analysis', label: '全量分析' }
]

// ===== 方法定义 =====

// 设置图表 ref 的辅助函数
function setDashboardChartRef(key, el) {
  if (el) {
    dashboardChartRefs.value[key] = el
  }
}

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
    const response = await axios.get(`/api/available-months?table_name=${tableName}`)
    return response.data.months || []
  } catch (error) {
    console.error('获取月份列表失败:', error)
    return []
  }
}

function formatMonth(month) {
  if (!month || month.length < 6) return month || ''
  const year = month.substring(0, 4)
  const m = month.substring(4, 6)
  return `${year}年${m}月`
}

function getAnalysisTypeName(type) {
  const map = {
    time_analysis: '时间分析',
    space_analysis: '空间分析',
    source_analysis: '来源分析',
    type_analysis: '类型分析',
    duplicate_analysis: '重复案件分析'
  }
  return map[type] || type
}

function formatAnalysis(text) {
  if (!text) return ''

  let formatted = text

  // 处理markdown标题，转换为带样式的HTML（统一字体大小）
  formatted = formatted.replace(/^#{1,6}\s+(.+)$/gm, '<strong style="display:block;margin-top:12px;margin-bottom:4px;">$1</strong>')

  // 去除粗体符号 (**)
  formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // 去除斜体符号 (*)
  formatted = formatted.replace(/\*([^*]+)\*/g, '$1')

  // 去除列表符号 (- 开头)
  formatted = formatted.replace(/^[-•]\s*/gm, '• ')

  // 减少多余空行（连续多个换行变成最多两个）
  formatted = formatted.replace(/\n{3,}/g, '\n\n')

  // 处理换行
  formatted = formatted.replace(/\n/g, '<br>')

  // 去除连续多个<br>
  formatted = formatted.replace(/(<br>){3,}/g, '<br><br>')

  return formatted
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

    console.log(`渲染图表 ${key}, 类型: ${config.type}, 数据:`, chartData)

    if (config.type === 'pie') {
      // 处理饼图数据格式
      let pieData = []
      if (Array.isArray(chartData)) {
        // 数据格式: [{字段名: "xxx", count: 100}, ...]
        pieData = chartData.map(item => {
          // 找到第一个不是 count 的字段作为 name
          const nameKey = Object.keys(item).find(k => k !== 'count')
          return {
            name: item[nameKey] || '未知',
            value: item.count || 0
          }
        })
      } else if (chartData.data && Array.isArray(chartData.data)) {
        pieData = chartData.data
      }

      option = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { type: 'scroll', bottom: 0 },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          data: pieData,
          label: { show: false }
        }]
      }
    } else if (config.type === 'bar') {
      // 处理柱状图数据格式
      let categories = []
      let values = []

      if (Array.isArray(chartData)) {
        // 数据格式: [{字段名: "xxx", count: 100}, ...]
        categories = chartData.map(item => {
          const nameKey = Object.keys(item).find(k => k !== 'count')
          return item[nameKey] || ''
        })
        values = chartData.map(item => item.count || 0)
      } else if (chartData.data) {
        const data = chartData.data
        categories = data.categories || data.map((_, i) => i + 1)
        values = data.values || data
      } else {
        categories = chartData.categories || chartData.map((_, i) => i + 1)
        values = chartData.values || chartData
      }

      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: categories, axisLabel: { rotate: 45, interval: 0 } },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: values }]
      }
    } else if (config.type === 'line') {
      // 处理折线图数据格式
      let categories = []
      let values = []

      if (Array.isArray(chartData)) {
        categories = chartData.map(item => {
          const nameKey = Object.keys(item).find(k => k !== 'count')
          return item[nameKey] || ''
        })
        values = chartData.map(item => item.count || 0)
      } else if (chartData.data) {
        const data = chartData.data
        categories = data.categories || data.map((_, i) => i + 1)
        values = data.values || data
      } else {
        categories = chartData.categories || chartData.map((_, i) => i + 1)
        values = chartData.values || chartData
      }

      option = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: categories },
        yAxis: { type: 'value' },
        series: [{ type: 'line', data: values, smooth: true }]
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

    // 等待 DOM 更新后渲染图表
    await nextTick()
    setTimeout(() => {
      renderV2Charts()
    }, 100)
  } catch (error) {
    console.error('分析失败:', error)
    console.error('错误详情:', error.response?.data)
    const errorMsg = error.response?.data?.error || error.message || '未知错误'
    alert('分析失败: ' + errorMsg + (error.response?.data?.details ? '\n' + error.response?.data?.details : ''))
  } finally {
    loadingV2.value = false
  }
}

function renderV2Charts() {
  if (!analysisV2Result.value?.charts) return

  console.log('开始渲染图表，图表数量:', analysisV2Result.value.charts.length)
  console.log('图表数据:', JSON.stringify(analysisV2Result.value.charts, null, 2))

  analysisV2Result.value.charts.forEach((chart, index) => {
    if (chart.type === 'image') return

    const chartEl = chartV2Refs.value[index]
    console.log(`图表 ${index} 元素:`, chartEl, '类型:', chart.type)

    if (!chartEl) {
      console.log(`图表元素 ${index} 未找到`)
      return
    }

    try {
      const echartsChart = echarts.init(chartEl)

      if (chart.type === 'echarts' && chart.data) {
        console.log(`图表 ${index} 完整数据:`, JSON.stringify(chart.data, null, 2))

        // 确保 series 存在且 data 是数组
        if (chart.data.series && Array.isArray(chart.data.series)) {
          chart.data.series.forEach((s, i) => {
            if (!Array.isArray(s.data)) {
              console.warn(`图表 ${index} series[${i}].data 不是数组:`, s.data)
            }
          })
        }

        echartsChart.setOption(chart.data)
      } else if (chart.data) {
        // 兼容旧格式
        echartsChart.setOption({
          tooltip: { trigger: 'item' },
          legend: { bottom: 0 },
          series: [{
            type: 'pie',
            data: Array.isArray(chart.data) ? chart.data : []
          }]
        })
      }
    } catch (error) {
      console.error('渲染图表失败:', error)
    }
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
  dashboardChartRefs.value = {} // 清空旧的 refs

  try {
    const response = await axios.post('/api/chart-analysis', {
      table_name: chartTable.value,
      month: chartMonth.value
    })
    chartResult.value = response.data

    console.log('图表分析结果:', response.data)
    console.log('图表数量:', Object.keys(response.data.charts || {}).length)

    // 使用更长的延迟确保 DOM 完全渲染
    await nextTick()
    setTimeout(() => {
      renderDashboardCharts()
    }, 200)
  } catch (error) {
    console.error('图表分析失败:', error)
    alert('图表分析失败: ' + (error.response?.data?.error || error.message))
  } finally {
    chartLoading.value = false
  }
}

function renderDashboardCharts() {
  if (!chartResult.value?.charts) {
    console.log('没有图表数据')
    return
  }

  const charts = chartResult.value.charts
  console.log('开始渲染仪表盘图表，图表数量:', Object.keys(charts).length)
  console.log('图表 keys:', Object.keys(charts))
  console.log('图表 refs:', dashboardChartRefs.value)

  Object.keys(charts).forEach(key => {
    console.log(`处理图表 ${key}...`)
    const chartEl = dashboardChartRefs.value[key]
    console.log(`图表 ${key} 元素:`, chartEl)

    if (!chartEl) {
      console.warn(`图表元素 ${key} 未找到`)
      return
    }

    const chartData = charts[key]
    console.log(`图表 ${key} 数据:`, chartData)

    if (!chartData || !chartData.data) {
      console.warn(`图表 ${key} 没有数据`)
      return
    }

    try {
      const chart = echarts.init(chartEl)
      let option = {}

      if (chartData.type === 'pie') {
        // 饼图数据格式: [{name: "xxx", value: 100}, ...]
        const pieData = Array.isArray(chartData.data) ? chartData.data : []
        console.log(`图表 ${key} 饼图数据条数:`, pieData.length)
        option = {
          tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
          legend: { type: 'scroll', bottom: 0 },
          series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            data: pieData,
            label: { show: false }
          }]
        }
      } else if (chartData.type === 'bar') {
        // 柱状图数据格式: {categories: [...], values: [...]}
        const categories = chartData.data?.categories || []
        const values = chartData.data?.values || []
        console.log(`图表 ${key} 柱状图数据:`, categories.length, '个分类')

        option = {
          tooltip: { trigger: 'axis' },
          xAxis: {
            type: 'category',
            data: categories,
            axisLabel: {
              rotate: categories.length > 5 ? 45 : 0,
              interval: 0,
              fontSize: 10
            }
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'bar',
            data: values,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#4facfe' },
                { offset: 1, color: '#00f2fe' }
              ])
            }
          }],
          grid: {
            left: '3%',
            right: '4%',
            bottom: categories.length > 5 ? '15%' : '3%',
            containLabel: true
          }
        }
      }

      chart.setOption(option)
      console.log(`图表 ${key} 渲染完成`)
    } catch (error) {
      console.error(`渲染图表 ${key} 失败:`, error)
    }
  })
}

function onSpotcheckFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  spotcheckFile.value = file
  spotcheckFileName.value = file.name
  spotcheckResult.value = null
}

async function runSpotcheck() {
  if (!spotcheckFile.value) {
    alert('请先选择文件')
    return
  }

  spotcheckLoading.value = true
  spotcheckResult.value = null

  const formData = new FormData()
  formData.append('file', spotcheckFile.value)

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

// ===== 智能报告方法 =====
async function onReportTableChange() {
  if (!reportTable.value) return

  // 获取月份列表
  reportAvailableMonths.value = await fetchAvailableMonths(reportTable.value)

  // 获取年份列表（从数据中提取）
  try {
    const response = await axios.get(`/api/table-columns?table_name=${reportTable.value}`)
    const columns = response.data.columns || []

    // 查找维度字段
    reportDimensionOptions.value = columns.filter(col =>
      ['大类名称', '小类名称', '所属片区', '问题来源', '处置部门', '所属街道'].includes(col)
    ).map(col => ({ value: col, label: col }))
  } catch (error) {
    console.error('获取表字段失败:', error)
  }
}

async function onReportDimensionChange() {
  if (!reportTable.value || !reportDimension.value) {
    reportDimensionValueOptions.value = []
    return
  }

  try {
    const response = await axios.get(`/api/column-values?table_name=${reportTable.value}&column=${reportDimension.value}`)
    reportDimensionValueOptions.value = (response.data.values || []).map(v => ({ value: v, label: v }))
  } catch (error) {
    console.error('获取字段值失败:', error)
    reportDimensionValueOptions.value = []
  }
}

async function generateSmartReport() {
  if (!reportTable.value) {
    alert('请选择数据表')
    return
  }

  reportLoading.value = true
  reportDataUrl.value = ''

  try {
    const response = await axios.post('/api/smart-report', {
      table_name: reportTable.value,
      template_type: reportTemplate.value,
      months: reportMonths.value,
      year: reportYear.value,
      dimension: reportDimension.value,
      dimension_values: reportDimensionValues.value
    })

    // 存储报告HTML，显示查看按钮
    const blob = new Blob([response.data.html], { type: 'text/html' })
    reportDataUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    console.error('生成报告失败:', error)
    alert('生成报告失败: ' + (error.response?.data?.error || error.message))
  } finally {
    reportLoading.value = false
  }
}

function openReport() {
  if (reportDataUrl.value) {
    window.open(reportDataUrl.value, '_blank')
  }
}

async function generateVideoReport() {
  if (!reportTable.value) {
    alert('请先选择数据表')
    return
  }

  videoLoading.value = true

  try {
    const response = await axios.post('/api/video-report', {
      table_name: reportTable.value,
      template_type: reportTemplate.value,
      months: reportMonths.value,
      year: reportYear.value,
      dimension: reportDimension.value,
      dimension_values: reportDimensionValues.value
    }, { responseType: 'blob' })

    // 下载视频文件
    const url = URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'report_video.mp4'
    a.click()
    URL.revokeObjectURL(url)

    alert('视频报告已生成并开始下载')
  } catch (error) {
    console.error('生成视频报告失败:', error)
    // 尝试读取错误详情
    if (error.response?.data) {
      try {
        const text = await error.response.data.text()
        const errData = JSON.parse(text)
        alert('生成视频报告失败: ' + (errData.error || errData.traceback?.split('\n')[0] || error.message))
      } catch {
        alert('生成视频报告失败: ' + error.message)
      }
    } else {
      alert('生成视频报告失败: ' + error.message)
    }
  } finally {
    videoLoading.value = false
  }
}

watch(reportTable, onReportTableChange)
watch(reportDimension, onReportDimensionChange)

// 切换模板类型时清空已生成的报告
watch(reportTemplate, () => {
  reportDataUrl.value = ''
  reportMonths.value = []
  reportYear.value = ''
  reportDimension.value = ''
  reportDimensionValues.value = []
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
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border-left: 4px solid var(--primary-500);
}

.ai-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.ai-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--primary-50);
  border-radius: var(--radius-md);
  color: var(--primary-500);
}

.ai-icon svg {
  width: 20px;
  height: 20px;
}

.ai-header h4 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
}

.ai-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}

.ai-content :deep(p) {
  margin: 0 0 var(--space-2);
}

.ai-content :deep(strong) {
  color: var(--primary-600);
  font-weight: 600;
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

.file-upload-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.file-hint {
  font-size: 13px;
  color: var(--text-tertiary);
}

.file-name {
  font-size: 14px;
  color: var(--primary-500);
  font-weight: 500;
}

.spotcheck-result,
.result-section {
  margin-top: var(--space-6);
  padding: var(--space-6);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
}

.spotcheck-result h4,
.result-section .result-title {
  margin: 0 0 var(--space-4);
  padding-bottom: var(--space-4);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 2px solid var(--primary-500);
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

/* 智能报告样式 */
.param-section {
  margin-top: var(--space-4);
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.checkbox-group.scrollable {
  max-height: 200px;
  overflow-y: auto;
  padding: var(--space-2);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-sm);
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-primary);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: all var(--transition-fast);
}

.checkbox-item:hover {
  border-color: var(--primary-400);
  background: var(--primary-50);
}

.checkbox-item input {
  accent-color: var(--primary-500);
}

.selected-info {
  margin-top: var(--space-2);
  font-size: 13px;
  color: var(--primary-500);
  font-weight: 500;
}

.report-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.btn-success {
  background: #27ae60;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #219a52;
}

.btn-info {
  background: #3498db;
  color: white;
}

.btn-info:hover:not(:disabled) {
  background: #2980b9;
}

.report-section {
  margin-top: var(--space-6);
  border-top: 1px solid var(--border-lighter);
  padding-top: var(--space-6);
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.report-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.report-iframe {
  width: 100%;
  height: 800px;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  background: white;
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

/* 模块说明样式 */
.module-guide {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-6);
  overflow: hidden;
}

.guide-header {
  display: flex;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  transition: background 0.2s;
}

.guide-header:hover {
  background: rgba(59, 130, 246, 0.05);
}

.guide-icon {
  font-size: 20px;
  margin-right: var(--space-3);
}

.guide-title {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.guide-toggle {
  font-size: 13px;
  color: var(--primary-500);
  padding: 2px 8px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 4px;
}

.guide-content {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid #e2e8f0;
  background: white;
}

.guide-content p {
  margin: 0 0 var(--space-4);
  color: var(--text-secondary);
  font-size: 14px;
}

.guide-steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.guide-step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-secondary);
  background: #f8fafc;
  padding: 6px 12px;
  border-radius: 6px;
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--primary-500);
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
}

.guide-tips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px dashed #e2e8f0;
}

.guide-tips strong {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: var(--space-2);
}

.guide-tips span {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 3px 10px;
  border-radius: 12px;
}
</style>