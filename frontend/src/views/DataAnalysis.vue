<template>
  <div class="analysis-page">
    <!-- 左侧面板 -->
    <aside class="analysis-sidebar">
      <div class="sidebar-head">
        <KbIcon name="bar-chart" :size="16" />
        <span>数据分析</span>
      </div>
      <div class="sidebar-body">
      

      <div class="sidebar-section">
        <h3 class="section-title">已上传数据</h3>
        <div v-if="months.length === 0" class="empty-hint">暂无数据</div>
        <div v-for="m in months" :key="m.batch" class="month-item" :class="{ active: selectedMonths.includes(m.batch) }" @click="toggleMonth(m.batch)">
          <span class="month-label">{{ formatBatch(m.batch) }}</span>
          <span class="month-count">{{ m.count }}条</span>
        </div>
        <div v-if="months.length > 0" class="month-actions">
          <button class="btn-text" @click="selectAllMonths">全选</button>
          <button class="btn-text" @click="selectedMonths = []">清空</button>
        </div>
      </div>

      <div class="sidebar-section">
        <h3 class="section-title">快捷分析</h3>
        <div class="quick-queries">
          <button v-for="q in quickQueries" :key="q" class="quick-btn" @click="sendQuery(q)">{{ q }}</button>
        </div>
      </div>

      <div class="sidebar-section">
        <h3 class="section-title">报告模板</h3>
        <div v-if="templatesLoading" class="loading-hint">加载中...</div>
        <div v-else-if="reportTemplates.length === 0" class="empty-hint">暂无模板</div>
        <div v-else class="template-list">
          <div v-for="tpl in reportTemplates" :key="tpl.id" class="template-item" @click="selectTemplate(tpl)">
            <div class="template-info">
              <span class="template-name">{{ tpl.name }}</span>
              <span class="template-meta">{{ tpl.section_count }}个章节 · {{ tpl.report_type === 'compare' ? '对比' : '单月' }}</span>
            </div>
            <div class="template-actions">
              <button class="template-exec-btn" @click.stop="executeAndExport(tpl)" :disabled="loading" title="生成报告并下载">
                <KbIcon name="download" :size="14" />
                <span>生成报告</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      </div>
    </aside>

    <!-- 主聊天区域 -->
    <main class="analysis-main">
      <div class="chat-messages" ref="chatContainer">
        <div v-if="messages.length === 0" class="welcome-screen">
          <div class="welcome-icon"><KbIcon name="bar-chart" :size="30" /></div>
          <h2>案件数据分析助手</h2>
          <p>上传Excel数据后，在下方输入分析需求，AI将为你生成分析结果</p>
          <p class="welcome-hint">也可在左侧"报告模板"中选择预设模板一键生成报告</p>
          <div class="welcome-examples">
            <span>试试问：</span>
            <button @click="sendQuery('各片区案件数量统计')">各片区案件数量统计</button>
            <button @click="sendQuery('街面秩序类案件最多的街道是哪些')">街面秩序类案件最多的街道</button>
            <button @click="sendQuery('本月案件处理效率分析')">案件处理效率分析</button>
          </div>
        </div>

        <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
          <div class="message-avatar" :class="msg.role">
            <KbIcon :name="msg.role === 'user' ? 'user' : 'bot'" :size="18" />
          </div>
          <div class="message-content">
            <div class="message-text" v-html="renderMarkdown(msg.text)"></div>
            <div v-if="msg.chart" class="message-chart" :id="'chart-' + msg.id"></div>
            <div v-if="msg.tableData && msg.tableData.length" class="message-table-wrap">
              <table class="message-table">
                <thead>
                  <tr><th v-for="col in getTableColumns(msg.tableData)" :key="col">{{ col }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in msg.tableData" :key="ri">
                    <td v-for="col in getTableColumns(msg.tableData)" :key="col"
                        :class="{ 'num-cell': isNumeric(row[col]) }">
                      {{ formatCellValue(row[col]) }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-more">共 {{ msg.tableData.length }} 条</div>
            </div>
          </div>
        </div>

        <div v-if="loading" class="message assistant">
          <div class="message-avatar assistant"><KbIcon name="bot" :size="18" /></div>
          <div class="message-content">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <textarea
            v-model="inputText"
            @keydown.enter.exact.prevent="sendMessage"
            placeholder="输入分析需求，如：各片区案件数量统计..."
            rows="1"
          ></textarea>
          <button class="send-btn" @click="sendMessage" :disabled="!inputText.trim() || loading">
            <KbIcon name="send" :size="18" />
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import axios from 'axios'
import { useThemeStore } from '../stores/theme'
import { chartTemplates, COLORS, fmtNum, getOrInitChart, disposeEcharts, setChartTheme } from '../composables/useEcharts'
import { formatBatch, getTableColumns, isNumeric, formatCellValue, renderMarkdown } from '../utils/analysisFormat'
import KbIcon from '../components/common/KbIcon.vue'

const API_BASE = '/api/analysis'
const themeStore = useThemeStore()

// 状态
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const months = ref([])
const selectedMonths = ref([])
const chatContainer = ref(null)
let msgSeq = 0

const quickQueries = [
  '各片区案件数量统计',
  '大类案件分布',
  '各处置部门案件数量排名',
  '案件处理时效分析',
  '延期和返工案件统计',
]

// 报告模板
const reportTemplates = ref([])
const templatesLoading = ref(false)


// 加载已上传月份
async function loadMonths() {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get(`${API_BASE}/months`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    months.value = res.data.months || []
  } catch (e) {
    console.error('加载月份失败:', e)
  }
}

// 选择/取消月份
function toggleMonth(batch) {
  const idx = selectedMonths.value.indexOf(batch)
  if (idx >= 0) {
    selectedMonths.value.splice(idx, 1)
  } else {
    selectedMonths.value.push(batch)
  }
}

function selectAllMonths() {
  selectedMonths.value = months.value.map(m => m.batch)
}

// 上传文件






// 发送查询
function sendQuery(text) {
  inputText.value = text
  sendMessage()
}

async function sendMessage() {
  const question = inputText.value.trim()
  if (!question || loading.value) return

  messages.value.push({ id: ++msgSeq, role: 'user', text: question })
  inputText.value = ''
  loading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const token = localStorage.getItem('token')
    const res = await axios.post(`${API_BASE}/query`, {
      question,
      months: selectedMonths.value.length > 0 ? selectedMonths.value : undefined
    }, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    })
    const data = res.data

    const assistantMsg = {
      id: ++msgSeq,
      role: 'assistant',
      text: data.answer || data.error || '未获取到分析结果',
      chart: data.chart || null,
      tableData: data.table_data || null,
    }
    messages.value.push(assistantMsg)

    await nextTick()
    scrollToBottom()

    if (data.chart) {
      renderChart(data.chart, assistantMsg.id)
    }
  } catch (e) {
    messages.value.push({ id: ++msgSeq, role: 'assistant', text: '请求失败: ' + (e.response?.data?.error || e.message) })
  } finally {
    loading.value = false
  }
}

