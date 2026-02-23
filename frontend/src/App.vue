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
const activeModule = ref('home'); // home, data, assessment, analysis, spotcheck, tools, chengguantong, cms, map, huiwentai

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

// CMS状态管理
const cmsCategories = ref([]);
const cmsArticles = ref([]);
const allHomeArticles = ref([]);
const selectedCategory = ref(null);
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
const adminActiveTab = ref('users'); // users, system
const systemConfigTab = ref('data'); // data, general, security, logs, cms
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

// 表格可见性状态管理
const tableVisibility = ref({});

// 小工具模块状态管理
const activeToolTab = ref('natural-language'); // natural-language, huanwei-assignment, other
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
  tools: false,
  chengguantong: false,
  map: false,
  huiwentai: false
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
  { icon: '📊', text: '读取数据...' },
  { icon: '⏰', text: '处理时间数据...' },
  { icon: '🤖', text: '调用大模型分析...' },
  { icon: '📝', text: '生成分析报告...' },
  { icon: '✅', text: '分析完成!' }
]);
const currentStep = ref(0);

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

// 初始化时获取数据库表
onMounted(() => {
  fetchTables();
  // 初始化表格可见性状态
  initTableVisibility();
  // 首页也需要获取CMS数据
  fetchCMSCategories();
});

// 监听系统配置标签页变化，当切换到cms标签时获取CMS数据
watch(
  () => systemConfigTab.value,
  (newTab) => {
    if (newTab === 'cms') {
      fetchCMSCategories();
    }
  }
);

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
    currentStep.value = 0;
    analysisMessage.value = '分析中...';
    console.log('开始分析，表名:', selectedTable.value, '分析类型:', selectedAnalysisType.value);
    
    // 步骤1: 读取数据
    currentStep.value = 1;
    analysisMessage.value = '读取数据...';
    
    // 步骤2: 处理时间数据
    currentStep.value = 2;
    analysisMessage.value = '处理时间数据...';
    
    // 步骤3: 调用大模型分析
    currentStep.value = 3;
    analysisMessage.value = '调用大模型分析...';
    
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        table_name: selectedTable.value,
        analysis_type: selectedAnalysisType.value
      })
    });
    
    console.log('分析请求响应状态:', response.status);
    
    // 步骤4: 生成分析报告
    currentStep.value = 4;
    analysisMessage.value = '生成分析报告...';
    
    const data = await response.json();
    console.log('分析请求响应数据:', data);
    
    if (data.error) {
      analysisMessage.value = 'Error: ' + data.error;
      console.error('分析错误:', data.error);
    } else {
      analysisResult.value = data;
          console.log('分析结果已保存:', analysisResult.value);
          analysisMessage.value = '分析完成';
          // 步骤5: 分析完成
          currentStep.value = 4;
          console.log('分析完成，结果已显示在当前页面');
          console.log('当前模块:', activeModule.value);
    }
  } catch (error) {
    analysisMessage.value = 'Error analyzing data: ' + error.message;
    console.error('Error analyzing data:', error);
  } finally {
    loading.value = false;
    console.log('分析完成，加载状态已重置');
  }
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

// 切换模块
function switchModule(module) {
  activeModule.value = module;
  // 切换到数据分析模块时重新获取表列表（应用可见性过滤）
  if (module === 'analysis') {
    console.log('切换到数据分析模块，获取可见的数据表');
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
      zoom: 11,
      center: [110.99825, 35.0378], // 运城市中心坐标
      resizeEnable: true,
      mapStyle: 'amap://styles/light'
    });
    
    // 高德地图2.0版本已移除内置控件，使用地图默认控件
    // 如需添加控件，请参考高德地图2.0文档使用新控件库
    
    // 添加运城市标记
    const marker = new window.AMap.Marker({
      position: [110.99825, 35.0378],
      title: '运城市',
      map: mapInstance.value
    });
    
    // 添加信息窗口
    const infoWindow = new window.AMap.InfoWindow({
      content: '<div style="padding: 10px;"><h3>运城市</h3><p>山西省地级市</p></div>',
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
      // 暂时不清除本地存储，避免刷新页面后回到登录页
      // localStorage.removeItem('token');
      // localStorage.removeItem('userInfo');
      // userInfo.value = null;
      // isLoggedIn.value = false;
      // showLogin.value = true;
    }
  } catch (error) {
    console.error('Token check error:', error);
    // 暂时不清除本地存储，避免刷新页面后回到登录页
    // localStorage.removeItem('token');
    // localStorage.removeItem('userInfo');
    // userInfo.value = null;
    // isLoggedIn.value = false;
    // showLogin.value = true;
  }
}

// 获取请求头，包含token
function getAuthHeaders() {
  const token = localStorage.getItem('token');
  return {
    'Authorization': `Bearer ${token}`
  };
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
    tools: Boolean(user.permissions?.tools) || false,
    chengguantong: Boolean(user.permissions?.chengguantong) || false,
    map: Boolean(user.permissions?.map) || false,
    huiwentai: Boolean(user.permissions?.huiwentai) || false
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
    tools: false,
    chengguantong: false,
    map: false,
    huiwentai: false
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
      // 默认选择第一个栏目
      if (data.categories.length > 0 && !selectedCategory.value) {
        selectedCategory.value = data.categories[0];
        await fetchCMSArticles(data.categories[0].id);
      }
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
    console.log('请求URL:', `/api/articles/category/${categoryId}?include_drafts=true&page=${page}&per_page=${cmsArticlesPerPage.value}`);
    
    const response = await fetch(`/api/articles/category/${categoryId}?include_drafts=true&page=${page}&per_page=${cmsArticlesPerPage.value}`);
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
    const response = await fetch('/api/articles?include_drafts=true');
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
  selectedCategory.value = category;
  cmsArticlesPage.value = 1;
  await fetchCMSArticles(category.id, 1);
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
    huanweiMessage.value = '处理中...';
    
    const formData = new FormData();
    formData.append('file', huanweiFile.value);
    
    const response = await fetch('/api/tools/huanwei-assignment', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });
    
    if (response.ok) {
      // 处理文件下载
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      huanweiDownloadUrl.value = url;
      huanweiMessage.value = '处理完成，请点击下方链接下载文件';
    } else {
      const data = await response.json();
      huanweiError.value = data.error || '处理失败';
      huanweiMessage.value = '';
    }
  } catch (error) {
    huanweiError.value = '处理失败: ' + error.message;
    huanweiMessage.value = '';
    console.error('Error processing huanwei file:', error);
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
        createdAt: new Date().toISOString()
      },
      {
        taskId: 'TASK002',
        description: '示例问题：路灯损坏',
        request: '请维修路灯',
        contact: '13900139000',
        createdAt: new Date().toISOString()
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
    fetchHuiwentaiTasks();
  } else if (tab === 'daily-reports') {
    fetchHuiwentaiDailyReports();
  }
}

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
    reported: report.accepted !== undefined && report.accepted !== null ? report.accepted : '-',
    accepted: report.collectorAccepted !== undefined && report.collectorAccepted !== null ? report.collectorAccepted : '-',
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
  content += `采集员上报受理:${report.collectorAccepted || 0}\n`;
  content += `重点领域日常巡查受理:${report.keyAreaPatrol || 0}\n`;
  content += `12345系统转办:${report.system12345 || 0}\n`;
  content += `民呼我应:${report.minhuWoYing || 0}\n`;
  content += `视频监控: ${report.videoMonitor || 0}\n`;
  content += `智能分析:${report.smartAnalysis || 0}\n`;
  content += `市民举报系统受理:${report.citizenReport || 0}\n\n`;
  
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

// 监听切换到汇问台模块时加载数据
watch(
  () => activeModule.value,
  (newModule) => {
    if (newModule === 'huiwentai') {
      fetchHuiwentaiTasks();
    }
  }
);
</script>

