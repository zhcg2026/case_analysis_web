<template>
  <div class="ledger-page">
    <div class="page-header">
      <h2>台账管理</h2>
    </div>

    <el-tabs v-model="activeTab" @tab-click="handleTabChange">
      <!-- 运维台账 -->
      <el-tab-pane label="运维台账" name="maintenance">
        <div class="tab-content">
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
      </el-tab-pane>

      <!-- 会议台账 -->
      <el-tab-pane label="会议台账" name="meeting">
        <div class="tab-content">
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
      </el-tab-pane>

      <!-- 培训台账 -->
      <el-tab-pane label="培训台账" name="training">
        <div class="tab-content">
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
      </el-tab-pane>
    </el-tabs>

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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import axios from 'axios'

const activeTab = ref('maintenance')

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
  images: []
})

const DETAIL_TITLES = {
  maintenance: '运维记录详情',
  meeting: '会议记录详情',
  training: '培训记录详情'
}

function openDetail(type, row) {
  detail.type = type
  detail.title = DETAIL_TITLES[type] || '详情'
  detail.data = { ...row }
  detail.images = (type === 'meeting' || type === 'training') ? parseImageList(row.images) : []
  detail.visible = true
}

// 运维台账
const maintenance = reactive({
  data: [],
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
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

// Tab切换
function handleTabChange(tab) {
  const name = tab.props.name || activeTab.value
  if (name === 'meeting' && meeting.data.length === 0 && !meeting.loaded) {
    loadMeeting()
    meeting.loaded = true
  } else if (name === 'training' && training.data.length === 0 && !training.loaded) {
    loadTraining()
    training.loaded = true
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
  loadMaintenance()
})
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
