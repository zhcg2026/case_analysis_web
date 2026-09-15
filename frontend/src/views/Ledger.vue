<template>
  <div class="ledger-page">
    <div class="page-header">
      <h2>{{ pageTitle }}</h2>
    </div>

    <div class="tab-content">
    <!-- 运维台账 -->
    <div v-show="activeTab === 'maintenance'">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-input v-model="maintenance.search" placeholder="搜索标题/提报人/处理人" clearable style="width: 250px" @keyup.enter="loadMaintenance">
                <template #append>
                  <el-button @click="loadMaintenance">
                    <el-icon><Search /></el-icon>
                  </el-button>
                </template>
              </el-input>
              <el-select v-model="maintenance.filters.status" placeholder="状态" clearable style="width: 120px" @change="loadMaintenance">
                <el-option label="待处理" value="待处理" />
                <el-option label="处理中" value="处理中" />
                <el-option label="已解决" value="已解决" />
              </el-select>
              <el-select v-model="maintenance.filters.fault_level" placeholder="故障等级" clearable style="width: 120px" @change="loadMaintenance">
                <el-option label="低" value="低" />
                <el-option label="中" value="中" />
                <el-option label="高" value="高" />
                <el-option label="紧急" value="紧急" />
              </el-select>
            </div>
            <el-button type="primary" @click="openMaintenanceDialog()">
              <el-icon><Plus /></el-icon> 新增记录
            </el-button>
          </div>

          <el-table :data="maintenance.data" v-loading="maintenance.loading" border stripe>
            <el-table-column prop="title" label="故障标题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="fault_level" label="等级" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getFaultLevelType(row.fault_level)" size="small">{{ row.fault_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reporter" label="提报人" width="80" align="center" />
            <el-table-column prop="assignee" label="处理人" width="80" align="center" />
            <el-table-column prop="reported_at" label="提报时间" width="160" align="center" />
            <el-table-column prop="resolved_at" label="解决时间" width="160" align="center" />
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail('maintenance', row)">查看</el-button>
                <el-button type="primary" link size="small" @click="openMaintenanceDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该记录？" @confirm="deleteMaintenance(row.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="maintenance.page"
            v-model:page-size="maintenance.pageSize"
            :total="maintenance.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadMaintenance"
            @current-change="loadMaintenance"
          />
    </div>

    <!-- 会议台账 -->
    <div v-show="activeTab === 'meeting'">
      <div class="toolbar">
            <div class="toolbar-left">
              <el-input v-model="meeting.search" placeholder="搜索主题/主持人/参会人" clearable style="width: 250px" @keyup.enter="loadMeeting">
                <template #append>
                  <el-button @click="loadMeeting">
                    <el-icon><Search /></el-icon>
                  </el-button>
                </template>
              </el-input>
            </div>
            <el-button type="primary" @click="openMeetingDialog()">
              <el-icon><Plus /></el-icon> 新增记录
            </el-button>
          </div>

          <el-table :data="meeting.data" v-loading="meeting.loading" border stripe>
            <el-table-column prop="meeting_time" label="会议时间" width="160" align="center" />
            <el-table-column prop="title" label="会议主题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="location" label="地点" width="120" show-overflow-tooltip />
            <el-table-column prop="attendees" label="参会人员" min-width="150" show-overflow-tooltip />
            <el-table-column prop="host" label="主持人" width="80" align="center" />
            <el-table-column label="照片" width="100" align="center">
              <template #default="{ row }">
                <template v-if="row.images">
                  <div class="thumb-list">
                    <img
                      v-for="(img, idx) in parseImageList(row.images).slice(0, 2)"
                      :key="idx"
                      :src="img"
                      class="thumb-img"
                      @click="openImagePreview(parseImageList(row.images), idx)"
                    />
                    <span v-if="parseImageList(row.images).length > 2" class="thumb-more">+{{ parseImageList(row.images).length - 2 }}</span>
                  </div>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail('meeting', row)">查看</el-button>
                <el-button type="primary" link size="small" @click="openMeetingDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该记录？" @confirm="deleteMeeting(row.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="meeting.page"
            v-model:page-size="meeting.pageSize"
            :total="meeting.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadMeeting"
        @current-change="loadMeeting"
      />
    </div>

    <!-- 培训台账 -->
    <div v-show="activeTab === 'training'">
      <div class="toolbar">
            <div class="toolbar-left">
              <el-input v-model="training.search" placeholder="搜索主题/培训人/参训人员" clearable style="width: 250px" @keyup.enter="loadTraining">
                <template #append>
                  <el-button @click="loadTraining">
                    <el-icon><Search /></el-icon>
                  </el-button>
                </template>
              </el-input>
            </div>
            <el-button type="primary" @click="openTrainingDialog()">
              <el-icon><Plus /></el-icon> 新增记录
            </el-button>
          </div>

          <el-table :data="training.data" v-loading="training.loading" border stripe>
            <el-table-column prop="training_time" label="培训时间" width="160" align="center" />
            <el-table-column prop="title" label="培训主题" min-width="150" show-overflow-tooltip />
            <el-table-column prop="location" label="地点" width="120" show-overflow-tooltip />
            <el-table-column prop="attendees" label="培训人员" min-width="150" show-overflow-tooltip />
            <el-table-column prop="trainer" label="培训人" width="80" align="center" />
            <el-table-column label="照片" width="100" align="center">
              <template #default="{ row }">
                <template v-if="row.images">
                  <div class="thumb-list">
                    <img
                      v-for="(img, idx) in parseImageList(row.images).slice(0, 2)"
                      :key="idx"
                      :src="img"
                      class="thumb-img"
                      @click="openImagePreview(parseImageList(row.images), idx)"
                    />
                    <span v-if="parseImageList(row.images).length > 2" class="thumb-more">+{{ parseImageList(row.images).length - 2 }}</span>
                  </div>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail('training', row)">查看</el-button>
                <el-button type="primary" link size="small" @click="openTrainingDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该记录？" @confirm="deleteTraining(row.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="training.page"
            v-model:page-size="training.pageSize"
            :total="training.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadTraining"
        @current-change="loadTraining"
      />
    </div>

    <!-- 文件资料 -->
    <div v-show="activeTab === 'docs'">
      <div class="toolbar">
            <div class="toolbar-left">
              <el-input v-model="docs.search" placeholder="搜索标题/发文单位/说明" clearable style="width: 250px" @keyup.enter="loadDocs">
                <template #append>
                  <el-button @click="loadDocs">
                    <el-icon><Search /></el-icon>
                  </el-button>
                </template>
              </el-input>
              <el-select v-model="docs.tagFilter" placeholder="类型" clearable style="width: 140px" @change="loadDocs">
                <el-option v-for="t in docsTagOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </div>
            <el-button type="primary" @click="openDocsDialog()">
              <el-icon><Plus /></el-icon> 添加文件
            </el-button>
          </div>

          <el-table :data="docs.data" v-loading="docs.loading" border stripe>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag v-if="row.pinned" type="danger" size="small" style="margin-right: 6px">置顶</el-tag>
                {{ row.title }}
              </template>
            </el-table-column>
            <el-table-column prop="tag" label="类型" width="110" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.tag" type="warning" size="small">{{ row.tag }}</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="source" label="发文单位" width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.source || '-' }}</template>
            </el-table-column>
            <el-table-column prop="doc_date" label="文件日期" width="110" align="center">
              <template #default="{ row }">{{ row.doc_date || '-' }}</template>
            </el-table-column>
            <el-table-column prop="content" label="说明" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.content || '-' }}</template>
            </el-table-column>
            <el-table-column label="附件" width="80" align="center">
              <template #default="{ row }">
                <el-badge :value="row.attachments.length" type="primary" v-if="row.attachments.length">
                  <el-button type="primary" link size="small" @click="openDetail('docs', row)">查看</el-button>
                </el-badge>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail('docs', row)">查看</el-button>
                <el-button type="primary" link size="small" @click="openDocsDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该文件资料？" @confirm="deleteDocs(row.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="docs.page"
            v-model:page-size="docs.pageSize"
            :total="docs.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
      @size-change="loadDocs"
      @current-change="loadDocs"
      />
    </div>

    <!-- 外单位调取监控 -->
    <div v-show="activeTab === 'monitor'">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="monitor.search" placeholder="搜索单位/来访人/事由/点位" clearable style="width: 250px" @keyup.enter="loadMonitor">
            <template #append>
              <el-button @click="loadMonitor"><el-icon><Search /></el-icon></el-button>
            </template>
          </el-input>
          <el-select v-model="monitor.filters.status" placeholder="状态" clearable style="width: 120px" @change="loadMonitor">
            <el-option label="接待中" value="接待中" />
            <el-option label="申请中" value="申请中" />
            <el-option label="已调取" value="已调取" />
            <el-option label="已归档" value="已归档" />
          </el-select>
        </div>
        <el-button type="primary" @click="openMonitorDialog()"><el-icon><Plus /></el-icon> 新增登记</el-button>
      </div>
      <el-table :data="monitor.data" v-loading="monitor.loading" border stripe>
        <el-table-column prop="visit_time" label="来访时间" width="150" align="center" />
        <el-table-column prop="unit_name" label="外单位" min-width="120" show-overflow-tooltip />
        <el-table-column prop="visitor_name" label="来访人" width="80" align="center" />
        <el-table-column label="证件" width="100" align="center">
          <template #default="{ row }">{{ row.id_type || '-' }}<span v-if="row.id_no" style="opacity:.7">·{{ row.id_no }}</span></template>
        </el-table-column>
        <el-table-column label="介绍信" width="70" align="center">
          <template #default="{ row }"><el-tag size="small" :type="row.has_intro_letter ? 'success' : 'info'">{{ row.has_intro_letter ? '有' : '无' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="申请表" width="70" align="center">
          <template #default="{ row }"><el-tag size="small" :type="row.has_application ? 'success' : 'info'">{{ row.has_application ? '已填' : '未填' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="领导签字" width="80" align="center">
          <template #default="{ row }"><el-tag size="small" :type="row.leader_signed ? 'success' : 'info'">{{ row.leader_signed ? '已签' : '未签' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="video_location" label="点位" min-width="100" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" align="center" />
        <el-table-column prop="operator" label="经办人" width="80" align="center" />
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openMonitorDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除？" @confirm="deleteMonitor(row.id)">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="monitor.page" v-model:page-size="monitor.pageSize" :total="monitor.total"
        :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadMonitor" @current-change="loadMonitor"
      />
    </div>

    <!-- 无人机飞行登记 -->
    <div v-show="activeTab === 'drone'">
      <el-card shadow="never" class="drone-equip-card" style="margin-bottom:12px">
        <div class="drone-equip">
          <span class="equip-label">设备信息</span>
          <span>型号：<b>{{ drone.equip.model || '未设置' }}</b></span>
          <span>保管人：<b>{{ drone.equip.keeper || '未设置' }}</b></span>
          <el-button v-if="!drone.equipEditing" type="primary" link size="small" @click="drone.equipEditing = true">编辑设备</el-button>
          <template v-else>
            <el-input v-model="drone.equipDraft.model" style="width:160px" placeholder="无人机型号" size="small" />
            <el-input v-model="drone.equipDraft.keeper" style="width:120px" placeholder="保管人员" size="small" />
            <el-button type="primary" size="small" @click="saveDroneEquip">保存</el-button>
            <el-button size="small" @click="drone.equipEditing = false">取消</el-button>
          </template>
        </div>
      </el-card>
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="drone.search" placeholder="搜索地点/目的/申请人" clearable style="width: 250px" @keyup.enter="loadDrone">
            <template #append>
              <el-button @click="loadDrone"><el-icon><Search /></el-icon></el-button>
            </template>
          </el-input>
          <el-select v-model="drone.filters.status" placeholder="状态" clearable style="width: 120px" @change="loadDrone">
            <el-option label="待批准" value="待批准" />
            <el-option label="已批准" value="已批准" />
            <el-option label="已完成" value="已完成" />
            <el-option label="已取消" value="已取消" />
          </el-select>
        </div>
        <el-button type="primary" @click="openDroneDialog()"><el-icon><Plus /></el-icon> 新增登记</el-button>
      </div>
      <el-table :data="drone.data" v-loading="drone.loading" border stripe>
        <el-table-column prop="flight_date" label="飞行日期" width="110" align="center" />
        <el-table-column prop="location" label="飞行地点" min-width="120" show-overflow-tooltip />
        <el-table-column prop="purpose" label="飞行目的" min-width="140" show-overflow-tooltip />
        <el-table-column label="飞行时间" width="180" align="center">
          <template #default="{ row }">{{ fmtRange(row.start_time, row.end_time) }}</template>
        </el-table-column>
        <el-table-column prop="applicant" label="申请人" width="80" align="center" />
        <el-table-column prop="approver" label="批准领导" width="90" align="center" />
        <el-table-column prop="drone_model" label="型号" width="100" show-overflow-tooltip />
        <el-table-column prop="keeper" label="保管人" width="80" align="center" />
        <el-table-column prop="status" label="状态" width="90" align="center" />
        <el-table-column label="操作" width="150" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openDroneDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除？" @confirm="deleteDrone(row.id)">
              <template #reference><el-button type="danger" link size="small">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="drone.page" v-model:page-size="drone.pageSize" :total="drone.total"
        :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadDrone" @current-change="loadDrone"
      />
    </div>
    </div>

    <!-- 调监控弹窗 -->
    <el-dialog v-model="monitor.dialogVisible" :title="monitor.editId ? '编辑调监控登记' : '新增调监控登记'" width="620px">
      <el-form :model="monitor.form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="外单位" required><el-input v-model="monitor.form.unit_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来访人" required><el-input v-model="monitor.form.visitor_name" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="证件类型"><el-input v-model="monitor.form.id_type" placeholder="如：警官证" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="证件号"><el-input v-model="monitor.form.id_no" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="持介绍信"><el-switch v-model="monitor.form.has_intro_letter" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="已填申请"><el-switch v-model="monitor.form.has_application" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="领导签字"><el-switch v-model="monitor.form.leader_signed" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="来访时间"><el-date-picker v-model="monitor.form.visit_time" type="datetime" style="width:100%" value-format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
        <el-form-item label="调取事由"><el-input v-model="monitor.form.purpose" type="textarea" :rows="2" placeholder="关联事项/案件说明" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="监控点位"><el-input v-model="monitor.form.video_location" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="监控时段"><el-input v-model="monitor.form.video_time_range" placeholder="如：2026-09-01 10:00-12:00" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="经办人"><el-input v-model="monitor.form.operator" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="monitor.form.status" style="width:100%">
                <el-option label="接待中" value="接待中" />
                <el-option label="申请中" value="申请中" />
                <el-option label="已调取" value="已调取" />
                <el-option label="已归档" value="已归档" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注"><el-input v-model="monitor.form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="monitor.dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="monitor.saving" @click="saveMonitor">保存</el-button>
      </template>
    </el-dialog>

    <!-- 无人机弹窗 -->
    <el-dialog v-model="drone.dialogVisible" :title="drone.editId ? '编辑飞行登记' : '新增飞行登记'" width="620px">
      <el-form :model="drone.form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="飞行日期" required><el-date-picker v-model="drone.form.flight_date" type="date" style="width:100%" value-format="YYYY-MM-DD" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="drone.form.status" style="width:100%">
                <el-option label="待批准" value="待批准" />
                <el-option label="已批准" value="已批准" />
                <el-option label="已完成" value="已完成" />
                <el-option label="已取消" value="已取消" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="飞行地点" required><el-input v-model="drone.form.location" /></el-form-item>
        <el-form-item label="飞行目的" required><el-input v-model="drone.form.purpose" type="textarea" :rows="2" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始时间"><el-date-picker v-model="drone.form.start_time" type="datetime" style="width:100%" value-format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间"><el-date-picker v-model="drone.form.end_time" type="datetime" style="width:100%" value-format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="申请人"><el-input v-model="drone.form.applicant" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="批准领导"><el-input v-model="drone.form.approver" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="无人机型号"><el-input v-model="drone.form.drone_model" :placeholder="drone.equip.model || '默认用设备信息'" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保管人员"><el-input v-model="drone.form.keeper" :placeholder="drone.equip.keeper || '默认用设备信息'" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注"><el-input v-model="drone.form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drone.dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="drone.saving" @click="saveDrone">保存</el-button>
      </template>
    </el-dialog>

    <!-- 运维台账弹窗 -->
    <el-dialog v-model="maintenance.dialogVisible" :title="maintenance.editId ? '编辑运维记录' : '新增运维记录'" width="600px">
      <el-form :model="maintenance.form" label-width="80px">
        <el-form-item label="故障标题" required>
          <el-input v-model="maintenance.form.title" placeholder="请输入故障标题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="故障等级">
              <el-select v-model="maintenance.form.fault_level" style="width: 100%">
                <el-option label="低" value="低" />
                <el-option label="中" value="中" />
                <el-option label="高" value="高" />
                <el-option label="紧急" value="紧急" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="maintenance.form.status" style="width: 100%">
                <el-option label="待处理" value="待处理" />
                <el-option label="处理中" value="处理中" />
                <el-option label="已解决" value="已解决" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="提报人" required>
              <el-input v-model="maintenance.form.reporter" placeholder="请输入提报人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="处理人">
              <el-input v-model="maintenance.form.assignee" placeholder="请输入处理人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="问题描述">
          <el-input v-model="maintenance.form.description" type="textarea" :rows="3" placeholder="请输入问题描述" />
        </el-form-item>
        <el-form-item label="解决方案">
          <el-input v-model="maintenance.form.solution" type="textarea" :rows="3" placeholder="请输入解决方案" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="提报时间">
              <el-date-picker v-model="maintenance.form.reported_at" type="datetime" placeholder="选择时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决时间">
              <el-date-picker v-model="maintenance.form.resolved_at" type="datetime" placeholder="选择时间" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="maintenance.dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMaintenance" :loading="maintenance.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 会议台账弹窗 -->
    <el-dialog v-model="meeting.dialogVisible" :title="meeting.editId ? '编辑会议记录' : '新增会议记录'" width="600px">
      <el-form :model="meeting.form" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="会议时间" required>
              <el-date-picker v-model="meeting.form.meeting_time" type="datetime" placeholder="选择时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="会议主题" required>
              <el-input v-model="meeting.form.title" placeholder="请输入会议主题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="会议地点">
              <el-input v-model="meeting.form.location" placeholder="请输入地点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主持人">
              <el-input v-model="meeting.form.host" placeholder="请输入主持人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="参会人员">
          <el-input v-model="meeting.form.attendees" placeholder="请输入参会人员，多人用逗号分隔" />
        </el-form-item>
        <el-form-item label="会议纪要">
          <el-input v-model="meeting.form.minutes" type="textarea" :rows="4" placeholder="请输入会议纪要" />
        </el-form-item>
        <el-form-item label="会议照片">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="(res) => handleUploadSuccess(res, 'meeting')"
            :file-list="meeting.fileList"
            list-type="picture-card"
            :limit="9"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="meeting.dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMeeting" :loading="meeting.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 培训台账弹窗 -->
    <el-dialog v-model="training.dialogVisible" :title="training.editId ? '编辑培训记录' : '新增培训记录'" width="600px">
      <el-form :model="training.form" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="培训时间" required>
              <el-date-picker v-model="training.form.training_time" type="datetime" placeholder="选择时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="培训主题" required>
              <el-input v-model="training.form.title" placeholder="请输入培训主题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="培训地点">
              <el-input v-model="training.form.location" placeholder="请输入地点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="培训人" required>
              <el-input v-model="training.form.trainer" placeholder="请输入培训人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="培训人员">
          <el-input v-model="training.form.attendees" placeholder="请输入参训人员，多人用逗号分隔" />
        </el-form-item>
        <el-form-item label="培训内容">
          <el-input v-model="training.form.content" type="textarea" :rows="4" placeholder="请输入培训内容" />
        </el-form-item>
        <el-form-item label="培训照片">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :on-success="(res) => handleUploadSuccess(res, 'training')"
            :file-list="training.fileList"
            list-type="picture-card"
            :limit="9"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="training.dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTraining" :loading="training.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 文件资料弹窗 -->
    <el-dialog v-model="docs.dialogVisible" :title="docs.editId ? '编辑文件资料' : '添加文件资料'" width="600px">
      <el-form :model="docs.form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="docs.form.title" placeholder="如：关于某某事项不考核的通知" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="docs.form.tag" filterable allow-create default-first-option clearable placeholder="选择或输入" style="width: 100%">
                <el-option v-for="t in docTagPresets" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发文单位">
              <el-input v-model="docs.form.source" placeholder="如：市城管局" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="文件日期">
              <el-date-picker v-model="docs.form.doc_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="置顶">
              <el-switch v-model="docs.form.pinned" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="docs.form.content" type="textarea" :rows="3" placeholder="文件要点说明，如：某某路段开挖施工，暂不采集" />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            :action="uploadFileUrl"
            :headers="uploadHeaders"
            multiple
            v-model:file-list="docs.uploadFiles"
            :on-success="handleDocUploadSuccess"
            :on-remove="handleDocUploadRemove"
          >
            <el-button type="primary" plain>选择文件上传</el-button>
            <template #tip>
              <div class="el-upload__tip">支持文档/表格/图片/压缩包，可多选</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="docs.dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDocs" :loading="docs.saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情弹窗 -->
    <el-dialog v-model="detail.visible" :title="detail.title" width="650px" top="6vh">
      <div class="detail-content" v-if="detail.data">
        <!-- 运维台账详情 -->
        <template v-if="detail.type === 'maintenance'">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="故障标题" :span="2">{{ detail.data.title }}</el-descriptions-item>
            <el-descriptions-item label="故障等级">
              <el-tag :type="getFaultLevelType(detail.data.fault_level)" size="small">{{ detail.data.fault_level }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(detail.data.status)" size="small">{{ detail.data.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="提报人">{{ detail.data.reporter }}</el-descriptions-item>
            <el-descriptions-item label="处理人">{{ detail.data.assignee || '-' }}</el-descriptions-item>
            <el-descriptions-item label="提报时间" :span="2">{{ detail.data.reported_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="解决时间" :span="2">{{ detail.data.resolved_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="问题描述" :span="2">
              <div class="detail-text">{{ detail.data.description || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="解决方案" :span="2">
              <div class="detail-text">{{ detail.data.solution || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">
              <div class="detail-text">{{ detail.data.notes || '-' }}</div>
            </el-descriptions-item>
          </el-descriptions>
        </template>
        <!-- 会议台账详情 -->
        <template v-if="detail.type === 'meeting'">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="会议主题" :span="2">{{ detail.data.title }}</el-descriptions-item>
            <el-descriptions-item label="会议时间" :span="2">{{ detail.data.meeting_time }}</el-descriptions-item>
            <el-descriptions-item label="会议地点">{{ detail.data.location || '-' }}</el-descriptions-item>
            <el-descriptions-item label="主持人">{{ detail.data.host || '-' }}</el-descriptions-item>
            <el-descriptions-item label="参会人员" :span="2">{{ detail.data.attendees || '-' }}</el-descriptions-item>
            <el-descriptions-item label="会议纪要" :span="2">
              <div class="detail-text">{{ detail.data.minutes || '-' }}</div>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="detail.images.length" class="detail-images">
            <div class="detail-images-label">会议照片</div>
            <div class="detail-images-grid">
              <img v-for="(img, idx) in detail.images" :key="idx" :src="img" class="detail-img" @click="openImagePreview(detail.images, idx)" />
            </div>
          </div>
        </template>
        <!-- 培训台账详情 -->
        <template v-if="detail.type === 'training'">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="培训主题" :span="2">{{ detail.data.title }}</el-descriptions-item>
            <el-descriptions-item label="培训时间" :span="2">{{ detail.data.training_time }}</el-descriptions-item>
            <el-descriptions-item label="培训地点">{{ detail.data.location || '-' }}</el-descriptions-item>
            <el-descriptions-item label="培训人">{{ detail.data.trainer }}</el-descriptions-item>
            <el-descriptions-item label="培训人员" :span="2">{{ detail.data.attendees || '-' }}</el-descriptions-item>
            <el-descriptions-item label="培训内容" :span="2">
              <div class="detail-text">{{ detail.data.content || '-' }}</div>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="detail.images.length" class="detail-images">
            <div class="detail-images-label">培训照片</div>
            <div class="detail-images-grid">
              <img v-for="(img, idx) in detail.images" :key="idx" :src="img" class="detail-img" @click="openImagePreview(detail.images, idx)" />
            </div>
          </div>
        </template>
        <!-- 文件资料详情 -->
        <template v-if="detail.type === 'docs'">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="标题" :span="2">{{ detail.data.title }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ detail.data.tag || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发文单位">{{ detail.data.source || '-' }}</el-descriptions-item>
            <el-descriptions-item label="文件日期">{{ detail.data.doc_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">
              <div class="detail-text">{{ detail.data.content || '-' }}</div>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="detail.attachments.length" class="detail-images">
            <div class="detail-images-label">附件下载</div>
            <div class="detail-attachments">
              <a v-for="(att, idx) in detail.attachments" :key="idx" :href="att.path" target="_blank" class="detail-att-link">
                {{ att.name }}
              </a>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="detail.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 图片预览弹窗 -->
    <div v-if="imagePreview.visible" class="image-preview-overlay" @click="closeImagePreview">
      <div class="image-preview-container" @click.stop>
        <button class="preview-close" @click="closeImagePreview">&times;</button>
        <button v-if="imagePreview.images.length > 1" class="preview-prev" @click="prevImage">&#8249;</button>
        <img :src="imagePreview.images[imagePreview.index]" class="preview-main-img" />
        <button v-if="imagePreview.images.length > 1" class="preview-next" @click="nextImage">&#8250;</button>
        <div class="preview-counter">{{ imagePreview.index + 1 }} / {{ imagePreview.images.length }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import axios from 'axios'

const route = useRoute()

const TAB_TITLES = {
  maintenance: '运维台账',
  meeting: '会议台账',
  training: '培训台账',
  docs: '文件资料',
  monitor: '调取监控',
  drone: '无人机飞行'
}

const activeTab = computed(() => {
  const tab = route.params.tab
  return TAB_TITLES[tab] ? tab : 'maintenance'
})

const pageTitle = computed(() => TAB_TITLES[activeTab.value])

function ensureTabLoaded(tab) {
  if (tab === 'maintenance' && maintenance.data.length === 0 && !maintenance.loaded) {
    loadMaintenance()
    maintenance.loaded = true
  } else if (tab === 'meeting' && meeting.data.length === 0 && !meeting.loaded) {
    loadMeeting()
    meeting.loaded = true
  } else if (tab === 'training' && training.data.length === 0 && !training.loaded) {
    loadTraining()
    training.loaded = true
  } else if (tab === 'docs' && !docs.loaded) {
    loadDocs()
    docs.loaded = true
  } else if (tab === 'monitor' && !monitor.loaded) {
    loadMonitor()
    monitor.loaded = true
  } else if (tab === 'drone' && !drone.loaded) {
    loadDrone()
    loadDroneEquip()
    drone.loaded = true
  }
}

// ===== 调取监控台账 =====
const monitor = reactive({
  data: [], total: 0, page: 1, pageSize: 20, loading: false, loaded: false,
  search: '', filters: { status: '' },
  dialogVisible: false, editId: null, saving: false,
  form: emptyMonitorForm()
})

function emptyMonitorForm() {
  return {
    unit_name: '', visitor_name: '', id_type: '', id_no: '',
    has_intro_letter: false, has_application: false, leader_signed: false,
    visit_time: null, purpose: '', video_location: '', video_time_range: '',
    operator: '', status: '接待中', notes: ''
  }
}

async function loadMonitor() {
  monitor.loading = true
  try {
    const { data } = await axios.get('/api/ledger/monitor-access', {
      params: { page: monitor.page, pageSize: monitor.pageSize, keyword: monitor.search, status: monitor.filters.status }
    })
    monitor.data = data.data || []
    monitor.total = data.total || 0
  } catch (e) {
    ElMessage.error('加载调监控台账失败')
  } finally {
    monitor.loading = false
  }
}

function openMonitorDialog(row = null) {
  if (row) {
    monitor.editId = row.id
    monitor.form = {
      unit_name: row.unit_name || '',
      visitor_name: row.visitor_name || '',
      id_type: row.id_type || '',
      id_no: row.id_no || '',
      has_intro_letter: !!row.has_intro_letter,
      has_application: !!row.has_application,
      leader_signed: !!row.leader_signed,
      visit_time: row.visit_time,
      purpose: row.purpose || '',
      video_location: row.video_location || '',
      video_time_range: row.video_time_range || '',
      operator: row.operator || '',
      status: row.status || '接待中',
      notes: row.notes || ''
    }
  } else {
    monitor.editId = null
    monitor.form = emptyMonitorForm()
  }
  monitor.dialogVisible = true
}

async function saveMonitor() {
  if (!monitor.form.unit_name.trim() || !monitor.form.visitor_name.trim()) {
    ElMessage.warning('请填写外单位与来访人')
    return
  }
  monitor.saving = true
  try {
    const payload = { ...monitor.form }
    if (monitor.editId) {
      await axios.put(`/api/ledger/monitor-access/${monitor.editId}`, payload)
    } else {
      await axios.post('/api/ledger/monitor-access', payload)
    }
    ElMessage.success('保存成功')
    monitor.dialogVisible = false
    await loadMonitor()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    monitor.saving = false
  }
}

async function deleteMonitor(id) {
  try {
    await axios.delete(`/api/ledger/monitor-access/${id}`)
    ElMessage.success('删除成功')
    await loadMonitor()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// ===== 无人机 =====
const drone = reactive({
  data: [], total: 0, page: 1, pageSize: 20, loading: false, loaded: false,
  search: '', filters: { status: '' },
  dialogVisible: false, editId: null, saving: false,
  form: emptyDroneForm(),
  equip: { model: '', keeper: '' },
  equipDraft: { model: '', keeper: '' },
  equipEditing: false
})

function emptyDroneForm() {
  return {
    flight_date: null, location: '', purpose: '',
    start_time: null, end_time: null,
    applicant: '', approver: '', drone_model: '', keeper: '',
    status: '待批准', notes: ''
  }
}

function fmtRange(a, b) {
  if (!a && !b) return '-'
  const t = (s) => (s || '').slice(11, 16)
  if (a && b) return `${t(a)}-${t(b)}`
  return a ? t(a) : t(b)
}

async function loadDrone() {
  drone.loading = true
  try {
    const { data } = await axios.get('/api/ledger/drone', {
      params: { page: drone.page, pageSize: drone.pageSize, keyword: drone.search, status: drone.filters.status }
    })
    drone.data = data.data || []
    drone.total = data.total || 0
  } catch (e) {
    ElMessage.error('加载无人机台账失败')
  } finally {
    drone.loading = false
  }
}

async function loadDroneEquip() {
  try {
    const { data } = await axios.get('/api/ledger/drone-equipment')
    drone.equip.model = data.drone_model || ''
    drone.equip.keeper = data.keeper || ''
    drone.equipDraft = { model: drone.equip.model, keeper: drone.equip.keeper }
  } catch (e) { /* ignore */ }
}

async function saveDroneEquip() {
  try {
    await axios.post('/api/ledger/drone-equipment', {
      drone_model: drone.equipDraft.model,
      drone_keeper: drone.equipDraft.keeper
    })
    ElMessage.success('设备信息已保存')
    drone.equipEditing = false
    await loadDroneEquip()
  } catch (e) {
    ElMessage.error('保存设备信息失败')
  }
}

function openDroneDialog(row = null) {
  if (row) {
    drone.editId = row.id
    drone.form = {
      flight_date: row.flight_date,
      location: row.location || '',
      purpose: row.purpose || '',
      start_time: row.start_time,
      end_time: row.end_time,
      applicant: row.applicant || '',
      approver: row.approver || '',
      drone_model: row.drone_model || '',
      keeper: row.keeper || '',
      status: row.status || '待批准',
      notes: row.notes || ''
    }
  } else {
    drone.editId = null
    drone.form = emptyDroneForm()
  }
  drone.dialogVisible = true
}

async function saveDrone() {
  if (!drone.form.flight_date || !drone.form.location.trim() || !drone.form.purpose.trim()) {
    ElMessage.warning('请填写日期、地点与目的')
    return
  }
  drone.saving = true
  try {
    const payload = { ...drone.form }
    if (drone.editId) {
      await axios.put(`/api/ledger/drone/${drone.editId}`, payload)
    } else {
      await axios.post('/api/ledger/drone', payload)
    }
    ElMessage.success('保存成功')
    drone.dialogVisible = false
    await loadDrone()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    drone.saving = false
  }
}

async function deleteDrone(id) {
  try {
    await axios.delete(`/api/ledger/drone/${id}`)
    ElMessage.success('删除成功')
    await loadDrone()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 上传相关
const uploadUrl = '/api/upload/image'
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))

// 图片预览
const imagePreview = reactive({
  visible: false,
  images: [],
  index: 0
})

function openImagePreview(images, index = 0) {
  imagePreview.images = images
  imagePreview.index = index
  imagePreview.visible = true
}

function closeImagePreview() {
  imagePreview.visible = false
}

function prevImage() {
  imagePreview.index = (imagePreview.index - 1 + imagePreview.images.length) % imagePreview.images.length
}

function nextImage() {
  imagePreview.index = (imagePreview.index + 1) % imagePreview.images.length
}

// 查看详情
const detail = reactive({
  visible: false,
  type: '',
  title: '',
  data: null,
  images: [],
  attachments: []
})

// ===== 文件资料 =====
const uploadFileUrl = '/api/upload/file'
const docTagPresets = ['考核豁免', '采集豁免', '暂不采集', '通知公告', '其他']
const docs = reactive({
  data: [],
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
  loaded: false,
  search: '',
  tagFilter: '',
  dialogVisible: false,
  editId: null,
  saving: false,
  uploadFiles: [],
  form: { title: '', tag: '', source: '', doc_date: null, content: '', pinned: false, attachments: [] }
})

const docsTagOptions = computed(() => {
  const set = new Set([...docTagPresets])
  for (const d of docs.data) if (d.tag) set.add(d.tag)
  return [...set]
})

// 加载文件资料
async function loadDocs() {
  docs.loading = true
  try {
    const { data } = await axios.get('/api/notice-docs', { params: { keyword: docs.search, tag: docs.tagFilter } })
    const all = data.docs || []
    docs.total = all.length
    const start = (docs.page - 1) * docs.pageSize
    docs.data = all.slice(start, start + docs.pageSize)
  } catch (e) {
    ElMessage.error('加载文件资料失败')
  } finally {
    docs.loading = false
  }
}

function openDocsDialog(row = null) {
  if (row) {
    docs.editId = row.id
    docs.form = {
      title: row.title, tag: row.tag || '', source: row.source || '',
      doc_date: row.doc_date || null, content: row.content || '',
      pinned: !!row.pinned, attachments: (row.attachments || []).map(a => ({ ...a }))
    }
    docs.uploadFiles = (row.attachments || []).map(a => ({ name: a.name, url: a.path }))
  } else {
    docs.editId = null
    docs.form = { title: '', tag: '', source: '', doc_date: new Date().toISOString().slice(0, 10), content: '', pinned: false, attachments: [] }
    docs.uploadFiles = []
  }
  docs.dialogVisible = true
}

function handleDocUploadSuccess(res, file) {
  if (res.file_path) {
    docs.form.attachments.push({ name: file.name, path: res.file_path })
  } else {
    ElMessage.error(res.error || '附件上传失败')
  }
}

function handleDocUploadRemove(uploadFile) {
  const p = uploadFile.response?.file_path || uploadFile.url
  docs.form.attachments = docs.form.attachments.filter(a => a.path !== p)
}

async function saveDocs() {
  if (!docs.form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  docs.saving = true
  try {
    const payload = { ...docs.form, pinned: docs.form.pinned ? 1 : 0 }
    if (docs.editId) {
      await axios.put(`/api/notice-docs/${docs.editId}`, payload)
      ElMessage.success('更新成功')
    } else {
      await axios.post('/api/notice-docs', payload)
      ElMessage.success('添加成功')
    }
    docs.dialogVisible = false
    await loadDocs()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    docs.saving = false
  }
}

async function deleteDocs(id) {
  try {
    await axios.delete(`/api/notice-docs/${id}`)
    ElMessage.success('删除成功')
    await loadDocs()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const DETAIL_TITLES = {
  maintenance: '运维记录详情',
  meeting: '会议记录详情',
  training: '培训记录详情',
  docs: '文件资料详情'
}

function openDetail(type, row) {
  detail.type = type
  detail.title = DETAIL_TITLES[type] || '详情'
  detail.data = { ...row }
  detail.images = (type === 'meeting' || type === 'training') ? parseImageList(row.images) : []
  detail.attachments = (type === 'docs' && Array.isArray(row.attachments)) ? row.attachments : []
  detail.visible = true
}

// 运维台账
const maintenance = reactive({
  data: [],
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
  loaded: false,
  search: '',
  filters: { status: '', fault_level: '' },
  dialogVisible: false,
  editId: null,
  saving: false,
  form: { title: '', fault_level: '中', reporter: '', assignee: '', description: '', solution: '', status: '待处理', reported_at: null, resolved_at: null }
})

// 会议台账
const meeting = reactive({
  data: [],
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
  loaded: false,
  search: '',
  dialogVisible: false,
  editId: null,
  saving: false,
  fileList: [],
  form: { meeting_time: null, title: '', location: '', attendees: '', host: '', minutes: '', images: '' }
})

// 培训台账
const training = reactive({
  data: [],
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
  loaded: false,
  search: '',
  dialogVisible: false,
  editId: null,
  saving: false,
  fileList: [],
  form: { training_time: null, title: '', location: '', attendees: '', trainer: '', content: '', images: '' }
})

// 加载运维台账
async function loadMaintenance() {
  maintenance.loading = true
  try {
    const params = {
      page: maintenance.page,
      pageSize: maintenance.pageSize,
      keyword: maintenance.search,
      ...maintenance.filters
    }
    const { data } = await axios.get('/api/ledger/maintenance', { params })
    maintenance.data = data.data
    maintenance.total = data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    maintenance.loading = false
  }
}

// 加载会议台账
async function loadMeeting() {
  meeting.loading = true
  try {
    const params = {
      page: meeting.page,
      pageSize: meeting.pageSize,
      keyword: meeting.search
    }
    const { data } = await axios.get('/api/ledger/meeting', { params })
    meeting.data = data.data
    meeting.total = data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    meeting.loading = false
  }
}

// 加载培训台账
async function loadTraining() {
  training.loading = true
  try {
    const params = {
      page: training.page,
      pageSize: training.pageSize,
      keyword: training.search
    }
    const { data } = await axios.get('/api/ledger/training', { params })
    training.data = data.data
    training.total = data.total
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    training.loading = false
  }
}

// 打开运维弹窗
function openMaintenanceDialog(row = null) {
  if (row) {
    maintenance.editId = row.id
    maintenance.form = { ...row }
  } else {
    maintenance.editId = null
    maintenance.form = { title: '', fault_level: '中', reporter: '', assignee: '', description: '', solution: '', status: '待处理', reported_at: null, resolved_at: null }
  }
  maintenance.dialogVisible = true
}

// 打开会议弹窗
function openMeetingDialog(row = null) {
  if (row) {
    meeting.editId = row.id
    meeting.form = { ...row }
    meeting.fileList = parseImages(row.images)
  } else {
    meeting.editId = null
    meeting.form = { meeting_time: null, title: '', location: '', attendees: '', host: '', minutes: '', images: '' }
    meeting.fileList = []
  }
  meeting.dialogVisible = true
}

// 打开培训弹窗
function openTrainingDialog(row = null) {
  if (row) {
    training.editId = row.id
    training.form = { ...row }
    training.fileList = parseImages(row.images)
  } else {
    training.editId = null
    training.form = { training_time: null, title: '', location: '', attendees: '', trainer: '', content: '', images: '' }
    training.fileList = []
  }
  training.dialogVisible = true
}

// 解析图片JSON
function parseImages(imagesStr) {
  if (!imagesStr) return []
  try {
    const urls = JSON.parse(imagesStr)
    return urls.map(url => ({ name: url, url }))
  } catch {
    return []
  }
}

// 解析图片列表（用于el-image预览）
function parseImageList(imagesStr) {
  if (!imagesStr) return []
  try {
    return JSON.parse(imagesStr)
  } catch {
    return []
  }
}

// 上传成功回调
function handleUploadSuccess(res, type) {
  if (res.success) {
    const form = type === 'meeting' ? meeting.form : training.form
    let images = []
    try {
      images = JSON.parse(form.images || '[]')
    } catch {
      images = []
    }
    images.push(res.url)
    form.images = JSON.stringify(images)
  }
}

// 保存运维台账
async function saveMaintenance() {
  if (!maintenance.form.title || !maintenance.form.reporter) {
    ElMessage.warning('请填写必填项')
    return
  }
  maintenance.saving = true
  try {
    if (maintenance.editId) {
      await axios.put(`/api/ledger/maintenance/${maintenance.editId}`, maintenance.form)
    } else {
      await axios.post('/api/ledger/maintenance', maintenance.form)
    }
    ElMessage.success('保存成功')
    maintenance.dialogVisible = false
    loadMaintenance()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    maintenance.saving = false
  }
}

// 保存会议台账
async function saveMeeting() {
  if (!meeting.form.title || !meeting.form.meeting_time) {
    ElMessage.warning('请填写必填项')
    return
  }
  meeting.saving = true
  try {
    if (meeting.editId) {
      await axios.put(`/api/ledger/meeting/${meeting.editId}`, meeting.form)
    } else {
      await axios.post('/api/ledger/meeting', meeting.form)
    }
    ElMessage.success('保存成功')
    meeting.dialogVisible = false
    loadMeeting()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    meeting.saving = false
  }
}

// 保存培训台账
async function saveTraining() {
  if (!training.form.title || !training.form.trainer || !training.form.training_time) {
    ElMessage.warning('请填写必填项')
    return
  }
  training.saving = true
  try {
    if (training.editId) {
      await axios.put(`/api/ledger/training/${training.editId}`, training.form)
    } else {
      await axios.post('/api/ledger/training', training.form)
    }
    ElMessage.success('保存成功')
    training.dialogVisible = false
    loadTraining()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    training.saving = false
  }
}

// 删除运维台账
async function deleteMaintenance(id) {
  try {
    await axios.delete(`/api/ledger/maintenance/${id}`)
    ElMessage.success('删除成功')
    loadMaintenance()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 删除会议台账
async function deleteMeeting(id) {
  try {
    await axios.delete(`/api/ledger/meeting/${id}`)
    ElMessage.success('删除成功')
    loadMeeting()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 删除培训台账
async function deleteTraining(id) {
  try {
    await axios.delete(`/api/ledger/training/${id}`)
    ElMessage.success('删除成功')
    loadTraining()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 故障等级样式
function getFaultLevelType(level) {
  const map = { '低': 'info', '中': 'warning', '高': 'danger', '紧急': 'danger' }
  return map[level] || 'info'
}

// 状态样式
function getStatusType(status) {
  const map = { '待处理': 'info', '处理中': 'warning', '已解决': 'success' }
  return map[status] || 'info'
}

onMounted(() => {
  ensureTabLoaded(activeTab.value)
})

watch(
  () => route.params.tab,
  (tab) => {
    ensureTabLoaded(TAB_TITLES[tab] ? tab : 'maintenance')
  }
)
</script>

<style scoped>
.ledger-page {
  padding: var(--space-5);
}

.page-header {
  margin-bottom: var(--space-5);
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.tab-content {
  padding-top: var(--space-4);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.toolbar-left {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.el-pagination {
  margin-top: var(--space-4);
  justify-content: flex-end;
}

.thumb-list {
  display: flex;
  gap: 4px;
  align-items: center;
  justify-content: center;
}

.thumb-img {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  cursor: pointer;
  border: 1px solid var(--border-lighter);
  transition: border-color var(--transition-fast);
}

.thumb-img:hover {
  border-color: var(--primary-500);
}

.thumb-more {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 图片预览弹窗 */
.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview-container {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.preview-main-img {
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 4px;
}

.preview-close {
  position: absolute;
  top: -40px;
  right: 0;
  background: none;
  border: none;
  color: white;
  font-size: 32px;
  cursor: pointer;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-close:hover {
  color: #409eff;
}

.preview-prev,
.preview-next {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  font-size: 36px;
  cursor: pointer;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.preview-prev {
  left: -60px;
}

.preview-next {
  right: -60px;
}

.preview-prev:hover,
.preview-next:hover {
  background: rgba(255, 255, 255, 0.4);
}

.preview-counter {
  text-align: center;
  color: white;
  margin-top: 12px;
  font-size: 14px;
}

/* 详情弹窗 */
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: var(--text-regular);
}

.detail-images {
  margin-top: 16px;
}

.detail-images-label {
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.detail-images-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-img {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-lighter);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.detail-img:hover {
  border-color: var(--primary-500);
}
</style>
