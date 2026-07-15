<template>
  <div class="knowledge-page">
    <!-- 欢迎页（无对话时显示） -->
    <div v-if="!chatHistory.length" class="welcome-container">
      <div class="welcome-card">
        <div class="welcome-icon">🏛️</div>
        <h1 class="welcome-title">城市管理知识库</h1>
        <p class="welcome-desc">我是城市管理AI助手，可以帮您解答城市管理相关问题，包括职责归属、处置时限、法律法规等</p>

        <div class="welcome-input">
          <textarea
            v-model="question"
            placeholder="请输入城市管理相关问题..."
            rows="2"
            @keydown.enter.exact.prevent="askQuestion"
          ></textarea>
          <button class="send-btn" @click="askQuestion" :disabled="asking || !question.trim()">
            <span v-if="asking">⏳</span>
            <span v-else>↑</span>
          </button>
        </div>

        <div class="quick-questions">
          <p class="quick-title">或者试试这些热门问题</p>
          <div class="quick-list">
            <button
              v-for="q in quickQuestions"
              :key="q"
              class="quick-btn"
              @click="askQuickQuestion(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <div class="stats-bar">
          <span class="stat-item">
            <span class="stat-num">{{ unifiedStats.total_vectors || 0 }}</span>
            <span class="stat-label">知识条目</span>
          </span>
          <span class="stat-divider">|</span>
          <span class="stat-item">
            <span class="stat-num">{{ unifiedStats.standards?.parents || 0 }}</span>
            <span class="stat-label">立结案标准</span>
          </span>
          <span class="stat-divider">|</span>
          <span class="stat-item">
            <span class="stat-num">{{ unifiedStats.general?.doc_count || 0 }}</span>
            <span class="stat-label">通用文档</span>
          </span>
        </div>
      </div>
    </div>

    <!-- 对话模式 -->
    <div v-else class="chat-container">
      <div class="chat-header">
        <h2 class="chat-title">城市管理知识库</h2>
        <button class="clear-btn" @click="clearChat">新建对话</button>
      </div>

      <!-- 对话消息列表 -->
      <div class="chat-messages" ref="chatMessagesRef">
        <div v-for="(msg, i) in chatHistory" :key="i" class="chat-msg" :class="msg.role">
          <div class="msg-avatar" v-if="msg.role === 'assistant'">
            <span class="avatar-icon">🤖</span>
          </div>
          <div class="msg-content">
            <div class="chat-bubble" v-html="renderMarkdown(msg.content)"></div>
            <div class="chat-sources" v-if="msg.sources && msg.sources.length">
              <span class="source-label">来源：</span>
              <span class="source-tag" v-for="s in msg.sources" :key="s">{{ s }}</span>
            </div>
            <div class="chat-actions" v-if="msg.role === 'assistant'">
              <button class="action-btn" @click="copyMessage(msg.content)">复制</button>
            </div>
          </div>
        </div>
        <div v-if="asking" class="chat-msg assistant">
          <div class="msg-avatar">
            <span class="avatar-icon">🤖</span>
          </div>
          <div class="msg-content">
            <div class="chat-bubble typing">
              <span class="typing-text">思考中</span>
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <div class="location-bar" v-if="hasLocation">
          <span class="location-badge">📍 已定位: {{ selectedLng }}, {{ selectedLat }}</span>
          <button class="location-clear" @click="clearLocation">×</button>
        </div>
        <div class="input-wrapper">
          <textarea
            v-model="question"
            placeholder="输入城市管理相关问题..."
            rows="2"
            @keydown.enter.exact.prevent="askQuestion"
            ref="textareaRef"
          ></textarea>
          <button class="send-btn" @click="askQuestion" :disabled="asking || !question.trim()">
            <span v-if="asking" class="send-loading">⏳</span>
            <span v-else class="send-icon">↑</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 需要位置提示弹窗 -->
    <div class="location-modal" v-if="needLocation && !hasLocation">
      <div class="modal-mask" @click="needLocation = false"></div>
      <div class="modal-content">
        <div class="modal-header">
          <h3>需要定位位置</h3>
          <button class="modal-close" @click="needLocation = false">×</button>
        </div>
        <p>您的问题涉及区域判定，请在地图上点选具体位置</p>
        <div class="modal-map">
          <div ref="modalMapRef" class="amap"></div>
        </div>
        <div class="location-row">
          <input v-model="selectedLng" placeholder="经度" readonly />
          <input v-model="selectedLat" placeholder="纬度" readonly />
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="needLocation = false">取消</button>
          <button class="btn-confirm" @click="confirmLocation" :disabled="!hasLocation">确认位置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'

// 统一统计
const unifiedStats = ref({ total_vectors: 0, general: {}, standards: {} })

// 问答状态
const question = ref('')
const asking = ref(false)
const chatHistory = ref([])
const chatMessagesRef = ref(null)
const textareaRef = ref(null)

// 地图状态
const modalMapRef = ref(null)
const mapInitError = ref('')
const selectedLng = ref('')
const selectedLat = ref('')
const needLocation = ref(false)

