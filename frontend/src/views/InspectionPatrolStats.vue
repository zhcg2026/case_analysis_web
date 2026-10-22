<template>
  <div class="ips-page">
    <div class="page-header">
      <div>
        <h2>巡查数据统计</h2>
        <p class="page-sub">数字全部实时聚合，没有手工维护的汇总。导出的 Excel 版式与《问题处置汇总总台账》一致。</p>
      </div>
      <div>
        <el-button :loading="exporting" @click="exportExcel">导出台账</el-button>
        <el-button type="primary" @click="load">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-radio-group v-model="mode" @change="onModeChange">
          <el-radio-button label="range">时间段</el-radio-button>
          <el-radio-button label="all">全部</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="mode === 'range'"
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :shortcuts="shortcuts"
          style="width: 260px"
          @change="load"
        />
        <span v-else class="muted">统计范围：全部已入库数据</span>
      </div>
    </el-card>

    <!-- 总览 -->
    <el-row :gutter="16" class="overview">
      <el-col :span="6">
        <div class="stat-box total">
          <div class="stat-num">{{ stats.total }}</div>
          <div class="stat-label">问题总数</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-box done">
          <div class="stat-num">{{ stats.rectified }}</div>
          <div class="stat-label">已整改</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-box pending">
          <div class="stat-num">{{ stats.pending }}</div>
          <div class="stat-label">待整改</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-box rate">
          <div class="stat-num">{{ stats.rectify_rate }}<small>%</small></div>
          <div class="stat-label">整改率</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 按责任单位 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><b>按责任单位</b></template>
          <el-table :data="stats.by_dept" border size="small" max-height="420">
            <el-table-column prop="dept" label="单位" min-width="90" />
            <el-table-column prop="total" label="问题数" width="70" align="center" />
            <el-table-column prop="rectified" label="已整改" width="70" align="center" />
            <el-table-column label="整改率" width="80" align="center">
              <template #default="{ row }">
                {{ row.total ? Math.round(row.rectified / row.total * 100) : 0 }}%
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 按道路 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><b>按道路</b></template>
          <el-table :data="stats.by_road" border size="small" max-height="420">
            <el-table-column prop="road" label="道路" min-width="110" show-overflow-tooltip />
            <el-table-column prop="total" label="问题数" width="70" align="center" />
            <el-table-column prop="rectified" label="已整改" width="70" align="center" />
            <el-table-column label="整改率" width="80" align="center">
              <template #default="{ row }">
                {{ row.total ? Math.round(row.rectified / row.total * 100) : 0 }}%
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 按日期 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><b>按发现日期</b></template>
          <el-table :data="stats.by_date" border size="small" max-height="420">
            <el-table-column label="日期" width="100">
              <template #default="{ row }">{{ fmtDate(row.date) }}</template>
            </el-table-column>
            <el-table-column prop="total" label="问题数" width="70" align="center" />
            <el-table-column prop="rectified" label="已整改" width="70" align="center" />
            <el-table-column label="整改率" width="80" align="center">
              <template #default="{ row }">
                {{ row.total ? Math.round(row.rectified / row.total * 100) : 0 }}%
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const mode = ref('range')
const dateRange = ref(null)
const exporting = ref(false)
const stats = reactive({ total: 0, rectified: 0, pending: 0, rectify_rate: 0, by_dept: [], by_road: [], by_date: [] })

const pad = (n) => String(n).padStart(2, '0')
const dayText = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const today = () => dayText(new Date())
const shift = (days) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return dayText(d)
}
const shortcuts = [
  { text: '最近7天', value: () => [shift(-6), today()] },
  { text: '最近30天', value: () => [shift(-29), today()] },
  { text: '本月', value: () => {
      const d = new Date()
      return [dayText(new Date(d.getFullYear(), d.getMonth(), 1)), today()]
    } },
  { text: '全部', value: () => null },
]

const fmtDate = (d) => {
  if (!d) return ''
  const s = String(d)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return `${s.slice(5, 7)}月${s.slice(8, 10)}日`
  return s
}

function onModeChange() {
  if (mode.value === 'range' && !dateRange.value) dateRange.value = [shift(-6), today()]
  load()
}

async function load() {
  try {
    const params = mode.value === 'range' && dateRange.value?.length === 2
      ? { date_from: dateRange.value[0], date_to: dateRange.value[1] }
      : {}
    const { data } = await axios.get('/api/inspection/stats', { params })
    Object.assign(stats, data)
  } catch { /* 拦截器已提示 */ }
}

async function exportExcel() {
  exporting.value = true
  try {
    const params = mode.value === 'range' && dateRange.value?.length === 2
      ? { date_from: dateRange.value[0], date_to: dateRange.value[1] }
      : {}
    const { data, headers } = await axios.get('/api/inspection/export', {
      params, responseType: 'blob',
    })
    const disposition = headers['content-disposition'] || ''
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
    const fname = utf8 ? decodeURIComponent(utf8[1]) : '巡查问题台账.xlsx'
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = fname
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* 拦截器已提示 */ }
  exporting.value = false
}

onMounted(() => {
  dateRange.value = [shift(-6), today()]
  load()
})
</script>

<style scoped>
.ips-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 6px; font-size: 20px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; max-width: 720px; line-height: 1.6; }
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 14px; }
.muted { color: #909399; font-size: 13px; }
.overview { margin-bottom: 16px; }
.stat-box { text-align: center; padding: 22px 10px; border-radius: 8px; color: #fff; }
.stat-num { font-size: 32px; font-weight: 600; line-height: 1; }
.stat-num small { font-size: 16px; margin-left: 2px; }
.stat-label { font-size: 13px; margin-top: 8px; opacity: .9; }
.stat-box.total { background: linear-gradient(135deg, #409eff, #66b1ff); }
.stat-box.done { background: linear-gradient(135deg, #67c23a, #95d475); }
.stat-box.pending { background: linear-gradient(135deg, #e6a23c, #f0c78a); }
.stat-box.rate { background: linear-gradient(135deg, #9254de, #b37feb); }
</style>
