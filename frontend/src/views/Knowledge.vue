<template>
  <div class="knowledge-page">
    <!-- ============ 左侧：知识检索 / 概览面板 ============ -->
    <aside class="kb-aside">
      <div class="kb-aside-head">
        <div class="kb-search">
          <span class="kb-search-icon"><KbIcon name="search" :size="16" /></span>
          <input
            v-model="searchQuery"
            @keyup.enter="runSearch"
            placeholder="搜索知识库：标准 / 职责 / 法规…"
          />
          <button v-if="searchQuery" class="kb-search-clear" @click="clearSearch" title="清空">×</button>
          <button class="kb-search-btn" @click="runSearch" :disabled="searching">搜索</button>
        </div>
        <div class="kb-chips">
          <button class="chip" :class="{ active: !activeType }" @click="selectType('')">全部</button>
          <button
            v-for="t in typeList"
            :key="t.key"
            class="chip"
            :class="{ active: activeType === t.key }"
            :style="{ '--c': t.color }"
            @click="selectType(t.key)"
          ><KbIcon :name="t.icon" :size="14" /><span>{{ t.label }}</span></button>
        </div>
      </div>

      <div class="kb-aside-body">
        <!-- 检索结果 -->
        <div v-if="hasSearched" class="sr-wrap">
          <div class="sr-bar">
            <span class="sr-count">检索到 <b>{{ searchResults.length }}</b> 条</span>
            <button class="sr-back" @click="clearSearch">← 返回概览</button>
          </div>

          <div v-if="searchResults.length" class="sr-list">
            <div
              v-for="(r, i) in searchResults"
              :key="i"
              class="sr-card"
              @click="askFromResult(r)"
            >
              <div class="sr-card-top">
                <span class="type-tag" :style="tagStyle(r.doc_type)">{{ typeLabel(r.doc_type) }}</span>
                <span class="sr-score" v-if="typeof r.score === 'number'">{{ Math.round(r.score * 100) }}%</span>
              </div>
              <div class="sr-title">{{ r.title }}</div>
              <div class="sr-excerpt">{{ excerpt(r.text) }}</div>
              <div class="sr-law" v-if="r.law_status"><KbIcon name="alert-triangle" :size="12" /> {{ r.law_status }}</div>
              <div class="sr-foot">点击用 AI 进一步解答 →</div>
            </div>
          </div>
          <div v-else class="sr-empty">
            <span class="sr-empty-icon"><KbIcon name="search-x" :size="32" /></span>
            <p>未找到相关内容，换个关键词或分类试试</p>
          </div>
        </div>

        <!-- 概览：统计 + 热门 -->
        <div v-else class="ov-wrap">
          <div class="ov-title">知识库概览</div>
          <div class="stat-grid">
            <div
              v-for="t in typeList"
              :key="t.key"
              class="stat-card"
              :style="{ '--c': t.color, '--cb': t.bg }"
              @click="selectType(t.key)"
            >
              <div class="stat-icon"><KbIcon :name="t.icon" :size="20" /></div>
              <div class="stat-num">{{ t.count }}</div>
              <div class="stat-label">{{ t.label }}</div>
            </div>
          </div>

          <div class="ov-title">热门问题</div>
          <div class="hot-list">
            <button
              v-for="q in quickQuestions"
              :key="q"
              class="hot-btn"
              @click="askQuickQuestion(q)"
            >
              <span class="hot-dot">•</span>{{ q }}
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- ============ 右侧：问答对话 ============ -->
    <section class="kb-main">
      <!-- 欢迎页 -->
      <div v-if="!chatHistory.length" class="welcome">
        <div class="welcome-inner">
          <div class="welcome-icon"><KbIcon name="landmark" :size="34" /></div>
          <h1 class="welcome-title">城市管理知识库</h1>
          <p class="welcome-desc">
            我是城市管理 AI 助手，可解答职责归属、处置时限、法律法规等问题。
            在左侧检索知识，或直接向我提问。
          </p>
          <div class="welcome-input">
            <textarea
              v-model="question"
              placeholder="请输入城市管理相关问题…"
              rows="2"
              @keydown.enter.exact.prevent="askQuestion"
            ></textarea>
            <button class="send-btn" @click="askQuestion" :disabled="asking || !question.trim()">
              <KbIcon v-if="asking" name="spinner" :size="18" />
              <KbIcon v-else name="arrow-up" :size="18" />
            </button>
          </div>
          <div class="welcome-hint">试试在左侧点击分类，或搜索「井盖」「环卫」「执法」</div>
        </div>
      </div>

      <!-- 对话模式 -->
      <template v-else>
        <div class="chat-header">
          <div class="chat-header-left">
            <span class="chat-header-icon"><KbIcon name="headset" :size="18" /></span>
            <h2 class="chat-title">知识问答</h2>
          </div>
          <button class="clear-btn" @click="clearChat">+ 新建对话</button>
        </div>

        <div class="chat-messages" ref="chatMessagesRef">
          <div v-for="(msg, i) in chatHistory" :key="i" class="chat-msg" :class="msg.role">
            <div class="msg-avatar" v-if="msg.role === 'assistant'">
              <span class="avatar-icon"><KbIcon name="headset" :size="20" /></span>
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
              <span class="avatar-icon"><KbIcon name="headset" :size="20" /></span>
            </div>
            <div class="msg-content">
              <div class="chat-bubble typing">
                <span class="typing-text">思考中</span>
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <div class="location-bar" v-if="hasLocation">
            <span class="location-badge"><KbIcon name="map-pin" :size="14" /> 已定位: {{ selectedLng }}, {{ selectedLat }}</span>
            <button class="location-clear" @click="clearLocation">×</button>
          </div>
          <div class="input-wrapper">
            <textarea
              v-model="question"
              placeholder="输入城市管理相关问题…"
              rows="2"
              @keydown.enter.exact.prevent="askQuestion"
              ref="textareaRef"
            ></textarea>
            <button class="send-btn" @click="askQuestion" :disabled="asking || !question.trim()">
              <KbIcon v-if="asking" name="spinner" :size="18" />
              <KbIcon v-else name="arrow-up" :size="18" />
            </button>
          </div>
        </div>
      </template>
    </section>

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
import KbIcon from '../components/common/KbIcon.vue'

