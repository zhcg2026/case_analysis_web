<template>
  <div class="page-container">
    <h1 class="page-title">地图服务</h1>

    <!-- 顶部控制面板 -->
    <div class="top-panel">
      <!-- 管辖范围切换 -->
      <div class="dept-switcher">
        <span class="switcher-label">管辖范围：</span>
        <div class="dept-buttons">
          <button
            v-for="dept in departments"
            :key="dept.key"
            class="dept-btn"
            :class="{ active: activeDept === dept.key }"
            :style="{ '--dept-color': dept.color }"
            @click="toggleDept(dept.key)"
          >
            <span class="dept-dot"></span>
            {{ dept.name }}
          </button>
        </div>
      </div>

      <!-- 当前选中的片区信息 -->
      <div v-if="activeDept" class="dept-info">
        <span class="info-text">{{ activeDept }}片区 · 点击地图查看详情</span>
      </div>
    </div>

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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const mapContainer = ref(null)
let mapInstance = null
let geoJsonPolygons = [] // 存储管辖范围多边形
let roadPolylines = [] // 存储市政道路线
let selectedPointMarker = null // 存储用户定位点标记

const mapLoading = ref(false)
const mapError = ref('')

// 管辖范围相关
const activeDept = ref('')
const geoJsonData = ref(null)
const gardenGeoJsonData = ref(null)

// 部门配置（颜色和名称）
const departments = [
  { key: '环卫', name: '环卫', color: '#22c55e' },
  { key: '执法', name: '执法', color: '#ef4444' },
  { key: '园林', name: '园林', color: '#10b981' },
  { key: '市政', name: '市政', color: '#f59e0b' }
]

const propertyLabelMap = {
  id: '编号',
  zone_code: '片区编码',
  zone_name: '片区名称',
  dept: '部门',
  manager_org: '责任单位',
  manager_person: '责任人',
  manager_phone: '联系电话',
  remark: '备注',
  area_m2: '面积(㎡)',
  created_at: '创建时间',
  updated_at: '更新时间',
  name: '名称'
}

function buildInfoRows(properties = {}) {
  return Object.entries(properties)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => {
      const label = propertyLabelMap[key] || key
      return `
        <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 8px;border-radius:8px;background:#f8fafc;">
          <span style="flex:0 0 78px;font-size:12px;color:#64748b;line-height:1.5;">${label}</span>
          <span style="flex:1;font-size:13px;color:#1e293b;line-height:1.5;font-weight:500;word-break:break-all;">${value}</span>
        </div>
      `
    })
    .join('')
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

    // 记录用户点击的定位点，供知识库问答页面复用
    mapInstance.on('click', (event) => {
      const lng = event?.lnglat?.getLng?.()
      const lat = event?.lnglat?.getLat?.()
      if (typeof lng !== 'number' || typeof lat !== 'number') {
        return
      }
      saveSelectedLocation(lng, lat)
      renderSelectedPointMarker([lng, lat])
    })

    restoreSelectedLocationMarker()

    mapLoading.value = false

  } catch (error) {
    console.error('地图初始化失败:', error)
    mapError.value = '地图初始化失败: ' + error.message
    mapLoading.value = false
  }
}

function saveSelectedLocation(lng, lat) {
  const payload = {
    lng: Number(lng.toFixed(6)),
    lat: Number(lat.toFixed(6)),
    timestamp: Date.now()
  }
  localStorage.setItem('selected_map_location', JSON.stringify(payload))
  window.dispatchEvent(new CustomEvent('map-location-updated', { detail: payload }))
}

function getSavedLocation() {
  try {
    const raw = localStorage.getItem('selected_map_location')
    if (!raw) return null
    const location = JSON.parse(raw)
    if (typeof location?.lng !== 'number' || typeof location?.lat !== 'number') {
      return null
    }
    return location
  } catch (error) {
    console.error('读取定位点失败:', error)
    return null
  }
}