<template>
  <div class="system-container">
    <!-- 顶部标题栏 -->
    <div class="header" :style="{ backgroundImage: `url(${headerBg})` }">
      <h1>运城市智慧城市管理平台-一站通</h1>
      <div v-if="isLoggedIn" class="user-info">
        <span class="username">{{ userInfo?.username }} ({{ userInfo?.role }})</span>
        <button class="logout-btn" @click="logout">登出</button>
      </div>
    </div>
    
    <!-- 调试信息已移除 -->
    
    <!-- 登录弹窗 -->
    <div v-if="showLogin" class="login-modal">
      <div class="login-form">
        <h2>用户登录</h2>
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
          {{ loginLoading ? '登录中...' : '登录' }}
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
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_analysis)" class="tab" :class="{ active: activeModule === 'analysis' }" @click="switchModule('analysis')">
        数据分析
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.spotcheck)" class="tab" :class="{ active: activeModule === 'spotcheck' }" @click="switchModule('spotcheck')">
        案件抽查
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.map)" class="tab" :class="{ active: activeModule === 'map' }" @click="switchModule('map')">
        地图服务
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.chengguantong)" class="tab" :class="{ active: activeModule === 'chengguantong' }" @click="switchModule('chengguantong')">
        城管通
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.huiwentai)" class="tab" :class="{ active: activeModule === 'huiwentai' }" @click="switchModule('huiwentai')">
        汇问台
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.tools)" class="tab" :class="{ active: activeModule === 'tools' }" @click="switchModule('tools')">
        小工具
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin'" class="tab" :class="{ active: activeModule === 'admin' }" @click="switchModule('admin')">
        管理员管理
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div v-if="isLoggedIn" class="main-content">
      <!-- 首页模块 -->
      <div v-if="activeModule === 'home'" class="tab-content">
        <!-- CMS内容展示 -->
        <div class="cms-home-section" style="margin-top: 20px;">
          <div class="cms-columns" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 40px;">
            <div v-for="(category, index) in cmsCategories" :key="category.id" class="cms-column" style="padding: 25px; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); background-color: #ffffff;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 class="column-title" style="font-size: 22px; font-weight: bold; margin: 0; color: #333;">{{ category.name }}</h3>
                <a href="#" class="more-link" style="font-size: 16px; color: #666; text-decoration: none; padding: 6px 12px; border: 1px solid #ddd; border-radius: 4px;" @click.prevent="showAllArticles(category.id)">更多</a>
              </div>
              <div class="column-articles">
                <div v-if="cmsLoading" class="loading" style="font-size: 16px; padding: 20px; text-align: center; color: #666;">加载中...</div>
                <div v-else-if="cmsError" class="error" style="font-size: 16px; padding: 20px; text-align: center; color: #ff4d4f;">{{ cmsError }}</div>
                <div v-else-if="getCategoryArticles(category.id).length === 0" class="empty" style="font-size: 16px; padding: 20px; text-align: center; color: #999;">该栏目下暂无文章</div>
                <div v-else class="articles-list" style="list-style: none; padding: 0; margin: 0;">
                  <div v-for="article in getCategoryArticles(category.id)" :key="article.id" class="article-item" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding: 8px; border-radius: 4px; transition: all 0.3s ease;" @click="fetchArticleDetail(article.id)" :style="{ backgroundColor: 'hover' === 'hover' ? '#f5f5f5' : 'transparent' }" @mouseenter="$event.currentTarget.style.backgroundColor='#f5f5f5'" @mouseleave="$event.currentTarget.style.backgroundColor='transparent'">
                    <span style="flex: 1; font-size: 16px; color: #333; line-height: 1.4; text-align: left;">
                      <span style="margin-right: 12px; color: #1890ff;">•</span>
                      {{ article.title }}
                    </span>
                    <span style="font-size: 14px; color: #999; white-space: nowrap; margin-left: 15px;">
                      [{{ formatDate(article.published_at || article.created_at) }}]
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      

      
      <!-- 汇问台模块 -->
      <div v-if="activeModule === 'huiwentai' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.huiwentai))" class="tab-content">
        <h2 class="section-title">汇问台</h2>
        <div class="huiwentai-section" style="max-width: 1000px; margin: 0 auto;">
          <!-- 标签页导航 -->
          <div class="huiwentai-tabs" style="display: flex; margin-bottom: 24px; border-bottom: 2px solid #e8e8e8; background: #fafafa; border-radius: 8px 8px 0 0; overflow: hidden;">
            <div 
              class="huiwentai-tab" 
              :class="{ active: huiwentaiActiveTab === 'tasks' }"
              @click="switchHuiwentaiTab('tasks')"
              style="padding: 14px 28px; cursor: pointer; font-size: 16px; font-weight: 500; color: #666; border-bottom: 3px solid transparent; transition: all 0.3s; position: relative; background: transparent;"
              :style="{ 
                color: huiwentaiActiveTab === 'tasks' ? '#1890ff' : '#666',
                background: huiwentaiActiveTab === 'tasks' ? '#e6f7ff' : 'transparent',
                borderBottomColor: huiwentaiActiveTab === 'tasks' ? '#1890ff' : 'transparent',
                fontWeight: huiwentaiActiveTab === 'tasks' ? '600' : '500'
              }"
            >
              问题列表
            </div>
            <div 
              class="huiwentai-tab" 
              :class="{ active: huiwentaiActiveTab === 'daily-reports' }"
              @click="switchHuiwentaiTab('daily-reports')"
              style="padding: 14px 28px; cursor: pointer; font-size: 16px; font-weight: 500; color: #666; border-bottom: 3px solid transparent; transition: all 0.3s; position: relative; background: transparent;"
              :style="{ 
                color: huiwentaiActiveTab === 'daily-reports' ? '#1890ff' : '#666',
                background: huiwentaiActiveTab === 'daily-reports' ? '#e6f7ff' : 'transparent',
                borderBottomColor: huiwentaiActiveTab === 'daily-reports' ? '#1890ff' : 'transparent',
                fontWeight: huiwentaiActiveTab === 'daily-reports' ? '600' : '500'
              }"
            >
              日报数据
            </div>
          </div>
          
          <!-- 刷新按钮 -->
          <div style="margin-bottom: 20px; text-align: right;">
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
          <div v-if="huiwentaiLoading" class="loading" style="font-size: 16px; padding: 40px; text-align: center; color: #666;">
            加载数据中...
          </div>
          
          <!-- 错误信息 -->
          <div v-else-if="huiwentaiError" class="error" style="font-size: 16px; padding: 40px; text-align: center; color: #ff4d4f;">
            <p>{{ huiwentaiError }}</p>
            <p style="font-size: 14px; color: #999; margin-top: 10px;">请检查：</p>
            <ul style="font-size: 14px; color: #999; text-align: left; max-width: 400px; margin: 10px auto;">
              <li>1. 云环境ID是否正确</li>
              <li>2. 云数据库安全规则是否允许读取操作</li>
              <li>3. 网络连接是否正常</li>
              <li>4. {{ huiwentaiActiveTab === 'tasks' ? 'tasks' : 'daily-reports' }}集合是否存在</li>
            </ul>
            <p style="font-size: 14px; color: #999; margin-top: 10px;">详细错误信息请查看浏览器控制台</p>
          </div>
          
          <!-- 任务数据标签页内容 -->
          <div v-else-if="huiwentaiActiveTab === 'tasks'" class="tasks-table">
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px; text-align: left;">
              <thead>
                <tr style="background-color: #f5f5f5;">
                  <th style="padding: 12px; border: 1px solid #ddd;">任务号</th>
                  <th style="padding: 12px; border: 1px solid #ddd;">问题描述</th>
                  <th style="padding: 12px; border: 1px solid #ddd;">诉求</th>
                  <th style="padding: 12px; border: 1px solid #ddd; min-width: 150px;">联系方式</th>
                  <th style="padding: 12px; border: 1px solid #ddd;">创建时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="huiwentaiTasks.length === 0">
                  <td colspan="5" style="padding: 40px; border: 1px solid #ddd; text-align: center;">暂无任务数据</td>
                </tr>
                <tr v-for="task in huiwentaiTasks" :key="task.taskId || task._id" style="background-color: white;">
                  <td style="padding: 12px; border: 1px solid #ddd;">{{ task.taskId || task._id || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid #ddd;">{{ task.description || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid #ddd;">{{ task.request || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid #ddd;">{{ task.contact || '无' }}</td>
                  <td style="padding: 12px; border: 1px solid #ddd;">{{ task.createdAt ? new Date(task.createdAt).toLocaleString() : '无' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          
          <!-- 日报数据标签页内容 -->
          <div v-else-if="huiwentaiActiveTab === 'daily-reports'" class="daily-reports-section">
            <div v-if="huiwentaiDailyReports.length === 0" style="padding: 40px; text-align: center; color: #999;">
              暂无日报数据
            </div>
            <div v-else class="reports-list" style="display: flex; flex-direction: column; gap: 16px; margin-top: 20px;">
              <div 
                v-for="report in huiwentaiDailyReports" 
                :key="report._id"
                class="report-card"
                @click="toggleReportExpand(report)"
                style="border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer; transition: all 0.3s ease;"
                :style="{ 
                  backgroundColor: expandedReportId === (report._id || report.id) 
                    ? (parseReportSummary(report).shift.includes('夜') ? '#f9f0ff' : '#e6f7ff') 
                    : (parseReportSummary(report).shift.includes('夜') ? '#fdfbf7' : '#f0f9ff'),
                  transform: expandedReportId === (report._id || report.id) ? 'scale(1.01)' : 'scale(1)',
                  boxShadow: expandedReportId === (report._id || report.id) 
                    ? (parseReportSummary(report).shift.includes('夜') ? '0 4px 16px rgba(114, 46, 209, 0.15)' : '0 4px 16px rgba(24, 144, 255, 0.15)') 
                    : '0 2px 8px rgba(0,0,0,0.06)'
                }"
              >
                <!-- 卡片头部 - 关键信息 -->
                <div 
                  class="report-summary" 
                  style="padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; background-color: #fafafa; transition: background-color 0.3s;"
                  :style="{
                    backgroundColor: parseReportSummary(report).shift.includes('夜') ? '#faf5ff' : '#f0f9ff'
                  }"
                >
                  <div style="display: flex; gap: 32px; align-items: center;">
                    <div style="min-width: 120px;">
                      <span style="font-size: 12px; color: #999;">日期</span>
                      <div style="font-size: 16px; font-weight: 600; color: #333; margin-top: 4px;">
                        {{ parseReportSummary(report).date }}
                      </div>
                    </div>
                    <div style="min-width: 100px;">
                      <span style="font-size: 12px; color: #999;">值班人员</span>
                      <div style="font-size: 16px; color: #333; margin-top: 4px;">
                        {{ parseReportSummary(report).person }}
                      </div>
                    </div>
                    <div style="min-width: 90px;">
                      <span style="font-size: 12px; color: #999;">班次</span>
                      <div style="margin-top: 4px;">
                        <span 
                          style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: 500;"
                          :style="{
                            backgroundColor: parseReportSummary(report).shift.includes('夜') ? '#f9f0ff' : '#e6f7ff',
                            color: parseReportSummary(report).shift.includes('夜') ? '#722ed1' : '#1890ff',
                            border: parseReportSummary(report).shift.includes('夜') ? '1px solid #d3adf7' : '1px solid #91d5ff'
                          }"
                        >
                          {{ parseReportSummary(report).shift }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div style="display: flex; gap: 24px; align-items: center;">
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: #999;">上报</span>
                      <div style="font-size: 20px; font-weight: 600; color: #1890ff; margin-top: 4px;">
                        {{ parseReportSummary(report).reported }}
                      </div>
                    </div>
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: #999;">受理</span>
                      <div style="font-size: 20px; font-weight: 600; color: #52c41a; margin-top: 4px;">
                        {{ parseReportSummary(report).accepted }}
                      </div>
                    </div>
                    <div style="text-align: center;">
                      <span style="font-size: 12px; color: #999;">办结</span>
                      <div style="font-size: 20px; font-weight: 600; color: #fa8c16; margin-top: 4px;">
                        {{ parseReportSummary(report).completed }}
                      </div>
                    </div>
                    <div style="margin-left: 16px; color: #999; font-size: 20px;">
                      {{ expandedReportId === (report._id || report.id) ? '▼' : '▶' }}
                    </div>
                  </div>
                </div>
                
                <!-- 展开的详细内容 -->
                <div 
                  v-if="expandedReportId === (report._id || report.id)"
                  class="report-detail"
                  style="padding: 24px 20px; border-top: 1px solid #f0f0f0; background-color: white;"
                >
                  <div style="white-space: pre-wrap; line-height: 2.2; color: #333; font-size: 15px; font-family: 'Microsoft YaHei', sans-serif;">
                    {{ formatReportContent(report) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 考核计分模块 -->
      <div v-if="activeModule === 'assessment' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.assessment))" class="tab-content">
        <h2 class="section-title">考核计分</h2>
        <div class="assessment-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 说明信息 -->
          <div style="margin-bottom: 25px; padding: 16px; background: linear-gradient(135deg, #fff3cd 0%, #ffe082 5%); border-left: 4px solid #ffc107; border-radius: 6px; color: #856404;">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
              <span style="font-size: 20px; flex-shrink: 0;">⚠️</span>
              <div>
                <div style="font-weight: 600; margin-bottom: 6px;">计算说明</div>
                <p style="margin: 0; line-height: 1.5; font-size: 14px;">超时案件计算：结案时间 > 捆绑处置截止时间判定的，与实际超时计算有出入</p>
              </div>
            </div>
          </div>
          
          <!-- 配置区域 -->
          <div style="padding: 25px; background: white; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
              <div>
                <label for="department-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: #333;">选择部门：</label>
                <select id="department-select" v-model="selectedDepartment" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">
                  <option value="">-- 请选择部门 --</option>
                  <option value="城市综合行政执法队">城市综合行政执法队</option>
                  <option value="市容环卫中心">市容环卫中心</option>
                  <option value="园林绿化服务中心（片区）">园林绿化服务中心（片区）</option>
                  <option value="园林绿化服务中心（公园广场）">园林绿化服务中心（公园广场）</option>
                </select>
              </div>
              <div>
                <label for="table-select-assessment" style="display: block; font-weight: 600; margin-bottom: 10px; color: #333;">选择数据表：</label>
                <select id="table-select-assessment" v-model="selectedAssessmentTable" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">
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
              style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
              @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)'"
              @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
            >
              <span v-if="loading">⏳ 计算中...</span>
              <span v-else>📊 开始计算</span>
            </button>
            
            <!-- 消息提示 -->
            <div v-if="assessmentMessage" style="margin-top: 15px; padding: 12px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px;">
              ✓ {{ assessmentMessage }}
            </div>
          </div>
          
          <!-- 考核结果显示 -->
          <div v-if="assessmentResult" style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
            <h3 style="margin: 0 0 20px 0; padding-bottom: 15px; border-bottom: 2px solid #667eea; font-size: 20px; color: #333;">📋 考核结果</h3>
            
            <!-- 结果摘要 -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px;">
              <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; color: white;">
                <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">总案件数</div>
                <div style="font-size: 32px; font-weight: bold;">{{ assessmentResult.total_cases }}</div>
              </div>
              <div style="padding: 20px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 8px; color: white;">
                <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">平均得分</div>
                <div style="font-size: 32px; font-weight: bold;">{{ assessmentResult.score }} 分</div>
              </div>
            </div>
            
            <!-- 排名表格 -->
            <div v-if="assessmentResult.team_results">
              <h4 style="margin: 0 0 15px 0; color: #333; font-size: 16px;">🏆 片区排名</h4>
              <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                  <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
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
                    <tr v-for="(team, index) in assessmentResult.team_results" :key="team.department" :style="{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : '#ffffff', transition: 'all 0.3s ease' }" @mouseenter="$event.currentTarget.style.backgroundColor='#e8eef9'" @mouseleave="$event.currentTarget.style.backgroundColor=(index % 2 === 0 ? '#f8f9fa' : '#ffffff')">
                      <td style="padding: 12px; text-align: center; font-weight: 600; color: #667eea;">
                        <span style="display: inline-block; width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 50%; line-height: 32px; font-size: 14px;">{{ team.rank }}</span>
                      </td>
                      <td style="padding: 12px; text-align: left; color: #333;">{{ team.department }}</td>
                      <td style="padding: 12px; text-align: center; color: #555;">{{ team.total_cases }}</td>
                      <td style="padding: 12px; text-align: center; color: #2ecc71; font-weight: 600;">{{ team.on_time_count }}</td>
                      <td style="padding: 12px; text-align: center; color: #e74c3c; font-weight: 600;">{{ team.overdue_count }}</td>
                      <td style="padding: 12px; text-align: center; color: #f39c12;">{{ team.delay_count }}</td>
                      <td style="padding: 12px; text-align: center; color: #9b59b6;">{{ team.rework_count }}</td>
                      <td style="padding: 12px; text-align: center; font-weight: bold; font-size: 16px;">
                        <span style="display: inline-block; padding: 4px 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 20px;">{{ team.score }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 数据分析模块 -->
      <div v-if="activeModule === 'analysis' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.data_analysis))" class="tab-content">
        <h2 class="section-title">📊 数据分析</h2>
        <div class="config-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 分析配置区域 -->
          <div style="padding: 25px; background: white; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px;">
              <div>
                <label for="table-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: #333;">选择数据表：</label>
                <select id="table-select" v-model="selectedTable" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">
                  <option value="">-- 请选择 --</option>
                  <option v-for="table in tables" :key="table" :value="table">
                    {{ table }}
                  </option>
                </select>
              </div>
              <div>
                <label for="analysis-select" style="display: block; font-weight: 600; margin-bottom: 10px; color: #333;">分析类型：</label>
                <select id="analysis-select" v-model="selectedAnalysisType" :disabled="loading" style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">
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
              style="width: 100%; padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
              @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)'"
              @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
            >
              <span v-if="loading">⏳ 分析中...</span>
              <span v-else>🔍 开始分析</span>
            </button>
            
            <!-- 消息提示 -->
            <div v-if="analysisMessage" style="margin-top: 15px; padding: 12px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px;">
              ✓ {{ analysisMessage }}
            </div>
            
            <!-- 分析进度显示 -->
            <div v-if="loading" style="margin-top: 25px; padding: 20px; background: linear-gradient(135deg, #f5f7ff 0%, #f8f6ff 100%); border-radius: 6px; border-left: 4px solid #667eea;">
              <div style="font-weight: 600; color: #667eea; margin-bottom: 15px; font-size: 14px;">⏳ 分析进度</div>
              <div v-for="(step, index) in analysisSteps" :key="index" style="display: flex; align-items: center; margin-bottom: 10px; padding: 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.5); transition: all 0.3s ease;" :class="{ active: currentStep >= index }">
                <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 50%; margin-right: 12px; font-size: 16px; flex-shrink: 0;">{{ step.icon }}</div>
                <div style="color: #333; font-size: 14px; font-weight: 500;">{{ step.text }}</div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 分析结果 -->
        <div v-if="analysisResult" style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
          <!-- 结果标题 -->
          <div style="margin-bottom: 25px; padding-bottom: 15px; border-bottom: 2px solid #667eea;">
            <h3 style="margin: 0; font-size: 20px; color: #333;">📈 {{ analysisResult.table_name }} - {{ getAnalysisTypeName(analysisResult.analysis_type) }}</h3>
            <p style="margin: 12px 0 0 0; color: #666; font-size: 14px; line-height: 1.6;">{{ analysisResult.data_summary }}</p>
          </div>
          
          <div class="result-details">
            <!-- 图表展示 -->
            <div v-if="analysisResult.chart_data" class="charts-section" style="margin-bottom: 30px;">
              <h4 style="margin: 0 0 20px 0; color: #667eea; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                <span>📊</span>
                <span>数据可视化</span>
              </h4>
              <div class="chart-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">
                <!-- 时间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'time_analysis'">
                  <div class="chart-item" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📅 日案件量趋势</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">⏰ 小时级高峰时段</h5>
                    <div ref="hourlyChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 空间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'space_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.street" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">🏘️ 各街道案件密度</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.community" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">🏢 各社区案件密度</h5>
                    <div ref="spaceChart2" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.area" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📍 各片区案件密度</h5>
                    <div ref="spaceChart3" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 来源分析图表 -->
                <template v-if="analysisResult.analysis_type === 'source_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.source" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8; grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">🔗 案件来源分布</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 案件类型分析图表 -->
                <template v-if="analysisResult.analysis_type === 'type_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.type" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8; grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📋 案件类型分布</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                <!-- 重复案件分析图表 -->
                <template v-if="analysisResult.analysis_type === 'duplicate_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_duplicates" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">❓ 问题描述重复TOP10</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_duplicates" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📍 地址描述重复TOP10</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_type_distribution" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">🏷️ 地址描述类型占比</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.combined_duplicates" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">🔀 组合重复TOP10</h5>
                    <div ref="spaceChart2" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.violation_type_distribution" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">⚠️ 重复案件违规类型占比</h5>
                    <div ref="spaceChart3" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
                
                <!-- 对比上月分析图表 -->
                <template v-if="analysisResult.analysis_type === 'monthly_comparison'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.monthly_comparison" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8; grid-column: 1 / -1;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📊 上月vs本月案件量对比</h5>
                    <div ref="dailyChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.case_size_comparison" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📈 案件大小类别变化</h5>
                    <div ref="sourceChart" class="chart" style="height: 300px;"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_trend" style="padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e8e8e8;">
                    <h5 style="margin: 0 0 15px 0; color: #333; font-size: 14px; font-weight: 600;">📉 问题趋势变化</h5>
                    <div ref="spaceChart" class="chart" style="height: 300px;"></div>
                  </div>
                </template>
              </div>
            </div>
            
            <!-- 智能分析结果 -->
            <div v-if="analysisResult.analysis" style="margin-top: 30px; padding: 20px; background: linear-gradient(135deg, #f5f7ff 0%, #f8f6ff 100%); border-radius: 8px; border-left: 4px solid #667eea;">
              <h4 style="margin: 0 0 15px 0; color: #667eea; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                <span>🤖</span>
                <span>AI智能分析</span>
              </h4>
              <div style="line-height: 1.8; color: #333; font-size: 15px;" v-html="analysisResult.analysis.replace(/\n/g, '<br>')"></div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 案件抽查模块 -->
      <div v-if="activeModule === 'spotcheck' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.spotcheck))" class="tab-content">
        <h2 class="section-title">案件抽查</h2>
        <div class="spotcheck-section" style="max-width: 900px; margin: 0 auto;">
          <!-- 提示信息 -->
          <div style="margin-bottom: 25px; padding: 16px; background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border-left: 4px solid #667eea; border-radius: 6px; color: #555;">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
              <span style="font-size: 20px; flex-shrink: 0;">ℹ️</span>
              <div>
                <div style="font-weight: 600; color: #667eea; margin-bottom: 6px;">文件上传说明</div>
                <p style="margin: 0; line-height: 1.5;">支持上传 DOCX 或 XLSX 格式的文件，系统将使用大模型进行智能分析，并返回详细的案件质量评估结果。</p>
              </div>
            </div>
          </div>
          
          <!-- 文件上传区域 -->
          <div style="padding: 25px; background: white; border: 2px dashed #667eea; border-radius: 8px; margin-bottom: 25px;">
            <div class="form-group" style="margin-bottom: 20px;">
              <label for="spotcheck-file-input" style="display: block; font-weight: 600; margin-bottom: 12px; color: #333;">选择要分析的文件：</label>
              <input 
                type="file" 
                id="spotcheck-file-input"
                accept=".docx,.xlsx"
                @change="handleSpotcheckFileSelect"
                style="padding: 10px; border: 1px solid #ddd; border-radius: 6px; width: 100%; box-sizing: border-box; cursor: pointer;"
              >
              <div v-if="spotcheckFile" style="margin-top: 12px; padding: 10px 12px; background-color: #e8f5e9; color: #2e7d32; border-radius: 4px; border-left: 3px solid #4caf50;">
                ✓ 已选择：{{ spotcheckFile.name }}
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div style="display: flex; gap: 12px;">
              <button 
                @click="uploadAndAnalyzeSpotcheck"
                :disabled="!spotcheckFile || spotcheckLoading"
                style="flex: 1; padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 16px; transition: all 0.3s ease; disabled: { opacity: 0.6, cursor: 'not-allowed' };"
                @mouseenter="$event.target.style.transform='translateY(-2px)'; $event.target.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)'"
                @mouseleave="$event.target.style.transform='translateY(0)'; $event.target.style.boxShadow='none'"
              >
                <span v-if="spotcheckLoading">⏳ 分析中...</span>
                <span v-else>📤 上传并分析</span>
              </button>
              <button 
                @click="clearSpotcheck"
                :disabled="spotcheckLoading"
                style="padding: 12px 24px; background-color: #95a5a6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s ease;"
                @mouseenter="$event.target.style.backgroundColor='#7f8c8d'"
                @mouseleave="$event.target.style.backgroundColor='#95a5a6'"
              >
                🔄 清除
              </button>
            </div>
            
            <!-- 消息提示 -->
            <div v-if="spotcheckMessage" style="margin-top: 15px; padding: 12px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px;">
              ✓ {{ spotcheckMessage }}
            </div>
            <div v-if="spotcheckError" style="margin-top: 15px; padding: 12px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 4px;">
              ✗ {{ spotcheckError }}
            </div>
          </div>
          
          <!-- 分析结果 -->
          <div v-if="spotcheckResult" style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
            <h3 style="margin-top: 0; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #667eea; font-size: 20px; color: #333;">分析结果</h3>
            
            <!-- 文件内容 -->
            <div v-if="spotcheckResult.file_content" style="margin-bottom: 25px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                <span style="font-size: 18px;">📄</span>
                <h4 style="margin: 0; color: #667eea; font-size: 16px;">读取的文件内容</h4>
              </div>
              <div style="background-color: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea; max-height: 300px; overflow-y: auto;">
                <p v-for="(line, index) in spotcheckResult.file_content.split('\n')" :key="index" v-if="line && line.trim()" style="margin: 8px 0; line-height: 1.5; color: #555; font-size: 14px;">
                  {{ line }}
                </p>
              </div>
            </div>
            
            <!-- 分析内容 -->
            <div v-if="spotcheckResult.analysis">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                <span style="font-size: 18px;">🔍</span>
                <h4 style="margin: 0; color: #667eea; font-size: 16px;">AI智能分析</h4>
              </div>
              <div style="background-color: #f8f9fa; padding: 20px; border-radius: 6px; border-left: 3px solid #764ba2; line-height: 1.8; color: #333;">
                <div v-html="spotcheckResult.analysis"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 小工具模块 -->
      <div v-if="activeModule === 'tools' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.tools))" class="tab-content">
        <h2 class="section-title">小工具</h2>
        
        <!-- 小工具标签页导航 -->
        <div class="tool-tabs" style="display: flex; margin-bottom: 20px; border-bottom: 1px solid #dee2e6;">
          <div 
            class="tool-tab" 
            :class="{ active: activeToolTab === 'natural-language' }"
            @click="activeToolTab = 'natural-language'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="activeToolTab === 'natural-language' ? { borderBottomColor: '#27ae60', color: '#27ae60' } : {}"
          >
            自然语言查询
          </div>
          <div 
            class="tool-tab" 
            :class="{ active: activeToolTab === 'huanwei-assignment' }"
            @click="activeToolTab = 'huanwei-assignment'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="activeToolTab === 'huanwei-assignment' ? { borderBottomColor: '#27ae60', color: '#27ae60' } : {}"
          >
            市容环卫案件分配
          </div>
          <div 
            class="tool-tab" 
            :class="{ active: activeToolTab === 'location-extraction' }"
            @click="activeToolTab = 'location-extraction'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="activeToolTab === 'location-extraction' ? { borderBottomColor: '#27ae60', color: '#27ae60' } : {}"
          >
            地址信息提取
          </div>
          <div 
            class="tool-tab" 
            :class="{ active: activeToolTab === 'data-cleaning' }"
            @click="activeToolTab = 'data-cleaning'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="activeToolTab === 'data-cleaning' ? { borderBottomColor: '#27ae60', color: '#27ae60' } : {}"
          >
            数据清洗脱敏
          </div>
          <div 
            class="tool-tab" 
            :class="{ active: activeToolTab === 'other' }"
            @click="activeToolTab = 'other'"
            style="padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-right: 10px; font-weight: bold;"
            :style="activeToolTab === 'other' ? { borderBottomColor: '#27ae60', color: '#27ae60' } : {}"
          >
            其他功能
          </div>
        </div>
        
        <!-- 自然语言查询标签页内容 -->
        <div v-if="activeToolTab === 'natural-language'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px;">
            <p>该模块允许输入自然语句，系统会自动将其转换为SQL语句并执行查询。</p>
          </div>
          
          <!-- 第二行：输入框和下拉菜单 -->
          <div class="input-section" style="margin-bottom: 20px;">
            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
              <div style="flex: 2;">
                <label for="natural-language-input" style="display: block; margin-bottom: 5px; font-weight: bold;">自然语言查询：</label>
                <textarea 
                  id="natural-language-input" 
                  v-model="naturalLanguageQuery" 
                  placeholder="例如：帮我查询12月份所有的市容环卫中心的案件" 
                  rows="1" 
                  :disabled="toolLoading"
                  style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; resize: vertical; font-size: 14px;"
                ></textarea>
              </div>
              <div style="flex: 1;">
                <label for="tool-table-select" style="display: block; margin-bottom: 5px; font-weight: bold;">选择数据表：</label>
                <select 
                  id="tool-table-select" 
                  v-model="selectedToolTable" 
                  :disabled="toolLoading"
                  style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;"
                >
                  <option value="">-- 请选择 --</option>
                  <option v-for="table in tables" :key="table" :value="table">
                    {{ table }}
                  </option>
                </select>
              </div>
            </div>
            
            <div class="button-group" style="display: flex; gap: 10px; margin-bottom: 15px;">
              <button 
                @click="executeNaturalLanguageQuery"
                :disabled="toolLoading || !naturalLanguageQuery || !selectedToolTable"
                class="btn-primary"
                style="flex: 1; padding: 12px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
              >
                <span v-if="toolLoading">处理中...</span>
                <span v-else>执行查询</span>
              </button>
              <button 
                @click="resetToolState"
                :disabled="toolLoading"
                class="btn-secondary"
                style="padding: 12px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;"
              >
                重置
              </button>
            </div>
            
            <div v-if="toolMessage" class="message success" style="padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ toolMessage }}
            </div>
            <div v-if="toolError" class="message error" style="padding: 10px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ toolError }}
            </div>
          </div>
          
          <!-- 第三行：生成的SQL语句 -->
          <!-- SQL语句现在只在弹框中显示，不再在原页面显示 -->
          
          <!-- 第四行：查询结果 -->
          <!-- 结果现在只通过弹框显示，不再在原页面显示 -->
        </div>
        
        <!-- 市容环卫案件分配标签页内容 -->
        <div v-if="activeToolTab === 'huanwei-assignment'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px;">
            <p>该模块允许上传Excel文件，为市容环卫中心的案件分配到各环卫部门（添加"环卫"前缀）。</p>
            <p style="color: #666; font-size: 14px; margin-top: 5px;"><strong>注意：</strong>请确保Excel文件中包含以下列：</p>
            <ul style="color: #666; font-size: 14px; margin-top: 5px; margin-left: 20px;">
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
              <div v-if="huanweiFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: #666;">
                已选择：{{ huanweiFile.name }}
              </div>
            </div>
            
            <div class="button-group" style="display: flex; gap: 10px; margin-bottom: 15px;">
              <button 
                @click="processHuanweiFile"
                :disabled="!huanweiFile || huanweiLoading"
                class="btn-primary"
                style="flex: 1; padding: 12px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
              >
                <span v-if="huanweiLoading">处理中...</span>
                <span v-else>处理文件</span>
              </button>
              <button 
                @click="resetHuanweiFile"
                :disabled="huanweiLoading"
                class="btn-secondary"
                style="padding: 12px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;"
              >
                重置
              </button>
            </div>
            
            <div v-if="huanweiMessage" class="message success" style="padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ huanweiMessage }}
            </div>
            <div v-if="huanweiError" class="message error" style="padding: 10px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ huanweiError }}
            </div>
          </div>
          
          <!-- 第三行：下载按钮 -->
          <div v-if="huanweiDownloadUrl" class="download-section" style="margin-top: 20px;">
            <a 
              :href="huanweiDownloadUrl"
              download
              style="display: inline-block; padding: 12px 24px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none;"
            >
              下载处理后的文件
            </a>
          </div>
        </div>
        
        <!-- 地址信息提取标签页内容 -->
        <div v-if="activeToolTab === 'location-extraction'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px;">
            <p>该模块允许上传Excel文件，从问题描述中提取地址信息并替换原文件中地址描述为“没有相关位置描述”“无位置描述”。</p>
            <p style="color: #666; font-size: 14px; margin-top: 5px;"><strong>注意：</strong>请确保Excel文件中包含以下列：</p>
            <ul style="color: #666; font-size: 14px; margin-top: 5px; margin-left: 20px;">
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
              <div v-if="locationFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: #666;">
                已选择：{{ locationFile.name }}
              </div>
            </div>
            
            <div class="button-group" style="display: flex; gap: 10px; margin-bottom: 15px;">
              <button 
                @click="processLocationFile"
                :disabled="!locationFile || locationLoading"
                class="btn-primary"
                style="flex: 1; padding: 12px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
              >
                <span v-if="locationLoading">处理中...</span>
                <span v-else>提取地址信息</span>
              </button>
              <button 
                @click="resetLocationFile"
                :disabled="locationLoading"
                class="btn-secondary"
                style="padding: 12px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;"
              >
                重置
              </button>
            </div>
            
            <div v-if="locationMessage" class="message success" style="padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ locationMessage }}
            </div>
            <div v-if="locationError" class="message error" style="padding: 10px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ locationError }}
            </div>
          </div>
          
          <!-- 第三行：下载按钮 -->
          <div v-if="locationDownloadUrl" class="download-section" style="margin-top: 20px;">
            <a 
              :href="locationDownloadUrl"
              download
              style="display: inline-block; padding: 12px 24px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none;"
            >
              下载处理后的文件
            </a>
          </div>
        </div>
        
        <!-- 数据清洗脱敏标签页内容 -->
        <div v-if="activeToolTab === 'data-cleaning'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px;">
            <p>该模块允许上传Excel文件，对数据进行清洗和脱敏处理，包括删除任务编号、车牌号、电话号码、姓名和精细地址等信息。</p>
            <p style="color: #666; font-size: 14px; margin-top: 5px;"><strong>处理说明：</strong></p>
            <ul style="color: #666; font-size: 14px; margin-top: 5px; margin-left: 20px;">
              <li>删除各种任务编号（数字串或字母+数字串）</li>
              <li>删除车牌号（如"晋M·E5191"）</li>
              <li>删除电话号码（手机和座机）</li>
              <li>删除姓名（如"张先生"、"李女士"等）</li>
              <li>删除精细地址（如几单元几室）</li>
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
              <div v-if="cleaningFile" class="file-info" style="margin-top: 5px; font-size: 14px; color: #666;">
                已选择：{{ cleaningFile.name }}
              </div>
            </div>
            
            <div class="button-group" style="display: flex; gap: 10px; margin-bottom: 15px;">
              <button 
                @click="fetchCleaningFields"
                :disabled="!cleaningFile || cleaningLoading"
                class="btn-primary"
                style="flex: 1; padding: 12px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
              >
                <span v-if="cleaningLoading">读取中...</span>
                <span v-else>读取文件字段</span>
              </button>
              <button 
                @click="resetCleaningFile"
                :disabled="cleaningLoading"
                class="btn-secondary"
                style="padding: 12px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;"
              >
                重置
              </button>
            </div>
            
            <div v-if="cleaningMessage" class="message success" style="padding: 10px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ cleaningMessage }}
            </div>
            <div v-if="cleaningError" class="message error" style="padding: 10px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 4px; margin-bottom: 15px;">
              {{ cleaningError }}
            </div>
          </div>
          
          <!-- 第三行：字段选择 -->
          <div v-if="cleaningFields.length > 0" class="fields-section" style="margin-bottom: 20px; padding: 20px; border: 1px solid #dee2e6; border-radius: 4px; background-color: #f9f9f9;">
            <h4 style="margin-top: 0; margin-bottom: 15px; color: #333;">字段选择</h4>
            <div class="field-selection" style="display: flex; flex-direction: column; gap: 15px;">
              <div style="display: flex; flex-direction: column;">
                <label style="margin-bottom: 5px; font-weight: bold;">选择字段：</label>
                <select 
                  v-model="selectedCleaningField"
                  style="padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; width: 300px;"
                >
                  <option value="">-- 请选择字段 --</option>
                  <option v-for="field in cleaningFields" :key="field" :value="field">
                    {{ field }}
                  </option>
                </select>
              </div>
            </div>
            
            <div class="button-group" style="display: flex; gap: 10px; margin-top: 20px;">
              <button 
                @click="processCleaningFile"
                :disabled="cleaningLoading || !selectedCleaningField"
                class="btn-primary"
                style="flex: 1; padding: 12px; background-color: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
              >
                <span v-if="cleaningLoading">处理中...</span>
                <span v-else>清洗处理</span>
              </button>
            </div>
          </div>
          
          <!-- 第四行：下载按钮 -->
          <div v-if="cleaningDownloadUrl" class="download-section" style="margin-top: 20px;">
            <a 
              :href="cleaningDownloadUrl"
              download
              style="display: inline-block; padding: 12px 24px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none;"
            >
              下载处理后的文件
            </a>
          </div>
        </div>
        

        
        <!-- 其他功能标签页内容 -->
        <div v-if="activeToolTab === 'other'" class="tools-section" style="max-width: 800px; margin: 0 auto;">
          <div style="padding: 40px; text-align: center; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
            <h3 style="margin-bottom: 20px;">其他功能</h3>
            <p>该功能正在开发中，敬请期待...</p>
          </div>
        </div>
      </div>
      
      <!-- 城管通模块 -->
      <div v-if="activeModule === 'chengguantong' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.chengguantong))" class="tab-content">
        <h2 class="section-title">城管通</h2>
        <div class="chengguantong-section" style="max-width: 1200px; margin: 0 auto;">
          <!-- 第一行：提示文字 -->
          <div class="tip-section" style="margin-bottom: 20px; padding: 15px; background-color: #e3f2fd; border: 1px solid #bbdefb; border-radius: 4px; color: #1565c0;">
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
                 border: 1px solid #ddd; 
                 border-radius: 16px; 
                 resize: vertical; 
                 font-size: 18px; 
                 font-family: Arial, sans-serif; 
                 min-height: 90px; 
                 /* 移除max-width限制，让文本框占满容器 */
                 line-height: 1.6;
                 box-sizing: border-box;"
        ></textarea>
              <!-- 确保padding不超出宽度 -->
              
              <div class="button-group" style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
                <button 
                  @click="resetChengguantong"
                  :disabled="chengguantongLoading"
                  class="btn-secondary"
                  style="padding: 12px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px;"
                >
                  清空
                </button>
                <button 
                  @click="callBaiLianAPI(chengguantongQuery)"
                  :disabled="chengguantongLoading || !chengguantongQuery"
                  class="btn-primary"
                  style="padding: 12px 30px; background-color: #2196f3; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold;"
                >
                  <span v-if="chengguantongLoading">处理中...</span>
                  <span v-else>发送</span>
                </button>
              </div>
              
              <div v-if="chengguantongError" class="error-message" style="padding: 10px; background-color: #ffebee; color: #c62828; border: 1px solid #ffcdd2; border-radius: 6px; margin-top: 10px;">
                {{ chengguantongError }}
              </div>
            </div>
            
            <!-- 响应结果 -->
            <div v-if="showResponse && chengguantongResponse" class="response-container" style="width: 100%; padding: 24px; border: 1px solid #e0e0e0; border-radius: 12px; background-color: #f9f9f9; box-shadow: 0 2px 8px rgba(0,0,0,0.05); box-sizing: border-box;">
              <div class="response-content" style="line-height: 1.7; color: #333; white-space: pre-wrap; word-wrap: break-word; overflow-wrap: break-word; font-size: 16px;">
                {{ chengguantongResponse }}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 地图服务模块 -->
      <div v-if="activeModule === 'map' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.map))" class="tab-content">
        <h2 class="section-title">地图服务</h2>
        <div class="map-section">
          <div v-if="mapLoading" class="loading">
            地图加载中...
          </div>
          <div v-else-if="mapError" class="error">
            {{ mapError }}
          </div>
          <div v-else id="map-container" style="width: 100%; height: 600px; border-radius: 8px;"></div>
          <div class="map-info" style="margin-top: 20px; padding: 20px; background-color: #f9f9f9; border-radius: 8px;">
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
        <h2 class="section-title">管理员管理</h2>
        <div class="admin-section">
          <div class="admin-tabs">
            <div class="admin-tab" :class="{ active: adminActiveTab === 'users' }" @click="adminActiveTab = 'users'">
              用户管理
            </div>
            <div class="admin-tab" :class="{ active: adminActiveTab === 'system' }" @click="adminActiveTab = 'system'">
              系统配置
            </div>
          </div>
          
          <!-- 用户管理子模块 -->
          <div v-if="adminActiveTab === 'users'" class="admin-subsection">
            <h3 class="subsection-title">用户列表</h3>
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
          
          <!-- 系统配置子模块 -->
          <div v-if="adminActiveTab === 'system'" class="admin-subsection">
            <h3 class="subsection-title">系统配置</h3>
            
            <!-- 配置标签页 -->
            <div class="config-tabs">
              <button class="config-tab" :class="{ active: systemConfigTab === 'data' }" @click="systemConfigTab = 'data'">数据管理</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'general' }" @click="systemConfigTab = 'general'">通用配置</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'security' }" @click="systemConfigTab = 'security'">安全配置</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'logs' }" @click="systemConfigTab = 'logs'">系统日志</button>
              <button class="config-tab" :class="{ active: systemConfigTab === 'cms' }" @click="systemConfigTab = 'cms'">内容管理</button>
            </div>
            
            <!-- 配置内容 -->
            <div class="config-content">
              <!-- 数据管理配置 -->
              <div v-if="systemConfigTab === 'data'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">数据库管理</h4>
                  <p class="panel-description">管理数据库中的数据表，可上传Excel文件和删除不需要的数据表</p>
                </div>
                <div class="panel-body">
                  <!-- Excel上传功能 -->
                  <div class="data-management" style="margin-bottom: 40px;">
                    <h5 class="management-title" style="margin-bottom: 20px;">Excel数据上传</h5>
                    <div class="upload-section">
                      <div class="file-selector">
                        <input type="file" accept=".xlsx" @change="handleFileSelect" :disabled="loading" />
                        <span class="file-name">{{ selectedFile ? selectedFile.name : '未选择任何文件' }}</span>
                      </div>
                      <button class="upload-btn" @click="uploadFile" :disabled="loading || !selectedFile" style="margin-top: 15px;">
                        {{ loading ? '上传中...' : '上传并导入数据库' }}
                      </button>
                      <div class="upload-status" style="margin-top: 15px;">
                        <span class="status-label">上传状态：</span>
                        <span class="status-value">{{ message || '等待上传' }}</span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 数据表管理 -->
                  <div class="table-management">
                    <h5 class="management-title" style="margin-bottom: 20px;">数据表管理</h5>
                    <button class="refresh-btn" @click="fetchTablesForManagement" :disabled="adminLoading">
                      {{ adminLoading ? '加载中...' : '刷新数据表' }}
                    </button>
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
                  <div class="table-visibility-config" style="margin-top: 30px;">
                    <h5 class="management-title" style="margin-bottom: 15px;">数据表可见性配置</h5>
                    <p class="config-description" style="margin-bottom: 15px; color: #666;">配置哪些数据表对前端用户可见，用户只能选择可见的数据表进行分析和考核。</p>
                    <button class="save-visibility-btn" @click="saveTableVisibility" :disabled="adminLoading" style="padding: 8px 16px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                      {{ adminLoading ? '保存中...' : '保存配置' }}
                    </button>
                  </div>
                </div>
              </div>
              
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
              
              <!-- CMS内容管理 -->
              <div v-if="systemConfigTab === 'cms'" class="config-panel">
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
                    <button class="add-btn" @click="addNewArticle">添加文章</button>
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
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id, 1)" :disabled="cmsArticlesPage === 1">首页</button>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id, cmsArticlesPage - 1)" :disabled="cmsArticlesPage === 1">上一页</button>
                          <template v-for="page in getPageNumbers()" :key="page">
                            <button v-if="page !== '...'" class="page-btn" :class="{ active: page === cmsArticlesPage }" @click="fetchCMSArticles(selectedCategory?.id, page)">
                              {{ page }}
                            </button>
                            <span v-else class="page-ellipsis">...</span>
                          </template>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id, cmsArticlesPage + 1)" :disabled="cmsArticlesPage === cmsArticlesPages">下一页</button>
                          <button class="page-btn" @click="fetchCMSArticles(selectedCategory?.id, cmsArticlesPages)" :disabled="cmsArticlesPage === cmsArticlesPages">末页</button>
                        </div>
                      </div>
                    </div>
                    <div v-else class="empty-state">
                      <p>暂无文章</p>
                    </div>
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
              <label for="new-username">用户名：</label>
              <input type="text" id="new-username" v-model="newUser.username" placeholder="请输入用户名" autocomplete="username" />
            </div>
            <div class="form-group">
              <label for="new-password">密码：</label>
              <input type="password" id="new-password" v-model="newUser.password" placeholder="请输入密码" autocomplete="new-password" />
            </div>
            <div class="form-group">
              <label for="new-role">角色：</label>
              <select id="new-role" v-model="newUser.role">
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
                <label for="perm-data-analysis">数据分析</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-spotcheck" v-model="editingPermissions.spotcheck" />
                <label for="perm-spotcheck">案件抽查</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-tools" v-model="editingPermissions.tools" />
                <label for="perm-tools">小工具</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-chengguantong" v-model="editingPermissions.chengguantong" />
                <label for="perm-chengguantong">城管通</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-map" v-model="editingPermissions.map" />
                <label for="perm-map">地图服务</label>
              </div>
              <div class="permission-item">
                <input type="checkbox" id="perm-huiwentai" v-model="editingPermissions.huiwentai" />
                <label for="perm-huiwentai">汇问台</label>
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
              <div v-if="fileUploadLoading" style="font-size: 12px; color: #666; margin-top: 5px;">上传中...</div>
              <div v-if="fileUploadError" style="font-size: 12px; color: #e74c3c; margin-top: 5px;">{{ fileUploadError }}</div>
              <div v-if="newArticle.file_path" style="font-size: 12px; color: #27ae60; margin-top: 5px;">已上传文件</div>
            </div>
            
            <div class="form-group">
              <label for="article-image">图片上传（插入到内容）：</label>
              <input type="file" id="article-image" accept=".jpg,.jpeg,.png,.gif,.webp" @change="uploadImage" :disabled="imageUploadLoading" />
              <div v-if="imageUploadLoading" style="font-size: 12px; color: #666; margin-top: 5px;">上传中...</div>
              <div v-if="imageUploadError" style="font-size: 12px; color: #e74c3c; margin-top: 5px;">{{ imageUploadError }}</div>
              <div style="font-size: 12px; color: #666; margin-top: 5px;">提示：上传后图片将自动插入到文章内容中</div>
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
              <div style="font-size: 12px; color: #666; margin-top: 5px;">提示：可以直接输入HTML标签来实现格式化效果，例如 &lt;b&gt;粗体&lt;/b&gt;、&lt;i&gt;斜体&lt;/i&gt; 等</div>
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
      <div class="modal-content" style="background-color: white; border-radius: 8px; padding: 30px; width: 90%; max-width: 1000px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 20px; color: #333;">查询结果</h2>
          <button @click="closeResultModal" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">&times;</button>
        </div>
        
        <!-- 生成的SQL语句 -->
        <div v-if="generatedSQL" class="sql-section" style="margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
          <h4 style="margin-top: 0; margin-bottom: 10px; color: #495057;">生成的SQL语句：</h4>
          <pre style="background-color: #e9ecef; padding: 10px; border-radius: 4px; overflow-x: auto; margin: 0;">{{ generatedSQL }}</pre>
        </div>
        
        <!-- 查询结果 -->
        <div v-if="queryResult">
          <div v-if="Array.isArray(queryResult) && queryResult.length > 0" class="result-table-container" style="overflow-x: auto; margin-bottom: 20px;">
            <table style="width: 100%; border-collapse: collapse; background-color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 11px; line-height: 1.3;">
              <thead style="background-color: #f8f9fa;">
                <tr>
                  <th v-for="(key, index) in Object.keys(queryResult[0])" :key="index" style="padding: 4px 6px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: bold; white-space: nowrap;">
                    {{ key }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in queryResult" :key="rowIndex" style="border-bottom: 1px solid #dee2e6;">
                  <td v-for="(value, colIndex) in Object.values(row)" :key="colIndex" style="padding: 4px 6px; word-break: break-all;">
                    {{ value }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="Array.isArray(queryResult) && queryResult.length === 0" class="empty-result" style="padding: 40px; text-align: center; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
            <p>查询结果为空</p>
          </div>
          <div v-else class="result-message" style="padding: 40px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
            <p>{{ queryResult }}</p>
          </div>
        </div>
        
        <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
          <button 
            @click="closeResultModal"
            style="padding: 10px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold;"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
    
    <!-- 页脚 -->
    <div v-if="isLoggedIn" class="footer">
      <p>© 2026 运城市智慧城市管理平台-一站通</p> 
      <p>联系电话：0359-2381078</p>
      <p>电子邮箱：bnc9595@163.com</p>
    </div>
    
    <!-- 文章详情弹窗 -->
    <div v-if="showArticleDetail" class="article-detail-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(135deg, rgba(0, 0, 0, 0.4) 0%, rgba(0, 0, 0, 0.6) 100%); display: flex; justify-content: center; align-items: center; z-index: 1000; animation: fadeIn 0.3s ease;">
      <div class="article-detail-content" style="background: white; border-radius: 12px; padding: 0; width: 90%; max-width: 900px; max-height: 85vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25); animation: slideUp 0.3s ease;">
        <!-- 文章头部 -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 30px 20px 30px; position: relative; border-radius: 12px 12px 0 0;">
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
            <div style="font-size: 18px; color: #666;">加载中...</div>
          </div>
          
          <div v-else-if="articleDetailError" style="text-align: center; padding: 40px; background-color: #fff3cd; color: #856404; border-radius: 8px; border: 1px solid #ffc107;">
            <div style="font-size: 16px; margin-bottom: 15px;">{{ articleDetailError }}</div>
            <button @click="closeArticleDetail" style="padding: 8px 20px; background-color: #ffc107; color: #333; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; transition: all 0.3s ease;" @mouseenter="$event.target.style.backgroundColor='#ffb300'" @mouseleave="$event.target.style.backgroundColor='#ffc107'">关闭</button>
          </div>
          
          <div v-else-if="currentArticle" style="color: #333;">
            <!-- 摘要部分 -->
            <div v-if="currentArticle.summary" style="margin-bottom: 25px; padding: 18px; background: linear-gradient(135deg, #f5f7ff 0%, #fffbf5 100%); border-left: 4px solid #667eea; border-radius: 6px;">
              <div style="font-weight: 600; color: #667eea; margin-bottom: 8px; font-size: 14px;">摘要</div>
              <div style="line-height: 1.6; color: #555; font-size: 15px;">{{ currentArticle.summary }}</div>
            </div>
            
            <!-- 正文内容 -->
            <div style="margin-bottom: 30px;">
              <div style="line-height: 1.8; color: #333; font-size: 16px;" v-html="currentArticle.content"></div>
            </div>
            
            <!-- 附件部分 -->
            <div v-if="currentArticle.file_path" style="margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 8px; border: 2px dashed #ddd;">
              <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-size: 24px;">📎</span>
                <h4 style="margin: 0; font-size: 16px; color: #333;">相关附件</h4>
              </div>
              <a :href="currentArticleFileUrl" :download="currentArticle.file_path.split('/').pop()" style="display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; transition: all 0.3s ease; cursor: pointer;" @mouseenter="$event.currentTarget.style.transform='translateY(-2px)'; $event.currentTarget.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)'" @mouseleave="$event.currentTarget.style.transform='translateY(0)'; $event.currentTarget.style.boxShadow='none'">
                <span>⬇️</span>
                <span>下载文件</span>
              </a>
            </div>
          </div>
        </div>
        
        <!-- 关闭按钮 (底部) -->
        <div style="padding: 15px 30px; background-color: #f8f9fa; border-top: 1px solid #eee; border-radius: 0 0 12px 12px; text-align: right;">
          <button @click="closeArticleDetail" style="padding: 8px 20px; background-color: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500; transition: all 0.3s ease;" @mouseenter="$event.target.style.backgroundColor='#7f8c8d'" @mouseleave="$event.target.style.backgroundColor='#95a5a6'">关闭</button>
        </div>
      </div>
    </div>
    
    <!-- 全部文章弹窗 -->
    <div v-if="showAllArticlesModal" class="all-articles-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 1000;">
      <div class="all-articles-content" style="background-color: white; border-radius: 8px; padding: 30px; width: 90%; max-width: 800px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 24px; color: #333; text-align: left;">{{ getCategoryName(allArticlesCategoryId) }} - 全部文章</h2>
          <button @click="closeAllArticlesModal" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">&times;</button>
        </div>
        <div v-if="allArticlesLoading" style="text-align: center; padding: 40px; color: #666;">
          <div>加载中...</div>
        </div>
        <div v-else-if="allArticlesList.length === 0" style="text-align: center; padding: 40px; color: #999;">
          <div>该栏目下暂无文章</div>
        </div>
        <div v-else>
          <div class="articles-list" style="list-style: none; padding: 0; margin: 0;">
            <div v-for="article in allArticlesList" :key="article.id" class="article-item" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding: 8px; border-radius: 4px; transition: all 0.3s ease;" @click="() => { fetchArticleDetail(article.id); closeAllArticlesModal(); }" @mouseenter="$event.currentTarget.style.backgroundColor='#f5f5f5'" @mouseleave="$event.currentTarget.style.backgroundColor='transparent'">
              <span style="flex: 1; font-size: 16px; color: #333; line-height: 1.4; text-align: left;">
                <span style="margin-right: 12px; color: #1890ff;">•</span>
                {{ article.title }}
              </span>
              <span style="font-size: 14px; color: #999; white-space: nowrap; margin-left: 15px;">
                [{{ formatDate(article.published_at || article.created_at) }}]
              </span>
            </div>
          </div>
          
          <!-- 分页控件 -->
          <div v-if="allArticlesTotal > 0" class="pagination" style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 4px; flex-wrap: wrap; gap: 10px;">
            <span class="pagination-info" style="font-size: 14px; color: #666;">共 {{ allArticlesTotal }} 条，第 {{ allArticlesPage }}/{{ allArticlesPages }} 页</span>
            <div class="pagination-buttons" style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, 1)" :disabled="allArticlesPage === 1" style="padding: 8px 14px; background: white; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">首页</button>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPage - 1)" :disabled="allArticlesPage === 1" style="padding: 8px 14px; background: white; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">上一页</button>
              <template v-for="page in getAllArticlesPageNumbers()" :key="page">
                <button v-if="page !== '...'" class="page-btn" :class="{ active: page === allArticlesPage }" @click="fetchAllArticles(allArticlesCategoryId, page)" :style="page === allArticlesPage ? 'background: #007bff; color: white; border-color: #007bff;' : ''" style="padding: 8px 14px; background: white; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">
                  {{ page }}
                </button>
                <span v-else class="page-ellipsis" style="padding: 0 8px; color: #666; font-size: 16px;">...</span>
              </template>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPage + 1)" :disabled="allArticlesPage === allArticlesPages" style="padding: 8px 14px; background: white; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">下一页</button>
              <button class="page-btn" @click="fetchAllArticles(allArticlesCategoryId, allArticlesPages)" :disabled="allArticlesPage === allArticlesPages" style="padding: 8px 14px; background: white; color: #333; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s ease;">末页</button>
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

