<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-content">
      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-item"
          :class="{ active: isActive(item.path) }"
        >
          <span class="item-icon" v-html="item.icon"></span>
          <span class="item-text" v-show="!isCollapsed">{{ item.title }}</span>
          <span class="item-badge" v-if="item.badge && !isCollapsed">{{ item.badge }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer" v-show="!isCollapsed">
        <div class="version">v2.0.0</div>
      </div>
    </div>

    <button class="collapse-btn" @click="toggleCollapse" :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline :points="isCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"></polyline>
      </svg>
    </button>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '../../stores/user'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:collapsed'])
const route = useRoute()
const userStore = useUserStore()

const isCollapsed = ref(props.collapsed)

// SVG图标定义
const icons = {
  home: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  dashboard: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
  business: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>`,
  ai: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>`,
  huiwentai: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4H4a2 2 0 1 0 0 4h12a2 2 0 1 0 0-4Z"/><path d="M6 8v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>`,
  assessment: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>`,
  cases: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>`,
  cms: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>`,
  map: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>`,
  tools: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
  admin: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`
}

const navItems = computed(() => {
  const items = [
    { path: '/', title: '首页', icon: icons.home },
    { path: '/dashboard', title: '数据大屏', icon: icons.dashboard },
    { path: '/ai-apps', title: 'AI应用', icon: icons.ai },
    { path: '/huiwentai', title: '汇问台', icon: icons.huiwentai, permission: 'huiwentai' },
    { path: '/assessment', title: '考核计分', icon: icons.assessment, permission: 'assessment' },
    { path: '/cases', title: '案件管理', icon: icons.cases, permission: 'cases' },
    { path: '/map', title: '地图服务', icon: icons.map, permission: 'map' },
    { path: '/business', title: '业务平台', icon: icons.business },
    { path: '/admin', title: '系统管理', icon: icons.admin, requiresAdmin: true }
  ]

  return items.filter(item => {
    if (item.requiresAdmin && !userStore.isAdmin) return false
    if (item.permission && !userStore.hasPermission(item.permission)) return false
    return true
  })
})

function isActive(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
  emit('update:collapsed', isCollapsed.value)
}
</script>

<style scoped>
.app-sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--bg-card);
  border-right: 1px solid var(--border-lighter);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  z-index: var(--z-fixed);
  transition: width var(--transition-normal);
}

.app-sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: var(--space-4);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-fast);
  position: relative;
}

.sidebar-item:hover {
  background: var(--fill-light);
  color: var(--text-primary);
}

.sidebar-item.active {
  background: var(--primary-50);
  color: var(--primary-500);
}

[data-theme="dark"] .sidebar-item.active {
  background: rgba(64, 158, 255, 0.1);
}

.item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.item-icon :deep(svg) {
  width: 20px;
  height: 20px;
}

.item-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-badge {
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  background: var(--danger);
  border-radius: var(--radius-full);
}

.sidebar-footer {
  margin-top: auto;
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.version {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 12px;
}

.collapse-btn {
  position: absolute;
  right: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: 50%;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
  z-index: 1;
}

.collapse-btn:hover {
  background: var(--primary-50);
  color: var(--primary-500);
  border-color: var(--primary-200);
}

[data-theme="dark"] .collapse-btn:hover {
  background: rgba(64, 158, 255, 0.1);
}

/* 收起状态 */
.app-sidebar.collapsed .sidebar-item {
  justify-content: center;
  padding: var(--space-3);
}

.app-sidebar.collapsed .sidebar-content {
  padding: var(--space-2);
}

/* 响应式 */
@media (max-width: 768px) {
  .app-sidebar {
    transform: translateX(-100%);
  }

  .app-sidebar:not(.collapsed) {
    transform: translateX(0);
  }
}
</style>