<template>
  <div class="dispatch-page">
    <!-- 顶部标题栏 -->
    <header class="dispatch-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回首页</span>
        </router-link>
      </div>
      <div class="header-center">
        <h1 class="dispatch-title">
          <svg class="title-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          案件归属
        </h1>
      </div>
      <div class="header-right">
        <span class="header-subtitle">智能派单 · 精准定位</span>
      </div>
    </header>

    <!-- 全屏地图背景 -->
    <div class="map-fullscreen">
      <div id="dispatch-map" class="map-element"></div>
    </div>

    <!-- 地图工具栏 -->
    <div class="map-toolbar">
      <button class="toolbar-btn" @click="zoomIn" title="放大">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
      <button class="toolbar-btn" @click="zoomOut" title="缩小">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
    </div>

    <!-- 左侧展开/收起按钮 -->
    <button class="panel-toggle-btn left-toggle" :class="{ collapsed: leftPanelCollapsed }" @click="leftPanelCollapsed = !leftPanelCollapsed" :title="leftPanelCollapsed ? '展开查询' : '收起查询'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline :points="leftPanelCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/>
      </svg>
    </button>

    <!-- 左侧查询面板 -->
    <aside class="floating-panel left-panel" :class="{ collapsed: leftPanelCollapsed }">
      <div class="panel-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
        <h3>归属查询</h3>
      </div>

      <div class="query-content">
        <!-- 案件类型选择 -->
        <div class="query-section">
          <div class="query-title">案件类型</div>
          <select v-model="selectedCategory" class="query-select" @change="onCategoryChange">
            <option value="">选择大类</option>
            <option v-for="cat in categories" :key="cat.name" :value="cat.name">{{ cat.name }}</option>
          </select>
          <select v-model="selectedCaseType" class="query-select" :disabled="!filteredTypes.length">
            <option value="">选择具体类型</option>
            <option v-for="ct in filteredTypes" :key="ct.id" :value="ct.id">{{ ct.name }}</option>
          </select>
        </div>

        <!-- 自然语言输入 -->
        <div class="query-section">
          <div class="query-title">问题描述<span class="optional">（可选）</span></div>
          <textarea
            v-model="questionText"
            class="query-textarea"
            placeholder="如：圣惠路路面遗撒垃圾，归哪个部门处理？"
            rows="3"
          ></textarea>
        </div>

        <!-- 坐标信息 -->
        <div class="query-section">
          <div class="query-title">地图定位</div>
          <div class="location-info" v-if="selectedLng && selectedLat">
            <span class="loc-label">经度:</span> <span class="loc-value">{{ selectedLng }}</span>
            <span class="loc-sep">|</span>
            <span class="loc-label">纬度:</span> <span class="loc-value">{{ selectedLat }}</span>
            <button class="loc-clear" @click="clearLocation" title="清除定位">×</button>
          </div>
          <div class="location-hint" v-else>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            点击地图选择位置
          </div>
        </div>

        <!-- 查询按钮 -->
        <button class="query-btn" @click="doDispatch" :disabled="querying">
          <svg v-if="querying" class="spin-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          {{ querying ? '查询中...' : '查询归属' }}
        </button>
      </div>
    </aside>

    <!-- 右侧展开/收起按钮 -->
    <button class="panel-toggle-btn right-toggle" :class="{ collapsed: rightPanelCollapsed }" @click="rightPanelCollapsed = !rightPanelCollapsed" :title="rightPanelCollapsed ? '展开结果' : '收起结果'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline :points="rightPanelCollapsed ? '15 18 9 12 15 6' : '9 18 15 12 9 6'"/>
      </svg>
    </button>

    <!-- 右侧结果面板 -->
    <aside class="floating-panel right-panel" :class="{ collapsed: rightPanelCollapsed }">
      <div class="panel-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        <h3>查询结果</h3>
      </div>

      <!-- 有结果 -->
      <div v-if="dispatchResult" class="result-content">
        <div class="result-status" :class="dispatchResult.in_jurisdiction ? 'status-ok' : 'status-warn'">
          <svg v-if="dispatchResult.in_jurisdiction" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {{ dispatchResult.in_jurisdiction ? '管辖范围内' : '需进一步确认' }}
        </div>

        <div class="result-card" v-if="dispatchResult.department">
          <div class="result-label">归属部门</div>
          <div class="result-value dept-value">{{ dispatchResult.department }}</div>
        </div>

        <div class="result-card" v-if="dispatchResult.unit">
          <div class="result-label">处置单位</div>
          <div class="result-value unit-value">{{ dispatchResult.unit }}</div>
        </div>

        <div class="result-card" v-if="dispatchResult.case_type">
          <div class="result-label">案件类型</div>
          <div class="result-value">{{ dispatchResult.case_type.name }}</div>
        </div>

        <div class="result-card">
          <div class="result-label">图层状态</div>
          <div class="result-value">
            <span class="layer-tag" :class="layerStatusClass">{{ layerStatusText }}</span>
          </div>
        </div>

        <div class="result-answer">
          <div class="answer-label">结论</div>
          <div class="answer-text">{{ dispatchResult.answer }}</div>
        </div>
      </div>

      <!-- 无结果 -->
      <div v-else class="empty-result">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
        <p>选择案件类型并在地图上点选位置后查询</p>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { useUserStore } from '../stores/user'
