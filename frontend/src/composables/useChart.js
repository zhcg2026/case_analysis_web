import { onMounted, onUnmounted, ref } from 'vue'
import { useThemeStore } from '../stores/theme'
import * as echarts from 'echarts'

/**
 * 图表组合式函数
 * 自动处理图表初始化、主题切换和销毁
 */
export function useChart(chartRef) {
  const themeStore = useThemeStore()
  let chartInstance = null

  // 初始化图表
  function initChart() {
    if (!chartRef.value) return null

    // 销毁已有实例
    if (chartInstance) {
      chartInstance.dispose()
    }

    // 创建新实例
    chartInstance = echarts.init(chartRef.value, themeStore.isDark() ? 'dark' : null)
    return chartInstance
  }

  // 更新图表配置
  function setOption(option, notMerge = false) {
    if (!chartInstance) {
      initChart()
    }
    if (chartInstance) {
      chartInstance.setOption(option, notMerge)
    }
  }

  // 调整图表大小
  function resize() {
    if (chartInstance) {
      chartInstance.resize()
    }
  }

  // 销毁图表
  function dispose() {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }

  // 监听窗口大小变化
  function handleResize() {
    resize()
  }

  // 主题切换时重新渲染
  function handleThemeChange() {
    if (chartRef.value && chartInstance) {
      const option = chartInstance.getOption()
      dispose()
      initChart()
      if (option) {
        chartInstance.setOption(option)
      }
    }
  }

  onMounted(() => {
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    dispose()
  })

  return {
    chartInstance: ref(chartInstance),
    initChart,
    setOption,
    resize,
    dispose
  }
}

/**
 * ECharts 暗色主题配置
 */
export const darkTheme = {
  backgroundColor: 'transparent',
  textStyle: {
    color: 'rgba(255, 255, 255, 0.8)'
  },
  title: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.9)'
    }
  },
  legend: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.7)'
    }
  },
  xAxis: {
    axisLine: {
      lineStyle: {
        color: 'rgba(100, 149, 237, 0.5)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.7)'
    }
  },
  yAxis: {
    axisLine: {
      lineStyle: {
        color: 'rgba(100, 149, 237, 0.5)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.7)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(100, 149, 237, 0.2)'
      }
    }
  }
}

// 注册暗色主题
echarts.registerTheme('dark', darkTheme)