function renderSelectedPointMarker(position) {
  if (!mapInstance) return
  if (!selectedPointMarker) {
    selectedPointMarker = new window.AMap.Marker({
      map: mapInstance,
      anchor: 'bottom-center',
      offset: new window.AMap.Pixel(0, -2)
    })
  }
  selectedPointMarker.setPosition(position)
  selectedPointMarker.setTitle('已选定位点')
}

function restoreSelectedLocationMarker() {
  const location = getSavedLocation()
  if (!location) return
  renderSelectedPointMarker([location.lng, location.lat])
}

// 加载GeoJSON管辖范围数据
async function loadGeoJson() {
  try {
    const response = await fetch('/data/guanxia.geojson')
    const data = await response.json()
    geoJsonData.value = data
    console.log('GeoJSON数据加载成功:', data.features?.length, '个片区')
  } catch (error) {
    console.error('加载GeoJSON失败:', error)
  }
}

// 加载园林片区GeoJSON数据
async function loadGardenGeoJson() {
  try {
    const response = await fetch('/data/园林片区.geojson')
    const data = await response.json()
    gardenGeoJsonData.value = data
    console.log('园林片区数据加载成功:', data.features?.length, '个片区')
  } catch (error) {
    console.error('加载园林片区GeoJSON失败:', error)
  }
}

// 加载市政道路GeoJSON数据
let roadData = null
async function loadRoadData() {
  try {
    const response = await fetch('/data/市政管辖道路.geojson')
    roadData = await response.json()
    console.log('市政道路数据加载成功:', roadData.features?.length, '条道路')
  } catch (error) {
    console.error('加载市政道路数据失败:', error)
  }
}

// 切换部门显示
function toggleDept(deptKey) {
  if (activeDept.value === deptKey) {
    // 再次点击则隐藏
    clearPolygons()
    clearRoads()
    activeDept.value = ''
    return
  }

  // 清除现有图层，显示新选中的部门
  clearPolygons()
  clearRoads()
  activeDept.value = deptKey
  showDeptPolygons(deptKey)

  // 如果是市政部门，显示道路
  if (deptKey === '市政') {
    showRoads()
  }
}

// 显示指定部门的多边形
function showDeptPolygons(deptKey) {
  if (!mapInstance) return

  const deptConfig = departments.find(d => d.key === deptKey)
  if (!deptConfig) return

  const sourceData = deptKey === '园林' && gardenGeoJsonData.value
    ? gardenGeoJsonData.value
    : geoJsonData.value

  if (!sourceData) return

  const features = sourceData.features.filter(f => f.properties.dept === deptKey)

  features.forEach(feature => {
    if (feature.geometry.type === 'Polygon') {
      const coordinates = feature.geometry.coordinates[0].map(coord => [coord[0], coord[1]])

      const polygon = new window.AMap.Polygon({
        path: coordinates,
        strokeColor: deptConfig.color,
        strokeWeight: 2,
        strokeOpacity: 0.8,
        fillColor: deptConfig.color,
        fillOpacity: 0.3,
        map: mapInstance
      })

      // 点击显示片区信息
      polygon.on('click', () => {
        const zoneLabel = feature.properties.zone_name || feature.properties.name || '未命名片区'
        const detailRows = buildInfoRows(feature.properties)
        const infoWindow = new window.AMap.InfoWindow({
          content: `<div style="width:300px;max-width:90vw;padding:12px;background:#ffffff;border-radius:12px;box-shadow:0 10px 28px rgba(15,23,42,0.18);border:1px solid #e2e8f0;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;">
              <div style="font-size:15px;font-weight:700;color:#0f172a;line-height:1.4;">${zoneLabel}</div>
              <span style="padding:3px 10px;border-radius:999px;background:#ecfeff;color:#0f766e;font-size:12px;font-weight:600;">${feature.properties.dept || '园林'}</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;max-height:220px;overflow:auto;padding-right:2px;">
              ${detailRows || '<div style="font-size:13px;color:#64748b;padding:8px;">暂无属性信息</div>'}
            </div>
          </div>`,
          offset: new window.AMap.Pixel(0, -10)
        })
        infoWindow.open(mapInstance, polygon.getBounds().getCenter())
      })

      geoJsonPolygons.push(polygon)
    }
  })

  console.log(`显示 ${deptKey} 的 ${features.length} 个片区`)
}

