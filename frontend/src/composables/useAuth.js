import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import axios from 'axios'

/**
 * 认证组合式函数
 */
export function useAuth() {
  const router = useRouter()
  const userStore = useUserStore()

  const loading = ref(false)
  const error = ref('')

  // 登录
  async function login(username, password) {
    loading.value = true
    error.value = ''

    try {
      const response = await axios.post('/api/login', { username, password })
      const { token, user_id, username: name, role, permissions } = response.data

      // 构建用户对象
      const user = {
        id: user_id,
        username: name,
        role,
        permissions: permissions ? Object.keys(permissions).filter(key => permissions[key]) : []
      }

      userStore.login(token, user)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`

      router.push('/')
      return true
    } catch (err) {
      error.value = err.response?.data?.error || err.response?.data?.message || '登录失败，请检查用户名和密码'
      return false
    } finally {
      loading.value = false
    }
  }

  // 登出
  function logout() {
    userStore.logout()
    delete axios.defaults.headers.common['Authorization']
    router.push('/login')
  }

  // 检查 token 有效性
  async function checkToken() {
    const token = userStore.token
    if (!token) return false

    try {
      const response = await axios.get('/api/verify-token', {
        headers: { Authorization: `Bearer ${token}` }
      })
      return response.data.valid
    } catch {
      userStore.logout()
      return false
    }
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const response = await axios.get('/api/user-info', {
        headers: { Authorization: `Bearer ${userStore.token}` }
      })
      userStore.updateUserInfo(response.data)
      return response.data
    } catch {
      return null
    }
  }

  return {
    loading,
    error,
    login,
    logout,
    checkToken,
    fetchUserInfo,
    isLoggedIn: computed(() => userStore.isLoggedIn),
    isAdmin: computed(() => userStore.isAdmin),
    user: computed(() => userStore.userInfo)
  }
}

/**
 * API 请求拦截器设置
 */
export function setupApiInterceptors() {
  const userStore = useUserStore()

  // 请求拦截器
  axios.interceptors.request.use(
    (config) => {
      const token = userStore.token
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  // 响应拦截器
  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        userStore.logout()
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
  )
}