/* 标题栏背景图 */
.header {
  background-size: 100% 100%;
  background-position: center;
  background-repeat: no-repeat;
  width: 1020px;
  height: 120px;
  margin: 0 auto;
  padding: 0 20px;
  position: relative;
  overflow: hidden;
}

.header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1;
}

.header h1 {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  color: white;
  font-size: 24px;
  margin: 0;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
}

.header .user-info {
  position: absolute;
  right: 20px;
  bottom: 15px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 15px;
}

.header .username {
  color: white;
  font-size: 14px;
  text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
}

.header .logout-btn {
  padding: 6px 12px;
  background-color: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background-color 0.3s ease;
}

.header .logout-btn:hover {
  background-color: #c0392b;
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
  background-color: #ecf0f1;
  overflow-y: auto;
  width: 100%;
  margin-top: 0;
  margin-bottom: 0;
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
  background-color: #34495e;
  color: #fff;
  margin-top: 0;
}

.tab {
  flex: 1;
  padding: 15px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tab:hover {
  background-color: #3a536b;
}

.tab.active {
  background-color: #27ae60;
  font-weight: bold;
}

.main-content {
  flex: 1;
  padding: 30px 20px;
  background-color: #ecf0f1;
  overflow-y: auto;
  width: 100%;
  margin-top: 0;
}
/* 覆盖原有的 #app 样式 */
#app {
  padding: 0; /* 或者只保留左右 */
  /* padding: 0 2rem; */
}

