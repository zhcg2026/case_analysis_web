<template>
  <div class="case-map-page">
    <!-- 顶部标题栏 -->
    <header class="case-map-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回首页</span>
        </router-link>
      </div>
      <div class="header-center">
        <h1 class="case-map-title">
          <svg class="title-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          案件地图
        </h1>
      </div>
      <div class="header-right">
        <span class="header-subtitle">案件空间分布分析</span>
      </div>
    </header>

    <!-- 全屏地图背景 -->
    <div class="map-fullscreen">
      <div id="case-map-container" class="map-element" v-loading="loading"></div>
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
    <button class="panel-toggle-btn left-toggle" :class="{ collapsed: leftPanelCollapsed }" @click="leftPanelCollapsed = !leftPanelCollapsed" :title="leftPanelCollapsed ? '展开筛选' : '收起筛选'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline :points="leftPanelCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/>
      </svg>
    </button>

    <!-- 左侧筛选面板 -->
    <aside class="floating-panel left-panel" :class="{ collapsed: leftPanelCollapsed }">
      <div class="panel-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
        </svg>
        <h3>筛选条件</h3>
      </div>

      <div class="filter-content">
        <div class="filter-section">
          <div class="filter-title">月份</div>
          <select v-model="selectedBatches" multiple class="filter-select" @change="emitFilterChange">
            <option v-for="b in batches" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>

        <div class="filter-section">
          <div class="filter-title">时间范围</div>
          <div class="date-range">
            <input type="date" v-model="startDate" class="filter-input" @change="emitFilterChange" />
            <span class="date-sep">至</span>
            <input type="date" v-model="endDate" class="filter-input" @change="emitFilterChange" />
          </div>
        </div>

        <div class="filter-section">
          <div class="filter-title">案件大类</div>
          <select v-model="selectedBigCategory" class="filter-select" @change="handleBigCategoryChange">
            <option value="">全部</option>
            <option v-for="cat in categories" :key="cat.big_category" :value="cat.big_category">
              {{ cat.big_category }} ({{ cat.total }})
            </option>
          </select>
        </div>

        <div class="filter-section" v-if="smallCategories.length">
          <div class="filter-title">案件小类</div>
          <select v-model="selectedSmallCategory" class="filter-select" @change="emitFilterChange">
            <option value="">全部</option>
            <option v-for="sc in smallCategories" :key="sc.name" :value="sc.name">
              {{ sc.name }} ({{ sc.count }})
            </option>
          </select>
        </div>

        <div class="filter-section">
          <div class="filter-title">显示模式</div>
          <div class="mode-switch">
            <button class="mode-btn" :class="{ active: viewMode === 'heatmap' }" @click="switchMode('heatmap')">热力图</button>
            <button class="mode-btn" :class="{ active: viewMode === 'cluster' }" @click="switchMode('cluster')">聚合点</button>
          </div>
        </div>

        <div class="filter-section">
          <button class="reset-btn" @click="resetFilters">重置筛选</button>
        </div>
      </div>
    </aside>

    <!-- 右侧展开/收起按钮 -->
    <button class="panel-toggle-btn right-toggle" :class="{ collapsed: rightPanelCollapsed }" @click="rightPanelCollapsed = !rightPanelCollapsed" :title="rightPanelCollapsed ? '展开详情' : '收起详情'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline :points="rightPanelCollapsed ? '15 18 9 12 15 6' : '9 18 15 12 9 6'"/>
      </svg>
    </button>

    <!-- 右侧信息面板 -->
    <aside class="floating-panel right-panel" :class="{ collapsed: rightPanelCollapsed }">
      <div class="panel-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="16" x2="12" y2="12"/>
          <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
        <h3>基本信息</h3>
      </div>

      <!-- 统计概览 -->
      <div class="stats-overview" v-if="stats.total_cases">
        <div class="stat-row">
          <div class="stat-block">
            <span class="stat-value">{{ stats.total_cases || 0 }}</span>
            <span class="stat-label">案件总数</span>
          </div>
          <div class="stat-block highlight-completion">
            <span class="stat-value">{{ stats.completion_rate ?? 0 }}%</span>
            <span class="stat-label">结案率</span>
          </div>
        </div>
        <div class="stat-row">
          <div class="stat-block highlight-delayed">
            <span class="stat-value">{{ stats.delayed_count || 0 }}</span>
            <span class="stat-label">延期</span>
          </div>
          <div class="stat-block highlight-rework">
            <span class="stat-value">{{ stats.rework_count || 0 }}</span>
            <span class="stat-label">返工</span>
          </div>
        </div>
        <div class="stat-row" v-if="selectedBatches.length">
          <div class="stat-block wide">
            <span class="stat-value small">{{ selectedBatches.join('、') }}</span>
            <span class="stat-label">所选月份</span>
          </div>
        </div>
      </div>

      <!-- 选中案件详情 -->
      <div v-if="selectedCase" class="detail-content">
        <div class="detail-divider"></div>
        <div class="detail-header">
          <span class="detail-category" :style="{ background: getCategoryColor(selectedCase.big_category) }">
            {{ selectedCase.big_category }}
          </span>
          <span class="detail-type">{{ selectedCase.small_category }}</span>
        </div>
        <div class="detail-info">
          <div class="info-row"><span class="info-label">任务号</span><span class="info-value">{{ selectedCase.task_no }}</span></div>
          <div class="info-row"><span class="info-label">问题来源</span><span class="info-value">{{ selectedCase.source }}</span></div>
          <div class="info-row"><span class="info-label">上报时间</span><span class="info-value">{{ selectedCase.report_time }}</span></div>
          <div class="info-row"><span class="info-label">问题描述</span><span class="info-value desc">{{ selectedCase.description }}</span></div>
          <div class="info-row"><span class="info-label">地址</span><span class="info-value">{{ selectedCase.address }}</span></div>
          <div class="info-row"><span class="info-label">片区</span><span class="info-value">{{ selectedCase.district }}</span></div>
          <div class="info-row"><span class="info-label">街道</span><span class="info-value">{{ selectedCase.street }}</span></div>
          <div class="info-row"><span class="info-label">社区</span><span class="info-value">{{ selectedCase.community }}</span></div>
          <div class="info-row"><span class="info-label">处置部门</span><span class="info-value">{{ selectedCase.department }}</span></div>
          <div class="info-row"><span class="info-label">当前阶段</span><span class="info-value">{{ selectedCase.stage }}</span></div>
          <div class="info-row">
            <span class="info-label">延期</span>
            <span class="info-value" :class="selectedCase.is_delayed ? 'tag-danger' : 'tag-info'">{{ selectedCase.is_delayed ? '是' : '否' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">返工</span>
            <span class="info-value" :class="selectedCase.is_rework ? 'tag-danger' : 'tag-info'">{{ selectedCase.is_rework ? '是' : '否' }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-detail">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
          <circle cx="12" cy="10" r="3"/>
        </svg>
        <p>点击地图上的标记查看案件详情</p>
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

// 状态
const loading = ref(false)
const stats = ref({})
const categories = ref([])
const batches = ref([])
const initialBatches = ref([])
const selectedCase = ref(null)
const leftPanelCollapsed = ref(false)
const rightPanelCollapsed = ref(true)
const viewMode = ref('heatmap')

// 筛选
const selectedBatches = ref([])
const startDate = ref('')
const endDate = ref('')
const selectedBigCategory = ref('')
const selectedSmallCategory = ref('')

// 地图实例
let mapInstance = null
let markerCluster = null
let heatmapLayer = null
let debounceTimer = null

// 大类颜色
const CATEGORY_COLORS = {
  '市容环境': '#e74c3c',
  '宣传广告': '#e67e22',
  '施工管理': '#f1c40f',
  '街面秩序': '#2ecc71',
  '突发事件': '#9b59b6',
}

function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || '#3498db'
}

function getAuthHeaders() {
  const token = userStore.token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const smallCategories = computed(() => {
  if (!selectedBigCategory.value) return []
  const cat = categories.value.find(c => c.big_category === selectedBigCategory.value)
  return cat ? cat.small_categories : []
})

// 初始化地图
function initMap() {
  const AMap = window.AMap
  if (!AMap) {
    console.error('AMap not loaded')
    return
  }

  const isDark = themeStore.theme !== 'light'

  mapInstance = new AMap.Map('case-map-container', {
    zoom: 12,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: isDark ? 'amap://styles/dark' : 'amap://styles/normal'
  })

  mapInstance.on('moveend', debounceLoadData)
  mapInstance.on('zoomend', debounceLoadData)
}

function debounceLoadData() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (viewMode.value === 'heatmap') {
      loadHeatmapData()
    }
  }, 300)
}

