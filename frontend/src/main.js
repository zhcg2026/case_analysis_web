import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

// 设计系统样式
import './styles/common.css'
import './styles/themes.css'

const app = createApp(App)

// 使用 Pinia
const pinia = createPinia()
app.use(pinia)

// 使用 Vue Router
app.use(router)

// 使用 Element Plus
app.use(ElementPlus, {
  locale: zhCn
})

app.mount('#app')