function renderChart(chartSpec, msgId) {
  nextTick(() => {
    const container = document.getElementById('chart-' + msgId)
    if (!container) return

    const templateFn = chartTemplates[chartSpec.chart_type] || chartTemplates.bar
    const option = templateFn(chartSpec.title, chartSpec.data, chartSpec.x_field, chartSpec.y_field)

    const chart = getOrInitChart(container, themeStore.theme === 'light' ? 'light' : 'dark')
    chart.setOption(option, true)
  })
}

// 滚动到底部
function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 加载报告模板
async function loadTemplates() {
  templatesLoading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/report-templates', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    reportTemplates.value = res.data.templates || []
  } catch (e) {
    console.error('加载模板失败:', e)
  } finally {
    templatesLoading.value = false
  }
}

// 执行模板并直接导出Word文档
async function executeAndExport(tpl) {
  if (loading.value) return

  // Validate month selection for comparison templates
  const isCompare = tpl.report_type === 'compare' || tpl.name.includes('对比')
  if (isCompare && selectedMonths.value.length < 2) {
    messages.value.push({ role: 'user', text: `生成报告: ${tpl.name}` })
    messages.value.push({ role: 'assistant', text: `对比分析报告至少需要选择2个月的数据，当前只选择了${selectedMonths.value.length}个月。请在左侧"已上传数据"中选择至少2个月的数据。` })
    return
  }

  messages.value.push({ role: 'user', text: `生成报告: ${tpl.name}` })
  messages.value.push({ role: 'assistant', text: `正在生成 "${tpl.name}" 报告，请稍候...` })
  loading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const token = localStorage.getItem('token')
    const params = new URLSearchParams()
    if (selectedMonths.value.length > 0) {
      params.set('months', selectedMonths.value.join(','))
    }
    const queryString = params.toString()
    const url = `/api/report-templates/${tpl.id}/export${queryString ? '?' + queryString : ''}`

    const res = await axios.get(url, {
      headers: { 'Authorization': `Bearer ${token}` },
      responseType: 'blob'
    })

    const blob = res.data
    // Extract filename from Content-Disposition header
    const disposition = res.headers['content-disposition']
    let filename = `${tpl.name}.docx`
    if (disposition) {
      const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;\n]+)/i)
      if (match) {
        filename = decodeURIComponent(match[1].replace(/['"]/g, ''))
      }
    }
    const blobUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(blobUrl)
    document.body.removeChild(a)

    messages.value.push({
      role: 'assistant',
      text: `报告 "${filename}" 已生成并开始下载`,
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', text: '报告生成失败: ' + e.message })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

onMounted(() => {
  setChartTheme(themeStore.theme)
  loadMonths()
  loadTemplates()
})

// 主题切换时，重新渲染所有已展示的图表，使其配色跟随浅色/深色模式
watch(() => themeStore.theme, async (t) => {
  setChartTheme(t)
  await nextTick()
  messages.value.forEach(m => {
    if (m.chart) renderChart(m.chart, m.id)
  })
})

onUnmounted(() => {
  document.querySelectorAll('.message-chart, .section-chart').forEach(el => disposeEcharts(el))
})
</script>

<style scoped>
.analysis-page {
  height: 100%;
  display: flex;
  overflow: hidden;
  gap: var(--space-4);
  padding: var(--space-2);
}

/* 左侧面板 */
.analysis-sidebar {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.sidebar-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-title {
  font-size: 13px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 10px;
}




.month-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}
.month-item:hover {
  background: var(--primary-100);
}
.month-item.active {
  background: var(--primary-50);
  color: var(--primary-500);
}
.month-count {
  font-size: 11px;
  color: var(--text-tertiary);
}
.month-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.btn-text {
  background: none;
  border: none;
  color: var(--primary-500);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
}
.btn-text:hover {
  text-decoration: underline;
}

.empty-hint {
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 8px 0;
}

.quick-queries {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.quick-btn {
  background: var(--primary-50);
  border: 1px solid var(--primary-50);
  color: var(--text-secondary);
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  text-align: left;
  transition: all 0.2s;
}
.quick-btn:hover {
  background: var(--primary-100);
  color: #ffffff;
}

/* 报告模板 */
.loading-hint {
  color: var(--text-tertiary);
  font-size: 12px;
  padding: 8px 0;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.template-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: var(--primary-50);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-item:hover {
  background: rgba(64, 158, 255, 0.12);
  border-color: color-mix(in srgb, var(--primary-500) 40%, transparent);
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.template-name {
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.template-meta {
  font-size: 10px;
  color: var(--text-tertiary);
}

.template-exec-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: 13px;
  background: var(--primary-50);
  border: none;
  color: var(--primary-500);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-shrink: 0;
  transition: all 0.2s;
  font-size: 12px;
  white-space: nowrap;
}

.template-exec-btn:hover:not(:disabled) {
  background: var(--primary-500);
  color: #ffffff;
}

.template-exec-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.template-actions {
  display: flex;
  gap: 4px;
}

/* 主聊天区域 */
.analysis-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  gap: 12px;
}
.welcome-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-500);
  background: linear-gradient(135deg, var(--primary-50), var(--primary-50));
  box-shadow: 0 10px 28px -10px var(--primary-600);
  margin-bottom: 4px;
}
.welcome-screen h2 {
  font-size: 24px;
  color: var(--text-primary);
  margin: 0;
}
.welcome-screen p {
  color: var(--text-secondary);
  font-size: 14px;
}
.welcome-hint {
  color: var(--primary-500);
  font-size: 13px;
  margin-top: -4px;
}
.welcome-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  align-items: center;
}
.welcome-examples span {
  color: var(--text-tertiary);
  font-size: 13px;
}
.welcome-examples button {
  background: var(--primary-100);
  border: 1px solid rgba(64, 158, 255, 0.25);
  color: var(--primary-500);
  padding: 6px 14px;
  border-radius: 16px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.welcome-examples button:hover {
  background: var(--primary-50);
}

.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
  min-width: 0;
}
.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--fill-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
  border: 1px solid var(--border-lighter);
}
.message.user .message-avatar {
  color: var(--text-tertiary);
}
.message.assistant .message-avatar {
  color: #fff;
  background: var(--primary-500);
  border-color: var(--primary-500);
}
.message-content {
  background: var(--fill-light);
  border: 1px solid var(--border-lighter);
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: break-word;
  word-break: break-word;
  min-width: 0;
}
.message.user .message-content {
  background: var(--primary-100);
  border-color: var(--primary-50);
}

.message-chart {
  width: 100%;
  height: 400px;
  margin-top: 12px;
  border-radius: 8px;
  overflow: hidden;
}

.message-table-wrap {
  margin-top: 12px;
  max-height: 320px;
  overflow-y: auto;
  border-radius: 8px;
  border: 1px solid var(--border-lighter);
}

.message-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.message-table th {
  background: rgba(64, 158, 255, 0.12);
  color: var(--text-primary);
  padding: 8px 12px;
  text-align: left;
  font-weight: 500;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid var(--border-lighter);
}
.message-table td {
  padding: 6px 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-lighter);
}
.message-table tbody tr:nth-child(even) {
  background: var(--border-lighter);
}
.message-table tbody tr:hover {
  background: var(--primary-50);
}
.message-table td.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.table-more {
  text-align: center;
  padding: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
}

/* 输入区域 */
.chat-input-area {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-lighter);
}
.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--fill-light);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 8px 12px;
}
.input-wrapper textarea {
  flex: 1;
  background: none;
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  max-height: 120px;
}
.input-wrapper textarea::placeholder {
  color: var(--text-tertiary);
}
.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary-500);
  border: none;
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s;
}
.send-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary-500) 85%, #000);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  animation: typing 1.4s infinite;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* ============ 响应式（与知识库一致） ============ */
@media (max-width: 860px) {
  .analysis-page {
    flex-direction: column;
    overflow-y: auto;
  }
  .analysis-sidebar {
    width: 100%;
    max-height: 45vh;
  }
  .analysis-main {
    min-height: 55vh;
  }
}
</style>
