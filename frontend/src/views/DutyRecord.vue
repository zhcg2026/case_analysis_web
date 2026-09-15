<template>
  <div class="duty-record-page">
    <div class="page-header">
      <h1 class="page-title">值班记录</h1>
      <div class="month-nav">
        <button class="month-btn" @click="changeMonth(-1)" title="上一月">‹</button>
        <span class="month-label">{{ monthLabel }}</span>
        <button class="month-btn" @click="changeMonth(1)" title="下一月">›</button>
        <button v-if="currentMonth !== todayMonth" class="btn-today" @click="goThisMonth">本月</button>
        <button class="btn btn-primary btn-export" :disabled="exporting" @click="exportMonth">
          {{ exporting ? '导出中…' : '导出本月' }}
        </button>
      </div>
    </div>

    <!-- 月历 -->
    <div class="calendar-card">
      <div class="cal-week-row">
        <div v-for="w in weekNames" :key="w" class="cal-week-name" :class="{ weekend: w === '六' || w === '日' }">{{ w }}</div>
      </div>
      <div class="cal-grid">
        <div v-for="(cell, i) in calendarCells" :key="i" class="cal-cell" :class="{ blank: cell.blank, today: cell.isToday }">
          <template v-if="!cell.blank">
            <div class="cal-date">{{ cell.day }}</div>
            <div class="cal-shifts">
              <button class="shift-chip" :class="['day', chipStatus(cell.dayShift)]" @click="openEditor(cell.date, '白班')">
                白班<span v-if="cell.dayShift && cell.dayShift.is_normal" class="chip-mark">✓</span>
              </button>
              <button class="shift-chip" :class="['night', chipStatus(cell.nightShift)]" @click="openEditor(cell.date, '夜班')">
                夜班<span v-if="cell.nightShift && cell.nightShift.is_normal" class="chip-mark">✓</span>
              </button>
            </div>
          </template>
        </div>
      </div>
      <div class="cal-legend">
        <span class="legend-item"><i class="legend-dot ok"></i>已填写</span>
        <span class="legend-item"><i class="legend-dot normal"></i>一切正常</span>
        <span class="legend-item"><i class="legend-dot"></i>未填写</span>
        <span class="legend-hint">点击班次填写/查看，夜班记录含次日清晨事件、统一记在值班当天</span>
      </div>
    </div>

    <!-- 当月数据分析 -->
    <div class="analytics-section">
      <h2 class="section-title">当月数据分析</h2>

      <div class="stat-cards">
        <div class="stat-card">
          <div class="stat-value">{{ analytics.sumReported }}</div>
          <div class="stat-label">本月上报（件）</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ analytics.sumAccepted }}</div>
          <div class="stat-label">本月受理（件）</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ analytics.sumCompleted }}</div>
          <div class="stat-label">本月办结（件）</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ analytics.nightEvents }}</div>
          <div class="stat-label">夜班事件（起）</div>
          <div class="stat-sub">12345：{{ analytics.night12345 }} 起 · 市民来电：{{ analytics.nightCalls }} 起</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ analytics.issueCount }}</div>
          <div class="stat-label">关注案件（件）</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ analytics.normalDays }}<span class="stat-unit">天</span></div>
          <div class="stat-label">夜班一切正常</div>
        </div>
      </div>

      <div class="charts-row">
        <div class="chart-card chart-card--wide">
          <div ref="trendChart" class="chart-box"></div>
        </div>
        <div class="chart-card">
          <div ref="sourceChart" class="chart-box"></div>
        </div>
      </div>

      <div class="issues-card">
        <h3 class="subsection-title">当月关注案件（{{ analytics.issues.length }}）</h3>
        <table v-if="analytics.issues.length" class="data-table">
          <thead>
            <tr>
              <th style="width:80px">日期</th>
              <th style="width:130px">案件编号</th>
              <th style="width:220px">位置</th>
              <th>问题描述</th>
              <th style="width:260px">处理情况</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(it, i) in analytics.issues" :key="i">
              <td>{{ it.date.slice(5) }}</td>
              <td>{{ it.ticket_no || '—' }}</td>
              <td>{{ it.location || '—' }}</td>
              <td>{{ it.description || '—' }}</td>
              <td>{{ it.result || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-hint">本月暂无关注案件</div>
      </div>
    </div>

    <!-- 填写弹窗 -->
    <div v-if="editor.visible" class="modal-overlay" @click.self="closeEditor">
      <div class="editor-modal">
        <div class="modal-header">
          <h3>{{ editor.date }} · {{ editor.shift }}值班记录</h3>
          <div class="header-right">
            <button class="close-btn" @click="closeEditor">&times;</button>
          </div>
        </div>

        <div v-if="editor.loading" class="loading-state"><div class="loading-spinner"></div></div>

        <fieldset v-else class="editor-fieldset">
          <div class="editor-body">
          <!-- 值班人员 -->
          <div class="form-row">
            <label class="form-label">值班人员</label>
            <input
              v-model="editor.members"
              type="text" class="form-input"
              :placeholder="rosterHint || '多个人员用顿号分隔'"
            />
            <div v-if="rosterHint" class="form-tip">已从值班表带出「{{ editor.shift }}：{{ rosterHint }}」，可修改</div>
          </div>

          <!-- 夜班：一切正常 -->
          <div v-if="editor.shift === '夜班'" class="form-row">
            <label class="check-label">
              <input v-model="editor.is_normal" type="checkbox" />
              一切正常（无事件，勾选后保存即可）
            </label>
          </div>

          <!-- 白班：系统运行统计 -->
          <template v-if="editor.shift === '白班'">
            <div class="form-row">
              <label class="form-label">一、系统运行</label>
              <div class="stats-grid">
                <div class="stat-input" v-for="f in totalStatDefs" :key="f.key">
                  <span>{{ f.label }}</span>
                  <input type="number" min="0" v-model.number="editor.stats[f.key]" :placeholder="'0'" />
                </div>
              </div>
              <div class="stats-grid stats-grid--src">
                <div class="stat-input" v-for="f in srcStatDefs" :key="f.key">
                  <span>{{ f.label }}</span>
                  <input type="number" min="0" v-model.number="editor.stats[f.key]" :placeholder="'0'" />
                </div>
              </div>
              <div v-if="statMismatch" class="form-warn">
                七类来源合计 {{ statSum }}，与受理数 {{ editor.stats.stat_accepted ?? '空' }} 不一致，请核对（可保存）
              </div>
            </div>

            <div class="form-row">
              <label class="form-label">备注</label>
              <input v-model="editor.note" type="text" class="form-input" placeholder="其他需要说明的情况，如系统故障（可空）" />
            </div>
          </template>

          <!-- 事件区：白班=关注问题 / 夜班=未勾选一切正常时 -->
          <div v-if="showEvents" class="form-row">
            <div class="events-head">
              <label class="form-label">{{ editor.shift === '白班' ? '二、关注问题' : '夜间事件' }}</label>
              <button type="button" class="btn btn-secondary btn-sm" @click="addEvent">
                + 添加{{ editor.shift === '白班' ? '关注案件' : '事件' }}
              </button>
            </div>

            <div v-if="editor.events.length === 0" class="empty-hint">
              {{ editor.shift === '白班' ? '无关注问题' : '无夜间事件' }}
            </div>

            <div v-for="(ev, i) in editor.events" :key="i" class="event-card">
              <div class="event-head">
                <span class="event-no">{{ i + 1 }}</span>
                <select v-model="ev.category" class="form-input cat-select">
                  <option v-for="c in eventCategories" :key="c" :value="c">{{ c }}</option>
                </select>
                <input
                  v-model="ev.ticket_no" type="text" class="form-input no-input"
                  :placeholder="ev.category === '关注问题' ? '案件编号，如 202609110661' : '12345单号（可选）'"
                />
                <button type="button" class="btn-text danger" @click="removeEvent(i)">删除</button>
              </div>

              <div v-if="editor.shift === '夜班'" class="event-grid">
                <input v-model="ev.caller_name" type="text" class="form-input" placeholder="来电人姓名" />
                <input v-model="ev.caller_phone" type="text" class="form-input" placeholder="来电电话" />
              </div>
              <input v-model="ev.location" type="text" class="form-input event-field" placeholder="位置，如：圣惠路美悦鱼庄门口非机动车道" />
              <textarea v-model="ev.description" rows="2" class="form-input event-field" placeholder="问题描述"></textarea>

              <div class="timeline-block">
                <div class="timeline-label">处置时间线</div>
                <div v-for="(t, j) in ev.timeline" :key="j" class="timeline-row">
                  <input v-model="t.time" type="time" class="form-input time-input" />
                  <input v-model="t.text" type="text" class="form-input" placeholder="如：联系市排水处理 / 市排水回复…（已回复12345）" />
                  <button type="button" class="btn-text danger" @click="removeTimeline(ev, j)">×</button>
                </div>
                <button type="button" class="btn-link" @click="addTimeline(ev)">+ 加一个时间点</button>
              </div>

              <input v-model="ev.result" type="text" class="form-input event-field" placeholder="处理结果，如：已登记系统 / 已回复12345 / 案件派遣至排水服务中心" />
            </div>
          </div>
          </div>
        </fieldset>

        <div class="modal-footer" v-if="!editor.loading">
          <div class="footer-left">
            <button
              v-if="editor.exists && userStore.isAdmin"
              class="btn btn-danger" @click="deleteRecord"
            >删除此记录</button>
            <button
              v-if="editor.exists"
              class="btn btn-secondary" :disabled="exporting" @click="exportCurrent"
            >{{ exporting ? '导出中…' : '导出当日' }}</button>
          </div>
          <div class="footer-right">
            <button class="btn btn-secondary" @click="closeEditor">取消</button>
            <button class="btn btn-primary" :disabled="editor.saving" @click="saveRecord">
              {{ editor.saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../stores/user'
import { chartTemplates, getOrInitChart, disposeEcharts, COLORS, setChartTheme } from '../composables/useEcharts'
import { useThemeStore } from '../stores/theme'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const weekNames = ['日', '一', '二', '三', '四', '五', '六']

const now = new Date()
const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
const todayMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

const currentMonth = ref(todayMonth)
const monthData = ref({ month: todayMonth, records: [] })

const trendChart = ref(null)
const sourceChart = ref(null)

// 统计字段定义（顺序即录入与图表顺序）
const totalStatDefs = [
  { key: 'stat_reported', label: '上报' },
  { key: 'stat_accepted', label: '受理' },
  { key: 'stat_completed', label: '办结' },
]
const srcStatDefs = [
  { key: 'src_collector', label: '采集员上报' },
  { key: 'src_patrol', label: '重点领域巡查' },
  { key: 'src_12345', label: '12345转办' },
  { key: 'src_minhu', label: '民呼我应' },
  { key: 'src_video', label: '视频监控' },
  { key: 'src_ai', label: '智能分析' },
  { key: 'src_public', label: '市民举报' },
]
const eventCategories = ['12345', '市民来电', '关注问题']

// ---------- 月历 ----------
const monthLabel = computed(() => {
  const [y, m] = currentMonth.value.split('-')
  return `${y}年${Number(m)}月`
})

const monthMap = computed(() => {
  const map = {}
  for (const r of monthData.value.records || []) {
    if (!map[r.date]) map[r.date] = {}
    map[r.date][r.shift] = r
  }
  return map
})

const calendarCells = computed(() => {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const lead = new Date(y, m - 1, 1).getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const cells = []
  for (let i = 0; i < lead; i++) cells.push({ blank: true })
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ blank: false, date: ds, day: d, isToday: ds === todayStr, dayShift: monthMap.value[ds]?.['白班'] || null, nightShift: monthMap.value[ds]?.['夜班'] || null })
  }
  return cells
})

function chipStatus(rec) {
  if (!rec) return ''
  return rec.is_normal ? 'normal' : 'ok'
}

function changeMonth(delta) {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  fetchMonth()
}

function goThisMonth() {
  currentMonth.value = todayMonth
  fetchMonth()
}

async function fetchMonth() {
  try {
    const resp = await axios.get('/api/duty-record/month', { params: { month: currentMonth.value } })
    monthData.value = resp.data
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error('获取值班记录失败:', e)
  }
}

// ---------- 当月数据分析 ----------
const analytics = computed(() => {
  const records = monthData.value.records || []
  let sumReported = 0, sumAccepted = 0, sumCompleted = 0
  let nightEvents = 0, night12345 = 0, nightCalls = 0, normalDays = 0
  const srcSums = srcStatDefs.map(f => ({ key: f.key, name: f.label, count: 0 }))
  const srcIndex = Object.fromEntries(srcSums.map(s => [s.key, s]))
  const issues = []
  const trend = {}

  for (const rec of records) {
    if (rec.shift === '白班') {
      const s = rec.stats || {}
      const reported = s.stat_reported || 0
      const accepted = s.stat_accepted || 0
      const completed = s.stat_completed || 0
      const hasStat = totalStatDefs.some(f => s[f.key] != null) || srcStatDefs.some(f => s[f.key] != null)
      if (hasStat) {
        trend[rec.date] = { reported, accepted, completed }
        sumReported += reported
        sumAccepted += accepted
        sumCompleted += completed
      }
      for (const f of srcStatDefs) srcIndex[f.key].count += s[f.key] || 0
      for (const ev of rec.events || []) {
        if (ev.category === '关注问题') {
          issues.push({ date: rec.date, ...ev })
        }
      }
    } else {
      if (rec.is_normal) { normalDays++; continue }
      for (const ev of rec.events || []) {
        nightEvents++
        if (ev.category === '12345') night12345++
        else if (ev.category === '市民来电') nightCalls++
      }
    }
  }

  const trendDays = Object.keys(trend).sort()
  return {
    sumReported, sumAccepted, sumCompleted,
    nightEvents, night12345, nightCalls, normalDays,
    issueCount: issues.length,
    issues,
    srcSums,
    trendDays: trendDays.map(ds => ds.slice(5).replace('-', '/')),
    trendReported: trendDays.map(ds => trend[ds].reported),
    trendAccepted: trendDays.map(ds => trend[ds].accepted),
    trendCompleted: trendDays.map(ds => trend[ds].completed),
  }
})

// ---------- 图表 ----------
// 透明背景 + palette 配色，随页面亮暗主题走（不传 echarts 主题，避免白底/深底冲突）
function nowTimeStr() {
  const n = new Date()
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`
}

function palette() {
  const light = themeStore.theme === 'light'
  return light ? {
    title: '#1f2d3d', axis: '#64748b', axisLine: 'rgba(31,45,61,0.18)', grid: 'rgba(31,45,61,0.06)',
  } : {
    title: '#e0e0e0', axis: '#aaa', axisLine: 'rgba(255,255,255,0.15)', grid: 'rgba(255,255,255,0.06)',
  }
}

function renderCharts() {
  setChartTheme(themeStore.theme)
  const c = palette()

  if (trendChart.value) {
    const chart = getOrInitChart(trendChart.value, null)
    chart.setOption({
      title: { text: '每日案件走势', left: 'center', textStyle: { color: c.title, fontSize: 15 } },
      tooltip: { trigger: 'axis' },
      legend: { data: ['上报', '受理', '办结'], top: 30, textStyle: { color: c.axis } },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '26%', containLabel: true },
      xAxis: {
        type: 'category', boundaryGap: false, data: analytics.value.trendDays,
        axisLabel: { color: c.axis }, axisLine: { lineStyle: { color: c.axisLine } },
      },
      yAxis: {
        type: 'value', axisLabel: { color: c.axis }, splitLine: { lineStyle: { color: c.grid } },
      },
      series: [
        { name: '上报', type: 'line', smooth: true, symbolSize: 6, data: analytics.value.trendReported, lineStyle: { width: 2.5, color: COLORS[0] }, itemStyle: { color: COLORS[0] } },
        { name: '受理', type: 'line', smooth: true, symbolSize: 6, data: analytics.value.trendAccepted, lineStyle: { width: 2.5, color: COLORS[1] }, itemStyle: { color: COLORS[1] } },
        { name: '办结', type: 'line', smooth: true, symbolSize: 6, data: analytics.value.trendCompleted, lineStyle: { width: 2.5, color: COLORS[2] }, itemStyle: { color: COLORS[2] } },
      ],
    })
  }

  if (sourceChart.value) {
    const hasSrc = analytics.value.srcSums.some(s => s.count > 0)
    const chart = getOrInitChart(sourceChart.value, null)
    chart.setOption(hasSrc
      ? chartTemplates.horizontal_bar('当月来源构成', analytics.value.srcSums, 'name', 'count')
      : {
          title: { text: '当月来源构成', left: 'center', textStyle: { color: c.title, fontSize: 15 } },
          xAxis: { type: 'value', show: false }, yAxis: { type: 'category', show: false },
          series: [], label: { show: false },
        })
  }
}

// 主题切换时跟随重绘
watch(() => themeStore.theme, () => {
  setChartTheme(themeStore.theme)
  nextTick(renderCharts)
})

// ---------- 填写弹窗 ----------
const editor = ref({
  visible: false, loading: false, saving: false,
  date: '', shift: '', recordId: null, exists: false, canEdit: true,
  members: '', is_normal: true, note: '',
  stats: blankStats(), events: [],
})
const rosterHint = ref('')

function blankStats() {
  const s = {}
  for (const f of [...totalStatDefs, ...srcStatDefs]) s[f.key] = null
  return s
}

const showEvents = computed(() => editor.value.shift === '白班' || !editor.value.is_normal)

const statSum = computed(() =>
  srcStatDefs.reduce((sum, f) => sum + (Number(editor.value.stats[f.key]) || 0), 0)
)
const statMismatch = computed(() =>
  editor.value.stats.stat_accepted != null &&
  String(editor.value.stats.stat_accepted) !== '' &&
  statSum.value !== Number(editor.value.stats.stat_accepted)
)

async function openEditor(date, shift) {
  editor.value = {
    visible: true, loading: true, saving: false,
    date, shift, recordId: null, exists: false, canEdit: true,
    members: '', is_normal: true, note: '',
    stats: blankStats(), events: [],
  }
  rosterHint.value = ''
  const [dayResp, rosterResp] = await Promise.all([
    axios.get('/api/duty-record/day', { params: { date } }).catch(() => null),
    axios.get('/api/duty/roster', { params: { date } }).catch(() => null),
  ])

  // 值班表带出当日该班次人员
  const rosterShifts = rosterResp?.data?.shifts || []
  const rosterHit = rosterShifts.find(s => s.shift === shift)
  if (rosterHit && rosterHit.members?.length) rosterHint.value = rosterHit.members.join('、')

  const rec = (dayResp?.data?.records || []).find(r => r.shift === shift)
  if (rec) {
    editor.value.exists = true
    editor.value.recordId = rec.id
    editor.value.canEdit = !!rec.can_edit
    editor.value.members = rec.members || ''
    editor.value.is_normal = !!rec.is_normal
    editor.value.note = rec.note || ''
    editor.value.stats = { ...blankStats(), ...(rec.stats || {}) }
    editor.value.events = (rec.events || []).map(ev => ({ ...ev, timeline: (ev.timeline || []).map(t => ({ ...t })) }))
  } else if (rosterHint.value) {
    editor.value.members = rosterHint.value
  }
  editor.value.loading = false
}

function closeEditor() {
  editor.value.visible = false
}

function addEvent() {
  editor.value.events.push({
    category: editor.value.shift === '白班' ? '关注问题' : '12345',
    ticket_no: '', caller_name: '', caller_phone: '',
    location: '', description: '', timeline: [{ time: nowTimeStr(), text: '' }], result: '',
  })
}

function removeEvent(i) {
  editor.value.events.splice(i, 1)
}

function addTimeline(ev) {
  // 新时间点默认当前时间（值班时边发生边记）
  ev.timeline.push({ time: nowTimeStr(), text: '' })
}

function removeTimeline(ev, j) {
  ev.timeline.splice(j, 1)
}

async function saveRecord() {
  editor.value.saving = true
  try {
    await axios.post('/api/duty-record', {
      date: editor.value.date,
      shift: editor.value.shift,
      members: editor.value.members,
      is_normal: editor.value.shift === '夜班' ? editor.value.is_normal : false,
      note: editor.value.note,
      stats: editor.value.stats,
      events: editor.value.events,
    })
    closeEditor()
    await fetchMonth()
  } catch {
    // error toast via interceptor
  } finally {
    editor.value.saving = false
  }
}

async function deleteRecord() {
  if (!confirm(`确定删除 ${editor.value.date} ${editor.value.shift} 的值班记录？`)) return
  try {
    await axios.delete(`/api/duty-record/${editor.value.recordId}`)
    closeEditor()
    await fetchMonth()
  } catch {
    // error toast via interceptor
  }
}

// ---------- 导出 ----------
const exporting = ref(false)

async function downloadExport(params, filename) {
  exporting.value = true
  try {
    const resp = await axios.get('/api/duty-record/export', { params, responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    let msg = e.message
    if (e.response?.data instanceof Blob) {
      try { msg = JSON.parse(await e.response.data.text()).error || msg } catch {}
    }
    // error toast via interceptor
  } finally {
    exporting.value = false
  }
}

function exportMonth() {
  downloadExport({ month: currentMonth.value }, `值班记录_${monthLabel.value}.docx`)
}

function exportCurrent() {
  downloadExport(
    { date: editor.value.date, shift: editor.value.shift },
    `值班记录_${editor.value.shift}_${editor.value.date}.docx`
  )
}

// ---------- 生命周期 ----------
onMounted(async () => {
  await fetchMonth()
  // 首页"今日记录"点击直达：/duty-record?date=xx&shift=白班
  const qDate = route.query.date
  const qShift = route.query.shift
  if (qDate && (qShift === '白班' || qShift === '夜班')) {
    const [y, m] = String(qDate).split('-')
    if (y && m) {
      currentMonth.value = `${y}-${m}`
      await fetchMonth()
    }
    openEditor(String(qDate), qShift)
  }
})

onUnmounted(() => {
  if (trendChart.value) disposeEcharts(trendChart.value)
  if (sourceChart.value) disposeEcharts(sourceChart.value)
})
</script>

<style scoped>
.duty-record-page {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.month-nav {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.month-btn {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-light);
  background: var(--bg-card);
  color: var(--text-primary);
  border-radius: var(--radius-md);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
}

.month-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-500);
}

.month-label {
  min-width: 100px;
  text-align: center;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-today {
  height: 30px;
  padding: 0 12px;
  margin-left: var(--space-2);
  border: 1px solid var(--border-light);
  background: var(--bg-card);
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
}

.btn-today:hover {
  color: var(--primary-500);
  border-color: var(--primary-500);
}

.btn-export {
  height: 30px;
  padding: 0 14px;
  margin-left: var(--space-3);
  font-size: 13px;
}

/* ---------- 月历 ---------- */
.calendar-card {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-6);
}

.cal-week-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: var(--space-2);
}

.cal-week-name {
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 600;
}

.cal-week-name.weekend {
  color: var(--danger);
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.cal-cell {
  min-height: 76px;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cal-cell.blank {
  border-color: transparent;
  background: transparent;
}

.cal-cell.today {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 1px var(--primary-500);
}

.cal-date {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.cal-cell.today .cal-date {
  color: var(--primary-500);
}

.cal-shifts {
  display: flex;
  gap: 4px;
}

.shift-chip {
  flex: 1;
  border: none;
  border-radius: 999px;
  font-size: 11px;
  padding: 2px 0;
  cursor: pointer;
  background: var(--fill-light);
  color: var(--text-placeholder);
  transition: transform var(--transition-fast);
}

.shift-chip:hover {
  transform: scale(1.06);
}

.shift-chip.ok {
  background: rgba(103, 194, 58, 0.16);
  color: var(--success-dark);
  font-weight: 600;
}

.shift-chip.normal {
  background: rgba(64, 158, 255, 0.14);
  color: var(--primary-500);
  font-weight: 600;
}

[data-theme="dark"] .shift-chip.ok {
  color: var(--success);
}

.chip-mark {
  margin-left: 2px;
}

.cal-legend {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-3);
  font-size: 12px;
  color: var(--text-tertiary);
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--fill-light);
  display: inline-block;
}

.legend-dot.ok {
  background: var(--success);
}

.legend-dot.normal {
  background: var(--primary-500);
}

.legend-hint {
  margin-left: auto;
}

/* ---------- 数据分析 ---------- */
.analytics-section {
  margin-bottom: var(--space-6);
}

.section-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  text-align: center;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.stat-unit {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 2px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.stat-sub {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
}

.chart-box {
  width: 100%;
  height: 300px;
}

.issues-card {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.subsection-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-3);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th,
.data-table td {
  padding: var(--space-2) var(--space-3);
  text-align: left;
  border-bottom: 1px solid var(--border-lighter);
  color: var(--text-primary);
}

.data-table th {
  color: var(--text-tertiary);
  font-weight: 600;
  font-size: 12px;
}

.empty-hint {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: var(--space-4);
}

/* ---------- 填写弹窗 ---------- */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.editor-modal {
  width: 860px;
  max-width: 96vw;
  /* 固定高度：表单内容不参与撑高，内层滚动区才能有确定的可用高度 */
  height: 92vh;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-lighter);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ro-tag {
  font-size: 12px;
  color: var(--warning-dark);
  background: rgba(230, 162, 60, 0.14);
  border-radius: 999px;
  padding: 2px 10px;
}

[data-theme="dark"] .ro-tag {
  color: var(--warning);
}

.close-btn {
  border: none;
  background: none;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
  line-height: 1;
}

/* fieldset 不能做滚动容器（Chromium 不支持 fieldset 滚动），
   只用它做整体禁用语义；滚动由内层绝对定位的 .editor-body 承担 */
.editor-fieldset {
  border: none;
  padding: 0;
  margin: 0;
  min-width: 0;
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
}

.editor-body {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.editor-fieldset:disabled .editor-body {
  opacity: 0.75;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-input {
  width: 100%;
}

.form-tip {
  font-size: 12px;
  color: var(--primary-500);
}

.form-warn {
  font-size: 12px;
  color: var(--warning-dark);
  background: rgba(230, 162, 60, 0.12);
  border-radius: var(--radius-md);
  padding: 6px 10px;
}

[data-theme="dark"] .form-warn {
  color: var(--warning);
}

.check-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

.stats-grid--src {
  grid-template-columns: repeat(4, 1fr);
}

.stat-input {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--fill-light);
  border-radius: var(--radius-md);
  padding: 6px 10px;
}

.stat-input span {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.stat-input input {
  width: 100%;
  min-width: 0;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  text-align: right;
  outline: none;
  font-variant-numeric: tabular-nums;
}

.events-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-sm {
  padding: 4px 12px;
  font-size: 13px;
}

.event-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--fill-lighter);
}

.event-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.event-no {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--primary-500);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cat-select {
  width: 110px;
  flex-shrink: 0;
}

.no-input {
  flex: 1;
}

.event-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.event-field {
  margin: 0;
}

.timeline-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-left: 2px solid var(--border-light);
  padding-left: var(--space-3);
  margin: var(--space-1) 0;
}

.timeline-label {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 600;
}

.timeline-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.time-input {
  width: 110px;
  flex-shrink: 0;
}

.btn-link {
  border: none;
  background: none;
  color: var(--primary-500);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  padding: 0;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-lighter);
}

.footer-left {
  display: flex;
  gap: var(--space-3);
}

.footer-right {
  display: flex;
  gap: var(--space-3);
  margin-left: auto;
}

.loading-state {
  padding: var(--space-6);
  display: flex;
  justify-content: center;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-light);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---------- 响应式 ---------- */
@media (max-width: 1100px) {
  .stat-cards {
    grid-template-columns: repeat(3, 1fr);
  }

  .charts-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .cal-cell {
    min-height: 64px;
    padding: 4px;
  }

  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .stats-grid--src {
    grid-template-columns: repeat(2, 1fr);
  }

  .legend-hint {
    margin-left: 0;
  }
}
</style>
