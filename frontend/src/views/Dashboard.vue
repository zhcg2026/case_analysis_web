<template>
  <div class="dashboard-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="grid-lines"></div>
      <div class="glow-orb orb-1"></div>
      <div class="glow-orb orb-2"></div>
    </div>

    <!-- 顶部标题栏 -->
    <header class="dashboard-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回首页</span>
        </router-link>
      </div>
      <div class="header-center">
        <h1 class="dashboard-title">
          <svg class="title-icon" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M3 9h18M9 21V9"/>
          </svg>
          数据大屏
        </h1>
      </div>
      <div class="header-right">
        <div class="time-display">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>{{ currentTime }}</span>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="dashboard-main">
      <!-- 左侧面板 -->
      <aside class="dashboard-panel left-panel">
        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <h3 class="panel-title">案件统计</h3>
          </div>
          <div class="stat-cards">
            <div class="stat-card">
              <div class="stat-icon total">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
              </div>
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总案件数</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon success">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>
              <div class="stat-value success">{{ stats.completed }}</div>
              <div class="stat-label">已结案</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon warning">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
              </div>
              <div class="stat-value warning">{{ stats.pending }}</div>
              <div class="stat-label">跟进中</div>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>
              <path d="M22 12A10 10 0 0 0 12 2v10z"/>
            </svg>
            <h3 class="panel-title">案件分类</h3>
          </div>
          <div class="chart-wrapper" ref="categoryChartRef"></div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="20" x2="18" y2="10"/>
              <line x1="12" y1="20" x2="12" y2="4"/>
              <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
            <h3 class="panel-title">案件来源</h3>
          </div>
          <div class="chart-wrapper" ref="sourceChartRef"></div>
        </div>
      </aside>

      <!-- 中间地图区 -->
      <section class="dashboard-center">
        <div class="map-container" ref="mapRef">
          <div v-if="mapLoading" class="map-loading">
            <div class="loading-spinner"></div>
            <span>地图加载中...</span>
          </div>
        </div>

        <!-- 底部滚动数据 -->
        <div class="scroll-data">
          <div class="scroll-label">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
            实时案件动态
          </div>
          <div class="scroll-container">
            <div class="scroll-wrapper" ref="scrollWrapper">
              <div class="scroll-item" v-for="item in recentCases" :key="item.id">
                <span class="scroll-time">{{ item.time }}</span>
                <span class="scroll-content">{{ item.content }}</span>
                <span class="scroll-status" :class="item.status">{{ item.statusText }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <aside class="dashboard-panel right-panel">
        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            <h3 class="panel-title">本月趋势</h3>
          </div>
          <div class="chart-wrapper large" ref="trendChartRef"></div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20V10"/>
              <path d="M18 20V4"/>
              <path d="M6 20v-4"/>
            </svg>
            <h3 class="panel-title">部门排名</h3>
          </div>
          <div class="rank-list">
            <div class="rank-item" v-for="(dept, index) in departmentRanks" :key="dept.name">
              <span class="rank-num" :class="{ top: index < 3 }">{{ index + 1 }}</span>
              <div class="rank-info">
                <span class="rank-name">{{ dept.name }}</span>
                <div class="rank-bar">
                  <div class="rank-bar-fill" :style="{ width: (dept.value / 156 * 100) + '%' }"></div>
                </div>
              </div>
              <span class="rank-value">{{ dept.value }}</span>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
            <h3 class="panel-title">实时动态</h3>
          </div>
          <div class="activity-list">
            <div class="activity-item" v-for="activity in activities" :key="activity.id">
              <span class="activity-icon" :class="activity.type">
                <svg v-if="activity.type === 'add'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="16"/>
                  <line x1="8" y1="12" x2="16" y2="12"/>
                </svg>
                <svg v-else-if="activity.type === 'check'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <svg v-else-if="activity.type === 'send'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                </svg>
              </span>
              <div class="activity-content">
                <div class="activity-text">{{ activity.text }}</div>
                <div class="activity-time">{{ activity.time }}</div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

// 时间
const currentTime = ref('')
let timeInterval = null

// 地图实例
let mapInstance = null
const mapLoading = ref(true)

// 统计数据
const stats = ref({
  total: 0,
  completed: 0,
  pending: 0,
  followUp: 0,
  expiringSoon: 0
})

// 最近案件
const recentCases = ref([])

// 部门排名
const departmentRanks = ref([
  { name: '东城片区', value: 156 },
  { name: '西城片区', value: 142 },
  { name: '南城片区', value: 128 },
  { name: '北城片区', value: 115 },
  { name: '中心片区', value: 98 }
])

// 实时动态
const activities = ref([])

// 图表数据
const categoryChartData = ref([])
const sourceChartData = ref([])
const trendChartData = ref([])
const casesData = ref([])

// 图表引用
const categoryChartRef = ref(null)
const sourceChartRef = ref(null)
const trendChartRef = ref(null)
const mapRef = ref(null)
const scrollWrapper = ref(null)

let categoryChart = null
let sourceChart = null
let trendChart = null

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

async function fetchStats() {
  try {
    const response = await axios.get('/api/cases/stats')
    const data = response.data || {}
    // 字段映射
    stats.value = {
      total: data.total || 0,
      completed: data.closed || 0,
      pending: data.follow_up || 0,
      followUp: data.follow_up || 0,
      expiringSoon: data.expiring_soon || 0
    }
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

async function fetchDashboardData() {
  try {
    // 获取案件分类统计
    const categoryRes = await axios.get('/api/cases/category-stats')
    categoryChartData.value = categoryRes.data || []

    // 获取案件来源统计
    const sourceRes = await axios.get('/api/cases/source-stats')
    sourceChartData.value = sourceRes.data || []

    // 获取最近案件（用于底部滚动和实时动态）
    const recentRes = await axios.get('/api/cases', { params: { page: 1, pageSize: 10 } })
    const cases = recentRes.data.cases || []
    recentCases.value = cases.slice(0, 5).map(c => ({
      id: c.id,
      time: formatDate(c.created_at),
      content: c.problem_desc?.substring(0, 30) || c.task_number,
      status: c.status === '已结案' ? 'completed' : 'pending',
      statusText: c.status || '跟进中'
    }))

    // 生成实时动态
    activities.value = cases.slice(0, 5).map((c, i) => ({
      id: c.id,
      type: c.status === '已结案' ? 'check' : 'add',
      text: (c.problem_desc?.substring(0, 20) || c.task_number) + (c.status === '已结案' ? ' 已结案' : ' 跟进中'),
      time: formatTimeAgo(c.created_at)
    }))
  } catch (error) {
    console.error('获取大屏数据失败:', error)
    // 使用默认数据
    recentCases.value = []
    activities.value = []
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return ''
  const now = new Date()
  const d = new Date(dateStr)
  const diff = Math.floor((now - d) / 1000 / 60)
  if (diff < 60) return `${diff}分钟前`
  if (diff < 1440) return `${Math.floor(diff / 60)}小时前`
  return `${Math.floor(diff / 1440)}天前`
}

function initCharts() {
  // 案件分类图表 - 使用真实数据或默认数据
  const categoryData = categoryChartData.value.length > 0
    ? categoryChartData.value.map((item, index) => {
        const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']
        return {
          value: item.count,
          name: item.category || item.name || '未分类',
          itemStyle: { color: colors[index % colors.length] }
        }
      })
    : [
        { value: 1048, name: '市容环境', itemStyle: { color: '#409eff' } },
        { value: 735, name: '违法建设', itemStyle: { color: '#67c23a' } },
        { value: 580, name: '占道经营', itemStyle: { color: '#e6a23c' } },
        { value: 484, name: '噪音扰民', itemStyle: { color: '#f56c6c' } }
      ]

  if (categoryChartRef.value) {
    categoryChart = echarts.init(categoryChartRef.value)
    categoryChart.setOption({
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(0, 20, 40, 0.9)',
        borderColor: 'rgba(64, 158, 255, 0.3)',
        textStyle: { color: '#fff' }
      },
      series: [{
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: 'rgba(10, 22, 40, 0.8)',
          borderWidth: 2
        },
        label: {
          show: true,
          color: '#fff',
          fontSize: 11,
          formatter: '{b}\n{d}%'
        },
        labelLine: {
          lineStyle: { color: 'rgba(64, 158, 255, 0.5)' }
        },
        data: categoryData
      }]
    })
  }

  // 案件来源图表
  if (sourceChartRef.value) {
    // 使用真实数据或默认数据
    const sourceLabels = sourceChartData.value.length > 0
      ? sourceChartData.value.map(item => item.source?.substring(0, 6) || '其他')
      : ['12345', '网格员', '巡查', '其他']
    const sourceValues = sourceChartData.value.length > 0
      ? sourceChartData.value.map(item => item.count)
      : [320, 280, 180, 120]

    sourceChart = echarts.init(sourceChartRef.value)
    sourceChart.setOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(0, 20, 40, 0.9)',
        borderColor: 'rgba(64, 158, 255, 0.3)',
        textStyle: { color: '#fff' }
      },
      xAxis: {
        type: 'category',
        data: sourceLabels,
        axisLabel: { color: 'rgba(255, 255, 255, 0.7)', fontSize: 11 },
        axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.3)' } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(255, 255, 255, 0.7)', fontSize: 11 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.1)' } }
      },
      series: [{
        data: sourceValues,
        type: 'bar',
        barWidth: '50%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.3)' }
          ]),
          borderRadius: [4, 4, 0, 0]
        }
      }],
      grid: { left: '15%', right: '5%', top: '10%', bottom: '15%' }
    })
  }

  // 趋势图表
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
    const dates = []
    const values = []
    for (let i = 29; i >= 0; i--) {
      const d = new Date()
      d.setDate(d.getDate() - i)
      dates.push(`${d.getMonth() + 1}/${d.getDate()}`)
      values.push(Math.floor(Math.random() * 50) + 20)
    }
    trendChart.setOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(0, 20, 40, 0.9)',
        borderColor: 'rgba(64, 158, 255, 0.3)',
        textStyle: { color: '#fff' }
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: 'rgba(255, 255, 255, 0.6)', fontSize: 9, rotate: 45 },
        axisLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.3)' } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: 'rgba(255, 255, 255, 0.7)', fontSize: 11 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(64, 158, 255, 0.1)' } }
      },
      series: [{
        data: values,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
          ])
        },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' }
      }],
      grid: { left: '10%', right: '5%', top: '10%', bottom: '20%' }
    })
  }
}

