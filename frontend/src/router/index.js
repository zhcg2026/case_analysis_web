import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useSystemConfig } from '../composables/useSystemConfig'

// 路由懒加载
const Home = () => import('../views/Home.vue')
const Business = () => import('../views/Business.vue')
const DataAnalysis = () => import('../views/DataAnalysis.vue')
const Map = () => import('../views/Map.vue')
const Admin = () => import('../views/Admin.vue')
const Login = () => import('../views/Login.vue')
const Knowledge = () => import('../views/Knowledge.vue')
const ArticleDetail = () => import('../views/ArticleDetail.vue')
const CategoryArticles = () => import('../views/CategoryArticles.vue')
const ReportView = () => import('../views/ReportView.vue')

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false, title: '登录' }
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true, title: '首页' }
  },
  {
    path: '/data-analysis',
    name: 'DataAnalysis',
    component: DataAnalysis,
    meta: { requiresAuth: true, title: '数据分析', permission: 'data_analysis' }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: Knowledge,
    meta: { requiresAuth: true, title: '知识库' }
  },
  {
    path: '/map',
    name: 'Map',
    component: Map,
    meta: { requiresAuth: true, title: '数图城管', permission: 'map' }
  },
  {
    path: '/business',
    name: 'Business',
    component: Business,
    meta: { requiresAuth: true, title: '业务平台', permission: 'business' }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: Admin,
    meta: { requiresAuth: true, title: '系统管理', requiresAdmin: true }
  },
  {
    path: '/report/:id',
    name: 'ReportView',
    component: ReportView,
    meta: { requiresAuth: true, title: '分析报告' }
  },
  {
    path: '/article/:id',
    name: 'ArticleDetail',
    component: ArticleDetail,
    meta: { requiresAuth: true, title: '文章详情' }
  },
  {
    path: '/category/:id',
    name: 'CategoryArticles',
    component: CategoryArticles,
    meta: { requiresAuth: true, title: '栏目文章' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  // 设置页面标题（品牌名取自系统配置，默认“智慧平台一站通”）
  const brandName = useSystemConfig().config.name || '智慧平台一站通'
  document.title = to.meta.title ? `${to.meta.title} - ${brandName}` : brandName

  // 检查是否需要登录
  if (to.meta.requiresAuth !== false && !userStore.isLoggedIn) {
    next({ name: 'Login' })
    return
  }

  // 检查是否需要管理员权限
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ name: 'Home' })
    return
  }

  // 检查特定权限
  if (to.meta.permission && !userStore.hasPermission(to.meta.permission)) {
    next({ name: 'Home' })
    return
  }

  next()
})

export default router
