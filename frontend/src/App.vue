<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue';
import * as echarts from 'echarts';
import cloudbase from '@cloudbase/js-sdk';
import axios from 'axios';
import headerBg from './image/header.jpeg';

// 打印CloudBase SDK版本
console.log('CloudBase SDK版本:', cloudbase.version);

// 状态管理
const tables = ref([]);
const selectedTable = ref('');
const selectedAnalysisType = ref('');
const analysisResult = ref(null);
const loading = ref(false);
const message = ref(''); // 通用消息
const analysisMessage = ref(''); // 数据分析消息
const assessmentMessage = ref(''); // 考核计分消息
const selectedFile = ref(null);

// 计算属性：安全处理文章文件路径
const currentArticleFileUrl = computed(() => {
  if (!currentArticle.value?.file_path) return '';
  let filePath = currentArticle.value.file_path;
  // 如果是旧的完整路径，只提取文件名部分
  if (filePath.includes('backend/uploads/')) {
    const fileName = filePath.split('backend/uploads/').pop();
    return `/uploads/${fileName}`;
  }
  // 如果已经是 uploads/ 开头，直接加 /
  if (filePath.startsWith('uploads/')) {
    return `/${filePath}`;
  }
  // 其他情况，直接用
  return filePath.startsWith('/') ? filePath : `/${filePath}`;
});

// 计算属性：过滤后的问题列表（按月份）
const filteredHuiwentaiTasks = computed(() => {
  if (!selectedMonthTasks.value) {
    return huiwentaiTasks.value;
  }
  return huiwentaiTasks.value.filter(task => {
    if (!task.createdAt) return false;
    const taskDate = new Date(task.createdAt);
    const taskMonth = `${taskDate.getFullYear()}-${String(taskDate.getMonth() + 1).padStart(2, '0')}`;
    return taskMonth === selectedMonthTasks.value;
  });
});

// 计算属性：过滤后的日报数据（按月份）
const filteredHuiwentaiDailyReports = computed(() => {
  if (!selectedMonthReports.value) {
    return huiwentaiDailyReports.value;
  }
  return huiwentaiDailyReports.value.filter(report => {
    if (!report.reportDate) return false;
    const reportDate = new Date(report.reportDate);
    const reportMonth = `${reportDate.getFullYear()}-${String(reportDate.getMonth() + 1).padStart(2, '0')}`;
    return reportMonth === selectedMonthReports.value;
  });
});

// 计算属性：问题列表可用的月份选项
const availableMonthsTasks = computed(() => {
  const months = new Set();
  huiwentaiTasks.value.forEach(task => {
    if (task.createdAt) {
      const taskDate = new Date(task.createdAt);
      months.add(`${taskDate.getFullYear()}-${String(taskDate.getMonth() + 1).padStart(2, '0')}`);
    }
  });
  return Array.from(months).sort().reverse();
});

// 计算属性：日报数据可用的月份选项
const availableMonthsReports = computed(() => {
  const months = new Set();
  huiwentaiDailyReports.value.forEach(report => {
    if (report.reportDate) {
      const reportDate = new Date(report.reportDate);
      months.add(`${reportDate.getFullYear()}-${String(reportDate.getMonth() + 1).padStart(2, '0')}`);
    }
  });
  return Array.from(months).sort().reverse();
});

// 计算属性：本月数据统计（基于北京时间）
const currentMonthStats = computed(() => {
  // 获取北京时间当前年月
  const now = new Date();
  const beijingOffset = 8 * 60; // 北京时间UTC+8
  const localOffset = now.getTimezoneOffset();
  const beijingTime = new Date(now.getTime() + (beijingOffset + localOffset) * 60 * 1000);
  const currentYear = beijingTime.getFullYear();
  const currentMonth = beijingTime.getMonth() + 1;
  const currentMonthStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}`;

  let totalReported = 0;
  let totalAccepted = 0;
  let totalCompleted = 0;

  huiwentaiDailyReports.value.forEach(report => {
    if (report.reportDate) {
      const reportDate = new Date(report.reportDate);
      const reportMonth = `${reportDate.getFullYear()}-${String(reportDate.getMonth() + 1).padStart(2, '0')}`;
      if (reportMonth === currentMonthStr) {
        totalReported += report.reported || 0;
        totalAccepted += report.accepted || 0;
        totalCompleted += report.completed || 0;
      }
    }
  });

  return {
    reported: totalReported,
    accepted: totalAccepted,
    completed: totalCompleted
  };
});

// 计算属性：问题列表分页后的数据
const paginatedHuiwentaiTasks = computed(() => {
  const start = (tasksCurrentPage.value - 1) * tasksPageSize.value;
  const end = start + tasksPageSize.value;
  return filteredHuiwentaiTasks.value.slice(start, end);
});

// 计算属性：问题列表总页数
const tasksTotalPages = computed(() => {
  return Math.ceil(filteredHuiwentaiTasks.value.length / tasksPageSize.value) || 1;
});

// 计算属性：日报数据分页后的数据
const paginatedHuiwentaiDailyReports = computed(() => {
  const start = (reportsCurrentPage.value - 1) * reportsPageSize.value;
  const end = start + reportsPageSize.value;
  return filteredHuiwentaiDailyReports.value.slice(start, end);
});

// 计算属性：日报数据总页数
const reportsTotalPages = computed(() => {
  return Math.ceil(filteredHuiwentaiDailyReports.value.length / reportsPageSize.value) || 1;
});

const activeModule = ref('home'); // home, data, assessment, analysis, spotcheck, tools, chengguantong, cms, map, huiwentai, ai-apps
const aiAppsActiveTab = ref('analysis'); // analysis, analysis-v2, spotcheck, chengguantong

// 数据分析（新版）状态管理
const selectedTableV2 = ref('');
const analysisPrompt = ref('');
const selectedModel = ref('volcengine'); // 'volcengine' 或 'bailian'
const analysisV2Loading = ref(false);
const analysisV2Result = ref(null);
const analysisV2Message = ref('');
const analysisV2Error = ref('');
const chartRefs = ref([]);

// 地图服务状态管理
const mapInstance = ref(null);
const mapLoading = ref(false);
const mapError = ref('');
const casesData = ref([]);

// 案件抽查模块状态管理
const spotcheckFile = ref(null);
const spotcheckLoading = ref(false);
const spotcheckResult = ref(null);
const spotcheckMessage = ref('');
const spotcheckError = ref('');

// 考核计分状态管理
const selectedDepartment = ref('');
const selectedAssessmentTable = ref('');
const assessmentResult = ref(null);
const assessmentActiveTab = ref('old'); // 'old' 为原版，'new' 为新版

// 新版考核计分状态管理
const selectedDepartmentV2 = ref('');
const selectedAssessmentTableV2 = ref('');
const assessmentResultV2 = ref(null);
const assessmentMessageV2 = ref('');

// CMS状态管理
const cmsCategories = ref([]);
const cmsArticles = ref([]);
const allHomeArticles = ref([]);
const allCategoryOption = { id: 'all', name: '全部' }; // "全部"选项常量
const selectedCategory = ref(allCategoryOption);
const cmsLoading = ref(false);
const cmsError = ref('');
const showArticleDetail = ref(false);
const currentArticle = ref(null);
const articleDetailLoading = ref(false);
const articleDetailError = ref('');
const cmsArticlesPage = ref(1);
const cmsArticlesPerPage = ref(10);
const cmsArticlesTotal = ref(0);
const cmsArticlesPages = ref(0);

// 汇问台状态管理
const cloudbaseInstance = ref(null);
const huiwentaiTasks = ref([]);
const huiwentaiLoading = ref(false);
const huiwentaiError = ref('');
const huiwentaiActiveTab = ref('tasks'); // tasks, daily-reports
const huiwentaiDailyReports = ref([]);
const expandedReportId = ref(null); // 当前展开的日报ID
const selectedMonthTasks = ref(''); // 问题列表选择的月份
const selectedMonthReports = ref(''); // 日报数据选择的月份
const tasksCurrentPage = ref(1); // 问题列表当前页
const tasksPageSize = ref(10); // 问题列表每页数量
const reportsCurrentPage = ref(1); // 日报数据当前页
const reportsPageSize = ref(20); // 日报数据每页数量

// 案件管理状态管理
const casesList = ref([]);
const casesLoading = ref(false);
const casesError = ref('');
const casesCurrentPage = ref(1);
const casesPageSize = ref(20);
const casesTotal = ref(0);
const casesSearch = ref('');
const currentCase = ref(null);
const showCaseDetail = ref(false);
const caseImportFile = ref(null);
const caseImportLoading = ref(false);
const caseImportMessage = ref('');

// 业务平台展示状态管理
const displayBusinessPlatforms = ref([]);
const businessPlatformsLoading = ref(false);

// 城管通模块状态管理
const chengguantongQuery = ref('');
const chengguantongResponse = ref('');
const chengguantongLoading = ref(false);
const chengguantongError = ref('');
const showResponse = ref(false);
const chatHistory = ref([]);
const showHistory = ref(false);

// 阿里云百炼API配置已移至后端，前端不再需要配置API Key

// CMS表单状态
const showAddCategoryForm = ref(false);
const showAddArticleForm = ref(false);
const editingCategory = ref(null);
const editingArticle = ref(null);
const newCategory = ref({
  name: '',
  slug: '',
  description: '',
  order: 0
});
const newArticle = ref({
  title: '',
  slug: '',
  content: '',
  summary: '',
  category_id: '',
  status: 'published',
  file_path: ''
});
const cmsFormError = ref('');
const fileUploadLoading = ref(false);
const fileUploadError = ref('');
const imageUploadLoading = ref(false);
const imageUploadError = ref('');

// 登录状态管理
const isLoggedIn = ref(false);
const userInfo = ref(null);
const showLogin = ref(true);
const loginForm = ref({
  username: '',
  password: ''
});
const loginLoading = ref(false);
const loginError = ref('');

// 管理员管理状态
const adminActiveTab = ref('users'); // users, business, system
const systemConfigTab = ref('general'); // general, security, logs
const businessTab = ref('data'); // data, cms, business-platforms, assessment

// 部门列表
const assessmentDepartments = [
  '城市综合行政执法队',
  '市容环卫中心',
  '园林绿化服务中心（片区）',
  '园林绿化服务中心（公园广场）'
];

// 当前选择的部门
const selectedAssessmentDepartment = ref('城市综合行政执法队');

// 考核计分系数状态管理 - 按部门存储
const assessmentCoefficients = ref({
  '城市综合行政执法队': {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  },
  '市容环卫中心': {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  },
  '园林绿化服务中心（片区）': {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  },
  '园林绿化服务中心（公园广场）': {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  }
});

// 安全获取当前部门系数
function getCurrentDeptCoefficients() {
  const dept = selectedAssessmentDepartment.value;
  if (!assessmentCoefficients.value[dept]) {
    assessmentCoefficients.value[dept] = {
      on_time: 1.0,
      overdue: 0.4,
      closure_weight: 0.8,
      delay_weight: 0.1,
      rework_weight: 0.1
    };
  }
  return assessmentCoefficients.value[dept];
}
const assessmentCoefficientsLoading = ref(false);
const assessmentCoefficientsError = ref('');
const assessmentCoefficientsMessage = ref('');
const users = ref([]);
const showAddUserForm = ref(false);
const editingUser = ref(null);
const newUser = ref({
  username: '',
  password: '',
  role: 'user'
});
const adminLoading = ref(false);
const adminError = ref('');

// 业务平台管理状态
const businessPlatforms = ref([]);
const showAddPlatformForm = ref(false);
const editingPlatform = ref(null);
const newPlatform = ref({
  name: '',
  url: '',
  image_path: ''
});
const platformLoading = ref(false);
const platformError = ref('');
const platformFileUploadLoading = ref(false);
const platformFileUploadError = ref('');

// 表格可见性状态管理
const tableVisibility = ref({});

// 小工具模块状态管理
const activeToolTab = ref('huanwei-assignment'); // huanwei-assignment, location-extraction, data-cleaning, sql-generator
const naturalLanguageQuery = ref('');
const selectedToolTable = ref('');
const toolLoading = ref(false);
const toolMessage = ref('');
const toolError = ref('');
const queryResult = ref(null);
const generatedSQL = ref('');
const showResultModal = ref(false); // 控制查询结果弹框的显示/隐藏

// 市容环卫案件分配状态管理
const huanweiFile = ref(null);
const huanweiLoading = ref(false);
const huanweiMessage = ref('');
const huanweiError = ref('');
const huanweiDownloadUrl = ref('');

// 地址信息提取状态管理
const locationFile = ref(null);
const locationLoading = ref(false);
const locationMessage = ref('');
const locationError = ref('');
const locationDownloadUrl = ref('');

// 数据清洗模块状态管理
const cleaningFile = ref(null);
const cleaningLoading = ref(false);
const cleaningMessage = ref('');
const cleaningError = ref('');
const cleaningDownloadUrl = ref('');
const cleaningFields = ref([]);
const selectedCleaningField = ref('');



// 初始化表格可见性状态
function initTableVisibility() {
  const savedVisibility = localStorage.getItem('tableVisibility');
  if (savedVisibility) {
    try {
      const parsedConfig = JSON.parse(savedVisibility);
      tableVisibility.value = parsedConfig;
      console.log('从localStorage加载表格可见性配置:', parsedConfig);
    } catch (error) {
      console.error('Error parsing table visibility:', error);
      tableVisibility.value = {};
      // 清空损坏的配置
      localStorage.removeItem('tableVisibility');
    }
  } else {
    console.log('localStorage中没有表格可见性配置');
  }
}

// 权限管理状态
const showEditPermissionsForm = ref(false);
const editingPermissionsUser = ref(null);
const editingPermissions = ref({
  assessment: false,
  data_analysis: false,
  spotcheck: false,
  map: false,
  huiwentai: false,
  cases: false,
  business: false
});

// 从本地存储获取token和用户信息
const token = localStorage.getItem('token');
const savedUserInfo = localStorage.getItem('userInfo');

// 如果有保存的用户信息，直接使用
if (savedUserInfo) {
  try {
    const parsedUserInfo = JSON.parse(savedUserInfo);
    userInfo.value = parsedUserInfo;
    isLoggedIn.value = true;
    showLogin.value = false;
  } catch (error) {
    console.error('解析用户信息失败:', error);
  }
}

// 验证token是否有效
if (token) {
  checkTokenValidity();
}

// 图表引用
const dailyChart = ref(null);
const hourlyChart = ref(null);
const spaceChart = ref(null);
const spaceChart2 = ref(null);
const spaceChart3 = ref(null);
const sourceChart = ref(null);

// 分析进度管理
const analysisSteps = ref([
  { icon: '📊', text: '读取数据...', status: 'pending' },
  { icon: '⏰', text: '处理时间数据...', status: 'pending' },
  { icon: '🤖', text: '调用大模型分析...', status: 'pending' },
  { icon: '📝', text: '生成分析报告...', status: 'pending' },
  { icon: '✅', text: '分析完成!', status: 'pending' }
]);
const currentStep = ref(-1);

// 重置分析步骤状态
function resetAnalysisSteps() {
  analysisSteps.value.forEach(step => {
    step.status = 'pending';
  });
  currentStep.value = -1;
}

// 更新步骤状态
function updateStepStatus(stepIndex, status) {
  if (stepIndex >= 0 && stepIndex < analysisSteps.value.length) {
    // 更新当前步骤状态
    analysisSteps.value[stepIndex].status = status;
    currentStep.value = stepIndex;

    // 如果是完成状态，标记之前的步骤都已完成
    if (status === 'active') {
      for (let i = 0; i < stepIndex; i++) {
        analysisSteps.value[i].status = 'completed';
      }
    } else if (status === 'completed') {
      for (let i = 0; i <= stepIndex; i++) {
        analysisSteps.value[i].status = 'completed';
      }
    }
  }
}

// 渲染图表
function renderCharts() {
  if (!analysisResult.value || !analysisResult.value.chart_data) return;
  
  const chartData = analysisResult.value.chart_data;
  
  // 渲染日案件量趋势图表（时间分析）
  if (chartData.daily && dailyChart.value) {
    const dailyChartInstance = echarts.init(dailyChart.value);
    const dailyOption = {
      title: {
        text: '日案件量趋势',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}日: {c}件'
      },
      xAxis: {
        type: 'category',
        data: chartData.daily.map(item => item.day),
        name: '日期'
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: chartData.daily.map(item => item.count),
        type: 'line',
        smooth: true,
        itemStyle: {
          color: '#27ae60'
        }
      }]
    };
    dailyChartInstance.setOption(dailyOption);
  }
  
  // 渲染小时级高峰时段图表（时间分析）
  if (chartData.hourly && hourlyChart.value) {
    const hourlyChartInstance = echarts.init(hourlyChart.value);
    const hourlyOption = {
      title: {
        text: '小时级高峰时段',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}:00: {c}件'
      },
      xAxis: {
        type: 'category',
        data: chartData.hourly.map(item => item.hour),
        name: '小时'
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: chartData.hourly.map(item => item.count),
        type: 'bar',
        itemStyle: {
          color: '#3498db'
        }
      }]
    };
    hourlyChartInstance.setOption(hourlyOption);
  }
  
  // 渲染街道案件密度图表（空间分析）
  if (chartData.street && spaceChart.value) {
    const spaceChartInstance = echarts.init(spaceChart.value);
    const streetData = chartData.street;
    
    // 尝试获取街道名称和案件数量字段
    let streetNames = [];
    let caseCounts = [];
    
    // 遍历数据，提取街道名称和案件数量
    streetData.forEach(item => {
      // 找到包含街道名称的字段（不是数字的字段）
      const keys = Object.keys(item);
      for (const key of keys) {
        const value = item[key];
        if (typeof value === 'string' && !/^\d+$/.test(value)) {
          streetNames.push(value);
        } else if (typeof value === 'number' || /^\d+$/.test(value)) {
          caseCounts.push(Number(value));
        }
      }
    });
    
    // 如果没有找到字符串字段，使用默认标签
    if (streetNames.length === 0) {
      streetNames = streetData.map((_, index) => `街道${index + 1}`);
    }
    
    // 如果没有找到数字字段，尝试从值中提取
    if (caseCounts.length === 0) {
      streetData.forEach(item => {
        const values = Object.values(item);
        for (const value of values) {
          if (typeof value === 'number' || /^\d+$/.test(value)) {
            caseCounts.push(Number(value));
            break;
          }
        }
      });
    }
    
    const spaceOption = {
      title: {
        text: '各街道案件密度',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}件'
      },
      xAxis: {
        type: 'category',
        data: streetNames,
        name: '街道',
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: caseCounts,
        type: 'bar',
        itemStyle: {
          color: '#e74c3c'
        }
      }]
    };
    spaceChartInstance.setOption(spaceOption);
  }
  
  // 渲染社区案件密度图表（空间分析）
  if (chartData.community && spaceChart2.value) {
    const spaceChartInstance2 = echarts.init(spaceChart2.value);
    const communityData = chartData.community;
    
    // 尝试获取社区名称和案件数量字段
    let communityNames = [];
    let caseCounts = [];
    
    // 遍历数据，提取社区名称和案件数量
    communityData.forEach(item => {
      // 找到包含社区名称的字段（不是数字的字段）
      const keys = Object.keys(item);
      for (const key of keys) {
        const value = item[key];
        if (typeof value === 'string' && !/^\d+$/.test(value)) {
          communityNames.push(value);
        } else if (typeof value === 'number' || /^\d+$/.test(value)) {
          caseCounts.push(Number(value));
        }
      }
    });
    
    // 如果没有找到字符串字段，使用默认标签
    if (communityNames.length === 0) {
      communityNames = communityData.map((_, index) => `社区${index + 1}`);
    }
    
    // 如果没有找到数字字段，尝试从值中提取
    if (caseCounts.length === 0) {
      communityData.forEach(item => {
        const values = Object.values(item);
        for (const value of values) {
          if (typeof value === 'number' || /^\d+$/.test(value)) {
            caseCounts.push(Number(value));
            break;
          }
        }
      });
    }
    
    const spaceOption2 = {
      title: {
        text: '各社区案件密度',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}件'
      },
      xAxis: {
        type: 'category',
        data: communityNames,
        name: '社区',
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: caseCounts,
        type: 'bar',
        itemStyle: {
          color: '#f39c12'
        }
      }]
    };
    spaceChartInstance2.setOption(spaceOption2);
  }
  
  // 渲染片区案件密度图表（空间分析）
  if (chartData.area && spaceChart3.value) {
    const spaceChartInstance3 = echarts.init(spaceChart3.value);
    const areaData = chartData.area;
    
    // 尝试获取片区名称和案件数量字段
    let areaNames = [];
    let caseCounts = [];
    
    // 遍历数据，提取片区名称和案件数量
    areaData.forEach(item => {
      // 找到包含片区名称的字段（不是数字的字段）
      const keys = Object.keys(item);
      for (const key of keys) {
        const value = item[key];
        if (typeof value === 'string' && !/^\d+$/.test(value)) {
          areaNames.push(value);
        } else if (typeof value === 'number' || /^\d+$/.test(value)) {
          caseCounts.push(Number(value));
        }
      }
    });
    
    // 如果没有找到字符串字段，使用默认标签
    if (areaNames.length === 0) {
      areaNames = areaData.map((_, index) => `片区${index + 1}`);
    }
    
    // 如果没有找到数字字段，尝试从值中提取
    if (caseCounts.length === 0) {
      areaData.forEach(item => {
        const values = Object.values(item);
        for (const value of values) {
          if (typeof value === 'number' || /^\d+$/.test(value)) {
            caseCounts.push(Number(value));
            break;
          }
        }
      });
    }
    
    const spaceOption3 = {
      title: {
        text: '各片区案件密度',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}件'
      },
      xAxis: {
        type: 'category',
        data: areaNames,
        name: '片区',
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: caseCounts,
        type: 'bar',
        itemStyle: {
          color: '#9b59b6'
        }
      }]
    };
    spaceChartInstance3.setOption(spaceOption3);
  }
  
  // 渲染案件来源分布图表（来源分析）
  if (chartData.source && sourceChart.value) {
    const sourceChartInstance = echarts.init(sourceChart.value);
    const sourceData = chartData.source;
    
    // 尝试获取来源名称和案件数量字段
    let sourceNames = [];
    let caseCounts = [];
    
    // 遍历数据，提取来源名称和案件数量
    sourceData.forEach(item => {
      // 找到包含来源名称的字段（不是数字的字段）
      const keys = Object.keys(item);
      for (const key of keys) {
        const value = item[key];
        if (typeof value === 'string' && !/^\d+$/.test(value)) {
          sourceNames.push(value);
        } else if (typeof value === 'number' || /^\d+$/.test(value)) {
          caseCounts.push(Number(value));
        }
      }
    });
    
    // 如果没有找到字符串字段，使用默认标签
    if (sourceNames.length === 0) {
      sourceNames = sourceData.map((_, index) => `来源${index + 1}`);
    }
    
    // 如果没有找到数字字段，尝试从值中提取
    if (caseCounts.length === 0) {
      sourceData.forEach(item => {
        const values = Object.values(item);
        for (const value of values) {
          if (typeof value === 'number' || /^\d+$/.test(value)) {
            caseCounts.push(Number(value));
            break;
          }
        }
      });
    }
    
    const sourceOption = {
      title: {
        text: '案件来源分布',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}件'
      },
      xAxis: {
        type: 'category',
        data: sourceNames,
        name: '来源',
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: caseCounts,
        type: 'bar',
        itemStyle: {
          color: '#3498db'
        }
      }]
    };
    sourceChartInstance.setOption(sourceOption);
  }
  
  // 渲染案件类型分布图表（案件类型分析）
  if (chartData.type && sourceChart.value) {
    const typeChartInstance = echarts.init(sourceChart.value);
    const typeData = chartData.type;
    
    // 尝试获取类型名称和案件数量字段
    let typeNames = [];
    let caseCounts = [];
    
    // 遍历数据，提取类型名称和案件数量
    typeData.forEach(item => {
      // 找到包含类型名称的字段（不是数字的字段）
      const keys = Object.keys(item);
      for (const key of keys) {
        const value = item[key];
        if (typeof value === 'string' && !/^\d+$/.test(value)) {
          typeNames.push(value);
        } else if (typeof value === 'number' || /^\d+$/.test(value)) {
          caseCounts.push(Number(value));
        }
      }
    });
    
    // 如果没有找到字符串字段，使用默认标签
    if (typeNames.length === 0) {
      typeNames = typeData.map((_, index) => `类型${index + 1}`);
    }
    
    // 如果没有找到数字字段，尝试从值中提取
    if (caseCounts.length === 0) {
      typeData.forEach(item => {
        const values = Object.values(item);
        for (const value of values) {
          if (typeof value === 'number' || /^\d+$/.test(value)) {
            caseCounts.push(Number(value));
            break;
          }
        }
      });
    }
    
    const typeOption = {
      title: {
        text: '案件类型分布',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}: {c}件'
      },
      xAxis: {
        type: 'category',
        data: typeNames,
        name: '案件类型',
        axisLabel: {
          rotate: 45,
          interval: 0
        }
      },
      yAxis: {
        type: 'value',
        name: '案件量'
      },
      series: [{
        data: caseCounts,
        type: 'bar',
        itemStyle: {
          color: '#e74c3c'
        }
      }]
    };
    typeChartInstance.setOption(typeOption);
  }
  
  // 渲染重复案件分析图表
  try {
    // 1. 地址描述重复TOP10柱状图
    if (chartData.address_duplicates && sourceChart.value) {
      const duplicateChartInstance = echarts.init(sourceChart.value);
      const duplicateData = chartData.address_duplicates;
      
      // 尝试获取地址描述和重复次数字段
      let addressNames = [];
      let duplicateCounts = [];
      
      // 遍历数据，提取地址描述和重复次数
      duplicateData.forEach(item => {
        // 找到包含地址描述的字段（不是数字的字段）
        const keys = Object.keys(item);
        for (const key of keys) {
          const value = item[key];
          if (typeof value === 'string' && !/^\d+$/.test(value)) {
            addressNames.push(value);
          } else if (typeof value === 'number' || /^\d+$/.test(value)) {
            duplicateCounts.push(Number(value));
          }
        }
      });
      
      // 如果没有找到字符串字段，使用默认标签
      if (addressNames.length === 0) {
        addressNames = duplicateData.map((_, index) => `地址${index + 1}`);
      }
      
      // 如果没有找到数字字段，尝试从值中提取
      if (duplicateCounts.length === 0) {
        duplicateData.forEach(item => {
          const values = Object.values(item);
          for (const value of values) {
            if (typeof value === 'number' || /^\d+$/.test(value)) {
              duplicateCounts.push(Number(value));
              break;
            }
          }
        });
      }
      
      const duplicateOption = {
        title: {
          text: '地址描述重复TOP10',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          formatter: '{b}: {c}次重复'
        },
        xAxis: {
          type: 'category',
          data: addressNames,
          name: '地址描述',
          axisLabel: {
            rotate: 45,
            interval: 0
          }
        },
        yAxis: {
          type: 'value',
          name: '重复次数'
        },
        series: [{
          data: duplicateCounts,
          type: 'bar',
          itemStyle: {
            color: '#9b59b6'
          }
        }]
      };
      duplicateChartInstance.setOption(duplicateOption);
    }
    
    // 2. 问题描述重复TOP10柱状图（纵向）
    if (chartData.problem_duplicates && dailyChart.value) {
      const problemChartInstance = echarts.init(dailyChart.value);
      const problemData = chartData.problem_duplicates;
      
      // 尝试获取问题描述和重复次数字段
      let problemNames = [];
      let problemCounts = [];
      
      // 遍历数据，提取问题描述和重复次数
      problemData.forEach(item => {
        const keys = Object.keys(item);
        for (const key of keys) {
          const value = item[key];
          if (typeof value === 'string' && !/^\d+$/.test(value)) {
            problemNames.push(value);
          } else if (typeof value === 'number' || /^\d+$/.test(value)) {
            problemCounts.push(Number(value));
          }
        }
      });
      
      // 如果没有找到字符串字段，使用默认标签
      if (problemNames.length === 0) {
        problemNames = problemData.map((_, index) => `问题${index + 1}`);
      }
      
      // 如果没有找到数字字段，尝试从值中提取
      if (problemCounts.length === 0) {
        problemData.forEach(item => {
          const values = Object.values(item);
          for (const value of values) {
            if (typeof value === 'number' || /^\d+$/.test(value)) {
              problemCounts.push(Number(value));
              break;
            }
          }
        });
      }
      
      const problemOption = {
        title: {
          text: '问题描述重复TOP10',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          formatter: '{b}: {c}次重复'
        },
        xAxis: {
          type: 'category',
          data: problemNames,
          name: '问题描述',
          axisLabel: {
            rotate: 45,
            interval: 0
          }
        },
        yAxis: {
          type: 'value',
          name: '重复次数'
        },
        series: [{
          data: problemCounts,
          type: 'bar',
          itemStyle: {
            color: '#e74c3c'
          }
        }]
      };
      problemChartInstance.setOption(problemOption);
    }
    
    // 3. 地址描述类型占比饼图
    if (chartData.address_type_distribution && spaceChart.value) {
      const addressTypeChartInstance = echarts.init(spaceChart.value);
      const addressTypeData = chartData.address_type_distribution;
      
      // 准备饼图数据
      const pieData = addressTypeData.map(item => {
        return {
          name: item.type,
          value: item.count
        };
      });
      
      const addressTypeOption = {
        title: {
          text: '地址描述类型占比',
          left: 'center'
        },
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          left: 'left',
          data: addressTypeData.map(item => item.type)
        },
        series: [{
          name: '地址类型',
          type: 'pie',
          radius: '50%',
          center: ['50%', '60%'],
          data: pieData,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }]
      };
      addressTypeChartInstance.setOption(addressTypeOption);
    }
    
    // 4. 组合重复TOP10横向条形图
    if (chartData.combined_duplicates && spaceChart2.value) {
      const combinedChartInstance = echarts.init(spaceChart2.value);
      const combinedData = chartData.combined_duplicates;
      
      // 尝试获取组合描述和重复次数字段
      let combinedNames = [];
      let combinedCounts = [];
      
      // 遍历数据，提取组合描述和重复次数
      combinedData.forEach(item => {
        const keys = Object.keys(item);
        for (const key of keys) {
          const value = item[key];
          if (typeof value === 'string' && !/^\d+$/.test(value)) {
            combinedNames.push(value);
          } else if (typeof value === 'number' || /^\d+$/.test(value)) {
            combinedCounts.push(Number(value));
          }
        }
      });
      
      // 如果没有找到字符串字段，使用默认标签
      if (combinedNames.length === 0) {
        combinedNames = combinedData.map((_, index) => `组合${index + 1}`);
      }
      
      // 如果没有找到数字字段，尝试从值中提取
      if (combinedCounts.length === 0) {
        combinedData.forEach(item => {
          const values = Object.values(item);
          for (const value of values) {
            if (typeof value === 'number' || /^\d+$/.test(value)) {
              combinedCounts.push(Number(value));
              break;
            }
          }
        });
      }
      
      const combinedOption = {
        title: {
          text: '组合重复TOP10',
          left: 'center'
        },
        tooltip: {
          trigger: 'axis',
          formatter: '{b}: {c}次重复'
        },
        xAxis: {
          type: 'value',
          name: '重复次数'
        },
        yAxis: {
          type: 'category',
          data: combinedNames,
          name: '问题+地址组合',
          axisLabel: {
            interval: 0,
            formatter: function(value) {
              return value.length > 20 ? value.substring(0, 20) + '...' : value;
            }
          }
        },
        series: [{
          data: combinedCounts,
          type: 'bar',
          itemStyle: {
            color: '#3498db'
          }
        }]
      };
      combinedChartInstance.setOption(combinedOption);
    }
    
    // 5. 重复案件违规类型占比饼图
    if (chartData.violation_type_distribution && spaceChart3.value) {
      const violationChartInstance = echarts.init(spaceChart3.value);
      const violationData = chartData.violation_type_distribution;
      
      // 准备饼图数据
      const violationPieData = violationData.map(item => {
        return {
          name: item.type,
          value: item.count
        };
      });
      
      const violationOption = {
        title: {
          text: '重复案件违规类型占比',
          left: 'center'
        },
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          left: 'left',
          data: violationData.map(item => item.type)
        },
        series: [{
          name: '违规类型',
          type: 'pie',
          radius: '50%',
          center: ['50%', '60%'],
          data: violationPieData,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }]
      };
      violationChartInstance.setOption(violationOption);
    }
    
    // 渲染对比上月分析图表
    if (analysisResult.value.analysis_type === 'monthly_comparison') {
      // 1. 月度案件量对比图表
      if (chartData.monthly_comparison && dailyChart.value) {
        const monthlyChartInstance = echarts.init(dailyChart.value);
        const monthlyOption = {
          title: {
            text: '月度案件量对比',
            left: 'center'
          },
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: {c}件'
          },
          xAxis: {
            type: 'category',
            data: chartData.monthly_comparison.map(item => item.month),
            name: '月份'
          },
          yAxis: {
            type: 'value',
            name: '案件量'
          },
          series: [{
            data: chartData.monthly_comparison.map(item => item.count),
            type: 'bar',
            itemStyle: {
              color: '#3498db'
            }
          }]
        };
        monthlyChartInstance.setOption(monthlyOption);
      }
      
      // 2. 案件大小类别变化图表
      if (chartData.case_size_comparison && sourceChart.value) {
        const caseSizeChartInstance = echarts.init(sourceChart.value);
        
        // 准备数据
        const categories = [];
        const series = [];
        
        chartData.case_size_comparison.forEach((item, index) => {
          const typeName = item.type;
          const color = index === 0 ? '#e74c3c' : '#27ae60';
          
          // 提取类别名称和数量
          const categoryNames = [];
          const counts = [];
          
          item.categories.forEach(cat => {
            // 找到类别名称和数量字段
            let name = '';
            let count = 0;
            
            for (const key in cat) {
              if (typeof cat[key] === 'string' && !/^\d+$/.test(cat[key])) {
                name = cat[key];
              } else if (typeof cat[key] === 'number' || /^\d+$/.test(cat[key])) {
                count = Number(cat[key]);
              }
            }
            
            categoryNames.push(name);
            counts.push(count);
          });
          
          // 确保类别名称唯一
          if (categories.length === 0) {
            categories.push(...categoryNames);
          }
          
          // 添加系列数据
          series.push({
            name: typeName,
            type: 'bar',
            data: counts,
            itemStyle: {
              color: color
            }
          });
        });
        
        const caseSizeOption = {
          title: {
            text: '案件大小类别变化',
            left: 'center'
          },
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: {c}件'
          },
          legend: {
            data: chartData.case_size_comparison.map(item => item.type),
            bottom: 10
          },
          xAxis: {
            type: 'category',
            data: categories,
            name: '案件类型',
            axisLabel: {
              rotate: 45,
              interval: 0
            }
          },
          yAxis: {
            type: 'value',
            name: '案件量'
          },
          series: series
        };
        caseSizeChartInstance.setOption(caseSizeOption);
      }
      
      // 3. 问题趋势变化图表
      if (chartData.problem_trend && spaceChart.value) {
        const problemTrendChartInstance = echarts.init(spaceChart.value);
        
        // 准备数据
        const problemNames = [];
        const series = [];
        
        chartData.problem_trend.forEach((item, index) => {
          const typeName = item.type;
          const color = index === 0 ? '#f39c12' : '#9b59b6';
          
          // 提取问题名称和数量
          const names = [];
          const counts = [];
          
          item.problems.forEach(problem => {
            // 找到问题名称和数量字段
            let name = '';
            let count = 0;
            
            for (const key in problem) {
              if (typeof problem[key] === 'string' && !/^\d+$/.test(problem[key])) {
                name = problem[key];
              } else if (typeof problem[key] === 'number' || /^\d+$/.test(problem[key])) {
                count = Number(problem[key]);
              }
            }
            
            names.push(name);
            counts.push(count);
          });
          
          // 确保问题名称唯一
          if (problemNames.length === 0) {
            problemNames.push(...names);
          }
          
          // 添加系列数据
          series.push({
            name: typeName,
            type: 'bar',
            data: counts,
            itemStyle: {
              color: color
            }
          });
        });
        
        const problemTrendOption = {
          title: {
            text: '问题趋势变化',
            left: 'center'
          },
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: {c}件'
          },
          legend: {
            data: chartData.problem_trend.map(item => item.type),
            bottom: 10
          },
          xAxis: {
            type: 'category',
            data: problemNames,
            name: '问题描述',
            axisLabel: {
              rotate: 45,
              interval: 0
            }
          },
          yAxis: {
            type: 'value',
            name: '案件量'
          },
          series: series
        };
        problemTrendChartInstance.setOption(problemTrendOption);
      }
    }
  } catch (error) {
    console.error('Error rendering charts:', error);
    // 继续执行，不中断分析流程
  }
  }

// 监听分析结果变化，更新图表
watch(() => analysisResult.value, () => {
  nextTick(() => {
    renderCharts();
  });
});

// 监听窗口大小变化，调整图表大小
window.addEventListener('resize', () => {
  if (dailyChart.value) {
    echarts.getInstanceByDom(dailyChart.value)?.resize();
  }
  if (hourlyChart.value) {
    echarts.getInstanceByDom(hourlyChart.value)?.resize();
  }
  if (spaceChart.value) {
    echarts.getInstanceByDom(spaceChart.value)?.resize();
  }
  if (spaceChart2.value) {
    echarts.getInstanceByDom(spaceChart2.value)?.resize();
  }
  if (spaceChart3.value) {
    echarts.getInstanceByDom(spaceChart3.value)?.resize();
  }
  if (sourceChart.value) {
    echarts.getInstanceByDom(sourceChart.value)?.resize();
  }
});

// 分析类型选项
const analysisTypes = [
  { value: 'time_analysis', label: '案件时间分析' },
  { value: 'space_analysis', label: '案件空间分析' },
  { value: 'source_analysis', label: '案件来源分析' },
  { value: 'type_analysis', label: '案件类型分析' },
  { value: 'duplicate_analysis', label: '重复案件分析' },
  { value: 'monthly_comparison', label: '对比上月分析' }
];

// 获取分析类型的中文名称
function getAnalysisTypeName(typeValue) {
  const type = analysisTypes.find(t => t.value === typeValue);
  return type ? type.label : typeValue;
}

// 格式化日期为 MM-DD 格式
function formatDate(dateString) {
  if (!dateString) return '';
  
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '';
  
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  
  return `${month}-${day}`;
}

// 截断标题，最多显示20个字符
function truncateTitle(title) {
  if (!title) return '';
  if (title.length <= 20) return title;
  return title.substring(0, 20) + '...';
}

function getPhotoPaths(photoPath) {
  if (!photoPath) return [];
  return photoPath.split(',').filter(path => path.trim());
}

function handleImageError(event) {
  event.target.style.display = 'none';
}

// 初始化时获取数据库表
onMounted(() => {
  fetchTables();
  // 初始化表格可见性状态
  initTableVisibility();
  // 首页也需要获取CMS数据
  fetchCMSCategories();
  // 获取业务平台数据用于展示
  fetchDisplayBusinessPlatforms();
  // 获取考核计分系数
  fetchAssessmentCoefficients();
  // 获取汇问台日报数据用于首页统计
  fetchHuiwentaiDailyReports();
});

// 监听业务管理标签页变化，当切换到cms标签时获取CMS数据
watch(
  () => businessTab.value,
  (newTab) => {
    if (newTab === 'cms') {
      fetchCMSCategories();
    } else if (newTab === 'business-platforms') {
      fetchBusinessPlatforms();
    } else if (newTab === 'data') {
      fetchTablesForManagement();
    } else if (newTab === 'assessment') {
      fetchAssessmentCoefficients();
    }
  }
);

// 监听管理员标签页变化，当切换到业务管理时获取数据
watch(
  () => adminActiveTab.value,
  (newTab) => {
    if (newTab === 'business') {
      // 切换到业务管理时，重置为第一个标签（数据管理）
      businessTab.value = 'data';
      fetchTablesForManagement();
    }
  }
);

// 获取业务平台列表用于展示
async function fetchDisplayBusinessPlatforms() {
  try {
    businessPlatformsLoading.value = true;
    
    const response = await fetch('/api/business-platforms');
    const data = await response.json();
    if (data.platforms) {
      displayBusinessPlatforms.value = data.platforms;
    }
  } catch (error) {
    console.error('Error fetching business platforms for display:', error);
  } finally {
    businessPlatformsLoading.value = false;
  }
}

// 获取业务平台列表
async function fetchBusinessPlatforms() {
  try {
    platformLoading.value = true;
    platformError.value = '';
    
    const response = await fetch('/api/business-platforms', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.platforms) {
      businessPlatforms.value = data.platforms;
    }
  } catch (error) {
    platformError.value = '获取业务平台列表失败: ' + error.message;
    console.error('Error fetching business platforms:', error);
  } finally {
    platformLoading.value = false;
  }
}

// 上传平台封面图片
async function uploadPlatformImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  try {
    platformFileUploadLoading.value = true;
    platformFileUploadError.value = '';
    
    // 检查登录状态
    console.log('Upload initiated, isLoggedIn:', isLoggedIn.value);
    console.log('User info:', userInfo.value);
    
    const formData = new FormData();
    formData.append('file', file);
    
    // 确保获取正确的认证头
    const authHeaders = getAuthHeaders();
    console.log('Upload headers:', authHeaders);
    
    const response = await fetch('/api/upload/image', {
      method: 'POST',
      headers: authHeaders,
      body: formData
    });
    
    console.log('Upload response status:', response.status);
    const data = await response.json();
    console.log('Upload response data:', data);
    
    if (data.location) {
      if (editingPlatform.value) {
        editingPlatform.value.image_path = data.location;
      } else {
        newPlatform.value.image_path = data.location;
      }
    } else if (data.error) {
      platformFileUploadError.value = '上传失败: ' + data.error;
    } else {
      platformFileUploadError.value = '上传失败: 未知错误';
    }
  } catch (error) {
    platformFileUploadError.value = '上传失败: ' + error.message;
    console.error('Error uploading platform image:', error);
  } finally {
    platformFileUploadLoading.value = false;
  }
}

// 添加业务平台
async function addBusinessPlatform() {
  if (!newPlatform.value.name || !newPlatform.value.url) {
    platformError.value = '请输入平台名称和地址';
    return;
  }
  
  try {
    platformLoading.value = true;
    platformError.value = '';
    
    const response = await fetch('/api/business-platforms', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(newPlatform.value)
    });
    
    const data = await response.json();
    if (data.id) {
      businessPlatforms.value.push(data);
      showAddPlatformForm.value = false;
      newPlatform.value = {
        name: '',
        url: '',
        image_path: ''
      };
    } else if (data.error) {
      platformError.value = data.error;
    }
  } catch (error) {
    platformError.value = '添加失败: ' + error.message;
    console.error('Error adding business platform:', error);
  } finally {
    platformLoading.value = false;
  }
}

// 编辑业务平台
async function updateBusinessPlatform() {
  if (!editingPlatform.value.name || !editingPlatform.value.url) {
    platformError.value = '请输入平台名称和地址';
    return;
  }
  
  try {
    platformLoading.value = true;
    platformError.value = '';
    
    const response = await fetch(`/api/business-platforms/${editingPlatform.value.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(editingPlatform.value)
    });
    
    const data = await response.json();
    if (data.id) {
      const index = businessPlatforms.value.findIndex(p => p.id === data.id);
      if (index !== -1) {
        businessPlatforms.value[index] = data;
      }
      editingPlatform.value = null;
    } else if (data.error) {
      platformError.value = data.error;
    }
  } catch (error) {
    platformError.value = '更新失败: ' + error.message;
    console.error('Error updating business platform:', error);
  } finally {
    platformLoading.value = false;
  }
}

