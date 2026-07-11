<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h1 class="page-title">城市管理知识库</h1>
      <p class="page-desc">智能问答与知识检索，理解问题、提取重点、精准回答</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-card">
      <div class="stat-item">
        <span class="stat-label">总向量数</span>
        <span class="stat-value">{{ unifiedStats.total_vectors || 0 }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">通用文档</span>
        <span class="stat-value">{{ unifiedStats.general?.doc_count || 0 }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">立结案标准</span>
        <span class="stat-value">{{ unifiedStats.standards?.parents || 0 }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">运行模式</span>
        <span class="stat-value">{{ unifiedStats.general?.mode === 'server' ? '服务器' : '本地' }}</span>
      </div>
    </div>

    <!-- 主内容区：问答 + 地图 -->
    <div class="main-grid">
      <!-- 左列：问答区 -->
      <div class="qa-column">
        <div class="section-card">
          <div class="section-header">
            <h3>智能问答</h3>
            <button v-if="chatHistory.length" class="clear-btn" @click="clearChat">清空对话</button>
          </div>

          <!-- 对话消息列表 -->
          <div class="chat-messages" v-if="chatHistory.length">
            <div v-for="(msg, i) in chatHistory" :key="i" class="chat-msg" :class="msg.role">
              <div class="chat-bubble">
                <div class="chat-text">{{ msg.content }}</div>
                <div class="chat-sources" v-if="msg.sources && msg.sources.length">
                  <span class="source-tag" v-for="s in msg.sources" :key="s">{{ s }}</span>
                </div>
              </div>
            </div>
            <div v-if="asking" class="chat-msg assistant">
              <div class="chat-bubble typing">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="qa-input">
            <textarea 
              v-model="question" 
              placeholder="请输入城市管理相关问题，如：井盖破损的处置时限是多少？这个问题归哪个部门管？" 
              rows="3"
              @keydown.enter.exact.prevent="askQuestion"
            ></textarea>
            <button class="ask-btn" @click="askQuestion" :disabled="asking || !question.trim()">
              {{ asking ? '思考中...' : '提问' }}
            </button>
          </div>

          <!-- 需要位置提示 -->
          <div class="location-hint" v-if="needLocation && !hasLocation">
            <div class="hint-icon">📍</div>
            <div class="hint-content">
              <p class="hint-title">需要定位位置</p>
              <p class="hint-desc">您的问题涉及区域判定，请在右侧地图上点选具体位置</p>
              <button class="hint-btn" @click="showMap = true">点选位置</button>
            </div>
          </div>

          <!-- 已定位提示 -->
          <div class="location-selected" v-if="hasLocation">
            <span class="location-text">已定位: {{ selectedLng }}, {{ selectedLat }}</span>
            <button class="clear-location-btn" @click="clearLocation">清除</button>
          </div>
        </div>

        <!-- 知识检索 -->
        <div class="section-card">
          <div class="section-header">
            <h3>知识检索</h3>
          </div>
          <div class="search-input">
            <input v-model="searchQuery" placeholder="搜索关键词..." @keydown.enter="searchKnowledge" />
            <button class="search-btn" @click="searchKnowledge" :disabled="searching">
              {{ searching ? '搜索中...' : '搜索' }}
            </button>
          </div>
          <div class="search-results" v-if="searchResults.length">
            <div class="result-item" v-for="(result, index) in searchResults" :key="index">
              <div class="result-header">
                <span class="result-type" v-if="result.source_type === 'standards'">立结案标准</span>
                <span class="result-type general" v-else>通用知识</span>
                <span class="result-score">相似度: {{ ((result.score || 0) * 100).toFixed(1) }}%</span>
              </div>
              <div class="result-content">{{ result.content || result.child_text || result.parent_text }}</div>
              <div class="result-meta" v-if="result.case_type">
                <span class="meta-tag">{{ result.case_type }}</span>
                <span v-if="result.meta_info?.time_limit" class="meta-info">处置时限: {{ result.meta_info.time_limit }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右列：地图区 -->
      <div class="map-column" :class="{ expanded: showMap }">
        <div class="section-card">
          <div class="section-header">
            <h3>地图定位</h3>
            <button class="toggle-map-btn" @click="showMap = !showMap">
              {{ showMap ? '收起' : '展开' }}
            </button>
          </div>
          
          <div v-show="showMap" class="map-container">
            <div ref="mapRef" class="amap"></div>
            <div class="map-footer">
              <span v-if="mapInitError" class="map-error">{{ mapInitError }}</span>
              <span v-else class="map-help">点击地图任意位置自动定位</span>
            </div>
          </div>

          <div v-show="showMap" class="location-row">
            <input v-model="selectedLng" placeholder="经度" />
            <input v-model="selectedLat" placeholder="纬度" />
          </div>

          <div v-show="showMap" class="location-actions">
            <button class="location-btn" @click="loadLocationFromMap">读取点位</button>
            <button class="location-btn primary" @click="useLocation" v-if="selectedLng && selectedLat">
              使用此位置
            </button>
          </div>
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

// 搜索状态
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])

// 地图状态
const showMap = ref(false)
const mapRef = ref(null)
const mapInitError = ref('')
const selectedLng = ref('')
const selectedLat = ref('')
const needLocation = ref(false)

let mapInstance = null
let pointMarker = null

// 计算属性
const hasLocation = computed(() => {
  return selectedLng.value !== '' && selectedLat.value !== '' && 
         !isNaN(Number(selectedLng.value)) && !isNaN(Number(selectedLat.value))
})

// 获取token
function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
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
      showMap.value = true
      return
    }

    // 追加AI回答到对话历史
    chatHistory.value.push({ 
      role: 'assistant', 
      content: data.answer, 
      sources: data.sources 
    })
  } catch (e) {
    const errMsg = e.name === 'AbortError' ? '请求超时，请稍后重试' : '查询失败: ' + e.message
    chatHistory.value.push({ role: 'assistant', content: errMsg })
  } finally {
    asking.value = false
  }
}

