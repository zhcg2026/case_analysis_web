// 数据分析模块共用的 ECharts 图表模板与格式化工具
// 从 DataAnalysis.vue / ReportView.vue 抽离，避免重复代码
import * as echarts from 'echarts'

export const COLORS = ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4','#ea7ccc','#48b8d0']

export function fmtNum(v) {
  if (v == null) return '-'
  if (typeof v !== 'number') return String(v)
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

// —— 主题配色：图表文字/轴线跟随页面浅色或深色模式 ——
const CHART_PALETTE_DARK = {
  title: '#e0e0e0',
  axis: '#aaa',
  label: '#ccc',
  axisLine: 'rgba(255,255,255,0.15)',
  grid: 'rgba(255,255,255,0.06)',
  pieBorder: 'rgba(10,22,40,0.8)',
  labelLine: 'rgba(255,255,255,0.3)',
  itemBorder: '#fff',
}
const CHART_PALETTE_LIGHT = {
  title: '#1f2d3d',
  axis: '#64748b',
  label: '#475569',
  axisLine: 'rgba(31,45,61,0.18)',
  grid: 'rgba(31,45,61,0.06)',
  pieBorder: 'rgba(255,255,255,0.95)',
  labelLine: 'rgba(31,45,61,0.3)',
  itemBorder: '#fff',
}

let _chartTheme = null
// 由页面在挂载/切换主题时调用，显式告知当前主题
export function setChartTheme(theme) {
  _chartTheme = theme === 'light' ? 'light' : 'dark'
}
// 解析当前主题：优先用 setChartTheme 显式设置，否则回退读 DOM（兼容未调用 setChartTheme 的页面）
function resolveTheme() {
  if (_chartTheme) return _chartTheme
  try {
    const el = document.querySelector('.app-container')
    return el && el.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
  } catch (e) {
    return 'dark'
  }
}
function chartPalette() {
  return resolveTheme() === 'light' ? CHART_PALETTE_LIGHT : CHART_PALETTE_DARK
}

function barTemplate(title, data, xField, yField) {
  const c = chartPalette()
  const xData = data.map(d => d[xField])
  const yData = data.map(d => d[yField])
  return {
    title: { text: title, left: 'center', textStyle: { color: c.title, fontSize: 15 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: p => `${p[0].name}<br/>${p[0].marker} ${yField}: <b>${fmtNum(p[0].value)}</b>` },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '16%', containLabel: true },
    xAxis: { type: 'category', data: xData,
      axisLabel: { color: c.axis, rotate: xData.length > 6 ? 30 : 0 },
      axisLine: { lineStyle: { color: c.axisLine } } },
    yAxis: { type: 'value', name: yField, nameTextStyle: { color: c.axis },
      axisLabel: { color: c.axis, formatter: v => fmtNum(v) },
      splitLine: { lineStyle: { color: c.grid } } },
    series: [{
      type: 'bar', data: yData, barMaxWidth: 50,
      itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#5470c6' }, { offset: 1, color: '#3b4fd0' }
        ])
      },
      label: { show: true, position: 'top', color: c.label, fontSize: 11, formatter: p => fmtNum(p.value) },
      animationDuration: 1000, animationEasing: 'cubicOut'
    }]
  }
}

function horizontalBarTemplate(title, data, xField, yField) {
  const c = chartPalette()
  const sorted = [...data].sort((a, b) => (a[yField] || 0) - (b[yField] || 0))
  const limited = sorted.slice(-15)
  const names = limited.map(d => d[xField])
  const values = limited.map(d => d[yField])
  return {
    title: { text: title, left: 'center', textStyle: { color: c.title, fontSize: 15 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: p => `${p[0].name}<br/>${p[0].marker} ${yField}: <b>${fmtNum(p[0].value)}</b>` },
    grid: { left: '3%', right: '12%', bottom: '3%', top: '16%', containLabel: true },
    xAxis: { type: 'value', name: yField, nameTextStyle: { color: c.axis },
      axisLabel: { color: c.axis, formatter: v => fmtNum(v) },
      splitLine: { lineStyle: { color: c.grid } } },
    yAxis: { type: 'category', data: names,
      axisLabel: { color: c.label, fontSize: 11 },
      axisLine: { lineStyle: { color: c.axisLine } } },
    series: [{
      type: 'bar', data: values, barMaxWidth: 28,
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#3b4fd0' }, { offset: 1, color: '#5470c6' }
        ])
      },
      label: { show: true, position: 'right', color: c.label, fontSize: 11, formatter: p => fmtNum(p.value) },
      animationDuration: 1000, animationEasing: 'cubicOut'
    }]
  }
}

