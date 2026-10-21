<template>
  <div class="cyw-requirement-page">
    <div class="page-header">
      <div>
        <h2>管理要求</h2>
        <p class="page-sub">监控点位涉及区域内管理标准——到岗时间与管理标准，录入、抽查、台账请对照执行</p>
      </div>
      <span class="version-tag">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        2026-10-15 改定版
      </span>
    </div>

    <!-- 到岗时间 -->
    <section class="duty-time-card">
      <div class="dt-head">
        <span class="dt-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </span>
        <div class="dt-heading">
          <h3>到岗时间</h3>
          <p>各点位责任人按以下时段到岗值守，在岗抽查以到岗时间为核对依据</p>
        </div>
      </div>
      <div class="dt-grid">
        <div class="dt-block">
          <div class="dt-name">主次干道 · 商业大街</div>
          <div class="dt-row">
            <span class="dt-label">工作日</span>
            <span class="dt-time">早 7:00 – 8:30</span>
            <span class="dt-dot" />
            <span class="dt-time">晚 5:00 – 6:30</span>
          </div>
          <div class="dt-row">
            <span class="dt-label">非工作日</span>
            <span class="dt-time">8:30 – 10:00</span>
          </div>
        </div>
        <div class="dt-block">
          <div class="dt-name">夜市</div>
          <div class="dt-row">
            <span class="dt-label">每日</span>
            <span class="dt-time">早 6:00 – 7:30</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 管理标准 -->
    <div class="std-grid">
      <section class="std-card tone-blue">
        <header class="std-head">
          <span class="std-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="3"/><circle cx="18" cy="5" r="3"/><path d="M12 19h4.5a3.5 3.5 0 0 0 0-7h-9a3.5 3.5 0 0 1 0-7H12"/></svg>
          </span>
          <div class="std-heading">
            <h3>主次干道 · 商业大街</h3>
            <span class="std-scope">通用标准</span>
          </div>
        </header>
        <div class="aspect-list">
          <div v-for="a in generalAspects" :key="a.label" class="aspect-item">
            <span class="aspect-tag">{{ a.label }}</span>
            <p class="aspect-text">{{ a.text }}</p>
          </div>
        </div>
      </section>

      <section class="std-card tone-orange">
        <header class="std-head">
          <span class="std-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/></svg>
          </span>
          <div class="std-heading">
            <h3>夜市</h3>
            <span class="std-scope">专项标准</span>
          </div>
        </header>
        <ul class="point-list">
          <li v-for="(t, i) in nightPoints" :key="i">{{ t }}</li>
        </ul>
      </section>

      <section class="std-card tone-green">
        <header class="std-head">
          <span class="std-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 1.5-5h15L21 9"/><path d="M4 9v11a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9"/><path d="M2 7h20"/><path d="M9 21v-6h6v6"/></svg>
          </span>
          <div class="std-heading">
            <h3>商业大街（盬街）</h3>
            <span class="std-scope">专项标准</span>
          </div>
        </header>
        <ul class="point-list">
          <li v-for="(t, i) in guStreetPoints" :key="i">{{ t }}</li>
        </ul>
      </section>
    </div>

    <p class="page-foot">依据《监控点位涉及区域内管理标准（2026-10-15 改定版）》整理，标准修订后以最新文件为准。</p>
  </div>
</template>

<script setup>
// 内容逐字取自《监控点位涉及区域内管理标准（2026-10-15 改定版）》，仅做版式拆分，未改写措辞
const generalAspects = [
  { label: '环卫方面', text: '环境干净整洁，无脏乱差，无乱扔垃圾现象；路面、果皮箱周边垃圾及时清运，绿化带内及表面垃圾捡拾干净，无积存垃圾、纸屑、烟蒂、污物等现象。' },
  { label: '市容方面', text: '非机动车及共享单车有序规范停放，无违规占道经营现象，无流动摊贩无序摆放现象；无违法广告、小广告乱张贴现象。' },
  { label: '市政方面', text: '道路路面硬化、排水设施完善，无坑洼不平和路面积水(1平方米以上)；人行步道连续通畅、铺装平整。' },
  { label: '园林方面', text: '监控区域绿地内无缺苗断垄及枯枝死苗等现象。' }
]

const nightPoints = [
  '管理规范有序，非机动车有序规范停放，环境干净整洁，无脏乱差，无乱扔垃圾、乱摆乱放现象；',
  '无影响交通、群众生活问题。'
]

const guStreetPoints = [
  '环境干净整洁，无脏乱差，无乱扔垃圾现象；',
  '路面、果皮箱周边垃圾及时清运，绿化带内及表面垃圾捡拾干净，无积存垃圾、纸屑、烟蒂、污物等现象；',
  '道路路面硬化、排水设施完善，无坑洼不平和路面积水(1平方米以上)；',
  '人行步道连续通畅、铺装平整；',
  '无违规店外、占道经营现象，无流动摊贩；',
  '机动车、非机动车有序规范停放；',
  '机动车在人行横道前主动礼让行人；',
  '要及时劝阻不文明行为。'
]
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-sub {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.6;
  max-width: 720px;
}

.version-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding: 5px 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--primary-200);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

/* ========== 到岗时间 ========== */
.duty-time-card {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--primary-50), var(--bg-card) 60%);
  box-shadow: var(--shadow-sm);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.dt-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.dt-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--primary-500);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(64, 158, 255, 0.35);
}

.dt-heading h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.dt-heading p {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

.dt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-3);
}

.dt-block {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.dt-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.dt-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: 5px 0;
}

.dt-row + .dt-row {
  border-top: 1px dashed var(--border-lighter);
}

.dt-label {
  display: inline-block;
  min-width: 52px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--fill-light);
  color: var(--text-secondary);
  font-size: 12px;
  text-align: center;
}

.dt-time {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-500);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.2px;
}

.dt-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-placeholder);
}

/* ========== 管理标准卡片 ========== */
.std-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

@media (max-width: 1100px) {
  .std-grid {
    grid-template-columns: 1fr;
  }
}

.std-card {
  --tone: var(--primary-500);
  --tone-strong: var(--primary-600);
  --tone-bg: var(--primary-50);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  padding: var(--space-4) var(--space-4) var(--space-3);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.std-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.std-card.tone-orange {
  --tone: var(--warning);
  --tone-strong: var(--warning-dark);
  --tone-bg: var(--warning-light);
}

.std-card.tone-green {
  --tone: var(--success);
  --tone-strong: var(--success-dark);
  --tone-bg: var(--success-light);
}

.std-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-lighter);
  margin-bottom: var(--space-3);
}

.std-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: var(--tone-bg);
  color: var(--tone-strong);
  flex-shrink: 0;
}

.std-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
}

.std-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.std-scope {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--tone-bg);
  color: var(--tone-strong);
  font-size: 11px;
  font-weight: 500;
}

/* 四方面标准：左侧标签 + 右侧条文 */
.aspect-item {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.aspect-item + .aspect-item {
  border-top: 1px dashed var(--border-lighter);
}

.aspect-tag {
  height: fit-content;
  padding: 3px 0;
  border-radius: var(--radius-sm);
  background: var(--tone-bg);
  color: var(--tone-strong);
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}

.aspect-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  word-break: break-word;
}

/* 专项标准：菱形符号列表 */
.point-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.point-list li {
  position: relative;
  padding: 5px 0 5px 18px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  word-break: break-word;
}

.point-list li::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 15px;
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: var(--tone);
  transform: rotate(45deg);
}

.page-foot {
  margin: var(--space-4) 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