// 统一统计
const unifiedStats = ref({ total: 0, by_type: {} })

// 问答状态
const question = ref('')
const asking = ref(false)
const chatHistory = ref([])
const chatMessagesRef = ref(null)
const textareaRef = ref(null)

// 检索面板状态（此前为死代码，本次补齐声明并接好 UI）
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])
const activeType = ref('')          // '' = 全部；否则为某一 doc_type
const hasSearched = ref(false)

// 地图状态
const modalMapRef = ref(null)
const mapInitError = ref('')
const selectedLng = ref('')
const selectedLat = ref('')
const needLocation = ref(false)

let modalMapInstance = null
let pointMarker = null

// 文档类型元信息（颜色 / 图标 / 中文名）
const TYPE_META = {
  standard: { label: '立结案标准', icon: 'standard', color: 'var(--primary-500)', bg: 'var(--primary-50)' },
  org:      { label: '职责机构',   icon: 'org',      color: 'var(--warning)',    bg: 'var(--warning-light)' },
  qa:       { label: '知识问答',   icon: 'qa',       color: 'var(--success)',    bg: 'var(--success-light)' },
  general:  { label: '通用制度',   icon: 'general',  color: 'var(--info)',       bg: 'var(--info-light)' },
  law:      { label: '法律法规',   icon: 'law',      color: 'var(--danger)',     bg: 'var(--danger-light)' },
}

const typeList = computed(() => {
  const bt = unifiedStats.value.by_type || {}
  return Object.keys(TYPE_META).map(k => ({ key: k, ...TYPE_META[k], count: bt[k] || 0 }))
})

function typeLabel(k) {
  return (TYPE_META[k] || {}).label || k
}
function tagStyle(k) {
  const m = TYPE_META[k] || { color: 'var(--info)', bg: 'var(--info-light)' }
  return { color: m.color, background: m.bg }
}
function excerpt(text) {
  const t = (text || '').replace(/\s+/g, ' ').trim()
  return t.length > 110 ? t.slice(0, 110) + '…' : t
}

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

