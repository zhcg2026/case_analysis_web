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
        <!-- 管辖范围切换 -->
        <div class="dept-switcher">
          <h4 class="switcher-title">管辖范围</h4>
          <div class="dept-buttons">
            <button
              v-for="dept in departments"
              :key="dept.key"
              class="dept-btn"
              :class="{ active: activeDept === dept.key }"
              :style="{ borderColor: dept.color }"
              @click="toggleDept(dept.key)"
            >
              {{ dept.name }}
            </button>
          </div>
        </div>

        <!-- 当前选中的片区信息 -->
        <div v-if="activeDept" class="dept-info">
          <h4 class="info-title">{{ activeDept }}片区</h4>
          <p class="info-desc">点击地图上的片区查看详情</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const mapContainer = ref(null)
let mapInstance = null
let geoJsonPolygons = [] // 存储管辖范围多边形

const mapLoading = ref(false)
const mapError = ref('')

// 管辖范围相关
const activeDept = ref('')
const geoJsonData = ref(null)

// 部门配置（颜色和名称）
const departments = [
  { key: '环卫', name: '环卫', color: '#22c55e' },
  { key: '执法', name: '执法', color: '#ef4444' },
  { key: '园林', name: '园林', color: '#10b981' },
  { key: '市政', name: '市政', color: '#f59e0b' }
]

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

    mapLoading.value = false

  } catch (error) {
    console.error('地图初始化失败:', error)
    mapError.value = '地图初始化失败: ' + error.message
    mapLoading.value = false
  }
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

// 切换部门显示
function toggleDept(deptKey) {
  if (activeDept.value === deptKey) {
    // 再次点击则隐藏
    clearPolygons()
    activeDept.value = ''
    return
  }

  // 清除现有图层，显示新选中的部门
  clearPolygons()
  activeDept.value = deptKey
  showDeptPolygons(deptKey)
}

// 显示指定部门的多边形
function showDeptPolygons(deptKey) {
  if (!mapInstance || !geoJsonData.value) return

  const deptConfig = departments.find(d => d.key === deptKey)
  if (!deptConfig) return

  const features = geoJsonData.value.features.filter(f => f.properties.dept === deptKey)

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
        const infoWindow = new window.AMap.InfoWindow({
          content: `<div style="padding:10px;">
            <strong>${feature.properties.dept} - ${feature.properties.name}</strong>
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

onMounted(() => {
  loadGeoJson() // 加载GeoJSON数据
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

.dept-switcher {
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.switcher-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.dept-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.dept-btn {
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 2px solid var(--border-lighter);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.dept-btn:hover {
  background: var(--fill-light);
}

.dept-btn.active {
  background: var(--primary-50);
  color: var(--primary-600);
}

.dept-info {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-1);
}

.info-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

@media (max-width: 768px) {
  .map-wrapper { flex-direction: column; }
  .info-panel { width: 100%; max-height: 300px; }
}
</style>