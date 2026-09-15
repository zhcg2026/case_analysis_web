<template>
  <div class="home-page">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-content">
        <h1 class="welcome-title">欢迎回来，{{ userStore.username }}</h1>
        <p class="welcome-subtitle">{{ config.name }} v2.0 - 智能数据分析平台</p>
      </div>
      <div v-if="dutyShifts.length" class="welcome-duty">
        <div class="duty-label">
          今日值班
          <span v-if="dutyNote" class="duty-note-tag">{{ dutyNote }}</span>
        </div>
        <div class="duty-shifts">
          <div v-for="s in dutyShifts" :key="s.shift" class="duty-shift">
            <span class="duty-chip" :class="isNightShift(s.shift) ? 'night' : 'day'">
              <svg v-if="isNightShift(s.shift)" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="4"/>
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
              </svg>
              {{ s.shift }}
            </span>
            <span class="duty-members">{{ s.members.join('、') }}</span>
          </div>
        </div>
      </div>
      <div class="welcome-record" @click="goDutyRecord" title="进入值班记录">
        <div class="record-label">值班数据</div>
        <div class="record-data-rows">
          <div class="record-data-row">
            <span class="rd-tag" :class="recordData.dayLabel === '昨日' ? 'rd-tag--yesterday' : 'rd-tag--day'">{{ recordData.dayLabel }}</span>
            <span class="rd-item" v-for="k in ['reported', 'accepted', 'completed']" :key="k">
              {{ rdLabel(k) }} <b :class="{ empty: recordData.day[k] == null }">{{ rdNum(recordData.day[k]) }}</b>
            </span>
          </div>
          <div class="record-data-row">
            <span class="rd-tag rd-tag--month">本月</span>
            <span class="rd-item" v-for="k in ['reported', 'accepted', 'completed']" :key="k">
              {{ rdLabel(k) }} <b :class="{ empty: !recordData.month[k] }">{{ rdNum(recordData.month[k]) }}</b>
            </span>
          </div>
        </div>
      </div>
      <div class="welcome-time">
        <div class="time-display">{{ currentTime }}</div>
        <div class="date-display">{{ currentDate }}</div>
      </div>
    </div>

    <!-- 通知公告轮播（栏目「通知公告」已发布文章；不作为独立栏目块） -->
    <div v-if="notices.length" class="notice-bar" @mouseenter="pauseNotice" @mouseleave="resumeNotice">
      <div class="notice-label">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        通知公告
      </div>
      <button class="notice-arrow" type="button" title="上一条" @click="prevNotice">‹</button>
      <a
        class="notice-link"
        :href="noticeHref"
        target="_blank"
        rel="noopener"
        @click="openNotice($event)"
      >{{ currentNotice?.title }}</a>
      <button class="notice-arrow" type="button" title="下一条" @click="nextNotice">›</button>
      <div v-if="notices.length > 1" class="notice-dots">
        <button
          v-for="(n, i) in notices"
          :key="n.id"
          type="button"
          class="notice-dot"
          :class="{ active: i === noticeIndex }"
          :title="n.title"
          @click="noticeIndex = i"
        />
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useSystemConfig } from '../composables/useSystemConfig'
import axios from 'axios'

const userStore = useUserStore()
const { config } = useSystemConfig()
const router = useRouter()

const currentTime = ref('')
const currentDate = ref('')
let timeInterval = null

const columns = ref([])

// 通知公告轮播
const notices = ref([])
const noticeIndex = ref(0)
let noticeTimer = null
const NOTICE_INTERVAL_MS = 5000

const currentNotice = computed(() => notices.value[noticeIndex.value] || null)

const noticeHref = computed(() => {
  const n = currentNotice.value
  if (!n) return '#'
  const fp = (n.file_path || '').trim()
  if (fp && fp.toLowerCase().endsWith('.html')) {
    return fp.startsWith('/') ? fp : `/${fp}`
  }
  return n.url || `#/article/${n.id}`
})

function openNotice(e) {
  e?.preventDefault?.()
  const n = currentNotice.value
  if (!n) return
  const fp = (n.file_path || '').trim()
  if (fp && fp.toLowerCase().endsWith('.html')) {
    const url = fp.startsWith('/') ? fp : `/${fp}`
    window.open(url, '_blank', 'noopener')
  } else if (n.url) {
    window.open(n.url, '_blank', 'noopener')
  } else {
    window.open(`/article/${n.id}`, '_blank', 'noopener')
  }
  resetNoticeTimer()
}