// 删除业务平台
async function deleteBusinessPlatform(platformId) {
  if (!confirm('确定要删除这个业务平台吗？')) return;
  
  try {
    platformLoading.value = true;
    platformError.value = '';
    
    const response = await fetch(`/api/business-platforms/${platformId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    if (data.message) {
      businessPlatforms.value = businessPlatforms.value.filter(p => p.id !== platformId);
    } else if (data.error) {
      platformError.value = data.error;
    }
  } catch (error) {
    platformError.value = '删除失败: ' + error.message;
    console.error('Error deleting business platform:', error);
  } finally {
    platformLoading.value = false;
  }
}

// 开始编辑业务平台
function startEditPlatform(platform) {
  editingPlatform.value = { ...platform };
}

// 取消编辑
function cancelEditPlatform() {
  editingPlatform.value = null;
}

// 取消添加
function cancelAddPlatform() {
  showAddPlatformForm.value = false;
  newPlatform.value = {
    name: '',
    url: '',
    image_path: ''
  };
}

// 测试函数，用于调试栏目名称显示问题
function testCategoryName() {
  console.log('cmsCategories:', cmsCategories.value);
  console.log('测试栏目ID 2:', getCategoryName(2));
  console.log('测试栏目ID "2":', getCategoryName('2'));
}

// 监听栏目名称变化，自动生成slug
watch(
  () => newCategory.value.name,
  (newName) => {
    console.log('栏目名称变化:', newName);
    console.log('editingCategory.value:', editingCategory.value);
    console.log('条件判断:', newName && !editingCategory.value);
    if (newName && !editingCategory.value) {
      console.log('生成slug:', generateSlug(newName));
      newCategory.value.slug = generateSlug(newName);
    }
  },
  { immediate: false }
);

// 监听文章标题变化，自动生成slug
watch(
  () => newArticle.value.title,
  (newTitle) => {
    console.log('文章标题变化:', newTitle);
    console.log('editingArticle.value:', editingArticle.value);
    console.log('条件判断:', newTitle && !editingArticle.value);
    if (newTitle && !editingArticle.value) {
      console.log('生成slug:', generateSlug(newTitle));
      newArticle.value.slug = generateSlug(newTitle);
    }
  },
  { immediate: false }
);

// 获取数据库表
async function fetchTables() {
  try {
    const token = localStorage.getItem('token');
    if (!token) return;
    
    // 确保表格可见性配置已经加载
    initTableVisibility();
    console.log('当前表格可见性配置:', tableVisibility.value);
    
    const response = await fetch('/api/tables', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.tables) {
      // 过滤掉系统表，只显示用户上传的表
      const systemTables = ['users', 'permissions'];
      let filteredTables = data.tables.filter(table => !systemTables.includes(table));
      
      // 应用表格可见性过滤
      console.log('原始数据表（过滤系统表后）:', filteredTables);
      
      // 使用当前的表格可见性配置进行过滤
      const finalTables = filteredTables.filter(table => {
        // 只有在配置中明确设置为true的表格才显示
        const isVisible = tableVisibility.value[table] === true;
        console.log(`表格 ${table} 可见性: ${isVisible}`);
        return isVisible;
      });
      
      console.log('过滤后的数据表:', finalTables);
      
      tables.value = finalTables;
      console.log('最终显示的数据表:', tables.value);
    }
  } catch (error) {
    console.error('Error fetching tables:', error);
  }
}

// 处理文件选择
function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    selectedFile.value = file;
  }
}

// 处理文件上传
async function uploadFile() {
  if (!selectedFile.value) {
    message.value = '请先选择文件';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    message.value = '请先登录';
    return;
  }

  const formData = new FormData();
  formData.append('file', selectedFile.value);

  try {
    loading.value = true;
    message.value = '上传中...';
    const response = await fetch('/api/upload', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    const data = await response.json();
    if (data.message) {
      message.value = data.message;
      // 重新获取表列表
      await fetchTables();
    } else if (data.error) {
      message.value = 'Error: ' + data.error;
    }
  } catch (error) {
    message.value = 'Error uploading file: ' + error.message;
    console.error('Error uploading file:', error);
  } finally {
    loading.value = false;
  }
}

// 开始分析
async function startAnalysis() {
  if (!selectedTable.value || !selectedAnalysisType.value) {
    analysisMessage.value = '请选择表和分析类型';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    analysisMessage.value = '请先登录';
    return;
  }

  try {
    loading.value = true;
    resetAnalysisSteps();
    analysisMessage.value = '分析中...';
    console.log('开始分析，表名:', selectedTable.value, '分析类型:', selectedAnalysisType.value);

    // 步骤1: 读取数据
    updateStepStatus(0, 'active');
    await new Promise(resolve => setTimeout(resolve, 500)); // 模拟处理时间

    // 步骤2: 处理时间数据
    updateStepStatus(1, 'active');

    // 步骤3: 调用大模型分析
    updateStepStatus(2, 'active');

    // 添加超时控制 (300秒)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          table_name: selectedTable.value,
          analysis_type: selectedAnalysisType.value
        }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      console.log('分析请求响应状态:', response.status);

      // 步骤4: 生成分析报告
      updateStepStatus(3, 'active');

      const data = await response.json();
      console.log('分析请求响应数据:', data);

      if (data.error) {
        analysisMessage.value = 'Error: ' + data.error;
        console.error('分析错误:', data.error);
        resetAnalysisSteps();
      } else {
        analysisResult.value = data;
        console.log('分析结果已保存:', analysisResult.value);

        // 步骤5: 分析完成
        updateStepStatus(4, 'completed');
        analysisMessage.value = '分析完成';
        console.log('分析完成，结果已显示在当前页面');
        console.log('当前模块:', activeModule.value);
      }
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        analysisMessage.value = '请求超时，请稍后重试';
        console.error('请求超时');
      } else {
        throw fetchError;
      }
      resetAnalysisSteps();
    }
  } catch (error) {
    analysisMessage.value = 'Error analyzing data: ' + error.message;
    console.error('Error analyzing data:', error);
    resetAnalysisSteps();
  } finally {
    loading.value = false;
    console.log('分析完成，加载状态已重置');
  }
}

// 数据分析（新版）开始分析
async function startAnalysisV2() {
  if (!selectedTableV2.value || !analysisPrompt.value) {
    analysisV2Error.value = '请选择数据表并输入分析提示词';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    analysisV2Error.value = '请先登录';
    return;
  }

  try {
    analysisV2Loading.value = true;
    analysisV2Error.value = '';
    analysisV2Message.value = '分析中...';
    analysisV2Result.value = null;

    // 添加超时控制 (300秒)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000);

    try {
      const response = await fetch('/api/analyze-v2', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          table_name: selectedTableV2.value,
          prompt: analysisPrompt.value,
          model: selectedModel.value
        }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      if (data.error) {
        analysisV2Error.value = 'Error: ' + data.error;
      } else {
        analysisV2Result.value = data;
        analysisV2Message.value = '分析完成';

        // 等待DOM更新后渲染图表
        setTimeout(() => {
          renderAnalysisV2Charts();
        }, 100);
      }
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError.name === 'AbortError') {
        analysisV2Error.value = '请求超时，请稍后重试';
        console.error('请求超时');
      } else {
        throw fetchError;
      }
    }
  } catch (error) {
    analysisV2Error.value = 'Error analyzing data: ' + error.message;
    console.error('Error analyzing data:', error);
  } finally {
    analysisV2Loading.value = false;
  }
}

// 渲染数据分析（新版）图表
function renderAnalysisV2Charts() {
  if (!analysisV2Result.value || !analysisV2Result.value.charts) return;
  
  analysisV2Result.value.charts.forEach((chart, index) => {
    if (chart.type === 'image') return;
    
    const chartEl = chartRefs.value[index];
    if (!chartEl) return;
    
    try {
      const chartInstance = echarts.init(chartEl);
      chartInstance.setOption(chart.data);
      
      // 响应窗口大小变化
      window.addEventListener('resize', () => {
        chartInstance.resize();
      });
    } catch (error) {
      console.error('Error rendering chart:', error);
    }
  });
}

// 格式化分析报告内容
function formatAnalysisReport(content) {
  if (!content) return '';
  
  let formatted = content;
  
  // 删除段落中的多余空格
  formatted = formatted.replace(/[ \t]+/g, ' ');
  formatted = formatted.replace(/^[ \t]+/gm, '');
  formatted = formatted.replace(/[ \t]+$/gm, '');
  
  // 处理换行
  formatted = formatted.replace(/\n/g, '<br>');
  
  // 处理标题（#开头）
  formatted = formatted.replace(/^### (.*)$/gm, '<h3 style="color: white; font-size: 16px; font-weight: 700; margin-top: 16px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.2);">$1</h3>');
  formatted = formatted.replace(/^## (.*)$/gm, '<h2 style="color: white; font-size: 17px; font-weight: 700; margin-top: 18px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 2px solid #4facfe;">$1</h2>');
  formatted = formatted.replace(/^# (.*)$/gm, '<h1 style="color: white; font-size: 18px; font-weight: 800; margin-top: 20px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 2px solid #4facfe;">$1</h1>');
  
  // 处理粗体（**内容**）
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong style="color: white; font-weight: 700;">$1</strong>');
  
  // 处理斜体（*内容*）
  formatted = formatted.replace(/\*(.*?)\*/g, '<em style="color: rgba(255, 255, 255, 0.9); font-style: italic;">$1</em>');
  
  // 处理列表项（- 开头）
  formatted = formatted.replace(/^- (.*)$/gm, '<li style="margin: 4px 0; padding-left: 8px; color: rgba(255, 255, 255, 0.9); border-left: 2px solid #4facfe; padding-left: 10px;">$1</li>');
  
  // 处理列表容器
  formatted = formatted.replace(/(<li.*<\/li>)/s, '<ul style="list-style: none; padding: 0; margin: 10px 0;">$1</ul>');
  
  // 处理分隔线（---）
  formatted = formatted.replace(/^---$/gm, '<hr style="border: none; border-top: 1px solid rgba(255, 255, 255, 0.2); margin: 16px 0;">');
  
  // 处理代码块（```开头结尾）
  formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre style="background: rgba(0, 0, 0, 0.3); color: rgba(255, 255, 255, 0.9); padding: 12px; border-radius: 6px; overflow-x: auto; font-family: monospace; font-size: 13px; margin: 12px 0;"><code>$1</code></pre>');
  
  return formatted;
}

// 复制报告
function copyReport() {
  if (!analysisV2Result.value?.report) return;
  
  // 移除HTML标签，只保留纯文本
  let text = analysisV2Result.value.report;
  text = text.replace(/<[^>]*>/g, '');
  text = text.replace(/&nbsp;/g, ' ');
  
  navigator.clipboard.writeText(text).then(() => {
    analysisV2Message.value = '报告已复制到剪贴板！';
    setTimeout(() => {
      analysisV2Message.value = '';
    }, 2000);
  }).catch(err => {
    analysisV2Error.value = '复制失败，请手动复制';
    console.error('复制失败:', err);
  });
}

// 开始考核计算
async function startAssessment() {
  if (!selectedDepartment.value || !selectedAssessmentTable.value) {
    assessmentMessage.value = '请选择部门和数据表';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    assessmentMessage.value = '请先登录';
    return;
  }

  try {
    loading.value = true;
    assessmentMessage.value = '计算中...';
    
    const response = await fetch('/api/assess', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        table_name: selectedAssessmentTable.value,
        department: selectedDepartment.value
      })
    });
    
    const data = await response.json();
    
    if (data.error) {
      assessmentMessage.value = 'Error: ' + data.error;
    } else {
      assessmentResult.value = data;
      assessmentMessage.value = '计算完成';
    }
  } catch (error) {
    assessmentMessage.value = 'Error calculating assessment: ' + error.message;
    console.error('Error calculating assessment:', error);
  } finally {
    loading.value = false;
  }
}

// 开始新版考核计算
async function startAssessmentV2() {
  if (!selectedDepartmentV2.value || !selectedAssessmentTableV2.value) {
    assessmentMessageV2.value = '请选择部门和数据表';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    assessmentMessageV2.value = '请先登录';
    return;
  }

  try {
    loading.value = true;
    assessmentMessageV2.value = '计算中...';
    
    const response = await fetch('/api/assess/v2', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        table_name: selectedAssessmentTableV2.value,
        department: selectedDepartmentV2.value,
        coefficients: assessmentCoefficients.value
      })
    });
    
    const data = await response.json();
    
    if (data.error) {
      assessmentMessageV2.value = 'Error: ' + data.error;
    } else {
      assessmentResultV2.value = data;
      assessmentMessageV2.value = '计算完成';
    }
  } catch (error) {
    assessmentMessageV2.value = 'Error calculating assessment: ' + error.message;
    console.error('Error calculating assessment:', error);
  } finally {
    loading.value = false;
  }
}

// 切换模块
function switchModule(module) {
  activeModule.value = module;
  // 切换到数据分析模块时重新获取表列表（应用可见性过滤）
  if (module === 'analysis') {
    console.log('切换到数据分析模块，获取可见的数据表');
    fetchTables();
  }
  // 切换到AI应用模块时重新获取表列表（应用可见性过滤）
  if (module === 'ai-apps') {
    console.log('切换到AI应用模块，获取可见的数据表');
    fetchTables();
  }
  // 切换到考核计分模块时也需要获取表列表（应用可见性过滤）
  if (module === 'assessment') {
    console.log('切换到考核计分模块，获取可见的数据表');
    fetchTables();
  }
  // 切换到管理员模块时获取用户列表和CMS数据
  if (module === 'admin' && userInfo.value && userInfo.value.role === 'admin') {
    fetchUsers();
    fetchCMSCategories();
  }
  // 切换到首页时重新获取CMS数据
  if (module === 'home') {
    fetchCMSCategories();
  }
  // 切换到业务平台模块时获取业务平台数据
  if (module === 'business') {
    fetchDisplayBusinessPlatforms();
  }
  // 切换到地图服务模块时初始化地图
  if (module === 'map') {
    nextTick(() => {
      initMap();
    });
  }
}

// 初始化地图
function initMap() {
  if (!window.AMap) {
    mapError.value = '高德地图加载失败';
    return;
  }
  
  mapLoading.value = true;
  mapError.value = '';
  
  try {
    // 初始化地图实例
    mapInstance.value = new window.AMap.Map('map-container', {
      zoom: 13,
      center: [110.976935, 35.06161], // 指定坐标
      resizeEnable: true,
      mapStyle: 'amap://styles/light'
    });
    
    // 高德地图2.0版本已移除内置控件，使用地图默认控件
    // 如需添加控件，请参考高德地图2.0文档使用新控件库
    
    // 添加指定坐标标记
    const marker = new window.AMap.Marker({
      position: [110.976935, 35.06161],
      title: '指定位置',
      map: mapInstance.value
    });
    
    // 添加信息窗口
    const infoWindow = new window.AMap.InfoWindow({
      content: '<div style="padding: 10px;"><h3>指定位置</h3><p>坐标: 110.976935, 35.06161</p></div>',
      offset: new window.AMap.Pixel(0, -30)
    });
    
    marker.on('click', function() {
      infoWindow.open(mapInstance.value, marker.getPosition());
    });
    
    // 模拟案件数据（后续可从API获取）
    loadMockCaseData();
    
  } catch (error) {
    console.error('地图初始化失败:', error);
    mapError.value = '地图初始化失败: ' + error.message;
  } finally {
    mapLoading.value = false;
  }
}

// 加载模拟案件数据
function loadMockCaseData() {
  // 模拟运城市内的案件数据
  casesData.value = [
    { id: 1, name: '占道经营', location: [110.98, 35.04], type: '市容市貌' },
    { id: 2, name: '乱停乱放', location: [111.01, 35.03], type: '交通秩序' },
    { id: 3, name: '垃圾堆积', location: [110.97, 35.02], type: '环境卫生' },
    { id: 4, name: '违规搭建', location: [111.02, 35.05], type: '违法建设' },
    { id: 5, name: '噪音扰民', location: [110.99, 35.01], type: '环境噪音' }
  ];
  
  // 在地图上标记案件
  markCasesOnMap();
}

// 在地图上标记案件
function markCasesOnMap() {
  if (!mapInstance.value || casesData.value.length === 0) return;
  
  casesData.value.forEach(caseItem => {
    const marker = new window.AMap.Marker({
      position: caseItem.location,
      title: caseItem.name,
      map: mapInstance.value,
      icon: new window.AMap.Icon({
        size: new window.AMap.Size(30, 30),
        image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
        imageSize: new window.AMap.Size(30, 30)
      })
    });
    
    // 添加案件信息窗口
    const infoWindow = new window.AMap.InfoWindow({
      content: `
        <div style="padding: 10px;">
          <h4>${caseItem.name}</h4>
          <p>类型: ${caseItem.type}</p>
          <p>案件ID: ${caseItem.id}</p>
        </div>
      `,
      offset: new window.AMap.Pixel(0, -30)
    });
    
    marker.on('click', function() {
      infoWindow.open(mapInstance.value, marker.getPosition());
    });
  });
  
  // 尝试添加热力图（如果数据足够）
  try {
    if (window.AMap.Heatmap) {
      const heatmap = new window.AMap.Heatmap(mapInstance.value, {
        radius: 25,
        opacity: [0, 0.8]
      });
      
      const heatData = casesData.value.map(item => ({
        lng: item.location[0],
        lat: item.location[1],
        count: Math.random() * 10 + 1
      }));
      
      heatmap.setDataSet({
        data: heatData,
        max: 10
      });
    }
  } catch (error) {
    console.log('热力图加载失败（可选功能）:', error);
  }
}

// 登录函数
async function login() {
  if (!loginForm.value.username || !loginForm.value.password) {
    loginError.value = '请输入用户名和密码';
    return;
  }
  
  try {
    loginLoading.value = true;
    loginError.value = '';
    
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(loginForm.value)
    });
    
    const data = await response.json();
    
    if (data.error) {
      loginError.value = data.error;
    } else {
      // 保存token到本地存储
      localStorage.setItem('token', data.token);
      localStorage.setItem('userInfo', JSON.stringify(data));
      
      // 更新登录状态
      userInfo.value = data;
      isLoggedIn.value = true;
      showLogin.value = false;
      
      // 切换到首页
      activeModule.value = 'home';
    }
  } catch (error) {
    loginError.value = '登录失败，请稍后重试';
    console.error('Login error:', error);
  } finally {
    loginLoading.value = false;
  }
}

// 登出函数
function logout() {
  // 清除本地存储
  localStorage.removeItem('token');
  localStorage.removeItem('userInfo');
  
  // 更新登录状态
  isLoggedIn.value = false;
  userInfo.value = null;
  showLogin.value = true;
  
  // 切换到登录页面
  activeModule.value = 'home';
}

// 检查token有效性
async function checkTokenValidity() {
  try {
    const token = localStorage.getItem('token');
    if (!token) return;
    
    const response = await fetch('/api/user', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      userInfo.value = data;
      isLoggedIn.value = true;
      showLogin.value = false;
    } else {
      // token无效，清除本地存储
      localStorage.removeItem('token');
      localStorage.removeItem('userInfo');
      userInfo.value = null;
      isLoggedIn.value = false;
      showLogin.value = true;
    }
  } catch (error) {
    console.error('Token check error:', error);
    // 网络错误，清除本地存储
    localStorage.removeItem('token');
    localStorage.removeItem('userInfo');
    userInfo.value = null;
    isLoggedIn.value = false;
    showLogin.value = true;
  }
}