let modalMapInstance = null
let pointMarker = null

// 快捷问题
const quickQuestions = [
  '井盖破损的处置时限是多少？',
  '路灯不亮找哪个部门？',
  '道路破损归谁管理？',
  '绿化带内水管破裂怎么处理？',
  '占道经营如何处理？',
  '垃圾清理标准是什么？'
]

// 计算属性
const hasLocation = computed(() => {
  return selectedLng.value !== '' && selectedLat.value !== '' &&
         !isNaN(Number(selectedLng.value)) && !isNaN(Number(selectedLat.value))
})

// Markdown渲染（简易版）
function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^### (.*$)/gm, '<h4>$1</h4>')
    .replace(/^## (.*$)/gm, '<h3>$1</h3>')
    .replace(/^# (.*$)/gm, '<h2>$1</h2>')
    .replace(/^- (.*$)/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.*$)/gm, '<li>$2</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

// 获取token
function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
}

// 快捷问题点击
function askQuickQuestion(q) {
  question.value = q
  nextTick(() => askQuestion())
}

// 复制消息
function copyMessage(content) {
  navigator.clipboard.writeText(content).catch(() => {
    // fallback
    const textarea = document.createElement('textarea')
    textarea.value = content
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  })
}

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (chatMessagesRef.value) {
      chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
    }
  })
}

// 加载统一统计
async function loadStats() {
  try {
    const res = await fetch('/api/kb/stats', {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    unifiedStats.value = data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

// 统一问答
async function askQuestion() {
  if (!question.value.trim()) return

  asking.value = true
  const currentQuestion = question.value.trim()

  // 追加用户消息到对话历史
  chatHistory.value.push({ role: 'user', content: currentQuestion })
  question.value = ''
  scrollToBottom()

  try {
    const location = hasLocation.value
      ? { lng: Number(selectedLng.value), lat: Number(selectedLat.value) }
      : null

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 90000)

    const res = await fetch('/api/kb/ask', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        question: currentQuestion,
        location,
        history: chatHistory.value.slice(0, -1)
      }),
      signal: controller.signal
    })
    clearTimeout(timeoutId)

    const rawText = await res.text()
    let data = null
    if (rawText) {
      try {
        data = JSON.parse(rawText)
      } catch (parseError) {
        throw new Error(`接口返回非JSON内容（状态码 ${res.status}）`)
      }
    }

    if (!res.ok) {
      const errMsg = data?.error || data?.answer || `请求失败（状态码 ${res.status}）`
      throw new Error(errMsg)
    }

    if (!data) {
      throw new Error(`接口返回为空（状态码 ${res.status}）`)
    }

    // 检查是否需要位置信息
    if (data.need_location) {
      needLocation.value = true
      chatHistory.value.push({
        role: 'assistant',
        content: data.message || '请在地图上点选具体位置'
      })
      scrollToBottom()
      return
    }

    // 追加AI回答到对话历史
    chatHistory.value.push({
      role: 'assistant',
      content: data.answer,
      sources: data.sources
    })
    scrollToBottom()
  } catch (e) {
    const errMsg = e.name === 'AbortError' ? '请求超时，请稍后重试' : '查询失败: ' + e.message
    chatHistory.value.push({ role: 'assistant', content: errMsg })
    scrollToBottom()
  } finally {
    asking.value = false
  }
}

// 清空对话
function clearChat() {
  chatHistory.value = []
  needLocation.value = false
  selectedLng.value = ''
  selectedLat.value = ''
}

// 确认位置
function confirmLocation() {
  needLocation.value = false
  if (question.value.trim()) {
    askQuestion()
  }
}

// 统一检索
async function searchKnowledge() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  searchResults.value = []
  try {
    const res = await fetch('/api/kb/search', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ query: searchQuery.value })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '请求失败')
    searchResults.value = data.results || []
  } catch (e) {
    console.error('知识检索失败:', e)
  } finally {
    searching.value = false
  }
}

// ================= 地图相关 =================

async function ensureAmapReady(timeoutMs = 8000) {
  const start = Date.now()
  while (!window.AMap && Date.now() - start < timeoutMs) {
    await new Promise(resolve => setTimeout(resolve, 120))
  }
  return Boolean(window.AMap)
}

async function initModalMap() {
  if (modalMapInstance || !modalMapRef.value) return
  const amapReady = await ensureAmapReady()
  if (!amapReady || !window.AMap) {
    mapInitError.value = '地图加载失败，请刷新后重试'
    return
  }
  mapInitError.value = ''
  modalMapInstance = new window.AMap.Map(modalMapRef.value, {
    zoom: 12,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: 'amap://styles/normal'
  })

  modalMapInstance.on('click', (event) => {
    const lng = event?.lnglat?.getLng?.()
    const lat = event?.lnglat?.getLat?.()
    if (typeof lng !== 'number' || typeof lat !== 'number') return
    selectedLng.value = String(Number(lng.toFixed(6)))
    selectedLat.value = String(Number(lat.toFixed(6)))
    setModalMapMarker(lng, lat)
  })
}