// 清空对话
function clearChat() {
  chatHistory.value = []
  needLocation.value = false
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

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

function loadLocationFromMap() {
  try {
    const raw = localStorage.getItem('selected_map_location')
    if (!raw) return
    const location = JSON.parse(raw)
    if (typeof location?.lng === 'number' && typeof location?.lat === 'number') {
      selectedLng.value = String(location.lng)
      selectedLat.value = String(location.lat)
    }
  } catch (e) {
    console.error('读取地图定位点失败:', e)
  }
}

function handleMapLocationUpdated(event) {
  const detail = event?.detail
  if (typeof detail?.lng === 'number' && typeof detail?.lat === 'number') {
    selectedLng.value = String(detail.lng)
    selectedLat.value = String(detail.lat)
  }
}

function saveSelectedLocation(lng, lat) {
  const payload = {
    lng: Number(lng.toFixed(6)),
    lat: Number(lat.toFixed(6)),
    timestamp: Date.now()
  }
  localStorage.setItem('selected_map_location', JSON.stringify(payload))
  selectedLng.value = String(payload.lng)
  selectedLat.value = String(payload.lat)
}

function setMapPointMarker(lng, lat) {
  if (!mapInstance || !window.AMap) return
  if (!pointMarker) {
    pointMarker = new window.AMap.Marker({
      map: mapInstance,
      anchor: 'bottom-center',
      offset: new window.AMap.Pixel(0, -2)
    })
  }
  pointMarker.setPosition([lng, lat])
}

async function ensureAmapReady(timeoutMs = 8000) {
  const start = Date.now()
  while (!window.AMap && Date.now() - start < timeoutMs) {
    await new Promise(resolve => setTimeout(resolve, 120))
  }
  return Boolean(window.AMap)
}

async function initMap() {
  if (mapInstance || !mapRef.value) return
  const amapReady = await ensureAmapReady()
  if (!amapReady || !window.AMap) {
    mapInitError.value = '地图加载失败，请刷新后重试'
    console.error('高德地图未加载或加载超时')
    return
  }
  mapInitError.value = ''
  mapInstance = new window.AMap.Map(mapRef.value, {
    zoom: 12,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: 'amap://styles/normal'
  })

  mapInstance.on('click', (event) => {
    const lng = event?.lnglat?.getLng?.()
    const lat = event?.lnglat?.getLat?.()
    if (typeof lng !== 'number' || typeof lat !== 'number') return
    saveSelectedLocation(lng, lat)
    setMapPointMarker(lng, lat)
  })

  // 恢复之前选中的位置
  if (selectedLng.value && selectedLat.value) {
    setMapPointMarker(Number(selectedLng.value), Number(selectedLat.value))
  }
}

async function useLocation() {
  if (!hasLocation.value) return
  
  needLocation.value = false
  // 显示位置已确认
  chatHistory.value.push({ 
    role: 'assistant', 
    content: `已定位到坐标 (${selectedLng.value}, ${selectedLat.value})。请输入问题后点击提问，系统将根据问题类型判断对应部门的管辖范围。`
  })
  // 如果有未发送的问题，自动发送
  if (question.value.trim()) {
    askQuestion()
  }
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
  // 不自动恢复上次位置，默认不标记地点
  window.addEventListener('map-location-updated', handleMapLocationUpdated)
})

