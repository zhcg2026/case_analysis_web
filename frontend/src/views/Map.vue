<template>
  <div class="urban-map-page">
    <!-- 顶部标题栏 -->
    <header class="urban-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回首页</span>
        </router-link>
      </div>
      <div class="header-center">
        <h1 class="urban-title">
          <svg class="title-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M3 3v18h18"/>
            <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/>
          </svg>
          数图城管
        </h1>
      </div>
      <div class="header-right">
        <span class="header-subtitle">城市管理要素展示</span>
      </div>
    </header>

    <!-- 全屏地图背景 -->
    <div class="map-fullscreen">
      <div id="urban-map" class="map-element"></div>
    </div>

    <!-- 地图工具栏 -->
    <div class="map-toolbar">
      <button class="toolbar-btn" @click="zoomIn" title="放大">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
      <button class="toolbar-btn" @click="zoomOut" title="缩小">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
      </button>
      <button class="toolbar-btn" :class="{ active: mapMode === 'add' }" @click="toggleAddMode" title="添加标记" v-if="isAdmin">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>
    </div>

    <!-- 左侧展开/收起按钮 -->
    <button class="panel-toggle-btn left-toggle" :class="{ collapsed: leftPanelCollapsed }" @click="leftPanelCollapsed = !leftPanelCollapsed" :title="leftPanelCollapsed ? '展开图层' : '收起图层'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline :points="leftPanelCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/>
      </svg>
    </button>

    <!-- 左侧图层面板 -->
    <aside class="floating-panel left-panel" :class="{ collapsed: leftPanelCollapsed }">
      <div class="panel-header">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12 2 2 7 12 12 22 7 12 2"/>
          <polyline points="2 17 12 22 22 17"/>
          <polyline points="2 12 12 17 22 12"/>
        </svg>
        <h3>图层控制</h3>
      </div>

      <!-- 搜索框 -->
      <div class="search-box">
        <input type="text" v-model="searchQuery" placeholder="搜索..." class="search-input" />
      </div>

      <!-- 图层列表 -->
      <div class="layer-list">
        <div v-for="group in filteredLayers" :key="group.id" class="layer-group">
          <div class="layer-group-header" @click="group.expanded = !group.expanded">
            <svg :class="{ expanded: group.expanded }" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
            <span class="group-name">{{ group.name }}</span>
            <span class="group-count">{{ group.children.length }}</span>
          </div>
          <div v-show="group.expanded" class="layer-children">
            <label v-for="layer in group.children" :key="layer.id" class="layer-item">
              <input type="checkbox" :checked="layer.visible" @change="toggleLayer(layer, $event)" />
              <span class="layer-icon">{{ layer.icon }}</span>
              <span class="layer-name">{{ layer.name }}</span>
              <span class="layer-count">{{ getLayerCount(layer) }}</span>
            </label>
          </div>
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
        <h3>详细信息</h3>
      </div>

      <!-- 选中项详情 -->
      <div v-if="selectedItem" class="detail-content">
        <div class="detail-header">
          <span class="detail-category" :style="{ background: getItemColor(selectedItem.category) }">{{ getItemCategoryName(selectedItem.category) }}</span>
          <span class="detail-type">{{ selectedItem.subcategory }}</span>
        </div>
        <h4 class="detail-name">{{ selectedItem.name }}</h4>
        <p class="detail-desc">{{ selectedItem.description || '暂无描述' }}</p>
        <div v-if="selectedItem.images && selectedItem.images.length" class="detail-images">
          <img v-for="(img, idx) in selectedItem.images" :key="idx" :src="img" class="detail-image" @click="previewImage(img)" />
        </div>
        <div class="detail-info">
          <div class="info-row">
            <span class="info-label">经度</span>
            <span class="info-value">{{ selectedItem.longitude }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">纬度</span>
            <span class="info-value">{{ selectedItem.latitude }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">创建时间</span>
            <span class="info-value">{{ formatDate(selectedItem.created_at) }}</span>
          </div>
        </div>
        <div v-if="isAdmin" class="detail-actions">
          <button class="btn-edit" @click="editItem(selectedItem)">编辑</button>
          <button class="btn-delete" @click="deleteItem(selectedItem)">删除</button>
        </div>
      </div>
      <div v-else class="empty-detail">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="16" x2="12" y2="12"/>
          <line x1="12" y1="8" x2="12.01" y2="8"/>
        </svg>
        <p>点击地图上的标记查看详情</p>
      </div>
    </aside>

    <!-- 底部统计栏 -->
    <div class="bottom-stats">
      <div v-for="stat in categoryStats" :key="stat.key" class="stat-item">
        <span class="stat-icon">{{ stat.icon }}</span>
        <span class="stat-name">{{ stat.name }}</span>
        <span class="stat-value">{{ stat.count }}</span>
      </div>
    </div>

    <!-- 添加/编辑标记弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showMarkerForm" @click="showMarkerForm = false">
        <div class="modal-panel marker-form-panel" @click.stop>
          <div class="modal-header">
            <h3>{{ editingMarker ? '编辑标记' : '添加标记' }}</h3>
            <button class="modal-close" @click="showMarkerForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>分类</label>
              <select v-model="markerForm.category" class="form-select">
                <option value="">请选择分类</option>
                <option v-for="group in layers" :key="group.id" :value="group.id">{{ group.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>子类型</label>
              <select v-model="markerForm.subcategory" class="form-select" :disabled="!markerForm.category">
                <option value="">请选择子类型</option>
                <option v-for="child in getChildrenByCategory(markerForm.category)" :key="child.id" :value="child.id">{{ child.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>名称 *</label>
              <input type="text" v-model="markerForm.name" class="form-input" placeholder="请输入名称" />
            </div>
            <div class="form-group">
              <label>描述</label>
              <textarea v-model="markerForm.description" class="form-textarea" placeholder="请输入描述" rows="3"></textarea>
            </div>
            <div class="form-group">
              <label>经度</label>
              <input type="text" v-model="markerForm.longitude" class="form-input" readonly />
            </div>
            <div class="form-group">
              <label>纬度</label>
              <input type="text" v-model="markerForm.latitude" class="form-input" readonly />
            </div>
            <div class="form-group">
              <label>图片</label>
              <div class="image-upload">
                <input type="file" ref="imageInput" accept="image/*" @change="handleImageUpload" hidden />
                <button class="btn-upload" @click="$refs.imageInput.click()">选择图片</button>
                <div v-if="markerForm.images.length" class="image-preview-list">
                  <div v-for="(img, idx) in markerForm.images" :key="idx" class="image-preview-item">
                    <img :src="img" />
                    <button class="btn-remove" @click="removeImage(idx)">&times;</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn-cancel" @click="showMarkerForm = false">取消</button>
            <button class="btn-save" @click="saveMarker" :disabled="!markerForm.name || !markerForm.category">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 图片预览弹窗 -->
    <transition name="modal">
      <div class="modal-overlay image-preview-overlay" v-if="previewImageUrl" @click="previewImageUrl = ''">
        <img :src="previewImageUrl" class="preview-image" />
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()

// ========== 地图状态 ==========
const mapContainer = ref(null)
let mapInstance = null
const mapLoading = ref(true)
const mapError = ref('')
const mapMode = ref('view') // view | add
const searchQuery = ref('')

// ========== 面板状态 ==========
const leftPanelCollapsed = ref(false)
const rightPanelCollapsed = ref(false)

// ========== 用户权限 ==========
const isAdmin = computed(() => userStore.isAdmin)

// ========== 标记点状态 ==========
const markers = ref([])
const selectedItem = ref(null)
const editingMarker = ref(null)
const showMarkerForm = ref(false)
const imageInput = ref(null)
const markerForm = reactive({
  category: '',
  subcategory: '',
  name: '',
  description: '',
  longitude: '',
  latitude: '',
  images: []
})

// ========== 图层配置 ==========
const layers = ref([
  {
    id: 'huanwei', name: '环卫', icon: '🗑️', expanded: true,
    children: [
      { id: 'huanwei_area', name: '管辖范围', type: 'geojson', file: '/data/guanxia.geojson', deptFilter: '环卫', visible: false, icon: '📍', color: '#22c55e' },
      { id: 'huanwei_toilet', name: '公共厕所', type: 'markers', visible: false, icon: '🚻' },
      { id: 'huanwei_station', name: '河东驿站', type: 'markers', visible: false, icon: '🏪' },
      { id: 'huanwei_transfer', name: '垃圾中转站', type: 'markers', visible: false, icon: '♻️' }
    ]
  },
  {
    id: 'yuanlin', name: '园林', icon: '🌳', expanded: true,
    children: [
      { id: 'yuanlin_area', name: '管辖范围', type: 'geojson', file: '/data/园林片区.geojson', visible: false, icon: '📍', color: '#10b981' },
      { id: 'yuanlin_park', name: '公园广场', type: 'geojson', file: '/data/公园广场.geojson', visible: false, icon: '🌳', color: '#34d399' },
      { id: 'yuanlin_small_garden', name: '小游园', type: 'markers', visible: false, icon: '🌿' },
      { id: 'yuanlin_pocket_park', name: '口袋公园', type: 'markers', visible: false, icon: '🌺' },
      { id: 'yuanlin_tree', name: '古树名木', type: 'markers', visible: false, icon: '🌲' }
    ]
  },
  {
    id: 'shizheng', name: '市政', icon: '🔧', expanded: true,
    children: [
      { id: 'shizheng_road', name: '管辖道路', type: 'geojson', file: '/data/市政管辖道路.geojson', visible: false, icon: '🛣️', color: '#f59e0b' },
      { id: 'shizheng_pipe', name: '排水管网', type: 'geojson', file: '/data/排水管网.geojson', visible: false, icon: '💧', color: '#3b82f6' }
    ]
  },
  {
    id: 'zhifa', name: '执法', icon: '🏢', expanded: true,
    children: [
      { id: 'zhifa_area', name: '管辖范围', type: 'geojson', file: '/data/执法管辖.geojson', visible: false, icon: '📍', color: '#ef4444' },
      { id: 'zhifa_post', name: '中队岗亭', type: 'markers', visible: false, icon: '🏢' }
    ]
  }
])

// ========== 地图覆盖物 ==========
const geoJsonLayers = {} // 存储GeoJSON图层（非响应式，避免代理AMap对象）
const loadedLayerIds = ref(new Set()) // 追踪已加载图层ID（响应式，驱动UI更新）
const markerLayers = {} // 存储标记点图层

// ========== 统计数据 ==========
const categoryStats = computed(() => {
  return layers.value.map(group => ({
    key: group.id,
    name: group.name,
    icon: group.icon,
    count: markers.value.filter(m => m.category === group.id).length
  }))
})

// ========== 搜索过滤 ==========
const filteredLayers = computed(() => {
  if (!searchQuery.value) return layers.value
  const query = searchQuery.value.toLowerCase()
  return layers.value.filter(group => {
    const groupMatch = group.name.toLowerCase().includes(query)
    const childMatch = group.children.some(child => child.name.toLowerCase().includes(query))
    return groupMatch || childMatch
  }).map(group => ({
    ...group,
    children: group.children.filter(child => child.name.toLowerCase().includes(query))
  }))
})

// ========== 方法 ==========

function getItemColor(category) {
  const colors = {
    huanwei: '#22c55e',
    yuanlin: '#10b981',
    shizheng: '#f59e0b',
    zhifa: '#ef4444'
  }
  return colors[category] || '#6b7280'
}

function getItemCategoryName(category) {
  const names = {
    huanwei: '环卫',
    yuanlin: '园林',
    shizheng: '市政',
    zhifa: '执法'
  }
  return names[category] || '未知'
}

function getLayerCount(layer) {
  if (layer.type === 'geojson') {
    return loadedLayerIds.value.has(layer.id) ? '已加载' : '-'
  }
  return markers.value.filter(m => m.subcategory === layer.id).length
}

function getChildrenByCategory(categoryId) {
  const group = layers.value.find(g => g.id === categoryId)
  return group ? group.children.filter(c => c.type === 'markers') : []
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

function toggleAddMode() {
  mapMode.value = mapMode.value === 'add' ? 'view' : 'add'
  if (mapInstance) {
    mapInstance.setCursor(mapMode.value === 'add' ? 'crosshair' : 'default')
  }
}

function toggleLayer(layer, event) {
  if (!mapInstance) return
  layer.visible = event.target.checked

  if (layer.type === 'geojson') {
    if (layer.visible) {
      loadGeoJsonLayer(layer)
    } else {
      removeGeoJsonLayer(layer.id)
      // 取消图层时，如果选中的项属于该图层，清空详情
      if (selectedItem.value && selectedItem.value.subcategory === layer.id) {
        selectedItem.value = null
        rightPanelCollapsed.value = true
      }
    }
  } else {
    if (layer.visible) {
      loadMarkerLayer(layer)
    } else {
      removeMarkerLayer(layer.id)
      // 取消图层时，如果选中的项属于该图层，清空详情
      if (selectedItem.value && selectedItem.value.subcategory === layer.id) {
        selectedItem.value = null
        rightPanelCollapsed.value = true
      }
    }
  }
}

async function loadGeoJsonLayer(layer) {
  try {
    const response = await fetch(layer.file)
    const data = await response.json()

    // 如果有部门过滤，只显示该部门的区域
    let features = data.features
    if (layer.deptFilter) {
      features = features.filter(f => f.properties && f.properties.dept === layer.deptFilter)
    }

    const color = layer.color || getLayerColor(layer.id)

    if (layer.id === 'shizheng_road') {
      // 市政道路 - LineString类型
      const polylines = features.map(feature => {
        let path
        if (feature.geometry.type === 'LineString') {
          path = feature.geometry.coordinates.map(c => new window.AMap.LngLat(c[0], c[1]))
        } else if (feature.geometry.type === 'MultiLineString') {
          path = feature.geometry.coordinates[0].map(c => new window.AMap.LngLat(c[0], c[1]))
        } else {
          return null
        }

        if (!path) return null

        const roadType = feature.properties?.road_type
        const strokeWidth = roadType === 1 ? 6 : roadType === 2 ? 4 : 2.5

        const polyline = new window.AMap.Polyline({
          path: path,
          strokeColor: color,
          strokeWeight: strokeWidth,
          strokeOpacity: 0.8
        })

        polyline.setExtData(feature.properties)

        polyline.on('click', () => {
          const props = feature.properties || {}
          selectedItem.value = {
            name: props.道路名称 || props.name || layer.name,
            category: 'shizheng',
            subcategory: layer.id,
            description: `编号: ${props.编号 || ''}`,
            longitude: feature.geometry.coordinates[0][0],
            latitude: feature.geometry.coordinates[0][1]
          }
          rightPanelCollapsed.value = false
        })

        return polyline
      }).filter(p => p !== null)

      geoJsonLayers[layer.id] = polylines
      polylines.forEach(p => mapInstance.add(p))
      loadedLayerIds.value.add(layer.id)
    } else {
      // Polygon类型 - 管辖范围
      const polygons = features.map(feature => {
        let path
        if (feature.geometry.type === 'Polygon') {
          path = feature.geometry.coordinates[0].map(c => new window.AMap.LngLat(c[0], c[1]))
        } else if (feature.geometry.type === 'MultiPolygon') {
          path = feature.geometry.coordinates[0][0].map(c => new window.AMap.LngLat(c[0], c[1]))
        } else {
          return null
        }

        if (!path) return null

        const polygon = new window.AMap.Polygon({
          path: path,
          fillColor: color,
          fillOpacity: 0.15,
          strokeColor: color,
          strokeWeight: 2,
          strokeOpacity: 0.8
        })

        polygon.setExtData(feature.properties)

        polygon.on('click', () => {
          const props = feature.properties || {}
          selectedItem.value = {
            name: props.name || props.zone_name || layer.name,
            category: layer.id.split('_')[0],
            subcategory: layer.id,
            description: props.remark || props.description || props.manager_org || '',
            longitude: feature.geometry.coordinates[0][0],
            latitude: feature.geometry.coordinates[0][1]
          }
          rightPanelCollapsed.value = false
        })

        return polygon
      }).filter(p => p !== null)

      geoJsonLayers[layer.id] = polygons
      polygons.forEach(p => mapInstance.add(p))
      loadedLayerIds.value.add(layer.id)
    }
  } catch (error) {
    console.error(`加载GeoJSON失败: ${layer.file}`, error)
  }
}

function removeGeoJsonLayer(layerId) {
  const polygons = geoJsonLayers[layerId]
  if (polygons) {
    polygons.forEach(p => mapInstance.remove(p))
    delete geoJsonLayers[layerId]
    loadedLayerIds.value.delete(layerId)
  }
}

function loadMarkerLayer(layer) {
  const categoryItems = markers.value.filter(m => m.subcategory === layer.id)
  const markerList = categoryItems.map(item => {
    const marker = new window.AMap.Marker({
      position: new window.AMap.LngLat(item.longitude, item.latitude),
      title: item.name,
      content: `<div style="font-size:20px;text-shadow:0 2px 4px rgba(0,0,0,0.3)">${layer.icon}</div>`,
      offset: new window.AMap.Pixel(-12, -12)
    })

    marker.on('click', () => {
      selectedItem.value = item
      rightPanelCollapsed.value = false
    })

    return marker
  })

  markerLayers[layer.id] = markerList
  markerList.forEach(m => mapInstance.add(m))
}

function removeMarkerLayer(layerId) {
  const markerList = markerLayers[layerId]
  if (markerList) {
    markerList.forEach(m => mapInstance.remove(m))
    delete markerLayers[layerId]
  }
}

function getLayerColor(layerId) {
  const colors = {
    huanwei_area: '#22c55e',
    yuanlin_area: '#10b981',
    shizheng_area: '#f59e0b',
    zhifa_area: '#ef4444',
    shizheng_pipe: '#3b82f6'
  }
  return colors[layerId] || '#6b7280'
}

function showFeatureInfo(feature) {
  const properties = feature.properties || {}
  selectedItem.value = {
    name: properties.name || properties.zone_name || '未知',
    category: 'huanwei',
    description: properties.remark || properties.description || '',
    longitude: feature.geometry.coordinates[0][0],
    latitude: feature.geometry.coordinates[0][1]
  }
  rightPanelCollapsed.value = false
}

// ========== 标记点操作 ==========

function handleMapClick(e) {
  if (mapMode.value !== 'add') return

  const lng = e.lnglat.getLng()
  const lat = e.lnglat.getLat()

  markerForm.longitude = lng.toFixed(6)
  markerForm.latitude = lat.toFixed(6)
  markerForm.name = ''
  markerForm.description = ''
  markerForm.images = []
  editingMarker.value = null
  showMarkerForm.value = true
}

function editItem(item) {
  editingMarker.value = item
  markerForm.category = item.category
  markerForm.subcategory = item.subcategory
  markerForm.name = item.name
  markerForm.description = item.description || ''
  markerForm.longitude = item.longitude
  markerForm.latitude = item.latitude
  markerForm.images = [...(item.images || [])]
  showMarkerForm.value = true
}

function deleteItem(item) {
  if (confirm(`确定删除"${item.name}"吗？`)) {
    markers.value = markers.value.filter(m => m.id !== item.id)
    saveMarkersToStorage()
    refreshMarkers()
    selectedItem.value = null
    rightPanelCollapsed.value = true
  }
}

async function saveMarker() {
  if (!markerForm.name || !markerForm.category) return

  if (editingMarker.value) {
    // 编辑模式
    const idx = markers.value.findIndex(m => m.id === editingMarker.value.id)
    if (idx !== -1) {
      markers.value[idx] = {
        ...markers.value[idx],
        category: markerForm.category,
        subcategory: markerForm.subcategory,
        name: markerForm.name,
        description: markerForm.description,
        longitude: markerForm.longitude,
        latitude: markerForm.latitude,
        images: [...markerForm.images]
      }
    }
  } else {
    // 新增模式
    const newMarker = {
      id: Date.now(),
      category: markerForm.category,
      subcategory: markerForm.subcategory,
      name: markerForm.name,
      description: markerForm.description,
      longitude: markerForm.longitude,
      latitude: markerForm.latitude,
      images: [...markerForm.images],
      created_at: new Date().toISOString()
    }
    markers.value.push(newMarker)
  }

  saveMarkersToStorage()
  refreshMarkers()
  showMarkerForm.value = false
  mapMode.value = 'view'
}

function handleImageUpload(e) {
  const file = e.target.files[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (event) => {
    markerForm.images.push(event.target.result)
  }
  reader.readAsDataURL(file)
}

function removeImage(idx) {
  markerForm.images.splice(idx, 1)
}

function previewImage(url) {
  window.open(url, '_blank')
}

function refreshMarkers() {
  // 清除所有标记图层
  Object.keys(markerLayers).forEach(key => {
    removeMarkerLayer(key)
  })
  // 重新加载可见的标记图层
  layers.value.forEach(group => {
    group.children.forEach(layer => {
      if (layer.type === 'markers' && layer.visible) {
        loadMarkerLayer(layer)
      }
    })
  })
}

function saveMarkersToStorage() {
  localStorage.setItem('urban_map_markers', JSON.stringify(markers.value))
}

function loadMarkersFromStorage() {
  try {
    const saved = localStorage.getItem('urban_map_markers')
    if (saved) {
      markers.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载标记数据失败:', e)
  }
}

// ========== 地图初始化 ==========

function initMap() {
  if (!window.AMap) {
    mapError.value = '高德地图加载失败，请刷新页面重试'
    return
  }

  try {
    mapInstance = new window.AMap.Map('urban-map', {
      zoom: 13,
      center: [110.976935, 35.06161],
      resizeEnable: true,
      mapStyle: 'amap://styles/dark'
    })

    mapInstance.on('click', handleMapClick)

    mapLoading.value = false
  } catch (error) {
    console.error('地图初始化失败:', error)
    mapError.value = '地图初始化失败: ' + error.message
    mapLoading.value = false
  }
}

function zoomIn() {
  if (mapInstance) mapInstance.zoomIn()
}

function zoomOut() {
  if (mapInstance) mapInstance.zoomOut()
}

// ========== 生命周期 ==========

onMounted(() => {
  loadMarkersFromStorage()
  nextTick(() => {
    initMap()
  })
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
  }
})
</script>

<style scoped>
.urban-map-page {
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
.urban-header {
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

.header-left {
  flex: 1;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.back-btn:hover {
  color: #409eff;
}

.header-center {
  flex: 2;
  text-align: center;
}

.urban-title {
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

.header-right {
  flex: 1;
  text-align: right;
}

.header-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

/* 全屏地图 */
.map-fullscreen {
  position: fixed;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
}

.map-element {
  width: 100%;
  height: 100%;
}

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

.toolbar-btn:hover, .toolbar-btn.active {
  background: rgba(64, 158, 255, 0.3);
  color: #fff;
}

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

.panel-toggle-btn:hover {
  background: rgba(64, 158, 255, 0.4);
  color: #fff;
}

.left-toggle {
  left: 0;
  border-radius: 0 8px 8px 0;
  border-left: none;
}

.left-toggle.collapsed {
  left: 0;
}

.floating-panel.left-panel:not(.collapsed) ~ .left-toggle,
.left-toggle:not(.collapsed) {
  left: 320px;
}

.right-toggle {
  right: 0;
  border-radius: 8px 0 0 8px;
  border-right: none;
}

.right-toggle.collapsed {
  right: 0;
}

.floating-panel.right-panel:not(.collapsed) ~ .right-toggle,
.right-toggle:not(.collapsed) {
  right: 320px;
}

/* 悬浮面板 */
.floating-panel {
  position: fixed;
  top: 50px;
  bottom: 56px;
  width: 320px;
  z-index: 100;
  background: rgba(13, 31, 60, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(64, 158, 255, 0.12);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: transform 0.3s ease;
}
.floating-panel::-webkit-scrollbar { width: 4px; }
.floating-panel::-webkit-scrollbar-track { background: transparent; }
.floating-panel::-webkit-scrollbar-thumb { background: rgba(64, 158, 255, 0.2); border-radius: 2px; }

.left-panel {
  left: 0;
}

.left-panel.collapsed {
  transform: translateX(-320px);
}

.right-panel {
  right: 0;
}

.right-panel.collapsed {
  transform: translateX(320px);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  color: #fff;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

/* 搜索框 */
.search-box {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

/* 图层列表 */
.layer-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.layer-group {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.layer-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.8);
  transition: background 0.2s;
}

.layer-group-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.layer-group-header svg {
  transition: transform 0.2s;
}

.layer-group-header svg.expanded {
  transform: rotate(0deg);
}

.group-name {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
}

.group-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 10px;
}

.layer-children {
  padding: 4px 0;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px 8px 32px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.7);
  transition: background 0.2s;
}

.layer-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.layer-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #409eff;
}

.layer-icon {
  font-size: 14px;
}

.layer-name {
  flex: 1;
  font-size: 13px;
}

.layer-count {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}

/* 详情面板 */
.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-header {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
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

.detail-name {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.detail-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin: 0 0 12px 0;
}

.detail-images {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.detail-image {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.detail-info {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.info-label {
  color: rgba(255, 255, 255, 0.5);
}

.info-value {
  color: rgba(255, 255, 255, 0.9);
}

.detail-actions {
  display: flex;
  gap: 8px;
}

.btn-edit, .btn-delete {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-edit {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
  border: 1px solid rgba(64, 158, 255, 0.3);
}

.btn-edit:hover {
  background: rgba(64, 158, 255, 0.3);
}

.btn-delete {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
  border: 1px solid rgba(245, 108, 108, 0.3);
}

.btn-delete:hover {
  background: rgba(245, 108, 108, 0.3);
}

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

.empty-detail p {
  margin: 16px 0 0;
  font-size: 13px;
}

/* 底部统计栏 */
.bottom-stats {
  position: fixed;
  bottom: 0;
  left: 320px;
  right: 320px;
  height: 56px;
  background: rgba(13, 31, 60, 0.6);
  backdrop-filter: blur(12px);
  border-top: 1px solid rgba(64, 158, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  z-index: 100;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.8);
}

.stat-icon {
  font-size: 18px;
}

.stat-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #409eff;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.marker-form-panel {
  width: 400px;
  max-height: 80vh;
  background: #0d1f3c;
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.modal-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.modal-close:hover {
  color: #fff;
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid rgba(64, 158, 255, 0.15);
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 6px;
}

.form-select, .form-input, .form-textarea {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.form-select:focus, .form-input:focus, .form-textarea:focus {
  border-color: #409eff;
}

.form-select option {
  background: #0d1f3c;
  color: #fff;
}

.btn-cancel, .btn-save {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
}

.btn-cancel:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn-save {
  background: #409eff;
  color: #fff;
}

.btn-save:hover {
  background: #66b1ff;
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 图片上传 */
.image-upload {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-upload {
  padding: 8px 16px;
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
  border: 1px dashed rgba(64, 158, 255, 0.4);
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.btn-upload:hover {
  background: rgba(64, 158, 255, 0.3);
}

.image-preview-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.image-preview-item {
  position: relative;
  width: 60px;
  height: 60px;
}

.image-preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background: #f56c6c;
  color: #fff;
  border: none;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 图片预览弹窗 */
.image-preview-overlay {
  cursor: pointer;
}

.preview-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}

/* 过渡动画 */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.2s;
}

.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
</style>
