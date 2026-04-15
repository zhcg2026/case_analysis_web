<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h1 class="page-title">知识库</h1>
      <p class="page-desc">智能问答和知识检索功能，文档管理请前往系统管理</p>
    </div>

    <!-- Tab切换 -->
    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'general' }" @click="activeTab = 'general'">
        通用知识库
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'standards' }" @click="activeTab = 'standards'">
        立结案标准库
      </button>
    </div>

    <!-- 通用知识库 -->
    <div v-show="activeTab === 'general'">
      <!-- 统计卡片 -->
      <div class="stats-card">
        <div class="stat-item">
          <span class="stat-label">向量数量</span>
          <span class="stat-value">{{ stats.count || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">文档数</span>
          <span class="stat-value">{{ stats.doc_count || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">运行模式</span>
          <span class="stat-value">{{ stats.exists ? (stats.mode === 'server' ? '服务器' : '本地') : '未初始化' }}</span>
        </div>
      </div>

      <!-- 智能问答 -->
      <div class="qa-section single-section">
        <div class="section-header">
          <h3>智能问答</h3>
        </div>

        <div class="qa-input">
          <textarea v-model="question" placeholder="输入问题，从知识库中检索答案..." rows="3"></textarea>
          <button class="ask-btn" @click="askQuestion" :disabled="asking || !question.trim()">
            {{ asking ? '思考中...' : '提问' }}
          </button>
        </div>

        <!-- 回答结果 -->
        <div class="qa-result" v-if="answer">
          <div class="answer-box">
            <div class="answer-header">
              <span class="answer-label">回答</span>
              <span class="answer-status" :class="answer.success ? 'success' : 'error'">
                {{ answer.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="answer-content">{{ answer.answer }}</div>
          </div>

          <div class="sources-box" v-if="answer.sources && answer.sources.length">
            <div class="sources-header">
              <span class="sources-label">参考来源</span>
            </div>
            <div class="sources-list">
              <div class="source-item" v-for="source in answer.sources" :key="source">
                {{ source }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 知识检索 -->
      <div class="search-section single-section">
        <div class="section-header">
          <h3>知识检索</h3>
        </div>

        <div class="search-input">
          <input v-model="searchQuery" placeholder="搜索关键词..." />
          <button class="search-btn" @click="searchKnowledge" :disabled="searching">
            {{ searching ? '搜索中...' : '搜索' }}
          </button>
        </div>

        <div class="search-results" v-if="searchResults.length">
          <div class="result-item" v-for="(result, index) in searchResults" :key="index">
            <div class="result-header">
              <span class="result-source">{{ result.source }}</span>
              <span class="result-score">相似度: {{ (result.score * 100).toFixed(1) }}%</span>
            </div>
            <div class="result-content">{{ result.content }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 立结案标准库 -->
    <div v-show="activeTab === 'standards'" class="standards-section">
      <!-- 统计卡片 -->
      <div class="stats-card" v-if="standardsStats.exists">
        <div class="stat-item">
          <span class="stat-label">父文档</span>
          <span class="stat-value">{{ standardsStats.parents || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">子文档</span>
          <span class="stat-value">{{ standardsStats.children || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">模式</span>
          <span class="stat-value">{{ standardsStats.mode || '未知' }}</span>
        </div>
      </div>

      <!-- 标准问答 -->
      <div class="standards-qa">
        <div class="section-header">
          <h3>立结案标准问答</h3>
        </div>
        <div class="qa-input">
          <textarea v-model="standardsQuestion" placeholder="输入问题，如：井盖破损的处置时限是多少？" rows="3"></textarea>
          <div class="standards-map-panel">
            <div class="map-panel-header">
              <span>地图定位（点击地图选择位置）</span>
            </div>
            <div ref="standardsMapRef" class="standards-map"></div>
            <div class="map-panel-footer">
              <span v-if="mapInitError" class="map-error-text">{{ mapInitError }}</span>
              <span v-else class="map-help-text">点击地图任意位置即可自动定位并填充经纬度</span>
            </div>
          </div>
          <div class="location-row">
            <input v-model="standardsLng" placeholder="经度（如 111.00）" />
            <input v-model="standardsLat" placeholder="纬度（如 35.03）" />
          </div>
          <div class="location-actions">
            <button class="location-btn" type="button" @click="loadLocationFromMap">读取地图点位</button>
            <span class="location-tip" v-if="standardsLng && standardsLat">
              当前点位：{{ standardsLng }}, {{ standardsLat }}<span v-if="mapLocationTime">（{{ mapLocationTime }}）</span>
            </span>
          </div>
          <button class="ask-btn" @click="askStandards" :disabled="askingStandards || !standardsQuestion.trim()">
            {{ askingStandards ? '查询中...' : '提问' }}
          </button>
        </div>
        <div class="qa-result" v-if="standardsAnswer">
          <div class="answer-box">
            <div class="answer-header">
              <span class="answer-label">回答</span>
              <span class="answer-status" :class="standardsAnswer.success ? 'success' : 'error'">
                {{ standardsAnswer.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="answer-content">{{ standardsAnswer.answer }}</div>
          </div>
          <div class="sources-box" v-if="standardsAnswer.sources && standardsAnswer.sources.length">
            <div class="sources-header">参考案件类型</div>
            <div class="sources-list">
              <span class="source-tag" v-for="s in standardsAnswer.sources" :key="s">{{ s }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 标准搜索 -->
      <div class="standards-search">
        <div class="section-header">
          <h3>标准检索</h3>
        </div>
        <div class="search-input">
          <input v-model="standardsSearchQuery" placeholder="搜索关键词..." />
          <button class="search-btn" @click="searchStandards" :disabled="searchingStandards">
            {{ searchingStandards ? '搜索中...' : '搜索' }}
          </button>
        </div>
        <div class="search-results" v-if="standardsSearchResults.length">
          <div class="result-item" v-for="(r, i) in standardsSearchResults" :key="i">
            <div class="result-header">
              <span class="result-type">{{ r.case_type }}</span>
              <span class="result-score">相似度: {{ ((r.score || 0) * 100).toFixed(1) }}%</span>
            </div>
            <div class="result-child">{{ r.child_text }}</div>
            <div class="result-meta" v-if="r.meta_info">
              <span v-if="r.meta_info.time_limit">处置时限: {{ r.meta_info.time_limit }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()

// Tab切换
const activeTab = ref('general')

// 通用知识库状态
const stats = ref({ exists: false, count: 0 })
const question = ref('')
const asking = ref(false)
const answer = ref(null)
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])

// 立结案标准相关状态
const standardsStats = ref({ exists: false })
const standardsQuestion = ref('')
const standardsLng = ref('')
const standardsLat = ref('')
const mapLocationTime = ref('')
const standardsMapRef = ref(null)
const mapInitError = ref('')
const askingStandards = ref(false)
const standardsAnswer = ref(null)
const standardsSearchQuery = ref('')
const searchingStandards = ref(false)
const standardsSearchResults = ref([])

let standardsMapInstance = null
let standardsPointMarker = null

// API基础URL
const apiBase = '/api/knowledge'

// 获取token
function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
}

// 加载统计信息
async function loadStats() {
  try {
    const res = await fetch(`${apiBase}/stats`, {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    stats.value = data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

// ================= 立结案标准相关方法 =================

// 加载立结案标准统计
async function loadStandardsStats() {
  try {
    const res = await fetch('/api/case-standards/stats', {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    standardsStats.value = data
  } catch (e) {
    console.error('加载标准统计失败:', e)
  }
}

// 立结案标准问答
async function askStandards() {
  if (!standardsQuestion.value.trim()) return

  askingStandards.value = true
  standardsAnswer.value = null

  try {
    const location = (standardsLng.value !== '' && standardsLat.value !== '')
      ? { lng: Number(standardsLng.value), lat: Number(standardsLat.value) }
      : null
    const res = await fetch('/api/case-standards/ask', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ question: standardsQuestion.value, location })
    })
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
    standardsAnswer.value = data
  } catch (e) {
    standardsAnswer.value = { success: false, answer: '查询失败: ' + e.message }
  } finally {
    askingStandards.value = false
  }
}

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
      standardsLng.value = String(location.lng)
      standardsLat.value = String(location.lat)
      mapLocationTime.value = formatTime(location.timestamp)
    }
  } catch (e) {
    console.error('读取地图定位点失败:', e)
  }
}

function handleMapLocationUpdated(event) {
  const detail = event?.detail
  if (typeof detail?.lng === 'number' && typeof detail?.lat === 'number') {
    standardsLng.value = String(detail.lng)
    standardsLat.value = String(detail.lat)
    mapLocationTime.value = formatTime(detail.timestamp)
  }
}

function saveSelectedLocation(lng, lat) {
  const payload = {
    lng: Number(lng.toFixed(6)),
    lat: Number(lat.toFixed(6)),
    timestamp: Date.now()
  }
  localStorage.setItem('selected_map_location', JSON.stringify(payload))
  standardsLng.value = String(payload.lng)
  standardsLat.value = String(payload.lat)
  mapLocationTime.value = formatTime(payload.timestamp)
}

function setMapPointMarker(lng, lat) {
  if (!standardsMapInstance || !window.AMap) return
  if (!standardsPointMarker) {
    standardsPointMarker = new window.AMap.Marker({
      map: standardsMapInstance,
      anchor: 'bottom-center',
      offset: new window.AMap.Pixel(0, -2)
    })
  }
  standardsPointMarker.setPosition([lng, lat])
}

async function ensureAmapReady(timeoutMs = 8000) {
  const start = Date.now()
  while (!window.AMap && Date.now() - start < timeoutMs) {
    await new Promise(resolve => setTimeout(resolve, 120))
  }
  return Boolean(window.AMap)
}

async function initStandardsMap() {
  if (standardsMapInstance || !standardsMapRef.value) return
  const amapReady = await ensureAmapReady()
  if (!amapReady || !window.AMap) {
    mapInitError.value = '地图加载失败，请刷新后重试'
    console.error('高德地图未加载或加载超时')
    return
  }
  mapInitError.value = ''
  standardsMapInstance = new window.AMap.Map(standardsMapRef.value, {
    zoom: 12,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: 'amap://styles/normal'
  })

  standardsMapInstance.on('click', (event) => {
    const lng = event?.lnglat?.getLng?.()
    const lat = event?.lnglat?.getLat?.()
    if (typeof lng !== 'number' || typeof lat !== 'number') return
    saveSelectedLocation(lng, lat)
    setMapPointMarker(lng, lat)
  })

  loadLocationFromMap()
  if (standardsLng.value && standardsLat.value) {
    setMapPointMarker(Number(standardsLng.value), Number(standardsLat.value))
  }
}

// 搜索立结案标准
async function searchStandards() {
  if (!standardsSearchQuery.value.trim()) return

  searchingStandards.value = true
  standardsSearchResults.value = []

  try {
    const res = await fetch('/api/case-standards/search', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ query: standardsSearchQuery.value })
    })
    const data = await res.json()
    standardsSearchResults.value = data.results || []
  } catch (e) {
    console.error('标准搜索失败:', e)
  } finally {
    searchingStandards.value = false
  }
}

// 初始化
onMounted(() => {
  loadStats()
  loadStandardsStats()
  loadLocationFromMap()
  window.addEventListener('map-location-updated', handleMapLocationUpdated)
})

watch(activeTab, async (tab) => {
  if (tab !== 'standards') return
  await nextTick()
  await initStandardsMap()
  setTimeout(() => {
    standardsMapInstance?.resize?.()
  }, 0)
})

onUnmounted(() => {
  window.removeEventListener('map-location-updated', handleMapLocationUpdated)
  if (standardsMapInstance) {
    standardsMapInstance.destroy()
  }
  standardsMapInstance = null
  standardsPointMarker = null
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

.stats-card {
  display: flex;
  gap: var(--space-4);
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
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-500);
}

/* 单独区块样式 */
.single-section {
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

/* 问答区样式 */
.qa-input textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  resize: vertical;
  background: var(--bg-base);
  color: var(--text-primary);
}

.standards-map-panel {
  margin-top: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
}

.map-panel-header {
  padding: var(--space-2) var(--space-3);
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-lighter);
  background: var(--fill-light);
}

.standards-map {
  height: 280px;
  width: 100%;
  cursor: crosshair;
}

.map-panel-footer {
  padding: 6px 10px;
  border-top: 1px solid var(--border-lighter);
  background: var(--bg-card);
}

.map-help-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.map-error-text {
  font-size: 12px;
  color: var(--danger);
}

.location-row {
  margin-top: var(--space-2);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.location-row input {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.location-actions {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.location-btn {
  padding: 6px 12px;
  background: var(--fill-light);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.location-btn:hover {
  background: var(--fill-dark);
}

.location-tip {
  font-size: 12px;
  color: var(--text-secondary);
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

.qa-result {
  margin-top: var(--space-4);
}

.answer-box {
  padding: var(--space-3);
  background: var(--primary-50);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

[data-theme="dark"] .answer-box {
  background: rgba(64, 158, 255, 0.1);
}

.answer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-500);
}

.answer-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.answer-status.success {
  background: var(--success-light);
  color: var(--success);
}

.answer-status.error {
  background: var(--danger-light);
  color: var(--danger);
}

.answer-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

.sources-box {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.sources-header {
  margin-bottom: var(--space-2);
}

.sources-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.source-item {
  padding: var(--space-1) var(--space-2);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
}

/* 搜索区样式 */
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

.result-source {
  font-size: 12px;
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

/* Tab导航样式 */
.tab-nav {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.tab-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--fill-light);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.tab-btn:hover:not(.active) {
  background: var(--fill-dark);
}

/* 立结案标准模块样式 */
.standards-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.standards-qa {
  margin-bottom: var(--space-6);
}

.standards-search {
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.source-tag {
  padding: var(--space-1) var(--space-2);
  background: var(--primary-50);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.result-type {
  font-size: 12px;
  color: var(--primary-500);
  font-weight: 500;
}

.result-child {
  font-size: 13px;
  color: var(--text-primary);
  margin: var(--space-1) 0;
}

.result-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .standards-map {
    height: 220px;
  }
}
</style>