// Markdown渲染（支持标题/有序无序列表，列表自动包裹 ul/ol）
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^####\s+(.*)$/gm, '<h5>$1</h5>')
    .replace(/^###\s+(.*)$/gm, '<h4>$1</h4>')
    .replace(/^##\s+(.*)$/gm, '<h3>$1</h3>')
    .replace(/^#\s+(.*)$/gm, '<h2>$1</h2>')
  // 列表项
  html = html
    .replace(/^[-*]\s+(.*)$/gm, '<li>$1</li>')
    .replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  // 连续 <li> 包裹为 <ul>
  html = html.replace(/(?:<li>[\s\S]*?<\/li>)(?:\s*<li>[\s\S]*?<\/li>)*/g, m => '<ul>' + m + '</ul>')
  // 换行转 <br>
  html = html.replace(/\n/g, '<br>')
  return html
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
    const res = await fetch('/api/kb/stats', { headers: getAuthHeaders() })
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

  chatHistory.value.push({ role: 'user', content: currentQuestion })
  question.value = ''
  scrollToBottom()

  try {
    const location = hasLocation.value
      ? { lng: Number(selectedLng.value), lat: Number(selectedLat.value) }
      : null

    const controller = new AbortController()
    // 后端 ask 需经 embedding 检索 + 至多两次 LLM 调用（各 50s 预算），首问还可能
    // 触发本地 embedding 模型加载（约 10~30s），故前端硬超时设为 180s，避免慢 LLM
    // 或首问加载被过早 abort 成“请求超时”。后端自身也有 50s/次的 LLM 超时兜底。
    const timeoutId = setTimeout(() => controller.abort(), 180000)

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

    if (data.need_location) {
      needLocation.value = true
      chatHistory.value.push({
        role: 'assistant',
        content: data.message || '请在地图上点选具体位置'
      })
      scrollToBottom()
      return
    }

    chatHistory.value.push({
      role: 'assistant',
      content: data.answer,
      sources: (data.citations || []).map(c => c.title || c.source || '')
    })
    scrollToBottom()
  } catch (e) {
    const errMsg = e.name === 'AbortError'
      ? '请求超时：当前回答生成较慢，请稍后重试，或换种问法再试一次'
      : '查询失败: ' + e.message
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

// ================= 检索面板 =================
function selectType(t) {
  activeType.value = (activeType.value === t) ? '' : t
  if (searchQuery.value.trim()) runSearch()
}

async function runSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  hasSearched.value = true
  searchResults.value = []
  try {
    const body = { query: searchQuery.value.trim() }
    if (activeType.value) body.doc_type = activeType.value
    const res = await fetch('/api/kb/search', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body)
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || '请求失败')
    searchResults.value = data.results || []
  } catch (e) {
    console.error('知识检索失败:', e)
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  hasSearched.value = false
  activeType.value = ''
}

// 点击检索结果 → 用 AI 进一步解答
function askFromResult(r) {
  question.value = r.title || ''
  nextTick(() => askQuestion())
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
  height: 100%;
  display: flex;
  overflow: hidden;
  gap: var(--space-4);
  padding: var(--space-2);
}

/* ============ 左侧面板 ============ */
.kb-aside {
  width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.kb-aside-head {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-lighter);
}

.kb-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px 4px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-base);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.kb-search:focus-within {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}
[data-theme="dark"] .kb-search:focus-within {
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.2);
}
.kb-search-icon {
  display: flex;
  align-items: center;
  color: var(--text-tertiary);
}
.kb-search input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}
.kb-search-clear {
  border: none;
  background: none;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 0 2px;
}
.kb-search-btn {
  flex-shrink: 0;
  padding: 5px 12px;
  font-size: 13px;
  color: #fff;
  background: var(--primary-500);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.kb-search-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.kb-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: var(--space-3);
}
.chip {
  --c: var(--info);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}
.chip:hover {
  border-color: var(--c);
  color: var(--c);
}
.chip.active {
  color: #fff;
  background: var(--c);
  border-color: var(--c);
}

.kb-aside-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3);
}

/* 概览 */
.ov-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: var(--space-3) var(--space-1) var(--space-2);
}
.ov-title:first-child {
  margin-top: 0;
}
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}
.stat-card {
  --c: var(--info);
  --cb: var(--info-light);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.stat-card:hover {
  border-color: var(--c);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.stat-icon {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  border-radius: var(--radius-sm);
  color: var(--c);
  background: var(--cb);
}
.stat-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--c);
  line-height: 1.1;
}
.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.hot-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hot-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.hot-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-500);
  background: var(--primary-50);
}
.hot-dot {
  color: var(--primary-500);
}

