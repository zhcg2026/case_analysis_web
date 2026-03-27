import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // 从 localStorage 读取主题，默认跟随系统
  const getSystemTheme = () => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'light'
  }

  const storedTheme = localStorage.getItem('theme')
  const theme = ref(storedTheme || getSystemTheme())

  // 应用主题到 DOM
  function applyTheme(newTheme) {
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
  }

  // 初始化主题
  applyTheme(theme.value)

  // 监听主题变化
  watch(theme, (newTheme) => {
    applyTheme(newTheme)
  })

  // 切换主题
  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  // 设置特定主题
  function setTheme(newTheme) {
    theme.value = newTheme
  }

  // 是否暗色主题
  const isDark = () => theme.value === 'dark'

  return {
    theme,
    toggleTheme,
    setTheme,
    isDark
  }
})