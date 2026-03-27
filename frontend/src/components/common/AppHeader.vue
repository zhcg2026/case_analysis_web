<template>
  <header class="app-header">
    <div class="header-left">
      <button class="sidebar-toggle" @click="$emit('toggleSidebar')" aria-label="切换侧边栏">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
      <div class="logo">
        <span class="logo-icon">📊</span>
        <span class="logo-text">案件分析系统</span>
      </div>
    </div>

    <div class="header-right">
      <ThemeSwitch />
      <div class="user-menu" @click="showUserDropdown = !showUserDropdown" ref="userMenuRef">
        <span class="user-avatar">{{ userInitial }}</span>
        <span class="user-name">{{ username }}</span>
        <svg class="dropdown-arrow" :class="{ open: showUserDropdown }" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>

        <Transition name="fade">
          <div v-if="showUserDropdown" class="user-dropdown">
            <div class="dropdown-item" @click="goToProfile">
              <span>👤</span> 个人信息
            </div>
            <div class="dropdown-divider"></div>
            <div class="dropdown-item danger" @click="handleLogout">
              <span>🚪</span> 退出登录
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import ThemeSwitch from './ThemeSwitch.vue'

const emit = defineEmits(['toggleSidebar'])
const router = useRouter()
const userStore = useUserStore()

const showUserDropdown = ref(false)
const userMenuRef = ref(null)

const username = computed(() => userStore.username || '用户')
const userInitial = computed(() => username.value.charAt(0).toUpperCase())

function goToProfile() {
  showUserDropdown.value = false
}

function handleLogout() {
  showUserDropdown.value = false
  userStore.logout()
  router.push('/login')
}

function handleClickOutside(event) {
  if (userMenuRef.value && !userMenuRef.value.contains(event.target)) {
    showUserDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.app-header {
  height: var(--header-height);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-4);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  box-shadow: var(--shadow-sm);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sidebar-toggle:hover {
  background: var(--fill-light);
  color: var(--text-primary);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.user-menu:hover {
  background: var(--fill-light);
}

.user-avatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-500);
  color: white;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 600;
}

.user-name {
  color: var(--text-primary);
  font-weight: 500;
}

.dropdown-arrow {
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: var(--space-2);
  min-width: 160px;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: var(--z-dropdown);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--fill-light);
}

.dropdown-item.danger {
  color: var(--danger);
}

.dropdown-divider {
  height: 1px;
  background: var(--border-lighter);
  margin: var(--space-1) 0;
}

@media (max-width: 640px) {
  .logo-text {
    display: none;
  }

  .user-name {
    display: none;
  }
}
</style>