function handleResize() {
  categoryChart?.resize()
  sourceChart?.resize()
  trendChart?.resize()
}

function initMap() {
  if (!window.AMap) {
    mapLoading.value = false
    return
  }

  try {
    mapInstance = new window.AMap.Map(mapRef.value, {
      zoom: 14,
      center: [111.04, 35.017],
      resizeEnable: true,
      mapStyle: 'amap://styles/dark'
    })

    // 添加案件标记点
    casesData.value.forEach(caseItem => {
      if (caseItem.lng && caseItem.lat) {
        const marker = new window.AMap.Marker({
          position: [caseItem.lng, caseItem.lat],
          map: mapInstance
        })
      }
    })

    mapLoading.value = false
  } catch (error) {
    console.error('地图初始化失败:', error)
    mapLoading.value = false
  }
}

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)

  await fetchStats()
  await fetchDashboardData()
  initCharts()

  // 初始化地图
  nextTick(() => {
    initMap()
  })

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  categoryChart?.dispose()
  sourceChart?.dispose()
  trendChart?.dispose()
  if (mapInstance) {
    mapInstance.destroy()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.dashboard-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #0a1628 0%, #0d1f3c 50%, #0a1428 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  z-index: 9999;
  overflow: hidden;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
}

.grid-lines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    linear-gradient(rgba(64, 158, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(64, 158, 255, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}

.glow-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.3;
}

.orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(64, 158, 255, 0.4) 0%, transparent 70%);
  top: -100px;
  left: -100px;
  animation: float 20s ease-in-out infinite;
}

