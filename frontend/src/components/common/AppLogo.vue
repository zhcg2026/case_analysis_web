<template>
  <img
    v-if="config.logo"
    :src="config.logo"
    :width="size"
    :height="size"
    :alt="config.name"
    class="app-logo-img"
  />
  <svg
    v-else
    :width="size"
    :height="size"
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    :alt="config.name"
    class="app-logo-svg"
  >
    <!-- 圆角渐变底 -->
    <rect width="40" height="40" rx="9" :fill="`url(#${gid})`" />
    <!-- 城市楼宇群 -->
    <g fill="#ffffff">
      <rect x="8" y="21" width="6.5" height="13" rx="1" />
      <rect x="16" y="14" width="8" height="20" rx="1" />
      <rect x="26" y="23" width="6" height="11" rx="1" />
    </g>
    <!-- 对勾徽标（已办结/核验意象） -->
    <circle cx="28" cy="13" r="7" fill="#ffffff" />
    <path
      d="M25 13 L27.5 15.5 L31.5 10.5"
      :stroke="`url(#${gid})`"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="none"
    />
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#409eff" />
        <stop offset="100%" stop-color="#00c6fb" />
      </linearGradient>
    </defs>
  </svg>
</template>

<script setup>
import { useSystemConfig } from '../../composables/useSystemConfig'

const props = defineProps({
  size: { type: Number, default: 40 }
})

const { config } = useSystemConfig()

// 每个实例唯一渐变 id，避免同页多份 SVG 的 url(#id) 冲突
let _counter = 0
const gid = `appLogoGrad_${++_counter}_${Math.random().toString(36).slice(2, 7)}`
</script>

<style scoped>
.app-logo-img,
.app-logo-svg {
  display: block;
}
</style>
