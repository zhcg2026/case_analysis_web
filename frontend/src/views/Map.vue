<template>
  <div class="page-container">
    <h1 class="page-title">地图服务</h1>

    <!-- 地图容器 -->
    <div class="map-wrapper">
      <div v-if="mapLoading" class="map-loading">
        <div class="loading-spinner"></div>
        <span>地图加载中...</span>
      </div>
      <div v-else-if="mapError" class="map-error">
        <span class="error-icon">⚠️</span>
        <span>{{ mapError }}</span>
      </div>
      <div v-else ref="mapContainer" id="map-container" class="map-container"></div>

      <!-- 侧边信息面板 -->
      <div class="info-panel">
        <h3 class="panel-title">案件分布</h3>

        <div class="stats-list">
          <div class="stat-item">
            <span class="stat-label">总案件数</span>
            <span class="stat-value">{{ stats.total }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">跟进中</span>
            <span class="stat-value highlight">{{ stats.follow_up }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已结案</span>
            <span class="stat-value success">{{ stats.closed }}</span>
          </div>
        </div>

        <div class="legend">
          <h4 class="legend-title">图例</h4>
          <div class="legend-item">
            <span class="legend-color follow-up"></span>
            <span>跟进中</span>
          </div>
          <div class="legend-item">
            <span class="legend-color closed"></span>
            <span>已结案</span>
          </div>
          <div class="legend-item">
            <span class="legend-color pending"></span>
            <span>挂账案件</span>
          </div>
        </div>

        <!-- 案件列表 -->
        <div class="cases-list" v-if="casesList.length > 0">
          <h4 class="list-title">案件列表</h4>
          <div v-for="caseItem in casesList" :key="caseItem.id" class="case-item" @click="selectCase(caseItem)">
            <span class="case-status" :class="getStatusClass(caseItem.status)"></span>
            <div class="case-info">
              <div class="case-title">{{ caseItem.task_number }}</div>
              <div class="case-address">{{ caseItem.problem_desc?.slice(0, 20) }}...</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 案件详情弹窗 -->
    <div v-if="selectedCase" class="case-detail-popup">
      <div class="popup-header">
        <h3>案件详情</h3>
        <button class="close-btn" @click="selectedCase = null">×</button>
      </div>
      <div class="popup-body">
        <div class="detail-row">
          <span class="label">任务号：</span>
          <span>{{ selectedCase.task_number }}</span>
        </div>
        <div class="detail-row">
          <span class="label">描述：</span>
          <span>{{ selectedCase.problem_desc }}</span>
        </div>
        <div class="detail-row">
          <span class="label">地址：</span>
          <span>{{ selectedCase.address_desc }}</span>
        </div>
        <div class="detail-row">
          <span class="label">状态：</span>
          <span :class="['status-badge', getStatusClass(selectedCase.status)]">
            {{ selectedCase.status || '跟进中' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'

const mapContainer = ref(null)
let mapInstance = null
let markers = []

const mapLoading = ref(false)
const mapError = ref('')
const stats = ref({ total: 0, follow_up: 0, closed: 0 })
const casesList = ref([])
const selectedCase = ref(null)

function getStatusClass(status) {
  if (status === '已结案') return 'closed'
  if (status === '跟进中' || !status) return 'follow-up'
  return 'follow-up'
}

async function fetchStats() {
  try {
    const response = await axios.get('/api/cases/stats')
    stats.value = response.data || {}
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

async function fetchCases() {
  try {
    const response = await axios.get('/api/cases', {
      params: { per_page: 50 }
    })
    casesList.value = response.data.cases || []
    // 在地图上标记案件
    if (mapInstance && casesList.value.length > 0) {
      markCasesOnMap()
    }
  } catch (error) {
    console.error('获取案件失败:', error)
  }
}

function initMap() {
  if (!window.AMap) {
    mapError.value = '高德地图加载失败，请刷新页面重试'
    return
  }

  mapLoading.value = true
  mapError.value = ''

  try {
    // 初始化地图实例 - 运城市中心坐标
    mapInstance = new window.AMap.Map('map-container', {
      zoom: 13,
      center: [110.976935, 35.06161],
      resizeEnable: true,
      mapStyle: 'amap://styles/normal'
    })

    // 添加中心标记
    const centerMarker = new window.AMap.Marker({
      position: [110.976935, 35.06161],
      title: '运城市',
      map: mapInstance
    })

    const infoWindow = new window.AMap.InfoWindow({
      content: '<div style="padding:10px;"><strong>运城市智慧城市管理平台</strong></div>',
      offset: new window.AMap.Pixel(0, -30)
    })

    centerMarker.on('click', function() {
      infoWindow.open(mapInstance, centerMarker.getPosition())
    })

    mapLoading.value = false

    // 加载案件数据并在地图上标记
    fetchCases()

  } catch (error) {
    console.error('地图初始化失败:', error)
    mapError.value = '地图初始化失败: ' + error.message
    mapLoading.value = false
  }
}

function markCasesOnMap() {
  if (!mapInstance || !window.AMap) return

  // 清除旧标记
  markers.forEach(m => m.setMap(null))
  markers = []

  casesList.value.forEach((caseItem, index) => {
    // 随机偏移位置（模拟案件位置）
    const offsetLng = (Math.random() - 0.5) * 0.05
    const offsetLat = (Math.random() - 0.5) * 0.05

    const marker = new window.AMap.Marker({
      position: [110.976935 + offsetLng, 35.06161 + offsetLat],
      title: caseItem.task_number,
      map: mapInstance,
      icon: new window.AMap.Icon({
        size: new window.AMap.Size(25, 34),
        image: caseItem.status === '已结案'
          ? 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png'
          : 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png',
        imageSize: new window.AMap.Size(25, 34)
      })
    })

    marker.on('click', () => {
      selectedCase.value = caseItem
    })

    markers.push(marker)
  })
}

function selectCase(caseItem) {
  selectedCase.value = caseItem
}

onMounted(() => {
  fetchStats()
  nextTick(() => {
    initMap()
  })
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
  }
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 100%;
  height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.map-wrapper {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 500px;
}

.map-container {
  flex: 1;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  overflow: hidden;
}

.map-loading, .map-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-lighter);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.error-icon { font-size: 48px; }

.info-panel {
  width: 280px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow-y: auto;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.stats-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.stat-label {
  color: var(--text-tertiary);
  font-size: 13px;
}

.stat-value {
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.highlight { color: var(--primary-500); }
.stat-value.success { color: var(--success); }

.legend {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-lighter);
}

.legend-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 var(--space-2);
  color: var(--text-primary);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-color.follow-up { background: var(--danger); }
.legend-color.closed { background: var(--success); }
.legend-color.pending { background: var(--warning); }

.cases-list {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-lighter);
  max-height: 300px;
  overflow-y: auto;
}

.list-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 var(--space-2);
  color: var(--text-primary);
}

.case-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.case-item:hover { background: var(--fill-light); }

.case-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.case-status.follow-up { background: var(--danger); }
.case-status.closed { background: var(--success); }

.case-info { flex: 1; min-width: 0; }

.case-title {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.case-address {
  font-size: 12px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-detail-popup {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 400px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  box-shadow: var(--shadow-xl);
  z-index: 1000;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.popup-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

.close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
  font-size: 20px;
}

.close-btn:hover { background: var(--fill-light); }

.popup-body { padding: var(--space-4); }

.detail-row {
  display: flex;
  margin-bottom: var(--space-3);
}

.detail-row .label {
  width: 70px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.status-badge {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: var(--radius-full);
}

.status-badge.follow-up { background: var(--primary-100); color: var(--primary-700); }
.status-badge.closed { background: var(--success-light); color: var(--success-dark); }

@media (max-width: 768px) {
  .map-wrapper { flex-direction: column; }
  .info-panel { width: 100%; max-height: 300px; }
}
</style>