.orb-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(103, 194, 58, 0.3) 0%, transparent 70%);
  bottom: -50px;
  right: -50px;
  animation: float 25s ease-in-out infinite reverse;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(50px, 30px); }
}

/* 顶部标题栏 */
.dashboard-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: linear-gradient(180deg, rgba(0, 20, 50, 0.8) 0%, rgba(0, 20, 50, 0.4) 100%);
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
  position: relative;
  z-index: 10;
}

.dashboard-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.5), transparent);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  font-size: 14px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid rgba(64, 158, 255, 0.2);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.4);
  color: #fff;
}

.header-center {
  display: flex;
  align-items: center;
}

.dashboard-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  letter-spacing: 2px;
}

.title-icon {
  color: #409eff;
}

.time-display {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 15px;
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.9);
  padding: var(--space-2) var(--space-3);
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: var(--radius-md);
}

/* 主内容区 */
.dashboard-main {
  flex: 1;
  display: flex;
  padding: var(--space-4);
  gap: var(--space-4);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* 侧边面板 */
.dashboard-panel {
  width: 340px;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  overflow-y: auto;
  flex-shrink: 0;
}

.dashboard-panel::-webkit-scrollbar {
  width: 4px;
}

.dashboard-panel::-webkit-scrollbar-track {
  background: rgba(64, 158, 255, 0.05);
  border-radius: 2px;
}

.dashboard-panel::-webkit-scrollbar-thumb {
  background: rgba(64, 158, 255, 0.2);
  border-radius: 2px;
}

.panel-section {
  background: linear-gradient(180deg, rgba(13, 31, 60, 0.8) 0%, rgba(10, 22, 40, 0.9) 100%);
  border: 1px solid rgba(64, 158, 255, 0.15);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}

.panel-section::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.5), transparent);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
}

