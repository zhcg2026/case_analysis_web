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
            <div class="dropdown-item" @click="openChangePassword">
              <KbIcon name="lock" :size="16" /> 修改密码
            </div>
            <div class="dropdown-item danger" @click="handleLogout">
              <KbIcon name="log-out" :size="16" /> 退出登录
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- 修改密码弹窗 -->
    <div v-if="pwdVisible" class="pwd-overlay" @click.self="closePwdDialog">
      <div class="pwd-modal" role="dialog" aria-modal="true" aria-label="修改密码">
        <div class="pwd-header">
          <h3>修改密码</h3>
          <button class="pwd-close" type="button" @click="closePwdDialog">&times;</button>
        </div>
        <form class="pwd-body" @submit.prevent="submitChangePassword">
          <label class="pwd-field">
            <span>当前密码</span>
            <input
              v-model="pwdForm.current"
              type="password"
              class="pwd-input"
              autocomplete="current-password"
              placeholder="请输入当前密码"
            />
          </label>
          <label class="pwd-field">
            <span>新密码</span>
            <input
              v-model="pwdForm.next"
              type="password"
              class="pwd-input"
              autocomplete="new-password"
              placeholder="至少8位，含字母和数字"
            />
          </label>
          <label class="pwd-field">
            <span>确认新密码</span>
            <input
              v-model="pwdForm.confirm"
              type="password"
              class="pwd-input"
              autocomplete="new-password"
              placeholder="请再次输入新密码"
            />
          </label>
          <div class="pwd-footer">
            <button type="button" class="pwd-btn secondary" @click="closePwdDialog">取消</button>
            <button type="submit" class="pwd-btn primary" :disabled="pwdSaving">
              {{ pwdSaving ? '提交中…' : '确认修改' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../../stores/user'
import ThemeSwitch from './ThemeSwitch.vue'
import KbIcon from './KbIcon.vue'
import axios from 'axios'

const emit = defineEmits(['toggleSidebar'])
const router = useRouter()
const userStore = useUserStore()

const showUserDropdown = ref(false)
const userMenuRef = ref(null)

const pwdVisible = ref(false)
const pwdSaving = ref(false)
const pwdForm = reactive({ current: '', next: '', confirm: '' })

const username = computed(() => userStore.username || '用户')
const userInitial = computed(() => username.value.charAt(0).toUpperCase())

function handleLogout() {
  showUserDropdown.value = false
  userStore.logout()
  router.push('/login')
}

function openChangePassword() {
  showUserDropdown.value = false
  pwdForm.current = ''
  pwdForm.next = ''
  pwdForm.confirm = ''
  pwdVisible.value = true
}

function closePwdDialog() {
  if (pwdSaving.value) return
  pwdVisible.value = false
}

async function submitChangePassword() {
  if (!pwdForm.current || !pwdForm.next || !pwdForm.confirm) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (pwdForm.next !== pwdForm.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  pwdSaving.value = true
  try {
    await axios.post('/api/change-password', {
      current_password: pwdForm.current,
      new_password: pwdForm.next,
      confirm_password: pwdForm.confirm,
    }, { silentErrorHandler: true })
    ElMessage.success('密码修改成功')
    pwdSaving.value = false
    pwdVisible.value = false
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '密码修改失败，请稍后重试。')
  } finally {
    pwdSaving.value = false
  }
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

.pwd-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal, 1000);
  padding: 16px;
}

.pwd-modal {
  width: 100%;
  max-width: 400px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-lighter);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.pwd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-lighter);
}

.pwd-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.pwd-close {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0 4px;
}

.pwd-close:hover {
  color: var(--text-primary);
}

.pwd-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.pwd-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pwd-field span {
  font-size: 13px;
  color: var(--text-secondary);
}

.pwd-input {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--border-lighter);
  border-radius: 8px;
  background: var(--bg-primary, #fff);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

.pwd-input:focus {
  border-color: var(--primary-500);
}

.pwd-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.pwd-btn {
  height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 13px;
}

.pwd-btn.secondary {
  background: transparent;
  border-color: var(--border-lighter);
  color: var(--text-primary);
}

.pwd-btn.primary {
  background: var(--primary-500);
  color: #fff;
}

.pwd-btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
