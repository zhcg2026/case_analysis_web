<template>
  <div class="cyw-dict-tab">
    <div class="page-header">
      <div>
        <h2>字典管理</h2>
        <p class="page-sub">点位档案 / 责任单位 / 问题类型。派发部门按问题类型的「默认派发部门」带出，登记时可逐单改派。</p>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <!-- 点位档案 -->
      <el-tab-pane label="点位档案" name="spots">
        <div class="toolbar">
          <el-input v-model="spotKeyword" placeholder="监控序号/名称/路段" clearable style="width: 220px"
            @keyup.enter="loadSpots" @clear="loadSpots" />
          <el-button type="primary" @click="loadSpots">查询</el-button>
          <el-button type="primary" @click="openSpotEditor()">添加点位</el-button>
          <el-button @click="importVisible = true">Excel 导入</el-button>
          <el-button link type="primary" @click="downloadTemplate">下载导入模板(CSV)</el-button>
        </div>
        <el-table :data="spots" v-loading="spotsLoading" border stripe>
          <el-table-column prop="monitor_no" label="监控序号" width="90" />
          <el-table-column prop="name" label="点位名称" min-width="130" />
          <el-table-column prop="road" label="所在路段" min-width="95" />
          <el-table-column prop="manage_unit" label="管理单位" width="90" />
          <el-table-column prop="spot_type" label="类型" width="75" />
          <el-table-column prop="camera_source" label="摄像头归属" width="90" />
          <!-- 联系人：按源表格式一条一行全列出（部门/角色 — 姓名 — 电话），不折叠不摘要 -->
          <el-table-column label="联系人" min-width="400">
            <template #default="{ row }">
              <div v-if="row.contacts?.length" class="spot-contacts">
                <div v-for="(c, i) in row.contacts" :key="i" class="contact-line">
                  <span class="contact-dept">{{ c.dept_label || '联系人' }}</span>
                  <span class="contact-person">{{ c.person }}</span>
                  <span class="contact-phone">{{ c.phone }}</span>
                </div>
              </div>
              <span v-else style="color: #c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="坐标" width="150">
            <template #default="{ row }">
              <span v-if="row.lng != null && row.lat != null" class="coord-text">{{ fmtCoord(row) }}</span>
              <span v-else style="color: #c0c4cc">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openSpotEditor(row)">编辑</el-button>
              <el-popconfirm title="删除后不可恢复（已被问题引用的点位不能删除），确认？" @confirm="removeSpot(row)">
                <template #reference><el-button link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination v-model:current-page="spotPage" v-model:page-size="spotPageSize" :total="spotTotal"
            layout="total, sizes, prev, pager, next" :page-sizes="[20, 50, 200]"
            @current-change="loadSpots" @size-change="loadSpots" />
        </div>
      </el-tab-pane>

      <!-- 责任单位 -->
      <el-tab-pane label="责任单位" name="depts">
        <div class="toolbar">
          <el-button type="primary" @click="openDeptEditor()">添加单位</el-button>
        </div>
        <el-table :data="depts" v-loading="deptsLoading" border stripe>
          <el-table-column prop="name" label="单位名称" width="140" />
          <el-table-column prop="contact" label="创文联络员" width="120" />
          <el-table-column prop="phone" label="联系电话" width="140" />
          <el-table-column label="底色" width="120">
            <template #default="{ row }">
              <span class="color-chip" :style="{ background: row.color }"></span>{{ row.color }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDeptEditor(row)">编辑</el-button>
              <el-popconfirm title="已被引用的单位不能删除，确认？" @confirm="removeDept(row)">
                <template #reference><el-button link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 问题类型 -->
      <el-tab-pane label="问题类型" name="types">
        <div class="toolbar">
          <el-button type="primary" @click="openTypeEditor()">添加类型</el-button>
        </div>
        <el-table :data="types" v-loading="typesLoading" border stripe>
          <el-table-column prop="name" label="类型名称" width="140" />
          <el-table-column label="默认派发部门" width="140">
            <template #default="{ row }">
              <span v-if="row.default_dept_name" class="dept-chip" :style="{ borderColor: row.default_dept_color }">
                {{ row.default_dept_name }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTypeEditor(row)">编辑</el-button>
              <el-popconfirm title="已被问题引用的类型不能删除，确认？" @confirm="removeType(row)">
                <template #reference><el-button link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 点位编辑 -->
    <el-dialog v-model="spotDialog.visible" :title="spotDialog.form.id ? '编辑点位' : '添加点位'" width="600px">
      <el-form :model="spotDialog.form" label-width="110px">
        <el-form-item label="监控序号" required>
          <el-input v-model="spotDialog.form.monitor_no" placeholder="监控画面序号，录入时按此检索" />
        </el-form-item>
        <el-form-item label="点位名称" required>
          <el-input v-model="spotDialog.form.name" />
        </el-form-item>
        <el-form-item label="所在路段">
          <el-input v-model="spotDialog.form.road" />
        </el-form-item>
        <el-form-item label="点位类型">
          <el-select v-model="spotDialog.form.spot_type" filterable allow-create
            default-first-option placeholder="主干道/次干道/商业大街/夜市" style="width: 100%">
            <el-option v-for="t in spotTypeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="管理单位">
          <el-select v-model="spotDialog.form.manage_unit" filterable allow-create
            default-first-option placeholder="点位归谁管，大部分是城市管理局" style="width: 100%">
            <el-option v-for="u in manageUnits" :key="u" :label="u" :value="u" />
          </el-select>
          <div class="form-tip">大部分点位属城市管理局，康杰路/陶朱公街/柳河东路归开发区；可下拉选择也可直接输入新单位</div>
        </el-form-item>
        <el-form-item label="摄像头归属">
          <el-select v-model="spotDialog.form.camera_source" filterable allow-create
            default-first-option placeholder="如 雪亮 / 盬街 / 黄河夜市" style="width: 100%">
            <el-option v-for="s in cameraSourceOptions" :key="s" :label="s" :value="s" />
          </el-select>
          <div class="form-tip">摄像头隶属来源（雪亮工程/盬街/黄河夜市管理等），源表未注明的留空即可</div>
        </el-form-item>
        <el-form-item label="点位联系人">
          <div class="contact-editor">
            <div v-for="(c, i) in spotDialog.form.contacts" :key="i" class="contact-row">
              <el-input v-model="c.dept_label" placeholder="部门/角色" style="width: 38%" />
              <el-input v-model="c.person" placeholder="姓名" style="width: 24%" />
              <el-input v-model="c.phone" placeholder="电话" style="width: 24%" />
              <el-button link type="danger" @click="spotDialog.form.contacts.splice(i, 1)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addContactRow">+ 添加一行</el-button>
          </div>
          <div class="form-tip">
            按统计表格式逐条填：部门/角色（如 环卫中心·片区负责人、环卫中心·点位主管、执法队·东城分队三中队、点位总负责人）、姓名、电话；一个点位可有多条
          </div>
        </el-form-item>
        <el-form-item label="高德坐标">
          <div class="coord-row">
            <el-input v-model="spotDialog.form.lng" placeholder="经度 如 110.98" style="width: 46%" />
            <el-input v-model="spotDialog.form.lat" placeholder="纬度 如 35.14" style="width: 46%" />
          </div>
          <div class="form-tip">在高德地图坐标拾取器上复制，预留后期地图展示用；可不填</div>
        </el-form-item>
        <el-form-item label="重点点位">
          <el-switch v-model="spotDialog.form.is_key" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="spotDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="spotDialog.saving" @click="submitSpot">保存</el-button>
      </template>
    </el-dialog>

    <!-- 单位编辑 -->
    <el-dialog v-model="deptDialog.visible" :title="deptDialog.form.id ? '编辑单位' : '添加单位'" width="480px">
      <el-form :model="deptDialog.form" label-width="100px">
        <el-form-item label="单位名称" required>
          <el-input v-model="deptDialog.form.name" />
        </el-form-item>
        <el-form-item label="创文联络员">
          <el-input v-model="deptDialog.form.contact" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="deptDialog.form.phone" />
        </el-form-item>
        <el-form-item label="部门底色">
          <el-color-picker v-model="deptDialog.form.color" />
              <span class="color-tip">详单标题条取派发部门底色</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deptDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="deptDialog.saving" @click="submitDept">保存</el-button>
      </template>
    </el-dialog>

    <!-- 类型编辑 -->
    <el-dialog v-model="typeDialog.visible" :title="typeDialog.form.id ? '编辑类型' : '添加类型'" width="480px">
      <el-form :model="typeDialog.form" label-width="120px">
        <el-form-item label="类型名称" required>
          <el-input v-model="typeDialog.form.name" />
        </el-form-item>
        <el-form-item label="默认派发部门">
          <el-select v-model="typeDialog.form.default_dept_id" clearable style="width: 100%">
            <el-option v-for="d in allDepts" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="typeDialog.saving" @click="submitType">保存</el-button>
      </template>
    </el-dialog>

    <!-- Excel 导入预览 -->
    <el-dialog v-model="importVisible" title="导入点位档案" width="720px">
      <template v-if="!importState.preview">
        <el-upload drag :http-request="onImportFile" :show-file-list="false" accept=".xlsx,.xls">
          <div class="import-drop">
            <p>将点位 Excel 拖到此处，或<b>点击选择文件</b></p>
            <p class="import-tip">
              主表 sheet 必需列：监控序号、点位名称；可选列：所在路段、管理单位、点位类型、摄像头归属、是否重点、经度、纬度<br />
              另建一个名为「联系人」的 sheet：列 = 监控序号、部门、人员、电话，一个点位可占多行（按监控序号归组）
            </p>
          </div>
        </el-upload>
      </template>
      <template v-else>
        <el-alert v-if="importState.preview.invalid?.length" type="error" :closable="false"
          :title="`${importState.preview.invalid.length} 行数据有问题，需修正后重新导入`" />
        <el-alert v-if="importState.preview.warnings?.length" type="warning" :closable="false" style="margin-top: 8px"
          :title="`${importState.preview.warnings.length} 条提醒：${importState.preview.warnings.map(w => `第${w.row}行${w.reason}`).join('；')}`" />
        <el-alert v-if="importState.preview.dup_in_file?.length" type="warning" :closable="false" style="margin-top: 8px"
          :title="`文件内监控序号重复：${importState.preview.dup_in_file.join('、')}（后者覆盖前者）`" />
        <p style="margin: 12px 0 8px">
          共解析 <b>{{ importState.preview.total }}</b> 行
          <template v-if="importState.preview.contact_count">
            ，「联系人」表 <b>{{ importState.preview.contact_count }}</b> 条
          </template>
          ，预览前 10 行：
        </p>
        <el-table :data="importState.preview.preview" border size="small" max-height="280">
          <el-table-column prop="monitor_no" label="监控序号" width="90" />
          <el-table-column prop="name" label="点位名称" />
          <el-table-column prop="road" label="所在路段" />
          <el-table-column prop="manage_unit" label="管理单位" width="110" />
          <el-table-column label="联系人" width="80">
            <template #default="{ row }">{{ row.contacts?.length || 0 }} 人</template>
          </el-table-column>
          <el-table-column label="坐标" width="150">
            <template #default="{ row }">
              {{ row.lng != null && row.lat != null ? `${row.lng}, ${row.lat}` : '' }}
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="resetImport">重新选择</el-button>
        <el-button v-if="importState.preview" type="primary" :loading="importState.saving"
          :disabled="!!importState.preview.invalid?.length" @click="confirmImport">
          确认导入（{{ importState.preview.total }} 行）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('spots')

// ---------- 点位 ----------
const spots = ref([])
const spotTotal = ref(0)
const spotPage = ref(1)
const spotPageSize = ref(20)
const spotKeyword = ref('')
const spotsLoading = ref(false)
const allDepts = ref([])

const spotDialog = reactive({
  visible: false, saving: false,
  form: { id: null, monitor_no: '', name: '', road: '', manage_unit: '城市管理局',
          camera_source: '', spot_type: '', contacts: [], lng: '', lat: '', is_key: 0 }
})

// 点位管理单位候选项（大部分属城市管理局，康杰路/陶朱公街/柳河东路归开发区；可输入新值自动追加）
const manageUnits = ref(['城市管理局', '开发区'])
const spotTypeOptions = ['主干道', '次干道', '商业大街', '夜市']
const cameraSourceOptions = ['雪亮', '盬街', '黄河夜市', '运城市城市管理局']

async function loadSpots() {
  spotsLoading.value = true
  try {
    const { data } = await axios.get('/api/cyw/spots', {
      params: { keyword: spotKeyword.value, page: spotPage.value, page_size: spotPageSize.value }
    })
    spots.value = data.spots || []
    spotTotal.value = data.total || 0
  } catch { /* error toast via interceptor */ }
  finally { spotsLoading.value = false }
}

function addContactRow() {
  spotDialog.form.contacts.push({ dept_label: '', person: '', phone: '' })
}

function openSpotEditor(row) {
  spotDialog.form = row
    ? { id: row.id, monitor_no: row.monitor_no, name: row.name,
        road: row.road || '', manage_unit: row.manage_unit || '城市管理局',
        camera_source: row.camera_source || '', spot_type: row.spot_type || '',
        // 联系人深拷贝，避免弹窗内改动直接改到表格数据
        contacts: (row.contacts || []).map(c => ({ ...c })),
        lng: row.lng ?? '', lat: row.lat ?? '', is_key: row.is_key ? 1 : 0 }
    : { id: null, monitor_no: '', name: '', road: '', manage_unit: '城市管理局',
        camera_source: '', spot_type: '', contacts: [],
        lng: '', lat: '', is_key: 0 }
  spotDialog.visible = true
}

async function submitSpot() {
  const f = spotDialog.form
  if (!f.monitor_no.trim() || !f.name.trim()) return ElMessage.warning('监控序号和点位名称不能为空')
  spotDialog.saving = true
  try {
    if (f.id) {
      await axios.put(`/api/cyw/spots/${f.id}`, f)
    } else {
      await axios.post('/api/cyw/spots', f)
    }
    ElMessage.success('已保存')
    spotDialog.visible = false
    loadSpots()
  } catch { /* error toast via interceptor */ }
  finally { spotDialog.saving = false }
}

async function removeSpot(row) {
  try {
    await axios.delete(`/api/cyw/spots/${row.id}`)
    ElMessage.success('已删除')
    loadSpots()
  } catch { /* error toast via interceptor */ }
}

// ---------- 单位 ----------
const depts = ref([])
const deptsLoading = ref(false)
const deptDialog = reactive({
  visible: false, saving: false,
  form: { id: null, name: '', contact: '', phone: '', color: '#1565C0' }
})

async function loadDepts() {
  deptsLoading.value = true
  try {
    const { data } = await axios.get('/api/cyw/depts')
    depts.value = data.depts || []
    allDepts.value = data.depts || []
  } catch { /* error toast via interceptor */ }
  finally { deptsLoading.value = false }
}

function openDeptEditor(row) {
  deptDialog.form = row
    ? { id: row.id, name: row.name, contact: row.contact || '', phone: row.phone || '', color: row.color || '#1565C0' }
    : { id: null, name: '', contact: '', phone: '', color: '#1565C0' }
  deptDialog.visible = true
}

async function submitDept() {
  const f = deptDialog.form
  if (!f.name.trim()) return ElMessage.warning('单位名称不能为空')
  deptDialog.saving = true
  try {
    if (f.id) {
      await axios.put(`/api/cyw/depts/${f.id}`, f)
    } else {
      await axios.post('/api/cyw/depts', f)
    }
    ElMessage.success('已保存')
    deptDialog.visible = false
    loadDepts()
  } catch { /* error toast via interceptor */ }
  finally { deptDialog.saving = false }
}

async function removeDept(row) {
  try {
    await axios.delete(`/api/cyw/depts/${row.id}`)
    ElMessage.success('已删除')
    loadDepts()
  } catch { /* error toast via interceptor */ }
}

// ---------- 类型 ----------
const types = ref([])
const typesLoading = ref(false)
const typeDialog = reactive({
  visible: false, saving: false,
  form: { id: null, name: '', default_dept_id: null }
})

async function loadTypes() {
  typesLoading.value = true
  try {
    const { data } = await axios.get('/api/cyw/types')
    types.value = data.types || []
  } catch { /* error toast via interceptor */ }
  finally { typesLoading.value = false }
}

function openTypeEditor(row) {
  typeDialog.form = row
    ? { id: row.id, name: row.name, default_dept_id: row.default_dept_id }
    : { id: null, name: '', default_dept_id: null }
  typeDialog.visible = true
}

async function submitType() {
  const f = typeDialog.form
  if (!f.name.trim()) return ElMessage.warning('类型名称不能为空')
  typeDialog.saving = true
  try {
    if (f.id) {
      await axios.put(`/api/cyw/types/${f.id}`, f)
    } else {
      await axios.post('/api/cyw/types', f)
    }
    ElMessage.success('已保存')
    typeDialog.visible = false
    loadTypes()
  } catch { /* error toast via interceptor */ }
  finally { typeDialog.saving = false }
}

async function removeType(row) {
  try {
    await axios.delete(`/api/cyw/types/${row.id}`)
    ElMessage.success('已删除')
    loadTypes()
  } catch { /* error toast via interceptor */ }
}

// ---------- Excel 导入（两段式：预览 → 确认） ----------
const importVisible = ref(false)
const importState = reactive({ preview: null, saving: false })

async function onImportFile({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await axios.post('/api/cyw/spots/import', fd)
    importState.preview = data
  } catch { /* error toast via interceptor */ }
}

function resetImport() {
  importState.preview = null
}

async function confirmImport() {
  importState.saving = true
  try {
    const { data } = await axios.post('/api/cyw/spots/import/confirm', { rows: importState.preview.rows })
    ElMessage.success(`导入完成：新增 ${data.inserted} 条，更新 ${data.updated} 条`)
    importVisible.value = false
    importState.preview = null
    loadSpots()
  } catch { /* error toast via interceptor */ }
  finally { importState.saving = false }
}

function downloadTemplate() {
  // CSV 只能装主表；联系人需按 Excel 双 sheet 导入（见导入弹窗说明）
  const csv = '\uFEFF监控序号,点位名称,所在路段,管理单位,点位类型,摄像头归属,是否重点,经度,纬度\n'
    + '01,示例广场,XX路,城市管理局,主干道,雪亮,否,110.983652,35.140218\n'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '创文点位导入模板.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(() => {
  loadSpots()
  loadDepts()
  loadTypes()
})

// 坐标展示：保留 6 位小数内的有效精度，避免 110.983652 显示成 110.9836520
function fmtCoord(row) {
  const f = (v) => (v == null ? '' : Number(v).toFixed(6).replace(/0+$/, '').replace(/\.$/, ''))
  return `${f(row.lng)}, ${f(row.lat)}`
}
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; }
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.coord-row { display: flex; justify-content: space-between; width: 100%; }
.coord-text { font-family: Consolas, Menlo, monospace; font-size: 12px; color: #606266; }
.dim { color: #909399; font-size: 12px; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.6; }
.dept-chip {
  display: inline-block;
  border: 1px solid;
  border-radius: 3px;
  padding: 0 6px;
  margin-right: 6px;
  font-size: 12px;
  color: #606266;
}
.color-chip {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  margin-right: 6px;
  vertical-align: -2px;
  border: 1px solid #ebeef5;
}
.color-tip { margin-left: 10px; color: #909399; font-size: 12px; }
.import-drop { padding: 20px; text-align: center; }
.import-tip { color: #909399; font-size: 12px; line-height: 1.7; }
/* 点位联系人：表格内一条一行全列出（部门/角色 — 姓名 — 电话），与快速录入页命中行同一套对齐口径 */
.spot-contacts { width: 100%; }
.contact-line {
  display: grid;
  /* 电话列定宽，部门列吃掉剩余宽度：单元格再窄也只是部门标签折行，不会把电话顶出格子 */
  grid-template-columns: minmax(0, 1fr) 64px 84px;
  align-items: baseline;
  column-gap: 10px;
  padding: 2px 0;
  font-size: 13px;
  line-height: 1.7;
}
.contact-dept { color: #606266; font-size: 12px; }
.contact-person { color: #303133; font-weight: 500; }
.contact-phone { color: #409eff; font-family: Consolas, Menlo, monospace; font-size: 12px; }
.contact-editor { width: 100%; }
.contact-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
</style>