// 加载批次列表
async function loadBatches() {
  try {
    const res = await axios.get('/api/analysis/months', { headers: getAuthHeaders() })
    if (res.data?.months?.length) {
      const monthStrs = res.data.months.map(m => m.batch)
      batches.value = monthStrs
      initialBatches.value = [monthStrs[0]]
    }
  } catch (e) {
    console.error('加载批次失败:', e)
  }
}

// 加载分类列表
async function loadCategories() {
  if (!selectedBatches.value?.length && !startDate.value && !endDate.value) return
  try {
    const res = await axios.get('/api/case-map/categories', {
      params: {
        batch: selectedBatches.value?.join(',') || '',
        big_category: selectedBigCategory.value || '',
        small_category: selectedSmallCategory.value || '',
        start_date: startDate.value || '',
        end_date: endDate.value || ''
      },
      headers: getAuthHeaders()
    })
    if (res.data?.success) {
      categories.value = res.data.categories
    }
  } catch (e) {
    console.error('加载分类失败:', e)
  }
}

// 加载统计
async function loadStats() {
  if (!selectedBatches.value?.length && !startDate.value && !endDate.value) return
  try {
    const res = await axios.get('/api/case-map/stats', {
      params: {
        batch: selectedBatches.value?.join(',') || '',
        big_category: selectedBigCategory.value || '',
        small_category: selectedSmallCategory.value || '',
        start_date: startDate.value || '',
        end_date: endDate.value || ''
      },
      headers: getAuthHeaders()
    })
    if (res.data?.success) {
      stats.value = res.data
      if (res.data.total_cases) {
        rightPanelCollapsed.value = false
      }
    }
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

// 加载地图数据
async function loadMapData() {
  if (!mapInstance) return
  if (!selectedBatches.value?.length && !startDate.value && !endDate.value) return

  loading.value = true
  try {
    if (viewMode.value === 'heatmap') {
      await loadHeatmapData()
    } else {
      await loadClusterData()
    }
  } finally {
    loading.value = false
  }
}

// 热力图数据 - 用模糊圆形标记按数量显示不同大小
async function loadHeatmapData() {
  const AMap = window.AMap
  if (!AMap || !mapInstance) return

  const params = {
    batch: selectedBatches.value.join(','),
    big_category: selectedBigCategory.value || '',
    small_category: selectedSmallCategory.value || '',
    start_date: startDate.value || '',
    end_date: endDate.value || '',
    grid_size: 0.002
  }

  try {
    const res = await axios.get('/api/case-map/heatmap', {
      params,
      headers: getAuthHeaders()
    })

    if (!res.data?.success) return

    clearMapLayers()

    const data = res.data.data
    if (!data.length) return

    const maxCount = res.data.max_count || 100
    const minSize = 16
    const maxSize = 80

    function getHeatColor(ratio) {
      if (ratio < 0.25) return { bg: 'rgba(26,152,80,0.55)', shadow: 'rgba(26,152,80,0.25)' }
      if (ratio < 0.5) return { bg: 'rgba(145,207,96,0.55)', shadow: 'rgba(145,207,96,0.25)' }
      if (ratio < 0.75) return { bg: 'rgba(254,224,139,0.6)', shadow: 'rgba(254,224,139,0.3)' }
      return { bg: 'rgba(215,48,39,0.6)', shadow: 'rgba(215,48,39,0.3)' }
    }

    const markers = data.map(d => {
      const ratio = d.count / maxCount
      const size = Math.max(minSize, Math.round(minSize + ratio * (maxSize - minSize)))
      const blur = Math.round(size * 0.25)
      const colors = getHeatColor(ratio)

      const marker = new AMap.Marker({
        position: [d.lng, d.lat],
        content: `<div style="
          width:${size}px;height:${size}px;border-radius:50%;
          background:${colors.bg};
          box-shadow: 0 0 ${blur}px ${Math.round(blur*0.5)}px ${colors.shadow};
          cursor:pointer;
        "></div>`,
        offset: new AMap.Pixel(-size / 2, -size / 2),
        zIndex: Math.round(ratio * 100),
      })

      marker.on('click', () => {
        const info = `<div style="padding:4px 8px;font-size:13px;color:#333"><b>${d.count}</b> 件</div>`
        const infoWindow = new AMap.InfoWindow({ content: info, offset: new AMap.Pixel(0, -size / 2) })
        infoWindow.open(mapInstance, [d.lng, d.lat])
      })

      return marker
    })

    heatmapLayer = markers
    mapInstance.add(markers)
  } catch (e) {
    console.error('加载热力图失败:', e)
  }
}

// 聚合点数据
async function loadClusterData() {
  const AMap = window.AMap
  if (!AMap || !mapInstance) return

  const params = {
    batch: selectedBatches.value.join(','),
    big_category: selectedBigCategory.value || '',
    small_category: selectedSmallCategory.value || '',
    start_date: startDate.value || '',
    end_date: endDate.value || '',
    per_page: 5000,
    page: 1
  }

  try {
    const res = await axios.get('/api/case-map/points', {
      params,
      headers: getAuthHeaders()
    })

    if (!res.data?.success) return

    clearMapLayers()

    const points = res.data.points
    if (!points.length) return

    const clusterData = points.map(p => ({
      lnglat: [p.lng, p.lat],
      big_category: p.big_category,
      small_category: p.small_category,
      report_time: p.report_time,
      description: p.description,
      address: p.address,
      department: p.department,
      stage: p.stage,
      is_delayed: p.is_delayed,
      is_rework: p.is_rework,
      task_no: p.task_no,
      district: p.district,
      street: p.street,
      community: p.community,
      source: p.source
    }))

    await new Promise(resolve => {
      AMap.plugin(['AMap.MarkerCluster'], resolve)
    })

    markerCluster = new AMap.MarkerCluster(mapInstance, clusterData, {
      gridSize: 60,
      maxZoom: 18,
      renderMarker: (context) => {
        const data = context.data && context.data[0] ? context.data[0] : null
        const color = data ? getCategoryColor(data.big_category) : '#3498db'
        context.marker.setContent(
          `<div style="width:10px;height:10px;border-radius:50%;background:${color};border:1px solid rgba(255,255,255,0.8);cursor:pointer"></div>`
        )
        context.marker.setOffset(new AMap.Pixel(-5, -5))
        if (data) {
          context.marker.on('click', () => {
            selectedCase.value = data
            rightPanelCollapsed.value = false
          })
        }
      },
      renderClusterMarker: (context) => {
        const count = context.count
        const size = Math.min(24 + Math.sqrt(count) * 2, 60)
        context.marker.setContent(
          `<div style="width:${size}px;height:${size}px;border-radius:50%;background:rgba(52,152,219,0.75);color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;border:2px solid rgba(255,255,255,0.5);cursor:pointer">${count}</div>`
        )
        context.marker.setOffset(new AMap.Pixel(-size / 2, -size / 2))
      }
    })
  } catch (e) {
    console.error('加载聚合点失败:', e)
  }
}

// 清除地图图层
function clearMapLayers() {
  const AMap = window.AMap
  if (!AMap) return

  if (heatmapLayer) {
    if (Array.isArray(heatmapLayer)) {
      mapInstance.remove(heatmapLayer)
    } else {
      heatmapLayer.setMap(null)
    }
    heatmapLayer = null
  }
  if (markerCluster) {
    markerCluster.setMap(null)
    markerCluster = null
  }
}

// 筛选变化
async function emitFilterChange() {
  if (!selectedBatches.value?.length && !startDate.value && !endDate.value) {
    clearMapLayers()
    stats.value = {}
    categories.value = []
    return
  }
  await Promise.all([loadCategories(), loadStats(), loadMapData()])
}

function handleBigCategoryChange() {
  selectedSmallCategory.value = ''
  emitFilterChange()
}

function switchMode(mode) {
  viewMode.value = mode
  loadMapData()
}

function resetFilters() {
  selectedBatches.value = []
  startDate.value = ''
  endDate.value = ''
  selectedBigCategory.value = ''
  selectedSmallCategory.value = ''
  viewMode.value = 'heatmap'
  clearMapLayers()
  stats.value = {}
  categories.value = []
  selectedCase.value = null
  rightPanelCollapsed.value = true
}

function zoomIn() {
  if (mapInstance) mapInstance.zoomIn()
}

function zoomOut() {
  if (mapInstance) mapInstance.zoomOut()
}

// 主题监听
watch(() => themeStore.theme, (t) => {
  if (mapInstance && typeof mapInstance.setMapStyle === 'function') {
    mapInstance.setMapStyle(t === 'light' ? 'amap://styles/normal' : 'amap://styles/dark')
  }
})

onMounted(async () => {
  await nextTick()
  initMap()
  await loadBatches()
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  clearMapLayers()
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
  }
})
</script>

<style scoped>
.case-map-page {
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
.case-map-header {
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

.case-map-title {
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

/* 筛选面板内容 */
.filter-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-select, .filter-input {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.filter-select:focus, .filter-input:focus { border-color: #409eff; }
.filter-select option { background: #0d1f3c; color: #fff; }

.date-range {
  display: flex;
  align-items: center;
  gap: 6px;
}
.date-range .filter-input {
  width: 100%;
  flex: 1;
  min-width: 0;
  max-width: calc(50% - 3px);
}
.date-sep { font-size: 12px; color: rgba(255, 255, 255, 0.4); flex-shrink: 0; }
.filter-input { padding: 6px 8px; font-size: 12px; }

.mode-switch {
  display: flex;
  gap: 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.mode-btn {
  flex: 1;
  padding: 8px 0;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn.active {
  background: rgba(64, 158, 255, 0.25);
  color: #fff;
  font-weight: 600;
}
.mode-btn:hover:not(.active) { background: rgba(255, 255, 255, 0.1); }

.reset-btn {
  width: 100%;
  padding: 8px 0;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.reset-btn:hover { background: rgba(255, 255, 255, 0.15); color: #fff; }

/* 右侧统计面板 */
.stats-overview {
  padding: 12px 16px;
  flex-shrink: 0;
}
.stat-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.stat-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}
.stat-block.wide { flex: 1; }
.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
}
.stat-value.small { font-size: 12px; font-weight: 500; }
.stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}
.highlight-delayed .stat-value { color: #e67e22; }
.highlight-rework .stat-value { color: #e74c3c; }
.highlight-completion .stat-value { color: #27ae60; }

/* 案件详情 */
.detail-divider {
  height: 1px;
  background: rgba(64, 158, 255, 0.15);
  margin: 0 16px;
}
.detail-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 16px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px 8px;
}
.detail-category {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
}
.detail-type {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
.detail-info {
  padding: 0 16px;
}
.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.info-label { color: rgba(255, 255, 255, 0.45); flex-shrink: 0; }
.info-value { color: rgba(255, 255, 255, 0.85); text-align: right; margin-left: 12px; word-break: break-all; }
.info-value.desc { text-align: left; margin-left: 0; }
.tag-danger { color: #f56c6c; font-weight: 600; }
.tag-info { color: rgba(255, 255, 255, 0.5); }

.empty-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
  padding: 40px 20px;
  text-align: center;
}
.empty-detail p { margin: 16px 0 0; font-size: 13px; }

/* ============ 浅色模式 ============ */
[data-theme="light"] .case-map-page { background: #eef1f6; }
[data-theme="light"] .case-map-header {
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
[data-theme="light"] .filter-title { color: rgba(0, 0, 0, 0.5); }
[data-theme="light"] .filter-select,
[data-theme="light"] .filter-input {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.15);
  color: #303133;
}
[data-theme="light"] .filter-select option { background: #fff; color: #303133; }
[data-theme="light"] .date-sep { color: rgba(0, 0, 0, 0.4); }
[data-theme="light"] .mode-switch { border: 1px solid rgba(0, 0, 0, 0.15); }
[data-theme="light"] .mode-btn { background: rgba(0, 0, 0, 0.03); color: rgba(0, 0, 0, 0.6); }
[data-theme="light"] .mode-btn.active { background: rgba(64, 158, 255, 0.15); color: #409eff; }
[data-theme="light"] .reset-btn {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.15);
  color: rgba(0, 0, 0, 0.6);
}
[data-theme="light"] .stat-block { background: rgba(0, 0, 0, 0.03); }
[data-theme="light"] .stat-value { color: rgba(0, 0, 0, 0.85); }
[data-theme="light"] .stat-label { color: rgba(0, 0, 0, 0.4); }
[data-theme="light"] .detail-type { color: rgba(0, 0, 0, 0.6); }
[data-theme="light"] .detail-divider { background: rgba(64, 158, 255, 0.2); }
[data-theme="light"] .info-label { color: rgba(0, 0, 0, 0.45); }
[data-theme="light"] .info-value { color: rgba(0, 0, 0, 0.85); }
[data-theme="light"] .tag-info { color: rgba(0, 0, 0, 0.4); }
[data-theme="light"] .empty-detail { color: rgba(0, 0, 0, 0.3); }
</style>
