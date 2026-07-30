// 系统配置（系统名称 / Logo）共享状态
// 全站品牌展示统一从这里取，后端以 system_config 表持久化。
import { reactive } from 'vue'
import axios from 'axios'

export const DEFAULT_SYSTEM_NAME = '智慧平台一站通'

// 模块级单例：所有组件共享同一份响应式状态
const state = reactive({
  name: DEFAULT_SYSTEM_NAME,
  logo: '' // 自定义 Logo 的图片 URL；为空则使用内置 SVG
})

let loaded = false

export function useSystemConfig() {
  async function loadSystemConfig() {
    try {
      const { data } = await axios.get('/api/system/config')
      if (data && data.system_name) state.name = data.system_name
      if (data && typeof data.system_logo === 'string') state.logo = data.system_logo
    } catch (e) {
      console.error('加载系统配置失败，使用默认值:', e)
    } finally {
      loaded = true
    }
  }

  async function saveSystemConfig(cfg) {
    const payload = {
      system_name: (cfg && cfg.name != null ? cfg.name : state.name) || DEFAULT_SYSTEM_NAME,
      system_logo: (cfg && cfg.logo != null ? cfg.logo : state.logo) || ''
    }
    const { data } = await axios.post('/api/system/config', payload)
    if (data && data.system_name) state.name = data.system_name
    if (data && typeof data.system_logo === 'string') state.logo = data.system_logo
    return data
  }

  return {
    config: state,
    isLoaded: () => loaded,
    loadSystemConfig,
    saveSystemConfig
  }
}