// 获取请求头，包含token
function getAuthHeaders() {
  const token = localStorage.getItem('token');
  console.log('Token from localStorage:', token ? 'Found' : 'Not found');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// 获取用户列表
async function fetchUsers() {
  try {
    const token = localStorage.getItem('token');
    if (!token) return;
    
    const response = await fetch('/api/users', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.users) {
      users.value = data.users;
    }
  } catch (error) {
    console.error('Error fetching users:', error);
  }
}

// 添加用户
async function saveUser() {
  if (!newUser.value.username || !newUser.value.password) {
    adminError.value = '请输入用户名和密码';
    return;
  }
  
  const token = localStorage.getItem('token');
  if (!token) {
    adminError.value = '请先登录';
    return;
  }
  
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    let response;
    if (editingUser.value) {
      // 编辑用户
      response = await fetch(`/api/users/${editingUser.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(newUser.value)
      });
    } else {
      // 添加用户
      response = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(newUser.value)
      });
    }
    
    const data = await response.json();
    if (data.error) {
      adminError.value = data.error;
    } else {
      // 重新获取用户列表
      await fetchUsers();
      // 关闭弹窗
      closeAddUserForm();
    }
  } catch (error) {
    adminError.value = '操作失败，请稍后重试';
    console.error('Save user error:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 编辑用户
function editUser(user) {
  editingUser.value = user;
  newUser.value = {
    username: user.username,
    password: '',
    role: user.role
  };
  showAddUserForm.value = true;
}

// 删除用户
async function deleteUser(userId) {
  if (userId === 1) {
    adminError.value = '不能删除管理员用户';
    return;
  }
  
  if (!confirm('确定要删除这个用户吗？')) {
    return;
  }
  
  const token = localStorage.getItem('token');
  if (!token) {
    adminError.value = '请先登录';
    return;
  }
  
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    const response = await fetch(`/api/users/${userId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    if (data.error) {
      adminError.value = data.error;
    } else {
      // 重新获取用户列表
      await fetchUsers();
    }
  } catch (error) {
    adminError.value = '删除失败，请稍后重试';
    console.error('Delete user error:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 关闭添加用户弹窗
function closeAddUserForm() {
  showAddUserForm.value = false;
  editingUser.value = null;
  newUser.value = {
    username: '',
    password: '',
    role: 'user'
  };
  adminError.value = '';
}

// 案件抽查模块方法
function handleSpotcheckFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    // 验证文件类型
    const allowedTypes = ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    const allowedExtensions = ['.docx', '.xlsx'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
      spotcheckError.value = '只支持docx和xlsx文件';
      spotcheckFile.value = null;
      return;
    }
    
    spotcheckFile.value = file;
    spotcheckError.value = '';
  }
}

async function uploadAndAnalyzeSpotcheck() {
  if (!spotcheckFile.value) {
    spotcheckError.value = '请先选择文件';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    spotcheckError.value = '请先登录';
    return;
  }

  const formData = new FormData();
  formData.append('file', spotcheckFile.value);

  try {
    spotcheckLoading.value = true;
    spotcheckMessage.value = '上传中...';
    spotcheckError.value = '';
    spotcheckResult.value = null;
    
    // 添加上传进度提示
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      spotcheckError.value = '上传超时，请稍后重试';
      spotcheckLoading.value = false;
    }, 60000); // 60秒超时
    
    const response = await fetch('/api/spotcheck', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      throw new Error(`服务器响应失败: ${response.status}`);
    }
    
    spotcheckMessage.value = '分析中...';
    const data = await response.json();
    
    if (data.error) {
      spotcheckError.value = '错误: ' + data.error;
    } else {
      spotcheckResult.value = data;
      spotcheckMessage.value = '分析完成';
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      spotcheckError.value = '上传超时，请稍后重试';
    } else {
      spotcheckError.value = '错误: ' + error.message;
    }
    console.error('Error uploading spotcheck file:', error);
  } finally {
    spotcheckLoading.value = false;
  }
}

function clearSpotcheck() {
  spotcheckFile.value = null;
  spotcheckResult.value = null;
  spotcheckMessage.value = '';
  spotcheckError.value = '';
  // 重置文件输入
  const fileInput = document.getElementById('spotcheck-file-input');
  if (fileInput) {
    fileInput.value = '';
  }
}

// 编辑用户权限
function editUserPermissions(user) {
  // 添加调试代码
  console.log('编辑用户权限，用户对象:', user);
  console.log('编辑用户权限，user.permissions:', user.permissions);
  console.log('编辑用户权限，user.permissions是否存在:', !!user.permissions);
  
  editingPermissionsUser.value = user;
  editingPermissions.value = {
    assessment: Boolean(user.permissions?.assessment) || false,
    data_analysis: Boolean(user.permissions?.data_analysis) || false,
    spotcheck: Boolean(user.permissions?.spotcheck) || false,
    map: Boolean(user.permissions?.map) || false,
    huiwentai: Boolean(user.permissions?.huiwentai) || false,
    cases: Boolean(user.permissions?.cases) || false,
    business: Boolean(user.permissions?.business) || false
  };
  
  // 打印设置后的权限值
  console.log('编辑用户权限，设置后的editingPermissions.value:', editingPermissions.value);
  
  showEditPermissionsForm.value = true;
}

// 保存用户权限
async function saveUserPermissions() {
  if (!editingPermissionsUser.value) return;
  
  const token = localStorage.getItem('token');
  if (!token) {
    adminError.value = '请先登录';
    return;
  }
  
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    const response = await fetch(`/api/users/${editingPermissionsUser.value.id}/permissions`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify(editingPermissions.value)
    });
    
    const data = await response.json();
    if (data.error) {
      adminError.value = data.error;
    } else {
      // 重新获取用户列表
      await fetchUsers();
      // 关闭弹窗
      closeEditPermissionsForm();
    }
  } catch (error) {
    adminError.value = '操作失败，请稍后重试';
    console.error('Save permissions error:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 获取数据表列表（管理用）
async function fetchTablesForManagement() {
  const token = localStorage.getItem('token');
  if (!token) {
    adminError.value = '请先登录';
    return;
  }
  
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    const response = await fetch('/api/tables', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.tables) {
      tables.value = data.tables;
      // 初始化表格可见性状态
      initTableVisibility();
      
      // 确保所有数据表都有可见性设置
      const currentVisibility = { ...tableVisibility.value };
      data.tables.forEach(table => {
        if (currentVisibility[table] === undefined) {
          currentVisibility[table] = true; // 默认所有表都可见
        }
      });
      tableVisibility.value = currentVisibility;
    }
  } catch (error) {
    adminError.value = '获取数据表失败，请稍后重试';
    console.error('Error fetching tables:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 保存表格可见性配置
async function saveTableVisibility() {
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    // 保存到本地存储
    const visibilityConfig = JSON.stringify(tableVisibility.value);
    localStorage.setItem('tableVisibility', visibilityConfig);
    
    // 验证保存是否成功
    const savedConfig = localStorage.getItem('tableVisibility');
    if (savedConfig) {
      console.log('表格可见性配置已保存:', JSON.parse(savedConfig));
    }
    
    // 显示保存成功消息
    adminError.value = '配置保存成功！';
    
    // 3秒后清除消息
    setTimeout(() => {
      adminError.value = '';
    }, 3000);
  } catch (error) {
    adminError.value = '保存配置失败，请稍后重试';
    console.error('Error saving table visibility:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 删除数据表
async function deleteTable(tableName) {
  if (!confirm(`确定要删除数据表 ${tableName} 吗？此操作不可恢复！`)) {
    return;
  }
  
  const token = localStorage.getItem('token');
  if (!token) {
    adminError.value = '请先登录';
    return;
  }
  
  try {
    adminLoading.value = true;
    adminError.value = '';
    
    const response = await fetch(`/api/tables/${tableName}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    if (data.error) {
      adminError.value = data.error;
    } else {
      // 重新获取数据表列表
      await fetchTablesForManagement();
      adminError.value = `数据表 ${tableName} 删除成功！`;
    }
  } catch (error) {
    adminError.value = '删除数据表失败，请稍后重试';
    console.error('Error deleting table:', error);
  } finally {
    adminLoading.value = false;
  }
}

// 添加新用户
function addNewUser() {
  editingUser.value = null;
  newUser.value = {
    username: '',
    password: '',
    role: 'user'
  };
  showAddUserForm.value = true;
}

// 关闭权限编辑弹窗
function closeEditPermissionsForm() {
  showEditPermissionsForm.value = false;
  editingPermissionsUser.value = null;
  editingPermissions.value = {
    assessment: false,
    data_analysis: false,
    spotcheck: false,
    map: false,
    huiwentai: false,
    cases: false,
    business: false
  };
  adminError.value = '';
}

// CMS相关方法

// 获取CMS栏目
async function fetchCMSCategories() {
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    
    const response = await fetch('/api/categories');
    const data = await response.json();
    
    if (data.categories) {
      cmsCategories.value = data.categories;
      // 默认选择"全部"文章
      selectedCategory.value = allCategoryOption;
      await fetchCMSArticles('all', 1);
      // 获取所有栏目的文章，确保首页能显示所有栏目
      await fetchAllCMSArticles();
    }
  } catch (error) {
    cmsError.value = '获取栏目失败，请稍后重试';
    console.error('Error fetching CMS categories:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 获取CMS文章
async function fetchCMSArticles(categoryId, page = 1) {
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    cmsArticlesPage.value = page;
    
    console.log('=== 调试信息：fetchCMSArticles 开始 ===');
    console.log('categoryId:', categoryId);
    
    let url;
    if (categoryId === 'all' || !categoryId) {
      // 获取所有文章
      url = `/api/articles?include_drafts=true&page=${page}&per_page=${cmsArticlesPerPage.value}`;
    } else {
      // 获取指定栏目的文章
      url = `/api/articles/category/${categoryId}?include_drafts=true&page=${page}&per_page=${cmsArticlesPerPage.value}`;
    }
    
    console.log('请求URL:', url);
    
    const response = await fetch(url);
    const data = await response.json();
    
    console.log('后端返回数据:', data);
    
    if (data.articles) {
      cmsArticles.value = data.articles;
      cmsArticlesTotal.value = data.total || 0;
      cmsArticlesPages.value = data.pages || 0;
      
      console.log('文章总数:', cmsArticlesTotal.value);
      console.log('总页数:', cmsArticlesPages.value);
      console.log('当前页:', cmsArticlesPage.value);
    }
    console.log('=== 调试信息：fetchCMSArticles 结束 ===');
  } catch (error) {
    cmsError.value = '获取文章失败，请稍后重试';
    console.error('Error fetching CMS articles:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 获取所有CMS文章
async function fetchAllCMSArticles() {
  try {
    // 获取大量文章，确保首页能显示所有栏目的文章
    const response = await fetch('/api/articles?include_drafts=true&per_page=1000');
    const data = await response.json();
    
    if (data.articles) {
      allHomeArticles.value = data.articles;
    }
  } catch (error) {
    console.error('Error fetching all CMS articles:', error);
  }
}

// 切换CMS栏目
async function switchCMSCategory(category) {
  if (category === 'all' || (category && category.id === 'all')) {
    selectedCategory.value = allCategoryOption;
    cmsArticlesPage.value = 1;
    await fetchCMSArticles('all', 1);
  } else {
    selectedCategory.value = category;
    cmsArticlesPage.value = 1;
    await fetchCMSArticles(category.id, 1);
  }
}

// 获取栏目名称
function getCategoryName(categoryId) {
  // 确保类型匹配
  const idToFind = Number(categoryId);
  const category = cmsCategories.value.find(cat => Number(cat.id) === idToFind);
  return category ? category.name : '未知栏目';
}

// 根据栏目ID获取文章（首页用）
function getCategoryArticles(categoryId) {
  // 过滤出指定栏目的文章，按时间排序（最新的在前），只返回前5条
  return allHomeArticles.value
    .filter(article => Number(article.category_id) === Number(categoryId))
    .sort((a, b) => {
      const dateA = new Date(a.published_at || a.created_at);
      const dateB = new Date(b.published_at || b.created_at);
      return dateB - dateA; // 降序排序
    })
    .slice(0, 5); // 只返回前5条
}

// 生成页码列表
function getPageNumbers() {
  const pages = [];
  const totalPages = cmsArticlesPages.value;
  const currentPage = cmsArticlesPage.value;
  
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    if (currentPage <= 4) {
      for (let i = 1; i <= 5; i++) {
        pages.push(i);
      }
      pages.push('...');
      pages.push(totalPages);
    } else if (currentPage >= totalPages - 3) {
      pages.push(1);
      pages.push('...');
      for (let i = totalPages - 4; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);
      pages.push('...');
      for (let i = currentPage - 1; i <= currentPage + 1; i++) {
        pages.push(i);
      }
      pages.push('...');
      pages.push(totalPages);
    }
  }
  
  return pages;
}

// 添加/编辑栏目
async function saveCategory() {
  if (!newCategory.value.name) {
    cmsFormError.value = '名称不能为空';
    return;
  }
  
  try {
    cmsLoading.value = true;
    cmsFormError.value = '';
    
    const token = localStorage.getItem('token');
    if (!token) {
      cmsFormError.value = '请先登录';
      return;
    }
    
    let response;
    if (editingCategory.value) {
      // 编辑栏目
      response = await fetch(`/api/categories/${editingCategory.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newCategory.value)
      });
    } else {
      // 添加栏目
      response = await fetch('/api/categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newCategory.value)
      });
    }
    
    const data = await response.json();
    if (data.error) {
      cmsFormError.value = data.error;
    } else {
      // 重新获取栏目列表
      await fetchCMSCategories();
      closeCategoryForm();
    }
  } catch (error) {
    cmsFormError.value = '操作失败，请稍后重试';
    console.error('Error saving category:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 删除栏目
async function deleteCategory(categoryId) {
  if (!confirm('确定要删除这个栏目吗？如果该栏目下有文章，将无法删除。')) {
    return;
  }
  
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    
    const token = localStorage.getItem('token');
    if (!token) {
      cmsError.value = '请先登录';
      return;
    }
    
    const response = await fetch(`/api/categories/${categoryId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    if (data.error) {
      cmsError.value = data.error;
    } else {
      // 重新获取栏目列表
      await fetchCMSCategories();
    }
  } catch (error) {
    cmsError.value = '删除失败，请稍后重试';
    console.error('Error deleting category:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 编辑栏目
function editCategory(category) {
  editingCategory.value = category;
  newCategory.value = {
    name: category.name,
    slug: category.slug,
    description: category.description,
    order: category.order
  };
  showAddCategoryForm.value = true;
}

// 关闭栏目表单
function closeCategoryForm() {
  showAddCategoryForm.value = false;
  editingCategory.value = null;
  newCategory.value = {
    name: '',
    slug: '',
    description: '',
    order: 0
  };
  cmsFormError.value = '';
}

// 添加/编辑文章
async function saveArticle() {
  if (!newArticle.value.title || !newArticle.value.content) {
    cmsFormError.value = '标题和内容不能为空';
    return;
  }
  
  if (!newArticle.value.category_id) {
    cmsFormError.value = '请选择栏目';
    return;
  }
  
  try {
    cmsLoading.value = true;
    cmsFormError.value = '';
    
    const token = localStorage.getItem('token');
    if (!token) {
      cmsFormError.value = '请先登录';
      return;
    }
    
    let response;
    if (editingArticle.value) {
      // 编辑文章
      response = await fetch(`/api/articles/${editingArticle.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newArticle.value)
      });
    } else {
      // 添加文章
      response = await fetch('/api/articles', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newArticle.value)
      });
    }
    
    const data = await response.json();
    if (data.error) {
      cmsFormError.value = data.error;
    } else {
      // 重新获取栏目列表和文章列表
      await fetchCMSCategories();
      await fetchCMSArticles(selectedCategory.value?.id || cmsCategories.value[0]?.id, cmsArticlesPage.value);
      closeArticleForm();
    }
  } catch (error) {
    cmsFormError.value = '操作失败，请稍后重试';
    console.error('Error saving article:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 删除文章
async function deleteArticle(articleId) {
  if (!confirm('确定要删除这篇文章吗？')) {
    return;
  }
  
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    
    const token = localStorage.getItem('token');
    if (!token) {
      cmsError.value = '请先登录';
      return;
    }
    
    const response = await fetch(`/api/articles/${articleId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    if (data.error) {
      cmsError.value = data.error;
    } else {
      // 重新获取文章列表 - 检查当前页是否还有内容
      let newPage = cmsArticlesPage.value;
      // 如果当前页只剩这一篇文章，删除后回到上一页
      if (cmsArticles.value.length === 1 && newPage > 1) {
        newPage = newPage - 1;
      }
      await fetchCMSArticles(selectedCategory.value?.id || cmsCategories.value[0]?.id, newPage);
    }
  } catch (error) {
    cmsError.value = '删除失败，请稍后重试';
    console.error('Error deleting article:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 编辑文章
async function editArticle(article) {
  try {
    cmsLoading.value = true;
    // 获取完整的文章详情，包括content字段
    const response = await fetch(`/api/articles/${article.id}`);
    const articleDetail = await response.json();
    
    if (articleDetail.error) {
      cmsError.value = articleDetail.error;
      return;
    }
    
    editingArticle.value = articleDetail;
    newArticle.value = {
      title: articleDetail.title,
      slug: articleDetail.slug,
      content: articleDetail.content,
      summary: articleDetail.summary,
      category_id: articleDetail.category_id,
      status: 'published',
      file_path: articleDetail.file_path
    };
    showAddArticleForm.value = true;
  } catch (error) {
    cmsError.value = '获取文章详情失败，请稍后重试';
    console.error('Error fetching article detail for editing:', error);
  } finally {
    cmsLoading.value = false;
  }
}

// 关闭文章表单
function closeArticleForm() {
  showAddArticleForm.value = false;
  editingArticle.value = null;
  newArticle.value = {
    title: '',
    slug: '',
    content: '',
    summary: '',
    category_id: '',
    status: 'published',
    file_path: ''
  };
  cmsFormError.value = '';
  fileUploadError.value = '';
  fileUploadLoading.value = false;
}

// 状态管理：全部文章弹窗
const showAllArticlesModal = ref(false);
const allArticlesCategoryId = ref(null);
const allArticlesList = ref([]);
const allArticlesPage = ref(1);
const allArticlesPerPage = ref(10);
const allArticlesTotal = ref(0);
const allArticlesPages = ref(0);
const allArticlesLoading = ref(false);



// 获取全部文章分页数据
async function fetchAllArticles(categoryId, page = 1) {
  try {
    allArticlesLoading.value = true;
    allArticlesPage.value = page;
    
    console.log('=== 调试信息：fetchAllArticles 开始 ===');
    console.log('请求URL:', `/api/articles/category/${categoryId}?include_drafts=false&page=${page}&per_page=${allArticlesPerPage.value}`);
    
    const response = await fetch(`/api/articles/category/${categoryId}?include_drafts=false&page=${page}&per_page=${allArticlesPerPage.value}`);
    const data = await response.json();
    
    console.log('后端返回数据:', data);
    
    if (data.articles) {
      allArticlesList.value = data.articles;
      allArticlesTotal.value = data.total || 0;
      allArticlesPages.value = data.pages || 0;
      
      console.log('文章总数:', allArticlesTotal.value);
      console.log('总页数:', allArticlesPages.value);
      console.log('当前页:', allArticlesPage.value);
    }
    console.log('=== 调试信息：fetchAllArticles 结束 ===');
  } catch (error) {
    console.error('Error fetching all articles:', error);
  } finally {
    allArticlesLoading.value = false;
  }
}

// 显示全部文章弹窗
async function showAllArticles(categoryId) {
  allArticlesCategoryId.value = categoryId;
  allArticlesPage.value = 1;
  showAllArticlesModal.value = true;
  await fetchAllArticles(categoryId, 1);
}

// 关闭全部文章弹窗
function closeAllArticlesModal() {
  showAllArticlesModal.value = false;
  allArticlesCategoryId.value = null;
  allArticlesList.value = [];
  allArticlesPage.value = 1;
  allArticlesTotal.value = 0;
  allArticlesPages.value = 0;
}

// 生成全部文章页码列表
function getAllArticlesPageNumbers() {
  const pages = [];
  const totalPages = allArticlesPages.value;
  const currentPage = allArticlesPage.value;
  
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    if (currentPage <= 4) {
      for (let i = 1; i <= 5; i++) {
        pages.push(i);
      }
      pages.push('...');
      pages.push(totalPages);
    } else if (currentPage >= totalPages - 3) {
      pages.push(1);
      pages.push('...');
      for (let i = totalPages - 4; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);
      pages.push('...');
      for (let i = currentPage - 1; i <= currentPage + 1; i++) {
        pages.push(i);
      }
      pages.push('...');
      pages.push(totalPages);
    }
  }
  
  return pages;
}

// 生成slug函数
function generateSlug(title) {
  return title
    .toLowerCase()
    .replace(/\s+/g, '-') // 空格替换为连字符
    .replace(/[^\u4e00-\u9fa5a-z0-9-]/g, '') // 保留中文和字母数字连字符
    .replace(/-+/g, '-') // 多个连字符替换为单个
    .replace(/^-|-$/g, ''); // 移除首尾连字符
}



// 添加新栏目
function addNewCategory() {
  editingCategory.value = null;
  newCategory.value = {
    name: '',
    slug: '',
    description: '',
    order: 0
  };
  showAddCategoryForm.value = true;
}

// 添加新文章
function addNewArticle() {
  editingArticle.value = null;
  newArticle.value = {
    title: '',
    slug: '',
    content: '',
    summary: '',
    category_id: '',
    status: 'published'
  };
  showAddArticleForm.value = true;
}

// 获取文章详情
async function fetchArticleDetail(articleId) {
  try {
    articleDetailLoading.value = true;
    articleDetailError.value = '';
    
    const response = await fetch(`/api/articles/${articleId}`);
    const data = await response.json();
    
    if (data.error) {
      articleDetailError.value = data.error;
    } else {
      currentArticle.value = data;
      showArticleDetail.value = true;
    }
  } catch (error) {
    articleDetailError.value = '获取文章详情失败，请稍后重试';
    console.error('Error fetching article detail:', error);
  } finally {
    articleDetailLoading.value = false;
  }
}

// 关闭文章详情
function closeArticleDetail() {
  showArticleDetail.value = false;
  currentArticle.value = null;
  articleDetailError.value = '';
}

// 上传CMS文件
async function uploadCMSFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  // 检查文件类型
  const allowedExtensions = ['docx', 'pdf'];
  const fileExtension = file.name.split('.').pop().toLowerCase();
  if (!allowedExtensions.includes(fileExtension)) {
    fileUploadError.value = '只支持DOCX和PDF文件';
    return;
  }
  
  try {
    fileUploadLoading.value = true;
    fileUploadError.value = '';
    
    const formData = new FormData();
    formData.append('file', file);
    
    const token = localStorage.getItem('token');
    const response = await fetch('/api/upload/file', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });
    
    const data = await response.json();
    if (data.error) {
      fileUploadError.value = data.error;
    } else {
      newArticle.value.file_path = data.file_path;
      fileUploadError.value = '';
    }
  } catch (error) {
    fileUploadError.value = '文件上传失败，请稍后重试';
    console.error('Error uploading file:', error);
  } finally {
    fileUploadLoading.value = false;
  }
}

// 上传图片
async function uploadImage(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  // 检查文件类型
  const allowedExtensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
  const fileExtension = file.name.split('.').pop().toLowerCase();
  if (!allowedExtensions.includes(fileExtension)) {
    imageUploadError.value = '只支持图片文件（JPG、PNG、GIF、WebP）';
    return;
  }
  
  try {
    imageUploadLoading.value = true;
    imageUploadError.value = '';
    
    const formData = new FormData();
    formData.append('file', file);
    
    const token = localStorage.getItem('token');
    const response = await fetch('/api/upload/image', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });
    
    const data = await response.json();
    if (data.error) {
      imageUploadError.value = data.error;
    } else {
      // 将图片URL插入到文章内容中
      const imageUrl = data.location;
      const imageTag = `<img src="${imageUrl}" alt="图片" style="max-width: 100%; height: auto; margin: 10px 0;">`;
      newArticle.value.content += imageTag;
      imageUploadError.value = '';
    }
  } catch (error) {
    imageUploadError.value = '图片上传失败，请稍后重试';
    console.error('Error uploading image:', error);
  } finally {
    imageUploadLoading.value = false;
  }
}

// 小工具模块方法
async function executeNaturalLanguageQuery() {
  if (!naturalLanguageQuery.value || !selectedToolTable.value) {
    toolError.value = '请输入自然语言查询并选择数据表';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    toolError.value = '请先登录';
    return;
  }

  try {
    toolLoading.value = true;
    toolMessage.value = '处理中...';
    toolError.value = '';
    queryResult.value = null;
    generatedSQL.value = '';
    
    const response = await fetch('/api/tools/natural-language-query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        natural_language: naturalLanguageQuery.value,
        table_name: selectedToolTable.value
      })
    });
    
    const data = await response.json();
    if (data.error) {
      toolError.value = '错误: ' + data.error;
    } else {
      generatedSQL.value = data.sql;
      queryResult.value = data.result;
      toolMessage.value = '查询完成';
      showResultModal.value = true; // 打开查询结果弹框
    }
  } catch (error) {
    toolError.value = '错误: ' + error.message;
    console.error('Error executing natural language query:', error);
  } finally {
    toolLoading.value = false;
  }
}

function closeResultModal() {
  showResultModal.value = false;
}

function resetToolState() {
  naturalLanguageQuery.value = '';
  selectedToolTable.value = '';
  toolMessage.value = '';
  toolError.value = '';
  queryResult.value = null;
  generatedSQL.value = '';
  showResultModal.value = false;
}

// 处理市容环卫文件选择
function handleHuanweiFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    huanweiFile.value = file;
    huanweiError.value = '';
  }
}

// 处理市容环卫文件
async function processHuanweiFile() {
  if (!huanweiFile.value) {
    huanweiError.value = '请先选择Excel文件';
    return;
  }
  
  const token = localStorage.getItem('token');
  if (!token) {
    huanweiError.value = '请先登录';
    return;
  }
  
  try {
    huanweiLoading.value = true;
    huanweiError.value = '';
    huanweiMessage.value = '正在上传文件，请稍候...';
    
    const formData = new FormData();
    formData.append('file', huanweiFile.value);
    
    // 使用 axios 发送请求，更好地处理超时和错误
    const response = await axios.post('/api/tools/huanwei-assignment', formData, {
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'multipart/form-data'
      },
      responseType: 'blob', // 重要：设置响应类型为 blob
      timeout: 300000, // 5分钟超时
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          huanweiMessage.value = `上传中... ${percentCompleted}%`;
        }
      }
    });
    
    // 处理文件下载
    const blob = new Blob([response.data], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    });
    const url = window.URL.createObjectURL(blob);
    huanweiDownloadUrl.value = url;
    huanweiMessage.value = '处理完成，请点击下方链接下载文件';
    
  } catch (error) {
    console.error('Error processing huanwei file:', error);
    
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      huanweiError.value = '请求超时，文件可能较大，请稍后重试或使用较小的文件';
    } else if (error.code === 'ERR_NETWORK' || error.message.includes('Network Error')) {
      huanweiError.value = '网络连接失败，请检查服务器是否正常运行';
    } else if (error.response) {
      // 服务器返回了错误响应
      if (error.response.data instanceof Blob) {
        // 尝试从 Blob 中解析错误信息
        try {
          const text = await error.response.data.text();
          const data = JSON.parse(text);
          huanweiError.value = data.error || `服务器错误 (${error.response.status})`;
        } catch {
          huanweiError.value = `服务器错误 (${error.response.status})`;
        }
      } else {
        huanweiError.value = error.response.data?.error || `服务器错误 (${error.response.status})`;
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      huanweiError.value = '服务器无响应，请检查服务器是否正常运行或联系管理员';
    } else {
      huanweiError.value = '处理失败: ' + (error.message || '未知错误');
    }
    huanweiMessage.value = '';
  } finally {
    huanweiLoading.value = false;
  }
}

// 重置市容环卫文件选择
function resetHuanweiFile() {
  huanweiFile.value = null;
  huanweiMessage.value = '';
  huanweiError.value = '';
  huanweiDownloadUrl.value = '';
  // 重置文件输入框
  const fileInput = document.getElementById('huanwei-file-input');
  if (fileInput) {
    fileInput.value = '';
  }
}

// 处理地址提取文件选择
function handleLocationFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    locationFile.value = file;
  }
}

// 处理地址提取文件
async function processLocationFile() {
  if (!locationFile.value) {
    locationMessage.value = '请先选择文件';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    locationMessage.value = '请先登录';
    return;
  }

  const formData = new FormData();
  formData.append('file', locationFile.value);

  try {
    locationLoading.value = true;
    locationMessage.value = '提取中...';
    locationError.value = '';
    
    const response = await fetch('/api/tools/extract-location', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (!response.ok) {
      // 处理错误响应
      const errorData = await response.json();
      locationError.value = errorData.error || '处理文件时出错';
      locationMessage.value = '';
      return;
    }
    
    // 处理文件响应
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    locationDownloadUrl.value = url;
    locationMessage.value = '地址提取完成，请下载处理后的文件';
    
    // 自动触发下载
    const a = document.createElement('a');
    a.href = url;
    a.download = 'case_data_with_extracted_location.xlsx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
  } catch (error) {
    locationError.value = '处理文件时出错: ' + error.message;
    locationMessage.value = '';
    console.error('Error processing location file:', error);
  } finally {
    locationLoading.value = false;
  }
}

// 重置地址提取
function resetLocationFile() {
  locationFile.value = null;
  locationMessage.value = '';
  locationError.value = '';
  locationDownloadUrl.value = '';
  // 重置文件输入框
  const fileInput = document.getElementById('location-file-input');
  if (fileInput) {
    fileInput.value = '';
  }
}

// 数据清洗模块方法
function handleCleaningFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    cleaningFile.value = file;
    cleaningError.value = '';
    cleaningFields.value = [];
    selectedCleaningField.value = '';
  }
}

async function processCleaningFile() {
  if (!cleaningFile.value) {
    cleaningError.value = '请先选择Excel文件';
    return;
  }

  if (!selectedCleaningField.value) {
    cleaningError.value = '请选择字段';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    cleaningError.value = '请先登录';
    return;
  }

  try {
    cleaningLoading.value = true;
    cleaningError.value = '';
    cleaningMessage.value = '处理中...';
    
    const formData = new FormData();
    formData.append('file', cleaningFile.value);
    formData.append('fields', JSON.stringify({ [selectedCleaningField.value]: 'problem_description' }));
    
    const response = await fetch('/api/tools/data-cleaning', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (response.ok) {
      // 处理文件下载
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      cleaningDownloadUrl.value = url;
      cleaningMessage.value = '处理完成，请点击下方链接下载文件';
    } else {
      const data = await response.json();
      cleaningError.value = data.error || '处理失败';
      cleaningMessage.value = '';
    }
  } catch (error) {
    cleaningError.value = '处理失败: ' + error.message;
    cleaningMessage.value = '';
    console.error('Error processing cleaning file:', error);
  } finally {
    cleaningLoading.value = false;
  }
}

function resetCleaningFile() {
  cleaningFile.value = null;
  cleaningMessage.value = '';
  cleaningError.value = '';
  cleaningDownloadUrl.value = '';
  cleaningFields.value = [];
  selectedCleaningField.value = '';
  // 重置文件输入框
  const fileInput = document.getElementById('cleaning-file-input');
  if (fileInput) {
    fileInput.value = '';
  }
}

async function fetchCleaningFields() {
  if (!cleaningFile.value) {
    cleaningError.value = '请先选择Excel文件';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    cleaningError.value = '请先登录';
    showLogin.value = true;
    return;
  }

  try {
    cleaningLoading.value = true;
    cleaningError.value = '';
    cleaningMessage.value = '读取文件字段中...';
    
    const formData = new FormData();
    formData.append('file', cleaningFile.value);
    
    const response = await fetch('/api/tools/data-cleaning/fields', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (response.ok) {
      const data = await response.json();
      cleaningFields.value = data.fields;
      selectedCleaningField.value = '';
      cleaningMessage.value = '字段读取完成，请选择需要处理的字段';
    } else {
      const data = await response.json();
      if (data.error === 'Invalid or expired token') {
        // Token过期，清除本地存储并引导重新登录
        localStorage.removeItem('token');
        localStorage.removeItem('userInfo');
        isLoggedIn.value = false;
        userInfo.value = null;
        showLogin.value = true;
        cleaningError.value = '登录已过期，请重新登录';
      } else {
        cleaningError.value = data.error || '读取字段失败';
      }
      cleaningMessage.value = '';
    }
  } catch (error) {
    cleaningError.value = '读取字段失败: ' + error.message;
    cleaningMessage.value = '';
    console.error('Error fetching cleaning fields:', error);
  } finally {
    cleaningLoading.value = false;
  }
}

// 数据脱敏模块方法
function handleDesensitizationFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    desensitizationFile.value = file;
    desensitizationError.value = '';
    desensitizationFields.value = [];
    selectedDesensitizationField.value = '';
    selectedDesensitizationType.value = '';
  }
}

async function processDesensitizationFile() {
  if (!desensitizationFile.value) {
    desensitizationError.value = '请先选择Excel文件';
    return;
  }

  if (!selectedDesensitizationField.value || !selectedDesensitizationType.value) {
    desensitizationError.value = '请选择字段和脱敏类型';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    desensitizationError.value = '请先登录';
    return;
  }

  try {
    desensitizationLoading.value = true;
    desensitizationError.value = '';
    desensitizationMessage.value = '处理中...';
    
    const formData = new FormData();
    formData.append('file', desensitizationFile.value);
    formData.append('fields', JSON.stringify({ [selectedDesensitizationField.value]: selectedDesensitizationType.value }));
    
    const response = await fetch('/api/tools/data-cleaning', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (response.ok) {
      // 处理文件下载
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      desensitizationDownloadUrl.value = url;
      desensitizationMessage.value = '处理完成，请点击下方链接下载文件';
    } else {
      const data = await response.json();
      desensitizationError.value = data.error || '处理失败';
      desensitizationMessage.value = '';
    }
  } catch (error) {
    desensitizationError.value = '处理失败: ' + error.message;
    desensitizationMessage.value = '';
    console.error('Error processing desensitization file:', error);
  } finally {
    desensitizationLoading.value = false;
  }
}

function resetDesensitizationFile() {
  desensitizationFile.value = null;
  desensitizationMessage.value = '';
  desensitizationError.value = '';
  desensitizationDownloadUrl.value = '';
  desensitizationFields.value = [];
  selectedDesensitizationField.value = '';
  selectedDesensitizationType.value = '';
  // 重置文件输入框
  const fileInput = document.getElementById('desensitization-file-input');
  if (fileInput) {
    fileInput.value = '';
  }
}

async function fetchDesensitizationFields() {
  if (!desensitizationFile.value) {
    desensitizationError.value = '请先选择Excel文件';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    desensitizationError.value = '请先登录';
    showLogin.value = true;
    return;
  }

  try {
    desensitizationLoading.value = true;
    desensitizationError.value = '';
    desensitizationMessage.value = '读取文件字段中...';
    
    const formData = new FormData();
    formData.append('file', desensitizationFile.value);
    
    const response = await fetch('/api/tools/data-cleaning/fields', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (response.ok) {
      const data = await response.json();
      desensitizationFields.value = data.fields;
      selectedDesensitizationField.value = '';
      selectedDesensitizationType.value = '';
      desensitizationMessage.value = '字段读取完成，请选择需要脱敏的字段';
    } else {
      const data = await response.json();
      if (data.error === 'Invalid or expired token') {
        // Token过期，清除本地存储并引导重新登录
        localStorage.removeItem('token');
        localStorage.removeItem('userInfo');
        isLoggedIn.value = false;
        userInfo.value = null;
        showLogin.value = true;
        desensitizationError.value = '登录已过期，请重新登录';
      } else {
        desensitizationError.value = data.error || '读取字段失败';
      }
      desensitizationMessage.value = '';
    }
  } catch (error) {
    desensitizationError.value = '读取字段失败: ' + error.message;
    desensitizationMessage.value = '';
    console.error('Error fetching desensitization fields:', error);
  } finally {
    desensitizationLoading.value = false;
  }
}

// 城管通模块方法

// 调用后端API进行城管通查询
async function callBaiLianAPI(query) {
  try {
    chengguantongLoading.value = true;
    chengguantongError.value = '';
    
    console.log('开始调用后端城管通API');
    console.log('请求参数:', {
      message: query
    });
    
    const token = localStorage.getItem('token');
    if (!token) {
      chengguantongError.value = '请先登录';
      return;
    }
    
    const response = await fetch('/api/chengguantong/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message: query }),
      timeout: 30000 // 添加30秒超时
    });
    
    console.log('API调用成功，响应状态:', response.status);
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `API调用失败: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('API调用成功，响应数据:', data);
    
    if (data.response) {
      chengguantongResponse.value = data.response;
      showResponse.value = true;
      
      // 添加到历史记录
      chatHistory.value.unshift({
        id: Date.now(),
        query: query,
        response: data.response,
        timestamp: new Date().toLocaleString()
      });
      
      // 限制历史记录数量
      if (chatHistory.value.length > 10) {
        chatHistory.value = chatHistory.value.slice(0, 10);
      }
    } else {
      chengguantongError.value = '未收到有效的响应';
      console.error('响应数据格式异常:', data);
    }
  } catch (error) {
    console.error('调用后端城管通API失败:', error);
    console.error('错误消息:', error.message);
    
    let errorMessage = 'API调用失败';
    if (error.message.includes('Network Error')) {
      errorMessage = '网络错误，请检查网络连接或防火墙设置';
    } else if (error.message.includes('timeout')) {
      errorMessage = 'API调用超时，请检查网络连接';
    } else {
      errorMessage = `API调用失败: ${error.message || '未知错误'}`;
    }
    
    chengguantongError.value = errorMessage;
  } finally {
    chengguantongLoading.value = false;
    console.log('API调用完成');
  }
}

// 防抖函数
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 重置城管通模块状态
function resetChengguantong() {
  chengguantongQuery.value = '';
  chengguantongResponse.value = '';
  chengguantongError.value = '';
  showResponse.value = false;
  chatHistory.value = [];
  showHistory.value = false;
}

// 案件管理相关方法

// 导入案件数据
async function importCases() {
  if (!caseImportFile.value) {
    casesError.value = '请选择要导入的Excel文件';
    return;
  }
  
  caseImportLoading.value = true;
  casesError.value = '';
  caseImportMessage.value = '';
  
  try {
    console.log('开始导入案件数据');
    console.log('选中的文件:', caseImportFile.value);
    
    const formData = new FormData();
    formData.append('file', caseImportFile.value);
    
    console.log('FormData创建成功，准备发送请求');
    
    const response = await fetch('/api/cases/import', {
      method: 'POST',
      body: formData
    });
    
    console.log('请求发送成功，响应状态:', response.status);
    
    if (!response.ok) {
      console.error('响应失败:', response.status, response.statusText);
      throw new Error('网络请求失败');
    }
    
    const data = await response.json();
    console.log('响应数据:', data);
    
    if (data.error) {
      casesError.value = '导入失败: ' + data.error;
      console.error('导入失败:', data.error);
    } else {
      caseImportMessage.value = `导入成功！共导入 ${data.imported_count} 条数据，跳过 ${data.skipped_count} 条重复数据`;
      console.log('导入成功:', data);
      await fetchCasesList();
    }
  } catch (error) {
    casesError.value = '导入失败: ' + error.message;
    console.error('Error importing cases:', error);
  } finally {
    caseImportLoading.value = false;
    console.log('导入过程结束');
  }
}

// 获取案件列表
async function fetchCasesList() {
  casesLoading.value = true;
  casesError.value = '';
  
  try {
    const params = new URLSearchParams({
      page: casesCurrentPage.value,
      per_page: casesPageSize.value,
      search: casesSearch.value
    });
    
    const response = await fetch(`/api/cases?${params}`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    if (data.error) {
      casesError.value = '获取案件列表失败: ' + data.error;
  } else {
    casesList.value = data.cases;
    casesTotal.value = data.total;
  }
  } catch (error) {
    casesError.value = '获取案件列表失败: ' + error.message;
    console.error('Error fetching cases:', error);
  } finally {
    casesLoading.value = false;
  }
}

// 查看案件详情
async function viewCaseDetail(caseId) {
  casesLoading.value = true;
  casesError.value = '';
  
  try {
    const response = await fetch(`/api/cases/${caseId}`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    if (data.error) {
      casesError.value = '获取案件详情失败: ' + data.error;
  } else {
    currentCase.value = data;
    showCaseDetail.value = true;
  }
  } catch (error) {
    casesError.value = '获取案件详情失败: ' + error.message;
    console.error('Error fetching case detail:', error);
  } finally {
    casesLoading.value = false;
  }
}

// 处理文件选择
function handleCaseFileSelect(event) {
  const file = event.target.files[0];
  if (file && file.name.endsWith('.xlsx')) {
    caseImportFile.value = file;
    casesError.value = '';
    caseImportMessage.value = '';
  } else {
    casesError.value = '请选择Excel文件（.xlsx格式）';
    caseImportFile.value = null;
  }
}

// 搜索案件
function searchCases() {
  casesCurrentPage.value = 1;
  fetchCasesList();
}

// 翻页
function handleCasesPageChange(page) {
  casesCurrentPage.value = page;
  fetchCasesList();
}

// 汇问台相关方法

// 测试CloudBase连接
async function testCloudBaseConnection() {
  try {
    console.log('开始测试CloudBase连接');
    
    // 使用用户提供的云环境ID
    const envId = 'cloud1-2g359sgd56ce6c79';
    console.log('云环境ID:', envId);
    
    // 初始化CloudBase实例
    console.log('初始化CloudBase实例...');
    const app = cloudbase.init({
      env: envId
    });
    console.log('CloudBase实例初始化成功');
    
    // 关键：先匿名登录
    console.log('开始匿名登录...');
    try {
      await app.auth().signInAnonymously();
      console.log('匿名登录成功');
    } catch (e) {
      console.error('匿名登录失败:', e);
      throw new Error(`匿名登录失败: ${e.message}`);
    }
    
    // 测试获取数据库引用
    console.log('获取数据库引用...');
    const db = app.database();
    console.log('数据库引用获取成功');
    
    // 测试读取数据
    console.log('测试读取tasks集合...');
    
    // 尝试读取数据
    const result = await db.collection('tasks').get();
    console.log('数据读取成功:', result);
    
    return result;
  } catch (error) {
    console.error('CloudBase连接测试失败:', error);
    console.error('错误类型:', typeof error);
    console.error('错误对象:', error);
    console.error('错误消息:', error.message);
    console.error('错误堆栈:', error.stack);
    throw error;
  }
}

// 读取tasks集合数据
async function fetchHuiwentaiTasks() {
  try {
    tasksCurrentPage.value = 1;
    huiwentaiLoading.value = true;
    huiwentaiError.value = '';
    
    console.log('开始读取tasks数据');
    
    // 测试CloudBase连接
    const result = await testCloudBaseConnection();
    
    if (result && result.data) {
      huiwentaiTasks.value = result.data;
      console.log('读取tasks数据成功:', result.data);
    } else {
      huiwentaiTasks.value = [];
      console.log('tasks集合为空');
    }
  } catch (error) {
    console.error('读取tasks数据失败:', error);
    huiwentaiError.value = `读取数据失败: ${error.message || '未知错误'}\n\n提示：请检查CloudBase云环境配置，或使用示例数据`;
    // 使用示例数据
    huiwentaiTasks.value = [
      {
        taskId: 'TASK001',
        description: '示例问题：街道堆放垃圾',
        request: '请及时清理',
        contact: '13800138000',
        createdAt: new Date().toISOString(),
        processResult: '已清理完毕'
      },
      {
        taskId: 'TASK002',
        description: '示例问题：路灯损坏',
        request: '请维修路灯',
        contact: '13900139000',
        createdAt: new Date().toISOString(),
        processResult: ''
      }
    ];
    console.log('使用示例数据');
  } finally {
    huiwentaiLoading.value = false;
    console.log('数据读取操作完成');
  }
}

// 读取daily-reports集合数据
async function fetchHuiwentaiDailyReports() {
  try {
    reportsCurrentPage.value = 1;
    huiwentaiLoading.value = true;
    huiwentaiError.value = '';
    
    console.log('开始读取daily-reports数据');
    
    // 使用用户提供的云环境ID
    const envId = 'cloud1-2g359sgd56ce6c79';
    console.log('云环境ID:', envId);
    
    // 初始化CloudBase实例
    console.log('初始化CloudBase实例...');
    const app = cloudbase.init({
      env: envId
    });
    console.log('CloudBase实例初始化成功');
    
    // 匿名登录
    console.log('开始匿名登录...');
    try {
      await app.auth().signInAnonymously();
      console.log('匿名登录成功');
    } catch (e) {
      console.error('匿名登录失败:', e);
      throw new Error(`匿名登录失败: ${e.message}`);
    }
    
    // 获取数据库引用
    console.log('获取数据库引用...');
    const db = app.database();
    console.log('数据库引用获取成功');
    
    // 读取daily-reports集合数据
    console.log('读取daily-reports集合...');
    const result = await db.collection('daily-reports').get();
    console.log('数据读取成功:', result);
    console.log('完整的result对象:', JSON.stringify(result, null, 2));
    
    if (result && result.data) {
      huiwentaiDailyReports.value = result.data;
      console.log('读取daily-reports数据成功:', result.data);
      console.log('数据条数:', result.data.length);
      if (result.data.length > 0) {
        console.log('第一条数据结构:', JSON.stringify(result.data[0], null, 2));
        console.log('第一条数据的所有字段:', Object.keys(result.data[0]));
      }
    } else {
      huiwentaiDailyReports.value = [];
      console.log('daily-reports集合为空');
    }
  } catch (error) {
    console.error('读取daily-reports数据失败:', error);
    huiwentaiError.value = `读取数据失败: ${error.message || '未知错误'}\n\n提示：请检查CloudBase云环境配置，或使用示例数据`;
    // 使用示例数据
    huiwentaiDailyReports.value = [
      {
        reportDate: '2026-02-20',
        dutyStaff: '张三',
        shiftName: '白班',
        reported: 15,
        accepted: 15,
        collectorAccepted: 10,
        completed: 12,
        keyAreaPatrol: 3,
        system12345: 5,
        minhuWoYing: 2,
        videoMonitor: 1,
        smartAnalysis: 1,
        citizenReport: 3,
        phoneTotal: 20,
        phoneCompleted: 18,
        phone12345: 12,
        citizenHotline: 8
      },
      {
        reportDate: '2026-02-19',
        dutyStaff: '李四',
        shiftName: '夜班',
        reported: 8,
        accepted: 8,
        collectorAccepted: 5,
        completed: 7,
        keyAreaPatrol: 2,
        system12345: 3,
        minhuWoYing: 1,
        videoMonitor: 0,
        smartAnalysis: 0,
        citizenReport: 2,
        phoneTotal: 10,
        phoneCompleted: 9,
        phone12345: 6,
        citizenHotline: 4
      }
    ];
    console.log('使用示例日报数据');
  } finally {
    huiwentaiLoading.value = false;
    console.log('daily-reports数据读取操作完成');
  }
}

// 切换汇问台标签页
function switchHuiwentaiTab(tab) {
  huiwentaiActiveTab.value = tab;
  if (tab === 'tasks') {
    tasksCurrentPage.value = 1;
    fetchHuiwentaiTasks();
  } else if (tab === 'daily-reports') {
    reportsCurrentPage.value = 1;
    fetchHuiwentaiDailyReports();
  }
}

// 问题列表分页函数
function goToTasksPage(page) {
  if (page >= 1 && page <= tasksTotalPages.value) {
    tasksCurrentPage.value = page;
  }
}

// 日报数据分页函数
function goToReportsPage(page) {
  if (page >= 1 && page <= reportsTotalPages.value) {
    reportsCurrentPage.value = page;
  }
}

// 监听月份选择变化，重置当前页
watch(selectedMonthTasks, () => {
  tasksCurrentPage.value = 1;
});

watch(selectedMonthReports, () => {
  reportsCurrentPage.value = 1;
});

// 切换日报展开/收起状态
function toggleReportExpand(report) {
  const reportId = report._id || report.id || Date.now();
  if (expandedReportId.value === reportId) {
    expandedReportId.value = null;
  } else {
    expandedReportId.value = reportId;
  }
}

// 从日报内容中提取关键信息
function parseReportSummary(report) {
  const result = {
    date: report.reportDate || '未知日期',
    person: report.dutyStaff || '未知',
    shift: report.shiftName || '未知',
    reported: report.reported !== undefined && report.reported !== null ? report.reported : '-',
    accepted: report.accepted !== undefined && report.accepted !== null ? report.accepted : '-',
    completed: report.completed !== undefined && report.completed !== null ? report.completed : '-'
  };
  
  return result;
}

// 格式化完整日报内容
function formatReportContent(report) {
  const summary = parseReportSummary(report);
  let content = '';
  
  // 第一部分：日期和值班人员
  content += `${summary.date}值班人员：\n`;
  content += `  ${summary.person}\n\n`;
  
  // 第一部分：系统运行
  content += '一、系统运行\n';
  content += `上报${summary.reported}件，受理${summary.accepted}件，办结${summary.completed}件。\n\n`;
  content += `采集员上报:${report.collectorAccepted || 0}\n`;
  content += `重点领域日常巡查:${report.keyAreaPatrol || 0}\n`;
  content += `12345系统转办:${report.system12345 || 0}\n`;
  content += `民呼我应:${report.minhuWoYing || 0}\n`;
  content += `视频监控: ${report.videoMonitor || 0}\n`;
  content += `智能分析:${report.smartAnalysis || 0}\n`;
  content += `市民举报系统:${report.citizenReport || 0}\n\n`;
  
  // 第二部分：电话热线
  content += '二、电话热线\n';
  content += `总计: ${report.phoneTotal || 0}办结：${report.phoneCompleted || 0}\n`;
  content += `1.12345电话：${report.phone12345 || 0}\n`;
  content += `2.市民热线：${report.citizenHotline || 0}`;
  
  return content;
}

// 获取日报完整内容
function getReportContent(report) {
  const content = report.content || report.text || report.reportContent || report.body || report.data;
  if (typeof content === 'string') {
    return content;
  } else if (typeof content === 'object') {
    return JSON.stringify(content, null, 2);
  }
  return '无内容';
}

// 获取考核计分系数
async function fetchAssessmentCoefficients() {
  try {
    assessmentCoefficientsLoading.value = true;
    assessmentCoefficientsError.value = '';
    
    const response = await fetch('/api/assessment-coefficients', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    
    // 后端返回每个部门的系数对象
    if (data && typeof data === 'object') {
      // 确保所有部门都有系数配置
      for (const dept of assessmentDepartments) {
        if (!data[dept]) {
          data[dept] = {
            on_time: 1.0,
            overdue: 0.4,
            closure_weight: 0.8,
            delay_weight: 0.1,
            rework_weight: 0.1
          };
        }
      }
      assessmentCoefficients.value = data;
    }
  } catch (error) {
    assessmentCoefficientsError.value = '获取考核系数失败: ' + error.message;
    console.error('Error fetching assessment coefficients:', error);
  } finally {
    assessmentCoefficientsLoading.value = false;
  }
}

// 保存考核计分系数
async function saveAssessmentCoefficients() {
  try {
    assessmentCoefficientsLoading.value = true;
    assessmentCoefficientsError.value = '';
    assessmentCoefficientsMessage.value = '';
    
    const response = await fetch('/api/assessment-coefficients', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        department: selectedAssessmentDepartment.value,
        ...assessmentCoefficients.value[selectedAssessmentDepartment.value]
      })
    });
    const data = await response.json();
    
    if (data.message) {
      assessmentCoefficientsMessage.value = '考核系数保存成功！';
      // 保存成功后，从后端返回的数据中更新本地状态
      if (data.coefficients) {
        assessmentCoefficients.value = data.coefficients;
      }
      setTimeout(() => {
        assessmentCoefficientsMessage.value = '';
      }, 3000);
    } else if (data.error) {
      assessmentCoefficientsError.value = data.error;
    }
  } catch (error) {
    assessmentCoefficientsError.value = '保存考核系数失败: ' + error.message;
    console.error('Error saving assessment coefficients:', error);
  } finally {
    assessmentCoefficientsLoading.value = false;
  }
}

// 重置考核计分系数
function resetAssessmentCoefficients() {
  assessmentCoefficients.value[selectedAssessmentDepartment.value] = {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  };
}

// 监听切换到汇问台模块时加载数据
watch(
  () => activeModule.value,
  (newModule) => {
    if (newModule === 'huiwentai') {
      fetchHuiwentaiTasks();
    }
  }
);

// 获取问候语
function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 6) return '凌晨好';
  if (hour < 9) return '早上好';
  if (hour < 12) return '上午好';
  if (hour < 14) return '中午好';
  if (hour < 17) return '下午好';
  if (hour < 19) return '傍晚好';
  if (hour < 22) return '晚上好';
  return '夜深了';
}

// 获取栏目图标
function getColumnIcon(index) {
  const icons = ['📌', '📰', '📋', '📢', '📑', '📰', '📋', '📢'];
  return icons[index % icons.length];
}


</script>

<template>
  <div class="system-container">
    <!-- 顶部标题栏 -->
    <div v-if="isLoggedIn" class="header">
      <h1>运城市智慧城市管理平台-一站通</h1>
      <div class="user-info">
        <span class="username">{{ userInfo?.username }} ({{ userInfo?.role }})</span>
        <button class="logout-btn" @click="logout">登出</button>
      </div>
    </div>
    
    <!-- 调试信息已移除 -->
    
    <!-- 登录弹窗 -->
    <div v-if="showLogin" class="login-modal">
      <div class="login-form">
        <div class="login-header">
          <div class="login-logo">🏛️</div>
          <h2>智慧城市管理平台-一站通</h2>
        </div>
        <div class="form-group">
          <label for="username">用户名：</label>
          <input type="text" id="username" v-model="loginForm.username" placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="form-group">
          <label for="password">密码：</label>
          <input type="password" id="password" v-model="loginForm.password" placeholder="请输入密码" autocomplete="current-password" />
        </div>
        <div v-if="loginError" class="login-error">{{ loginError }}</div>
        <button class="login-btn" @click="login" :disabled="loginLoading">
          <span v-if="loginLoading" class="loading-spinner"></span>
          {{ loginLoading ? '登录中...' : '登 录' }}
        </button>
      </div>
    </div>
    
    <!-- 导航标签页 -->
    <div v-if="isLoggedIn" class="nav-tabs">
      <div class="tab" :class="{ active: activeModule === 'home' }" @click="switchModule('home')">
        首页
      </div>

      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.assessment)" class="tab" :class="{ active: activeModule === 'assessment' }" @click="switchModule('assessment')">
        考核计分
      </div>
      <div v-if="(!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis))" class="tab" :class="{ active: activeModule === 'ai-apps' }" @click="switchModule('ai-apps')">
        AI应用
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.map)" class="tab" :class="{ active: activeModule === 'map' }" @click="switchModule('map')">
        地图服务
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.huiwentai)" class="tab" :class="{ active: activeModule === 'huiwentai' }" @click="switchModule('huiwentai')">
        汇问台
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.cases)" class="tab" :class="{ active: activeModule === 'cases' }" @click="switchModule('cases')">
        案件管理
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.business)" class="tab" :class="{ active: activeModule === 'business' }" @click="switchModule('business')">
        业务平台
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin'" class="tab" :class="{ active: activeModule === 'admin' }" @click="switchModule('admin')">
        系统后台
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div v-if="isLoggedIn" class="main-content">
      <!-- 首页模块 -->
      <div v-if="activeModule === 'home'" class="tab-content home-page">
        <!-- 欢迎横幅区域 -->
        <div class="welcome-banner">
          <div class="welcome-content">
            <div class="welcome-text">
              <h1 class="welcome-title">欢迎使用智慧城市管理平台</h1>
              <p class="welcome-subtitle">一站式城市管理解决方案，让城市更智慧、更美好</p>
            </div>
            <div class="welcome-user" v-if="userInfo">
              <div class="user-avatar">
                <span>{{ userInfo.username?.charAt(0)?.toUpperCase() || 'U' }}</span>
              </div>
              <div class="user-greeting">
                <span class="greeting-text">{{ getGreeting() }}</span>
                <span class="user-name">{{ userInfo.username }}</span>
              </div>
            </div>
          </div>
          <div class="quick-actions">
            <div class="quick-action-item" @click="switchModule('ai-apps')">
              <div class="action-icon">🤖</div>
              <span class="action-text">AI应用</span>
            </div>
            <div class="quick-action-item" @click="switchModule('assessment')">
              <div class="action-icon">📊</div>
              <span class="action-text">考核计分</span>
            </div>
            <div class="quick-action-item" @click="switchModule('business')">
              <div class="action-icon">🏢</div>
              <span class="action-text">业务平台</span>
            </div>
            <div class="quick-action-item" @click="switchModule('huiwentai')">
              <div class="action-icon">💬</div>
              <span class="action-text">汇问台</span>
            </div>
            <!-- 本月数据展示 -->
            <div class="quick-action-item monthly-stats">
              <div class="monthly-stats-content">
                <div class="stats-title">本月数据</div>
                <div class="stats-row">
                  <span class="stat-item">
                    <span class="stat-value">{{ currentMonthStats.reported }}</span>
                    <span class="stat-label">上报</span>
                  </span>
                  <span class="stat-divider">|</span>
                  <span class="stat-item">
                    <span class="stat-value">{{ currentMonthStats.accepted }}</span>
                    <span class="stat-label">受理</span>
                  </span>
                  <span class="stat-divider">|</span>
                  <span class="stat-item">
                    <span class="stat-value">{{ currentMonthStats.completed }}</span>
                    <span class="stat-label">办结</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 数据统计区域 -->
        <div class="stats-section">
          <div class="stats-card">
            <div class="stats-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
              <span>📁</span>
            </div>
            <div class="stats-info">
              <span class="stats-number">{{ cmsCategories.length }}</span>
              <span class="stats-label">内容栏目</span>
            </div>
          </div>
          <div class="stats-card">
            <div class="stats-icon" style="background: linear-gradient(135deg, #00c6fb 0%, #005bea 100%);">
              <span>📝</span>
            </div>
            <div class="stats-info">
              <span class="stats-number">{{ allHomeArticles.length }}</span>
              <span class="stats-label">文章总数</span>
            </div>
          </div>
          <div class="stats-card">
            <div class="stats-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
              <span>🏢</span>
            </div>
            <div class="stats-info">
              <span class="stats-number">{{ displayBusinessPlatforms.length }}</span>
              <span class="stats-label">业务平台</span>
            </div>
          </div>
          <div class="stats-card">
            <div class="stats-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
              <span>📊</span>
            </div>
            <div class="stats-info">
              <span class="stats-number">{{ tables.length }}</span>
              <span class="stats-label">数据表</span>
            </div>
          </div>
        </div>

        <!-- CMS内容展示 -->
        <div class="cms-home-section">
          <div class="cms-columns">
            <div v-for="(category, index) in cmsCategories" :key="category.id" class="cms-column">
              <div class="column-header">
                <div class="column-title-wrapper">
                  <span class="column-icon">{{ getColumnIcon(index) }}</span>
                  <h3 class="column-title">{{ category.name }}</h3>
                </div>
                <a href="#" class="more-link" @click.prevent="showAllArticles(category.id)">
                  <span>更多</span>
                  <span class="more-arrow">→</span>
                </a>
              </div>
              <div class="column-articles">
                <div v-if="cmsLoading" class="loading-state">
                  <div class="loading-spinner"></div>
                  <span>加载中...</span>
                </div>
                <div v-else-if="cmsError" class="error-state">
                  <span class="error-icon">⚠️</span>
                  <span>{{ cmsError }}</span>
                </div>
                <div v-else-if="getCategoryArticles(category.id).length === 0" class="empty-state">
                  <span class="empty-icon">📭</span>
                  <span>该栏目下暂无文章</span>
                </div>
                <div v-else class="articles-list">
                  <div 
                    v-for="(article, articleIndex) in getCategoryArticles(category.id)" 
                    :key="article.id" 
                    class="article-item"
                    @click="fetchArticleDetail(article.id)"
                  >
                    <span class="article-index">{{ String(articleIndex + 1).padStart(2, '0') }}</span>
                    <span class="article-title">{{ truncateTitle(article.title) }}</span>
                    <span class="article-date">{{ formatDate(article.published_at || article.created_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 业务平台模块 -->
      <div v-if="activeModule === 'business' && (!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.business))" class="tab-content">
        <div class="business-platforms-section" style="max-width: 1200px; margin: 0 auto; padding: 20px;">
          <div v-if="businessPlatformsLoading" class="loading" style="font-size: 16px; padding: 60px; text-align: center; color: rgba(255, 255, 255, 0.8);">加载中...</div>
          <div v-else-if="displayBusinessPlatforms.length === 0" class="empty" style="font-size: 16px; padding: 60px; text-align: center; color: rgba(255, 255, 255, 0.6);">暂无业务平台</div>
          <div v-else class="platform-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 40px;">
            <div v-for="platform in displayBusinessPlatforms" :key="platform.id" class="platform-item" style="padding: 25px; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); background-color: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); transition: all 0.3s ease;" @mouseenter="$event.currentTarget.style.transform='translateY(-5px)'; $event.currentTarget.style.boxShadow='0 5px 15px rgba(0,0,0,0.15)'; $event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.15)'" @mouseleave="$event.currentTarget.style.transform='translateY(0)'; $event.currentTarget.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'; $event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.1)'">
              <a :href="platform.url" target="_blank" style="text-decoration: none; color: white; display: block;">
                <div class="platform-image-container" style="display: flex; justify-content: center; margin-bottom: 15px;">
                  <img v-if="platform.image_path" :src="platform.image_path" :alt="platform.name" style="width: 250px; height: 180px; object-fit: cover; transition: transform 0.3s ease;" @mouseenter="$event.currentTarget.style.transform='scale(1.05)'" @mouseleave="$event.currentTarget.style.transform='scale(1)'">
                  <div v-else class="platform-image-placeholder" style="width: 250px; height: 180px; background-color: rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 48px; border-radius: 8px;">🏢</div>
                </div>
                <div class="platform-info" style="text-align: center;">
                  <h4 style="margin: 0; font-size: 18px; color: white;">{{ platform.name }}</h4>
                </div>
              </a>
            </div>
          </div>
        </div>
      </div>
      
      <!-- AI应用模块 -->
      <div v-if="activeModule === 'ai-apps'" class="tab-content">
        <!-- AI应用标签页导航 -->
        <div class="ai-apps-tabs" style="display: flex; margin-bottom: 20px; border-bottom: 1px solid #dee2e6;">
          <div 
            v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis)"
            class="ai-apps-tab" 
            :class="{ active: aiAppsActiveTab === 'analysis' }"
            @click="aiAppsActiveTab = 'analysis'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="aiAppsActiveTab === 'analysis' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
          >
            数据分析
          </div>
          <div 
            v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis)"
            class="ai-apps-tab" 
            :class="{ active: aiAppsActiveTab === 'analysis-v2' }"
            @click="aiAppsActiveTab = 'analysis-v2'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="aiAppsActiveTab === 'analysis-v2' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
          >
            数据分析（新版）
          </div>
          <div 
            v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis)"
            class="ai-apps-tab" 
            :class="{ active: aiAppsActiveTab === 'spotcheck' }"
            @click="aiAppsActiveTab = 'spotcheck'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="aiAppsActiveTab === 'spotcheck' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
          >
            案件抽查
          </div>
          <div
            v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis)"
            class="ai-apps-tab"
            :class="{ active: aiAppsActiveTab === 'chengguantong' }"
            @click="aiAppsActiveTab = 'chengguantong'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="aiAppsActiveTab === 'chengguantong' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
          >
            城管通
          </div>
        </div>
        
        <!-- 数据分析标签页内容 -->
        <div v-if="aiAppsActiveTab === 'analysis' && (!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis))">
        <div class="config-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 分析配置区域 -->
          <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
              <div>
                <label for="table-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择数据表：</label>
                <select id="table-select" v-model="selectedTable" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                  <option value="">-- 请选择 --</option>
                  <option v-for="table in tables" :key="table" :value="table">
                    {{ table }}
                  </option>
                </select>
              </div>
              <div>
                <label for="analysis-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">分析类型：</label>
                <select id="analysis-select" v-model="selectedAnalysisType" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                  <option value="">-- 请选择 --</option>
                  <option v-for="type in analysisTypes" :key="type.value" :value="type.value">
                    {{ type.label }}
                  </option>
                </select>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <button 
              class="analyze-btn" 
              @click="startAnalysis" 
              :disabled="loading || !selectedTable || !selectedAnalysisType"
              style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
              @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
              @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
            >
              <span v-if="loading">⏳ 分析中...</span>
              <span v-else>🔍 开始分析</span>
            </button>
            
            <!-- 消息提示 -->
            <div v-if="analysisMessage" style="margin-top: 15px; padding: 12px; background-color: rgba(76, 175, 80, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(76, 175, 80, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
              ✓ {{ analysisMessage }}
            </div>
            
            <!-- 分析进度显示 -->
            <div v-if="loading" style="margin-top: 25px; padding: 20px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 6px; border-left: 4px solid #4facfe;">
              <div style="font-weight: 600; color: #4facfe; margin-bottom: 15px; font-size: 14px;">⏳ 分析进度</div>
              <div v-for="(step, index) in analysisSteps" :key="index"
                   style="display: flex; align-items: center; margin-bottom: 10px; padding: 8px; border-radius: 4px; transition: all 0.4s ease;"
                   :style="{
                     background: step.status === 'completed' ? 'rgba(76, 175, 80, 0.2)' :
                              step.status === 'active' ? 'rgba(79, 172, 254, 0.2)' :
                              'rgba(255, 255, 255, 0.1)',
                     opacity: step.status === 'pending' ? '0.5' : '1',
                     transform: step.status !== 'pending' ? 'translateX(0)' : 'translateX(-10px)',
                     animation: step.status === 'active' ? 'pulse 1.5s ease-in-out infinite' : 'none'
                   }">
                <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; margin-right: 12px; font-size: 16px; flex-shrink: 0; transition: all 0.3s ease;"
                     :style="{
                       background: step.status === 'completed' ? 'linear-gradient(135deg, #4caf50 0%, #8bc34a 100%)' :
                                  step.status === 'active' ? 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' :
                                  'rgba(255, 255, 255, 0.2)',
                       color: 'white',
                       boxShadow: step.status === 'active' ? '0 0 10px rgba(79, 172, 254, 0.5)' : 'none'
                     }">
                  <span v-if="step.status === 'completed' && index < 4">✓</span>
                  <span v-else>{{ step.icon }}</span>
                </div>
                <div style="color: rgba(255, 255, 255, 0.8); font-size: 14px; font-weight: 500;"
                     :style="{ color: step.status === 'active' ? '#4facfe' : 'rgba(255, 255, 255, 0.8)' }">
                  {{ step.text }}
                </div>
              </div>
              <!-- 进度条 -->
              <div style="margin-top: 15px; height: 4px; background: rgba(255,255,255,0.2); border-radius: 2px; overflow: hidden;">
                <div style="height: 100%; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); transition: width 0.5s ease;"
                     :style="{ width: ((currentStep + 1) / analysisSteps.length * 100) + '%' }"></div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 分析结果 -->
        <div v-if="analysisResult" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
          <!-- 结果标题 -->
          <div style="margin-bottom: 25px; padding-bottom: 15px; border-bottom: 2px solid #4facfe;">
            <h3 style="margin: 0; font-size: 20px; color: white;">📈 {{ analysisResult.table_name }} - {{ getAnalysisTypeName(analysisResult.analysis_type) }}</h3>
            <p style="margin: 12px 0 0 0; color: rgba(255, 255, 255, 0.8); font-size: 14px; line-height: 1.6;">{{ analysisResult.data_summary }}</p>
          </div>
          
          <div class="result-details">
            <!-- 图表展示 -->
            <div v-if="analysisResult.chart_data" class="charts-section" style="margin-bottom: 30px;">
              <h4 style="margin: 0 0 20px 0; color: #4facfe; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                <span>📊</span>
                <span>数据可视化</span>
              </h4>
              <div class="chart-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">
                <!-- 时间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'time_analysis'">
                  <div class="chart-item" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📅 日案件量趋势</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">⏰ 小时级高峰时段</h5>
                    <div ref="hourlyChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 空间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'space_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.street" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">🏘️ 各街道案件密度</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.community" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">🏢 各社区案件密度</h5>
                    <div ref="spaceChart2" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.area" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📍 各片区案件密度</h5>
                    <div ref="spaceChart3" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 来源分析图表 -->
                <template v-if="analysisResult.analysis_type === 'source_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.source" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">🔗 案件来源分布</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 案件类型分析图表 -->
                <template v-if="analysisResult.analysis_type === 'type_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.type" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📋 案件类型分布</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 重复案件分析图表 -->
                <template v-if="analysisResult.analysis_type === 'duplicate_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_duplicates" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">❓ 问题描述重复TOP10</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_duplicates" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📍 地址描述重复TOP10</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_type_distribution" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">🏷️ 地址描述类型占比</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.combined_duplicates" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">🔀 组合重复TOP10</h5>
                    <div ref="spaceChart2" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.violation_type_distribution" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">⚠️ 重复案件违规类型占比</h5>
                    <div ref="spaceChart3" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                
                <!-- 对比上月分析图表 -->
                <template v-if="analysisResult.analysis_type === 'monthly_comparison'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.monthly_comparison" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📊 上月vs本月案件量对比</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.case_size_comparison" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📈 案件大小类别变化</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_trend" style="padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
                    <h5 style="margin: 0 0 15px 0; color: white; font-size: 14px; font-weight: 600;">📉 问题趋势变化</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
              </div>
            </div>
            
            <!-- 智能分析结果 -->
            <div v-if="analysisResult.analysis" style="margin-top: 30px; padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; border-left: 4px solid #4facfe; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);">
              <h4 style="margin: 0 0 15px 0; color: #4facfe; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                <span>🤖</span>
                <span>AI智能分析</span>
              </h4>
              <div style="line-height: 1.8; color: rgba(255, 255, 255, 0.9); font-size: 15px;" v-html="analysisResult.analysis.replace(/\n/g, '<br>')"></div>
            </div>
          </div>
        </div>
        </div>
        
        <!-- 数据分析（新版）标签页内容 -->
        <div v-if="aiAppsActiveTab === 'analysis-v2' && (!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis))">
        <div class="config-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 分析配置区域 -->
          <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
              <div>
                <label for="table-select-v2" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择数据表：</label>
                <select id="table-select-v2" v-model="selectedTableV2" :disabled="analysisV2Loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                  <option value="">-- 请选择 --</option>
                  <option v-for="table in tables" :key="table" :value="table">
                    {{ table }}
                  </option>
                </select>
              </div>
              <div>
                <label for="model-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择大模型：</label>
                <select id="model-select" v-model="selectedModel" :disabled="analysisV2Loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                  <option value="volcengine">火山引擎（豆包）</option>
                  <option value="bailian">阿里云百炼（通义千问）</option>
                </select>
              </div>
            </div>
            
            <div style="margin-bottom: 20px;">
              <label for="analysis-prompt" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">分析提示词：</label>
              <textarea 
                id="analysis-prompt" 
                v-model="analysisPrompt" 
                :disabled="analysisV2Loading"
                rows="5"
                placeholder="请输入您的分析需求，例如：请分析这个数据表中的案件来源分布情况，并生成图表展示"
                style="width: 100%; padding: 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; resize: vertical; min-height: 120px; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white;"
              ></textarea>
            </div>
            
            <!-- 操作按钮 -->
            <button 
              @click="startAnalysisV2" 
              :disabled="analysisV2Loading || !selectedTableV2 || !analysisPrompt"
              style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease;"
              @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
              @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
            >
              <span v-if="analysisV2Loading">⏳ 分析中...</span>
              <span v-else>🔍 开始分析</span>
            </button>
            
            <!-- 消息提示 -->
            <div v-if="analysisV2Message" style="margin-top: 15px; padding: 12px; background-color: rgba(76, 175, 80, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(76, 175, 80, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
              ✓ {{ analysisV2Message }}
            </div>
            <div v-if="analysisV2Error" style="margin-top: 15px; padding: 12px; background-color: rgba(248, 215, 218, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(245, 198, 203, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
              ✗ {{ analysisV2Error }}
            </div>
          </div>
        </div>
        
        <!-- 分析结果 -->
        <div v-if="analysisV2Result" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
          <!-- 结果标题 -->
          <div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 2px solid #4facfe;">
            <h3 style="margin: 0; font-size: 20px; color: white;">📈 {{ analysisV2Result.table_name }} - 智能分析报告</h3>
          </div>

          <!-- 筛选信息 -->
          <div v-if="analysisV2Result.filter_applied" style="margin-bottom: 20px; padding: 15px; background: rgba(79, 172, 254, 0.15); border-radius: 8px; border-left: 4px solid #4facfe;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <span style="font-size: 16px;">🔍</span>
              <span style="color: white; font-weight: 600; font-size: 14px;">数据筛选结果</span>
            </div>
            <div style="color: rgba(255, 255, 255, 0.9); font-size: 13px; line-height: 1.6;">
              <div style="margin-bottom: 4px;">
                <span style="color: rgba(255, 255, 255, 0.7);">筛选条件：</span>
                <span style="color: #4facfe; font-weight: 500;">{{ analysisV2Result.filter_summary }}</span>
              </div>
              <div>
                <span style="color: rgba(255, 255, 255, 0.7);">数据量：</span>
                <span style="color: white; font-weight: 600;">{{ analysisV2Result.original_count }}</span>
                <span style="color: rgba(255, 255, 255, 0.6);"> 条 → 筛选后 </span>
                <span style="color: #4facfe; font-weight: 600;">{{ analysisV2Result.filtered_count }}</span>
                <span style="color: rgba(255, 255, 255, 0.6);"> 条</span>
              </div>
            </div>
          </div>

          <!-- 未筛选时的数据量显示 -->
          <div v-else style="margin-bottom: 20px; padding: 12px 15px; background: rgba(255, 255, 255, 0.05); border-radius: 8px;">
            <span style="color: rgba(255, 255, 255, 0.7); font-size: 13px;">
              📊 共分析 <span style="color: white; font-weight: 600;">{{ analysisV2Result.filtered_count || analysisV2Result.original_count }}</span> 条数据
            </span>
          </div>

          <div class="result-details">
            <!-- 图表展示 -->
            <div v-if="analysisV2Result.charts" class="charts-section" style="margin-bottom: 30px;">
              <h4 style="margin: 0 0 20px 0; color: #4facfe; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                <span>📊</span>
                <span>数据可视化</span>
              </h4>
              <div class="chart-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">
                <div v-for="(chart, index) in analysisV2Result.charts" :key="index" class="chart-item" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                  <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">{{ chart.title }}</h5>
                  <div v-if="chart.type === 'image'" style="text-align: center;">
                    <img :src="chart.data" :alt="chart.title" style="max-width: 100%; height: auto; border-radius: 4px;" />
                  </div>
                  <div v-else :ref="el => { if (el) chartRefs[index] = el }" class="chart" style="height: 300px;"></div>
                </div>
              </div>
            </div>
            
            <!-- 分析报告 -->
            <div v-if="analysisV2Result.report" style="margin-top: 30px;">
              <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.15);">
                <div style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid rgba(255, 255, 255, 0.2);">
                  <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                      <span style="font-size: 24px;">🤖</span>
                    </div>
                    <div>
                      <h4 style="margin: 0; color: white; font-size: 20px; font-weight: 700;">AI智能分析报告</h4>
                      <p style="margin: 4px 0 0 0; color: rgba(255, 255, 255, 0.8); font-size: 14px;">基于大数据和AI智能生成的深度分析</p>
                    </div>
                  </div>
                </div>
                
                <div class="report-content" style="line-height: 1.6; color: rgba(255, 255, 255, 0.8); font-size: 14px; padding: 10px 0; text-align: left;">
                  <div v-html="formatAnalysisReport(analysisV2Result.report)" style="word-wrap: break-word; overflow-wrap: break-word;"></div>
                </div>
                
                <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255, 255, 255, 0.2); display: flex; justify-content: space-between; align-items: center;">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4facfe" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    <span style="color: rgba(255, 255, 255, 0.8); font-size: 13px;">{{ new Date().toLocaleString('zh-CN') }}</span>
                  </div>
                  <button 
                    @click="copyReport"
                    style="padding: 8px 16px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.3s ease;"
                    @mouseenter="$event.target.style.transform='translateY(-1px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
                    @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
                  >
                    📋 复制报告
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        </div>
        
        <!-- 案件抽查标签页内容 -->
        <div v-if="aiAppsActiveTab === 'spotcheck' && (!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis))">
        <div class="spotcheck-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 提示信息 -->
          <div style="margin-bottom: 25px; padding: 16px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-left: 4px solid #4facfe; border-radius: 6px; color: rgba(255, 255, 255, 0.8);">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
              <span style="font-size: 20px; flex-shrink: 0;">ℹ️</span>
              <div>
                <div style="font-weight: 600; color: #4facfe; margin-bottom: 6px;">文件上传说明</div>
                <p style="margin: 0; line-height: 1.5; color: rgba(255, 255, 255, 0.8);">支持上传 DOCX 或 XLSX 格式的文件，系统将使用大模型进行智能分析，并返回详细的案件质量评估结果。</p>
              </div>
            </div>
          </div>
          
          <!-- 文件上传区域 -->
          <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 2px dashed #4facfe; border-radius: 8px; margin-bottom: 25px;">
            <div class="form-group" style="margin-bottom: 20px;">
              <label for="spotcheck-file-input" style="display: block; font-weight: 600; margin-bottom: 12px; color: rgba(255, 255, 255, 0.9);">选择要分析的文件：</label>
              <input 
                type="file" 
                id="spotcheck-file-input"
                accept=".docx,.xlsx"
                @change="handleSpotcheckFileSelect"
                style="padding: 10px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; width: 100%; box-sizing: border-box; cursor: pointer; background: rgba(255, 255, 255, 0.15); color: white;"
              >
              <div v-if="spotcheckFile" style="margin-top: 12px; padding: 10px 12px; background-color: rgba(76, 175, 80, 0.2); color: rgba(255, 255, 255, 0.9); border-radius: 4px; border-left: 3px solid #4caf50; backdrop-filter: blur(5px);">
                ✓ 已选择：{{ spotcheckFile.name }}
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div style="display: flex; gap: 12px;">
              <button 
                @click="uploadAndAnalyzeSpotcheck"
                :disabled="!spotcheckFile || spotcheckLoading"
                style="flex: 1; padding: 12px 24px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 16px; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
                @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
                @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
              >
                <span v-if="spotcheckLoading">⏳ 分析中...</span>
                <span v-else>📤 上传并分析</span>
              </button>
              <button 
                @click="clearSpotcheck"
                :disabled="spotcheckLoading"
                style="padding: 12px 24px; background-color: rgba(149, 165, 166, 0.8); color: white; border: 1px solid rgba(149, 165, 166, 0.5); border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; backdrop-filter: blur(5px);"
                @mouseenter="$event.target.style.backgroundColor='rgba(127, 140, 141, 0.9)'"
                @mouseleave="$event.target.style.backgroundColor='rgba(149, 165, 166, 0.8)'"
              >
                🔄 清除
              </button>
            </div>
            
            <!-- 消息提示 -->
            <div v-if="spotcheckMessage" style="margin-top: 15px; padding: 12px; background-color: rgba(76, 175, 80, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(76, 175, 80, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
              ✓ {{ spotcheckMessage }}
            </div>
            <div v-if="spotcheckError" style="margin-top: 15px; padding: 12px; background-color: rgba(248, 215, 218, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(245, 198, 203, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
              ✗ {{ spotcheckError }}
            </div>
          </div>
          
          <!-- 分析结果 -->
          <div v-if="spotcheckResult" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
            <h3 style="margin-top: 0; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #4facfe; font-size: 20px; color: white;">分析结果</h3>
            
            <!-- 文件内容 -->
            <div v-if="spotcheckResult.file_content" style="margin-bottom: 25px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                <span style="font-size: 18px;">📄</span>
                <h4 style="margin: 0; color: #4facfe; font-size: 16px;">读取的文件内容</h4>
              </div>
              <div style="background-color: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); padding: 15px; border-radius: 6px; border-left: 3px solid #4facfe; max-height: 300px; overflow-y: auto; border: 1px solid rgba(255, 255, 255, 0.2);">
                <p v-for="(line, index) in spotcheckResult.file_content.split('\n')" :key="index" v-if="line && line.trim()" style="margin: 8px 0; line-height: 1.5; color: rgba(255, 255, 255, 0.8); font-size: 14px;">
                  {{ line }}
                </p>
              </div>
            </div>
            
            <!-- 分析内容 -->
            <div v-if="spotcheckResult.analysis">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                <span style="font-size: 18px;">🔍</span>
                <h4 style="margin: 0; color: #4facfe; font-size: 16px;">AI智能分析</h4>
              </div>
              <div style="background-color: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); padding: 20px; border-radius: 6px; border-left: 3px solid #00f2fe; line-height: 1.8; color: rgba(255, 255, 255, 0.8); border: 1px solid rgba(255, 255, 255, 0.2);">
                <div v-html="spotcheckResult.analysis"></div>
              </div>
            </div>
          </div>
        </div>
        </div>
        
        <!-- 城管通标签页内容 -->
        <div v-if="aiAppsActiveTab === 'chengguantong' && (!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis))">
        <div class="chengguantong-section" style="max-width: 1200px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px; padding: 15px; background-color: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; color: rgba(255, 255, 255, 0.8);">
            <p style="margin: 0;"><strong>功能说明：</strong>运城城管通智能问答系统，基于阿里云百炼大模型，提供城市管理相关问题的专业解答。</p>
          </div>
          
          <!-- 输入区域 - 模仿大模型对话界面 -->
          <div class="chat-interface" style="display: flex; flex-direction: column; gap: 20px; width: 100%; margin: 0 auto;">
            <!-- 问题输入区域 -->
            <div class="input-container" style="width: 100%;">
              <textarea 
          id="chengguantong-query" 
          v-model="chengguantongQuery" 
          placeholder="请输入您的城市管理相关问题..." 
          rows="3" 
          :disabled="chengguantongLoading"
          style="width: 100%; 
                 padding: 20px; 
                 border: 1px solid rgba(255, 255, 255, 0.3); 
                 border-radius: 16px; 
                 resize: vertical; 
                 font-size: 18px; 
                 font-family: Arial, sans-serif; 
                 min-height: 90px; 
                 /* 移除max-width限制，让文本框占满容器 */
                 line-height: 1.6;
                 box-sizing: border-box;
                 background: rgba(255, 255, 255, 0.15);
                 color: white;
                 placeholder-color: rgba(255, 255, 255, 0.5);"
        ></textarea>
              <!-- 确保padding不超出宽度 -->
              
              <div class="button-group" style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
                <button 
                  @click="resetChengguantong"
                  :disabled="chengguantongLoading"
                  class="btn-secondary"
                  style="padding: 12px 20px; background-color: rgba(149, 165, 166, 0.8); color: white; border: 1px solid rgba(149, 165, 166, 0.5); border-radius: 6px; cursor: pointer; font-size: 14px; backdrop-filter: blur(5px);"
                >
                  清空
                </button>
                <button 
                  @click="callBaiLianAPI(chengguantongQuery)"
                  :disabled="chengguantongLoading || !chengguantongQuery"
                  class="btn-primary"
                  style="padding: 12px 30px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold;"
                >
                  <span v-if="chengguantongLoading">处理中...</span>
                  <span v-else>发送</span>
                </button>
              </div>
              
              <div v-if="chengguantongError" class="error-message" style="padding: 10px; background-color: rgba(255, 235, 238, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(255, 205, 210, 0.4); border-radius: 6px; margin-top: 10px; backdrop-filter: blur(5px);">
                {{ chengguantongError }}
              </div>
            </div>
            
            <!-- 响应结果 -->
            <div v-if="showResponse && chengguantongResponse" class="response-container" style="width: 100%; padding: 24px; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 12px; background-color: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); box-shadow: 0 2px 8px rgba(0,0,0,0.15); box-sizing: border-box;">
              <div class="response-content" style="line-height: 1.7; color: rgba(255, 255, 255, 0.8); white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word; font-size: 16px;">
                {{ chengguantongResponse }}
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>

      
      <!-- 汇问台模块 -->
      <div v-if="activeModule === 'huiwentai' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.huiwentai))" class="tab-content">
        <div class="huiwentai-section" style="max-width: 1000px; margin: 0 auto;">
          <!-- 标签页导航 -->
          <div class="huiwentai-tabs" style="display: flex; margin-bottom: 20px; border-bottom: 1px solid #dee2e6;">
            <div 
              class="huiwentai-tab" 
              :class="{ active: huiwentaiActiveTab === 'tasks' }"
              @click="switchHuiwentaiTab('tasks')"
              style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
              :style="huiwentaiActiveTab === 'tasks' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
            >
              问题列表
            </div>
            <div 
              class="huiwentai-tab" 
              :class="{ active: huiwentaiActiveTab === 'daily-reports' }"
              @click="switchHuiwentaiTab('daily-reports')"
              style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
              :style="huiwentaiActiveTab === 'daily-reports' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : { color: 'rgba(255, 255, 255, 0.8)' }"
            >
              日报数据
            </div>
          </div>
          
          <!-- 刷新按钮和月份选择 -->
          <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <!-- 月份选择下拉框 -->
            <div>
              <label v-if="huiwentaiActiveTab === 'tasks'" style="margin-right: 10px; font-size: 14px; color: rgba(255, 255, 255, 0.9);">选择月份：</label>
              <select v-if="huiwentaiActiveTab === 'tasks'" v-model="selectedMonthTasks" style="padding: 8px 12px; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; font-size: 14px; background: rgba(30, 58, 138, 0.6); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px; transition: all 0.3s ease;" @mouseenter="$event.target.style.borderColor='rgba(100, 149, 237, 0.8)'; $event.target.style.background='rgba(30, 58, 138, 0.8)'" @mouseleave="$event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.background='rgba(30, 58, 138, 0.6)'">
                <option value="">全部</option>
                <option v-for="month in availableMonthsTasks" :key="month" :value="month">{{ month }}</option>
              </select>
              
              <label v-if="huiwentaiActiveTab === 'daily-reports'" style="margin-right: 10px; font-size: 14px; color: rgba(255, 255, 255, 0.9);">选择月份：</label>
              <select v-if="huiwentaiActiveTab === 'daily-reports'" v-model="selectedMonthReports" style="padding: 8px 12px; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; font-size: 14px; background: rgba(30, 58, 138, 0.6); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px; transition: all 0.3s ease;" @mouseenter="$event.target.style.borderColor='rgba(100, 149, 237, 0.8)'; $event.target.style.background='rgba(30, 58, 138, 0.8)'" @mouseleave="$event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.background='rgba(30, 58, 138, 0.6)'">
                <option value="">全部</option>
                <option v-for="month in availableMonthsReports" :key="month" :value="month">{{ month }}</option>
              </select>
            </div>
            
            <!-- 刷新按钮 -->
            <button 
              class="refresh-btn" 
              @click="huiwentaiActiveTab === 'tasks' ? fetchHuiwentaiTasks() : fetchHuiwentaiDailyReports()" 
              :disabled="huiwentaiLoading" 
              style="padding: 8px 16px; background-color: #1890ff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;"
            >
              {{ huiwentaiLoading ? '加载中...' : '刷新数据' }}
            </button>
          </div>
          
          <!-- 加载状态 -->
          <div v-if="huiwentaiLoading" class="loading" style="font-size: 16px; padding: 40px; text-align: center; color: rgba(255, 255, 255, 0.7);">
            加载数据中...
          </div>
          
          <!-- 错误信息 -->
          <div v-else-if="huiwentaiError" class="error" style="font-size: 16px; padding: 40px; text-align: center; color: #ff6b6b;">
            <p>{{ huiwentaiError }}</p>
            <p style="font-size: 14px; color: rgba(255, 255, 255, 0.6); margin-top: 10px;">请检查：</p>
            <ul style="font-size: 14px; color: rgba(255, 255, 255, 0.6); text-align: left; max-width: 400px; margin: 10px auto;">
              <li>1. 云环境ID是否正确</li>
              <li>2. 云数据库安全规则是否允许读取操作</li>
              <li>3. 网络连接是否正常</li>
              <li>4. {{ huiwentaiActiveTab === 'tasks' ? 'tasks' : 'daily-reports' }}集合是否存在</li>
            </ul>
            <p style="font-size: 14px; color: rgba(255, 255, 255, 0.6); margin-top: 10px;">详细错误信息请查看浏览器控制台</p>
          </div>
          
          <!-- 任务数据标签页内容 -->
          <div v-else-if="huiwentaiActiveTab === 'tasks'" class="tasks-table">
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px; text-align: left; background: rgba(30, 58, 138, 0.3); backdrop-filter: blur(10px); border-radius: 12px; overflow: hidden; border: 1px solid rgba(100, 149, 237, 0.3);">
              <thead>
                <tr style="background: rgba(30, 58, 138, 0.6);">
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600;">任务号</th>
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600;">问题描述</th>
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600;">诉求</th>
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600; min-width: 150px;">联系方式</th>
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600;">创建时间</th>
                  <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); color: white; font-weight: 600;">处理结果</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="filteredHuiwentaiTasks.length === 0">
                  <td colspan="6" style="padding: 40px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: center; color: rgba(255, 255, 255, 0.9); background: rgba(30, 58, 138, 0.2);">暂无任务数据</td>
                </tr>
                <tr v-for="task in paginatedHuiwentaiTasks" :key="task.taskId || task._id" style="background: rgba(30, 58, 138, 0.2);">
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.taskId || task._id || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.description || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.request || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.contact || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.createdAt ? new Date(task.createdAt).toLocaleString() : '无' }}</td>
                  <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ task.processResult || '' }}</td>
                </tr>
              </tbody>
            </table>
            
            <!-- 问题列表分页组件 -->
            <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 8px;">
              <button 
                @click="goToTasksPage(tasksCurrentPage - 1)" 
                :disabled="tasksCurrentPage === 1"
                style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; cursor: pointer; border-radius: 6px; transition: all 0.3s ease;"
                :style="{ opacity: tasksCurrentPage === 1 ? 0.5 : 1, cursor: tasksCurrentPage === 1 ? 'not-allowed' : 'pointer' }"
                @mouseenter="if(tasksCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                @mouseleave="if(tasksCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
              >上一页</button>
              
              <span style="padding: 0 10px; color: rgba(255, 255, 255, 0.9);">第 {{ tasksCurrentPage }} 页 / 共 {{ tasksTotalPages }} 页</span>
              
              <button 
                @click="goToTasksPage(tasksCurrentPage + 1)" 
                :disabled="tasksCurrentPage === tasksTotalPages"
                style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; cursor: pointer; border-radius: 6px; transition: all 0.3s ease;"
                :style="{ opacity: tasksCurrentPage === tasksTotalPages ? 0.5 : 1, cursor: tasksCurrentPage === tasksTotalPages ? 'not-allowed' : 'pointer' }"
                @mouseenter="if(tasksCurrentPage !== tasksTotalPages) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                @mouseleave="if(tasksCurrentPage !== tasksTotalPages) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
              >下一页</button>
            </div>
          </div>
          
          <!-- 日报数据标签页内容 -->
          <div v-else-if="huiwentaiActiveTab === 'daily-reports'" class="daily-reports-section">
            <div v-if="filteredHuiwentaiDailyReports.length === 0" style="padding: 40px; text-align: center; color: rgba(255, 255, 255, 0.9); background: rgba(30, 58, 138, 0.2); border-radius: 8px; border: 1px solid rgba(100, 149, 237, 0.3);">
              暂无日报数据
            </div>
            <div v-else class="reports-list" style="display: flex; flex-direction: column; gap: 16px; margin-top: 20px;">
              <div 
                v-for="report in paginatedHuiwentaiDailyReports" 
                :key="report._id"
                class="report-card"
                @click="toggleReportExpand(report)"
                style="border-radius: 10px; overflow: hidden; cursor: pointer; transition: all 0.3s ease; background: rgba(30, 58, 138, 0.3); backdrop-filter: blur(10px); border: 1px solid rgba(100, 149, 237, 0.3);"
                :style="{ 
                  transform: expandedReportId === (report._id || report.id) ? 'scale(1.01)' : 'scale(1)',
                  borderColor: expandedReportId === (report._id || report.id) ? 'rgba(100, 149, 237, 0.6)' : 'rgba(100, 149, 237, 0.3)',
                  boxShadow: expandedReportId === (report._id || report.id) ? '0 4px 16px rgba(0, 0, 0, 0.2)' : '0 2px 8px rgba(0, 0, 0, 0.1)'
                }"
              >
                <!-- 卡片头部 - 关键信息 -->
                <div 
                  class="report-summary" 
                  style="padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; transition: background-color 0.3s; background: rgba(30, 58, 138, 0.4);"
                >
                  <div style="display: flex; gap: 32px; align-items: center;">
                    <div style="min-width: 120px;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">日期</span>
                      <div style="font-size: 16px; font-weight: 600; color: white; margin-top: 4px;">
                        {{ parseReportSummary(report).date }}
                      </div>
                    </div>
                    <div style="min-width: 100px;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">值班人员</span>
                      <div style="font-size: 16px; color: white; margin-top: 4px;">
                        {{ parseReportSummary(report).person }}
                      </div>
                    </div>
                    <div style="min-width: 90px;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">班次</span>
                      <div style="margin-top: 4px;">
                        <span 
                          style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: 500; background: rgba(100, 149, 237, 0.3); color: white; border: 1px solid rgba(100, 149, 237, 0.5);"
                        >
                          {{ parseReportSummary(report).shift }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div style="display: flex; gap: 24px; align-items: center;">
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">上报</span>
                      <div style="font-size: 20px; font-weight: 600; color: #87ceeb; margin-top: 4px;">
                        {{ parseReportSummary(report).reported }}
                      </div>
                    </div>
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">受理</span>
                      <div style="font-size: 20px; font-weight: 600; color: #90ee90; margin-top: 4px;">
                        {{ parseReportSummary(report).accepted }}
                      </div>
                    </div>
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: rgba(255, 255, 255, 0.7);">办结</span>
                      <div style="font-size: 20px; font-weight: 600; color: #ffb6c1; margin-top: 4px;">
                        {{ parseReportSummary(report).completed }}
                      </div>
                    </div>
                    <div style="margin-left: 16px; color: rgba(255, 255, 255, 0.7); font-size: 20px;">
                      {{ expandedReportId === (report._id || report.id) ? '▼' : '▶' }}
                    </div>
                  </div>
                </div>
                
                <!-- 展开的详细内容 -->
                <div 
                  v-if="expandedReportId === (report._id || report.id)"
                  class="report-detail"
                  style="padding: 24px 20px; border-top: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.2);"
                >
                  <div style="white-space: pre-wrap; line-height: 2.2; color: rgba(255, 255, 255, 0.9); font-size: 15px; font-family: 'Microsoft YaHei', sans-serif;">
                    {{ formatReportContent(report) }}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 日报数据分页组件 -->
            <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 8px;">
              <button 
                @click="goToReportsPage(reportsCurrentPage - 1)" 
                :disabled="reportsCurrentPage === 1"
                style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; cursor: pointer; border-radius: 6px; transition: all 0.3s ease;"
                :style="{ opacity: reportsCurrentPage === 1 ? 0.5 : 1, cursor: reportsCurrentPage === 1 ? 'not-allowed' : 'pointer' }"
                @mouseenter="if(reportsCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                @mouseleave="if(reportsCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
              >上一页</button>
              
              <span style="padding: 0 10px; color: rgba(255, 255, 255, 0.9);">第 {{ reportsCurrentPage }} 页 / 共 {{ reportsTotalPages }} 页</span>
              
              <button 
                @click="goToReportsPage(reportsCurrentPage + 1)" 
                :disabled="reportsCurrentPage === reportsTotalPages"
                style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; cursor: pointer; border-radius: 6px; transition: all 0.3s ease;"
                :style="{ opacity: reportsCurrentPage === reportsTotalPages ? 0.5 : 1, cursor: reportsCurrentPage === reportsTotalPages ? 'not-allowed' : 'pointer' }"
                @mouseenter="if(reportsCurrentPage !== reportsTotalPages) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                @mouseleave="if(reportsCurrentPage !== reportsTotalPages) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
              >下一页</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 考核计分模块 -->
      <div v-if="activeModule === 'assessment' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.assessment))" class="tab-content">
        <!-- 标签页导航 -->
        <div class="assessment-tabs" style="display: flex; margin-bottom: 20px; border-bottom: 1px solid #dee2e6;">
          <div 
            class="assessment-tab" 
            :class="{ active: assessmentActiveTab === 'old' }"
            @click="assessmentActiveTab = 'old'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="assessmentActiveTab === 'old' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : {}"
          >
            考核计分（原版）
          </div>
          <div 
            class="assessment-tab" 
            :class="{ active: assessmentActiveTab === 'new' }"
            @click="assessmentActiveTab = 'new'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="assessmentActiveTab === 'new' ? { borderBottomColor: '#4facfe', color: '#4facfe' } : {}"
          >
            考核计分（新版）
          </div>
        </div>
        
        <div class="assessment-section" style="max-width: 900px; margin: 0 auto; min-height: 600px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 8px; padding: 20px;">
          <!-- 原版考核计分内容 -->
          <div v-if="assessmentActiveTab === 'old'">
            <!-- 说明信息 -->
            <div style="margin-bottom: 25px; padding: 16px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-left: 4px solid #4facfe; border-radius: 6px; color: rgba(255, 255, 255, 0.8);">
              <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span style="font-size: 20px; flex-shrink: 0;">⚠️</span>
                <div>
                  <div style="font-weight: 600; margin-bottom: 6px; color: #4facfe;">计算说明</div>
                  <p style="margin: 0; line-height: 1.5; font-size: 14px;">超时案件计算：结案时间 > 捆绑处置截止时间判定的，与实际超时计算有出入</p>
                </div>
              </div>
            </div>
            
            <!-- 配置区域 -->
            <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
                <div>
                  <label for="department-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择部门：</label>
                  <select id="department-select" v-model="selectedDepartment" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                    <option value="">-- 请选择部门 --</option>
                    <option value="城市综合行政执法队">城市综合行政执法队</option>
                    <option value="市容环卫中心">市容环卫中心</option>
                    <option value="园林绿化服务中心（片区）">园林绿化服务中心（片区）</option>
                    <option value="园林绿化服务中心（公园广场）">园林绿化服务中心（公园广场）</option>
                  </select>
                </div>
                <div>
                  <label for="table-select-assessment" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择数据表：</label>
                  <select id="table-select-assessment" v-model="selectedAssessmentTable" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                    <option value="">-- 请选择 --</option>
                    <option v-for="table in tables" :key="table" :value="table">
                      {{ table }}
                    </option>
                  </select>
                </div>
              </div>
              
              <!-- 操作按钮 -->
              <button 
                class="start-btn" 
                @click="startAssessment" 
                :disabled="loading || !selectedDepartment || !selectedAssessmentTable"
                style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
                @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
                @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
              >
                <span v-if="loading">⏳ 计算中...</span>
                <span v-else>📊 开始计算</span>
              </button>
              
              <!-- 消息提示 -->
              <div v-if="assessmentMessage" style="margin-top: 15px; padding: 12px; background-color: rgba(76, 175, 80, 0.2); color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(76, 175, 80, 0.4); border-radius: 4px; backdrop-filter: blur(5px);">
                ✓ {{ assessmentMessage }}
              </div>
            </div>
            
            <!-- 考核结果显示 -->
            <div v-if="assessmentResult" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15); margin-top: 20px; border: 1px solid rgba(255, 255, 255, 0.2);">
              <h3 style="margin: 0 0 20px 0; padding-bottom: 15px; border-bottom: 2px solid #4facfe; font-size: 20px; color: white;">📋 考核结果</h3>
              
              <!-- 结果摘要 -->
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px;">
                <div style="padding: 20px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 8px; color: white;">
                  <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">总案件数</div>
                  <div style="font-size: 32px; font-weight: bold;">{{ assessmentResult.total_cases }}</div>
                </div>
                <div style="padding: 20px; background: linear-gradient(135deg, #00c6fb 0%, #005bea 100%); border-radius: 8px; color: white;">
                  <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">平均得分</div>
                  <div style="font-size: 32px; font-weight: bold;">{{ assessmentResult.score }} 分</div>
                </div>
              </div>
              
              <!-- 排名表格 -->
              <div v-if="assessmentResult.team_results">
                <h4 style="margin: 0 0 15px 0; color: white; font-size: 16px;">🏆 片区排名</h4>
                <div style="overflow-x: auto;">
                  <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                      <tr style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
                        <th style="padding: 12px; text-align: center; font-weight: 600;">排名</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600;">片区名称</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">案件总数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">按期结案</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">超期结案</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">延期次数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">返工次数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">得分</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(team, index) in assessmentResult.team_results" :key="team.department" :style="{ backgroundColor: index % 2 === 0 ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.1)', transition: 'all 0.3s ease' }" @mouseenter="$event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.15)'" @mouseleave="$event.currentTarget.style.backgroundColor=(index % 2 === 0 ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.1)')">
                        <td style="padding: 12px; text-align: center; font-weight: 600; color: #4facfe;">
                          <span style="display: inline-block; width: 32px; height: 32px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 50%; line-height: 32px; font-size: 14px;">{{ team.rank }}</span>
                        </td>
                        <td style="padding: 12px; text-align: left; color: white;">{{ team.department }}</td>
                        <td style="padding: 12px; text-align: center; color: rgba(255, 255, 255, 0.8);">{{ team.total_cases }}</td>
                        <td style="padding: 12px; text-align: center; color: #2ecc71; font-weight: 600;">{{ team.on_time_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #e74c3c; font-weight: 600;">{{ team.overdue_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #f39c12;">{{ team.delay_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #9b59b6;">{{ team.rework_count }}</td>
                        <td style="padding: 12px; text-align: center; font-weight: bold; font-size: 16px;">
                          <span style="display: inline-block; padding: 4px 12px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 20px;">{{ team.score }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 新版考核计分内容 -->
          <div v-if="assessmentActiveTab === 'new'">
            <!-- 说明信息 -->
            <div style="margin-bottom: 25px; padding: 16px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-left: 4px solid #4facfe; border-radius: 6px; color: rgba(255, 255, 255, 0.8);">
              <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span style="font-size: 20px; flex-shrink: 0;">ℹ️</span>
                <div>
                  <div style="font-weight: 600; margin-bottom: 6px; color: #4facfe;">计算说明</div>
                  <p style="margin: 0; line-height: 1.5; font-size: 14px;">超时案件计算：根据表中"是否超时"字段判定，为空表示不超时，不为空表示超时</p>
                </div>
              </div>
            </div>
            
            <!-- 配置区域 -->
            <div style="padding: 25px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);">
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
                <div>
                  <label for="department-select-v2" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择部门：</label>
                  <select id="department-select-v2" v-model="selectedDepartmentV2" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                    <option value="">-- 请选择部门 --</option>
                    <option value="城市综合行政执法队">城市综合行政执法队</option>
                    <option value="市容环卫中心">市容环卫中心</option>
                    <option value="园林绿化服务中心（片区）">园林绿化服务中心（片区）</option>
                    <option value="园林绿化服务中心（公园广场）">园林绿化服务中心（公园广场）</option>
                  </select>
                </div>
                <div>
                  <label for="table-select-assessment-v2" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">选择数据表：</label>
                  <select id="table-select-assessment-v2" v-model="selectedAssessmentTableV2" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                    <option value="">-- 请选择 --</option>
                    <option v-for="table in tables" :key="table" :value="table">
                      {{ table }}
                    </option>
                  </select>
                </div>
              </div>
              
              <!-- 操作按钮 -->
              <button 
                class="start-btn" 
                @click="startAssessmentV2" 
                :disabled="loading || !selectedDepartmentV2 || !selectedAssessmentTableV2"
                style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
                @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'"
                @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
              >
                <span v-if="loading">⏳ 计算中...</span>
                <span v-else>📊 开始计算</span>
              </button>
              
              <!-- 消息提示 -->
              <div v-if="assessmentMessageV2" style="margin-top: 15px; padding: 12px; background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.4); border-radius: 4px; backdrop-filter: blur(10px);">
                ✓ {{ assessmentMessageV2 }}
              </div>
            </div>
            
            <!-- 考核结果显示 -->
            <div v-if="assessmentResultV2" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15); border: 1px solid rgba(255, 255, 255, 0.2);">
              <h3 style="margin: 0 0 20px 0; padding-bottom: 15px; border-bottom: 2px solid #4facfe; font-size: 20px; color: white;">📋 考核结果</h3>
              
              <!-- 结果摘要 -->
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px;">
                <div style="padding: 20px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 8px; color: white;">
                  <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">总案件数</div>
                  <div style="font-size: 32px; font-weight: bold;">{{ assessmentResultV2.total_cases }}</div>
                </div>
                <div style="padding: 20px; background: linear-gradient(135deg, #00c6fb 0%, #005bea 100%); border-radius: 8px; color: white;">
                  <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">平均得分</div>
                  <div style="font-size: 32px; font-weight: bold;">{{ assessmentResultV2.score }} 分</div>
                </div>
              </div>
              
              <!-- 排名表格 -->
              <div v-if="assessmentResultV2.team_results">
                <h4 style="margin: 0 0 15px 0; color: white; font-size: 16px;">🏆 片区排名</h4>
                <div style="overflow-x: auto;">
                  <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                      <tr style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
                        <th style="padding: 12px; text-align: center; font-weight: 600;">排名</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600;">片区名称</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">案件总数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">按期结案</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">超期结案</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">延期次数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">返工次数</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">得分</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(team, index) in assessmentResultV2.team_results" :key="team.department" :style="{ backgroundColor: index % 2 === 0 ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.1)', transition: 'all 0.3s ease' }" @mouseenter="$event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.15)'" @mouseleave="$event.currentTarget.style.backgroundColor=(index % 2 === 0 ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.1)')">
                        <td style="padding: 12px; text-align: center; font-weight: 600; color: #4facfe;">
                          <span style="display: inline-block; width: 32px; height: 32px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 50%; line-height: 32px; font-size: 14px;">{{ team.rank }}</span>
                        </td>
                        <td style="padding: 12px; text-align: left; color: white;">{{ team.department }}</td>
                        <td style="padding: 12px; text-align: center; color: rgba(255, 255, 255, 0.8);">{{ team.total_cases }}</td>
                        <td style="padding: 12px; text-align: center; color: #2ecc71; font-weight: 600;">{{ team.on_time_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #e74c3c; font-weight: 600;">{{ team.overdue_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #f39c12;">{{ team.delay_count }}</td>
                        <td style="padding: 12px; text-align: center; color: #9b59b6;">{{ team.rework_count }}</td>
                        <td style="padding: 12px; text-align: center; font-weight: bold; font-size: 16px;">
                          <span style="display: inline-block; padding: 4px 12px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 20px;">{{ team.score }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 案件管理模块 -->
      <div v-if="activeModule === 'cases'" class="tab-content">
        <div class="cases-section" style="max-width: 1200px; margin: 0 auto;">
          <!-- 导入区域 -->
          <div style="background: rgba(30, 58, 138, 0.4); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(100, 149, 237, 0.3); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);">
            <h3 style="margin: 0 0 15px 0; font-size: 18px; color: white; border-bottom: 1px solid rgba(100, 149, 237, 0.3); padding-bottom: 10px;">导入案件数据</h3>
            
            <div style="display: flex; gap: 15px; align-items: center; margin-top: 15px;">
              <input 
                type="file" 
                @change="handleCaseFileSelect" 
                accept=".xlsx"
                style="flex: 1; padding: 10px 12px; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; background: rgba(30, 58, 138, 0.6); color: white;"
              >
              <button 
                @click="importCases"
                :disabled="caseImportLoading || !caseImportFile"
                style="padding: 10px 20px; background: linear-gradient(135deg, rgba(30, 58, 138, 0.8) 0%, rgba(45, 74, 154, 0.8) 100%); color: white; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s ease;"
              >
                {{ caseImportLoading ? '导入中...' : '开始导入' }}
              </button>
            </div>
            
            <div v-if="caseImportMessage" style="margin-top: 10px; padding: 12px; background: rgba(76, 175, 80, 0.2); border: 1px solid rgba(76, 175, 80, 0.4); border-radius: 6px; color: rgba(255, 255, 255, 0.9); backdrop-filter: blur(5px);">
              {{ caseImportMessage }}
            </div>
            
            <div v-if="casesError" style="margin-top: 10px; padding: 12px; background: rgba(244, 67, 54, 0.2); border: 1px solid rgba(244, 67, 54, 0.4); border-radius: 6px; color: rgba(255, 255, 255, 0.9); backdrop-filter: blur(5px);">
              {{ casesError }}
            </div>
          </div>
          
          <!-- 搜索区域 -->
          <div style="background: rgba(30, 58, 138, 0.4); backdrop-filter: blur(10px); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid rgba(100, 149, 237, 0.3); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);">
            <div style="display: flex; gap: 15px; align-items: center;">
              <input 
                v-model="casesSearch"
                placeholder="搜索任务号、问题描述、地址..."
                @keyup.enter="searchCases"
                style="flex: 1; padding: 10px 12px; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; background: rgba(30, 58, 138, 0.6); color: white;"
              >
              <button 
                @click="searchCases"
                style="padding: 10px 20px; background: linear-gradient(135deg, rgba(30, 58, 138, 0.8) 0%, rgba(45, 74, 154, 0.8) 100%); color: white; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s ease;"
              >
                搜索
              </button>
            </div>
          </div>
          
          <!-- 案件列表 -->
          <div v-if="!showCaseDetail" style="background: rgba(30, 58, 138, 0.3); backdrop-filter: blur(10px); border-radius: 12px; border: 1px solid rgba(100, 149, 237, 0.3); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15); overflow: hidden;">
            <div v-if="casesLoading" style="padding: 40px; text-align: center; color: rgba(255, 255, 255, 0.9);">
              加载中...
            </div>
            
            <div v-else-if="casesList.length === 0" style="padding: 40px; text-align: center; color: rgba(255, 255, 255, 0.9);">
              暂无案件数据
            </div>
            
            <div v-else style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse;">
                <thead>
                  <tr style="background: rgba(30, 58, 138, 0.6);">
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">任务号</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">上报时间</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">问题来源</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">大类</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">小类</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">问题描述</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">地址</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">状态</th>
                    <th style="padding: 14px 12px; border: 1px solid rgba(100, 149, 237, 0.3); text-align: left; color: white; font-weight: 600;">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="caseItem in casesList" :key="caseItem.id" style="cursor: pointer; background: rgba(30, 58, 138, 0.2);" @click="viewCaseDetail(caseItem.id)" @mouseenter="$event.currentTarget.style.background='rgba(100, 149, 237, 0.2)'" @mouseleave="$event.currentTarget.style.background='rgba(30, 58, 138, 0.2)'">
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ caseItem.task_number }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ caseItem.report_time }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ caseItem.source }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ caseItem.major_category }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">{{ caseItem.minor_category }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ caseItem.problem_desc }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ caseItem.address_desc }}</td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2); color: rgba(255, 255, 255, 0.9);">
                      <span :style="{ color: caseItem.stage_light === '绿' ? '#90ee90' : caseItem.stage_light === '黄' ? '#ffd700' : '#ffb6c1', fontWeight: '600' }">{{ caseItem.stage_light }}</span>
                    </td>
                    <td style="padding: 12px; border: 1px solid rgba(100, 149, 237, 0.2);">
                      <button @click.stop="viewCaseDetail(caseItem.id)" style="padding: 6px 14px; background: rgba(30, 58, 138, 0.6); color: white; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.3s ease;" @mouseenter="$event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.8)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'" @mouseleave="$event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'">
                        查看
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
              
              <!-- 分页 -->
              <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 8px;">
                <button 
                  @click="handleCasesPageChange(casesCurrentPage - 1)"
                  :disabled="casesCurrentPage === 1"
                  style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; border-radius: 6px; cursor: pointer; transition: all 0.3s ease;"
                  :style="{ opacity: casesCurrentPage === 1 ? 0.5 : 1, cursor: casesCurrentPage === 1 ? 'not-allowed' : 'pointer' }"
                  @mouseenter="if(casesCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                  @mouseleave="if(casesCurrentPage !== 1) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
                >
                  上一页
                </button>
                <span style="color: rgba(255, 255, 255, 0.9);">第 {{ casesCurrentPage }} / {{ Math.ceil(casesTotal / casesPageSize) }} 页</span>
                <button 
                  @click="handleCasesPageChange(casesCurrentPage + 1)"
                  :disabled="casesCurrentPage >= Math.ceil(casesTotal / casesPageSize)"
                  style="padding: 8px 16px; border: 1px solid rgba(100, 149, 237, 0.3); background: rgba(30, 58, 138, 0.6); color: white; border-radius: 6px; cursor: pointer; transition: all 0.3s ease;"
                  :style="{ opacity: casesCurrentPage >= Math.ceil(casesTotal / casesPageSize) ? 0.5 : 1, cursor: casesCurrentPage >= Math.ceil(casesTotal / casesPageSize) ? 'not-allowed' : 'pointer' }"
                  @mouseenter="if(casesCurrentPage < Math.ceil(casesTotal / casesPageSize)) { $event.target.style.background='rgba(30, 58, 138, 0.8)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.5)'; $event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(0, 0, 0, 0.2)'; }"
                  @mouseleave="if(casesCurrentPage < Math.ceil(casesTotal / casesPageSize)) { $event.target.style.background='rgba(30, 58, 138, 0.6)'; $event.target.style.borderColor='rgba(100, 149, 237, 0.3)'; $event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'; }"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
          
          <!-- 案件详情 -->
          <div v-if="showCaseDetail && currentCase" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15); border: 1px solid rgba(255, 255, 255, 0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #4facfe; padding-bottom: 15px;">
              <h3 style="margin: 0; color: #4facfe; font-size: 20px;">案件详情</h3>
              <button @click="showCaseDetail = false; currentCase = null;" style="padding: 10px 20px; background: rgba(255, 255, 255, 0.2); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; cursor: pointer; font-weight: 500; transition: all 0.3s ease;">
                返回列表
              </button>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">任务号</p>
                <p style="margin: 0; font-size: 16px; font-weight: 600; color: white;">{{ currentCase.task_number }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">上报时间</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.report_time }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">问题来源</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.source }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">问题类型</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.problem_type }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">大类名称</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.major_category }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">小类名称</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.minor_category }}</p>
              </div>
            </div>
            
            <div style="margin-top: 20px;">
              <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">问题描述</p>
              <p style="margin: 0; font-size: 15px; padding: 12px 15px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(255, 255, 255, 0.15);">{{ currentCase.problem_desc }}</p>
            </div>
            
            <div style="margin-top: 20px;">
              <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">地址描述</p>
              <p style="margin: 0; font-size: 15px; padding: 12px 15px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; color: rgba(255, 255, 255, 0.9); border: 1px solid rgba(255, 255, 255, 0.15);">{{ currentCase.address_desc }}</p>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 20px;">
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">所属区域</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.area }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">所属街道</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.street }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">所属社区</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.community }}</p>
              </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 20px;">
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">责任网格</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.responsible_grid }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">批转时间</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.transfer_time }}</p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">当前阶段剩余时间</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.current_stage_remaining_time }}</p>
              </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">阶段红绿灯</p>
                <p style="margin: 0; font-size: 16px;">
                  <span style="font-weight: bold; color: #52c41b;" v-if="currentCase.stage_light == '绿'">{{ currentCase.stage_light }}</span>
                  <span style="font-weight: bold; color: #ff9800;" v-else-if="currentCase.stage_light == '黄'">{{ currentCase.stage_light }}</span>
                  <span style="font-weight: bold; color: #f44336;" v-else>{{ currentCase.stage_light }}</span>
                </p>
              </div>
              <div>
                <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">区域级别</p>
                <p style="margin: 0; font-size: 16px; color: rgba(255, 255, 255, 0.9);">{{ currentCase.area_level_name }}</p>
              </div>
            </div>
            
            <!-- 照片展示 -->
            <div v-if="currentCase.photo_path" style="margin-top: 20px;">
              <p style="margin: 0 0 10px 0; color: rgba(255, 255, 255, 0.6); font-size: 13px;">案件照片</p>
              <div style="padding: 15px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; text-align: center; border: 1px solid rgba(255, 255, 255, 0.15);">
                <div style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;">
                  <img 
                    v-for="(photo, index) in getPhotoPaths(currentCase.photo_path)" 
                    :key="index"
                    :src="photo" 
                    :alt="'案件照片 ' + (index + 1)" 
                    style="max-width: 100%; max-height: 400px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);" 
                    @error="handleImageError"
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 地图服务模块 -->
      <div v-if="activeModule === 'map' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.map))" class="tab-content">
        <div class="map-section">
          <div v-if="mapLoading" class="loading">
            地图加载中...
          </div>
          <div v-else-if="mapError" class="error">
            {{ mapError }}
          </div>
          <div v-else id="map-container" style="width: 100%; height: 600px; border-radius: 8px;"></div>
          <div class="map-info" style="margin-top: 20px; padding: 20px; border-radius: 8px;">
            <h3>地图服务说明</h3>
            <p>• 显示运城市地图</p>
            <p>• 标记案件位置</p>
            <p>• 支持热力图展示（数据足够时）</p>
            <p>• 点击标记查看案件详情</p>
          </div>
        </div>
      </div>

      <!-- 管理员管理模块 -->
      <div v-if="activeModule === 'admin' && (!userInfo || userInfo.role === 'admin')" class="tab-content">
        <div class="admin-section">
          <div class="admin-tabs">
            <div class="admin-tab" :class="{ active: adminActiveTab === 'users' }" @click="adminActiveTab = 'users'">
              用户管理
            </div>
            <div class="admin-tab" :class="{ active: adminActiveTab === 'business' }" @click="adminActiveTab = 'business'">
              业务管理
            </div>
            <div class="admin-tab" :class="{ active: adminActiveTab === 'system' }" @click="adminActiveTab = 'system'">
              系统配置
            </div>
          </div>
          
          <!-- 用户管理子模块 -->
          <div v-if="adminActiveTab === 'users'" class="admin-subsection">
            <div class="user-management">
              <div class="user-actions">
                <button class="add-user-btn" @click="addNewUser">添加用户</button>
              </div>
              <div class="user-list">
                <table class="user-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>用户名</th>
                      <th>角色</th>
                      <th>创建时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="user in users" :key="user.id">
                      <td>{{ user.id }}</td>
                      <td>{{ user.username }}</td>
                      <td>{{ user.role }}</td>
                      <td>{{ user.created_at }}</td>
                      <td>
                        <button class="edit-user-btn" @click="editUser(user)">编辑</button>
                        <button class="delete-user-btn" @click="deleteUser(user.id)" :disabled="user.id === 1">删除</button>
                        <button v-if="user.role !== 'admin'" class="edit-permissions-btn" @click="editUserPermissions(user)">权限</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          
          <!-- 业务管理子模块 -->
          <div v-if="adminActiveTab === 'business'" class="admin-subsection">
            <!-- 配置标签页 -->
            <div class="config-tabs">
              <button class="config-tab" :class="{ active: businessTab === 'data' }" @click="businessTab = 'data'">数据管理</button>
              <button class="config-tab" :class="{ active: businessTab === 'cms' }" @click="businessTab = 'cms'">内容管理</button>
              <button class="config-tab" :class="{ active: businessTab === 'business-platforms' }" @click="businessTab = 'business-platforms'">业务平台</button>
              <button class="config-tab" :class="{ active: businessTab === 'assessment' }" @click="businessTab = 'assessment'">考核计分</button>
              <button class="config-tab" :class="{ active: businessTab === 'tools' }" @click="businessTab = 'tools'">小工具</button>
            </div>
            
            <!-- 配置内容 -->
            <div class="config-content">
              <!-- 数据管理配置 -->
              <div v-if="businessTab === 'data'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">数据库管理</h4>
                  <p class="panel-description">管理数据库中的数据表，可上传Excel文件和删除不需要的数据表</p>
                </div>
                <div class="panel-body">
                  <!-- Excel上传功能 -->
                  <div class="data-management" style="margin-bottom: 25px;">
                    <h5 class="management-title" style="margin-bottom: 12px;">Excel数据上传</h5>
                    <div class="upload-section" style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                      <div class="file-selector" style="display: flex; align-items: center; gap: 10px;">
                        <input type="file" accept=".xlsx" @change="handleFileSelect" :disabled="loading" />
                        <span class="file-name">{{ selectedFile ? selectedFile.name : '未选择任何文件' }}</span>
                      </div>
                      <button class="upload-btn" @click="uploadFile" :disabled="loading || !selectedFile">
                        {{ loading ? '上传中...' : '上传并导入数据库' }}
                      </button>
                      <div class="upload-status">
                        <span class="status-label">状态：</span>
                        <span class="status-value">{{ message || '等待上传' }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- 数据表管理 -->
                  <div class="table-management">
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 12px;">
                      <h5 class="management-title" style="margin: 0;">数据表管理</h5>
                      <button class="refresh-btn" @click="fetchTablesForManagement" :disabled="adminLoading">
                        {{ adminLoading ? '加载中...' : '刷新数据表' }}
                      </button>
                    </div>
                    <div v-if="tables.length > 0" class="table-list">
                      <table class="table-table">
                        <thead>
                          <tr>
                            <th>表名</th>
                            <th>对用户可见</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="table in tables" :key="table">
                            <td>{{ table }}</td>
                            <td>
                              <input type="checkbox" v-model="tableVisibility[table]" @change="saveTableVisibility" :disabled="adminLoading" />
                            </td>
                            <td>
                              <button class="delete-table-btn" @click="deleteTable(table)" :disabled="adminLoading">
                                删除
                              </button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-else-if="!adminLoading" class="empty-state">
                      <p>暂无数据表</p>
                    </div>
                    <div v-if="adminError" class="admin-error">{{ adminError }}</div>
                  </div>

                  <!-- 数据表可见性配置 -->
                  <div class="table-visibility-config" style="margin-top: 20px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                      <h5 class="management-title" style="margin: 0;">数据表可见性配置</h5>
                      <button class="save-visibility-btn" @click="saveTableVisibility" :disabled="adminLoading" style="padding: 6px 14px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 4px; cursor: pointer;">
                        {{ adminLoading ? '保存中...' : '保存配置' }}
                      </button>
                    </div>
                    <p class="config-description" style="margin-top: 8px; margin-bottom: 0; font-size: 13px; color: rgba(255, 255, 255, 0.7);">配置哪些数据表对前端用户可见，用户只能选择可见的数据表进行分析和考核。</p>
                  </div>
                </div>
              </div>
              
              <!-- CMS内容管理 -->
              <div v-if="businessTab === 'cms'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">内容管理</h4>
                  <p class="panel-description">管理系统内容，包括栏目和文章</p>
                </div>
                <div class="panel-body">
                  <!-- 栏目管理 -->
                  <div class="cms-management">
                    <h5 class="management-title">栏目管理</h5>
                    <button class="add-btn" @click="addNewCategory">添加栏目</button>
                    <div v-if="cmsCategories.length > 0" class="category-list">
                      <table class="category-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>名称</th>
                            <th>Slug</th>
                            <th>排序</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="category in cmsCategories" :key="category.id">
                            <td>{{ category.id }}</td>
                            <td>{{ category.name }}</td>
                            <td>{{ category.slug }}</td>
                            <td>{{ category.order }}</td>
                            <td>
                              <button class="edit-btn" @click="editCategory(category)">编辑</button>
                              <button class="delete-btn" @click="deleteCategory(category.id)">删除</button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-else class="empty-state">
                      <p>暂无栏目</p>
                    </div>
                  </div>
                  
                  <!-- 文章管理 -->
                  <div class="cms-management" style="margin-top: 30px;">
                    <h5 class="management-title">文章管理</h5>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                      <div style="display: flex; align-items: center; gap: 10px;">
                        <label style="font-size: 14px;">选择栏目：</label>
                        <select v-model="selectedCategory" @change="switchCMSCategory(selectedCategory)" style="padding: 8px 12px; border: 1px solid rgba(100, 149, 237, 0.5); border-radius: 6px; font-size: 14px; background: rgba(30, 58, 138, 0.6); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                          <option :value="allCategoryOption">全部</option>
                          <option v-for="category in cmsCategories" :key="category.id" :value="category">
                            {{ category.name }}
                          </option>
                        </select>
                      </div>
                      <button class="add-btn" @click="addNewArticle">添加文章</button>
                    </div>
                    <div v-if="cmsArticles.length > 0" class="article-list">
                      <table class="article-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>标题</th>
                            <th>栏目</th>
                            <th>状态</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="article in cmsArticles" :key="article.id">
                            <td>{{ article.id }}</td>
                            <td>{{ article.title }}</td>
                            <td>{{ getCategoryName(article.category_id) }}</td>
                            <td>{{ article.status === 'draft' ? '草稿' : '已发布' }}</td>
                            <td>
                              <button class="edit-btn" @click="editArticle(article)">编辑</button>
                              <button class="delete-btn" @click="deleteArticle(article.id)">删除</button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                      
                      <!-- 分页控件 -->
                      <div v-if="cmsArticlesTotal > 0" class="pagination">
                        <span class="pagination-info">共 {{ cmsArticlesTotal }} 条，第 {{ cmsArticlesPage }}/{{ cmsArticlesPages }} 页</span>
                        <div class="pagination-buttons">
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id === 'all' ? 'all' : selectedCategory?.id, 1)" :disabled="cmsArticlesPage === 1">首页</button>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id === 'all' ? 'all' : selectedCategory?.id, cmsArticlesPage - 1)" :disabled="cmsArticlesPage === 1">上一页</button>
                          <template v-for="page in getPageNumbers()" :key="page">
                            <button v-if="page !== '...'" class="page-btn" :class="{ active: page === cmsArticlesPage }" @click="fetchCMSArticles(selectedCategory?.id === 'all' ? 'all' : selectedCategory?.id, page)">
                              {{ page }}
                            </button>
                            <span v-else class="page-ellipsis">...</span>
                          </template>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id === 'all' ? 'all' : selectedCategory?.id, cmsArticlesPage + 1)" :disabled="cmsArticlesPage === cmsArticlesPages">下一页</button>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id === 'all' ? 'all' : selectedCategory?.id, cmsArticlesPages)" :disabled="cmsArticlesPage === cmsArticlesPages">末页</button>
                        </div>
                      </div>
                    </div>
                    <div v-else class="empty-state">
                      <p>暂无文章</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 业务平台管理 -->
              <div v-if="businessTab === 'business-platforms'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">业务平台管理</h4>
                  <p class="panel-description">管理系统的业务平台信息</p>
                </div>
                <div class="panel-body">
                  <!-- 平台列表 -->
                  <div class="cms-management">
                    <h5 class="management-title">平台列表</h5>
                    <button class="add-btn" @click="showAddPlatformForm = true">添加业务平台</button>
                    <div v-if="businessPlatforms.length > 0" class="category-list">
                      <table class="category-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>平台名称</th>
                            <th>平台地址</th>
                            <th>封面图片</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="platform in businessPlatforms" :key="platform.id">
                            <td>{{ platform.id }}</td>
                            <td>{{ platform.name }}</td>
                            <td><a :href="platform.url" target="_blank">{{ platform.url }}</a></td>
                            <td>
                              <img v-if="platform.image_path" :src="platform.image_path" alt="" class="platform-image" width="100">
                              <span v-else>-</span>
                            </td>
                            <td>
                              <button class="edit-btn" @click="startEditPlatform(platform)">编辑</button>
                              <button class="delete-btn" @click="deleteBusinessPlatform(platform.id)">删除</button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-else class="empty-state">
                      <p>暂无业务平台</p>
                    </div>
                  </div>
                  
                  <!-- 添加平台表单 -->
                  <div v-if="showAddPlatformForm" class="cms-management" style="margin-top: 30px;">
                    <h5 class="management-title">添加业务平台</h5>
                    <div class="form-group mb-3">
                      <label for="platform-name">平台名称</label>
                      <input type="text" v-model="newPlatform.name" class="form-control" id="platform-name" placeholder="输入平台名称">
                    </div>
                    <div class="form-group mb-3">
                      <label for="platform-url">平台地址</label>
                      <input type="url" v-model="newPlatform.url" class="form-control" id="platform-url" placeholder="输入平台地址">
                    </div>
                    <div class="form-group mb-3">
                      <label for="platform-image">封面图片</label>
                      <input type="file" @change="uploadPlatformImage" class="form-control" id="platform-image" accept="image/*">
                      <div v-if="platformFileUploadLoading" class="mt-2 text-info">上传中...</div>
                      <div v-if="platformFileUploadError" class="mt-2 text-danger">{{ platformFileUploadError }}</div>
                      <img v-if="newPlatform.image_path" :src="newPlatform.image_path" alt="预览" class="platform-image-preview mt-2" width="200">
                    </div>
                    <div v-if="platformError" class="mt-2 text-danger">{{ platformError }}</div>
                    <div class="form-actions mt-3">
                      <button class="add-btn" @click="addBusinessPlatform" :disabled="platformLoading">{{ platformLoading ? '添加中...' : '添加' }}</button>
                      <button class="cancel-btn" @click="cancelAddPlatform">取消</button>
                    </div>
                  </div>
                  
                  <!-- 编辑平台表单 -->
                  <div v-if="editingPlatform" class="cms-management" style="margin-top: 30px;">
                    <h5 class="management-title">编辑业务平台</h5>
                    <div class="form-group mb-3">
                      <label for="edit-platform-name">平台名称</label>
                      <input type="text" v-model="editingPlatform.name" class="form-control" id="edit-platform-name" placeholder="输入平台名称">
                    </div>
                    <div class="form-group mb-3">
                      <label for="edit-platform-url">平台地址</label>
                      <input type="url" v-model="editingPlatform.url" class="form-control" id="edit-platform-url" placeholder="输入平台地址">
                    </div>
                    <div class="form-group mb-3">
                      <label for="edit-platform-image">封面图片</label>
                      <input type="file" @change="uploadPlatformImage" class="form-control" id="edit-platform-image" accept="image/*">
                      <div v-if="platformFileUploadLoading" class="mt-2 text-info">上传中...</div>
                      <div v-if="platformFileUploadError" class="mt-2 text-danger">{{ platformFileUploadError }}</div>
                      <img v-if="editingPlatform.image_path" :src="editingPlatform.image_path" alt="预览" class="platform-image-preview mt-2" width="200">
                    </div>
                    <div v-if="platformError" class="mt-2 text-danger">{{ platformError }}</div>
                    <div class="form-actions mt-3">
                      <button class="add-btn" @click="updateBusinessPlatform" :disabled="platformLoading">{{ platformLoading ? '更新中...' : '更新' }}</button>
                      <button class="cancel-btn" @click="cancelEditPlatform">取消</button>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 考核计分配置 -->
              <div v-if="businessTab === 'assessment'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">考核计分系数配置</h4>
                  <p class="panel-description">
                    计分公式：score = ( (on_time_rate × 按时结案系数 + overdue_rate × 超时结案系数) × 结案率权重 + (1 - delay_rate) × 延期率权重 + (1 - rework_rate) × 返工率权重 ) × 100
                  </p>
                </div>
                
                <div class="panel-body">
                  <div v-if="assessmentCoefficientsLoading" class="loading" style="text-align: center; padding: 40px; color: rgba(255, 255, 255, 0.7);">
                    加载中...
                  </div>
                  
                  <div v-else>
                    <!-- 部门选择器 -->
                    <div class="form-group" style="margin-bottom: 25px;">
                      <label style="display: block; font-weight: 600; margin-bottom: 8px; color: rgba(255, 255, 255, 0.9);">选择考核部门</label>
                      <select 
                        v-model="selectedAssessmentDepartment" 
                        style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;"
                      >
                        <option v-for="dept in assessmentDepartments" :key="dept" :value="dept">
                          {{ dept }}
                        </option>
                      </select>
                    </div>
                    
                    <div class="config-form" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                      <div class="form-group">
                        <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #333;">按时结案系数 (on_time)</label>
                        <input 
                          type="number" 
                          step="0.1" 
                          v-model.number="getCurrentDeptCoefficients().on_time" 
                          placeholder="1.0"
                          style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;"
                        />
                      </div>
                      
                      <div class="form-group">
                        <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #333;">超时结案系数 (overdue)</label>
                        <input 
                          type="number" 
                          step="0.1" 
                          v-model.number="getCurrentDeptCoefficients().overdue" 
                          placeholder="0.4"
                          style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;"
                        />
                      </div>
                      
                      <div class="form-group">
                        <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #333;">结案率权重 (closure_weight)</label>
                        <input 
                          type="number" 
                          step="0.1" 
                          v-model.number="getCurrentDeptCoefficients().closure_weight" 
                          placeholder="0.8"
                          style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;"
                        />
                      </div>
                      
                      <div class="form-group">
                        <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #333;">延期率权重 (delay_weight)</label>
                        <input 
                          type="number" 
                          step="0.1" 
                          v-model.number="getCurrentDeptCoefficients().delay_weight" 
                          placeholder="0.1"
                          style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;"
                        />
                      </div>
                      
                      <div class="form-group" style="grid-column: 1 / -1;">
                        <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #333;">返工率权重 (rework_weight)</label>
                        <input 
                          type="number" 
                          step="0.1" 
                          v-model.number="getCurrentDeptCoefficients().rework_weight" 
                          placeholder="0.1"
                          style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box;"
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div v-if="assessmentCoefficientsMessage" class="message success" style="margin-top: 20px; padding: 12px; background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.4); border-radius: 4px; backdrop-filter: blur(10px);">
                    ✓ {{ assessmentCoefficientsMessage }}
                  </div>
                  
                  <div v-if="assessmentCoefficientsError" class="message error" style="margin-top: 20px; padding: 12px; background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.4); border-radius: 4px; backdrop-filter: blur(10px);">
                    ✗ {{ assessmentCoefficientsError }}
                  </div>
                  
                  <div class="form-actions" style="margin-top: 25px; display: flex; gap: 15px;">
                    <button 
                      class="save-btn" 
                      @click="saveAssessmentCoefficients" 
                      :disabled="assessmentCoefficientsLoading"
                      style="padding: 12px 30px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease;"
                    >
                      <span v-if="assessmentCoefficientsLoading">保存中...</span>
                      <span v-else>保存系数</span>
                    </button>
                    <button 
                      class="cancel-btn" 
                      @click="resetAssessmentCoefficients"
                      style="padding: 12px 30px; background-color: #95a5a6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease;"
                    >
                      重置默认
                    </button>
                  </div>
                </div>
              </div>

              <!-- 小工具配置 -->
              <div v-if="businessTab === 'tools'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">小工具</h4>
                  <p class="panel-description">数据工具集：地址信息提取、数据清洗等</p>
                </div>

                <div class="panel-body">
                  <!-- 工具标签页 -->
                  <div class="config-tabs">
                    <button class="config-tab" :class="{ active: activeToolTab === 'huanwei-assignment' }" @click="activeToolTab = 'huanwei-assignment'">市容环卫案件分配</button>
                    <button class="config-tab" :class="{ active: activeToolTab === 'location-extraction' }" @click="activeToolTab = 'location-extraction'">地址信息提取</button>
                    <button class="config-tab" :class="{ active: activeToolTab === 'data-cleaning' }" @click="activeToolTab = 'data-cleaning'">数据清洗</button>
                  </div>

                  <!-- 工具内容 -->
                  <div class="tools-content" style="padding: 20px 0;">
                    <!-- 市容环卫案件分配标签页内容 -->
                    <div v-if="activeToolTab === 'huanwei-assignment'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
                      <!-- 第一行：提示文字 -->
                      <div class="tip-section" style="margin-bottom: 20px;">
                        <p>该模块允许上传Excel文件，为市容环卫中心的案件分配到各环卫部门（添加"环卫"前缀）。</p>
                        <p style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px;"><strong>注意：</strong>请确保Excel文件中包含以下列：</p>
                        <ul style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px; margin-left: 20px;">
                          <li>处置部门：案件的处理部门</li>
                          <li>所属片区：案件所属的片区</li>
                        </ul>
                      </div>

                      <!-- 第二行：文件上传 -->
                      <div class="upload-section" style="margin-bottom: 20px;">
                        <div class="form-group" style="margin-bottom: 15px;">
                          <label for="huanwei-file-input" style="display: block; margin-bottom: 5px; font-weight: bold;">选择Excel文件：</label>
                          <input
                            type="file"
                            id="huanwei-file-input"
                            accept=".xlsx"
                            @change="handleHuanweiFileSelect"
                            :disabled="huanweiLoading"
                          >
                          <div v-if="huanweiFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: rgba(255, 255, 255, 0.8);">
                            已选择：{{ huanweiFile.name }}
                          </div>
                        </div>

                        <div class="form-group">
                          <button
                            @click="processHuanweiFile"
                            :disabled="!huanweiFile || huanweiLoading"
                            class="upload-btn"
                          >
                            {{ huanweiLoading ? '处理中...' : '开始处理' }}
                          </button>
                        </div>

                        <div v-if="huanweiMessage" class="message success" style="padding: 10px; background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          ✓ {{ huanweiMessage }}
                        </div>
                        <div v-if="huanweiError" class="message error" style="padding: 10px; background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          ✗ {{ huanweiError }}
                        </div>
                      </div>
                    </div>

                    <!-- 地址信息提取标签页内容 -->
                    <div v-if="activeToolTab === 'location-extraction'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
                      <!-- 第一行：提示文字 -->
                      <div class="tip-section" style="margin-bottom: 20px;">
                        <p>该模块允许上传Excel文件，从问题描述中提取地址信息并替换原文件中地址描述为"没有相关位置描述""无位置描述"。</p>
                        <p style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px;"><strong>注意：</strong>请确保Excel文件中包含以下列：</p>
                        <ul style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px; margin-left: 20px;">
                          <li>问题描述：包含地址信息的文本</li>
                          <li>地址描述：需要替换的地址字段</li>
                        </ul>
                      </div>

                      <!-- 第二行：文件上传 -->
                      <div class="upload-section" style="margin-bottom: 20px;">
                        <div class="form-group" style="margin-bottom: 15px;">
                          <label for="location-file-input" style="display: block; margin-bottom: 5px; font-weight: bold;">选择Excel文件：</label>
                          <input
                            type="file"
                            id="location-file-input"
                            accept=".xlsx"
                            @change="handleLocationFileSelect"
                            :disabled="locationLoading"
                          >
                          <div v-if="locationFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: rgba(255, 255, 255, 0.8);">
                            已选择：{{ locationFile.name }}
                          </div>
                        </div>

                        <div class="form-group">
                          <button
                            @click="processLocationFile"
                            :disabled="!locationFile || locationLoading"
                            class="upload-btn"
                          >
                            {{ locationLoading ? '处理中...' : '开始处理' }}
                          </button>
                        </div>

                        <div v-if="locationMessage" class="message success" style="padding: 10px; background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          {{ locationMessage }}
                        </div>
                        <div v-if="locationError" class="message error" style="padding: 10px; background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          {{ locationError }}
                        </div>
                      </div>
                    </div>

                    <!-- 数据清洗标签页内容 -->
                    <div v-if="activeToolTab === 'data-cleaning'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
                      <!-- 第一行：提示文字 -->
                      <div class="tip-section" style="margin-bottom: 20px;">
                        <p>该模块允许上传Excel文件，进行数据清洗操作，包括去除重复数据、填充缺失值等。</p>
                        <p style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px;"><strong>注意：</strong>请确保Excel文件中包含以下列：</p>
                        <ul style="color: rgba(255, 255, 255, 0.7); font-size: 14px; margin-top: 5px; margin-left: 20px;">
                          <li>问题描述：包含地址信息的文本</li>
                          <li>地址描述：需要替换的地址字段</li>
                        </ul>
                      </div>

                      <!-- 第二行：文件上传 -->
                      <div class="upload-section" style="margin-bottom: 20px;">
                        <div class="form-group" style="margin-bottom: 15px;">
                          <label for="cleaning-file-input" style="display: block; margin-bottom: 5px; font-weight: bold;">选择Excel文件：</label>
                          <input
                            type="file"
                            id="cleaning-file-input"
                            accept=".xlsx"
                            @change="handleCleaningFileSelect"
                            :disabled="cleaningLoading"
                          >
                          <div v-if="cleaningFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: rgba(255, 255, 255, 0.8);">
                            已选择：{{ cleaningFile.name }}
                          </div>
                        </div>

                        <div class="form-group">
                          <button
                            @click="processCleaningFile"
                            :disabled="!cleaningFile || cleaningLoading"
                            class="upload-btn"
                          >
                            {{ cleaningLoading ? '处理中...' : '开始处理' }}
                          </button>
                        </div>

                        <div v-if="cleaningMessage" class="message success" style="padding: 10px; background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          {{ cleaningMessage }}
                        </div>
                        <div v-if="cleaningError" class="message error" style="padding: 10px; background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid rgba(231, 76, 60, 0.4); border-radius: 4px; margin-bottom: 15px; backdrop-filter: blur(10px);">
                          {{ cleaningError }}
                        </div>
                      </div>

                      <!-- 第三行：字段选择 -->
                      <div v-if="cleaningFields.length > 0" class="fields-section" style="margin-bottom: 20px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px);">
                        <h4 style="margin-top: 0; margin-bottom: 15px; color: white;">字段选择</h4>
                        <p style="margin-bottom: 15px; color: rgba(255, 255, 255, 0.8);">请选择需要保留的字段：</p>
                        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;">
                          <label v-for="field in cleaningFields" :key="field" style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: rgba(255, 255, 255, 0.9);">
                            <input type="checkbox" v-model="cleaningSelectedFields" :value="field" style="width: 18px; height: 18px;">
                            {{ field }}
                          </label>
                        </div>
                        <div style="margin-top: 15px; display: flex; gap: 10px;">
                          <button @click="selectAllCleaningFields" style="padding: 8px 16px; background: rgba(255, 255, 255, 0.2); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer;">全选</button>
                          <button @click="deselectAllCleaningFields" style="padding: 8px 16px; background: rgba(255, 255, 255, 0.2); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer;">取消全选</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 系统配置子模块 -->
          <div v-if="adminActiveTab === 'system'" class="admin-subsection">
            <!-- 配置标签页 -->
            <div class="config-tabs">
              <button class="config-tab" :class="{ active: systemConfigTab === 'general' }" @click="systemConfigTab = 'general'">通用配置</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'security' }" @click="systemConfigTab = 'security'">安全配置</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'logs' }" @click="systemConfigTab = 'logs'">系统日志</button>
            </div>
            
            <!-- 配置内容 -->
            <div class="config-content">
              <!-- 通用配置 -->
              <div v-if="systemConfigTab === 'general'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">通用配置</h4>
                  <p class="panel-description">系统通用设置</p>
                </div>
                <div class="panel-body">
                  <div class="config-form">
                    <div class="form-group">
                      <label>系统名称</label>
                      <input type="text" placeholder="运城市智慧城市管理平台" />
                    </div>
                    <div class="form-group">
                      <label>系统版本</label>
                      <input type="text" placeholder="1.0.0" disabled />
                    </div>
                    <div class="form-group">
                      <label>默认语言</label>
                      <select>
                        <option value="zh-CN">简体中文</option>
                        <option value="en-US">English</option>
                      </select>
                    </div>
                    <div class="form-actions">
                      <button class="save-btn">保存配置</button>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 安全配置 -->
              <div v-if="systemConfigTab === 'security'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">安全配置</h4>
                  <p class="panel-description">系统安全相关设置</p>
                </div>
                <div class="panel-body">
                  <div class="config-form">
                    <div class="form-group">
                      <label>登录超时时间</label>
                      <input type="number" placeholder="3600" />
                      <span class="form-help">秒</span>
                    </div>
                    <div class="form-group">
                      <label>密码复杂度要求</label>
                      <input type="checkbox" />
                      <span>启用密码强度检查</span>
                    </div>
                    <div class="form-actions">
                      <button class="save-btn">保存配置</button>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- 系统日志 -->
              <div v-if="systemConfigTab === 'logs'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">系统日志</h4>
                  <p class="panel-description">查看系统操作日志</p>
                </div>
                <div class="panel-body">
                  <div class="logs-section">
                    <p>系统日志功能开发中...</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 添加用户弹窗 -->
        <div v-if="showAddUserForm" class="modal">
          <div class="modal-content">
            <h3>{{ editingUser ? '编辑用户' : '添加用户' }}</h3>
            <div class="form-group">
              <label for="new-username" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">用户名：</label>
              <input type="text" id="new-username" v-model="newUser.username" placeholder="请输入用户名" autocomplete="username" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; background: rgba(255, 255, 255, 0.15); color: white;" />
            </div>
            <div class="form-group">
              <label for="new-password" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">密码：</label>
              <input type="password" id="new-password" v-model="newUser.password" placeholder="请输入密码" autocomplete="new-password" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; background: rgba(255, 255, 255, 0.15); color: white;" />
            </div>
            <div class="form-group">
              <label for="new-role" style="display: block; font-weight: 600; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">角色：</label>
              <select id="new-role" v-model="newUser.role" style="width: 100%; padding: 10px 12px; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 6px; font-size: 14px; box-sizing: border-box; background: rgba(255, 255, 255, 0.15); color: white; appearance: none; -webkit-appearance: none; -moz-appearance: none; background-image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuOCkiIGQ9Ik02IDlMMiA1aDhsNC41IDMuNSIvPjwvc3ZnPg=='); background-repeat: no-repeat; background-position: right 10px center; padding-right: 30px;">
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <div v-if="adminError" class="admin-error">{{ adminError }}</div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="closeAddUserForm">取消</button>
              <button class="save-btn" @click="saveUser" :disabled="adminLoading">
                {{ adminLoading ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
        
        <!-- 编辑用户权限弹窗 -->
        <div v-if="showEditPermissionsForm" class="modal">
          <div class="modal-content">
            <h3>编辑用户权限</h3>
            <div class="form-group">
              <label>{{ editingPermissionsUser ? editingPermissionsUser.username : '' }}</label>
            </div>
            <div class="permissions-list">
              <div class="permission-item">
                <input type="checkbox" id="perm-assessment" v-model="editingPermissions.assessment" />
                <label for="perm-assessment">考核计分</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-data-analysis" v-model="editingPermissions.data_analysis" />
                <label for="perm-data-analysis">AI应用</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-map" v-model="editingPermissions.map" />
                <label for="perm-map">地图服务</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-huiwentai" v-model="editingPermissions.huiwentai" />
                <label for="perm-huiwentai">汇问台</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-cases" v-model="editingPermissions.cases" />
                <label for="perm-cases">案件管理</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-business" v-model="editingPermissions.business" />
                <label for="perm-business">业务平台</label>
              </div>
            </div>
            <div v-if="adminError" class="admin-error">{{ adminError }}</div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="closeEditPermissionsForm">取消</button>
              <button class="save-btn" @click="saveUserPermissions" :disabled="adminLoading">
                {{ adminLoading ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
        
        <!-- 添加/编辑栏目弹窗 -->
        <div v-if="showAddCategoryForm" class="modal">
          <div class="modal-content">
            <h3>{{ editingCategory ? '编辑栏目' : '添加栏目' }}</h3>
            <div class="form-group">
              <label for="category-name">名称：</label>
              <input type="text" id="category-name" v-model="newCategory.name" placeholder="请输入栏目名称" @input="() => { if (!editingCategory) newCategory.slug = generateSlug(newCategory.name) }" />
            </div>

            <div class="form-group">
              <label for="category-description">描述：</label>
              <textarea id="category-description" v-model="newCategory.description" placeholder="请输入栏目描述" rows="3"></textarea>
            </div>
            <div class="form-group">
              <label for="category-order">排序：</label>
              <input type="number" id="category-order" v-model="newCategory.order" placeholder="请输入排序值" />
            </div>
            <div v-if="cmsFormError" class="admin-error">{{ cmsFormError }}</div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="closeCategoryForm">取消</button>
              <button class="save-btn" @click="saveCategory" :disabled="cmsLoading">
                {{ cmsLoading ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
        
        <!-- 添加/编辑文章弹窗 -->
        <div v-if="showAddArticleForm" class="modal">
          <div class="modal-content" style="max-width: 800px;">
            <h3>{{ editingArticle ? '编辑文章' : '添加文章' }}</h3>
            <div class="form-group">
              <label for="article-title">标题：</label>
              <input type="text" id="article-title" v-model="newArticle.title" placeholder="请输入文章标题" style="width: 100%;" @input="() => { if (!editingArticle) newArticle.slug = generateSlug(newArticle.title) }" />
            </div>
            
            <div class="form-group">
              <label for="article-file">文件上传（DOCX/PDF）：</label>
              <input type="file" id="article-file" accept=".docx,.pdf" @change="uploadCMSFile" :disabled="fileUploadLoading" />
              <div v-if="fileUploadLoading" style="font-size: 12px; color: rgba(255, 255, 255, 0.7); margin-top: 5px;">上传中...</div>
              <div v-if="fileUploadError" style="font-size: 12px; color: #ff6b6b; margin-top: 5px;">{{ fileUploadError }}</div>
              <div v-if="newArticle.file_path" style="font-size: 12px; color: #2ecc71; margin-top: 5px;">已上传文件</div>
            </div>
            
            <div class="form-group">
              <label for="article-image">图片上传（插入到内容）：</label>
              <input type="file" id="article-image" accept=".jpg,.jpeg,.png,.gif,.webp" @change="uploadImage" :disabled="imageUploadLoading" />
              <div v-if="imageUploadLoading" style="font-size: 12px; color: rgba(255, 255, 255, 0.7); margin-top: 5px;">上传中...</div>
              <div v-if="imageUploadError" style="font-size: 12px; color: #ff6b6b; margin-top: 5px;">{{ imageUploadError }}</div>
              <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 5px;">提示：上传后图片将自动插入到文章内容中</div>
            </div>

            <div class="form-group">
              <label for="article-category">栏目：</label>
              <select id="article-category" v-model="newArticle.category_id">
                <option value="">请选择栏目</option>
                <option v-for="category in cmsCategories" :key="category.id" :value="category.id">
                  {{ category.name }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label for="article-summary">摘要：</label>
              <textarea id="article-summary" v-model="newArticle.summary" placeholder="请输入文章摘要" rows="3" style="width: 100%;"></textarea>
            </div>
            <div class="form-group">
              <label for="article-content">内容：</label>
              <textarea id="article-content" v-model="newArticle.content" placeholder="请输入文章内容" rows="15" style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; line-height: 1.5; font-family: Arial, sans-serif; resize: vertical;"></textarea>
              <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 5px;">提示：可以直接输入HTML标签来实现格式化效果，例如 &lt;b&gt;粗体&lt;/b&gt;、&lt;i&gt;斜体&lt;/i&gt; 等</div>
            </div>
            <div v-if="cmsFormError" class="admin-error">{{ cmsFormError }}</div>
            <div class="modal-actions">
              <button class="cancel-btn" @click="closeArticleForm">取消</button>
              <button class="save-btn" @click="saveArticle" :disabled="cmsLoading">
                {{ cmsLoading ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 查询结果弹框 -->
    <div v-if="showResultModal" class="result-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 1000;">
      <div class="modal-content" style="background: linear-gradient(135deg, #1e3a8a 0%, #0a2463 100%); border-radius: 12px; padding: 30px; width: 90%; max-width: 1000px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15); border: 1px solid rgba(255, 255, 255, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 20px; color: white;">查询结果</h2>
          <button @click="closeResultModal" style="background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.3); font-size: 18px; cursor: pointer; color: white; padding: 5px 12px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px;">&times;</button>
        </div>
        
        <!-- 生成的SQL语句 -->
        <div v-if="generatedSQL" class="sql-section" style="margin-bottom: 20px; padding: 15px; background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; backdrop-filter: blur(10px);">
          <h4 style="margin-top: 0; margin-bottom: 10px; color: rgba(255, 255, 255, 0.9);">生成的SQL语句：</h4>
          <pre style="background: rgba(0, 0, 0, 0.3); padding: 10px; border-radius: 4px; overflow-x: auto; margin: 0; color: rgba(255, 255, 255, 0.9);">{{ generatedSQL }}</pre>
        </div>
        
        <!-- 查询结果 -->
        <div v-if="queryResult">
          <div v-if="Array.isArray(queryResult) && queryResult.length > 0" class="result-table-container" style="overflow-x: auto; margin-bottom: 20px;">
            <table style="width: 100%; border-collapse: collapse; background: rgba(255, 255, 255, 0.1); box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 11px; line-height: 1.3; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; overflow: hidden;">
              <thead style="background: rgba(255, 255, 255, 0.15);">
                <tr>
                  <th v-for="(key, index) in Object.keys(queryResult[0])" :key="index" style="padding: 8px 10px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.2); font-weight: bold; white-space: nowrap; color: white;">
                    {{ key }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in queryResult" :key="rowIndex" style="border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
                  <td v-for="(value, colIndex) in Object.values(row)" :key="colIndex" style="padding: 8px 10px; word-break: break-all; color: rgba(255, 255, 255, 0.9);">
                    {{ value }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="Array.isArray(queryResult) && queryResult.length === 0" class="empty-result" style="padding: 40px; text-align: center; background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; backdrop-filter: blur(10px);">
            <p style="color: rgba(255, 255, 255, 0.7); margin: 0;">查询结果为空</p>
          </div>
          <div v-else class="result-message" style="padding: 40px; background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; backdrop-filter: blur(10px);">
            <p style="color: rgba(255, 255, 255, 0.9); margin: 0;">{{ queryResult }}</p>
          </div>
        </div>
        
        <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
          <button 
            @click="closeResultModal"
            style="padding: 10px 20px; background: rgba(255, 255, 255, 0.2); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.3s ease;"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
    
    <!-- 页脚 -->
    <div v-if="isLoggedIn" class="footer">
      <div class="footer-content">
        <p class="footer-title">运城市智慧城市管理平台-一站通</p>
        <div class="footer-info">
          <span>📞 联系电话：0359-2381078</span>
          <span>📧 电子邮箱：bnc9595@163.com</span>
        </div>
        <p class="footer-copyright">© 2026 All Rights Reserved</p>
      </div>
    </div>
    
    <!-- 文章详情弹窗 -->
    <div v-if="showArticleDetail" class="article-detail-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(135deg, rgba(0, 0, 0, 0.4) 0%, rgba(0, 0, 0, 0.6) 100%); display: flex; justify-content: center; align-items: center; z-index: 1000; animation: fadeIn 0.3s ease;">
      <div class="article-detail-content" style="background: linear-gradient(135deg, #1e3a8a 0%, #0a2463 100%); border-radius: 12px; padding: 0; width: 90%; max-width: 900px; max-height: 85vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25); animation: slideUp 0.3s ease; border: 1px solid rgba(255, 255, 255, 0.2);">
        <!-- 文章头部 -->
        <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 30px 30px 20px 30px; position: relative; border-radius: 12px 12px 0 0;">
          <h2 style="margin: 0 0 15px 0; font-size: 28px; color: white; text-align: left; line-height: 1.4;">{{ currentArticle?.title }}</h2>
          
          <!-- 文章元信息 -->
          <div style="display: flex; gap: 25px; flex-wrap: wrap; font-size: 14px; color: rgba(255, 255, 255, 0.9);">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 16px;">📁</span>
              <span>{{ getCategoryName(currentArticle?.category_id) }}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 16px;">📅</span>
              <span>{{ formatDate(currentArticle?.published_at || currentArticle?.created_at) }}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 16px;">👁️</span>
              <span>浏览量：{{ currentArticle?.view_count }} 次</span>
            </div>
          </div>
        </div>
        
        <!-- 文章内容 -->
        <div style="padding: 30px;">
          <div v-if="articleDetailLoading" style="text-align: center; padding: 60px 20px;">
            <div style="font-size: 18px; color: rgba(255, 255, 255, 0.7);">加载中...</div>
          </div>
          
          <div v-else-if="articleDetailError" style="text-align: center; padding: 40px; background-color: rgba(255, 107, 107, 0.1); color: #ff6b6b; border-radius: 8px; border: 1px solid rgba(255, 107, 107, 0.3);">
            <div style="font-size: 16px; margin-bottom: 15px;">{{ articleDetailError }}</div>
            <button @click="closeArticleDetail" style="padding: 8px 20px; background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; transition: all 0.3s ease;">关闭</button>
          </div>
          
          <div v-else-if="currentArticle" style="color: rgba(255, 255, 255, 0.9);">
            <!-- 摘要部分 -->
            <div v-if="currentArticle.summary" style="margin-bottom: 25px; padding: 18px; background: rgba(255, 255, 255, 0.1); border-left: 4px solid #4facfe; border-radius: 6px; backdrop-filter: blur(10px);">
              <div style="font-weight: 600; color: #4facfe; margin-bottom: 8px; font-size: 14px;">摘要</div>
              <div style="line-height: 1.6; color: rgba(255, 255, 255, 0.8); font-size: 15px;">{{ currentArticle.summary }}</div>
            </div>
            
            <!-- 正文内容 -->
            <div style="margin-bottom: 30px;">
              <div class="article-content-body" style="line-height: 1.8; color: rgba(255, 255, 255, 0.9); font-size: 16px;" v-html="currentArticle.content"></div>
            </div>
            
            <!-- 附件部分 -->
            <div v-if="currentArticle.file_path" style="margin-top: 30px; padding: 20px; background-color: rgba(255, 255, 255, 0.1); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px);">
              <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-size: 24px;">📎</span>
                <h4 style="margin: 0; font-size: 16px; color: white;">相关附件</h4>
              </div>
              <a :href="currentArticleFileUrl" :download="currentArticle.file_path.split('/').pop()" style="display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; transition: all 0.3s ease; cursor: pointer;" @mouseenter="$event.currentTarget.style.transform='translateY(-2px)'; $event.currentTarget.style.boxShadow='0 4px 12px rgba(79, 172, 254, 0.4)'" @mouseleave="$event.currentTarget.style.transform='translateY(0)'; $event.currentTarget.style.boxShadow='none'">
                <span>⬇️</span>
                <span>下载文件</span>
              </a>
            </div>
          </div>
        </div>
        
        <!-- 关闭按钮 (底部) -->
        <div style="padding: 15px 30px; background-color: rgba(255, 255, 255, 0.1); border-top: 1px solid rgba(255, 255, 255, 0.2); border-radius: 0 0 12px 12px; text-align: right;">
          <button @click="closeArticleDetail" style="padding: 8px 20px; background: rgba(255, 255, 255, 0.2); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-weight: 500; transition: all 0.3s ease;">关闭</button>
        </div>
      </div>
    </div>
    
    <!-- 全部文章弹窗 -->
    <div v-if="showAllArticlesModal" class="all-articles-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 1000;">
      <div class="all-articles-content" style="background: linear-gradient(135deg, #1e3a8a 0%, #0a2463 100%); border-radius: 8px; padding: 30px; width: 90%; max-width: 800px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15); border: 1px solid rgba(255, 255, 255, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 24px; color: white; text-align: left;">{{ getCategoryName(allArticlesCategoryId) }} - 全部文章</h2>
          <button @click="closeAllArticlesModal" style="background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.3); font-size: 18px; cursor: pointer; color: white; padding: 5px 12px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 4px;">&times;</button>
        </div>
        <div v-if="allArticlesLoading" style="text-align: center; padding: 40px; color: rgba(255, 255, 255, 0.7);">
          <div>加载中...</div>
        </div>
        <div v-else-if="allArticlesList.length === 0" style="text-align: center; padding: 40px; color: rgba(255, 255, 255, 0.6);">
          <div>该栏目下暂无文章</div>
        </div>
        <div v-else>
          <div class="articles-list" style="list-style: none; padding: 0; margin: 0;">
            <div v-for="article in allArticlesList" :key="article.id" class="article-item" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding: 12px; border-radius: 6px; transition: all 0.3s ease; background: rgba(255, 255, 255, 0.05); border: 1px solid transparent;" @click="() => { fetchArticleDetail(article.id); closeAllArticlesModal(); }" @mouseenter="$event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.15)'; $event.currentTarget.style.borderColor='rgba(255, 255, 255, 0.2)'" @mouseleave="$event.currentTarget.style.backgroundColor='rgba(255, 255, 255, 0.05)'; $event.currentTarget.style.borderColor='transparent'">
              <span style="flex: 1; font-size: 16px; color: rgba(255, 255, 255, 0.9); line-height: 1.4; text-align: left;">
                <span style="margin-right: 12px; color: #4facfe;">•</span>
                {{ article.title }}
              </span>
              <span style="font-size: 14px; color: rgba(255, 255, 255, 0.6); white-space: nowrap; margin-left: 15px;">
                [{{ formatDate(article.published_at || article.created_at) }}]
              </span>
            </div>
          </div>
          
          <!-- 分页控件 -->
          <div v-if="allArticlesTotal > 0" class="pagination" style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding: 15px; background: rgba(255, 255, 255, 0.1); border-radius: 8px; flex-wrap: wrap; gap: 10px; border: 1px solid rgba(255, 255, 255, 0.2);">
            <span class="pagination-info" style="font-size: 14px; color: rgba(255, 255, 255, 0.8);">共 {{ allArticlesTotal }} 条，第 {{ allArticlesPage }}/{{ allArticlesPages }} 页</span>
            <div class="pagination-buttons" style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, 1)" :disabled="allArticlesPage === 1" style="padding: 8px 14px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">首页</button>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPage - 1)" :disabled="allArticlesPage === 1" style="padding: 8px 14px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">上一页</button>
              <template v-for="page in getAllArticlesPageNumbers()" :key="page">
                <button v-if="page !== '...'" class="page-btn" :class="{ active: page === allArticlesPage }" :style="page === allArticlesPage ? 'background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-color: transparent;' : 'background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3);'" style="padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">
                  {{ page }}
                </button>
                <span v-else class="page-ellipsis" style="padding: 0 8px; color: rgba(255, 255, 255, 0.6); font-size: 16px;">...</span>
              </template>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPage + 1)" :disabled="allArticlesPage === allArticlesPages" style="padding: 8px 14px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">下一页</button>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPages)" :disabled="allArticlesPage === allArticlesPages" style="padding: 8px 14px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">末页</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* 最优先：重置所有浏览器默认样式 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  border: 0 none;
  outline: 0;
}

/* 分析步骤动画 */
@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(79, 172, 254, 0.4);
  }
  50% {
    transform: scale(1.02);
    box-shadow: 0 0 15px 5px rgba(79, 172, 254, 0.2);
  }
}

@keyframes fadeInSlide {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes checkmark {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
  }
}

/* 彻底兜底：清除html、body所有默认样式，优先级拉满 */
html, body {
  font-family: Arial, sans-serif;
  line-height: 1.6;
  color: #333;
  background-color: #f5f5f5;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 none !important;
  overflow-x: auto;
  display: block;
}

/* 只清除导致顶部空隙的元素，保留其他布局样式 */
body > *:first-child,
.system-container > *:first-child,
.header,
.nav-tabs {
  margin-top: 0 !important;
  padding-top: 0 !important;
  border-top: 0 none !important;
}

/* ===================== 顶部标题栏样式 ===================== */
.header {
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  width: 1020px;
  height: 120px;
  margin: 0 auto;
  padding: 0 30px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 20px rgba(10, 36, 99, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.header::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
  animation: headerShimmer 8s linear infinite;
  pointer-events: none;
}

@keyframes headerShimmer {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
}

.header h1 {
  position: absolute;
  top: 50%;
  left: 30px;
  transform: translateY(-50%);
  z-index: 2;
  color: white;
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  letter-spacing: 2px;
  text-align: left;
  white-space: nowrap;
}

.header .user-info {
  position: absolute;
  right: 30px;
  bottom: 15px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 15px;
}

.header .username {
  color: white;
  font-size: 14px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.15);
  padding: 8px 16px;
  border-radius: 20px;
  backdrop-filter: blur(10px);
}

.header .logout-btn {
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.header .logout-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 确保body没有间隙 */
body {
  position: relative;
  top: 0;
  margin: 0 !important;
  padding: 0 !important;
  min-height: 100vh;
}

.system-container {
  /* 固定宽度1020px + 水平居中 + 顶部完全贴顶 */
  width: 1020px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  top: 0;
}

.main-content {
  flex: 1;
  padding: 30px 20px;
  overflow-y: auto;
  width: 1020px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  min-height: 600px;
  color: white;
}

.header {
  background-color: #2c3e50;
  color: #fff;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin: 0;
  position: relative;
  top: 0;
  /* 确保没有隐性的顶部外边距塌陷 */
  display: block;
  overflow: hidden;
}

.header h1 {
  font-size: 2.5em;
  margin: 0;
}

.nav-tabs {
  display: flex;
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  color: #fff;
  margin-top: 0;
  width: 1020px;
  margin: 0 auto;
  box-shadow: 0 2px 10px rgba(10, 36, 99, 0.2);
}

.tab {
  flex: 1;
  padding: 14px 15px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  border-bottom: 3px solid transparent;
  font-size: 15px;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.15);
}

.tab.active {
  background: rgba(255, 255, 255, 0.2);
  font-weight: 600;
  border-bottom-color: #fff;
}

.main-content {
  flex: 1;
  padding: 30px 20px;
  overflow-y: auto;
  width: 1020px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  min-height: 600px;
  color: white;
}
/* 覆盖原有的 #app 样式 */
#app {
  padding: 0; /* 或者只保留左右 */
  /* padding: 0 2rem; */
  min-height: 100vh;
}

.system-container {
  background: #f5f5f5;
  min-height: 100vh;
  color: #333;
  display: flex;
  flex-direction: column;
}

.tab-content {
  background-color: rgba(255, 255, 255, 0.1);
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
  width: 100%;
  margin: 0 auto;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.section-title {
  font-size: 1.4em;
  color: white;
  margin-bottom: 25px;
  padding-bottom: 10px;
  border-bottom: 2px solid rgba(255, 255, 255, 0.3);
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.file-selector {
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  padding: 15px;
  background-color: rgba(255, 255, 255, 0.1);
}

.file-selector input[type="file"] {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.file-name {
  display: block;
  font-size: 1em;
  color: rgba(255, 255, 255, 0.8);
}

.upload-btn {
  padding: 15px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1em;
  font-weight: bold;
  transition: all 0.3s ease;
}

.upload-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.upload-btn:disabled {
  background: rgba(255, 255, 255, 0.2);
  cursor: not-allowed;
  color: rgba(255, 255, 255, 0.5);
}

.upload-status {
  padding: 15px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  background-color: rgba(255, 255, 255, 0.1);
}

.status-label {
  font-weight: bold;
  color: rgba(255, 255, 255, 0.9);
}

.status-value {
  color: rgba(255, 255, 255, 0.8);
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: bold;
  color: rgba(255, 255, 255, 0.9);
}

.form-group select {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 1em;
  color: white;
}

.form-group select option {
  background: #1e3a8a;
  color: white;
}

.analyze-btn {
  padding: 15px;
  background-color: #3498db;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1em;
  font-weight: bold;
  transition: background-color 0.3s ease;
  margin-top: 10px;
}

.analyze-btn:hover {
  background-color: #2980b9;
}

.analyze-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
}

.analysis-progress {
  margin-top: 20px;
  padding: 20px;
  background-color: #f9f9f9;
  border-radius: 8px;
  border: 1px solid #ddd;
}

.progress-step {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  opacity: 0.5;
  transition: all 0.3s ease;
}

.progress-step.active {
  opacity: 1;
  color: #27ae60;
}

.step-indicator {
  font-size: 1.5em;
  margin-right: 15px;
}

.step-text {
  font-size: 1em;
  font-weight: 500;
}

.result-section {
  min-height: 400px;
  background-color: #f9f9f9;
  padding: 20px;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.empty-result {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
  font-size: 1.1em;
}

.result-content {
  line-height: 1.6;
}

.result-title {
  font-size: 1.3em;
  color: #4facfe;
  margin-bottom: 15px;
}

.data-summary {
  font-size: 1.1em;
  margin-bottom: 20px;
  color: rgba(255, 255, 255, 0.8);
}

.result-details {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.details-subtitle {
  font-size: 1.1em;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 15px;
  margin-top: 25px;
}

.column-list {
  list-style-type: none;
  margin-left: 20px;
}

.column-list li {
  margin-bottom: 8px;
  padding-left: 20px;
  position: relative;
  color: rgba(255, 255, 255, 0.8);
}

.column-list li::before {
  content: '•';
  color: #4facfe;
  position: absolute;
  left: 0;
  font-weight: bold;
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
  font-size: 0.9em;
  background-color: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.sample-table th, .sample-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.8);
}

.sample-table th {
  background-color: rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.sample-table tr:hover {
  background-color: rgba(255, 255, 255, 0.15);
}

.analysis-content {
  margin: 30px 0;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  border-left: 4px solid #4facfe;
}

.analysis-text {
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
  font-size: 1em;
  max-height: 600px;
  overflow-y: auto;
  padding-right: 10px;
}

.analysis-text br {
  margin-bottom: 10px;
}

/* 首页样式 */
.overview-section {
  padding: 20px;
  background-color: #f9f9f9;
  border-radius: 8px;
}

.feature-list {
  list-style-type: none;
  margin-left: 20px;
  margin-top: 15px;
}

.feature-list li {
  margin-bottom: 10px;
  padding-left: 20px;
  position: relative;
}

.feature-list li::before {
  content: '•';
  color: #27ae60;
  position: absolute;
  left: 0;
  font-weight: bold;
}

/* 考核计分和案件抽查样式 */
.assessment-section,
.spotcheck-section,
.tools-section,
.chengguantong-section {
  padding: 20px;
  background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(45, 74, 154, 0.4) 100%);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(100, 149, 237, 0.3);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  text-align: left;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 20px;
}

/* 地图服务样式 */
.map-section {
  padding: 20px;
  background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(45, 74, 154, 0.4) 100%);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid rgba(100, 149, 237, 0.3);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  text-align: left;
  min-height: 650px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 20px;
}

#map-container {
  width: 100%;
  height: 600px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #ddd;
}

.map-info {
  margin-top: 20px;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  width: 100%;
}

.map-info h3 {
  color: white;
  margin-bottom: 15px;
  font-size: 1.1em;
}

.map-info p {
  margin: 8px 0;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.4;
}

/* 图表样式 */
.charts-section {
  margin-top: 30px;
  margin-bottom: 30px;
}

.chart-container {
  display: flex;
  gap: 20px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.chart-item {
  flex: 1;
  min-width: 400px;
  background-color: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  margin: 10px 0;
}

.chart-item h5 {
  font-size: 1.1em;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 15px;
  text-align: center;
}

.chart {
  width: 100%;
  height: 400px;
}

.footer {
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  color: #fff;
  padding: 25px 30px;
  text-align: center;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  position: relative;
  overflow: hidden;
  box-shadow: 0 -4px 20px rgba(10, 36, 99, 0.3);
}

.footer::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
}

.footer-content {
  position: relative;
  z-index: 1;
}

.footer-title {
  font-size: 1.1em;
  font-weight: 600;
  margin: 0 0 12px 0;
  letter-spacing: 1px;
}

.footer-info {
  display: flex;
  justify-content: center;
  gap: 30px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: 0.9em;
  opacity: 0.95;
}

.footer-info span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.1);
  padding: 6px 14px;
  border-radius: 15px;
  backdrop-filter: blur(5px);
}

.footer-copyright {
  font-size: 0.85em;
  opacity: 0.8;
  margin: 0;
}

/* 调试信息样式 */
.debug-info {
  background: rgba(255, 255, 255, 0.1);
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  margin: 10px;
  border-radius: 4px;
  font-size: 0.8em;
  color: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
}

/* 登录弹窗样式 */
.login-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.login-form {
  background-color: #fff;
  padding: 50px 40px;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 420px;
  max-width: 90%;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.login-logo {
  font-size: 48px;
  margin-bottom: 15px;
}

.login-form h2 {
  text-align: center;
  color: #1e3a8a;
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 2px;
}

.login-form .form-group {
  margin-bottom: 25px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
}

.login-form label {
  flex-shrink: 0;
  width: 70px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.login-form input {
  flex: 1;
  padding: 14px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 15px;
  background: #f8f9fa;
  color: #333;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.login-form input:focus {
  outline: none;
  border-color: #1e3a8a;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(30, 58, 138, 0.1);
}

.login-form input::placeholder {
  color: #aaa;
}

.login-error {
  color: #e74c3c;
  margin-bottom: 20px;
  padding: 12px 16px;
  background: rgba(231, 76, 60, 0.1);
  border-radius: 8px;
  text-align: center;
  font-size: 14px;
  border: 1px solid rgba(231, 76, 60, 0.2);
}

.login-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #1e3a8a 0%, #0a2463 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(30, 58, 138, 0.4);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 用户信息样式 */
.user-info {
  position: absolute;
  top: 50%;
  right: 20px;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 15px;
}

.username {
  color: #fff;
  font-size: 0.9em;
}

.logout-btn {
  padding: 8px 15px;
  background-color: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
  transition: background-color 0.3s ease;
}

.logout-btn:hover {
  background-color: #c0392b;
}

/* 管理员管理样式 */
.admin-section {
  margin-top: 20px;
}

.admin-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.admin-tab {
  padding: 10px 20px;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: all 0.3s ease;
  color: rgba(255, 255, 255, 0.7);
}

.admin-tab:hover {
  background-color: rgba(255, 255, 255, 0.1);
  color: white;
}

.admin-tab.active {
  border-bottom-color: #4facfe;
  background-color: rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.admin-subsection {
  background-color: rgba(255, 255, 255, 0.1);
  padding: 20px;
  border-radius: 8px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.subsection-title {
  font-size: 1.2em;
  color: white;
  margin-bottom: 20px;
}

/* 用户管理样式 */
.user-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.user-actions {
  display: flex;
  justify-content: flex-start;
}

.add-user-btn {
  padding: 10px 20px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1em;
  transition: all 0.3s ease;
}

.add-user-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.user-list {
  overflow-x: auto;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
  background-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.user-table th,
.user-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
}

.user-table th {
  background-color: rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.user-table tr:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.edit-user-btn,
.delete-user-btn {
  padding: 5px 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
  transition: all 0.3s ease;
  margin-right: 5px;
}

.edit-user-btn {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
}

.edit-user-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.delete-user-btn {
  background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
  color: #fff;
}

.delete-user-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(231, 76, 60, 0.4);
}

.delete-user-btn:disabled {
  background: rgba(255, 255, 255, 0.2);
  cursor: not-allowed;
  color: rgba(255, 255, 255, 0.5);
}

.edit-permissions-btn {
  padding: 5px 10px;
  background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
  transition: all 0.3s ease;
  margin-right: 5px;
}

.edit-permissions-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(155, 89, 182, 0.4);
}

/* 弹窗样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  overflow: visible !important;
  transform: translateZ(0);
  will-change: transform;
}



.modal-content {
  background: linear-gradient(135deg, #1e3a8a 0%, #0a2463 100%);
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  width: 800px;
  max-width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  z-index: 2001;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.modal-content h3 {
  text-align: center;
  color: #4facfe;
  margin-bottom: 20px;
}

.modal-content .form-group {
  margin-bottom: 15px;
}

.modal-content label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: rgba(255, 255, 255, 0.9);
}

.modal-content input,
.modal-content select {
  width: 100%;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  font-size: 1em;
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.modal-content input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.admin-error {
  color: #ff6b6b;
  margin-bottom: 15px;
  padding: 10px;
  background-color: rgba(255, 107, 107, 0.1);
  border-radius: 4px;
  text-align: center;
  border: 1px solid rgba(255, 107, 107, 0.3);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  gap: 10px;
}

/* TinyMCE z-index fix for modal */
.tox-tinymce,
.tox-tinymce *,
.tox-menu,
.tox-menu *,
.tox-dialog,
.tox-dialog *,
.tox-pop,
.tox-pop *,
.tox-tbtn,
.tox-toolbar,
.tox-toolbar-overlord,
.tox-collection,
.tox-collection-item,
.tox-colorpicker,
.tox-listbox,
.tox-listboxitem {
  z-index: 3000 !important;
  position: relative !important;
}

/* Ensure modal content has proper stacking context */
.modal-content {
  position: relative !important;
  z-index: 2001 !important;
}

/* Ensure TinyMCE containers have higher z-index */
.mce-container,
.mce-container-body,
.mce-popover,
.mce-menu {
  z-index: 3000 !important;
}

.cancel-btn,
.save-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1em;
  transition: all 0.3s ease;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

.save-btn {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
}

.save-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.save-btn:disabled {
  background: rgba(255, 255, 255, 0.2);
  cursor: not-allowed;
  color: rgba(255, 255, 255, 0.5);
}

/* 固定宽度下，小屏也不缩放，保持1020并出现横向滚动条 */
@media (max-width: 1020px) {
  body {
    width: 1020px;
    overflow-x: auto;
  }
  .system-container {
    width: 1020px;
    margin: 0 auto !important;
  }
  .chart-item {
    min-width: 100%;
  }
  .user-info {
    position: relative;
    top: 0;
    right: 0;
    transform: none;
    margin-top: 10px;
    justify-content: center;
  }
}

/* 系统配置样式 */
.config-tabs {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.config-tab {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-bottom: none;
  cursor: pointer;
  margin-right: 5px;
  border-radius: 5px 5px 0 0;
  transition: all 0.3s ease;
  color: rgba(255, 255, 255, 0.7);
}

.config-tab:hover {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.config-tab.active {
  background: rgba(255, 255, 255, 0.15);
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.config-panel {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 5px;
  box-shadow: 0 0 10px rgba(0,0,0,0.1);
  overflow: hidden;
  backdrop-filter: blur(10px);
}

.panel-header {
  background: rgba(255, 255, 255, 0.1);
  padding: 15px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.panel-title {
  margin: 0 0 5px 0;
  color: white;
  font-size: 16px;
}

.panel-description {
  margin: 0;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}

.panel-body {
  padding: 20px;
}

.config-form {
  max-width: 500px;
}

.config-form .form-group {
  margin-bottom: 20px;
}

.config-form .form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  color: rgba(255, 255, 255, 0.9);
}

.config-form .form-group input,
.config-form .form-group select {
  width: 100%;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.config-form .form-group input[type="checkbox"] {
  width: auto;
  margin-right: 10px;
}

.config-form .form-group select option {
  background: #1e3a8a;
  color: white;
}

.config-form .form-help {
  margin-left: 10px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

.form-actions {
  margin-top: 30px;
  display: flex;
  justify-content: flex-end;
}

/* 数据管理样式 */
.data-management {
  margin-top: 20px;
}

.section-description {
  margin-bottom: 20px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.1);
  border-left: 4px solid #4facfe;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.table-management {
  margin-top: 20px;
}

.refresh-btn {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 20px;
  transition: all 0.3s ease;
  backdrop-filter: blur(5px);
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}

.refresh-btn:disabled {
  background: rgba(255, 255, 255, 0.1);
  cursor: not-allowed;
  border-color: rgba(255, 255, 255, 0.2);
}

.table-list {
  margin-top: 20px;
}

.table-table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 10px rgba(0,0,0,0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.table-table th,
.table-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
}

.table-table th {
  background: rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.table-table tr:hover {
  background: rgba(255, 255, 255, 0.15);
}

.delete-table-btn {
  padding: 6px 12px;
  background: rgba(220, 53, 69, 0.8);
  color: white;
  border: 1px solid rgba(220, 53, 69, 0.5);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s ease;
  backdrop-filter: blur(5px);
}

.delete-table-btn:hover {
  background: rgba(200, 35, 51, 0.9);
  transform: translateY(-2px);
}

.delete-table-btn:disabled {
  background: rgba(204, 204, 204, 0.3);
  cursor: not-allowed;
  border-color: rgba(204, 204, 204, 0.2);
}

.empty-state {
  padding: 40px;
  text-align: center;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
}

/* 系统日志样式 */
.logs-section {
  padding: 40px;
  text-align: center;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
}

/* CMS管理样式 */
.cms-management {
  margin-top: 20px;
}

.management-title {
  font-size: 16px;
  font-weight: 600;
  color: white;
  margin-bottom: 15px;
}

.add-btn {
  padding: 8px 16px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 15px;
  transition: all 0.3s ease;
}

.add-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.add-btn:disabled {
  background: rgba(255, 255, 255, 0.2);
  cursor: not-allowed;
  color: rgba(255, 255, 255, 0.5);
}

.edit-btn {
  padding: 5px 10px;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  margin-right: 5px;
  transition: all 0.3s ease;
}

.edit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
}

.delete-btn {
  padding: 5px 10px;
  background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s ease;
}

.delete-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(231, 76, 60, 0.4);
}

.category-table,
.article-table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.category-table th,
.category-table td,
.article-table th,
.article-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
}

.category-table th,
.article-table th {
  background: rgba(255, 255, 255, 0.15);
  font-weight: bold;
  color: white;
}

.category-table tr:hover,
.article-table tr:hover {
  background: rgba(255, 255, 255, 0.1);
}

.category-table a,
.article-table a {
  color: #4facfe;
  text-decoration: none;
}

.category-table a:hover,
.article-table a:hover {
  text-decoration: underline;
}

.platform-image {
  border-radius: 4px;
}

/* 分页样式 */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.pagination-info {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.pagination-buttons {
  display: flex;
  gap: 8px;
}

.page-btn {
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s ease;
}

.page-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-btn.active {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  border-color: transparent;
}

.page-ellipsis {
  color: rgba(255, 255, 255, 0.6);
  padding: 0 8px;
}

/* 额外样式调整 */
/* 汇问台标签页样式 */
.huiwentai-tab:hover {
  color: #1890ff;
}

.huiwentai-tab.active {
  color: #1890ff;
  border-bottom-color: #1890ff;
}

@media (max-width: 768px) {
  .header {
    padding: 20px;
    text-align: center;
  }
  .header h1 {
    font-size: 1.2em;
  }
  .admin-tabs {
    flex-wrap: wrap;
  }
  .admin-tab {
    flex: 1;
    min-width: 100px;
  }
}

/* ===================== 首页优化样式 ===================== */

/* 首页容器 */
.home-page {
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  padding: 30px;
  border-radius: 12px;
}

/* 欢迎横幅区域 */
.welcome-banner {
  background: linear-gradient(135deg, #0a2463 0%, #1e3a8a 100%);
  border-radius: 16px;
  padding: 30px;
  margin-bottom: 30px;
  box-shadow: 0 10px 40px rgba(10, 36, 99, 0.3);
  position: relative;
  overflow: hidden;
}

.welcome-banner::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 100%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: shimmer 3s infinite;
}

@keyframes shimmer {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  z-index: 1;
}

.welcome-text {
  text-align: left;
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: white;
  margin: 0 0 10px 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.welcome-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

.welcome-user {
  display: flex;
  align-items: center;
  gap: 15px;
  background: rgba(255, 255, 255, 0.15);
  padding: 15px 25px;
  border-radius: 50px;
  backdrop-filter: blur(10px);
}

.user-avatar {
  width: 50px;
  height: 50px;
  background: linear-gradient(135deg, #00c6fb 0%, #005bea 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  color: white;
  box-shadow: 0 4px 15px rgba(240, 147, 251, 0.4);
}

.user-greeting {
  display: flex;
  flex-direction: column;
}

.greeting-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

.user-name {
  font-size: 18px;
  font-weight: 600;
  color: white;
}

/* 快捷入口 */
.quick-actions {
  display: flex;
  gap: 20px;
  margin-top: 25px;
  position: relative;
  z-index: 1;
}

.quick-action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 15px 25px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.quick-action-item:hover {
  background: rgba(255, 255, 255, 0.25);
  transform: translateY(-3px);
}

.action-icon {
  font-size: 28px;
}

.action-text {
  font-size: 14px;
  color: white;
  font-weight: 500;
}

/* 本月数据展示样式 */
.quick-action-item.monthly-stats {
  flex: 1;
  flex-direction: row;
  padding: 12px 20px;
  cursor: default;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.quick-action-item.monthly-stats:hover {
  transform: none;
  background: rgba(255, 255, 255, 0.2);
}

.monthly-stats-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 20px;
  width: 100%;
}

.monthly-stats-content .stats-title {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
  white-space: nowrap;
}

.monthly-stats-content .stats-row {
  display: flex;
  align-items: center;
  gap: 15px;
}

.monthly-stats-content .stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.monthly-stats-content .stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}

.monthly-stats-content .stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.monthly-stats-content .stat-divider {
  color: rgba(255, 255, 255, 0.3);
  font-size: 20px;
  margin: 0 5px;
}

/* 数据统计区域 */
.stats-section {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 30px;
  background: transparent;
}

.stats-card {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 25px;
  display: flex;
  align-items: center;
  gap: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.stats-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.stats-icon {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}

.stats-info {
  display: flex;
  flex-direction: column;
}

.stats-number {
  font-size: 32px;
  font-weight: 700;
  color: white;
  line-height: 1;
}

.stats-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 5px;
}

/* CMS内容区域 */
.cms-home-section {
  background: transparent;
  border-radius: 16px;
  padding: 15px;
}

.section-header {
  margin-bottom: 25px;
  text-align: left;
}

.section-main-title {
  font-size: 22px;
  font-weight: 700;
  color: white;
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
}

/* 栏目卡片 - 使用蓝色系渐变背景 */
.cms-columns {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.cms-column {
  background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(45, 74, 154, 0.4) 100%);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(100, 149, 237, 0.3);
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(10px);
}

.cms-column:hover {
  border-color: rgba(100, 149, 237, 0.5);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.25);
  transform: translateY(-3px);
  background: linear-gradient(135deg, rgba(30, 58, 138, 0.5) 0%, rgba(45, 74, 154, 0.5) 100%);
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(100, 149, 237, 0.3);
}

.column-title-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.column-icon {
  font-size: 20px;
  color: #6495ed;
}

.column-title {
  font-size: 18px;
  font-weight: 600;
  color: white;
  margin: 0;
}

.more-link {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  color: #87ceeb;
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(100, 149, 237, 0.2);
  transition: all 0.3s ease;
}

.more-link:hover {
  background: rgba(100, 149, 237, 0.3);
  color: #b0e0e6;
  transform: translateX(3px);
}

.more-arrow {
  transition: transform 0.3s ease;
}

.more-link:hover .more-arrow {
  transform: translateX(3px);
}

/* 文章列表 */
.column-articles {
  min-height: 150px;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 25px;
  color: rgba(255, 255, 255, 0.8);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(100, 149, 237, 0.3);
  border-top-color: #6495ed;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon,
.empty-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.article-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid transparent;
}

.article-item:hover {
  background: rgba(100, 149, 237, 0.15);
  border-color: rgba(100, 149, 237, 0.3);
  transform: translateX(5px);
}

.article-index {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #6495ed 0%, #4169e1 100%);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  margin-right: 10px;
  flex-shrink: 0;
}

.article-title {
  flex: 1;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.article-date {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
  flex-shrink: 0;
}

/* CMS 首页栏目标题样式 */
.column-title {
  display: inline-block;
  color: white !important;
  padding: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  font-size: 16px !important;
  font-weight: 600 !important;
}

.column-title:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(100, 149, 237, 0.4);
}

/* 文章详情页面动画 */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    transform: translateY(30px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* 文章详情modal样式 */
.article-detail-modal {
  animation: fadeIn 0.3s ease;
}

.article-detail-content {
  animation: slideUp 0.3s ease;
}

/* 文章内容体样式 */
.article-content-body {
  color: rgba(255, 255, 255, 0.9);
}

.article-content-body p {
  margin-bottom: 1em;
  color: rgba(255, 255, 255, 0.9);
}

.article-content-body h1,
.article-content-body h2,
.article-content-body h3,
.article-content-body h4,
.article-content-body h5,
.article-content-body h6 {
  color: white;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
}

.article-content-body ul,
.article-content-body ol {
  margin-left: 1.5em;
  margin-bottom: 1em;
}

.article-content-body li {
  margin-bottom: 0.5em;
  color: rgba(255, 255, 255, 0.9);
}

.article-content-body a {
  color: #4facfe;
  text-decoration: none;
}

.article-content-body a:hover {
  text-decoration: underline;
}

.article-content-body img {
  max-width: 100%;
  border-radius: 8px;
  margin: 1em 0;
}

.article-content-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
}

.article-content-body th,
.article-content-body td {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.9);
}

.article-content-body th {
  background: rgba(255, 255, 255, 0.15);
  font-weight: bold;
}

.article-content-body blockquote {
  margin: 1em 0;
  padding: 15px 20px;
  background: rgba(255, 255, 255, 0.1);
  border-left: 4px solid #4facfe;
  border-radius: 0 8px 8px 0;
  color: rgba(255, 255, 255, 0.8);
}

.article-content-body pre {
  background: rgba(0, 0, 0, 0.3);
  padding: 15px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1em 0;
}

.article-content-body code {
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  color: #4facfe;
}

.article-content-body pre code {
  background: transparent;
  padding: 0;
}
</style>