function nextNotice() {
  if (!notices.value.length) return
  noticeIndex.value = (noticeIndex.value + 1) % notices.value.length
  resetNoticeTimer()
}

function prevNotice() {
  if (!notices.value.length) return
  noticeIndex.value = (noticeIndex.value - 1 + notices.value.length) % notices.value.length
  resetNoticeTimer()
}

function pauseNotice() {
  if (noticeTimer) {
    clearInterval(noticeTimer)
    noticeTimer = null
  }
}

function resumeNotice() {
  resetNoticeTimer()
}

function resetNoticeTimer() {
  pauseNotice()
  if (notices.value.length > 1) {
    noticeTimer = setInterval(() => {
      noticeIndex.value = (noticeIndex.value + 1) % notices.value.length
    }, NOTICE_INTERVAL_MS)
  }
}

async function fetchNotices() {
  try {
    const { data } = await axios.get('/api/cms/home-notices')
    notices.value = data.notices || []
    noticeIndex.value = 0
    resetNoticeTimer()
  } catch (e) {
    notices.value = []
    console.error('获取通知公告失败:', e)
  }
}

// 今日值班（值班表为可选功能，接口异常时静默隐藏展示区）
const dutyShifts = ref([])
const dutyNote = ref('')

function isNightShift(shift) {
  return /夜|晚/.test(shift || '')
}

async function fetchDuty() {
  try {
    const response = await axios.get('/api/duty/today')
    dutyShifts.value = response.data.shifts || []
    dutyNote.value = dutyShifts.value.map(s => s.note).find(Boolean) || ''
  } catch (error) {
    console.error('获取今日值班失败:', error)
  }
}

// 值班数据（今日白班已上报则显示今日，否则回退昨日；值班记录为可选功能，异常时静默）
const recordData = ref({
  dayLabel: '今日',
  day: { reported: null, accepted: null, completed: null },
  month: { reported: 0, accepted: 0, completed: 0 },
})

function localDateStr(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function dayStatsFromStatus(status) {
  const day = status?.['白班']
  const filled = !!day?.filled
  const stats = day?.stats || {}
  return {
    filled,
    day: {
      reported: filled ? (stats.stat_reported ?? null) : null,
      accepted: filled ? (stats.stat_accepted ?? null) : null,
      completed: filled ? (stats.stat_completed ?? null) : null,
    },
  }
}

async function fetchRecordStatus() {
  try {
    const today = new Date()
    const todayStr = localDateStr(today)
    const todayRes = await axios.get('/api/duty-record/status', { params: { date: todayStr } })
    const todayView = dayStatsFromStatus(todayRes.data)

    if (todayView.filled) {
      recordData.value = {
        dayLabel: '今日',
        day: todayView.day,
        month: todayRes.data.month_sums || { reported: 0, accepted: 0, completed: 0 },
      }
      return
    }

    const yest = new Date(today)
    yest.setDate(yest.getDate() - 1)
    const yestStr = localDateStr(yest)
    try {
      const yestRes = await axios.get('/api/duty-record/status', { params: { date: yestStr } })
      const yestView = dayStatsFromStatus(yestRes.data)
      recordData.value = {
        dayLabel: '昨日',
        day: yestView.day,
        // 本月汇总仍取今日接口（同月时一致；跨月时以上月 31/1 日接口可能不同，以今日 month_sums 为准）
        month: todayRes.data.month_sums || { reported: 0, accepted: 0, completed: 0 },
      }
    } catch {
      recordData.value = {
        dayLabel: '昨日',
        day: { reported: null, accepted: null, completed: null },
        month: todayRes.data.month_sums || { reported: 0, accepted: 0, completed: 0 },
      }
    }
  } catch (error) {
    console.error('获取值班数据失败:', error)
  }
}

const RD_LABELS = { reported: '上报', accepted: '受理', completed: '办结' }

function rdLabel(k) {
  return RD_LABELS[k]
}

function rdNum(v) {
  if (v == null || v === '') return '—'
  return Number(v).toLocaleString('zh-CN')
}

function goDutyRecord() {
  router.push('/duty-record')
}

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  currentDate.value = now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
}

