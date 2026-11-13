<template><div class="chart-wrap"><div ref="container" :style="{height:`${height}px`}" role="img" :aria-label="title"></div><el-button size="small" text @click="download">导出图片</el-button></div></template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount,nextTick} from 'vue'
import * as echarts from 'echarts'
import {useThemeStore} from '../stores/theme'
const props=defineProps({option:Object,title:String,height:{type:Number,default:320}}),emit=defineEmits(['select']),container=ref(null)
const themeStore=useThemeStore()
let chart,observer
function palette(){
 const style=getComputedStyle(container.value)
 const value=(name,fallback)=>style.getPropertyValue(name).trim()||fallback
 return {text:value('--text-primary','#303133'),secondary:value('--text-secondary','#606266'),border:value('--border-lighter','#ebeef5'),surface:value('--bg-primary','#ffffff'),muted:value('--bg-secondary','#f5f7fa')}
}
function render(){
 if(!chart||!props.option)return
 const colors=palette(),option=echarts.util.clone(props.option)
 option.textStyle={...option.textStyle,color:colors.text}
 option.legend={...option.legend,textStyle:{...option.legend?.textStyle,color:colors.secondary}}
 option.tooltip={...option.tooltip,backgroundColor:colors.surface,borderColor:colors.border,textStyle:{color:colors.text}}
 for(const key of ['xAxis','yAxis']){
  if(!option[key])continue
  const axes=Array.isArray(option[key])?option[key]:[option[key]]
  for(const axis of axes){
   axis.axisLabel={...axis.axisLabel,color:colors.secondary}
   axis.nameTextStyle={...axis.nameTextStyle,color:colors.secondary}
   axis.axisLine={...axis.axisLine,lineStyle:{...axis.axisLine?.lineStyle,color:colors.border}}
   axis.axisTick={...axis.axisTick,lineStyle:{...axis.axisTick?.lineStyle,color:colors.border}}
   axis.splitLine={...axis.splitLine,lineStyle:{...axis.splitLine?.lineStyle,color:colors.border}}
  }
 }
 for(const series of option.series||[])series.label={...series.label,color:colors.text}
 for(const zoom of option.dataZoom||[])Object.assign(zoom,{backgroundColor:colors.muted,borderColor:colors.border,textStyle:{color:colors.secondary}})
 chart.setOption(option,true)
}
function download(){if(!chart)return;const a=document.createElement('a');a.download=`${props.title}.png`;a.href=chart.getDataURL({type:'png',pixelRatio:2,backgroundColor:palette().surface});a.click()}
onMounted(()=>{chart=echarts.init(container.value);chart.on('click',p=>emit('select',p));observer=new ResizeObserver(()=>chart?.resize());observer.observe(container.value);render()})
watch(()=>props.option,render,{deep:true})
watch(()=>themeStore.theme,async()=>{await nextTick();render()},{flush:'post'})
onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose();chart=null})
</script>
<style scoped>.chart-wrap{text-align:right}.chart-wrap>div{text-align:left;width:100%}</style>