import { useThemeStore } from '../stores/theme'

const userStore = useUserStore()
const themeStore = useThemeStore()

// 面板状态
const leftPanelCollapsed = ref(false)
const rightPanelCollapsed = ref(true)

// 查询状态
const querying = ref(false)
const dispatchResult = ref(null)

// 案件类型数据
const caseTypes = ref([])
const categories = ref([])
const selectedCategory = ref('')
const selectedCaseType = ref('')
const questionText = ref('')

// 地图状态
const selectedLng = ref('')
const selectedLat = ref('')
let mapInstance = null
let pointMarker = null

// 过滤后的案件类型
const filteredTypes = computed(() => {
  if (!selectedCategory.value) return caseTypes.value
  return caseTypes.value.filter(t => t.category === selectedCategory.value)
})

// 图层状态映射
const layerStatusText = computed(() => {
  const s = dispatchResult.value?.layer_status
  const map = {
    'ready': '数据就绪',
    'no_location': '缺少坐标',
    'missing_location': '缺少坐标',
    'unknown_department': '部门未识别',
    'not_ready': '数据未完善',
    'missing_layer_file': '数据文件缺失',
    'park_not_ready_fallback_zone': '公园图层未完善',
  }
  return map[s] || s || ''
})

const layerStatusClass = computed(() => {
  const s = dispatchResult.value?.layer_status
  if (s === 'ready') return 'tag-ok'
  if (s === 'no_location' || s === 'missing_location') return 'tag-warn'
  return 'tag-info'
})

function getAuthHeaders() {
  const token = userStore.token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function onCategoryChange() {
  selectedCaseType.value = ''
}

// 加载案件类型列表
async function loadCaseTypes() {
  try {
    const res = await axios.get('/api/dispatch/types', { headers: getAuthHeaders() })
    if (res.data) {
      caseTypes.value = res.data.types || []
      categories.value = res.data.categories || []
    }
  } catch (e) {
    console.error('加载案件类型失败:', e)
  }
}

// 地图初始化
async function ensureAmapReady(timeoutMs = 8000) {
  const start = Date.now()
  while (!window.AMap && Date.now() - start < timeoutMs) {
    await new Promise(resolve => setTimeout(resolve, 120))
  }
  return Boolean(window.AMap)
}

async function initMap() {
  const amapReady = await ensureAmapReady()
  if (!amapReady || !window.AMap) {
    console.error('AMap not loaded')
    return
  }

  const isDark = themeStore.theme !== 'light'

  mapInstance = new window.AMap.Map('dispatch-map', {
    zoom: 12,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: isDark ? 'amap://styles/dark' : 'amap://styles/normal'
  })

  mapInstance.on('click', (event) => {
    const lng = event?.lnglat?.getLng?.()
    const lat = event?.lnglat?.getLat?.()
    if (typeof lng !== 'number' || typeof lat !== 'number') return
    selectedLng.value = String(Number(lng.toFixed(6)))
    selectedLat.value = String(Number(lat.toFixed(6)))
    setMapMarker(lng, lat)
  })
}

function setMapMarker(lng, lat) {
  if (!mapInstance || !window.AMap) return
  if (pointMarker) {
    pointMarker.setPosition([lng, lat])
  } else {
    pointMarker = new window.AMap.Marker({
      map: mapInstance,
      position: [lng, lat],
      anchor: 'bottom-center',
      offset: new window.AMap.Pixel(0, -2)
    })
  }
}

function clearLocation() {
  selectedLng.value = ''
  selectedLat.value = ''
  if (pointMarker) {
    pointMarker.setMap(null)
    pointMarker = null
  }
}

function zoomIn() {
  mapInstance?.zoomIn?.()
}

function zoomOut() {
  mapInstance?.zoomOut?.()
}

// 执行归属查询
async function doDispatch() {
  if (!selectedCaseType.value && !questionText.value.trim()) return

  querying.value = true
  dispatchResult.value = null

  try {
    const payload = {}
    if (selectedCaseType.value) payload.case_type_id = selectedCaseType.value
    if (questionText.value.trim()) payload.question = questionText.value.trim()
    if (selectedLng.value && selectedLat.value) {
      payload.location = { lng: parseFloat(selectedLng.value), lat: parseFloat(selectedLat.value) }
    }

    const res = await axios.post('/api/dispatch/query', payload, { headers: getAuthHeaders() })
    dispatchResult.value = res.data
    rightPanelCollapsed.value = false
  } catch (e) {
    console.error('归属查询失败:', e)
    dispatchResult.value = {
      success: false,
      department: null,
      unit: null,
      in_jurisdiction: false,
      layer_status: 'error',
      answer: '查询失败，请稍后重试',
    }
    rightPanelCollapsed.value = false
  } finally {
    querying.value = false
  }
}

// 主题切换
watch(() => themeStore.theme, (t) => {
  if (mapInstance) {
    mapInstance.setMapStyle(t === 'light' ? 'amap://styles/normal' : 'amap://styles/dark')
  }
})

onMounted(async () => {
  await loadCaseTypes()
  await nextTick()
  await initMap()
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
  }
  pointMarker = null
})
</script>