.tab-content {
  background-color: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  width: 100%;
  margin: 0 auto;
  max-width: 800px;
}

.section-title {
  font-size: 1.4em;
  color: #2c3e50;
  margin-bottom: 25px;
  padding-bottom: 10px;
  border-bottom: 2px solid #27ae60;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.file-selector {
  position: relative;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 15px;
  background-color: #f9f9f9;
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
  color: #666;
}

.upload-btn {
  padding: 15px;
  background-color: #27ae60;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1em;
  font-weight: bold;
  transition: background-color 0.3s ease;
}

.upload-btn:hover {
  background-color: #219a52;
}

.upload-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
}

.upload-status {
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #f9f9f9;
}

.status-label {
  font-weight: bold;
  color: #555;
}

.status-value {
  color: #333;
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
  color: #555;
}

.form-group select {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fff;
  font-size: 1em;
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
  color: #999;
  text-align: center;
  font-size: 1.1em;
}

.result-content {
  line-height: 1.6;
}

.result-title {
  font-size: 1.3em;
  color: #27ae60;
  margin-bottom: 15px;
}

.data-summary {
  font-size: 1.1em;
  margin-bottom: 20px;
  color: #34495e;
}

.result-details {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ddd;
}

.details-subtitle {
  font-size: 1.1em;
  color: #666;
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
}

