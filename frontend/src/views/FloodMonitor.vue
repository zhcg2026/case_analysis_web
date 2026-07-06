<template>
  <div class="flood-page">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="grid-lines"></div>
      <div class="glow-orb orb-1"></div>
      <div class="glow-orb orb-2"></div>
    </div>

    <!-- 顶部标题栏 -->
    <header class="flood-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>返回首页</span>
        </router-link>
      </div>
      <div class="header-center">
        <h1 class="flood-title">
          <svg class="title-icon" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2v6M12 16v6M4.93 4.93l4.24 4.24M14.83 14.83l4.24 4.24M2 12h6M16 12h6M4.93 19.07l4.24-4.24M14.83 9.17l4.24-4.24"/>
            <circle cx="12" cy="12" r="4"/>
          </svg>
          运城市智慧城市管理平台防汛指挥调度系统
        </h1>
      </div>
      <div class="header-right">
        <div class="time-display">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>{{ currentTime }}</span>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="flood-main">
      <!-- 左侧面板 -->
      <aside class="flood-panel left-panel">
        <!-- 预警控制 -->
        <div class="panel-section warning-section">
          <button v-if="!activeWarning" class="warning-start-btn" @click="openWarningStart">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            启动预警
          </button>
          <template v-else>
            <div class="warning-active-display" :class="getWarningLevelClass(activeWarning.level)">
              <span class="warning-pulse"></span>
              {{ getWarningLevelLabel(activeWarning.level) }}预警中
            </div>
            <button class="warning-end-btn-sm" @click="endWarning">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              结束
            </button>
          </template>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>
            </svg>
            <h3 class="panel-title">实时天气</h3>
          </div>
          <div class="weather-current" v-if="weather">
            <div class="weather-main">
              <span class="weather-icon">{{ getWeatherIcon(weather.text) }}</span>
              <div class="weather-temp">{{ weather.temperature }}°C</div>
            </div>
            <div class="weather-desc">{{ weather.text }}</div>
            <div class="weather-details">
              <div class="detail-item">
                <span class="detail-label">体感温度</span>
                <span class="detail-value">{{ weather.feelsLike }}°C</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">湿度</span>
                <span class="detail-value">{{ weather.humidity }}%</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">风向</span>
                <span class="detail-value">{{ weather.windDir }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">风力</span>
                <span class="detail-value">{{ weather.windScale }}级</span>
              </div>
            </div>
          </div>
          <div class="weather-loading" v-else>加载天气数据...</div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 3v18h18"/>
              <path d="m19 9-5 5-4-4-3 3"/>
            </svg>
            <h3 class="panel-title">24小时降雨预报</h3>
          </div>
          <div class="chart-wrapper" ref="hourlyChartRef"></div>
        </div>
      </aside>

      <!-- 中间地图区域 -->
      <div class="flood-center">
        <div class="map-container">
          <div id="flood-map" class="map-element"></div>
          <!-- 地图工具栏 -->
          <div class="map-toolbar">
            <button class="toolbar-btn" @click="zoomIn" title="放大">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button class="toolbar-btn" @click="zoomOut" title="缩小">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
            </button>
            <button class="toolbar-btn" :class="{ active: mapMode === 'add' }" @click="mapMode = 'add'" title="添加积水点">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>
          </div>
          <!-- 积水点统计 -->
          <div class="map-stats">
            <div class="stat-item">
              <span class="stat-num">{{ waterPoints.length }}</span>
              <span class="stat-text">积水点</span>
            </div>
            <div class="stat-item warning" v-if="severeCount > 0">
              <span class="stat-num">{{ severeCount }}</span>
              <span class="stat-text">严重</span>
            </div>
            <div class="stat-item danger" v-if="deepCount > 0">
              <span class="stat-num">{{ deepCount }}</span>
              <span class="stat-text">较深</span>
            </div>
          </div>
        </div>
        <!-- 滚动数据条 -->
        <div class="scroll-data">
          <div class="scroll-label">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
            <span>实时动态</span>
          </div>
          <div class="scroll-content">
            <div v-if="recentDispatchRecords.length" class="scroll-inner">
              <template v-for="(item, i) in recentDispatchRecords" :key="'a'+i">
                <div class="scroll-ticker">
                  <span class="ticker-time">{{ formatTime(item.eventTime) }}</span>
                  <span class="ticker-type">[{{ item.recordType }}]</span>
                  <span class="ticker-title">{{ item.title }}</span>
                </div>
              </template>
              <template v-for="(item, i) in recentDispatchRecords" :key="'b'+i">
                <div class="scroll-ticker">
                  <span class="ticker-time">{{ formatTime(item.eventTime) }}</span>
                  <span class="ticker-type">[{{ item.recordType }}]</span>
                  <span class="ticker-title">{{ item.title }}</span>
                </div>
              </template>
            </div>
            <div v-else class="scroll-empty">暂无调度动态</div>
          </div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <aside class="flood-panel right-panel">
        <!-- 带班领导 -->
        <div class="panel-section leader-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <h3 class="panel-title">{{ dutyLeader?.title || '带班领导' }}</h3>
            <button class="leader-edit-btn" @click="editLeader" title="编辑">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
          </div>
          <div class="leader-info" v-if="dutyLeader && dutyLeader.name">
            <div class="leader-name">{{ dutyLeader.name }}</div>
            <div class="leader-phone" v-if="dutyLeader.phone">{{ dutyLeader.phone }}</div>
          </div>
          <div class="leader-empty" v-else>点击编辑设置带班领导</div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <h3 class="panel-title">今日值班人员</h3>
          </div>
          <div class="duty-list" v-if="todayDuty.length">
            <div class="duty-card" v-for="d in todayDuty" :key="d.id">
              <div class="duty-shift-name">{{ d.shiftName }}</div>
              <div class="duty-persons">
                <div class="duty-person">
                  <span class="person-name">{{ d.person1 }}</span>
                  <span class="person-phone">{{ d.person1Phone }}</span>
                </div>
                <div class="duty-person" v-if="d.person2">
                  <span class="person-name">{{ d.person2 }}</span>
                  <span class="person-phone">{{ d.person2Phone }}</span>
                </div>
              </div>
            </div>
          </div>
          <!-- 增援人员 -->
          <div class="duty-list" v-if="addedDuty.length" style="margin-top:8px;">
            <div class="duty-card" v-for="d in addedDuty" :key="'added-'+d.id" style="border-left:3px solid #3b82f6;">
              <div class="duty-shift-name" style="color:#3b82f6;">增援</div>
              <div class="duty-persons">
                <div class="duty-person">
                  <span class="person-name">{{ d.personName }}</span>
                  <span class="person-phone">{{ d.personPhone }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="duty-empty" v-if="!todayDuty.length && !addedDuty.length">今日暂无排班</div>
        </div>

        <div class="panel-section">
          <div class="panel-header">
            <svg class="panel-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <h3 class="panel-title">最近调度记录</h3>
          </div>
          <div class="dispatch-list">
            <div class="dispatch-item" v-for="r in recentDispatchRecords" :key="r.id">
              <div class="dispatch-type-badge" :class="getTypeClass(r.recordType)">{{ r.recordType }}</div>
              <div class="dispatch-content">
                <div class="dispatch-title">{{ r.content }}</div>
                <div class="dispatch-meta">
                  <span>{{ formatTime(r.eventTime) }}</span>
                  <span v-if="r.location">{{ r.location }}</span>
                </div>
              </div>
            </div>
            <div class="dispatch-empty" v-if="!recentDispatchRecords.length">暂无调度记录</div>
          </div>
        </div>

        <!-- 功能入口 -->
        <div class="panel-section panel-actions">
          <button class="action-btn" @click="showDrawer('ledger')">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4H4a2 2 0 1 0 0 4h12a2 2 0 1 0 0-4Z"/><path d="M6 8v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>
            调度台账
          </button>
          <button class="action-btn" @click="showDrawer('shift')">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            值班排班
          </button>
          <button class="action-btn" @click="showDrawer('points')">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            积水点管理
          </button>
          <button class="action-btn" @click="showDrawer('supplies')">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            应急物资
          </button>
          <button class="action-btn" @click="showDrawer('plan')">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            应急预案
          </button>
          <button class="action-btn" @click="openReportSelect">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            生成报告
          </button>
        </div>
      </aside>
    </main>

    <!-- 侧边抽屉 - 应急预案 -->
    <transition name="drawer">
      <div class="drawer-overlay" v-if="activeDrawer === 'plan'" @click="closeDrawer">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-header">
            <h3>应急预案管理</h3>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <div class="drawer-toolbar">
              <label class="btn btn-primary upload-btn">
                上传预案
                <input type="file" accept=".pdf,.doc,.docx,.txt" @change="uploadEmergencyPlan" hidden/>
              </label>
            </div>
            <div class="plan-list-full">
              <div class="plan-item-full" v-for="f in emergencyPlanFiles" :key="f.filename">
                <div class="plan-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </div>
                <div class="plan-detail">
                  <a :href="f.url" target="_blank" class="plan-filename">{{ f.filename }}</a>
                  <span class="plan-meta">{{ formatFileSize(f.size) }}</span>
                </div>
                <button class="btn-sm danger" @click="deletePlan(f.filename)">删除</button>
              </div>
              <div class="empty-state" v-if="!emergencyPlanFiles.length">暂无预案文件，请上传</div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 侧边抽屉 - 调度台账 -->
    <transition name="drawer">
      <div class="drawer-overlay" v-if="activeDrawer === 'ledger'" @click="closeDrawer">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-header">
            <h3>调度台账</h3>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <div class="drawer-toolbar">
              <button class="btn btn-primary" @click="showLedgerForm = true" :disabled="!activeWarning" :title="!activeWarning ? '请先启动预警' : ''">新增记录</button>
              <span v-if="!activeWarning" class="toolbar-hint">需先启动预警才能新增调度记录</span>
            </div>
            <!-- 当前激活预警 -->
            <div v-if="activeWarning" class="warning-group-current" @click="selectWarning(activeWarning.id)">
              <div class="warning-group-header active">
                <span class="warning-group-level" :class="getWarningLevelClass(activeWarning.level)">
                  {{ getWarningLevelLabel(activeWarning.level) }}预警中
                </span>
                <span class="warning-group-time">{{ formatTime(activeWarning.startTime) }} 至今</span>
              </div>
            </div>
            <!-- 预警历史列表 -->
            <div class="warning-history-list" v-if="warningHistory.length">
              <div v-for="w in warningHistory" :key="w.id"
                class="warning-group-item"
                :class="{ expanded: selectedWarningId === w.id }"
                @click="selectWarning(w.id)">
                <div class="warning-group-header">
                  <span class="warning-group-level" :class="getWarningLevelClass(w.level)">
                    {{ getWarningLevelLabel(w.level) }}预警
                  </span>
                  <span class="warning-group-status" :class="w.status === 'active' ? 'active' : 'ended'">
                    {{ w.status === 'active' ? '进行中' : '已结束' }}
                  </span>
                  <span class="warning-group-count">{{ w.recordCount }}条记录</span>
                  <svg class="warning-group-arrow" :class="{ open: selectedWarningId === w.id }" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </div>
                <div class="warning-group-time">{{ formatWarningTime(w.startTime, w.endTime) }}</div>
                <!-- 展开的调度记录 -->
                <div v-if="selectedWarningId === w.id" class="warning-group-records" @click.stop>
                  <div class="ledger-item" v-for="r in warningRecords" :key="r.id">
                    <div class="ledger-header">
                      <span class="ledger-type" :class="getTypeClass(r.recordType)">{{ r.recordType }}</span>
                      <span class="ledger-time">{{ formatTime(r.eventTime) }}</span>
                    </div>
                    <div class="ledger-content">{{ r.content }}</div>
                    <div class="ledger-footer" v-if="r.location || r.operator">
                      <span v-if="r.location">{{ r.location }}</span>
                      <span v-if="r.operator">{{ r.operator }}</span>
                    </div>
                  </div>
                  <div class="empty-state" v-if="!warningRecords.length">该预警下暂无调度记录</div>
                </div>
              </div>
            </div>
            <div class="empty-state" v-if="!warningHistory.length && !activeWarning">暂无预警记录</div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 新增台账表单弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showLedgerForm" @click="showLedgerForm = false">
        <div class="modal-panel" @click.stop>
          <div class="modal-header">
            <h3>新增调度记录</h3>
            <button class="modal-close" @click="showLedgerForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>记录类型</label>
              <select v-model="ledgerForm.recordType">
                <option value="">请选择</option>
                <option value="车辆调度">车辆调度</option>
                <option value="人员调度">人员调度</option>
                <option value="交通管制">交通管制</option>
                <option value="市民来电">市民来电</option>
                <option value="巡检发现">巡检发现</option>
                <option value="其他">其他</option>
              </select>
            </div>
            <div class="form-group">
              <label>详细内容</label>
              <textarea v-model="ledgerForm.content" rows="3" placeholder="请输入调度记录的详细内容"></textarea>
            </div>
            <div class="form-group">
              <label>地点</label>
              <input type="text" v-model="ledgerForm.location" placeholder="地点"/>
            </div>
            <div class="form-group">
              <label>操作人</label>
              <input type="text" v-model="ledgerForm.operator" placeholder="操作人"/>
            </div>
            <div class="form-group">
              <label>上传图片</label>
              <input type="file" multiple accept="image/*" @change="handleLedgerImageUpload"/>
              <div class="image-preview" v-if="ledgerForm.images.length">
                <div class="preview-item" v-for="(img, i) in ledgerForm.images" :key="i">
                  <img :src="img"/>
                  <button class="remove-btn" @click="ledgerForm.images.splice(i, 1)">&times;</button>
                </div>
              </div>
            </div>
            <div class="weather-snapshot" v-if="weather">
              <span class="snapshot-label">当前天气:</span>
              <span>{{ weather.text }} {{ weather.temperature }}°C 湿度{{ weather.humidity }}%</span>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showLedgerForm = false">取消</button>
            <button class="btn btn-primary" @click="submitLedger" :disabled="submitting">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 侧边抽屉 - 值班排班 -->
    <transition name="drawer">
      <div class="drawer-overlay" v-if="activeDrawer === 'shift'" @click="closeDrawer">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-header">
            <h3>值班排班管理</h3>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <!-- Tab切换 -->
            <div style="display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid var(--border-color);">
              <button @click="shiftTab='schedule'" :style="{padding:'8px 16px',border:'none',background:'none',cursor:'pointer',borderBottom:shiftTab==='schedule'?'2px solid #3b82f6':'2px solid transparent',color:shiftTab==='schedule'?'#3b82f6':'var(--text-secondary)',fontWeight:shiftTab==='schedule'?'600':'400'}">排班表</button>
              <button @click="shiftTab='personnel';loadPersonnel()" :style="{padding:'8px 16px',border:'none',background:'none',cursor:'pointer',borderBottom:shiftTab==='personnel'?'2px solid #3b82f6':'2px solid transparent',color:shiftTab==='personnel'?'#3b82f6':'var(--text-secondary)',fontWeight:shiftTab==='personnel'?'600':'400'}">人员管理</button>
            </div>
            <!-- 排班表 -->
            <div v-if="shiftTab==='schedule'">
              <div class="drawer-toolbar">
                <button class="btn btn-primary" @click="showShiftForm = true">新增排班</button>
                <label class="btn btn-secondary upload-btn">
                  上传排班表
                  <input type="file" accept=".xlsx,.xls" @change="handleShiftUpload" hidden/>
                </label>
              </div>
              <div class="shift-list">
                <div class="shift-item" v-for="s in allShifts" :key="s.id">
                  <div class="shift-date">{{ formatDate(s.shiftDate) }}</div>
                  <div class="shift-name">{{ s.shiftName }}</div>
                  <div class="shift-persons">
                    <span>{{ s.person1 }}</span>
                    <span class="shift-divider">/</span>
                    <span>{{ s.person2 }}</span>
                  </div>
                </div>
                <div class="empty-state" v-if="!allShifts.length">暂无排班记录</div>
              </div>
            </div>
            <!-- 人员管理 -->
            <div v-if="shiftTab==='personnel'">
              <div class="drawer-toolbar">
                <button class="btn btn-primary" @click="showPersonnelForm=true;personnelForm={name:'',phone:'',groupType:'admin'}">新增人员</button>
              </div>
              <div class="shift-list">
                <div class="shift-item" v-for="p in personnelList" :key="p.id" style="display:flex;justify-content:space-between;align-items:center;">
                  <div>
                    <span style="font-weight:500;">{{ p.name }}</span>
                    <span style="color:var(--text-secondary);font-size:12px;margin-left:8px;">{{ p.phone || '未填' }}</span>
                    <span style="font-size:11px;padding:1px 6px;border-radius:4px;margin-left:6px;" :style="{background:p.groupType==='admin'?'#dbeafe':p.groupType==='group_a'?'#dcfce7':p.groupType==='group_b'?'#fef3c7':'#f3e8ff',color:p.groupType==='admin'?'#1d4ed8':p.groupType==='group_a'?'#166534':p.groupType==='group_b'?'#92400e':'#7c3aed'}">{{ {admin:'行政',group_a:'A组',group_b:'B组',night:'夜班'}[p.groupType]||p.groupType }}</span>
                  </div>
                  <div style="display:flex;gap:4px;">
                    <button class="btn btn-sm btn-secondary" @click="editPersonnel(p)" style="font-size:11px;padding:2px 8px;">编辑</button>
                    <button class="btn btn-sm btn-secondary" @click="deletePersonnel(p)" style="font-size:11px;padding:2px 8px;color:#ef4444;">删除</button>
                  </div>
                </div>
                <div class="empty-state" v-if="!personnelList.length">暂无人员</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 新增排班表单 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showShiftForm" @click="showShiftForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>新增排班</h3>
            <button class="modal-close" @click="showShiftForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-row">
              <div class="form-group">
                <label>值班日期</label>
                <input type="date" v-model="shiftForm.shiftDate"/>
              </div>
              <div class="form-group">
                <label>班次</label>
                <select v-model="shiftForm.shiftName">
                  <option value="白班">白班</option>
                  <option value="夜班">夜班</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>值守人员1</label>
                <input type="text" v-model="shiftForm.person1" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话1</label>
                <input type="text" v-model="shiftForm.person1Phone" placeholder="电话"/>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>值守人员2</label>
                <input type="text" v-model="shiftForm.person2" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话2</label>
                <input type="text" v-model="shiftForm.person2Phone" placeholder="电话"/>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showShiftForm = false">取消</button>
            <button class="btn btn-primary" @click="submitShift" :disabled="submitting">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 人员管理表单 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showPersonnelForm" @click="showPersonnelForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>{{ personnelForm.id ? '编辑人员' : '新增人员' }}</h3>
            <button class="modal-close" @click="showPersonnelForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>姓名</label>
              <input type="text" v-model="personnelForm.name" placeholder="姓名"/>
            </div>
            <div class="form-group">
              <label>电话</label>
              <input type="text" v-model="personnelForm.phone" placeholder="电话"/>
            </div>
            <div class="form-group">
              <label>分组</label>
              <select v-model="personnelForm.groupType">
                <option value="admin">行政</option>
                <option value="group_a">A组</option>
                <option value="group_b">B组</option>
                <option value="night">夜班</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showPersonnelForm = false">取消</button>
            <button class="btn btn-primary" @click="submitPersonnel" :disabled="submitting">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 侧边抽屉 - 积水点管理 -->
    <transition name="drawer">
      <div class="drawer-overlay" v-if="activeDrawer === 'points'" @click="closeDrawer">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-header">
            <h3>积水点管理</h3>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <div class="point-list">
              <div class="point-item point-item-compact" v-for="p in waterPoints" :key="p.id" @click="focusPoint(p)">
                <div class="point-header">
                  <span class="point-name">{{ p.name }}</span>
                  <span v-if="p.roadType" class="point-road-type">{{ p.roadType }}</span>
                  <span class="point-level" :class="'level-' + p.waterLevel">{{ getLevelLabel(p.waterLevel) }}</span>
                </div>
                <div class="point-actions">
                  <button class="btn-sm" @click.stop="editPoint(p)">编辑</button>
                  <button class="btn-sm" @click.stop="editWaterLevel(p)">水位</button>
                  <button class="btn-sm danger" @click.stop="deletePoint(p.id)">删除</button>
                </div>
              </div>
              <div class="empty-state" v-if="!waterPoints.length">暂无积水点，可在地图上点击添加</div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 侧边抽屉 - 应急物资管理 -->
    <transition name="drawer">
      <div class="drawer-overlay" v-if="activeDrawer === 'supplies'" @click="closeDrawer">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-header">
            <h3>应急物资管理</h3>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <div class="drawer-toolbar">
              <button class="btn btn-primary" @click="startAddSupply">新增物资点</button>
            </div>
            <div class="supply-list">
              <div class="supply-item" v-for="s in emergencySupplies" :key="s.id">
                <div class="supply-header">
                  <span class="supply-name">{{ s.name }}</span>
                </div>
                <div class="supply-info">
                  <span>联系人: {{ s.contactPerson || '-' }}</span>
                  <span>{{ s.contactPhone || '-' }}</span>
                </div>
                <div class="supply-items" v-if="s.suppliesList && s.suppliesList.length">
                  <span class="supply-tag" v-for="(item, i) in s.suppliesList" :key="i">{{ item }}</span>
                </div>
                <div class="point-actions">
                  <button class="btn-sm" @click="editSupply(s)">编辑</button>
                  <button class="btn-sm danger" @click="deleteSupply(s.id)">删除</button>
                </div>
              </div>
              <div class="empty-state" v-if="!emergencySupplies.length">暂无物资点，可在地图上点击添加</div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 新增/编辑物资点弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showSupplyForm" @click="showSupplyForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>{{ editingSupply ? '编辑物资点' : '新增物资点' }}</h3>
            <button class="modal-close" @click="showSupplyForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>物资点名称</label>
              <input type="text" v-model="supplyForm.name" placeholder="例如：市政仓库"/>
            </div>
            <div class="form-group">
              <label>物资清单（每行一项）</label>
              <textarea v-model="supplyForm.suppliesText" rows="4" placeholder="抽水泵&#10;沙袋&#10;救生衣&#10;手电筒"></textarea>
            </div>
            <div class="form-group">
              <label>联系人</label>
              <input type="text" v-model="supplyForm.contactPerson" placeholder="姓名"/>
            </div>
            <div class="form-group">
              <label>联系电话</label>
              <input type="text" v-model="supplyForm.contactPhone" placeholder="电话"/>
            </div>
            <div class="form-group">
              <label>备注</label>
              <textarea v-model="supplyForm.remark" rows="2" placeholder="备注信息"></textarea>
            </div>
            <div class="form-row" v-if="!editingSupply">
              <div class="form-group">
                <label>经度</label>
                <input type="text" v-model="supplyForm.longitude" readonly placeholder="点击地图选择"/>
              </div>
              <div class="form-group">
                <label>纬度</label>
                <input type="text" v-model="supplyForm.latitude" readonly placeholder="点击地图选择"/>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showSupplyForm = false">取消</button>
            <button class="btn btn-primary" @click="submitSupply">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 选择预警生成报告弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showReportSelect" @click="showReportSelect = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>选择预警生成报告</h3>
            <button class="modal-close" @click="showReportSelect = false">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="activeWarning" class="report-select-item active" @click="generateReport(activeWarning.id)">
              <span class="report-select-level" :class="getWarningLevelClass(activeWarning.level)">
                {{ getWarningLevelLabel(activeWarning.level) }}预警
              </span>
              <span class="report-select-status active">进行中</span>
              <span class="report-select-time">{{ formatTime(activeWarning.startTime) }} 至今</span>
            </div>
            <div v-for="w in warningHistory" :key="w.id" class="report-select-item" @click="generateReport(w.id)">
              <span class="report-select-level" :class="getWarningLevelClass(w.level)">
                {{ getWarningLevelLabel(w.level) }}预警
              </span>
              <span class="report-select-status ended">已结束</span>
              <span class="report-select-time">{{ formatWarningTime(w.startTime, w.endTime) }}</span>
            </div>
            <div class="empty-state" v-if="!warningHistory.length && !activeWarning">暂无预警记录</div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 启动预警弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showWarningStartForm" @click="showWarningStartForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>启动预警</h3>
            <button class="modal-close" @click="showWarningStartForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>预警等级</label>
              <div class="warning-level-select">
                <button v-for="lv in ['blue','yellow','orange','red']" :key="lv"
                  class="warning-level-option" :class="'level-' + lv + (warningStartForm.level === lv ? ' selected' : '')"
                  @click="warningStartForm.level = lv">
                  {{ {blue:'蓝',yellow:'黄',orange:'橙',red:'红'}[lv] }}预警
                </button>
              </div>
            </div>
            <div class="form-group">
              <label>带班领导职务</label>
              <input type="text" v-model="warningStartForm.leaderTitle" placeholder="如：带班领导、副局长、局长"/>
            </div>
            <div class="form-group">
              <label>带班领导姓名</label>
              <input type="text" v-model="warningStartForm.leaderName" placeholder="领导姓名"/>
            </div>
            <div class="form-group">
              <label>联系电话</label>
              <input type="text" v-model="warningStartForm.leaderPhone" placeholder="电话"/>
            </div>
            <!-- 推荐增援 -->
            <div class="form-group" v-if="staffingRecommend">
              <label style="display:flex;align-items:center;gap:6px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>
                </svg>
                推荐增援
              </label>
              <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:12px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                  <span style="font-weight:600;font-size:15px;">{{ staffingRecommend.personName }}</span>
                  <span style="color:var(--text-secondary);font-size:13px;">{{ staffingRecommend.personPhone }}</span>
                </div>
                <div style="color:var(--text-secondary);font-size:12px;margin-bottom:8px;">{{ staffingRecommend.reason }}</div>
                <div style="display:flex;gap:8px;">
                  <button class="btn btn-sm btn-primary" @click="confirmStaffing" style="font-size:12px;padding:4px 12px;">确认到岗</button>
                  <button class="btn btn-sm btn-secondary" @click="refreshStaffingRecommend" style="font-size:12px;padding:4px 12px;">换一个人</button>
                </div>
              </div>
            </div>
            <div class="form-group" v-else-if="staffingLoading">
              <div style="color:var(--text-secondary);font-size:13px;">正在计算推荐增援...</div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showWarningStartForm = false">取消</button>
            <button class="btn btn-primary" @click="confirmStartWarning">确认启动</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 编辑带班领导弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showLeaderEdit" @click="showLeaderEdit = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>设置带班领导</h3>
            <button class="modal-close" @click="showLeaderEdit = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>职务名称</label>
              <input type="text" v-model="leaderForm.title" placeholder="如：带班领导、副局长、局长"/>
            </div>
            <div class="form-group">
              <label>姓名</label>
              <input type="text" v-model="leaderForm.name" placeholder="领导姓名"/>
            </div>
            <div class="form-group">
              <label>联系电话</label>
              <input type="text" v-model="leaderForm.phone" placeholder="电话"/>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showLeaderEdit = false">取消</button>
            <button class="btn btn-primary" @click="saveLeader">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 更新水位弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showWaterLevelForm" @click="showWaterLevelForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>更新水位 - {{ editingPoint?.name }}</h3>
            <button class="modal-close" @click="showWaterLevelForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>水位深度 (cm)</label>
              <input type="number" v-model="waterLevelForm.depth" min="0" step="1"/>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showWaterLevelForm = false">取消</button>
            <button class="btn btn-primary" @click="submitWaterLevel">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 编辑积水点弹窗 -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showPointEditForm" @click="showPointEditForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>编辑积水点</h3>
            <button class="modal-close" @click="showPointEditForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>道路名称</label>
              <input type="text" v-model="pointEditForm.name" placeholder="道路名称"/>
            </div>
            <div class="form-group">
              <label>道路类型</label>
              <select v-model="pointEditForm.roadType">
                <option value="">请选择</option>
                <option value="桥涵">桥涵</option>
                <option value="路口路段">路口路段</option>
                <option value="城中村">城中村</option>
              </select>
            </div>
            <div class="form-group">
              <label>管理单位</label>
              <input type="text" v-model="pointEditForm.managementUnit" placeholder="管理单位"/>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>积水点责任人</label>
                <input type="text" v-model="pointEditForm.responsiblePerson" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话</label>
                <input type="text" v-model="pointEditForm.responsiblePhone" placeholder="电话"/>
              </div>
            </div>
            <div class="form-group">
              <label>值守人员</label>
              <div class="duty-persons-list">
                <div v-for="(p, i) in pointEditForm.dutyPersons" :key="i" class="duty-person-row">
                  <input type="text" v-model="p.name" placeholder="姓名" class="duty-input"/>
                  <input type="text" v-model="p.phone" placeholder="电话" class="duty-input"/>
                  <button class="duty-remove-btn" @click="pointEditForm.dutyPersons.splice(i, 1)">&times;</button>
                </div>
              </div>
              <button type="button" class="duty-add-btn" @click="pointEditForm.dutyPersons.push({name:'', phone:''})">+ 添加人员</button>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>交警责任人</label>
                <input type="text" v-model="pointEditForm.trafficPolice" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话</label>
                <input type="text" v-model="pointEditForm.trafficPolicePhone" placeholder="电话"/>
              </div>
            </div>
            <div class="form-group">
              <label>监控点位（每行一个，格式：类型 编号，如：平台 CAM001）</label>
              <textarea v-model="pointEditForm.monitoringPointsText" rows="3" placeholder="平台 CAM001&#10;雪亮 CAM002"></textarea>
            </div>
            <div class="form-group">
              <label>备注</label>
              <input type="text" v-model="pointEditForm.remarks" placeholder="备注信息"/>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showPointEditForm = false">取消</button>
            <button class="btn btn-primary" @click="submitPointEdit">保存</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 新增积水点弹窗（地图点击后弹出） -->
    <transition name="modal">
      <div class="modal-overlay" v-if="showPointForm" @click="showPointForm = false">
        <div class="modal-panel small" @click.stop>
          <div class="modal-header">
            <h3>新增积水点</h3>
            <button class="modal-close" @click="showPointForm = false">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>道路名称</label>
              <input type="text" v-model="pointForm.name" placeholder="例如：解放路与人民路交叉口"/>
            </div>
            <div class="form-group">
              <label>道路类型</label>
              <select v-model="pointForm.roadType">
                <option value="">请选择</option>
                <option value="桥涵">桥涵</option>
                <option value="路口路段">路口路段</option>
                <option value="城中村">城中村</option>
              </select>
            </div>
            <div class="form-group">
              <label>管理单位</label>
              <input type="text" v-model="pointForm.managementUnit" placeholder="例如：市城市管理局"/>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>积水点责任人</label>
                <input type="text" v-model="pointForm.responsiblePerson" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话</label>
                <input type="text" v-model="pointForm.responsiblePhone" placeholder="电话"/>
              </div>
            </div>
            <div class="form-group">
              <label>值守人员</label>
              <div class="duty-persons-list">
                <div v-for="(p, i) in pointForm.dutyPersons" :key="i" class="duty-person-row">
                  <input type="text" v-model="p.name" placeholder="姓名" class="duty-input"/>
                  <input type="text" v-model="p.phone" placeholder="电话" class="duty-input"/>
                  <button class="duty-remove-btn" @click="pointForm.dutyPersons.splice(i, 1)">&times;</button>
                </div>
              </div>
              <button type="button" class="duty-add-btn" @click="pointForm.dutyPersons.push({name:'', phone:''})">+ 添加人员</button>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>交警责任人</label>
                <input type="text" v-model="pointForm.trafficPolice" placeholder="姓名"/>
              </div>
              <div class="form-group">
                <label>电话</label>
                <input type="text" v-model="pointForm.trafficPolicePhone" placeholder="电话"/>
              </div>
            </div>
            <div class="form-group">
              <label>监控点位（每行一个，格式：类型 编号，如：平台 CAM001）</label>
              <textarea v-model="pointForm.monitoringPointsText" rows="3" placeholder="平台 CAM001&#10;雪亮 CAM002&#10;高空 CAM003"></textarea>
            </div>
            <div class="form-group">
              <label>备注</label>
              <input type="text" v-model="pointForm.remarks" placeholder="备注信息"/>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>经度</label>
                <input type="text" v-model="pointForm.longitude" readonly/>
              </div>
              <div class="form-group">
                <label>纬度</label>
                <input type="text" v-model="pointForm.latitude" readonly/>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="showPointForm = false">取消</button>
            <button class="btn btn-primary" @click="submitPoint" :disabled="submitting">保存</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

// ======== 状态 ========
const currentTime = ref('')
const weather = ref(null)
const hourlyForecast = ref([])
const activeRainEvent = ref(null)
const recentRainEvents = ref([])
const waterPoints = ref([])
const todayDuty = ref([])
const allShifts = ref([])
const dutyLeader = ref(null)
const showLeaderEdit = ref(false)
const leaderForm = ref({ title: '带班领导', name: '', phone: '' })
const dispatchRecords = ref([])
const recentDispatchRecords = ref([])
const warningHistory = ref([])
const selectedWarningId = ref(null)
const warningRecords = ref([])
const emergencyPlanFiles = ref([])
const emergencySupplies = ref([])
const activeWarning = ref(null)
const showWarningStartForm = ref(false)
const warningStartForm = ref({ level: 'blue', leaderTitle: '带班领导', leaderName: '', leaderPhone: '' })
const showReportSelect = ref(false)
const activeDrawer = ref(null)
const mapMode = ref('view')
const submitting = ref(false)

// 表单状态
const showLedgerForm = ref(false)
const showShiftForm = ref(false)
const showPointForm = ref(false)
const showPointEditForm = ref(false)
const showWaterLevelForm = ref(false)
const showSupplyForm = ref(false)
const editingPoint = ref(null)
const editingSupply = ref(null)

const ledgerForm = ref({ recordType: '', content: '', location: '', operator: '', images: [], warningId: null })
const shiftForm = ref({ shiftDate: '', shiftName: '白班', person1: '', person1Phone: '', person2: '', person2Phone: '' })
const pointForm = ref({ name: '', roadType: '', responsiblePerson: '', responsiblePhone: '', dutyPersons: [], dutyPersonsText: '', trafficPolice: '', trafficPolicePhone: '', longitude: '', latitude: '', managementUnit: '', monitoringPoints: [], monitoringPointsText: '', remarks: '' })
const pointEditForm = ref({ id: null, name: '', roadType: '', responsiblePerson: '', responsiblePhone: '', dutyPersons: [], dutyPersonsText: '', trafficPolice: '', trafficPolicePhone: '', managementUnit: '', monitoringPoints: [], monitoringPointsText: '', remarks: '' })
const waterLevelForm = ref({ depth: '0' })
const supplyForm = ref({ name: '', suppliesText: '', contactPerson: '', contactPhone: '', remark: '', longitude: '', latitude: '' })

// 增援状态
const staffingRecommend = ref(null)
const staffingLoading = ref(false)
const addedDuty = ref([])

// 人员管理状态
const shiftTab = ref('schedule')
const personnelList = ref([])
const showPersonnelForm = ref(false)
const personnelForm = ref({ id: null, name: '', phone: '', groupType: 'admin' })

// 地图
let mapInstance = null
let markers = []

// ======== 计算属性 ========
const severeCount = computed(() => waterPoints.value.filter(p => p.waterLevel === 'severe').length)
const deepCount = computed(() => waterPoints.value.filter(p => p.waterLevel === 'deep').length)

// ======== 工具函数 ========
function getWeatherIcon(text) {
  if (!text) return '☀️'
  if (text.includes('雨')) return '🌧️'
  if (text.includes('雪')) return '❄️'
  if (text.includes('云') || text.includes('阴')) return '☁️'
  if (text.includes('雾')) return '🌫️'
  return '☀️'
}

function getTypeClass(type) {
  const map = { '预警发布': 'warning', '预警结束': 'warning-end', '车辆调度': 'dispatch', '人员调度': 'personnel', '交通管制': 'traffic', '市民来电': 'call', '巡检发现': 'inspect' }
  return map[type] || 'default'
}

function getLevelLabel(level) {
  const map = { normal: '正常', shallow: '浅水', medium: '中等', deep: '较深', severe: '严重' }
  return map[level] || '正常'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

// ======== API 调用 ========
async function fetchWeather() {
  try {
    const [realtimeRes, hourlyRes] = await Promise.all([
      axios.get('/api/flood/weather/realtime'),
      axios.get('/api/flood/weather/hourly')
    ])
    weather.value = realtimeRes.data.weather
    hourlyForecast.value = hourlyRes.data.hourly || []
    await nextTick()
    renderHourlyChart()
  } catch (e) {
    console.error('获取天气失败:', e)
  }
}

async function fetchRainEvents() {
  try {
    const [activeRes, recentRes] = await Promise.all([
      axios.get('/api/flood/rain-events/active'),
      axios.get('/api/flood/rain-events', { params: { limit: 5 } })
    ])
    activeRainEvent.value = activeRes.data.event
    recentRainEvents.value = recentRes.data.events || []
  } catch (e) {
    console.error('获取降雨事件失败:', e)
  }
}

async function fetchWaterPoints() {
  try {
    const res = await axios.get('/api/flood/waterlogging-points')
    waterPoints.value = res.data.points || []
    renderMapMarkers()
  } catch (e) {
    console.error('获取积水点失败:', e)
  }
}

async function fetchTodayDuty() {
  try {
    const res = await axios.get('/api/flood/duty-shifts/today')
    todayDuty.value = res.data.shifts || []
  } catch (e) {
    console.error('获取今日值班失败:', e)
  }
  try {
    const res = await axios.get('/api/flood/duty-added/today')
    addedDuty.value = res.data.added || []
  } catch (e) {
    console.error('获取今日增援失败:', e)
  }
}

async function fetchDutyLeader() {
  try {
    const res = await axios.get('/api/flood/duty-leader')
    dutyLeader.value = res.data.leader
  } catch (e) {
    console.error('获取带班领导失败:', e)
  }
}

function editLeader() {
  if (dutyLeader.value) {
    leaderForm.value = {
      title: dutyLeader.value.title || '带班领导',
      name: dutyLeader.value.name || '',
      phone: dutyLeader.value.phone || '',
    }
  }
  showLeaderEdit.value = true
}

async function saveLeader() {
  try {
    await axios.post('/api/flood/duty-leader', leaderForm.value)
    showLeaderEdit.value = false
    await fetchDutyLeader()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  }
}

async function fetchAllShifts() {
  try {
    const today = new Date()
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 7).toISOString().split('T')[0]
    const end = new Date(today.getFullYear(), today.getMonth() + 1, 7).toISOString().split('T')[0]
    const res = await axios.get('/api/flood/duty-shifts', { params: { start_date: start, end_date: end } })
    allShifts.value = res.data.shifts || []
  } catch (e) {
    console.error('获取排班失败:', e)
  }
}

async function fetchDispatchRecords() {
  try {
    const params = { per_page: 50 }
    if (activeWarning.value) {
      params.warning_id = activeWarning.value.id
    }
    const res = await axios.get('/api/flood/dispatch-records', { params })
    dispatchRecords.value = res.data.records || []
    recentDispatchRecords.value = activeWarning.value ? dispatchRecords.value.slice(0, 2) : []
  } catch (e) {
    console.error('获取台账失败:', e)
  }
}

async function fetchWarningHistory() {
  try {
    const res = await axios.get('/api/flood/warnings/history')
    warningHistory.value = res.data.warnings || []
  } catch (e) {
    console.error('获取预警历史失败:', e)
  }
}

async function selectWarning(warningId) {
  if (selectedWarningId.value === warningId) {
    selectedWarningId.value = null
    warningRecords.value = []
    return
  }
  selectedWarningId.value = warningId
  try {
    const res = await axios.get('/api/flood/dispatch-records', { params: { warning_id: warningId, per_page: 100 } })
    warningRecords.value = res.data.records || []
  } catch (e) {
    console.error('获取预警调度记录失败:', e)
  }
}

async function fetchEmergencyPlan() {
  try {
    const res = await axios.get('/api/flood/emergency-plan')
    emergencyPlanFiles.value = res.data.files || []
  } catch (e) {
    console.error('获取应急预案失败:', e)
  }
}

async function uploadEmergencyPlan(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    await axios.post('/api/flood/emergency-plan/upload', formData)
    await fetchEmergencyPlan()
  } catch (err) {
    alert('上传失败: ' + (err.response?.data?.error || err.message))
  }
}

async function deletePlan(filename) {
  if (!confirm('确定删除该预案文件？')) return
  try {
    await axios.delete(`/api/flood/emergency-plan/${filename}`)
    await fetchEmergencyPlan()
  } catch (err) {
    alert('删除失败: ' + (err.response?.data?.error || err.message))
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

async function fetchEmergencySupplies() {
  try {
    const res = await axios.get('/api/flood/emergency-supplies')
    emergencySupplies.value = res.data.supplies || []
    renderSupplyMarkers()
  } catch (e) {
    console.error('获取应急物资失败:', e)
  }
}

async function fetchActiveWarning() {
  try {
    const res = await axios.get('/api/flood/warnings/active')
    activeWarning.value = res.data.warning
  } catch (e) {
    console.error('获取预警状态失败:', e)
  }
}

function openWarningStart() {
  if (dutyLeader.value) {
    warningStartForm.value.leaderTitle = dutyLeader.value.title || '带班领导'
    warningStartForm.value.leaderName = dutyLeader.value.name || ''
    warningStartForm.value.leaderPhone = dutyLeader.value.phone || ''
  }
  staffingRecommend.value = null
  staffingLoading.value = false
  showWarningStartForm.value = true
}

async function loadStaffingRecommend() {
  try {
    const res = await axios.get('/api/flood/staffing/recommend')
    staffingRecommend.value = res.data.recommendation
  } catch (e) {
    console.error('获取增援推荐失败:', e)
  } finally {
    staffingLoading.value = false
  }
}

async function refreshStaffingRecommend() {
  staffingLoading.value = true
  staffingRecommend.value = null
  try {
    const res = await axios.get('/api/flood/staffing/recommend')
    staffingRecommend.value = res.data.recommendation
  } catch (e) {
    console.error('获取增援推荐失败:', e)
  } finally {
    staffingLoading.value = false
  }
}

async function confirmStaffing() {
  if (!staffingRecommend.value) return
  try {
    await axios.post('/api/flood/staffing/confirm', {
      logId: staffingRecommend.value.logId,
      personName: staffingRecommend.value.personName,
      personPhone: staffingRecommend.value.personPhone,
    })
    await fetchTodayDuty()
    await fetchDispatchRecords()
    staffingRecommend.value = null
  } catch (e) {
    alert('确认增援失败: ' + (e.response?.data?.error || e.message))
  }
}

// 人员管理函数
async function loadPersonnel() {
  try {
    const res = await axios.get('/api/flood/personnel')
    personnelList.value = res.data.personnel || []
  } catch (e) {
    console.error('获取人员列表失败:', e)
  }
}

function editPersonnel(p) {
  personnelForm.value = { id: p.id, name: p.name, phone: p.phone, groupType: p.groupType }
  showPersonnelForm.value = true
}

async function submitPersonnel() {
  if (!personnelForm.value.name) { alert('请输入姓名'); return }
  submitting.value = true
  try {
    if (personnelForm.value.id) {
      await axios.put(`/api/flood/personnel/${personnelForm.value.id}`, {
        name: personnelForm.value.name,
        phone: personnelForm.value.phone,
        groupType: personnelForm.value.groupType,
      })
    } else {
      await axios.post('/api/flood/personnel', {
        name: personnelForm.value.name,
        phone: personnelForm.value.phone,
        groupType: personnelForm.value.groupType,
      })
    }
    await loadPersonnel()
    showPersonnelForm.value = false
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

async function deletePersonnel(p) {
  if (!confirm(`确定删除 ${p.name}？`)) return
  try {
    await axios.delete(`/api/flood/personnel/${p.id}`)
    await loadPersonnel()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

async function confirmStartWarning() {
  try {
    // 启动预警（后端会返回推荐增援）
    const warningRes = await axios.post('/api/flood/warnings/start', { level: warningStartForm.value.level })
    await axios.post('/api/flood/duty-leader', {
      title: warningStartForm.value.leaderTitle,
      name: warningStartForm.value.leaderName,
      phone: warningStartForm.value.leaderPhone,
    })
    // 如果有推荐增援且未手动确认，自动确认
    const recommendedStaff = warningRes.data.recommendedStaff
    if (recommendedStaff && !staffingRecommend.value) {
      await axios.post('/api/flood/staffing/confirm', {
        logId: recommendedStaff.logId,
        personName: recommendedStaff.personName,
        personPhone: recommendedStaff.personPhone,
      })
    }
    await fetchActiveWarning()
    await fetchDutyLeader()
    await fetchDispatchRecords()
    await fetchWarningHistory()
    await fetchTodayDuty()
    showWarningStartForm.value = false
  } catch (e) {
    alert('启动预警失败: ' + (e.response?.data?.error || e.message))
  }
}

async function endWarning() {
  if (!confirm('确定结束当前预警？\n\n系统将自动生成报告并保存，带班领导和积水数据将被清空。')) return
  try {
    await axios.post('/api/flood/warnings/end')
    await fetchActiveWarning()
    dispatchRecords.value = []
    recentDispatchRecords.value = []
    await fetchWarningHistory()
    await fetchDutyLeader()
  } catch (e) {
    alert('结束预警失败: ' + (e.response?.data?.error || e.message))
  }
}

function getWarningLevelLabel(level) {
  const map = { blue: '蓝', yellow: '黄', orange: '橙', red: '红' }
  return map[level] || ''
}

function getWarningLevelClass(level) {
  const map = { blue: 'warning-blue', yellow: 'warning-yellow', orange: 'warning-orange', red: 'warning-red' }
  return map[level] || ''
}

function parseMonitoringPoints(text) {
  if (!text) return []
  return text.split('\n').map(line => {
    const parts = line.trim().split(/\s+/)
    return { type: parts[0] || '', code: parts[1] || '' }
  }).filter(m => m.type && m.code)
}

function formatWarningTime(start, end) {
  const s = start ? new Date(start) : null
  const e = end ? new Date(end) : null
  if (!s) return ''
  const fmtDate = (d) => `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (e) return `${fmtDate(s)} ~ ${fmtDate(e)}`
  return `${fmtDate(s)} 至今`
}

function editSupply(supply) {
  editingSupply.value = supply
  supplyForm.value = {
    name: supply.name,
    suppliesText: (supply.suppliesList || []).join('\n'),
    contactPerson: supply.contactPerson || '',
    contactPhone: supply.contactPhone || '',
    remark: supply.remark || '',
    longitude: supply.longitude || '',
    latitude: supply.latitude || ''
  }
  showSupplyForm.value = true
}

async function submitSupply() {
  if (!supplyForm.value.name) {
    alert('请输入物资点名称')
    return
  }
  const items = supplyForm.value.suppliesText.split('\n').map(s => s.trim()).filter(s => s)
  const payload = {
    name: supplyForm.value.name,
    suppliesList: items,
    contactPerson: supplyForm.value.contactPerson,
    contactPhone: supplyForm.value.contactPhone,
    remark: supplyForm.value.remark
  }
  if (!editingSupply.value) {
    payload.longitude = supplyForm.value.longitude
    payload.latitude = supplyForm.value.latitude
  }
  try {
    if (editingSupply.value) {
      await axios.put(`/api/flood/emergency-supplies/${editingSupply.value.id}`, payload)
    } else {
      await axios.post('/api/flood/emergency-supplies', payload)
    }
    showSupplyForm.value = false
    editingSupply.value = null
    supplyForm.value = { name: '', suppliesText: '', contactPerson: '', contactPhone: '', remark: '', longitude: '', latitude: '' }
    mapMode.value = 'view'
    await fetchEmergencySupplies()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  }
}

async function deleteSupply(id) {
  if (!confirm('确定删除该物资点？')) return
  try {
    await axios.delete(`/api/flood/emergency-supplies/${id}`)
    await fetchEmergencySupplies()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

// ======== 地图 ========
function initMap() {
  if (!window.AMap) {
    console.error('AMap SDK 未加载')
    return
  }
  mapInstance = new window.AMap.Map('flood-map', {
    zoom: 13,
    center: [110.976935, 35.06161],
    resizeEnable: true,
    mapStyle: 'amap://styles/dark',
    zooms: [3, 18]
  })

  mapInstance.on('click', (e) => {
    const lng = e.lnglat.getLng().toFixed(6)
    const lat = e.lnglat.getLat().toFixed(6)
    if (mapMode.value === 'add') {
      pointForm.value.longitude = lng
      pointForm.value.latitude = lat
      showPointForm.value = true
    } else if (mapMode.value === 'add-supply') {
      supplyForm.value.longitude = lng
      supplyForm.value.latitude = lat
      showSupplyForm.value = true
      mapMode.value = 'view'
    }
  })
}

function zoomIn() {
  if (mapInstance) {
    mapInstance.zoomIn()
  }
}

function zoomOut() {
  if (mapInstance) {
    mapInstance.zoomOut()
  }
}

function renderMapMarkers() {
  if (!mapInstance) return
  markers.forEach(m => mapInstance.remove(m))
  markers = []

  waterPoints.value.forEach(p => {
    if (!p.longitude || !p.latitude) return
    const pos = new window.AMap.LngLat(parseFloat(p.longitude), parseFloat(p.latitude))
    const color = getMarkerColor(p.waterLevel)
    const marker = new window.AMap.Marker({
      position: pos,
      title: p.name,
      content: `<div style="width:16px;height:16px;background:${color};border-radius:50%;border:2px solid #fff;box-shadow:0 0 6px ${color}"></div>`,
      offset: new window.AMap.Pixel(-8, -8)
    })

    const dutyPersonsText = (p.dutyPersons || []).map(d => d.phone ? `${d.name}(${d.phone})` : d.name).join('、') || '-'
    const monitorText = (p.monitoringPoints || []).map(m => `<span style="display:inline-block;padding:1px 6px;background:rgba(103,194,58,0.2);color:#67c23a;border-radius:3px;font-size:11px;margin:1px">${m.type} ${m.code}</span>`).join(' ')
    const infoContent = `
      <div style="padding:14px 16px;min-width:240px;background:rgba(13,31,60,0.88);backdrop-filter:blur(12px);border-radius:10px;border:none;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-shadow:0 4px 24px rgba(0,0,0,0.5)">
        <div style="font-weight:700;font-size:14px;margin-bottom:8px;color:#fff;border-bottom:1px solid rgba(64,158,255,0.15);padding-bottom:8px">${p.name}</div>
        <div style="display:flex;flex-direction:column;gap:5px;font-size:12px;color:rgba(255,255,255,0.7)">
          ${p.roadType ? '<div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">类型</span><span style="color:#409eff;font-weight:500">' + p.roadType + '</span></div>' : ''}
          <div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">水位</span><span style="color:${p.waterLevel === 'severe' ? '#f5222d' : p.waterLevel === 'deep' ? '#f56c6c' : p.waterLevel === 'medium' ? '#e6a23c' : '#67c23a'};font-weight:500">${getLevelLabel(p.waterLevel)} (${p.waterDepth || '0'}cm)</span></div>
          ${p.managementUnit ? '<div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">管理</span>' + p.managementUnit + '</div>' : ''}
          ${p.responsiblePerson ? '<div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">责任人</span>' + p.responsiblePerson + (p.responsiblePhone ? ' <span style="color:rgba(255,255,255,0.4)">(' + p.responsiblePhone + ')</span>' : '') + '</div>' : ''}
          <div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">值守</span>${dutyPersonsText}</div>
          ${p.trafficPolice ? '<div><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px">交警</span>' + p.trafficPolice + (p.trafficPolicePhone ? ' <span style="color:rgba(255,255,255,0.4)">(' + p.trafficPolicePhone + ')</span>' : '') + '</div>' : ''}
          ${monitorText ? '<div style="margin-top:4px"><span style="color:rgba(255,255,255,0.4);display:inline-block;width:56px;vertical-align:top">监控</span><span>' + monitorText + '</span></div>' : ''}
        </div>
      </div>
    `
    const infoWindow = new window.AMap.InfoWindow({ content: infoContent, offset: new window.AMap.Pixel(0, -10) })
    marker.on('click', () => infoWindow.open(mapInstance, marker.getPosition()))
    mapInstance.add(marker)
    markers.push(marker)
  })

  renderSupplyMarkers()
}

function focusPoint(p) {
  if (!mapInstance || !p.longitude || !p.latitude) return
  const pos = new window.AMap.LngLat(parseFloat(p.longitude), parseFloat(p.latitude))
  mapInstance.setZoomAndCenter(16, pos, false)
  const idx = waterPoints.value.findIndex(wp => wp.id === p.id)
  if (idx >= 0 && markers[idx]) {
    markers[idx].emit('click')
  }
}

let supplyMarkers = []

function renderSupplyMarkers() {
  if (!mapInstance) return
  supplyMarkers.forEach(m => mapInstance.remove(m))
  supplyMarkers = []

  emergencySupplies.value.forEach(s => {
    if (!s.longitude || !s.latitude) return
    const pos = new window.AMap.LngLat(parseFloat(s.longitude), parseFloat(s.latitude))
    const marker = new window.AMap.Marker({
      position: pos,
      title: s.name,
      content: `<div style="width:20px;height:20px;background:#f5a623;border-radius:4px;border:2px solid #fff;box-shadow:0 0 6px #f5a623;display:flex;align-items:center;justify-content:center;font-size:10px;color:#fff;font-weight:bold">物</div>`,
      offset: new window.AMap.Pixel(-10, -10)
    })

    const itemsHtml = (s.suppliesList || []).map(i => `<span style="display:inline-block;padding:1px 4px;background:#f0f0f0;border-radius:3px;font-size:11px;margin:1px">${i}</span>`).join(' ')
    const infoContent = `
      <div style="padding:8px;min-width:180px">
        <div style="font-weight:600;margin-bottom:4px">${s.name}</div>
        <div style="font-size:12px;color:#666;margin-bottom:4px">${itemsHtml || '暂无物资清单'}</div>
        <div style="font-size:12px;color:#666">联系人: ${s.contactPerson || '-'}</div>
        <div style="font-size:12px;color:#666">电话: ${s.contactPhone || '-'}</div>
      </div>
    `
    const infoWindow = new window.AMap.InfoWindow({ content: infoContent, offset: new window.AMap.Pixel(0, -10) })
    marker.on('click', () => infoWindow.open(mapInstance, marker.getPosition()))
    mapInstance.add(marker)
    supplyMarkers.push(marker)
  })
}

function getMarkerColor(level) {
  const map = { normal: '#67c23a', shallow: '#409eff', medium: '#e6a23c', deep: '#f56c6c', severe: '#f5222d' }
  return map[level] || '#67c23a'
}

// ======== 图表 ========
function renderHourlyChart() {
  const el = document.querySelector('.flood-page .chart-wrapper')
  if (!el) return
  const chart = echarts.init(el, 'dark')
  const times = hourlyForecast.value.map(h => {
    const d = new Date(h.time)
    return `${d.getHours()}:00`
  })
  const precips = hourlyForecast.value.map(h => parseFloat(h.precip || 0))
  const temps = hourlyForecast.value.map(h => parseFloat(h.temp || 0))

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['降雨量', '温度'], textStyle: { color: '#ccc', fontSize: 11 }, top: 0 },
    grid: { left: 30, right: 10, top: 28, bottom: 20 },
    xAxis: { type: 'category', data: times, axisLabel: { color: '#999', fontSize: 10 }, axisLine: { lineStyle: { color: '#333' } } },
    yAxis: [
      { type: 'value', name: 'mm', axisLabel: { color: '#999', fontSize: 10 }, splitLine: { lineStyle: { color: '#333' } } },
      { type: 'value', name: '°C', axisLabel: { color: '#999', fontSize: 10 }, splitLine: { show: false } }
    ],
    series: [
      { name: '降雨量', type: 'bar', data: precips, itemStyle: { color: '#409eff' }, barMaxWidth: 12 },
      { name: '温度', type: 'line', yAxisIndex: 1, data: temps, smooth: true, lineStyle: { color: '#67c23a' }, itemStyle: { color: '#67c23a' }, symbol: 'none' }
    ]
  })

  const resizeHandler = () => chart.resize()
  window.addEventListener('resize', resizeHandler)
  el._resizeHandler = resizeHandler
}

// ======== 抽屉操作 ========
function showDrawer(type) {
  activeDrawer.value = type
  if (type === 'shift') fetchAllShifts()
  if (type === 'ledger') {
    fetchWarningHistory()
    selectedWarningId.value = null
    warningRecords.value = []
  }
}

function startAddSupply() {
  editingSupply.value = null
  supplyForm.value = { name: '', suppliesText: '', contactPerson: '', contactPhone: '', remark: '', longitude: '', latitude: '' }
  closeDrawer()
  mapMode.value = 'add-supply'
}

function closeDrawer() {
  activeDrawer.value = null
}

// ======== 提交操作 ========
async function submitLedger() {
  if (!ledgerForm.value.recordType || !ledgerForm.value.content) {
    alert('请填写记录类型和详细内容')
    return
  }
  submitting.value = true
  try {
    const payload = { ...ledgerForm.value }
    if (activeWarning.value) payload.warningId = activeWarning.value.id
    await axios.post('/api/flood/dispatch-records', payload)
    showLedgerForm.value = false
    ledgerForm.value = { recordType: '', content: '', location: '', operator: '', images: [], warningId: null }
    await fetchDispatchRecords()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

async function submitShift() {
  if (!shiftForm.value.shiftDate || !shiftForm.value.person1) {
    alert('请填写值班日期和至少一名值守人员')
    return
  }
  submitting.value = true
  try {
    await axios.post('/api/flood/duty-shifts', {
      ...shiftForm.value,
      shiftDate: shiftForm.value.shiftDate + 'T00:00:00'
    })
    showShiftForm.value = false
    shiftForm.value = { shiftDate: '', shiftName: '白班', person1: '', person1Phone: '', person2: '', person2Phone: '' }
    await fetchAllShifts()
    await fetchTodayDuty()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

async function submitPoint() {
  if (!pointForm.value.name) {
    alert('请输入积水点名称')
    return
  }
  submitting.value = true
  try {
    const payload = { ...pointForm.value }
    payload.dutyPersons = pointForm.value.dutyPersons.filter(p => p.name)
    payload.monitoringPoints = parseMonitoringPoints(pointForm.value.monitoringPointsText)
    delete payload.dutyPersonsText
    delete payload.monitoringPointsText
    await axios.post('/api/flood/waterlogging-points', payload)
    showPointForm.value = false
    pointForm.value = { name: '', roadType: '', responsiblePerson: '', responsiblePhone: '', dutyPersons: [{ name: '', phone: '' }], trafficPolice: '', trafficPolicePhone: '', longitude: '', latitude: '', managementUnit: '', monitoringPoints: [], monitoringPointsText: '', remarks: '' }
    mapMode.value = 'view'
    await fetchWaterPoints()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

function editPoint(point) {
  const dutyPersons = (point.dutyPersons || []).map(p => ({ name: p.name || '', phone: p.phone || '' }))
  const monitoringPoints = point.monitoringPoints || []
  pointEditForm.value = {
    id: point.id,
    name: point.name,
    roadType: point.roadType || '',
    responsiblePerson: point.responsiblePerson || '',
    responsiblePhone: point.responsiblePhone || '',
    dutyPersons: dutyPersons.length ? dutyPersons : [{ name: '', phone: '' }],
    trafficPolice: point.trafficPolice || '',
    trafficPolicePhone: point.trafficPolicePhone || '',
    managementUnit: point.managementUnit || '',
    monitoringPoints: monitoringPoints,
    monitoringPointsText: monitoringPoints.map(m => `${m.type} ${m.code}`).join('\n'),
    remarks: point.remarks || ''
  }
  showPointEditForm.value = true
}

async function submitPointEdit() {
  if (!pointEditForm.value.name) {
    alert('请输入积水点名称')
    return
  }
  try {
    await axios.put(`/api/flood/waterlogging-points/${pointEditForm.value.id}`, {
      name: pointEditForm.value.name,
      roadType: pointEditForm.value.roadType,
      responsiblePerson: pointEditForm.value.responsiblePerson,
      responsiblePhone: pointEditForm.value.responsiblePhone,
      dutyPersons: pointEditForm.value.dutyPersons.filter(p => p.name),
      trafficPolice: pointEditForm.value.trafficPolice,
      trafficPolicePhone: pointEditForm.value.trafficPolicePhone,
      managementUnit: pointEditForm.value.managementUnit,
      monitoringPoints: parseMonitoringPoints(pointEditForm.value.monitoringPointsText),
      remarks: pointEditForm.value.remarks
    })
    showPointEditForm.value = false
    await fetchWaterPoints()
  } catch (e) {
    alert('更新失败: ' + (e.response?.data?.error || e.message))
  }
}

function editWaterLevel(point) {
  editingPoint.value = point
  waterLevelForm.value.depth = point.waterDepth || '0'
  showWaterLevelForm.value = true
}

async function submitWaterLevel() {
  try {
    await axios.put(`/api/flood/waterlogging-points/${editingPoint.value.id}/water-level`, {
      waterDepth: waterLevelForm.value.depth
    })
    showWaterLevelForm.value = false
    await fetchWaterPoints()
  } catch (e) {
    alert('更新失败: ' + (e.response?.data?.error || e.message))
  }
}

async function deletePoint(id) {
  if (!confirm('确定删除该积水点？')) return
  try {
    await axios.delete(`/api/flood/waterlogging-points/${id}`)
    await fetchWaterPoints()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

async function handleLedgerImageUpload(e) {
  const files = e.target.files
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await axios.post('/api/flood/upload-image', formData)
      ledgerForm.value.images.push(res.data.url)
    } catch (err) {
      console.error('上传图片失败:', err)
    }
  }
}

async function handleShiftUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await axios.post('/api/flood/duty-shifts/upload', formData)
    alert(res.data.message)
    await fetchAllShifts()
    await fetchTodayDuty()
  } catch (err) {
    alert('上传失败: ' + (err.response?.data?.error || err.message))
  }
}

function openReportSelect() {
  fetchWarningHistory()
  showReportSelect.value = true
}

async function generateReport(warningId) {
  showReportSelect.value = false
  try {
    const res = await axios.get('/api/flood/dispatch-report', { params: { warning_id: warningId } })
    const report = res.data.report

    // 如果是已保存的文本报告，直接下载
    if (report.text) {
      const levelMap = { blue: '蓝色', yellow: '黄色', orange: '橙色', red: '红色' }
      const levelLabel = (lv) => levelMap[lv] || lv || '-'
      const fmtDate = (iso) => {
        if (!iso) return '-'
        const d = new Date(iso)
        return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`
      }
      const w = report.warning
      const levelName = w ? levelLabel(w.level) : ''
      const dateStr = w ? fmtDate(w.startTime) : ''

      const blob = new Blob([report.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${levelName}预警调度报告_${dateStr}.txt`
      a.click()
      URL.revokeObjectURL(url)
      return
    }

    // 否则动态生成报告
    const levelMap = { blue: '蓝色', yellow: '黄色', orange: '橙色', red: '红色' }
    const levelLabel = (lv) => levelMap[lv] || lv || '-'
    const fmt = (iso) => {
      if (!iso) return '-'
      const d = new Date(iso)
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
    }
    const fmtDate = (iso) => {
      if (!iso) return '-'
      const d = new Date(iso)
      return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`
    }
    const repeat = (ch, n) => ch.repeat(n)
    const w = report.warning
    const levelName = w ? levelLabel(w.level) : ''
    const dateStr = w ? `${fmtDate(w.startTime)}` : ''

    // 报告标题
    let text = `运城市智慧城市管理平台防汛指挥调度系统\n`
    text += `${levelName}预警调度报告\n`
    text += `${repeat('=', 50)}\n\n`

    // 一、预警基本信息
    text += `【一、预警信息】\n`
    if (w) {
      text += `  预警等级: ${levelName}预警\n`
      text += `  启动时间: ${fmt(w.startTime)}\n`
      text += `  结束时间: ${w.endTime ? fmt(w.endTime) : '进行中'}\n`
      text += `  当前状态: ${w.status === 'active' ? '进行中' : '已结束'}\n`
    } else {
      text += `  暂无预警信息\n`
    }

    // 二、带班领导与值班人员
    text += `\n【二、人员信息】\n`
    text += `  带班领导:\n`
    if (report.dutyLeader) {
      text += `    ${report.dutyLeader.title || '带班领导'}: ${report.dutyLeader.name}`
      if (report.dutyLeader.phone) text += ` (${report.dutyLeader.phone})`
      text += `\n`
    } else {
      text += `    暂未设置\n`
    }
    text += `  值班人员:\n`
    if (report.dutyShifts && report.dutyShifts.length) {
      report.dutyShifts.forEach(s => {
        text += `    ${s.shiftName || '-'}: ${s.person1 || '-'}`
        if (s.person1Phone) text += ` (${s.person1Phone})`
        text += ` / ${s.person2 || '-'}`
        if (s.person2Phone) text += ` (${s.person2Phone})`
        text += `\n`
      })
    } else {
      text += `    暂无排班记录\n`
    }

    // 三、汛期天气情况
    text += `\n【三、天气情况】\n`
    if (report.weatherSummary && report.weatherSummary.length) {
      const latest = report.weatherSummary[0]
      text += `  最新气象:\n`
      text += `    天气: ${latest.weatherText || '-'}\n`
      text += `    温度: ${latest.temperature || '-'}°C  湿度: ${latest.humidity || '-'}%\n`
      text += `    风向: ${latest.windDirection || '-'}  风力: ${latest.windPower || '-'}级\n`
      text += `    近1h降雨量: ${latest.rainfall1h || '0'}mm\n\n`
      text += `  观测记录(共${report.weatherSummary.length}条):\n`
      report.weatherSummary.slice(0, 20).forEach(item => {
        text += `    [${fmt(item.recordedAt)}] ${item.weatherText || '-'} ${item.temperature || '-'}°C 降雨${item.rainfall1h || '0'}mm\n`
      })
    } else {
      text += `  暂无天气观测记录\n`
    }

    if (report.rainEvents && report.rainEvents.length) {
      text += `\n  降雨事件:\n`
      report.rainEvents.forEach((e, i) => {
        text += `    第${i+1}次: ${fmt(e.startTime)} ~ ${e.endTime ? fmt(e.endTime) : '进行中'}\n`
        text += `      强度: ${e.intensity || '-'}  最大1h雨量: ${e.maxRainfall1h || '-'}mm\n`
      })
    }

    // 四、调度台账
    text += `\n【四、调度台账】\n`
    text += `  共${report.summary.totalRecords}条记录\n`
    if (Object.keys(report.summary.typeStats).length) {
      text += `  按类型: `
      text += Object.entries(report.summary.typeStats).map(([k, v]) => `${k}${v}条`).join('、')
      text += `\n\n`
    }
    if (report.records && report.records.length) {
      report.records.forEach(r => {
        text += `  [${fmt(r.eventTime)}] ${r.recordType || '其他'}\n`
        text += `    ${r.content || '-'}\n`
        if (r.location) text += `    地点: ${r.location}`
        if (r.operator) text += ` | 操作人: ${r.operator}`
        text += `\n`
      })
    } else {
      text += `  暂无调度记录\n`
    }

    // 五、积水点信息
    text += `\n【五、积水点信息】\n`
    if (report.waterPoints && report.waterPoints.length) {
      const levelOrder = { severe: 0, deep: 1, medium: 2, shallow: 3, normal: 4 }
      const sorted = [...report.waterPoints].sort((a, b) => (levelOrder[a.waterLevel] ?? 5) - (levelOrder[b.waterLevel] ?? 5))
      const waterLevelLabels = { normal: '正常', shallow: '浅水', medium: '中等', deep: '较深', severe: '严重' }
      text += `  共${report.waterPoints.length}个积水点\n`
      sorted.forEach(wp => {
        const label = waterLevelLabels[wp.waterLevel] || wp.waterLevel || '正常'
        text += `  ${wp.name}: ${label}(${wp.waterDepth || '0'}cm)`
        if (wp.dutyPersons && wp.dutyPersons.length) {
          const names = wp.dutyPersons.map(d => d.name).filter(n => n).join('、')
          if (names) text += ` 值守:${names}`
        }
        text += `\n`
      })
    } else {
      text += `  暂无积水点\n`
    }

    text += `\n${repeat('=', 50)}\n`
    text += `报告生成时间: ${fmt(new Date().toISOString())}\n`
    text += `运城市智慧城市管理平台防汛指挥调度系统\n`

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${levelName}预警调度报告_${dateStr}.txt`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    alert('生成报告失败: ' + (e.response?.data?.error || e.message))
  }
}

function previewImage(url) {
  window.open(url, '_blank')
}

// ======== 生命周期 ========
let timeInterval = null
let weatherInterval = null

onMounted(async () => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)

  await nextTick()
  initMap()

  await Promise.all([
    fetchWeather(),
    fetchRainEvents(),
    fetchWaterPoints(),
    fetchTodayDuty(),
    fetchDispatchRecords(),
    fetchEmergencyPlan(),
    fetchEmergencySupplies(),
    fetchActiveWarning(),
    fetchDutyLeader()
  ])

  // 每5分钟刷新天气
  weatherInterval = setInterval(() => {
    fetchWeather()
    fetchRainEvents()
  }, 300000)

  // 每2分钟刷新数据
  setInterval(() => {
    fetchWaterPoints()
    fetchTodayDuty()
    fetchEmergencySupplies()
    fetchActiveWarning()
  }, 120000)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (weatherInterval) clearInterval(weatherInterval)
  if (mapInstance) mapInstance.destroy()
})
</script>

<style scoped>
.flood-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #0a1628 0%, #0d1f3c 50%, #0a1628 100%);
  color: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  z-index: 9999;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(64, 158, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(64, 158, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
}
.glow-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
}
.orb-1 { width: 400px; height: 400px; background: #409eff; top: -100px; left: -100px; }
.orb-2 { width: 300px; height: 300px; background: #00c6fb; bottom: -50px; right: -50px; }

/* 头部 */
.flood-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(13, 31, 60, 0.8);
  border-bottom: 1px solid rgba(64, 158, 255, 0.15);
  position: relative;
  z-index: 10;
  flex-shrink: 0;
  min-height: 50px;
}
.header-left {
  flex: 1;
}
.header-left .back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}
.header-left .back-btn:hover { color: #409eff; }
.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}
.flood-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  font-weight: 700;
  background: linear-gradient(90deg, #409eff, #00c6fb);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  flex: 1;
  justify-content: flex-end;
}
/* 预警控制区块 */
.warning-section {
  border-color: rgba(245, 34, 45, 0.2) !important;
  background: rgba(245, 34, 45, 0.03);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}
.warning-start-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(245, 34, 45, 0.15);
  border: 1px solid rgba(245, 34, 45, 0.4);
  border-radius: 6px;
  color: #f5222d;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  width: 100%;
  justify-content: center;
}
.warning-start-btn:hover {
  background: rgba(245, 34, 45, 0.25);
  border-color: #f5222d;
}
.warning-active-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  flex: 1;
}
.warning-active-display.warning-blue { color: #409eff; }
.warning-active-display.warning-yellow { color: #e6a23c; }
.warning-active-display.warning-orange { color: #f5a623; }
.warning-active-display.warning-red { color: #f5222d; }
.warning-end-btn-sm {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  background: rgba(103, 194, 58, 0.15);
  border: 1px solid rgba(103, 194, 58, 0.4);
  border-radius: 6px;
  color: #67c23a;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.warning-end-btn-sm:hover {
  background: rgba(103, 194, 58, 0.25);
  border-color: #67c23a;
}
.warning-level-select {
  display: flex;
  gap: 8px;
}
.warning-level-option {
  flex: 1;
  padding: 8px 4px;
  border-radius: 6px;
  border: 2px solid transparent;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.warning-level-option.level-blue { background: rgba(64, 158, 255, 0.1); color: #409eff; border-color: rgba(64, 158, 255, 0.2); }
.warning-level-option.level-blue.selected { background: rgba(64, 158, 255, 0.25); border-color: #409eff; }
.warning-level-option.level-yellow { background: rgba(230, 162, 60, 0.1); color: #e6a23c; border-color: rgba(230, 162, 60, 0.2); }
.warning-level-option.level-yellow.selected { background: rgba(230, 162, 60, 0.25); border-color: #e6a23c; }
.warning-level-option.level-orange { background: rgba(245, 166, 35, 0.1); color: #f5a623; border-color: rgba(245, 166, 35, 0.2); }
.warning-level-option.level-orange.selected { background: rgba(245, 166, 35, 0.25); border-color: #f5a623; }
.warning-level-option.level-red { background: rgba(245, 34, 45, 0.1); color: #f5222d; border-color: rgba(245, 34, 45, 0.2); }
.warning-level-option.level-red.selected { background: rgba(245, 34, 45, 0.25); border-color: #f5222d; }
.time-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: rgba(255,255,255,0.7);
  font-variant-numeric: tabular-nums;
}

/* 主内容区 */
.flood-main {
  flex: 1;
  display: flex;
  gap: 12px;
  padding: 12px;
  min-width: 0;
  overflow: hidden;
}

/* 面板 */
.flood-panel {
  width: 300px;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  flex-shrink: 0;
}
.flood-panel::-webkit-scrollbar { width: 4px; }
.flood-panel::-webkit-scrollbar-track { background: transparent; }
.flood-panel::-webkit-scrollbar-thumb { background: rgba(64, 158, 255, 0.2); border-radius: 2px; }

.panel-section {
  background: rgba(13, 31, 60, 0.6);
  border: 1px solid rgba(64, 158, 255, 0.12);
  border-radius: 12px;
  padding: 14px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.panel-icon { color: #409eff; }
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
}

/* 天气面板 */
.weather-current { text-align: center; }
.weather-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 4px;
}
.weather-icon { font-size: 40px; }
.weather-temp {
  font-size: 36px;
  font-weight: 700;
  background: linear-gradient(180deg, #fff, rgba(255,255,255,0.7));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.weather-desc {
  font-size: 14px;
  color: rgba(255,255,255,0.7);
  margin-bottom: 10px;
}
.weather-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.detail-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
  background: rgba(0,0,0,0.2);
  border-radius: 8px;
}
.detail-label { font-size: 11px; color: rgba(255,255,255,0.5); }
.detail-value { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.9); }
.weather-loading {
  text-align: center;
  padding: 20px;
  color: rgba(255,255,255,0.5);
}

/* 图表 */
.chart-wrapper { height: 160px; }

/* 降雨状态 */
/* 中间地图 */
.flood-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
.map-container {
  flex: 1;
  position: relative;
  background: linear-gradient(180deg, rgba(13,31,60,0.6), rgba(10,22,40,0.8));
  border: 1px solid rgba(64,158,255,0.15);
  border-radius: 12px;
  overflow: hidden;
}
.map-element { width: 100%; height: 100%; }
.map-toolbar {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 5;
}
.toolbar-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13,31,60,0.8);
  border: 1px solid rgba(64,158,255,0.3);
  border-radius: 8px;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  transition: all 0.2s;
}
.toolbar-btn:hover, .toolbar-btn.active {
  background: rgba(64,158,255,0.2);
  color: #409eff;
  border-color: #409eff;
}
.map-stats {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  z-index: 5;
}
.stat-item {
  padding: 6px 12px;
  background: rgba(13,31,60,0.8);
  border: 1px solid rgba(64,158,255,0.3);
  border-radius: 8px;
  text-align: center;
}
.stat-num { font-size: 18px; font-weight: 700; color: #409eff; display: block; }
.stat-text { font-size: 11px; color: rgba(255,255,255,0.6); }
.stat-item.warning .stat-num { color: #e6a23c; }
.stat-item.danger .stat-num { color: #f56c6c; }

/* 滚动数据条 */
.scroll-data {
  height: 44px;
  background: rgba(13,31,60,0.8);
  border: 1px solid rgba(64,158,255,0.15);
  border-radius: 10px;
  display: flex;
  align-items: center;
  overflow: hidden;
}
.scroll-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  white-space: nowrap;
  border-right: 1px solid rgba(64,158,255,0.15);
  height: 100%;
  position: relative;
  z-index: 2;
  background: inherit;
}
.scroll-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  align-items: center;
  position: relative;
  z-index: 1;
}
.scroll-inner {
  display: flex;
  gap: 24px;
  padding: 0 12px;
  animation: scrollTicker 20s linear infinite;
}
@keyframes scrollTicker {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
.scroll-ticker {
  white-space: nowrap;
  font-size: 13px;
}
.scroll-empty {
  padding: 0 12px;
  font-size: 12px;
  color: rgba(255,255,255,0.3);
}
.ticker-time { color: rgba(255,255,255,0.4); margin-right: 6px; }
.ticker-type { color: #409eff; margin-right: 6px; }
.ticker-title { color: rgba(255,255,255,0.8); }

/* 值班人员 */
/* 带班领导 */
.leader-section {
  border-color: rgba(230, 162, 60, 0.25) !important;
  background: rgba(230, 162, 60, 0.05);
}
.leader-section .panel-header {
  position: relative;
}
.leader-edit-btn {
  position: absolute;
  right: 0;
  top: 0;
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}
.leader-edit-btn:hover {
  color: #e6a23c;
  background: rgba(230, 162, 60, 0.15);
}
.leader-info {
  text-align: center;
  padding: 4px 0;
}
.leader-name {
  font-size: 18px;
  font-weight: 700;
  color: #e6a23c;
}
.leader-phone {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 2px;
}
.leader-empty {
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  padding: 4px 0;
}
.duty-list { display: flex; flex-direction: column; gap: 8px; }
.duty-card {
  padding: 10px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.duty-shift-name {
  font-size: 12px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 6px;
}
.duty-persons { display: flex; flex-direction: column; gap: 4px; }
.duty-person {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.person-name { color: rgba(255,255,255,0.9); }
.person-phone { color: rgba(255,255,255,0.5); }
.duty-empty {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: rgba(255,255,255,0.4);
}

/* 调度记录列表 */
.dispatch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}
.dispatch-list::-webkit-scrollbar { width: 3px; }
.dispatch-list::-webkit-scrollbar-thumb { background: rgba(64,158,255,0.2); border-radius: 2px; }
.dispatch-item {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.dispatch-type-badge {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  align-self: flex-start;
}
.dispatch-type-badge.warning { background: rgba(230,162,60,0.2); color: #e6a23c; }
.dispatch-type-badge.warning-end { background: rgba(103,194,58,0.2); color: #67c23a; }
.dispatch-type-badge.dispatch { background: rgba(64,158,255,0.2); color: #409eff; }
.dispatch-type-badge.call { background: rgba(103,194,58,0.2); color: #67c23a; }
  .dispatch-type-badge.inspect { background: rgba(144,147,153,0.2); color: #909399; }
  .dispatch-type-badge.personnel { background: rgba(230,162,60,0.2); color: #e6a23c; }
  .dispatch-type-badge.traffic { background: rgba(245,108,108,0.2); color: #f56c6c; }
  .dispatch-type-badge.default { background: rgba(144,147,153,0.2); color: #909399; }
.dispatch-content { flex: 1; min-width: 0; }
.dispatch-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dispatch-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: rgba(255,255,255,0.4);
  margin-top: 2px;
}
.dispatch-empty {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: rgba(255,255,255,0.4);
}

/* 功能按钮 */
.panel-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  background: rgba(64,158,255,0.1);
  border: 1px solid rgba(64,158,255,0.25);
  border-radius: 8px;
  color: rgba(255,255,255,0.8);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:hover {
  background: rgba(64,158,255,0.2);
  border-color: #409eff;
  color: #fff;
}

/* ======== 抽屉 ======== */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 99999;
  display: flex;
  justify-content: flex-end;
}
.drawer-panel {
  width: 420px;
  height: 100%;
  background: #0d1f3c;
  border-left: 1px solid rgba(64,158,255,0.2);
  display: flex;
  flex-direction: column;
}
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(64,158,255,0.15);
}
.drawer-header h3 { font-size: 16px; font-weight: 600; }
.drawer-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: rgba(255,255,255,0.6);
  font-size: 24px;
  cursor: pointer;
  border-radius: 6px;
}
.drawer-close:hover { background: rgba(255,255,255,0.1); }
.drawer-body {
  flex: 1;
  padding: 16px 20px;
  overflow-y: auto;
}
.drawer-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}
.toolbar-hint {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}

/* ======== 模态框 ======== */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-panel {
  width: 520px;
  max-height: 80vh;
  background: #0d1f3c;
  border: 1px solid rgba(64,158,255,0.2);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
}
.modal-panel.small { width: 400px; }
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(64,158,255,0.15);
}
.modal-header h3 { font-size: 16px; font-weight: 600; }
.modal-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: rgba(255,255,255,0.6);
  font-size: 24px;
  cursor: pointer;
  border-radius: 6px;
}
.modal-close:hover { background: rgba(255,255,255,0.1); }
.modal-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid rgba(64,158,255,0.15);
}

/* ======== 表单 ======== */
.form-group {
  margin-bottom: 14px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,0.7);
  margin-bottom: 6px;
}
.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(64,158,255,0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  border-color: #409eff;
}
.form-group textarea { resize: vertical; }
.form-hint {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 4px;
}
.duty-persons-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 6px;
}
.duty-person-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.duty-input {
  flex: 1;
  padding: 6px 10px;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(64,158,255,0.2);
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  outline: none;
}
.duty-input:focus {
  border-color: #409eff;
}
.duty-remove-btn {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(245,108,108,0.15);
  color: #f56c6c;
  border: none;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.duty-remove-btn:hover {
  background: rgba(245,108,108,0.3);
}
.duty-add-btn {
  background: none;
  border: 1px dashed rgba(64,158,255,0.3);
  color: #409eff;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.duty-add-btn:hover {
  border-color: #409eff;
  background: rgba(64,158,255,0.1);
}
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.weather-snapshot {
  padding: 8px 12px;
  background: rgba(64,158,255,0.1);
  border-radius: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.7);
}
.snapshot-label { font-weight: 600; margin-right: 6px; }

/* ======== 按钮 ======== */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}
.btn-primary {
  background: #409eff;
  color: #fff;
}
.btn-primary:hover { background: #66b1ff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.8);
  border: 1px solid rgba(255,255,255,0.2);
}
.btn-secondary:hover { background: rgba(255,255,255,0.15); }
.upload-btn { cursor: pointer; display: inline-flex; align-items: center; }
.btn-sm {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  background: rgba(64,158,255,0.15);
  color: #409eff;
  border: 1px solid rgba(64,158,255,0.3);
  cursor: pointer;
  transition: all 0.2s;
}
.btn-sm:hover { background: rgba(64,158,255,0.25); }
.btn-sm.danger {
  background: rgba(245,108,108,0.15);
  color: #f56c6c;
  border-color: rgba(245,108,108,0.3);
}
.btn-sm.danger:hover { background: rgba(245,108,108,0.25); }

/* ======== 台账列表 ======== */
/* 预警分组 */
.warning-group-current {
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid rgba(64, 158, 255, 0.3);
  background: rgba(64, 158, 255, 0.08);
}
.warning-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.warning-group-item {
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(64, 158, 255, 0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.warning-group-item:hover {
  border-color: rgba(64, 158, 255, 0.3);
}
.warning-group-item.expanded {
  border-color: rgba(64, 158, 255, 0.4);
  background: rgba(64, 158, 255, 0.05);
}
.warning-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.warning-group-level {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}
.warning-group-level.warning-blue { background: rgba(64, 158, 255, 0.2); color: #409eff; }
.warning-group-level.warning-yellow { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
.warning-group-level.warning-orange { background: rgba(245, 166, 35, 0.2); color: #f5a623; }
.warning-group-level.warning-red { background: rgba(245, 34, 45, 0.2); color: #f5222d; }
.warning-group-status {
  font-size: 11px;
  font-weight: 600;
}
.warning-group-status.active { color: #67c23a; }
.warning-group-status.ended { color: rgba(255, 255, 255, 0.4); }
.warning-group-count {
  margin-left: auto;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
}
.warning-group-arrow {
  color: rgba(255, 255, 255, 0.4);
  transition: transform 0.2s;
  flex-shrink: 0;
}
.warning-group-arrow.open {
  transform: rotate(180deg);
}
.warning-group-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
}
.warning-group-records {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(64, 158, 255, 0.1);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ledger-list { display: flex; flex-direction: column; gap: 10px; }
.ledger-item {
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.ledger-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.ledger-type {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}
.ledger-type.warning { background: rgba(230,162,60,0.2); color: #e6a23c; }
.ledger-type.dispatch { background: rgba(64,158,255,0.2); color: #409eff; }
.ledger-type.personnel { background: rgba(230,162,60,0.2); color: #e6a23c; }
.ledger-type.traffic { background: rgba(245,108,108,0.2); color: #f56c6c; }
.ledger-type.call { background: rgba(103,194,58,0.2); color: #67c23a; }
.ledger-type.inspect { background: rgba(144,147,153,0.2); color: #909399; }
.ledger-time { font-size: 12px; color: rgba(255,255,255,0.4); }
.ledger-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.ledger-content { font-size: 13px; color: rgba(255,255,255,0.7); margin-bottom: 6px; }
.ledger-footer {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: rgba(255,255,255,0.4);
}
.ledger-images {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.ledger-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid rgba(64,158,255,0.2);
}
.image-preview {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.preview-item {
  position: relative;
  width: 60px;
  height: 60px;
}
.preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid rgba(64,158,255,0.2);
}
.remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f56c6c;
  color: #fff;
  border: none;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ======== 排班列表 ======== */
.shift-list { display: flex; flex-direction: column; gap: 8px; }
.shift-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.shift-date {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  white-space: nowrap;
}
.shift-name {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(64,158,255,0.15);
  color: #409eff;
}
.shift-persons {
  font-size: 13px;
  color: rgba(255,255,255,0.7);
}
.shift-divider { margin: 0 4px; color: rgba(255,255,255,0.3); }

/* ======== 积水点列表 ======== */
.point-list { display: flex; flex-direction: column; gap: 4px; }
.point-item {
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.point-item-compact {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.15s;
}
.point-item-compact:hover {
  background: rgba(64,158,255,0.1);
  border-color: rgba(64,158,255,0.3);
}
.point-item-compact .point-header { margin-bottom: 0; }
.point-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.point-name { font-size: 14px; font-weight: 600; }
.point-road-type {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}
.point-monitor-label {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin-right: 4px;
}
.point-monitor-tag {
  display: inline-block;
  padding: 1px 6px;
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
  border-radius: 4px;
  font-size: 11px;
  margin-right: 4px;
}
.point-level {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}
.point-level.level-normal { background: rgba(103,194,58,0.2); color: #67c23a; }
.point-level.level-shallow { background: rgba(64,158,255,0.2); color: #409eff; }
.point-level.level-medium { background: rgba(230,162,60,0.2); color: #e6a23c; }
.point-level.level-deep { background: rgba(245,108,108,0.2); color: #f56c6c; }
.point-level.level-severe { background: rgba(245,34,45,0.2); color: #f5222d; }
.point-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 8px;
}
.point-actions {
  display: flex;
  gap: 6px;
}

/* ======== 应急预案 ======== */
.plan-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.plan-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background: rgba(0,0,0,0.2);
  border-radius: 6px;
}
.plan-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.plan-info svg { color: #409eff; flex-shrink: 0; }
.plan-name {
  font-size: 12px;
  color: rgba(255,255,255,0.8);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.plan-name:hover { color: #409eff; }
.plan-size {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
  white-space: nowrap;
}
.plan-upload-btn {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  background: rgba(64,158,255,0.15);
  color: #409eff;
  border: 1px solid rgba(64,158,255,0.3);
  cursor: pointer;
  transition: all 0.2s;
}
.plan-upload-btn:hover { background: rgba(64,158,255,0.25); }
.empty-hint {
  font-size: 12px;
  color: rgba(255,255,255,0.4);
  padding: 8px 0;
}
.plan-list-full {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.plan-item-full {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.plan-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(64,158,255,0.1);
  border-radius: 8px;
  color: #409eff;
  flex-shrink: 0;
}
.plan-detail {
  flex: 1;
  min-width: 0;
}
.plan-filename {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,0.9);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.plan-filename:hover { color: #409eff; }
.plan-meta {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}

/* ======== 应急物资 ======== */
.supply-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.supply-item {
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
}
.supply-header {
  margin-bottom: 6px;
}
.supply-name {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
}
.supply-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 6px;
}
.supply-items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.supply-tag {
  padding: 2px 8px;
  background: rgba(245,166,35,0.15);
  color: #f5a623;
  border-radius: 4px;
  font-size: 11px;
}

/* ======== 空状态 ======== */
/* 报告选择弹窗 */
.report-select-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(64,158,255,0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 8px;
}
.report-select-item:hover {
  border-color: rgba(64,158,255,0.4);
  background: rgba(64,158,255,0.05);
}
.report-select-item.active {
  border-color: rgba(245,34,45,0.3);
  background: rgba(245,34,45,0.05);
}
.report-select-level {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.report-select-status {
  font-size: 11px;
  font-weight: 600;
}
.report-select-status.active { color: #67c23a; }
.report-select-status.ended { color: rgba(255,255,255,0.4); }
.report-select-time {
  margin-left: auto;
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  white-space: nowrap;
}
.empty-state {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: rgba(255,255,255,0.4);
}

/* ======== 动画 ======== */
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.3s; }
.drawer-enter-active .drawer-panel, .drawer-leave-active .drawer-panel { transition: transform 0.3s; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-panel, .drawer-leave-to .drawer-panel { transform: translateX(100%); }

.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel { transition: transform 0.2s, opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: scale(0.95); opacity: 0; }
</style>
