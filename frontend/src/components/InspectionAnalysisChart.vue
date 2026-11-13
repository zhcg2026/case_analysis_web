<template><div class="chart-wrap"><div ref="container" :style="{height:`${height}px`}" role="img" :aria-label="title"></div><el-button size="small" text @click="download">导出图片</el-button></div></template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import * as echarts from 'echarts'
const props=defineProps({option:Object,title:String,height:{type:Number,default:320}}),emit=defineEmits(['select']),container=ref(null)
let chart,observer
const render=()=>{if(chart&&props.option)chart.setOption(props.option,true)}
function download(){if(!chart)return;const a=document.createElement('a');a.download=`${props.title}.png`;a.href=chart.getDataURL({type:'png',pixelRatio:2,backgroundColor:'#fff'});a.click()}
onMounted(()=>{chart=echarts.init(container.value);chart.on('click',p=>emit('select',p));observer=new ResizeObserver(()=>chart?.resize());observer.observe(container.value);render()})
watch(()=>props.option,render,{deep:true})
onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose();chart=null})
</script>
<style scoped>.chart-wrap{text-align:right}.chart-wrap>div{text-align:left;width:100%}</style>
