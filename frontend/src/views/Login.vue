<template>
  <div class="login-page">
    <div class="login-background">
      <div class="login-shape shape-1"></div>
      <div class="login-shape shape-2"></div>
      <div class="login-shape shape-3"></div>
    </div>

    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <div class="login-logo">
            <AppLogo :size="60" />
          </div>
          <h1 class="login-title">{{ config.name }}</h1>
          <p class="login-subtitle">智能数据分析平台</p>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <div class="form-group">
            <div class="input-wrapper">
              <label class="form-label">用户名</label>
              <input
                v-model="form.username"
                type="text"
                class="form-input"
                placeholder="请输入用户名"
                autocomplete="username"
                required
              />
            </div>
          </div>

          <div class="form-group">
            <div class="input-wrapper">
              <label class="form-label">密　码</label>
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="form-input"
                placeholder="请输入密码"
                autocomplete="current-password"
                required
              />
              <button
                type="button"
                class="password-toggle"
                @click="showPassword = !showPassword"
                tabindex="-1"
              >
                <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                  <line x1="1" y1="1" x2="23" y2="23"></line>
                </svg>
              </button>
            </div>
          </div>

          <div v-if="error" class="login-error">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <div class="error-content">
              <span>{{ error }}</span>
              <span v-if="lockCountdown > 0" class="countdown">
                ({{ lockCountdown }}秒后可重试)
              </span>
            </div>
          </div>

          <button type="submit" class="login-btn" :disabled="loading">
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>登 录</span>
          </button>
        </form>

        <div class="login-footer">
          <p>© 2026 智慧平台一站通 v2.0</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useSystemConfig } from '../composables/useSystemConfig'
import AppLogo from '../components/common/AppLogo.vue'
import axios from 'axios'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({
  username: '',
  password: ''
})

const { config } = useSystemConfig()
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)
const lockCountdown = ref(0)
let countdownTimer = null

function parseLockout(errorMsg) {
  const match = errorMsg && errorMsg.match(/请(\d+)秒后/)
  if (match) {
    lockCountdown.value = parseInt(match[1], 10)
    startCountdown()
  }
}

function startCountdown() {
  clearCountdown()
  countdownTimer = setInterval(() => {
    if (lockCountdown.value > 1) {
      lockCountdown.value--
    } else {
      lockCountdown.value = 0
      clearCountdown()
    }
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

onUnmounted(() => {
  clearCountdown()
})

async function handleLogin() {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }

  if (lockCountdown.value > 0) {
    error.value = `账户已锁定，请等待 ${lockCountdown.value} 秒后再试`
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await axios.post('/api/login', {
      username: form.username,
      password: form.password
    })

    const { token, user_id, username, role, permissions } = response.data

    // 构建用户对象
    const user = {
      id: user_id,
      username,
      role,
      permissions: permissions ? Object.keys(permissions).filter(key => permissions[key]) : []
    }

    userStore.login(token, user)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

    router.push('/')
  } catch (err) {
    const msg = err.response?.data?.error || err.response?.data?.message || '登录失败，请检查用户名和密码'
    error.value = msg
    parseLockout(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
}

.login-shape {
  position: absolute;
  border-radius: 50%;
  opacity: 0.1;
}

.shape-1 {
  width: 400px;
  height: 400px;
  background: var(--primary-500);
  top: -100px;
  right: -100px;
  animation: float 20s infinite ease-in-out;
}

.shape-2 {
  width: 300px;
  height: 300px;
  background: var(--success);
  bottom: -50px;
  left: -50px;
  animation: float 15s infinite ease-in-out reverse;
}

.shape-3 {
  width: 200px;
  height: 200px;
  background: var(--warning);
  top: 50%;
  left: 30%;
  animation: float 18s infinite ease-in-out;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  25% { transform: translate(20px, -20px) rotate(5deg); }
  50% { transform: translate(-10px, 20px) rotate(-5deg); }
  75% { transform: translate(-20px, -10px) rotate(3deg); }
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: var(--space-4);
}

.login-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  border-radius: var(--radius-xl);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: var(--space-8);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto var(--space-4);
}

.login-logo svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 12px rgba(64, 158, 255, 0.3));
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin: 0 0 var(--space-2);
}

.login-subtitle {
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.8);
  width: 60px;
  flex-shrink: 0;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.form-input {
  flex: 1;
  padding: var(--space-3);
  font-size: 15px;
  color: white;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.form-input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.form-input:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
}

.form-input:focus {
  outline: none;
  background: rgba(255, 255, 255, 0.15);
  border-color: var(--primary-400);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.2);
}

.password-toggle {
  position: absolute;
  right: var(--space-3);
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.password-toggle:hover {
  color: rgba(255, 255, 255, 0.8);
}

.login-error {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  background: rgba(245, 108, 108, 0.1);
  border: 1px solid var(--danger);
  border-radius: var(--radius-md);
  color: var(--danger);
  font-size: 14px;
}

.error-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.countdown {
  font-weight: 600;
  color: var(--warning);
}

.login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  font-size: 16px;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-top: var(--space-2);
}

.login-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--primary-400) 0%, var(--primary-500) 100%);
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(64, 158, 255, 0.3);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-btn .loading-spinner {
  width: 20px;
  height: 20px;
  border-width: 2px;
  border-color: rgba(255, 255, 255, 0.3);
  border-top-color: white;
}

.login-footer {
  text-align: center;
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.login-footer p {
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  margin: 0;
}
</style>