<style scoped>
.dispatch-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #0a1628;
  z-index: 9999;
  display: flex;
  flex-direction: column;
}

/* 顶部标题栏 */
.dispatch-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(13, 31, 60, 0.95);
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
  position: relative;
  z-index: 200;
  flex-shrink: 0;
  min-height: 50px;
}

.header-left { flex: 1; }

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}
.back-btn:hover { color: #409eff; }

.header-center { flex: 2; text-align: center; }

.dispatch-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(90deg, #409eff, #00c6fb);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.title-icon { color: #409eff; -webkit-text-fill-color: #409eff; flex-shrink: 0; }

.header-right { flex: 1; text-align: right; }
.header-subtitle { font-size: 13px; color: rgba(255, 255, 255, 0.5); }

/* 全屏地图 */
.map-fullscreen {
  position: fixed;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}
.map-element { width: 100%; height: 100%; }

/* 地图工具栏 */
.map-toolbar {
  position: fixed;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  z-index: 250;
}
.toolbar-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 31, 60, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.4);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s;
}
.toolbar-btn:hover { background: rgba(64, 158, 255, 0.3); color: #fff; }

/* 面板切换按钮 */
.panel-toggle-btn {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 56px;
  background: rgba(13, 31, 60, 0.9);
  border: 1px solid rgba(64, 158, 255, 0.4);
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  z-index: 150;
}
.panel-toggle-btn:hover { background: rgba(64, 158, 255, 0.4); color: #fff; }

.left-toggle {
  left: 0;
  border-radius: 0 8px 8px 0;
  border-left: none;
}
.left-toggle:not(.collapsed) { left: 280px; }

.right-toggle {
  right: 0;
  border-radius: 8px 0 0 8px;
  border-right: none;
}
.right-toggle:not(.collapsed) { right: 280px; }

/* 悬浮面板 */
.floating-panel {
  position: fixed;
  top: 50px;
  bottom: 0;
  width: 280px;
  z-index: 100;
  background: rgba(13, 31, 60, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(64, 158, 255, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: transform 0.3s ease;
}
.floating-panel::-webkit-scrollbar { width: 4px; }
.floating-panel::-webkit-scrollbar-track { background: transparent; }
.floating-panel::-webkit-scrollbar-thumb { background: rgba(64, 158, 255, 0.2); border-radius: 2px; }

.left-panel { left: 0; }
.left-panel.collapsed { transform: translateX(-280px); }

.right-panel { right: 0; }
.right-panel.collapsed { transform: translateX(280px); }

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  color: #fff;
  flex-shrink: 0;
}
.panel-header h3 { margin: 0; font-size: 16px; font-weight: 600; }

/* 查询内容 */
.query-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.query-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.query-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.optional {
  font-weight: 400;
  color: rgba(255, 255, 255, 0.35);
  font-size: 12px;
}
.query-select {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
  margin-bottom: 8px;
}
.query-select:focus { border-color: #409eff; }
.query-select:disabled { opacity: 0.5; cursor: not-allowed; }
.query-select option { background: #0d1f3c; color: #fff; }

.query-textarea {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
}
.query-textarea:focus { border-color: #409eff; }
.query-textarea::placeholder { color: rgba(255, 255, 255, 0.3); }

/* 坐标信息 */
.location-info {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: rgba(64, 158, 255, 0.15);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  font-size: 13px;
}
.loc-label { color: rgba(255, 255, 255, 0.5); }
.loc-value { color: #409eff; font-weight: 500; font-family: monospace; }
.loc-sep { color: rgba(255, 255, 255, 0.2); margin: 0 4px; }
.loc-clear {
  margin-left: auto;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 16px;
  border-radius: 50%;
  transition: all 0.2s;
}
.loc-clear:hover { background: rgba(245, 108, 108, 0.2); color: #f56c6c; }

.location-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
}

/* 查询按钮 */
.query-btn {
  width: 100%;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: linear-gradient(135deg, #409eff, #00c6fb);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.query-btn:hover:not(:disabled) { background: linear-gradient(135deg, #2b7de9, #00a8e0); }
.query-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.spin-icon { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 结果面板 */
.result-content {
  padding: 16px;
}
.result-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 16px;
}
.status-ok {
  background: rgba(39, 174, 96, 0.15);
  color: #27ae60;
  border: 1px solid rgba(39, 174, 96, 0.3);
}
.status-warn {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
  border: 1px solid rgba(230, 162, 60, 0.3);
}

.result-card {
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.result-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 4px;
}
.result-value {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}
.dept-value {
  font-weight: 600;
  color: #409eff;
}
.unit-value {
  font-weight: 600;
  color: #27ae60;
}

.layer-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.tag-ok { background: rgba(39, 174, 96, 0.15); color: #27ae60; }
.tag-warn { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }
.tag-info { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.5); }

.result-answer {
  margin-top: 16px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}
.answer-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  margin-bottom: 6px;
}
.answer-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
}

/* 空结果 */
.empty-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
}
.empty-result p {
  margin-top: 12px;
  font-size: 13px;
}

/* ============ 浅色模式 ============ */
[data-theme="light"] .dispatch-page { background: #eef1f6; }
[data-theme="light"] .dispatch-header {
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid rgba(64, 158, 255, 0.25);
}
[data-theme="light"] .back-btn { color: rgba(0, 0, 0, 0.6); }
[data-theme="light"] .back-btn:hover { color: #409eff; }
[data-theme="light"] .header-subtitle { color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .toolbar-btn {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(64, 158, 255, 0.4);
  color: rgba(0, 0, 0, 0.7);
}
[data-theme="light"] .panel-toggle-btn {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(64, 158, 255, 0.4);
  color: rgba(0, 0, 0, 0.7);
}
[data-theme="light"] .floating-panel {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(64, 158, 255, 0.2);
}
[data-theme="light"] .floating-panel::-webkit-scrollbar-thumb { background: rgba(64, 158, 255, 0.3); }
[data-theme="light"] .panel-header { border-bottom: 1px solid rgba(64, 158, 255, 0.2); color: #303133; }
[data-theme="light"] .query-title { color: rgba(0, 0, 0, 0.5); }
[data-theme="light"] .optional { color: rgba(0, 0, 0, 0.35); }
[data-theme="light"] .query-select,
[data-theme="light"] .query-textarea {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.15);
  color: #303133;
}
[data-theme="light"] .query-select option { background: #fff; color: #303133; }
[data-theme="light"] .query-textarea::placeholder { color: rgba(0, 0, 0, 0.35); }
[data-theme="light"] .location-info {
  background: rgba(64, 158, 255, 0.08);
  border: 1px solid rgba(64, 158, 255, 0.2);
}
[data-theme="light"] .loc-label { color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .loc-value { color: #409eff; }
[data-theme="light"] .loc-sep { color: rgba(0, 0, 0, 0.15); }
[data-theme="light"] .loc-clear { color: rgba(0, 0, 0, 0.4); }
[data-theme="light"] .loc-clear:hover { background: rgba(245, 108, 108, 0.1); color: #f56c6c; }
[data-theme="light"] .location-hint {
  background: rgba(0, 0, 0, 0.03);
  border: 1px dashed rgba(0, 0, 0, 0.15);
  color: rgba(0, 0, 0, 0.35);
}
[data-theme="light"] .query-btn {
  background: linear-gradient(135deg, #409eff, #00c6fb);
  color: #fff;
}
[data-theme="light"] .result-card { border-bottom: 1px solid rgba(0, 0, 0, 0.06); }
[data-theme="light"] .result-label { color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .result-value { color: rgba(0, 0, 0, 0.85); }
[data-theme="light"] .dept-value { color: #409eff; }
[data-theme="light"] .unit-value { color: #27ae60; }
[data-theme="light"] .tag-ok { background: rgba(39, 174, 96, 0.1); color: #27ae60; }
[data-theme="light"] .tag-warn { background: rgba(230, 162, 60, 0.1); color: #e6a23c; }
[data-theme="light"] .tag-info { background: rgba(0, 0, 0, 0.05); color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .result-answer { background: rgba(0, 0, 0, 0.03); }
[data-theme="light"] .answer-label { color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .answer-text { color: rgba(0, 0, 0, 0.85); }
[data-theme="light"] .empty-result { color: rgba(0, 0, 0, 0.3); }
[data-theme="light"] .status-ok { background: rgba(39, 174, 96, 0.1); border-color: rgba(39, 174, 96, 0.2); }
[data-theme="light"] .status-warn { background: rgba(230, 162, 60, 0.1); border-color: rgba(230, 162, 60, 0.2); }
</style>
