import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

// 路由懒加载
const Home = () => import('../views/Home.vue')
const Business = () => import('../views/Business.vue')
const AiApps = () => import('../views/AiApps.vue')
const Huiwentai = () => import('../views/Huiwentai.vue')
const Assessment = () => import('../views/Assessment.vue')
const Cases = () => import('../views/Cases.vue')
const Map = () => import('../views/Map.vue')
const Dashboard = () => import('../views/Dashboard.vue')
const Admin = () => import('../views/Admin.vue')
const Login = () => import('../views/Login.vue')
const Knowledge = () => import('../views/Knowledge.vue')
const ArticleDetail = () => import('../views/ArticleDetail.vue')
const CategoryArticles = () => import('../views/CategoryArticles.vue')

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
    path: '/business',
    name: 'Business',
    component: Business,
    meta: { requiresAuth: true, title: '业务平台', permission: 'business' }
  },
  {
    path: '/ai-apps',
    name: 'AiApps',
    component: AiApps,
    meta: { requiresAuth: true, title: 'AI应用' }
  },
  {
    path: '/huiwentai',
    name: 'Huiwentai',
    component: Huiwentai,
    meta: { requiresAuth: true, title: '汇问台', permission: 'huiwentai' }
  },
  {
    path: '/assessment',
    name: 'Assessment',
    component: Assessment,
    meta: { requiresAuth: true, title: '考核计分', permission: 'assessment' }
  },
  {
    path: '/cases',
    name: 'Cases',
    component: Cases,
    meta: { requiresAuth: true, title: '案件管理', permission: 'cases' }
  },
  {
    path: '/map',
    name: 'Map',
    component: Map,
    meta: { requiresAuth: true, title: '地图服务', permission: 'map' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true, title: '数据大屏' }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: Admin,
    meta: { requiresAuth: true, title: '系统管理', requiresAdmin: true }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: Knowledge,
    meta: { requiresAuth: true, title: '知识库' }
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

  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - 智慧平台一站通` : '智慧平台一站通'

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