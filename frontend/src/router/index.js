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

const CaseMap = () => import('../views/CaseMap.vue')
const Dispatch = () => import('../views/Dispatch.vue')
const ReportEmbed = () => import('../views/ReportEmbed.vue')
const DataCleaning = () => import('../views/DataCleaning.vue')
const DataEditBrowse = () => import('../views/DataEditBrowse.vue')
const DataStats = () => import('../views/DataStats.vue')
const Ledger = () => import('../views/Ledger.vue')
const DutySchedule = () => import('../views/DutySchedule.vue')
const Assessment = () => import('../views/Assessment.vue')
const DutyRecord = () => import('../views/DutyRecord.vue')
const CaseStandards = () => import('../views/CaseStandards.vue')
const SpecialMatters = () => import('../views/SpecialMatters.vue')
const AssessmentInputPlatform = () => import('../views/AssessmentInputPlatform.vue')
const AssessmentInputCollector = () => import('../views/AssessmentInputCollector.vue')
const ExemptionSettings = () => import('../views/ExemptionSettings.vue')


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
    path: '/data',
    redirect: '/data/cleaning'
  },
  {
    path: '/data/cleaning',
    name: 'DataCleaning',
    component: DataCleaning,
    meta: { requiresAuth: true, title: '数据清洗入库', permission: 'data_cleaning' }
  },
  {
    path: '/data/browse',
    name: 'DataEditBrowse',
    component: DataEditBrowse,
    meta: { requiresAuth: true, title: '数据编辑浏览', permission: 'data_browse' }
  },
  {
    path: '/data/stats',
    name: 'DataStats',
    component: DataStats,
    meta: { requiresAuth: true, title: '统计查询', permission: 'data_stats' }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: Knowledge,
    meta: { requiresAuth: true, title: '知识库', permission: 'knowledge' }
  },
  {
    path: '/map',
    name: 'Map',
    component: Map,
    meta: { requiresAuth: true, title: '数图城管', permission: 'map' }
  },
  {
    path: '/case-map',
    name: 'CaseMap',
    component: CaseMap,
    meta: { requiresAuth: true, title: '案件地图', permission: 'case_map' }
  },
  {
    path: '/dispatch',
    redirect: '/dispatch/query'
  },
  {
    path: '/dispatch/standards',
    name: 'CaseStandards',
    component: CaseStandards,
    meta: { requiresAuth: true, title: '立结案标准', permission: 'dispatch_standards' }
  },
  {
    path: '/dispatch/query',
    name: 'Dispatch',
    component: Dispatch,
    meta: { requiresAuth: true, title: '归属查询', permission: 'dispatch_query' }
  },
  {
    path: '/dispatch/special',
    name: 'SpecialMatters',
    component: SpecialMatters,
    meta: { requiresAuth: true, title: '特殊事项归属', permission: 'dispatch_special' }
  },
  {
    path: '/business',
    name: 'Business',
    component: Business,
    meta: { requiresAuth: true, title: '业务平台', permission: 'business' }
  },
  {
    path: '/ledger',
    redirect: '/ledger/maintenance'
  },
  {
    path: '/ledger/:tab',
    name: 'Ledger',
    component: Ledger,
    meta: { requiresAuth: true, title: '台账管理' },
    beforeEnter: (to) => {
      const allowed = {
        maintenance: 'ledger_maintenance',
        meeting: 'ledger_meeting',
        training: 'ledger_training',
        docs: 'ledger_docs',
        monitor: 'ledger_monitor',
        drone: 'ledger_drone'
      }
      const tab = to.params.tab
      if (!allowed[tab]) {
        return { path: '/ledger/maintenance' }
      }
      const userStore = useUserStore()
      if (!userStore.isAdmin && !userStore.hasPermission(allowed[tab])) {
        return { path: '/' }
      }
      return true
    }
  },
  {
    path: '/duty',
    redirect: '/duty/records'
  },
  {
    path: '/duty/schedule',
    name: 'DutySchedule',
    component: DutySchedule,
    meta: { requiresAuth: true, title: '排班管理', permission: 'duty_schedule' }
  },
  {
    path: '/duty/records',
    name: 'DutyRecord',
    component: DutyRecord,
    meta: { requiresAuth: true, title: '值班记录', permission: 'duty_records' }
  },
  {
    path: '/duty-record',
    redirect: '/duty/records'
  },
  {
    path: '/assessment',
    redirect: '/assessment/score'
  },
  {
    path: '/assessment/input',
    redirect: '/assessment/input/platform'
  },
  {
    path: '/assessment/input/platform',
    name: 'AssessmentInputPlatform',
    component: AssessmentInputPlatform,
    meta: { requiresAuth: true, title: '平台数据录入', permission: 'assessment_input_platform' }
  },
  {
    path: '/assessment/input/collector',
    name: 'AssessmentInputCollector',
    component: AssessmentInputCollector,
    meta: { requiresAuth: true, title: '采集员数据录入', permission: 'assessment_input_collector' }
  },
  {
    path: '/assessment/exemption',
    name: 'ExemptionSettings',
    component: ExemptionSettings,
    meta: { requiresAuth: true, title: '豁免期设置', permission: 'assessment_exemption' }
  },
  {
    path: '/assessment/score',
    name: 'Assessment',
    component: Assessment,
    meta: { requiresAuth: true, title: '考核计分', permission: 'assessment_score' }
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
    path: '/report-embed/:filename',
    name: 'ReportEmbed',
    component: ReportEmbed,
    meta: { requiresAuth: true, title: '报告查看' }
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
  let pageTitle = to.meta.title
  if (to.name === 'Ledger' && to.params.tab) {
    const tabTitles = {
      maintenance: '运维台账',
      meeting: '会议台账',
      training: '培训台账',
      docs: '文件资料'
    }
    pageTitle = tabTitles[to.params.tab] || '台账管理'
  }
  document.title = pageTitle ? `${pageTitle} - ${brandName}` : brandName

  // 检查是否需要登录
  if (to.meta.requiresAuth !== false && !userStore.isLoggedIn) {
    next({ name: 'Login' })
    return
  }

  // 已登录用户访问登录页，重定向到首页
  if (to.name === 'Login' && userStore.isLoggedIn) {
    next({ name: 'Home' })
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