async function fetchColumns() {
  try {
    const response = await axios.get('/api/cms/home-columns')
    columns.value = response.data || []
  } catch (error) {
    console.error('获取栏目文章失败:', error)
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}-${date.getDate()}`
}

function viewArticle(article) {
  // 如果是HTML格式的数据分析报告，直接新窗口打开
  if (article.file_path && article.file_path.toLowerCase().endsWith('.html')) {
    const url = article.file_path.startsWith('/') ? article.file_path : '/' + article.file_path
    window.open(url, '_blank')
    return
  }
  router.push(`/article/${article.id}`)
}

function viewMore(column) {
  router.push(`/category/${column.id}`)
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  fetchColumns()
  fetchNotices()
  fetchDuty()
  fetchRecordStatus()
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
  pauseNotice()
})
</script>

<style scoped>
.home-page {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.welcome-content {
  flex: 1 1 auto;
  min-width: 0;
}

.welcome-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
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

/* 通知公告条：欢迎条下方、文章块上方（与上下卡片同底同边框） */
.notice-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 42px;
  padding: 8px var(--space-5);
  margin-bottom: var(--space-6);
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
}

.notice-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-500);
}

.notice-arrow {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: var(--fill-light);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.notice-arrow:hover {
  background: var(--primary-50);
  color: var(--primary-500);
}

.notice-link {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notice-link:hover {
  color: var(--primary-500);
}

.notice-dots {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
}

.notice-dot {
  width: 7px;
  height: 7px;
  border: none;
  border-radius: 50%;
  padding: 0;
  background: var(--border-light);
  cursor: pointer;
}

.notice-dot.active {
  background: var(--primary-500);
  width: 16px;
  border-radius: 999px;
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

/* 今日值班展示区 */
.welcome-duty {
  border-left: 1px solid var(--border-lighter);
  padding-left: var(--space-6);
  margin-right: var(--space-6);
  flex: 0 1 auto;
  min-width: 200px;
}

.duty-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}

.duty-note-tag {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(230, 162, 60, 0.14);
  color: var(--warning-dark);
}

.duty-shifts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.duty-shift {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.duty-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.duty-chip svg {
  width: 12px;
  height: 12px;
}

.duty-chip.day {
  background: rgba(230, 162, 60, 0.14);
  color: var(--warning-dark);
}

.duty-chip.night {
  background: rgba(99, 102, 241, 0.15);
  color: #5a5fd0;
}

.duty-members {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 0;
  white-space: nowrap;
  line-height: 1.4;
}

[data-theme="dark"] .duty-chip.day {
  color: var(--warning);
}

[data-theme="dark"] .duty-chip.night {
  color: #a5b4fc;
}

[data-theme="dark"] .duty-note-tag {
  color: var(--warning);
}

/* 值班数据展示区 */
.welcome-record {
  border-left: 1px solid var(--border-lighter);
  padding-left: var(--space-6);
  margin-right: var(--space-6);
  cursor: pointer;
}

.welcome-record:hover .record-label {
  color: var(--primary-500);
}

.record-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
  transition: color var(--transition-fast);
}

.record-data-rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.record-data-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
}

.rd-tag {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
}

.rd-tag--day {
  background: rgba(64, 158, 255, 0.14);
  color: var(--primary-500);
}

.rd-tag--yesterday {
  background: rgba(230, 162, 60, 0.16);
  color: var(--warning, #e6a23c);
}

.rd-tag--month {
  background: rgba(103, 194, 58, 0.16);
  color: var(--success-dark);
}

[data-theme="dark"] .rd-tag--month {
  color: var(--success);
}

.rd-item {
  font-size: 12px;
  color: var(--text-tertiary);
}

.rd-item b {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  margin-left: 2px;
  font-variant-numeric: tabular-nums;
}

.rd-item b.empty {
  color: var(--text-placeholder);
  font-weight: 400;
}

.cms-section {
  margin-bottom: var(--space-6);
}

.cms-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(280px, 1fr));
  gap: var(--space-4);
}

.cms-column {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
  min-width: 0;
  overflow: hidden;
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

@media (max-width: 768px) {
  .welcome-banner {
    flex-direction: column;
    text-align: center;
    gap: var(--space-4);
  }

  .welcome-time {
    text-align: center;
  }

  .welcome-duty {
    border-left: none;
    padding-left: 0;
    margin-right: 0;
    width: 100%;
  }

  .welcome-record {
    border-left: none;
    padding-left: 0;
    margin-right: 0;
    width: 100%;
  }

  .duty-label {
    justify-content: center;
  }

  .duty-shifts {
    align-items: center;
  }

  .record-label {
    text-align: center;
  }

  .record-data-rows {
    align-items: center;
  }

  .cms-columns {
    grid-template-columns: 1fr;
  }
}
</style>
