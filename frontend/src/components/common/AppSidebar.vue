<template>
  <aside class="app-sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-content">
      <!-- 顶部标题 -->
      <div class="sidebar-header">
        <div class="header-logo">
          <AppLogo :size="40" />
        </div>
        <span class="header-text" v-show="!isCollapsed">{{ config.name }}</span>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in navItems" :key="item.path || item.key">
          <!-- 可展开分组（台账管理） -->
          <div v-if="item.children" class="sidebar-group" :class="{ open: isGroupOpen(item) }">
            <button
              type="button"
              class="sidebar-item group-item"
              :class="{ active: isActive(item.path) }"
              @click="toggleGroup(item)"
            >
              <span class="item-icon" v-html="item.icon"></span>
              <span class="item-text" v-show="!isCollapsed">{{ item.title }}</span>
              <span class="group-arrow" v-show="!isCollapsed">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
              </span>
            </button>
            <div v-show="!isCollapsed && isGroupOpen(item)" class="sidebar-sub">
              <router-link
                v-for="child in item.children"
                :key="child.path"
                :to="child.path"
                class="sidebar-item sub-item"
                :class="{ active: isActive(child.path) }"
              >
                <span class="item-text">{{ child.title }}</span>
              </router-link>
            </div>
          </div>

          <!-- 普通一级菜单 -->
          <router-link
            v-else
            :to="item.path"
            class="sidebar-item"
            :class="{ active: isActive(item.path) }"
          >
            <span class="item-icon" v-html="item.icon"></span>
            <span class="item-text" v-show="!isCollapsed">{{ item.title }}</span>
            <span class="item-badge" v-if="item.badge && !isCollapsed">{{ item.badge }}</span>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-footer" v-show="!isCollapsed">
        <div class="version">v2.0.1</div>
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
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { useSystemConfig } from '../../composables/useSystemConfig'
import { MENU_PERMISSION_TREE } from '../../constants/menuPermissions'
import AppLogo from './AppLogo.vue'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:collapsed'])
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { config } = useSystemConfig()

const isCollapsed = ref(props.collapsed)

// SVG图标定义
const icons = {
  home: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  ai: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>`,
  knowledge: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M8 7h6"/><path d="M8 11h8"/><path d="M8 15h4"/></svg>`,
  map: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>`,
  caseMap: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M12 12h.01"/><path d="M12 8v0"/><path d="M8 12v0"/><path d="M16 12v0"/><path d="M12 16v0"/></svg>`,
  dispatch: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
  business: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>`,
  admin: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  cleaning: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
  ledger: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1z"/><path d="M8 10h8"/><path d="M8 14h4"/></svg>`,
  dutyRecord: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 12h6"/><path d="M9 16h4"/></svg>`,
  assessment: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>`
}

const iconByKey = {
  map: icons.map,
  knowledge: icons.knowledge,
  dispatch: icons.dispatch,
  data_mgmt: icons.cleaning,
  assessment: icons.assessment,
  data_analysis: icons.ai,
  case_map: icons.caseMap,
  ledger: icons.ledger,
  duty: icons.dutyRecord,
  business: icons.business
}

const navItems = computed(() => {
  const home = { path: '/', title: '首页', icon: icons.home }

  const items = [home]
  for (const node of MENU_PERMISSION_TREE) {
    if (node.children) {
      const children = node.children
        .filter((c) => userStore.hasPermission(c.key))
        .map((c) => ({ path: c.path || pathForPermissionKey(c.key), title: c.title || c.label, permission: c.key }))
      if (!children.length) continue
      // 父级无独立可见子项时不显示；父级权限关但子级有权限时仍显示分组
      items.push({
        key: node.key,
        path: groupBasePath(node.key),
        title: node.title || node.label,
        icon: iconByKey[node.key] || icons.home,
        permission: node.key,
        children
      })
    } else {
      if (!userStore.hasPermission(node.key)) continue
      items.push({
        path: node.path || pathForPermissionKey(node.key),
        title: node.title || node.label,
        icon: iconByKey[node.key] || icons.home,
        permission: node.key
      })
    }
  }

  items.push({ path: '/admin', title: '系统管理', icon: icons.admin, requiresAdmin: true })
  return items
})

function pathForPermissionKey(key) {
  const map = {
    map: '/map',
    knowledge: '/knowledge',
    data_analysis: '/data-analysis',
    case_map: '/case-map',
    business: '/business',
    data_cleaning: '/data/cleaning',
    data_browse: '/data/browse',
    data_stats: '/data/stats',
    assessment_input_platform: '/assessment/input/platform',
    assessment_input_collector: '/assessment/input/collector',
    assessment_exemption: '/assessment/exemption',
    assessment_score: '/assessment/score',
    dispatch_standards: '/dispatch/standards',
    dispatch_query: '/dispatch/query',
    dispatch_special: '/dispatch/special',
    ledger_maintenance: '/ledger/maintenance',
    ledger_meeting: '/ledger/meeting',
    ledger_training: '/ledger/training',
    ledger_docs: '/ledger/docs',
    ledger_monitor: '/ledger/monitor',
    ledger_drone: '/ledger/drone',
    duty_schedule: '/duty/schedule',
    duty_records: '/duty/records'
  }
  return map[key] || '/'
}

function groupBasePath(key) {
  const map = {
    dispatch: '/dispatch',
    data_mgmt: '/data',
    assessment: '/assessment',
    ledger: '/ledger',
    duty: '/duty'
  }
  return map[key] || '/'
}

// 手动展开状态；访问台账路由时自动展开
const openGroups = ref(new Set())

function isGroupOpen(item) {
  if (isActive(item.path)) return true
  return openGroups.value.has(item.key)
}

function toggleGroup(item) {
  // 收起态下点击分组：跳到默认子菜单
  if (isCollapsed.value) {
    const first = item.children?.[0]
    if (first) router.push(first.path)
    return
  }
  const next = new Set(openGroups.value)
  if (next.has(item.key)) next.delete(item.key)
  else next.add(item.key)
  openGroups.value = next
}

function isActive(path) {
  if (!path) return false
  if (path === '/' ) return route.path === '/'
  if (
    path === '/ledger' || path === '/duty' || path === '/dispatch' ||
    path === '/assessment' || path === '/data'
  ) {
    return route.path === path || route.path.startsWith(path + '/')
  }
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

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.header-logo {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.header-logo svg {
  width: 100%;
  height: 100%;
}

.header-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
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

.sidebar-group {
  display: flex;
  flex-direction: column;
}

.group-item {
  width: 100%;
  border: none;
  background: transparent;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.group-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.sidebar-group.open .group-arrow {
  transform: rotate(90deg);
}

.sidebar-sub {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 2px 0 4px 0;
  padding-left: 12px;
  border-left: 1px solid var(--border-lighter);
  margin-left: 18px;
}

.sub-item {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 400;
}

.sub-item.active {
  background: var(--primary-50);
  color: var(--primary-500);
}

[data-theme="dark"] .sub-item.active {
  background: rgba(64, 158, 255, 0.1);
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

.app-sidebar.collapsed .sidebar-sub {
  display: none !important;
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
