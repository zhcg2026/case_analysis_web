<template>
  <div class="app-container" :data-theme="themeStore.theme">
    <!-- 初始化中 -->
    <div v-if="initializing" class="app-loading">
      <div class="loading-spinner"></div>
    </div>

    <!-- 登录页面 -->
    <template v-else-if="!userStore.isLoggedIn">
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
const initializing = ref(true)

const { loadSystemConfig } = useSystemConfig()

onMounted(async () => {
  setupApiInterceptors()
  await loadSystemConfig()

  // 如果 localStorage 有 token 但没有 userInfo，清理无效状态
  if (userStore.token && !userStore.userInfo) {
    userStore.logout()
  }

  // 如果有 token，验证是否有效
  if (userStore.isLoggedIn) {
    try {
      await axios.get('/api/verify-token', {
        headers: { Authorization: `Bearer ${userStore.token}` }
      })
    } catch {
      userStore.logout()
    }
  }

  initializing.value = false

  if (!userStore.isLoggedIn) {
    router.push('/login')
  }
})
</script>

<style>
.app-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--bg-primary, #f5f7fa);
}

.loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border-lighter, #e4e7ed);
  border-top-color: var(--primary-500, #409eff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>