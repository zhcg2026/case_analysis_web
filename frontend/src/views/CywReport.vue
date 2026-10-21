<template>
  <div class="cyw-report-tab">
    <div class="page-header">
      <div>
        <h2>数据统计</h2>
        <p class="page-sub">按单日或起止日期（连续几天、一周、一月）汇总案件派发与处置情况，支持一键导出 txt 供交接班与对账。</p>
      </div>
      <div class="report-actions">
        <el-radio-group v-model="mode" @change="onModeChange">
          <el-radio-button label="day">单日</el-radio-button>
          <el-radio-button label="range">时间段</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="mode === 'day'"
          v-model="date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          @change="load"
        />
        <el-date-picker
          v-else
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :shortcuts="rangeShortcuts"
          style="width: 260px"
          @change="load"
        />
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :loading="exporting" @click="exportTxt">导出 txt</el-button>
      </div>
    </div>

    <div class="stat-cards">
      <el-card shadow="never" class="stat-card">
        <div class="stat-num primary">{{ counts.new }}</div>
        <div class="stat-label">{{ isSingle ? '当日新增' : '周期新增' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num success">{{ counts.closed }}</div>
        <div class="stat-label">{{ isSingle ? '当日已办结' : '周期已办结' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num warning">{{ counts.doing }}</div>
        <div class="stat-label">{{ isSingle ? '处置中' : '周期末仍未办结' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num info">{{ counts.open_total }}</div>
        <div class="stat-label">当前未办结总数</div>
      </el-card>
    </div>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <div class="detail-title">
          <span>{{ isSingle ? '当日' : '周期内' }}新增明细</span>
          <span class="detail-count">{{ details.new.length }} 条</span>
        </div>
      </template>
      <el-table :data="details.new" border size="small" max-height="300">
        <el-table-column prop="case_no" label="案件编号" width="150" />
        <el-table-column prop="found_at" label="发现时间" :width="isSingle ? 80 : 110" />
        <el-table-column prop="monitor_no" label="监控序号" width="90" />
        <el-table-column prop="spot_name" label="点位" min-width="150" />
        <el-table-column prop="type_name" label="类型" width="90" />
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>
    </el-card>

    <div class="detail-grid">
      <el-card shadow="never" class="detail-card">
        <template #header>
          <div class="detail-title">
            <span>{{ isSingle ? '当日' : '周期内' }}已办结</span>
            <span class="detail-count">{{ details.closed.length }} 条</span>
          </div>
        </template>
        <el-table :data="details.closed" border size="small" max-height="300">
          <el-table-column prop="case_no" label="案件编号" width="150" />
          <el-table-column prop="spot_name" label="点位" min-width="130" />
          <el-table-column prop="type_name" label="类型" width="90" />
        </el-table>
      </el-card>

      <el-card shadow="never" class="detail-card">
        <template #header>
          <div class="detail-title">
            <span>{{ isSingle ? '处置中（截至当日 24:00 未办结）' : '处置中（截至周期末仍未办结）' }}</span>
            <span class="detail-count">{{ details.doing.length }} 条</span>
          </div>
        </template>
        <el-table :data="details.doing" border size="small" max-height="300">
          <el-table-column prop="case_no" label="案件编号" width="150" />
          <el-table-column prop="spot_name" label="点位" min-width="130" />
          <el-table-column prop="type_name" label="类型" width="90" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const pad = (n) => String(n).padStart(2, '0')
const dayText = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const today = () => dayText(new Date())
const shift = (days) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return dayText(d)
}

const mode = ref('day')
const date = ref(today())
const dateRange = ref([shift(-6), today()])
const rangeShortcuts = [
  { text: '最近7天', value: () => [shift(-6), today()] },
  { text: '最近30天', value: () => [shift(-29), today()] },
  { text: '本月', value: () => {
      const d = new Date()
      return [dayText(new Date(d.getFullYear(), d.getMonth(), 1)), today()]
    } },
  { text: '上月', value: () => {
      const d = new Date()
      return [dayText(new Date(d.getFullYear(), d.getMonth() - 1, 1)),
              dayText(new Date(d.getFullYear(), d.getMonth(), 0))]
    } },
]

// 文案口径跟随后端返回的 is_single：起止同一天时按单日展示，不自己判断
const isSingle = ref(true)
const counts = reactive({ new: 0, closed: 0, doing: 0, open_total: 0 })
const details = reactive({ new: [], closed: [], doing: [] })
const exporting = ref(false)

// 时间段模式才带 date_from/date_to，否则退回单日 date（旧行为）
const rangeParams = () => (mode.value === 'range' && dateRange.value?.length === 2
  ? { date_from: dateRange.value[0], date_to: dateRange.value[1] }
  : { date: date.value })

async function load() {
  try {
    const { data } = await axios.get('/api/cyw/report/daily', { params: rangeParams() })
    Object.assign(counts, data.counts || {})
    Object.assign(details, data.details || {})
    isSingle.value = data.is_single !== false
  } catch { /* error toast via interceptor */ }
}

function onModeChange() {
  if (mode.value === 'range' && dateRange.value?.length !== 2) {
    dateRange.value = [shift(-6), today()]
  }
  load()
}

// 优先用后端给的文件名：单日 _YYYYMMDD.txt，时间段 _YYYYMMDD-YYYYMMDD.txt
// 注意 ASCII 的 filename= 在前，必须先匹配 filename*=UTF-8''
function fileNameFromDisposition(header, fallback) {
  if (header) {
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header)
    if (utf8) {
      try {
        return decodeURIComponent(utf8[1])
      } catch { /* 落到兜底 */ }
    }
  }
  return fallback
}

// 走 blob 下载：后端返回的是带 BOM 的 UTF-8 文本，直接 window.open 会被浏览器当 HTML 渲染
async function exportTxt() {
  const params = rangeParams()
  const isRange = 'date_from' in params
  if (isRange && !(dateRange.value && dateRange.value[0] && dateRange.value[1])) {
    ElMessage.warning('请先选择起止日期')
    return
  }
  if (!isRange && !date.value) {
    ElMessage.warning('请先选择日期')
    return
  }
  const fallback = isRange
    ? `创文数据统计_${params.date_from.replace(/-/g, '')}-${params.date_to.replace(/-/g, '')}.txt`
    : `创文数据统计_${params.date.replace(/-/g, '')}.txt`
  exporting.value = true
  try {
    const resp = await axios.get('/api/cyw/report/daily/export', {
      params,
      responseType: 'blob',
    })
    const blobUrl = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = fileNameFromDisposition(resp.headers['content-disposition'], fallback)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch (err) {
    // blob 响应里没有 JSON，手动读出来才能提示「请同时选择起止日期」这类具体原因
    const data = err?.response?.data
    if (data instanceof Blob) {
      try {
        const msg = JSON.parse(await data.text()).error
        if (msg) ElMessage.error(msg)
      } catch { /* 读不出就交给拦截器的通用提示 */ }
    }
  }
  exporting.value = false
}

onMounted(load)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0 0 4px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; }
.report-actions { display: flex; gap: 10px; align-items: center; }
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card { text-align: center; padding: 8px 0; }
.stat-num { font-size: 32px; font-weight: bold; }
.stat-num.primary { color: #409eff; }
.stat-num.success { color: #67c23a; }
.stat-num.warning { color: #e6a23c; }
.stat-num.info { color: #909399; }
.stat-label { color: #606266; font-size: 13px; margin-top: 4px; }
.detail-card { margin-bottom: 12px; }
.detail-title { display: flex; justify-content: space-between; font-weight: bold; }
.detail-count { color: #909399; font-weight: normal; font-size: 13px; }
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.detail-grid .detail-card { margin-bottom: 0; }
</style>