// 清除所有多边形
function clearPolygons() {
  geoJsonPolygons.forEach(polygon => {
    polygon.setMap(null)
  })
  geoJsonPolygons = []
}

// 显示市政道路
function showRoads() {
  if (!mapInstance || !roadData) return

  // 根据road_type设置不同宽度
  const roadWidths = {
    1: 8,  // 主干道
    2: 5,  // 次干道
    3: 3   // 支路
  }

  roadData.features.forEach(feature => {
    if (feature.geometry.type === 'LineString') {
      const coordinates = feature.geometry.coordinates.map(coord => [coord[0], coord[1]])
      const roadType = feature.properties.road_type || 2
      const strokeWidth = roadWidths[roadType] || 5

      const polyline = new window.AMap.Polyline({
        path: coordinates,
        strokeColor: '#f59e0b', // 市政部门颜色
        strokeWeight: strokeWidth,
        strokeOpacity: 0.9,
        map: mapInstance
      })

      // 点击显示道路信息（使用点击点坐标，避免长道路中心点偏移）
      polyline.on('click', (event) => {
        const infoWindow = new window.AMap.InfoWindow({
          content: `<div style="padding:12px 16px;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15);min-width:150px;">
            <div style="font-size:15px;font-weight:600;color:#333;margin-bottom:8px;border-bottom:1px solid #eee;padding-bottom:6px;">市政管辖道路</div>
            <div style="font-size:13px;color:#333;line-height:1.8;">
              <span style="color:#666;">道路名称：</span><span style="color:#f59e0b;font-weight:500;">${feature.properties.道路名称 || '未命名'}</span><br/>
              <span style="color:#666;">道路编号：</span><span>${feature.properties.编号 || '-'}</span><br/>
              <span style="color:#666;">道路类型：</span><span>${roadType === 1 ? '主干道' : roadType === 2 ? '次干道' : '支路'}</span>
            </div>
          </div>`,
          offset: new window.AMap.Pixel(0, -10)
        })
        const clickPosition = event?.lnglat || polyline.getBounds().getCenter()
        infoWindow.open(mapInstance, clickPosition)
      })

      roadPolylines.push(polyline)
    }
  })

  console.log(`显示 ${roadPolylines.length} 条市政道路`)
}

// 清除道路线
function clearRoads() {
  roadPolylines.forEach(polyline => {
    polyline.setMap(null)
  })
  roadPolylines = []
}

onMounted(() => {
  loadGeoJson() // 加载GeoJSON数据
  loadGardenGeoJson() // 加载园林片区数据
  loadRoadData() // 加载市政道路数据
  nextTick(() => {
    initMap()
  })
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
  }
  mapInstance = null
  selectedPointMarker = null
})
</script>

<style scoped>
.page-container {
  padding: var(--space-4);
  max-width: 100%;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
  flex-shrink: 0;
}

.top-panel {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.dept-switcher {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.switcher-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.dept-buttons {
  display: flex;
  gap: var(--space-2);
}

.dept-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dept-btn:hover {
  color: var(--text-primary);
  border-color: var(--primary-300);
  background: var(--fill-light);
}

.dept-btn.active {
  color: var(--primary-600);
  background: var(--primary-50);
  border-color: var(--primary-300);
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.1) inset;
}

.dept-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dept-color);
  flex-shrink: 0;
}

.dept-info {
  padding: 6px 12px;
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: 999px;
}

.info-text {
  font-size: 12px;
  font-weight: 500;
  color: var(--primary-600);
}

.map-wrapper {
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
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

@media (max-width: 768px) {
  .top-panel { flex-direction: column; align-items: flex-start; }
  .dept-buttons { flex-wrap: wrap; }
}
</style>