.column-list li::before {
  content: '•';
  color: #27ae60;
  position: absolute;
  left: 0;
  font-weight: bold;
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
  font-size: 0.9em;
  background-color: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.sample-table th, .sample-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.sample-table th {
  background-color: #f2f2f2;
  font-weight: bold;
  color: #34495e;
}

.sample-table tr:hover {
  background-color: #f5f5f5;
}

.analysis-content {
  margin: 30px 0;
  padding: 20px;
  background-color: #f9f9f9;
  border-radius: 8px;
  border-left: 4px solid #3498db;
}

.analysis-text {
  line-height: 1.8;
  color: #333;
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
  background-color: #f9f9f9;
  border-radius: 8px;
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
  background-color: #f9f9f9;
  border-radius: 8px;
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
  background-color: #ffffff;
  border-radius: 8px;
  border: 1px solid #ddd;
  width: 100%;
}

.map-info h3 {
  color: #2c3e50;
  margin-bottom: 15px;
  font-size: 1.1em;
}

.map-info p {
  margin: 8px 0;
  color: #555;
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
  background-color: #f9f9f9;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin: 10px 0;
}

.chart-item h5 {
  font-size: 1.1em;
  color: #666;
  margin-bottom: 15px;
  text-align: center;
}

.chart {
  width: 100%;
  height: 400px;
}

.footer {
  background-color: #2c3e50;
  color: #fff;
  padding: 15px;
  text-align: center;
  font-size: 0.9em;
  margin-top: 0 !important; /* 清除与main-content之间的空隙 */
  margin-bottom: 0 !important;
}

/* 调试信息样式 */
.debug-info {
  background-color: #f0f0f0;
  padding: 10px;
  border: 1px solid #ddd;
  margin: 10px;
  border-radius: 4px;
  font-size: 0.8em;
  color: #333;
}

/* 登录弹窗样式 */
.login-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.login-form {
  background-color: #fff;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  width: 400px;
  max-width: 90%;
}

.login-form h2 {
  text-align: center;
  color: #27ae60;
  margin-bottom: 30px;
}

.login-form .form-group {
  margin-bottom: 20px;
}

.login-form label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  color: #555;
}

