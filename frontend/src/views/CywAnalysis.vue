<template>
  <div class="cyw-analysis-tab">
    <div class="page-header">
      <div>
        <h2>数据分析</h2>
        <p class="page-sub">
          按单日或起止日期（连续几天、一周、一月）聚合高发点位与高发问题，口径与「数据统计」一致——按发现时间落在区间内计数。
          点击榜单里的任一行，可跳到问题台账按该项过滤，接着看是哪些案子。
        </p>
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
      </div>
    </div>

    <div class="stat-cards">
      <el-card shadow="never" class="stat-card">
        <div class="stat-num primary">{{ grandTotal }}</div>
        <div class="stat-label">{{ isSingle ? '当日案件总数' : '周期案件总数' }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num info">{{ topSpot.total }}</div>
        <div class="stat-label" :title="topSpot.label">最高发点位：{{ topSpot.shortLabel }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num warning">{{ topType.total }}</div>
        <div class="stat-label" :title="topType.label">最高发问题：{{ topType.label }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-num success">{{ topShare }}<small>%</small></div>
        <div class="stat-label">最高发问题占比</div>
      </el-card>
    </div>

    <div class="chart-grid">
      <el-card shadow="never" class="chart-card">
        <template #header>
          <div class="chart-title">
            <span>高发点位 TOP 10</span>
            <el-radio-group v-model="dimension" size="small" @change="load">
              <el-radio-button label="spot">点位</el-radio-button>
              <el-radio-button label="road">路段</el-radio-button>
              <el-radio-button label="dept">派发部门</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <div ref="rankChart" class="chart-box"></div>
        <el-table :data="ranking" border size="small" max-height="260" @row-click="onRankRowClick">
          <el-table-column type="index" label="#" width="46" />
          <el-table-column :label="dimensionLabel" min-width="170" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="clickable">{{ row.label }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="total" label="件数" width="62" align="center" />
          <el-table-column prop="closed" label="已办结" width="72" align="center" />
          <el-table-column prop="ratio" label="占比" width="72" align="center">
            <template #default="{ row }">{{ row.ratio }}%</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="chart-card">
        <template #header>
          <div class="chart-title"><span>高发问题 TOP 10</span></div>
        </template>
        <div ref="typeChart" class="chart-box"></div>
        <el-table :data="byType" border size="small" max-height="260" @row-click="onTypeRowClick">
          <el-table-column type="index" label="#" width="46" />
          <el-table-column prop="label" label="问题类型" min-width="150" show-overflow-tooltip>
            <template #default="{ row }"><span class="clickable">{{ row.label }}</span></template>
          </el-table-column>
          <el-table-column prop="total" label="件数" width="62" align="center" />
          <el-table-column prop="closed" label="已办结" width="72" align="center" />
          <el-table-column prop="ratio" label="占比" width="72" align="center">
            <template #default="{ row }">{{ row.ratio }}%</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-card shadow="never" class="cross-card">
      <template #header>
        <div class="chart-title">
          <span>点位 × 问题交叉榜 TOP 10</span>
          <span class="detail-count">
            同一位置反复出同类问题，说明该点位需要针对性治理
            <el-button size="small" type="primary" link :loading="exporting" @click="exportCross">
              导出 Excel
            </el-button>
          </span>
        </div>
      </template>
      <el-table :data="cross" border size="small" max-height="300" @row-click="onCrossRowClick">
        <el-table-column type="index" label="#" width="46" />
        <el-table-column label="点位" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="clickable">{{ spotFullName(row) }}</span>
            <small v-if="row.monitor_no" class="mono">（{{ row.monitor_no }}）</small>
          </template>
        </el-table-column>
        <el-table-column prop="type_name" label="问题类型" width="140" show-overflow-tooltip />
        <el-table-column prop="total" label="件数" width="62" align="center" />
        <el-table-column prop="closed" label="已办结" width="72" align="center" />
        <el-table-column prop="ratio" label="占周期比" width="90" align="center">
          <template #default="{ row }">{{ row.ratio }}%</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="trend-card">
      <template #header>
        <div class="chart-title">
          <span>按天趋势</span>
          <span class="detail-count">{{ isSingle ? '单日模式下仅一条' : '逐日新增与办结' }}</span>
        </div>
      </template>
      <div ref="trendChart" class="chart-box"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { chartTemplates, getOrInitChart, disposeEcharts, COLORS, setChartTheme } from '../composables/useEcharts'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const themeStore = useThemeStore()

const pad = (n) => String(n).padStart(2, '0')
const dayText = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const today = () => dayText(new Date())
const shift = (days) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return dayText(d)
}

const mode = ref('range')
const date = ref(today())
// 数据分析默认看近 30 天：单日口径下点位/问题都只有零星几条，看不出「高发」
const dateRange = ref([shift(-29), today()])
const rangeShortcuts = [
  { text: '最近7天', value: () => [shift(-6), today()] },
  { text: '最近30天', value: () => [shift(-29), today()] },
  { text: '本月', value: () => {
      const d = new Date()
      return [dayText(new Date(d.getFullYear(), d.getMonth(), 1)), today()]
    } },
  { text: '上月', value: () => [dayText(new Date(d.getFullYear(), d.getMonth() - 1, 1)),
                                dayText(new Date(d.getFullYear(), d.getMonth(), 0))] },
]

const dimension = ref('spot')
const dimensionLabel = computed(() => ({ spot: '点位', road: '路段', dept: '派发部门' }[dimension.value]))

// 文案口径跟随后端返回的 is_single：起止同一天时按单日展示，不自己判断
const isSingle = ref(true)
const grandTotal = ref(0)
const ranking = ref([])
const byType = ref([])
const cross = ref([])
const trend = ref([])

const rankChart = ref(null)
const typeChart = ref(null)
const trendChart = ref(null)

const topSpot = computed(() => ranking.value[0] || { total: 0, label: '-' })
const topType = computed(() => byType.value[0] || { total: 0, label: '-' })
const topShare = computed(() => topType.value.ratio || 0)

// 时间范围口径与数据统计页完全一致：时间段模式才带 date_from/date_to，否则退回单日 date
const rangeParams = () => (mode.value === 'range' && dateRange.value?.length === 2
  ? { date_from: dateRange.value[0], date_to: dateRange.value[1] }
  : { date: date.value })

async function load() {
  try {
    const { data } = await axios.get('/api/cyw/report/analysis',
      { params: { ...rangeParams(), dimension: dimension.value } })
    isSingle.value = data.is_single !== false
    grandTotal.value = data.grand_total || 0
    ranking.value = data.ranking || []
    byType.value = data.by_type || []
    cross.value = data.cross || []
    trend.value = data.trend || []
    await nextTick()
    renderCharts()
  } catch { /* error toast via interceptor */ }
}

function onModeChange() {
  if (mode.value === 'range' && dateRange.value?.length !== 2) {
    dateRange.value = [shift(-29), today()]
  }
  load()
}

// 点位完整名（含道路）：直接复用后端同款规则的极简版——点名已含路名时不重复拼。
// 后端在接口里已给 spot_road，这里只负责展示层拼接，与抽查报告口径一致
function spotFullName(row) {
  const name = row.spot_name || ''
  const road = row.spot_road || ''
  if (!road || !name) return name
  if (name.startsWith(road) || name.includes(road)) return name
  return `${road}${name}`
}

// ---------- 图表 ----------
// 透明背景 + palette 配色，随页面亮暗主题走（不传 echarts 主题，避免白底/深底冲突）
function palette() {
  const light = themeStore.theme === 'light'
  return light ? {
    title: '#1f2d3d', axis: '#64748b', axisLine: 'rgba(31,45,61,0.18)', grid: 'rgba(31,45,61,0.06)',
  } : {
    title: '#e0e0e0', axis: '#aaa', axisLine: 'rgba(255,255,255,0.15)', grid: 'rgba(255,255,255,0.06)',
  }
}

// 横向条形图模板只取前 15 条，这里榜单固定 10 条，直接用模板
function rankOption(title, rows) {
  if (!rows.length) {
    const c = palette()
    return {
      title: { text: title, left: 'center', textStyle: { color: c.title, fontSize: 15 } },
      xAxis: { type: 'value', show: false }, yAxis: { type: 'category', show: false }, series: [],
    }
  }
  // 双系列（总数/已办结）横向条形：模板按第一个字段升序排，正合榜单倒序展示的预期
  return chartTemplates.horizontal_bar(title, rows, 'label', ['total', 'closed'])
}

function renderCharts() {
  setChartTheme(themeStore.theme)
  if (rankChart.value) {
    getOrInitChart(rankChart.value, null).setOption(rankOption(`${dimensionLabel.value}高发 TOP 10`, ranking.value))
  }
  if (typeChart.value) {
    getOrInitChart(typeChart.value, null).setOption(rankOption('高发问题 TOP 10', byType.value))
  }
  if (trendChart.value) {
    const c = palette()
    const chart = getOrInitChart(trendChart.value, null)
    if (trend.value.length) {
      chart.setOption({
        title: { text: '按天趋势', left: 'center', textStyle: { color: c.title, fontSize: 15 } },
        tooltip: { trigger: 'axis' },
        legend: { data: ['新增', '已办结'], top: 30, textStyle: { color: c.axis } },
        grid: { left: '3%', right: '4%', bottom: '10%', top: '26%', containLabel: true },
        xAxis: {
          type: 'category', boundaryGap: false, data: trend.value.map(t => t.day),
          axisLabel: { color: c.axis }, axisLine: { lineStyle: { color: c.axisLine } },
        },
        yAxis: { type: 'value', axisLabel: { color: c.axis }, splitLine: { lineStyle: { color: c.grid } } },
        series: [
          { name: '新增', type: 'line', smooth: true, symbolSize: 6, data: trend.value.map(t => t.total), lineStyle: { width: 2.5, color: COLORS[0] }, itemStyle: { color: COLORS[0] } },
          { name: '已办结', type: 'line', smooth: true, symbolSize: 6, data: trend.value.map(t => t.closed), lineStyle: { width: 2.5, color: COLORS[1] }, itemStyle: { color: COLORS[1] } },
        ],
      })
    } else {
      chart.setOption({
        title: { text: '按天趋势', left: 'center', textStyle: { color: c.title, fontSize: 15 } },
        xAxis: { type: 'value', show: false }, yAxis: { type: 'category', show: false }, series: [],
      })
    }
  }
}

// 主题切换时跟随重绘
watch(() => themeStore.theme, () => {
  setChartTheme(themeStore.theme)
  nextTick(renderCharts)
})

// ---------- 下钻：跳到问题台账并带上过滤条件 ----------
// 台账页的 keyword 是模糊匹配（案件编号/描述/点位名/监控序号），点位名/路段名都能直接命中；
// 类型是下拉框，只能带 type_name 让前端回选中；日期统一带上当前统计区间
function goLedger(query) {
  const params = { ...rangeParams() }
  const q = { ...params }
  if (query.keyword) q.keyword = query.keyword
  if (query.type_name) q.type_name = query.type_name
  if (query.dept_name) q.dept_name = query.dept_name
  router.push({ path: '/cyw/ledger', query: q })
}

function onRankRowClick(row) {
  if (!row?.label) return
  if (dimension.value === 'spot') goLedger({ keyword: row.label })
  else if (dimension.value === 'dept') goLedger({ dept_name: row.label })
  else {
    // 路段维度：台账没有路段筛选项，用点位名模糊匹配容易落空，改为提示后仍带 keyword 兜底
    ElMessage.info('已按「' + row.label + '」跳转台账，如结果偏少请在台账页手动核对')
    goLedger({ keyword: row.label })
  }
}

function onTypeRowClick(row) {
  if (row?.label) goLedger({ type_name: row.label })
}

function onCrossRowClick(row) {
  if (!row?.spot_name) return
  goLedger({ keyword: row.spot_name, type_name: row.type_name })
}

// ---------- 导出 Excel ----------
// 后端按当前时段重新聚合一模一样的一份（含高发问题 TOP 10 sheet），
// 所以导出的数和屏幕上看到的一致；时段参数与上面 load 完全同源
const exporting = ref(false)

async function exportCross() {
  if (exporting.value) return
  exporting.value = true
  try {
    const resp = await axios.get('/api/cyw/report/analysis/export', {
      params: rangeParams(), responseType: 'blob',
    })
    // 文件名走后端 Content-Disposition（RFC5987），拿不到就按当前时段兜底拼一个
    let filename = `创文数据分析_${rangeParams().date_from || rangeParams().date}.xlsx`
    const disposition = resp.headers['content-disposition']
    if (disposition) {
      const m = disposition.match(/filename\*=UTF-8''([^;]+)/i)
      if (m) filename = decodeURIComponent(m[1])
    }
    const url = URL.createObjectURL(new Blob([resp.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    URL.revokeObjectURL(url)
    document.body.removeChild(a)
    ElMessage.success('导出成功')
  } catch (e) {
    // 失败时响应体是 blob（拦截器读不到 error 字段），自己解析出后端的中文提示
    const msg = await e?.response?.data?.text?.()
    ElMessage.error(msg ? (JSON.parse(msg).error || '导出失败') : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  setChartTheme(themeStore.theme)
  load()
})

onUnmounted(() => {
  for (const el of [rankChart.value, typeChart.value, trendChart.value]) disposeEcharts(el)
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0 0 4px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; max-width: 760px; }
.report-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card { text-align: center; padding: 8px 0; }
.stat-num { font-size: 32px; font-weight: bold; }
.stat-num.primary { color: #409eff; }
.stat-num.info { color: #909399; }
.stat-num.warning { color: #e6a23c; }
.stat-num.success { color: #67c23a; }
.stat-label {
  color: #606266; font-size: 13px; margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.chart-card, .cross-card, .trend-card { margin-bottom: 0; }
.chart-title { display: flex; justify-content: space-between; align-items: center; font-weight: bold; }
.detail-count { color: #909399; font-weight: normal; font-size: 12px; }
.chart-box { height: 280px; }
.clickable { color: #409eff; cursor: pointer; }
.clickable:hover { text-decoration: underline; }
.mono { color: #909399; font-family: Consolas, Monaco, monospace; }
</style>
