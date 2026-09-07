# Zcode 集成任务书：月度分析报告接入"一站通"数据分析模块

> 本文件是给实现 Agent（Zcode）的执行说明书。完整设计依据见同目录《月度分析报告集成方案.md》，本文件只给"做什么、按什么口径、注意什么"。

## 0. 目标
把已固化的 `case-monthly-report` skill（城市管理局月度案件分析流水线）接入 `case_analysis_web`（即"一站通"）的"数据分析"模块，让用户在网页上一键生成固定口径的政务月报：
- 网页内嵌查看（ECharts 交互图表，走 `ReportEmbed.vue` 的 iframe）；
- 可导出 Word 公文（docx）。

## 1. 源码与依据位置（本机）
- **实现说明书（必读）**：`C:\Users\Administrator\Documents\trae_projects\case_analysis_web\docs\月度分析报告集成方案.md`
- **skill 脚本源码（要搬进后端）**：`C:\Users\Administrator\.workbuddy\skills\case-monthly-report\scripts\`
  - `analyze.py`（核心：pandas 出指标 JSON）、`std_parse.py`、`build_html.py`、`template.html`、`make_word.py`、`polish_charts.py`、`polish_docx.py`、`run.py`、`smoke.js`
- **口径铁律文档**：`C:\Users\Administrator\.workbuddy\skills\case-monthly-report\references\口径与方法.md`

## 2. 三条铁律（不可违背）
1. **超时按 `is_overtime` 字段**（平台认定），绝不用"处置截止时间"反推。
2. **结案**按"当前阶段名称 = 办结"；**延期/返工**按对应字段。
3. **考核期限**取自《立案、处置和结案标准》（法定时限，按小类），不反算。

## 3. 两个关键前提（已与用户确认，务必照此执行）
### 3.1 `is_overtime`：产线已有，本地仅对齐
- **服务端（生产 MySQL `case_data`）已存在 `is_overtime` 列并已填充，是真值。**
- ❌ **禁止**在产线执行任何 `ALTER TABLE ... ADD COLUMN` 或重新上传/重导历史数据。
- ✅ 只做"本地对齐"：`backend/analysis_routes.py` 的 `COLUMN_MAP` 补 `'is_overtime':'is_overtime'`；`CREATE_TABLE_SQL` 用幂等写法 `ADD COLUMN IF NOT EXISTS is_overtime TINYINT DEFAULT 0`（仅本地重建表用）；`process_excel_upload()` 对 `is_overtime` 用与 `is_delayed`/`is_rework` 相同的 `_normalize_bool()` 归一化。
- ✅ 若本地库缺 202608 全量数据：从产线 `SELECT ... WHERE upload_batch='202608'` 导出导入本地，**不要**重新 `POST /api/analysis/upload`（会先 DELETE 同批次、且旧逻辑会再丢字段）。

### 3.2 ECharts：本地化，不依赖公网 CDN
- 报告 HTML 的图表用 ECharts 绘制。模板现从 `cdn.jsdelivr.net` 加载——改为引用站内本地文件。
- 复制 `frontend/node_modules/echarts/dist/echarts.min.js` → `backend/reports/echarts.min.js`；
- `template.html` 头部改为 `<script src="/reports/echarts.min.js"></script>`。
- 理由：查看报告的浏览器端可能无公网出口，CDN 会白屏；本地化零成本且消除外部依赖。

## 4. 实施步骤
### 4.1 数据层（见 §3.1，仅本地对齐）
- `backend/analysis_routes.py`：`COLUMN_MAP` 增 `is_overtime` 映射；`CREATE_TABLE_SQL` 幂等增列；上传归一化补 `is_overtime`。

### 4.2 新增模块 `backend/monthly_report/`
把 skill 的 `analyze.py / std_parse.py / build_html.py / template.html / make_word.py / polish_charts.py / polish_docx.py` 整体搬入，仅改两处：
- **输入层**：`analyze.py` 新增 `load_from_db(engine, batch)`，用 `pd.read_sql("SELECT * FROM case_data WHERE upload_batch=:b", conn, params={'b':batch})` 取数，英文列按 `COLUMN_MAP` 反向映射回中文（或改读取逻辑直接吃英文列）后调原 `analyze(df, cfg)`。**原函数签名不动**，只加数据入口。标准时限 xlsx 放一份到 `backend/monthly_report/` 静态目录，generate 时读取。
- **ECharts 引用**：`template.html` 改本地（见 §3.2）。

### 4.3 新增路由 `backend/monthly_report_routes.py`
- `POST /api/monthly-report/generate`：按 `upload_batch` 生成报告，写 HTML 到 `backend/reports/<batch>.html` 并落 `analysis.json`；
- `GET /api/monthly-report/<batch>/export`：返回 docx 下载。
- 在 `backend/app.py` 注册蓝图。

### 4.4 前端
- `frontend/src/views/DataAnalysis.vue` 加"生成月度分析报告"按钮（选 `upload_batch` / 月份），调用 generate 后跳 `/report-embed/<batch>.html`（`ReportEmbed.vue` 用 iframe 加载 `/reports/<batch>.html`）；同时提供 docx 导出入口。
- 复用现有 `/reports/` 静态目录与 `/report-embed/:filename` 路由，前端改动极小。

## 5. 验证标准
- 对 `202608` 批次跑 generate，生成的 `analysis.json` 与原 skill 8 月结果**逐指标一致**：总量 16476、超时 216（1.31%）、延期 223、返工 18、复发 ge3 862 组/4778 件（29.29%）、法定时限 201 小类全覆盖、地址缺失 1699。
- 打开 `/report-embed/202608.html`，32 个图表全部渲染（本地 echarts 生效，浏览器网络面板无 cdn.jsdelivr 请求）。
- `/api/monthly-report/202608/export` 返回可下载 docx，内容与该用户既定稿（优化版）一致。
- 不影响现有 AI 即席分析模块。

## 6. 风险与回滚
- `is_overtime` 产线已存在**不要动**；仅本地开发库可能需 `ADD COLUMN IF NOT EXISTS`，可 `DROP COLUMN` 回滚。
- `monthly_report/` 独立新增，与 `analysis_routes.py` 互不干扰；移除只需注释注册行 + 删目录。
- 实施前先确认本地库 `is_overtime` 列状态，再决定是否需要本地对齐。

## 7. 交付后
完成后在 `case_analysis_web` 跑通 202608 全流程，并向用户报告验证数值是否对齐上述基准。
