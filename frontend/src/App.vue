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
const activeTab = ref('upload'); // upload, analyze, result

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
    const response = await fetch('http://localhost:5000/api/tables');
    const data = await response.json();
    if (data.tables) {
      tables.value = data.tables;
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

  const formData = new FormData();
  formData.append('file', selectedFile.value);

  try {
    loading.value = true;
    message.value = '上传中...';
    const response = await fetch('http://localhost:5000/api/upload', {
      method: 'POST',
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
        'Content-Type': 'application/json'
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
      // 切换到结果标签页
      console.log('切换到结果标签页');
      activeTab.value = 'result';
      console.log('当前标签页:', activeTab.value);
    }
  } catch (error) {
    message.value = 'Error analyzing data: ' + error.message;
    console.error('Error analyzing data:', error);
  } finally {
    loading.value = false;
    console.log('分析完成，加载状态已重置');
  }
}

// 切换标签页
function switchTab(tab) {
  activeTab.value = tab;
  // 只有切换到分析配置标签页时才重新获取表列表
  if (tab === 'analyze') {
    fetchTables();
  }
}
</script>

<template>
  <div class="system-container">
    <!-- 顶部标题栏 -->
    <div class="header">
      <h1>智慧城市管理平台 - 案例分析系统</h1>
    </div>
    
    <!-- 导航标签页 -->
    <div class="nav-tabs">
      <div class="tab" :class="{ active: activeTab === 'upload' }" @click="switchTab('upload')">
        数据上传
      </div>
      <div class="tab" :class="{ active: activeTab === 'analyze' }" @click="switchTab('analyze')">
        分析配置
      </div>
      <div class="tab" :class="{ active: activeTab === 'result' }" @click="switchTab('result')">
        结果展示
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 数据上传标签页 -->
      <div v-if="activeTab === 'upload'" class="tab-content">
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
      
      <!-- 分析配置标签页 -->
      <div v-if="activeTab === 'analyze'" class="tab-content">
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
      </div>
      
      <!-- 结果展示标签页 -->
      <div v-if="activeTab === 'result'" class="tab-content">
        <h2 class="section-title">分析结果</h2>
        <div class="result-section">
          <div v-if="analysisResult" class="result-content">
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
          <div v-else class="empty-result">
            <p>请先上传数据并进行分析</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 底部版权信息 -->
    <div class="footer">
      <p>© 2024 智慧城市管理平台</p>
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

/* 确保body没有顶部间隙 */
body {
  position: relative;
  top: 0;
  margin-top: 0 !important;
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
}
</style>
