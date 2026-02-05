<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import * as echarts from 'echarts';

// 状态管理
const tables = ref([]);
const selectedTable = ref('');
const selectedAnalysisType = ref('');
const analysisResult = ref(null);
const loading = ref(false);
const message = ref('');
const selectedFile = ref(null);
const activeModule = ref('home'); // home, data, assessment, analysis, spotcheck, tools, chengguantong

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
const systemConfigTab = ref('data'); // data, general, security, logs
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

// 权限管理状态
const showEditPermissionsForm = ref(false);
const editingPermissionsUser = ref(null);
const editingPermissions = ref({
  data_management: false,
  assessment: false,
  data_analysis: false,
  spotcheck: false,
  tools: false,
  chengguantong: false
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

// 初始化时获取数据库表
onMounted(() => {
  fetchTables();
});

// 获取数据库表
async function fetchTables() {
  try {
    const token = localStorage.getItem('token');
    if (!token) return;
    
    const response = await fetch('http://localhost:5000/api/tables', {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (data.tables) {
      // 过滤掉系统表，只显示用户上传的表
      const systemTables = ['users', 'permissions'];
      tables.value = data.tables.filter(table => !systemTables.includes(table));
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

// 切换模块
function switchModule(module) {
  activeModule.value = module;
  // 只有切换到数据分析模块时才重新获取表列表
  if (module === 'analysis') {
    fetchTables();
  }
  // 切换到管理员模块时获取用户列表
  if (module === 'admin' && userInfo.value && userInfo.value.role === 'admin') {
    fetchUsers();
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

// 编辑用户权限
function editUserPermissions(user) {
  // 添加调试代码
  console.log('编辑用户权限，用户对象:', user);
  console.log('编辑用户权限，user.permissions:', user.permissions);
  console.log('编辑用户权限，user.permissions是否存在:', !!user.permissions);
  
  editingPermissionsUser.value = user;
  editingPermissions.value = {
    data_management: Boolean(user.permissions?.data_management) || false,
    assessment: Boolean(user.permissions?.assessment) || false,
    data_analysis: Boolean(user.permissions?.data_analysis) || false,
    spotcheck: Boolean(user.permissions?.spotcheck) || false,
    tools: Boolean(user.permissions?.tools) || false,
    chengguantong: Boolean(user.permissions?.chengguantong) || false
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
    }
  } catch (error) {
    adminError.value = '获取数据表失败，请稍后重试';
    console.error('Error fetching tables:', error);
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
    data_management: false,
    assessment: false,
    data_analysis: false,
    spotcheck: false,
    tools: false,
    chengguantong: false
  };
  adminError.value = '';
}
</script>

<template>
  <div class="system-container">
    <!-- 顶部标题栏 -->
    <div class="header">
      <h1>运城市智慧城市管理平台-城管通</h1>
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
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.data_management)" class="tab" :class="{ active: activeModule === 'data' }" @click="switchModule('data')">
        数据管理
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
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.tools)" class="tab" :class="{ active: activeModule === 'tools' }" @click="switchModule('tools')">
        小工具
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin' || (userInfo?.permissions && userInfo?.permissions.chengguantong)" class="tab" :class="{ active: activeModule === 'chengguantong' }" @click="switchModule('chengguantong')">
        城管通
      </div>
      <div v-if="!userInfo || userInfo?.role === 'admin'" class="tab" :class="{ active: activeModule === 'admin' }" @click="switchModule('admin')">
        管理员管理
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div v-if="isLoggedIn" class="main-content">
      <!-- 首页模块 -->
      <div v-if="activeModule === 'home'" class="tab-content">
        <h2 class="section-title">系统概览</h2>
        <div class="overview-section">
          <p>欢迎使用智慧城市管理平台 - 案例分析系统</p>
          <p>本系统提供以下功能：</p>
          <ul class="feature-list">
            <li>数据管理：上传和导入Excel数据</li>
            <li>考核计分：对案件处理情况进行考核评分</li>
            <li>数据分析：对案件数据进行多维度分析</li>
            <li>案件抽查：随机抽查案件处理情况</li>
          </ul>
        </div>
      </div>
      
      <!-- 数据管理模块 -->
      <div v-if="activeModule === 'data' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.data_management))" class="tab-content">
        <h2 class="section-title">Excel数据上传</h2>
        <div class="upload-section">
          <div class="file-selector">
            <input type="file" accept=".xlsx" @change="handleFileSelect" :disabled="loading" />
            <span class="file-name">{{ selectedFile ? selectedFile.name : '未选择任何文件' }}</span>
          </div>
          <button class="upload-btn" @click="uploadFile" :disabled="loading || !selectedFile">
            {{ loading ? '上传中...' : '上传并导入数据库' }}
          </button>
          <div class="upload-status">
            <span class="status-label">上传状态：</span>
            <span class="status-value">{{ message || '等待上传' }}</span>
          </div>
        </div>
      </div>
      
      <!-- 考核计分模块 -->
      <div v-if="activeModule === 'assessment' && (!userInfo || userInfo.role === 'admin' || (userInfo.permissions && userInfo.permissions.assessment))" class="tab-content">
        <h2 class="section-title">考核计分</h2>
        <div class="assessment-section">
          <p>考核计分功能开发中...</p>
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
          <p>案件抽查功能开发中...</p>
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
                        <button class="edit-permissions-btn" @click="editUserPermissions(user)">权限</button>
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
            </div>
            
            <!-- 配置内容 -->
            <div class="config-content">
              <!-- 数据管理配置 -->
              <div v-if="systemConfigTab === 'data'" class="config-panel">
                <div class="panel-header">
                  <h4 class="panel-title">数据库管理</h4>
                  <p class="panel-description">管理数据库中的数据表，可删除不需要的数据表</p>
                </div>
                <div class="panel-body">
                  <div class="table-management">
                    <button class="refresh-btn" @click="fetchTablesForManagement" :disabled="adminLoading">
                      {{ adminLoading ? '加载中...' : '刷新数据表' }}
                    </button>
                    <div v-if="tables.length > 0" class="table-list">
                      <table class="table-table">
                        <thead>
                          <tr>
                            <th>表名</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="table in tables" :key="table">
                            <td>{{ table }}</td>
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
                <input type="checkbox" id="perm-data-management" v-model="editingPermissions.data_management" />
                <label for="perm-data-management">数据管理</label>
              </div>
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
      </div>
    </div>
    
    <!-- 页脚 -->
    <div v-if="isLoggedIn" class="footer">
      <p>© 2024 运城市智慧城市管理平台-城管通</p>
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
  text-align: center;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
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
}

.modal-content {
  background-color: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  width: 400px;
  max-width: 90%;
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
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
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
