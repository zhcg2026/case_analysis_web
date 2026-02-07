<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue';
import * as echarts from 'echarts';

// 状态管理
const tables = ref([]);
const selectedTable = ref('');
const selectedAnalysisType = ref('');
const analysisResult = ref(null);
const loading = ref(false);
const message = ref('');
const selectedFile = ref(null);
const activeModule = ref('home'); // home, data, assessment, analysis, spotcheck, tools, chengguantong, cms, map

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
const selectedCategory = ref(null);
const cmsLoading = ref(false);
const cmsError = ref('');
const showArticleDetail = ref(false);
const currentArticle = ref(null);
const articleDetailLoading = ref(false);
const articleDetailError = ref('');

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
  map: false
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
    
    const response = await fetch('http://localhost:5000/api/tables', {
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
    const response = await fetch('http://localhost:5000/api/upload', {
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
    message.value = '请选择表和分析类型';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    message.value = '请先登录';
    return;
  }

  try {
    loading.value = true;
    currentStep.value = 0;
    message.value = '分析中...';
    console.log('开始分析，表名:', selectedTable.value, '分析类型:', selectedAnalysisType.value);
    
    // 步骤1: 读取数据
    currentStep.value = 1;
    message.value = '读取数据...';
    
    // 步骤2: 处理时间数据
    currentStep.value = 2;
    message.value = '处理时间数据...';
    
    // 步骤3: 调用大模型分析
    currentStep.value = 3;
    message.value = '调用大模型分析...';
    
    const response = await fetch('http://localhost:5000/api/analyze', {
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
    message.value = '生成分析报告...';
    
    const data = await response.json();
    console.log('分析请求响应数据:', data);
    
    if (data.error) {
      message.value = 'Error: ' + data.error;
      console.error('分析错误:', data.error);
    } else {
      analysisResult.value = data;
          console.log('分析结果已保存:', analysisResult.value);
          message.value = '分析完成';
          // 步骤5: 分析完成
          currentStep.value = 4;
          console.log('分析完成，结果已显示在当前页面');
          console.log('当前模块:', activeModule.value);
    }
  } catch (error) {
    message.value = 'Error analyzing data: ' + error.message;
    console.error('Error analyzing data:', error);
  } finally {
    loading.value = false;
    console.log('分析完成，加载状态已重置');
  }
}

// 开始考核计算
async function startAssessment() {
  if (!selectedDepartment.value || !selectedAssessmentTable.value) {
    message.value = '请选择部门和数据表';
    return;
  }

  const token = localStorage.getItem('token');
  if (!token) {
    message.value = '请先登录';
    return;
  }

  try {
    loading.value = true;
    message.value = '计算中...';
    
    const response = await fetch('http://localhost:5000/api/assess', {
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
      message.value = 'Error: ' + data.error;
    } else {
      assessmentResult.value = data;
      message.value = '计算完成';
    }
  } catch (error) {
    message.value = 'Error calculating assessment: ' + error.message;
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
    
    const response = await fetch('http://localhost:5000/api/login', {
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
    
    const response = await fetch('http://localhost:5000/api/user', {
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
    
    const response = await fetch('http://localhost:5000/api/users', {
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
      response = await fetch(`http://localhost:5000/api/users/${editingUser.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(newUser.value)
      });
    } else {
      // 添加用户
      response = await fetch('http://localhost:5000/api/users', {
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
    
    const response = await fetch(`http://localhost:5000/api/users/${userId}`, {
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
    
    const response = await fetch('http://localhost:5000/api/spotcheck', {
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
    map: Boolean(user.permissions?.map) || false
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
    
    const response = await fetch(`http://localhost:5000/api/users/${editingPermissionsUser.value.id}/permissions`, {
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
    
    const response = await fetch('http://localhost:5000/api/tables', {
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
    
    const response = await fetch(`http://localhost:5000/api/tables/${tableName}`, {
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
    map: false
  };
  adminError.value = '';
}

// CMS相关方法

// 获取CMS栏目
async function fetchCMSCategories() {
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    
    const response = await fetch('http://localhost:5000/api/categories');
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
async function fetchCMSArticles(categoryId) {
  try {
    cmsLoading.value = true;
    cmsError.value = '';
    
    const response = await fetch(`http://localhost:5000/api/articles/category/${categoryId}?include_drafts=true`);
    const data = await response.json();
    
    if (data.articles) {
      cmsArticles.value = data.articles;
    }
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
    const response = await fetch('http://localhost:5000/api/articles?include_drafts=true');
    const data = await response.json();
    
    if (data.articles) {
      cmsArticles.value = data.articles;
    }
  } catch (error) {
    console.error('Error fetching all CMS articles:', error);
  }
}

// 切换CMS栏目
async function switchCMSCategory(category) {
  selectedCategory.value = category;
  await fetchCMSArticles(category.id);
}

// 获取栏目名称
function getCategoryName(categoryId) {
  // 确保类型匹配
  const idToFind = Number(categoryId);
  const category = cmsCategories.value.find(cat => Number(cat.id) === idToFind);
  return category ? category.name : '未知栏目';
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
      response = await fetch(`http://localhost:5000/api/categories/${editingCategory.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newCategory.value)
      });
    } else {
      // 添加栏目
      response = await fetch('http://localhost:5000/api/categories', {
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
    
    const response = await fetch(`http://localhost:5000/api/categories/${categoryId}`, {
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
      response = await fetch(`http://localhost:5000/api/articles/${editingArticle.value.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newArticle.value)
      });
    } else {
      // 添加文章
      response = await fetch('http://localhost:5000/api/articles', {
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
      await fetchCMSArticles(selectedCategory.value?.id || cmsCategories.value[0]?.id);
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
    
    const response = await fetch(`http://localhost:5000/api/articles/${articleId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    if (data.error) {
      cmsError.value = data.error;
    } else {
      // 重新获取文章列表
      await fetchCMSArticles(selectedCategory.value?.id || cmsCategories.value[0]?.id);
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
    const response = await fetch(`http://localhost:5000/api/articles/${article.id}`);
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

// 根据栏目ID获取文章
function getCategoryArticles(categoryId) {
  // 过滤出指定栏目的文章，按时间排序（最新的在前），只返回前5条
  return cmsArticles.value
    .filter(article => Number(article.category_id) === Number(categoryId))
    .sort((a, b) => {
      const dateA = new Date(a.published_at || a.created_at);
      const dateB = new Date(b.published_at || b.created_at);
      return dateB - dateA; // 降序排序
    })
    .slice(0, 5); // 只返回前5条
}

// 显示全部文章弹窗
function showAllArticles(categoryId) {
  // 过滤出该栏目的所有文章并排序
  allArticlesList.value = cmsArticles.value
    .filter(article => Number(article.category_id) === Number(categoryId))
    .sort((a, b) => {
      const dateA = new Date(a.published_at || a.created_at);
      const dateB = new Date(b.published_at || b.created_at);
      return dateB - dateA; // 降序排序
    });
  
  allArticlesCategoryId.value = categoryId;
  showAllArticlesModal.value = true;
}

// 关闭全部文章弹窗
function closeAllArticlesModal() {
  showAllArticlesModal.value = false;
  allArticlesCategoryId.value = null;
  allArticlesList.value = [];
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
    
    const response = await fetch(`http://localhost:5000/api/articles/${articleId}`);
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
    const response = await fetch('http://localhost:5000/api/upload/file', {
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
    const response = await fetch('http://localhost:5000/api/upload/image', {
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
</script>

<template>
  <div class="system-container">
    <!-- 顶部标题栏 -->
    <div class="header">
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
      

      
      <!-- 考核计分模块 -->
      <div v-if="activeModule === 'assessment' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.assessment))" class="tab-content">
        <h2 class="section-title">考核计分</h2>
        <div class="assessment-section" style="max-width: 800px; margin: 0 auto;">
          <div style="margin-bottom: 20px;">
            <div style="margin-bottom: 15px;">
              <label for="department-select" style="display: block; margin-bottom: 5px; font-weight: bold;">选择部门：</label>
              <select id="department-select" v-model="selectedDepartment" :disabled="loading" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                <option value="">-- 请选择部门 --</option>
                <option value="城市综合行政执法队">城市综合行政执法队</option>
                <option value="市容环卫中心">市容环卫中心</option>
                <option value="园林绿化服务中心（片区）">园林绿化服务中心（片区）</option>
                <option value="园林绿化服务中心（公园广场）">园林绿化服务中心（公园广场）</option>
              </select>
            </div>
            <div style="margin-bottom: 15px;">
              <label for="table-select-assessment" style="display: block; margin-bottom: 5px; font-weight: bold;">选择数据表：</label>
              <select id="table-select-assessment" v-model="selectedAssessmentTable" :disabled="loading" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                <option value="">-- 请选择 --</option>
                <option v-for="table in tables" :key="table" :value="table">
                  {{ table }}
                </option>
              </select>
            </div>
            <button class="start-btn" @click="startAssessment" :disabled="loading" style="padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">
              {{ loading ? '计算中...' : '开始计算' }}
            </button>
            <div v-if="message" class="message" style="margin-top: 10px; padding: 10px; background-color: #f0f0f0; border-radius: 4px;">{{ message }}</div>
          </div>
          
          <!-- 考核结果显示 -->
          <div v-if="assessmentResult" class="assessment-result" style="margin-top: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;">
            <h3 style="margin-top: 0; padding-bottom: 10px; border-bottom: 1px solid #ddd;">考核结果</h3>
            <div class="result-summary" style="margin-bottom: 20px;">
              <p style="margin: 5px 0;">总案件数：{{ assessmentResult.total_cases }}</p>
              <p style="margin: 5px 0;">平均得分：{{ assessmentResult.score }}分</p>
            </div>
            <div v-if="assessmentResult.team_results" class="team-ranking">
              <h4 style="margin-top: 20px; margin-bottom: 10px;">片区排名</h4>
              <table class="ranking-table" style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <thead>
                  <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">排名</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">片区名称</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">案件总数</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">按期结案数</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">超期结案数</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">延期次数</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">返工次数</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">考核得分</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="team in assessmentResult.team_results" :key="team.department" style="background-color: white;">
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.rank }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.department }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.total_cases }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.on_time_count }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.overdue_count }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.delay_count }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.rework_count }}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{ team.score }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div>
        </div>
      </div>
      
      <!-- 数据分析模块 -->
      <div v-if="activeModule === 'analysis' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.data_analysis))" class="tab-content">
        <h2 class="section-title">分析配置</h2>
        <div class="config-section">
          <div class="form-group">
            <label for="table-select">选择表：</label>
            <select id="table-select" v-model="selectedTable" :disabled="loading">
              <option value="">-- 请选择 --</option>
              <option v-for="table in tables" :key="table" :value="table">
                {{ table }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="analysis-select">分析类型：</label>
            <select id="analysis-select" v-model="selectedAnalysisType" :disabled="loading">
              <option value="">-- 请选择 --</option>
              <option v-for="type in analysisTypes" :key="type.value" :value="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>
          
          <button class="analyze-btn" @click="startAnalysis" :disabled="loading || !selectedTable || !selectedAnalysisType">
            {{ loading ? '分析中...' : '开始分析' }}
          </button>
          
          <!-- 分析进度显示 -->
          <div v-if="loading" class="analysis-progress">
            <div class="progress-step" v-for="(step, index) in analysisSteps" :key="index" :class="{ active: currentStep >= index }">
              <div class="step-indicator">{{ step.icon }}</div>
              <div class="step-text">{{ step.text }}</div>
            </div>
          </div>
        </div>
        
        <!-- 分析结果 -->
        <div v-if="analysisResult" class="result-section">
          <h3 class="result-title">{{ analysisResult.table_name }} - {{ getAnalysisTypeName(analysisResult.analysis_type) }}</h3>
          <p class="data-summary">{{ analysisResult.data_summary }}</p>
          <div class="result-details">
            <!-- 图表展示 -->
            <div v-if="analysisResult.chart_data" class="charts-section">
              <h4 class="details-subtitle">数据可视化：</h4>
              <div class="chart-container">
                <!-- 时间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'time_analysis'">
                  <div class="chart-item">
                    <h5>日案件量趋势</h5>
                    <div ref="dailyChart" class="chart"></div>
                  </div>
                  <div class="chart-item">
                    <h5>小时级高峰时段</h5>
                    <div ref="hourlyChart" class="chart"></div>
                  </div>
                </template>
                <!-- 空间分析图表 -->
                <template v-if="analysisResult.analysis_type === 'space_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.street">
                    <h5>各街道案件密度</h5>
                    <div ref="spaceChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.community">
                    <h5>各社区案件密度</h5>
                    <div ref="spaceChart2" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.area">
                    <h5>各片区案件密度</h5>
                    <div ref="spaceChart3" class="chart"></div>
                  </div>
                </template>
                <!-- 来源分析图表 -->
                <template v-if="analysisResult.analysis_type === 'source_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.source">
                    <h5>案件来源分布</h5>
                    <div ref="sourceChart" class="chart"></div>
                  </div>
                </template>
                <!-- 案件类型分析图表 -->
                <template v-if="analysisResult.analysis_type === 'type_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.type">
                    <h5>案件类型分布</h5>
                    <div ref="sourceChart" class="chart"></div>
                  </div>
                </template>
                <!-- 重复案件分析图表 -->
                <template v-if="analysisResult.analysis_type === 'duplicate_analysis'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_duplicates">
                    <h5>问题描述重复TOP10</h5>
                    <div ref="dailyChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_duplicates">
                    <h5>地址描述重复TOP10</h5>
                    <div ref="sourceChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.address_type_distribution">
                    <h5>地址描述类型占比</h5>
                    <div ref="spaceChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.combined_duplicates">
                    <h5>组合重复TOP10</h5>
                    <div ref="spaceChart2" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.violation_type_distribution">
                    <h5>重复案件违规类型占比</h5>
                    <div ref="spaceChart3" class="chart"></div>
                  </div>
                </template>
                
                <!-- 对比上月分析图表 -->
                <template v-if="analysisResult.analysis_type === 'monthly_comparison'">
                  <div class="chart-item" v-if="analysisResult.chart_data?.monthly_comparison">
                    <h5>上月vs本月案件量对比</h5>
                    <div ref="dailyChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.case_size_comparison">
                    <h5>案件大小类别变化</h5>
                    <div ref="sourceChart" class="chart"></div>
                  </div>
                  <div class="chart-item" v-if="analysisResult.chart_data?.problem_trend">
                    <h5>问题趋势变化</h5>
                    <div ref="spaceChart" class="chart"></div>
                  </div>
                </template>
              </div>
            </div>
            <!-- 分析结果 -->
            <div v-if="analysisResult.analysis" class="analysis-content">
              <h4 class="details-subtitle">智能分析结果：</h4>
              <div class="analysis-text" v-html="analysisResult.analysis.replace(/\n/g, '<br>')"></div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 案件抽查模块 -->
      <div v-if="activeModule === 'spotcheck' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.spotcheck))" class="tab-content">
        <h2 class="section-title">案件抽查</h2>
        <div class="spotcheck-section">
          <!-- 第一行：提示文字 -->
          <div class="tip-section">
            <p>该模块允许上传文件（docx或者xlsx），并发送给大模型进行分析，然后返回结果。</p>
          </div>
          
          <!-- 第二行：文件选择和按钮 -->
          <div class="upload-section">
            <div class="form-group">
              <input 
                type="file" 
                id="spotcheck-file-input"
                accept=".docx,.xlsx" 
                @change="handleSpotcheckFileSelect"
              >
              <div v-if="spotcheckFile" class="file-info">
                已选择：{{ spotcheckFile.name }}
              </div>
            </div>
            
            <div class="button-group">
              <button 
                @click="uploadAndAnalyzeSpotcheck"
                :disabled="!spotcheckFile || spotcheckLoading"
                class="btn-primary"
              >
                <span v-if="spotcheckLoading">分析中...</span>
                <span v-else>上传并分析</span>
              </button>
              <button 
                @click="clearSpotcheck"
                :disabled="spotcheckLoading"
                class="btn-secondary"
              >
                清除
              </button>
            </div>
            
            <div v-if="spotcheckMessage" class="message success">
              {{ spotcheckMessage }}
            </div>
            <div v-if="spotcheckError" class="message error">
              {{ spotcheckError }}
            </div>
          </div>
          
          <!-- 第三行：分析结果（去除评分结果） -->
          <div v-if="spotcheckResult" class="result-section">
            <div class="result-card">
              <!-- 文件内容显示 -->
              <div v-if="spotcheckResult.file_content" class="file-content">
                <h5>读取的文件内容：</h5>
                <div class="content-display">
                  <p v-for="(line, index) in spotcheckResult.file_content.split('\n')" :key="index" v-if="line && line.trim()">
                    {{ line }}
                  </p>
                </div>
              </div>
              
              <div v-if="spotcheckResult.analysis" class="analysis-content">
                <h5>分析内容：</h5>
                <div v-html="spotcheckResult.analysis"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 小工具模块 -->
      <div v-if="activeModule === 'tools' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.tools))" class="tab-content">
        <h2 class="section-title">小工具</h2>
        <div class="tools-section">
          <p>小工具功能开发中...</p>
        </div>
      </div>
      
      <!-- 城管通模块 -->
      <div v-if="activeModule === 'chengguantong' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.chengguantong))" class="tab-content">
        <h2 class="section-title">城管通</h2>
        <div class="chengguantong-section">
          <p>城管通功能开发中...</p>
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
    
    <!-- 页脚 -->
    <div v-if="isLoggedIn" class="footer">
      <p>© 2024 运城市智慧城市管理平台-一站通</p> 
      <p>联系电话：0359-2381078</p>
    </div>
    
    <!-- 文章详情弹窗 -->
    <div v-if="showArticleDetail" class="article-detail-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: center; z-index: 1000;">
      <div class="article-detail-content" style="background-color: white; border-radius: 8px; padding: 30px; width: 90%; max-width: 800px; max-height: 80vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 24px; color: #333; text-align: left;">{{ currentArticle?.title }}</h2>
          <button @click="closeArticleDetail" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #999; padding: 0; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;">&times;</button>
        </div>
        
        <div v-if="articleDetailLoading" style="text-align: center; padding: 40px;">
          <div>加载中...</div>
        </div>
        
        <div v-else-if="articleDetailError" style="text-align: center; padding: 40px; color: #e74c3c;">
          <div>{{ articleDetailError }}</div>
          <button @click="closeArticleDetail" style="margin-top: 20px; padding: 8px 16px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">关闭</button>
        </div>
        
        <div v-else-if="currentArticle" style="line-height: 1.6; color: #333;">
          <div style="display: flex; gap: 20px; margin-bottom: 20px; font-size: 14px; color: #666;">
            <span>栏目：{{ getCategoryName(currentArticle.category_id) }}</span>
            <span>发布时间：{{ currentArticle.published_at || currentArticle.created_at }}</span>
            <span>浏览量：{{ currentArticle.view_count }}</span>
          </div>
          
          <div v-if="currentArticle.summary" style="margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #3498db; border-radius: 0 4px 4px 0;">
            {{ currentArticle.summary }}
          </div>
          
          <div style="margin-bottom: 20px; min-height: 200px;">
            <div v-html="currentArticle.content"></div>
          </div>
          
          <div v-if="currentArticle.file_path" style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 4px;">
            <h4 style="margin: 0 0 10px 0; font-size: 16px; color: #333;">附件</h4>
            <a :href="`http://localhost:5000/${currentArticle.file_path}`" :download="currentArticle.file_path.split('/').pop()" style="display: inline-block; padding: 8px 16px; background-color: #3498db; color: white; text-decoration: none; border-radius: 4px; font-size: 14px;">
              下载文件
            </a>
          </div>
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
        <div v-if="allArticlesList.length === 0" style="text-align: center; padding: 40px; color: #999;">
          <div>该栏目下暂无文章</div>
        </div>
        <div v-else class="articles-list" style="list-style: none; padding: 0; margin: 0;">
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
  background-image: url('https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=blue%20tech%20background%20with%20digital%20earth%20and%20data%20network%20connections%2C%20modern%20smart%20city%20technology%20concept%2C%20abstract%20digital%20lines%20and%20points%2C%20dark%20blue%20gradient%20background%2C%20no%20text%2C%20clean%20design&image_size=landscape_16_9');
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
  align-items: flex-start;
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
</style>
