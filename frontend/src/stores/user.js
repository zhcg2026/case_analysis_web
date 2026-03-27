import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // State
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  // Getters
  const isLoggedIn = computed(() => !!token.value && !!userInfo.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')
  const username = computed(() => userInfo.value?.username || '')

  // 用户权限列表
  const permissions = computed(() => {
    if (isAdmin.value) return ['all']
    return userInfo.value?.permissions || []
  })

  // Actions
  function login(tokenValue, user) {
    token.value = tokenValue
    userInfo.value = user
    localStorage.setItem('token', tokenValue)
    localStorage.setItem('userInfo', JSON.stringify(user))
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  function hasPermission(permission) {
    if (isAdmin.value) return true
    return permissions.value.includes(permission)
  }

  function updateUserInfo(user) {
    userInfo.value = { ...userInfo.value, ...user }
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
  }

  return {
    // State
    token,
    userInfo,
    // Getters
    isLoggedIn,
    isAdmin,
    username,
    permissions,
    // Actions
    login,
    logout,
    hasPermission,
    updateUserInfo
  }
})