/* 检索结果 */
.sr-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}
.sr-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.sr-count b {
  color: var(--primary-500);
}
.sr-back {
  font-size: 12px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
}
.sr-back:hover {
  color: var(--primary-500);
}
.sr-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.sr-card {
  padding: var(--space-3);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.sr-card:hover {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-sm);
}
.sr-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.type-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.sr-score {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
.sr-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.sr-excerpt {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sr-law {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--warning-dark);
}
.sr-foot {
  margin-top: 8px;
  font-size: 11px;
  color: var(--primary-500);
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.sr-card:hover .sr-foot {
  opacity: 1;
}
.sr-empty {
  text-align: center;
  padding: var(--space-10) var(--space-4);
  color: var(--text-tertiary);
}
.sr-empty-icon {
  font-size: 32px;
  display: block;
  margin-bottom: var(--space-2);
}
.sr-empty p {
  font-size: 13px;
}

/* ============ 右侧对话 ============ */
.kb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* 欢迎页 */
.welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}
.welcome-inner {
  text-align: center;
  max-width: 560px;
  width: 100%;
}
.welcome-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-500);
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary-500) 22%, transparent), color-mix(in srgb, var(--primary-500) 8%, transparent));
  box-shadow: 0 10px 28px -10px color-mix(in srgb, var(--primary-500) 60%, transparent);
  margin: 0 auto var(--space-3);
}
.welcome-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.welcome-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-bottom: var(--space-5);
}
/* 统一 composer 卡片（与对话框一致：浅色圆角容器 + 右下发送键） */
.welcome-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 24px;
  padding: 10px 10px 10px 16px;
  box-shadow: 0 2px 12px color-mix(in srgb, var(--text-primary) 6%, transparent);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.welcome-input:focus-within {
  border-color: var(--primary-500);
  box-shadow: 0 4px 18px color-mix(in srgb, var(--primary-500) 18%, transparent);
}
.welcome-input textarea {
  flex: 1;
  border: none;
  background: transparent;
  padding: 6px 0;
  font-size: 14px;
  resize: none;
  color: var(--text-primary);
  line-height: 1.5;
  outline: none;
  max-height: 140px;
}
.welcome-hint {
  margin-top: var(--space-4);
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 对话头 */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}
.chat-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.chat-header-icon {
  font-size: 18px;
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

/* 消息列表 */
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
  max-width: 860px;
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
  word-break: break-word;
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
.chat-bubble :deep(h4),
.chat-bubble :deep(h5) {
  margin: var(--space-3) 0 var(--space-2);
  font-weight: 600;
  line-height: 1.4;
}
.chat-bubble :deep(h2) { font-size: 18px; }
.chat-bubble :deep(h3) { font-size: 16px; }
.chat-bubble :deep(h4) { font-size: 15px; }
.chat-bubble :deep(h5) { font-size: 14px; color: var(--text-secondary); }
.chat-bubble :deep(ul),
.chat-bubble :deep(ol) {
  margin: var(--space-2) 0;
  padding-left: var(--space-5);
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
  display: inline-flex;
  align-items: center;
  gap: 4px;
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
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 24px;
  padding: 10px 10px 10px 16px;
  box-shadow: 0 2px 12px color-mix(in srgb, var(--text-primary) 6%, transparent);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-wrapper:focus-within {
  border-color: var(--primary-500);
  box-shadow: 0 4px 18px color-mix(in srgb, var(--primary-500) 18%, transparent);
}
.input-wrapper textarea {
  flex: 1;
  border: none;
  background: transparent;
  padding: 6px 0;
  font-size: 14px;
  resize: none;
  color: var(--text-primary);
  line-height: 1.5;
  outline: none;
  max-height: 140px;
}
.send-btn {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary-500) 35%, transparent);
  transition: background 0.2s, box-shadow 0.2s, transform 0.12s;
}
.send-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary-500) 88%, #000);
  box-shadow: 0 6px 18px color-mix(in srgb, var(--primary-500) 45%, transparent);
  transform: translateY(-1px);
}
.send-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.94);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--primary-500) 30%, transparent);
}
.send-btn:disabled {
  background: var(--border-light);
  color: var(--text-tertiary);
  box-shadow: none;
  cursor: not-allowed;
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

/* ============ 定位弹窗 ============ */
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

/* ============ 响应式 ============ */
@media (max-width: 860px) {
  .knowledge-page {
    flex-direction: column;
    overflow-y: auto;
  }
  .kb-aside {
    width: 100%;
    max-height: 45vh;
  }
  .kb-main {
    min-height: 55vh;
  }
}
</style>