// 监听地图展开
watch(showMap, async (show) => {
  if (show) {
    await nextTick()
    await initMap()
    setTimeout(() => {
      mapInstance?.resize?.()
    }, 0)
  }
})

onUnmounted(() => {
  window.removeEventListener('map-location-updated', handleMapLocationUpdated)
  if (mapInstance) {
    mapInstance.destroy()
  }
  mapInstance = null
  pointMarker = null
})
</script>

<style scoped>
.knowledge-page {
  padding: var(--space-6);
  max-width: 1400px;
}

.page-header {
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.page-desc {
  color: var(--text-secondary);
  font-size: 14px;
}

/* 统计卡片 */
.stats-card {
  display: flex;
  gap: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  margin-bottom: var(--space-6);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-500);
}

/* 主内容网格 */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: var(--space-4);
  align-items: start;
}

@media (max-width: 1024px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
  .map-column {
    order: -1;
  }
}

/* 区块卡片 */
.section-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.clear-btn {
  font-size: 12px;
  color: var(--text-tertiary);
  background: none;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
}

.clear-btn:hover {
  color: var(--danger-500, #ef4444);
  border-color: var(--danger-500, #ef4444);
}

/* 对话样式 */
.chat-messages {
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  max-height: 400px;
  overflow-y: auto;
}

.chat-msg {
  display: flex;
  margin-bottom: var(--space-3);
}

.chat-msg.user {
  justify-content: flex-end;
}

.chat-msg.assistant {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: 80%;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  line-height: 1.6;
  font-size: 14px;
  white-space: pre-wrap;
}

.chat-msg.user .chat-bubble {
  background: var(--primary-500, #3b82f6);
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-msg.assistant .chat-bubble {
  background: var(--fill-light, #f3f4f6);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.chat-sources {
  margin-top: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.source-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(255,255,255,0.2);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
}

.chat-msg.assistant .source-tag {
  background: var(--primary-50);
}

/* 输入区 */
.qa-input textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  resize: vertical;
  background: var(--bg-base);
  color: var(--text-primary);
  box-sizing: border-box;
}

.ask-btn {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}

.ask-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 位置提示 */
.location-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: var(--radius-md);
  margin-top: var(--space-3);
}

[data-theme="dark"] .location-hint {
  background: rgba(251, 146, 60, 0.1);
  border-color: rgba(251, 146, 60, 0.3);
}

.hint-icon {
  font-size: 20px;
}

.hint-content {
  flex: 1;
}

.hint-title {
  font-size: 14px;
  font-weight: 600;
  color: #c2410c;
  margin-bottom: 4px;
}

[data-theme="dark"] .hint-title {
  color: #fb923c;
}

.hint-desc {
  font-size: 13px;
  color: #9a3412;
  margin-bottom: var(--space-2);
}

[data-theme="dark"] .hint-desc {
  color: #fdba74;
}

.hint-btn {
  padding: 4px 12px;
  background: #ea580c;
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
}

.hint-btn:hover {
  background: #c2410c;
}

.location-selected {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--primary-50);
  border-radius: var(--radius-sm);
  margin-top: var(--space-2);
}

.location-text {
  font-size: 12px;
  color: var(--primary-500);
}

.clear-location-btn {
  font-size: 11px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

/* 搜索区 */
.search-input {
  display: flex;
  gap: var(--space-2);
}

.search-input input {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.search-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--fill-light);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.search-btn:disabled {
  opacity: 0.5;
}

.search-results {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.result-item {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.result-type {
  font-size: 12px;
  color: var(--primary-500);
  font-weight: 500;
}

.result-type.general {
  color: var(--text-secondary);
}

.result-score {
  font-size: 12px;
  color: var(--success);
}

.result-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.result-meta {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.meta-tag {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--primary-50);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
}

.meta-info {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 地图区 */
.map-column {
  position: sticky;
  top: var(--space-4);
}

.toggle-map-btn {
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
}

.toggle-map-btn:hover {
  background: var(--fill-light);
}

.map-container {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: var(--space-3);
}

.amap {
  height: 300px;
  width: 100%;
  cursor: crosshair;
}

.map-footer {
  padding: var(--space-2) var(--space-3);
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-lighter);
  background: var(--fill-light);
}

.map-error {
  color: var(--danger-500, #ef4444);
}

.location-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
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

.location-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.location-btn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 12px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
}

.location-btn.primary {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.location-btn:hover {
  opacity: 0.9;
}

/* 加载动画 */
.chat-bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: var(--space-2) var(--space-3);
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
</style>
