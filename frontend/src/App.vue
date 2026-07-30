<template>
  <div class="app-container" :data-theme="themeStore.theme">
    <!-- 登录页面 -->
    <template v-if="!userStore.isLoggedIn">
      <router-view />
    </template>

    <!-- 主应用布局 -->
    <template v-else>
      <div class="app-layout">
        <!-- 侧边栏 -->
        <AppSidebar v-model:collapsed="sidebarCollapsed" />

        <!-- 主内容区 -->
        <main class="app-main" :style="{ marginLeft: sidebarCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)' }">
          <!-- 顶部导航 -->
          <AppHeader @toggleSidebar="sidebarCollapsed = !sidebarCollapsed" />

          <!-- 内容区域 -->
          <div class="app-content">
            <router-view v-slot="{ Component }">
              <Transition name="fade" mode="out-in">
                <component :is="Component" />
              </Transition>
            </router-view>
          </div>
        </main>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from './stores/user'
import { useThemeStore } from './stores/theme'
import { setupApiInterceptors } from './composables/useAuth'
import { useSystemConfig } from './composables/useSystemConfig'
import AppHeader from './components/common/AppHeader.vue'
import AppSidebar from './components/common/AppSidebar.vue'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const sidebarCollapsed = ref(false)

const { loadSystemConfig } = useSystemConfig()

onMounted(() => {
  // 设置 API 拦截器
  setupApiInterceptors()

  // 加载系统配置（名称 / Logo），驱动全站品牌展示
  loadSystemConfig()

  // 如果未登录，跳转到登录页
  if (!userStore.isLoggedIn) {
    router.push('/login')
  }
})
</script>

<style>
/* App.vue 不需要额外样式，所有样式在 styles/ 目录下 */
</style>