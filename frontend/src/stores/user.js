import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  const isLoggedIn = computed(() => !!token.value && !!userInfo.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')
  const username = computed(() => userInfo.value?.username || '')

  /** 权限 map：{ key: boolean }；兼容旧数组格式 */
  const permissions = computed(() => {
    const p = userInfo.value?.permissions
    if (!p) return {}
    if (Array.isArray(p)) {
      const map = {}
      for (const k of p) map[k] = true
      if (p.includes('all')) map.all = true
      return map
    }
    return p
  })

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
    if (!permission) return true
    if (isAdmin.value) return true
    const perms = permissions.value
    if (perms.all) return true
    return Boolean(perms[permission])
  }

  function updateUserInfo(user) {
    userInfo.value = { ...userInfo.value, ...user }
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isAdmin,
    username,
    permissions,
    login,
    logout,
    hasPermission,
    updateUserInfo
  }
})