.login-form input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1em;
}

.login-error {
  color: #e74c3c;
  margin-bottom: 20px;
  padding: 10px;
  background-color: #f9f9f9;
  border-radius: 4px;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 15px;
  background-color: #27ae60;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.1em;
  font-weight: bold;
  transition: background-color 0.3s ease;
}

.login-btn:hover {
  background-color: #219a52;
}

.login-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
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
  border-bottom: 1px solid #ddd;
}

.admin-tab {
  padding: 10px 20px;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: all 0.3s ease;
}

.admin-tab:hover {
  background-color: #f9f9f9;
}

.admin-tab.active {
  border-bottom-color: #27ae60;
  background-color: #f0f8f0;
  font-weight: bold;
}

.admin-subsection {
  background-color: #f9f9f9;
  padding: 20px;
  border-radius: 8px;
}

.subsection-title {
  font-size: 1.2em;
  color: #2c3e50;
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
  background-color: #27ae60;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1em;
  transition: background-color 0.3s ease;
}

.add-user-btn:hover {
  background-color: #219a52;
}

.user-list {
  overflow-x: auto;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
  background-color: #fff;
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
}

.user-table th,
.user-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.user-table th {
  background-color: #f2f2f2;
  font-weight: bold;
  color: #333;
}

.user-table tr:hover {
  background-color: #f5f5f5;
}