function setModalMapMarker(lng, lat) {
  if (!modalMapInstance || !window.AMap) return
  if (!pointMarker) {
    pointMarker = new window.AMap.Marker({
      map: modalMapInstance,
      anchor: 'bottom-center',
      offset: new window.AMap.Pixel(0, -2)
    })
  }
  pointMarker.setPosition([lng, lat])
}

function clearLocation() {
  selectedLng.value = ''
  selectedLat.value = ''
  if (pointMarker) {
    pointMarker.setPosition([0, 0])
    pointMarker = null
  }
}

// 初始化
onMounted(() => {
  loadStats()
})

// 监听需要位置的弹窗
watch(needLocation, async (show) => {
  if (show) {
    await nextTick()
    await initModalMap()
    setTimeout(() => {
      modalMapInstance?.resize?.()
    }, 100)
  }
})

onUnmounted(() => {
  if (modalMapInstance) {
    modalMapInstance.destroy()
  }
  modalMapInstance = null
  pointMarker = null
})
</script>

<style scoped>
.knowledge-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ========== 欢迎页 ========== */
.welcome-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}

.welcome-card {
  text-align: center;
  max-width: 600px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: var(--space-4);
}

.welcome-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.welcome-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-6);
}

.welcome-input {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
  max-width: 500px;
  margin: 0 auto var(--space-6);
}

.welcome-input textarea {
  flex: 1;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  font-size: 14px;
  resize: none;
  background: var(--bg-card);
  color: var(--text-primary);
  line-height: 1.5;
}

.welcome-input textarea:focus {
  outline: none;
  border-color: var(--primary-500);
}

.welcome-input .send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
}

.welcome-input .send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quick-questions {
  margin-bottom: var(--space-6);
}

.quick-title {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}

.quick-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-500);
  background: var(--primary-50);
}

.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--fill-light);
  border-radius: var(--radius-lg);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-500);
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-divider {
  color: var(--border-light);
}

/* ========== 对话模式 ========== */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
  background: var(--bg-card);
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.clear-btn {
  padding: var(--space-1) var(--space-3);
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.clear-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-500);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--bg-base);
}

.chat-msg {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}

.chat-msg.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
}

.avatar-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--primary-500);
  border-radius: var(--radius-md);
  font-size: 18px;
}

.msg-content {
  flex: 1;
  min-width: 0;
}

.chat-msg.user .msg-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.chat-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  line-height: 1.7;
  font-size: 14px;
}

.chat-msg.user .chat-bubble {
  background: var(--primary-500);
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-msg.assistant .chat-bubble {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-lighter);
  border-bottom-left-radius: 4px;
}

.chat-bubble :deep(h2),
.chat-bubble :deep(h3),
.chat-bubble :deep(h4) {
  margin: var(--space-2) 0 var(--space-1);
  font-weight: 600;
}

.chat-bubble :deep(ul),
.chat-bubble :deep(ol) {
  margin: var(--space-2) 0;
  padding-left: var(--space-4);
}

.chat-bubble :deep(li) {
  margin-bottom: 4px;
}

.chat-bubble :deep(code) {
  padding: 2px 6px;
  background: var(--fill-light);
  border-radius: 4px;
  font-size: 13px;
}

.chat-bubble :deep(strong) {
  font-weight: 600;
}

.chat-sources {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-lighter);
}

.source-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.source-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--primary-50);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
}

.chat-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.action-btn {
  font-size: 12px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 8px;
}

.action-btn:hover {
  color: var(--primary-500);
}

/* 输入区 */
.chat-input-area {
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border-top: 1px solid var(--border-lighter);
}

.location-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.location-badge {
  font-size: 12px;
  padding: 4px 10px;
  background: var(--primary-50);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
}

.location-clear {
  font-size: 14px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
}

.input-wrapper {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
}

.input-wrapper textarea {
  flex: 1;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  font-size: 14px;
  resize: none;
  background: var(--bg-base);
  color: var(--text-primary);
  line-height: 1.5;
  max-height: 120px;
}

.input-wrapper textarea:focus {
  outline: none;
  border-color: var(--primary-500);
}

.send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: opacity 0.2s;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-icon {
  font-size: 18px;
  font-weight: bold;
}

.send-loading {
  font-size: 16px;
}

/* 打字动画 */
.typing {
  display: flex;
  align-items: center;
  gap: 4px;
}

.typing-text {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-right: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: bounce 1.2s infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}

/* ========== 定位弹窗 ========== */
.location-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.modal-content {
  position: relative;
  width: 500px;
  max-width: 90vw;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  z-index: 1;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  font-size: 20px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
}

.modal-content p {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}

.modal-map {
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: var(--space-3);
}

.modal-map .amap {
  height: 300px;
  width: 100%;
  cursor: crosshair;
}

.location-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.location-row input {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.btn-cancel {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
}

.btn-confirm {
  padding: var(--space-2) var(--space-3);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
