<template>
  <div class="analysis-page">
    <!-- 左侧面板 -->
    <aside class="analysis-sidebar">
      <div class="sidebar-section">
        <h3 class="section-title">数据上传</h3>
        <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
          <input type="file" ref="fileInput" accept=".xlsx,.xls" @change="handleFileSelect" hidden />
          <div class="upload-content" @click="$refs.fileInput.click()">
            <KbIcon name="upload" :size="32" :stroke-width="1.5" class="upload-icon" />
            <span>点击或拖拽上传Excel</span>
          </div>
          <div v-if="uploading" class="upload-progress">上传中...</div>
          <div v-if="uploadResult" class="upload-result" :class="uploadResult.success ? 'success' : 'error'">
            {{ uploadResult.message }}
          </div>
        </div>
      </div>

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
const uploading = ref(false)
const uploadResult = ref(null)
const chatContainer = ref(null)
let msgSeq = 0
const fileInput = ref(null)

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
async function handleFileSelect(e) {
  const file = e.target.files[0]
  if (file) await uploadFile(file)
}

function handleDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}

async function uploadFile(file) {
  uploading.value = true
  uploadResult.value = null
  try {
    const token = localStorage.getItem('token')
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post(`${API_BASE}/upload`, formData, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = res.data
    uploadResult.value = data
    if (data.success) {
      await loadMonths()
      // 自动选中新上传的月份
      if (data.batch && !selectedMonths.value.includes(data.batch)) {
        selectedMonths.value.push(data.batch)
      }
    }
  } catch (e) {
    uploadResult.value = { success: false, message: '上传失败: ' + e.message }
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

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
  /* 数据分析面板：语义变量（深色为默认，浅色由 [data-theme="light"] 覆盖） */
  .analysis-page {
    --da-bg: #0a1628;
    --da-panel: rgba(13, 31, 60, 0.8);
    --da-text: #e6edf3;
    --da-heading: #ffffff;
    --da-text-dim: rgba(255, 255, 255, 0.62);
    --da-text-faint: rgba(255, 255, 255, 0.4);
    --da-border: rgba(64, 158, 255, 0.15);
    --da-border-soft: rgba(255, 255, 255, 0.08);
    --da-dashed: rgba(64, 158, 255, 0.3);
    --da-accent: #409eff;
    --da-accent-soft: rgba(64, 158, 255, 0.08);
    --da-accent-soft2: rgba(64, 158, 255, 0.15);
    --da-accent-soft3: rgba(64, 158, 255, 0.2);
    --da-accent-strong: rgba(64, 158, 255, 0.6);
    --da-success: #22c55e;
    --da-success-soft: rgba(34, 197, 94, 0.15);
    --da-danger: #ef4444;
    --da-danger-soft: rgba(239, 68, 68, 0.15);
    --da-surface-soft: rgba(255, 255, 255, 0.05);
    --da-grid: rgba(255, 255, 255, 0.04);
    --da-on-accent: #ffffff;
  }
  [data-theme="light"] .analysis-page {
    --da-bg: #f4f7fb;
    --da-panel: #ffffff;
    --da-text: #1f2d3d;
    --da-heading: #16202c;
    --da-text-dim: rgba(31, 45, 61, 0.62);
    --da-text-faint: rgba(31, 45, 61, 0.42);
    --da-border: rgba(64, 158, 255, 0.22);
    --da-border-soft: rgba(31, 45, 61, 0.1);
    --da-dashed: rgba(64, 158, 255, 0.45);
    --da-accent: #2b8cf0;
    --da-accent-soft: rgba(64, 158, 255, 0.08);
    --da-accent-soft2: rgba(64, 158, 255, 0.14);
    --da-accent-soft3: rgba(64, 158, 255, 0.22);
    --da-accent-strong: rgba(64, 158, 255, 0.7);
    --da-success: #16a34a;
    --da-success-soft: rgba(34, 197, 94, 0.12);
    --da-danger: #dc2626;
    --da-danger-soft: rgba(239, 68, 68, 0.1);
    --da-surface-soft: rgba(31, 45, 61, 0.03);
    --da-grid: rgba(31, 45, 61, 0.04);
    --da-on-accent: #ffffff;
  }
.analysis-page {
  display: flex;
  height: calc(100vh - 50px);
  background: var(--da-bg);
  color: var(--da-text);
}

/* 左侧面板 */
.analysis-sidebar {
  width: 260px;
  background: var(--da-panel);
  border-right: 1px solid var(--da-border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 16px;
  gap: 20px;
}

.section-title {
  font-size: 13px;
  color: var(--da-text-dim);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 10px;
}

.upload-area {
  border: 2px dashed var(--da-dashed);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.upload-area:hover {
  border-color: var(--da-accent-strong);
  background: var(--da-accent-soft);
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--da-text-dim);
  font-size: 13px;
}
.upload-icon {
  color: var(--da-accent);
  opacity: 0.9;
  transition: transform 0.2s, opacity 0.2s;
}
.upload-area:hover .upload-icon {
  transform: translateY(-2px);
  opacity: 1;
}

.upload-progress {
  margin-top: 8px;
  color: var(--da-accent);
  font-size: 12px;
}
.upload-result {
  margin-top: 8px;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 4px;
}
.upload-result.success {
  background: var(--da-success-soft);
  color: var(--da-success);
}
.upload-result.error {
  background: var(--da-danger-soft);
  color: var(--da-danger);
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
  background: var(--da-accent-soft2);
}
.month-item.active {
  background: var(--da-accent-soft3);
  color: var(--da-accent);
}
.month-count {
  font-size: 11px;
  color: var(--da-text-faint);
}
.month-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.btn-text {
  background: none;
  border: none;
  color: var(--da-accent);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
}
.btn-text:hover {
  text-decoration: underline;
}

.empty-hint {
  color: var(--da-text-faint);
  font-size: 13px;
  padding: 8px 0;
}

.quick-queries {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.quick-btn {
  background: var(--da-accent-soft);
  border: 1px solid var(--da-accent-soft3);
  color: var(--da-text-dim);
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  text-align: left;
  transition: all 0.2s;
}
.quick-btn:hover {
  background: var(--da-accent-soft2);
  color: var(--da-on-accent);
}

/* 报告模板 */
.loading-hint {
  color: var(--da-text-faint);
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
  background: var(--da-accent-soft);
  border: 1px solid var(--da-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-item:hover {
  background: rgba(64, 158, 255, 0.12);
  border-color: var(--da-dashed);
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
  color: var(--da-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.template-meta {
  font-size: 10px;
  color: var(--da-text-faint);
}

.template-exec-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: 13px;
  background: var(--da-accent-soft3);
  border: none;
  color: var(--da-accent);
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
  background: var(--da-accent);
  color: var(--da-on-accent);
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
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
  color: var(--da-accent);
  background: linear-gradient(135deg, var(--da-accent-soft3), var(--da-accent-soft));
  box-shadow: 0 10px 28px -10px var(--da-accent-strong);
  margin-bottom: 4px;
}
.welcome-screen h2 {
  font-size: 24px;
  color: var(--da-heading);
  margin: 0;
}
.welcome-screen p {
  color: var(--da-text-dim);
  font-size: 14px;
}
.welcome-hint {
  color: var(--da-accent);
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
  color: var(--da-text-faint);
  font-size: 13px;
}
.welcome-examples button {
  background: var(--da-accent-soft2);
  border: 1px solid rgba(64, 158, 255, 0.25);
  color: var(--da-accent);
  padding: 6px 14px;
  border-radius: 16px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.welcome-examples button:hover {
  background: var(--da-accent-soft3);
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
  background: var(--da-accent-soft2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--da-text);
  flex-shrink: 0;
  border: 1px solid var(--da-border-soft);
}
.message.user .message-avatar {
  color: var(--da-text-dim);
}
.message.assistant .message-avatar {
  color: var(--da-accent);
  background: var(--da-accent-soft3);
  border-color: var(--da-accent-soft2);
}
.message-content {
  background: var(--da-surface-soft);
  border: 1px solid var(--da-border-soft);
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: break-word;
  word-break: break-word;
  min-width: 0;
}
.message.user .message-content {
  background: var(--da-accent-soft2);
  border-color: var(--da-accent-soft3);
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
  border: 1px solid var(--da-border-soft);
}

.message-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.message-table th {
  background: rgba(64, 158, 255, 0.12);
  color: var(--da-text);
  padding: 8px 12px;
  text-align: left;
  font-weight: 500;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid var(--da-border-soft);
}
.message-table td {
  padding: 6px 12px;
  color: var(--da-text-dim);
  border-bottom: 1px solid var(--da-grid);
}
.message-table tbody tr:nth-child(even) {
  background: var(--da-grid);
}
.message-table tbody tr:hover {
  background: var(--da-accent-soft);
}
.message-table td.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.table-more {
  text-align: center;
  padding: 8px;
  color: var(--da-text-faint);
  font-size: 12px;
}

/* 输入区域 */
.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--da-border-soft);
}
.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--da-surface-soft);
  border: 1px solid var(--da-border);
  border-radius: 12px;
  padding: 8px 12px;
}
.input-wrapper textarea {
  flex: 1;
  background: none;
  border: none;
  color: var(--da-text);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  max-height: 120px;
}
.input-wrapper textarea::placeholder {
  color: var(--da-text-faint);
}
.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--da-accent);
  border: none;
  color: var(--da-on-accent);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s;
}
.send-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--da-accent) 85%, #000);
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
</style>
