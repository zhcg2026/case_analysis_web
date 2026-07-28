// 数据分析模块共用的格式化/表格/Markdown 工具
// 从 DataAnalysis.vue / ReportView.vue 抽离，避免重复代码

/**
 * HTML 转义，防止 v-html 渲染 LLM 返回内容时产生 XSS。
 */
export function escapeHtml(s) {
  if (s == null) return ''
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 格式化批次月份（如 202606 -> 2026年06月）
export function formatBatch(batch) {
  if (!batch || batch.length < 6) return batch
  return batch.slice(0, 4) + '年' + batch.slice(4) + '月'
}

// 从表格数据第一行提取列名
export function getTableColumns(data) {
  if (!data || !data.length) return []
  return Object.keys(data[0])
}

// 判断某个单元格值是否为数值（用于表格右对齐样式）
export function isNumeric(v) {
  if (v == null) return false
  return typeof v === 'number' || (!isNaN(Number(v)) && v !== '')
}

// 单元格展示值格式化
export function formatCellValue(v) {
  if (v == null) return '-'
  if (typeof v === 'number') return fmtNumLocal(v)
  return String(v)
}

function fmtNumLocal(v) {
  if (typeof v !== 'number') return String(v)
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

/**
 * 极简 Markdown 渲染：先转义 HTML，再处理 **加粗** 与换行。
 * 顺序很重要——必须先转义再替换，避免注入。
 */
export function renderMarkdown(text) {
  if (!text) return ''
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
