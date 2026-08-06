<template>
  <div class="report-page">
    <header class="report-header">
      <button class="btn-back" @click="$router.back()">
        ← 返回
      </button>
      <div class="report-header-info">
        <h1 class="report-title">{{ reportName }}</h1>
        <span class="report-type-badge" :class="reportType">
          {{ reportType === 'compare' ? '对比报告' : '单月报告' }}
        </span>
      </div>
      <div class="report-header-actions">
        <select v-model="selectedMonth" class="month-select" v-if="months.length > 0">
          <option value="">所有月份</option>
          <option v-for="m in months" :key="m.batch" :value="m.batch">
            {{ formatBatch(m.batch) }} ({{ m.count }}条)
          </option>
        </select>
        <button class="btn btn-primary" @click="exportWord" :disabled="exporting">
          {{ exporting ? '导出中...' : '导出Word' }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>正在生成分析报告，请稍候...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadAndExecute">重试</button>
    </div>

    <div v-else class="report-content">
      <div v-for="(result, idx) in results" :key="idx" class="report-section">
        <h2 class="section-title">{{ result.title }}</h2>
        <div class="section-answer" v-html="renderMarkdown(result.answer)"></div>
        <div v-if="result.chart" class="section-chart" :id="'report-chart-' + idx"></div>
        <div v-if="result.table_data && result.table_data.length" class="section-table-wrap">
          <table class="section-table">
            <thead>
              <tr>
                <th v-for="col in getTableColumns(result.table_data)" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in result.table_data.slice(0, 50)" :key="ri">
                <td v-for="col in getTableColumns(result.table_data)" :key="col"
                    :class="{ 'num-cell': isNumeric(row[col]) }">
                  {{ formatCellValue(row[col]) }}
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="result.table_data.length > 50" class="table-more">
            共 {{ result.table_data.length }} 条
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { chartTemplates, COLORS, fmtNum, getOrInitChart, disposeEcharts } from '../composables/useEcharts'
import { formatBatch, getTableColumns, isNumeric, formatCellValue, renderMarkdown } from '../utils/analysisFormat'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const reportName = ref('')
const reportType = ref('single')
const results = ref([])
const months = ref([])
const selectedMonth = ref('')
const exporting = ref(false)







async function loadMonths() {
  try {
    const res = await axios.get('/api/analysis/months')
    months.value = res.data.months || []
  } catch (e) {
    console.error('加载月份失败:', e)
  }
}

async function loadAndExecute() {
  loading.value = true
  error.value = ''
  try {
    const tid = route.params.id

    // 加载模板信息
    const tplRes = await axios.get(`/api/report-templates/${tid}`)
    reportName.value = tplRes.data.name
    reportType.value = tplRes.data.report_type

    // 执行模板
    const execPayload = {}
    if (selectedMonth.value) {
      execPayload.months = [selectedMonth.value]
    }

    const execRes = await axios.post(`/api/report-templates/${tid}/execute`, execPayload)
    if (execRes.data.success) {
      results.value = execRes.data.results || []
      await nextTick()
      renderAllCharts()
    } else {
      error.value = execRes.data.error || '执行失败'
    }
  } catch (e) {
    error.value = e.response?.data?.error || e.message
  } finally {
    loading.value = false
  }
}

function renderAllCharts() {
  results.value.forEach((result, idx) => {
    if (result.chart && result.chart.data && result.chart.data.length > 0) {
      const container = document.getElementById('report-chart-' + idx)
      if (!container) return

      const spec = result.chart
      const templateFn = chartTemplates[spec.chart_type] || chartTemplates.bar
      const option = templateFn(spec.title, spec.data, spec.x_field, spec.y_field)

      const chart = getOrInitChart(container, 'dark')
      chart.setOption(option)
    }
  })
}

async function exportWord() {
  exporting.value = true
  try {
    const tid = route.params.id
    const params = new URLSearchParams()
    if (selectedMonth.value) {
      params.set('months', selectedMonth.value)
    }
    const queryString = params.toString()
    const exportUrl = `/api/report-templates/${tid}/export${queryString ? '?' + queryString : ''}`
    const res = await axios.get(exportUrl, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${reportName.value}.docx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    let errorMsg = e.message
    if (e.response?.data) {
      try {
        const errorData = e.response.data instanceof Blob
          ? JSON.parse(await e.response.data.text())
          : e.response.data
        errorMsg = errorData.error || errorMsg
      } catch { /* use default message */ }
    }
    alert('导出失败: ' + errorMsg)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadMonths()
  loadAndExecute()
})

onUnmounted(() => {
  document.querySelectorAll('.message-chart, .section-chart').forEach(el => disposeEcharts(el))
})
</script>

<style scoped>
.report-page {
  min-height: 100vh;
  background: #0a1628;
  color: #e0e0e0;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 32px;
  background: rgba(13, 31, 60, 0.9);
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  position: sticky;
  top: 0;
  z-index: 100;
}

.btn-back {
  background: none;
  border: 1px solid rgba(64, 158, 255, 0.3);
  color: #409eff;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.btn-back:hover {
  background: rgba(64, 158, 255, 0.1);
  border-color: #409eff;
}

.report-header-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.report-type-badge {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 500;
}
.report-type-badge.single {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}
.report-type-badge.compare {
  background: rgba(251, 200, 88, 0.2);
  color: #fac858;
}

.report-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.month-select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #e0e0e0;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.month-select option {
  background: #1a2a4a;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 16px;
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(64, 158, 255, 0.2);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-state {
  text-align: center;
  padding: 60px 20px;
  color: #ef4444;
}

.report-content {
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.report-section {
  background: rgba(13, 31, 60, 0.5);
  border: 1px solid rgba(64, 158, 255, 0.1);
  border-radius: 12px;
  padding: 24px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
}

.section-answer {
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 16px;
}

.section-chart {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 16px;
}

.section-table-wrap {
  max-height: 400px;
  overflow-y: auto;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.section-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.section-table th {
  background: rgba(64, 158, 255, 0.12);
  color: rgba(255, 255, 255, 0.8);
  padding: 10px 14px;
  text-align: left;
  font-weight: 500;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.section-table td {
  padding: 8px 14px;
  color: rgba(255, 255, 255, 0.7);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.section-table tbody tr:nth-child(even) {
  background: rgba(255, 255, 255, 0.02);
}
.section-table tbody tr:hover {
  background: rgba(64, 158, 255, 0.06);
}
.section-table td.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.table-more {
  text-align: center;
  padding: 10px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
}
</style>
