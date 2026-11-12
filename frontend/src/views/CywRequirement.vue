<template>
  <div class="cyw-requirement-page">
    <div class="page-header">
      <div>
        <h2>管理要求</h2>
        <p class="page-sub">监控点位涉及区域内管理标准——到岗时间与管理标准，录入、抽查、台账请对照执行</p>
      </div>
      <span class="version-tag">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        2026-11-12 更新版
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
            <span class="dt-time">早 5:30 – 7:00</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 按点位类型展示管理要求 -->
    <div class="std-grid">
      <section v-for="section in standards" :key="section.title" class="std-card" :class="section.tone">
        <header class="std-head">
          <h3>{{ section.title }}</h3>
        </header>
        <ol class="point-list">
          <li v-for="(paragraphs, i) in section.points" :key="i">
            <p v-for="(text, j) in paragraphs" :key="j">{{ text }}</p>
          </li>
        </ol>
      </section>
    </div>

    <p class="page-foot">管理要求更新于 2026-11-12，标准修订后以最新文件为准。</p>
  </div>
</template>

<script setup>
// 按 2026-11-12 确认的条文逐项展示，保留两类道路要求的措辞差异。
const yielding = ['95％以上的机动车在人行横道前主动礼让行人。']
const pavement = [
  '①道路路面硬化、排水设施完善，无明显坑洼不平和路面积水（1平方米以上）；',
  '②人行步道连续通畅、铺装平整。'
]
const parking = '①机动车、非机动车有序规范停放（城市管理部门在人行道、非机动车道、机动车道旁统一划线，机动车、非机动车在线内停放，且不影响正常交通，或在未划线情况下，机动车、非机动车能做到整齐停放，且不影响正常交通，这两种情况不算作违章停车）。'
const standards = [
  {
    title: '主次干道', tone: 'tone-blue',
    points: [yielding, pavement, [parking, '②无明显违规占道经营现象，无明显流动摊贩无序摆放现象。']]
  },
  {
    title: '商业大街', tone: 'tone-green',
    points: [yielding, pavement, [parking, '②无明显违规占道经营现象，无明显流动摊贩无序。']]
  },
  {
    title: '夜市', tone: 'tone-orange',
    points: [
      ['环境干净整洁，无明显脏乱差，无明显乱扔垃圾、乱摆乱放现象；'],
      ['管理规范有序，无明显影响交通、群众生活问题。']
    ]
  }
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.std-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.std-card.tone-orange {
  grid-column: 1 / -1;
}

.point-list {
  margin: 0;
  padding-left: 22px;
}

.point-list li {
  padding: 5px 0 5px 4px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.point-list li::marker {
  color: var(--tone-strong);
  font-weight: 600;
}

.point-list p {
  margin: 0;
}

.page-foot {
  margin: var(--space-4) 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 600px) {
  .page-header {
    flex-direction: column;
  }

  .dt-head {
    align-items: flex-start;
  }

  .dt-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
