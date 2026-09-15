// 菜单权限树（与后端 PERMISSION_KEYS 一一对应）
// children 的 key 为独立权限列；父级仅作分组展示控制

export const MENU_PERMISSION_TREE = [
  { key: 'map', label: '数图城管' },
  { key: 'knowledge', label: '知识库' },
  {
    key: 'dispatch',
    label: '案件归属',
    children: [
      { key: 'dispatch_standards', label: '立结案标准' },
      { key: 'dispatch_query', label: '归属查询' },
      { key: 'dispatch_special', label: '特殊事项归属' }
    ]
  },
  {
    key: 'data_mgmt',
    label: '数据管理',
    children: [
      { key: 'data_cleaning', label: '数据清洗入库' },
      { key: 'data_browse', label: '数据编辑浏览' },
      { key: 'data_stats', label: '统计查询' }
    ]
  },
  {
    key: 'assessment',
    label: '考核管理',
    children: [
      { key: 'assessment_input_platform', label: '平台数据录入' },
      { key: 'assessment_input_collector', label: '采集员数据录入' },
      { key: 'assessment_exemption', label: '豁免期设置' },
      { key: 'assessment_score', label: '考核计分' }
    ]
  },
  { key: 'data_analysis', label: '数据分析' },
  { key: 'case_map', label: '案件地图' },
  {
    key: 'ledger',
    label: '台账管理',
    children: [
      { key: 'ledger_maintenance', label: '运维台账' },
      { key: 'ledger_meeting', label: '会议台账' },
      { key: 'ledger_training', label: '培训台账' },
      { key: 'ledger_docs', label: '文件资料' },
      { key: 'ledger_monitor', label: '调取监控' },
      { key: 'ledger_drone', label: '无人机飞行' }
    ]
  },
  {
    key: 'duty',
    label: '值班管理',
    children: [
      { key: 'duty_schedule', label: '排班管理' },
      { key: 'duty_records', label: '值班记录' }
    ]
  },
  { key: 'business', label: '业务平台' }
]

export const ALL_MENU_PERMISSION_KEYS = MENU_PERMISSION_TREE.flatMap((item) =>
  item.children ? item.children.map((c) => c.key) : [item.key]
)

export function emptyPermissions() {
  const o = {}
  for (const k of ALL_MENU_PERMISSION_KEYS) o[k] = false
  return o
}

export function flattenPermissionNodes() {
  const list = []
  for (const item of MENU_PERMISSION_TREE) {
    if (item.children) {
      list.push({ ...item, isGroup: true })
      for (const c of item.children) list.push({ ...c, isGroup: false, parentKey: item.key, parentLabel: item.label })
    } else {
      list.push({ ...item, isGroup: false })
    }
  }
  return list
}