function pieTemplate(title, data, xField, yField) {
  const c = chartPalette()
  const pieData = data.map(d => ({ name: d[xField], value: d[yField] }))
  const total = pieData.reduce((s, d) => s + (d.value || 0), 0)
  return {
    title: { text: title, left: 'center', textStyle: { color: c.title, fontSize: 15 } },
    tooltip: { trigger: 'item',
      formatter: p => `${p.marker} ${p.name}<br/>数量: <b>${fmtNum(p.value)}</b><br/>占比: <b>${p.percent}%</b>` },
    legend: { orient: 'vertical', right: '2%', top: 'middle', textStyle: { color: c.axis, fontSize: 11 },
      formatter: n => { const item = pieData.find(d => d.name === n); return item ? `${n} ${total > 0 ? ((item.value/total)*100).toFixed(1) : 0}%` : n } },
    color: COLORS,
    series: [{
      type: 'pie', radius: ['38%', '68%'], center: ['38%', '55%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: c.pieBorder, borderWidth: 2 },
      label: { show: pieData.length <= 8, color: c.label, fontSize: 11,
        formatter: '{b}\n{d}%' },
      labelLine: { lineStyle: { color: c.labelLine } },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' }
      },
      data: pieData,
      animationDuration: 1000, animationEasing: 'cubicOut'
    }]
  }
}

function lineTemplate(title, data, xField, yField) {
  const c = chartPalette()
  const xData = data.map(d => d[xField])
  const yData = data.map(d => d[yField])
  return {
    title: { text: title, left: 'center', textStyle: { color: c.title, fontSize: 15 } },
    tooltip: { trigger: 'axis',
      formatter: p => `${p[0].name}<br/>${p[0].marker} ${yField}: <b>${fmtNum(p[0].value)}</b>` },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '16%', containLabel: true },
    xAxis: { type: 'category', data: xData, boundaryGap: false,
      axisLabel: { color: c.axis, rotate: xData.length > 8 ? 30 : 0 },
      axisLine: { lineStyle: { color: c.axisLine } } },
    yAxis: { type: 'value', name: yField, nameTextStyle: { color: c.axis },
      axisLabel: { color: c.axis, formatter: v => fmtNum(v) },
      splitLine: { lineStyle: { color: c.grid } } },
    series: [{
      type: 'line', data: yData, smooth: true, symbol: 'circle', symbolSize: 8,
      lineStyle: { width: 3, color: '#5470c6' },
      itemStyle: { color: '#5470c6', borderWidth: 2, borderColor: c.itemBorder },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(84,112,198,0.35)' },
          { offset: 1, color: 'rgba(84,112,198,0.02)' }
        ])
      },
      animationDuration: 1200, animationEasing: 'cubicOut'
    }]
  }
}

export const chartTemplates = { bar: barTemplate, horizontal_bar: horizontalBarTemplate, pie: pieTemplate, line: lineTemplate }

/**
 * 创建或复用某个 DOM 容器上的 ECharts 实例，避免重复 init 报错与内存泄漏。
 * 内部用 Map 缓存实例与 ResizeObserver，组件卸载时调用 disposeEcharts 清理。
 */
const _chartInstances = new Map()
const _resizeObservers = new Map()

export function getOrInitChart(container, theme = 'dark') {
  if (!container) return null
  let chart = echarts.getInstanceByDom(container)
  if (chart) {
    chart.dispose()
  }
  chart = echarts.init(container, theme)
  const ro = new ResizeObserver(() => chart && chart.resize())
  // 清理旧的 observer
  if (_resizeObservers.has(container)) {
    _resizeObservers.get(container).disconnect()
  }
  ro.observe(container)
  _chartInstances.set(container, chart)
  _resizeObservers.set(container, ro)
  return chart
}

export function disposeEcharts(container) {
  if (_resizeObservers.has(container)) {
    _resizeObservers.get(container).disconnect()
    _resizeObservers.delete(container)
  }
  const chart = _chartInstances.get(container)
  if (chart) {
    chart.dispose()
    _chartInstances.delete(container)
  }
}