.panel-icon {
  color: #409eff;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  color: #fff;
  letter-spacing: 1px;
}

/* 统计卡片 */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

.stat-card {
  text-align: center;
  padding: var(--space-3);
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(64, 158, 255, 0.1);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.stat-card:hover {
  border-color: rgba(64, 158, 255, 0.3);
  transform: translateY(-2px);
}

.stat-icon {
  width: 40px;
  height: 40px;
  margin: 0 auto var(--space-2);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
}

.stat-icon.total { background: rgba(64, 158, 255, 0.15); color: #409eff; }
.stat-icon.success { background: rgba(103, 194, 58, 0.15); color: #67c23a; }
.stat-icon.warning { background: rgba(230, 162, 60, 0.15); color: #e6a23c; }

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  font-variant-numeric: tabular-nums;
}

.stat-value.success { color: #67c23a; }
.stat-value.warning { color: #e6a23c; }

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: var(--space-1);
}

.chart-wrapper {
  height: 160px;
}

.chart-wrapper.large {
  height: 200px;
}

/* 中间区域 */
.dashboard-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.map-container {
  flex: 1;
  background: linear-gradient(180deg, rgba(13, 31, 60, 0.6) 0%, rgba(10, 22, 40, 0.8) 100%);
  border: 1px solid rgba(64, 158, 255, 0.15);
  border-radius: var(--radius-lg);
  overflow: hidden;
  position: relative;
}

.map-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.5), transparent);
}

.map-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  color: rgba(255, 255, 255, 0.6);
}

.map-loading .loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(64, 158, 255, 0.2);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 滚动数据 */
.scroll-data {
  height: 56px;
  background: linear-gradient(180deg, rgba(13, 31, 60, 0.8) 0%, rgba(10, 22, 40, 0.9) 100%);
  border: 1px solid rgba(64, 158, 255, 0.15);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  overflow: hidden;
  position: relative;
}

.scroll-data::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(64, 158, 255, 0.5), transparent);
  z-index: 3;
}

.scroll-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-4);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  white-space: nowrap;
  border-right: 1px solid rgba(64, 158, 255, 0.2);
  height: 100%;
  background: rgba(10, 22, 40, 1);
  flex-shrink: 0;
}

.scroll-container {
  flex: 1;
  overflow: hidden;
  height: 100%;
}

.scroll-wrapper {
  display: flex;
  gap: var(--space-6);
  padding: 0 var(--space-4);
  height: 100%;
  align-items: center;
  animation: scroll 30s linear infinite;
}

@keyframes scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.scroll-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  white-space: nowrap;
  font-size: 13px;
}

.scroll-time {
  color: rgba(255, 255, 255, 0.5);
  font-variant-numeric: tabular-nums;
}

.scroll-content {
  color: rgba(255, 255, 255, 0.8);
}

.scroll-status {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
}

.scroll-status.completed {
  background: rgba(103, 194, 58, 0.2);
  color: #85ce61;
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.scroll-status.pending {
  background: rgba(230, 162, 60, 0.2);
  color: #ebb563;
  border: 1px solid rgba(230, 162, 60, 0.3);
}

/* 排名列表 */
.rank-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.rank-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2);
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(64, 158, 255, 0.1);
  border-radius: var(--radius-md);
}

.rank-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-sm);
  color: rgba(255, 255, 255, 0.6);
}

.rank-num.top {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
}

.rank-info {
  flex: 1;
  min-width: 0;
}

.rank-name {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  display: block;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rank-bar {
  height: 4px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.rank-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.rank-value {
  font-size: 16px;
  font-weight: 700;
  color: #409eff;
  font-variant-numeric: tabular-nums;
}

/* 实时动态 */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 200px;
  overflow-y: auto;
}

.activity-list::-webkit-scrollbar {
  width: 4px;
}

.activity-list::-webkit-scrollbar-track {
  background: rgba(64, 158, 255, 0.05);
  border-radius: 2px;
}

.activity-list::-webkit-scrollbar-thumb {
  background: rgba(64, 158, 255, 0.2);
  border-radius: 2px;
}

.activity-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2);
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(64, 158, 255, 0.1);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.activity-item:hover {
  border-color: rgba(64, 158, 255, 0.3);
}

.activity-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.activity-icon.add {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}

.activity-icon.check {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.activity-icon.send {
  background: rgba(230, 162, 60, 0.15);
  color: #e6a23c;
}

.activity-icon.refresh {
  background: rgba(144, 147, 153, 0.15);
  color: #909399;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 2px;
}

.activity-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
}
</style>