.edit-user-btn,
.delete-user-btn {
  padding: 5px 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
  transition: background-color 0.3s ease;
  margin-right: 5px;
}

.edit-user-btn {
  background-color: #3498db;
  color: #fff;
}

.edit-user-btn:hover {
  background-color: #2980b9;
}

.delete-user-btn {
  background-color: #e74c3c;
  color: #fff;
}

.delete-user-btn:hover {
  background-color: #c0392b;
}

.delete-user-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
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
  background-color: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  width: 800px;
  max-width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  z-index: 2001;
}

.modal-content h3 {
  text-align: center;
  color: #27ae60;
  margin-bottom: 20px;
}

.modal-content .form-group {
  margin-bottom: 15px;
}

.modal-content label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #555;
}

.modal-content input,
.modal-content select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1em;
}

.admin-error {
  color: #e74c3c;
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f9f9f9;
  border-radius: 4px;
  text-align: center;
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
  transition: background-color 0.3s ease;
}

.cancel-btn {
  background-color: #95a5a6;
  color: #fff;
}

.cancel-btn:hover {
  background-color: #7f8c8d;
}

.save-btn {
  background-color: #27ae60;
  color: #fff;
}

.save-btn:hover {
  background-color: #219a52;
}

.save-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
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
  border-bottom: 1px solid #ddd;
}

.config-tab {
  padding: 10px 20px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-bottom: none;
  cursor: pointer;
  margin-right: 5px;
  border-radius: 5px 5px 0 0;
  transition: all 0.3s ease;
}

.config-tab:hover {
  background: #e8e8e8;
}

.config-tab.active {
  background: #fff;
  border-bottom: 1px solid #fff;
  font-weight: bold;
}

.config-panel {
  background: white;
  border: 1px solid #ddd;
  border-radius: 5px;
  box-shadow: 0 0 10px rgba(0,0,0,0.1);
  overflow: hidden;
}

.panel-header {
  background: #f8f9fa;
  padding: 15px 20px;
  border-bottom: 1px solid #ddd;
}

.panel-title {
  margin: 0 0 5px 0;
  color: #333;
  font-size: 16px;
}

.panel-description {
  margin: 0;
  color: #666;
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
  color: #333;
}

.config-form .form-group input,
.config-form .form-group select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.config-form .form-group input[type="checkbox"] {
  width: auto;
  margin-right: 10px;
}

.config-form .form-help {
  margin-left: 10px;
  color: #666;
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
  background: #f8f9fa;
  border-left: 4px solid #007bff;
  border-radius: 4px;
}

.table-management {
  margin-top: 20px;
}

.refresh-btn {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 20px;
  transition: background 0.3s ease;
}

.refresh-btn:hover {
  background: #0069d9;
}

.refresh-btn:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

.table-list {
  margin-top: 20px;
}

.table-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 0 10px rgba(0,0,0,0.1);
}

.table-table th,
.table-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.table-table th {
  background: #f2f2f2;
  font-weight: bold;
}

.table-table tr:hover {
  background: #f5f5f5;
}

.delete-table-btn {
  padding: 6px 12px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s ease;
}

.delete-table-btn:hover {
  background: #c82333;
}

.delete-table-btn:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

.empty-state {
  padding: 40px;
  text-align: center;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  color: #6c757d;
}

/* 系统日志样式 */
.logs-section {
  padding: 40px;
  text-align: center;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  color: #6c757d;
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

/* CMS首页栏目标题样式 */
.column-title {
  display: inline-block;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white !important;
  padding: 8px 16px !important;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  transition: all 0.3s ease;
}

.column-title:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

/* 栏目卡片样式优化 */
.cms-column {
  background: linear-gradient(to bottom, #ffffff 0%, #f8f9fa 100%) !important;
  border-left: 4px solid #667eea !important;
  transition: all 0.3s ease;
}

.cms-column:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15) !important;
  transform: translateY(-4px);
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

/* 分页控件样式 */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 4px;
  flex-wrap: wrap;
  gap: 10px;
}

.pagination-info {
  font-size: 14px;
  color: #666;
}

.pagination-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.page-btn {
  padding: 8px 14px;
  background: white;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.page-btn:disabled {
  background: #e9ecef;
  color: #adb5bd;
  cursor: not-allowed;
}

.page-btn.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.page-ellipsis {
  padding: 0 8px;
  color: #666;
  font-size: 16px;
}
</style>
