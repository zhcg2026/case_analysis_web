# 月度分析报告 — AI 动态章节实施方案

> 状态：设计文档（待实施）
> 目标：将第7章"数据特征归纳"和第8章"工作建议"从固定模板改为基于当月数据的 AI 动态生成

---

## 一、问题现状

当前模板的第7、8章是固定文案 + 数据占位符注入，每月生成的结论文字相同、只有数字变化。
实际上这两章应该是基于当月数据特征的分析结论——哪个月超时集中在哪个部门、复发率在恶化还是改善、哪些建议针对本月具体问题——这些不应该每月一样。

## 二、方案选择：混合模式（规则引擎 + LLM 润色）

**核心原则：LLM 只负责"写"，不负责"算"。**

所有数字由流水线 pandas 计算（analysis.json），LLM 拿到的是已经算好的结构化发现（bullets），它只做文字组织和公文润色。这样即使 LLM 出错，数字也是准的。

### 流程

```
analysis.json
    ↓
规则引擎（findings_extractor.py）
    ↓ 提取 3-8 条结构化发现，每条含：类别、数值、对比基准、严重程度
    ↓
LLM 润色（llm_writer.py）
    ↓ 输入：结构化发现 + 报告上下文（月份、单位等）
    ↓ 输出：第7章 + 第8章的完整公文段落
    ↓ 注入模板（替换原有固定文案区域）
    ↓
最终报告（HTML + Word）
```

## 三、规则引擎设计（findings_extractor.py）

从 analysis.json 提取关键发现，输出结构化列表。不依赖外部 API，纯 Python 逻辑。

### 提取规则（按优先级）

| # | 类别 | 规则 | 输出示例 |
|---|------|------|----------|
| 1 | 超时 | overtime_rate > 2% → 高亮；按部门排序取 top3 | "超时率1.31%，集中在XX部门（32件）、YY部门（28件）" |
| 2 | 延返 | delay_n + rework_n 占比；环比上月（需历史数据） | "延期223件、返工18件，合计占总量1.47%" |
| 3 | 复发 | ge3_rate > 25% → 标记；hot_n/top 小类 | "≥3件复发组862组涉4778件（29.29%），无照经营游商占首位" |
| 4 | 处置效率 | dur.p50 与上月对比；快/慢部门 | "全平台中位处置时长1.4小时，XX部门中位4.2小时偏高" |
| 5 | 来源结构 | src_gov_rate 趋势；政务渠道占比 | "政务渠道占2.3%，12345热线转办中位用时XX小时" |
| 6 | 监督员 | sup_cv > 40% → 标记离散度 | "36名专职采集员变异系数42%，采集量差异较大" |
| 7 | 地址质量 | no_addr_rate > 10% → 标记 | "地址缺失1699件（10.31%），影响复发识别精度" |
| 8 | 异常日 | anomalies 有数据时 | "本月3个异常采集日，剔除后日均571.6件" |

### 输出格式

```python
[
    {
        "category": "超时",
        "severity": "warning",  # info / warning / alert
        "metric": {"overtime_n": 216, "overtime_rate": 1.31},
        "detail": "超时率1.31%，XX部门32件最多",
        "context": "较上月XX件有所改善/恶化"  # 需要历史数据支持
    },
    ...
]
```

### 历史数据支持（环比）

规则引擎需要上月数据做环比。两种获取方式：
- **简单版**：从 DB 查 `SELECT ... WHERE upload_batch=<上月>` 聚合几个关键指标（overtime_n, total, ge3_n 等）
- **完整版**：pipeline 对上月批次也跑一遍 analysis，缓存结果

建议先用简单版（只查几个聚合值），后续需要再扩展。

## 四、LLM 润色模块（llm_writer.py）

### 输入

```python
{
    "month": "2026年8月",
    "org": "运城市城市管理局...",
    "findings": [  # 规则引擎输出
        {"category": "超时", "severity": "warning", "detail": "..."},
        ...
    ],
    "key_metrics": {  # 直接从 analysis.json 取，给 LLM 参考但不生成
        "total": 16475, "overtime_n": 194, "ge3_rate": 29.29, ...
    }
}
```

### Prompt 设计要点

```
你是城市管理案件分析报告的撰写助手。请根据以下数据发现，撰写两个章节：

第7章 数据特征归纳：总结本月数据的3-5个核心特征，每个特征一段话。
第8章 工作建议：基于上述特征提出3-5条具体建议。

要求：
1. 数字必须与提供的数据完全一致，不要自行计算或修改
2. 使用政务公文风格，语气客观、建议具体可操作
3. 每条建议要对应一个具体的数据发现
4. 不要编造数据中没有的信息
5. 输出格式：第7章和第8章各3-5段，每段2-3句
```

### LLM 选择

项目已有豆包 API（DOUBAO_API_KEY / DOUBAO_API_URL / DOUBAO_MODEL 在 analysis_routes.py 中配置）。复用同一套配置，新增一个 `llm_writer.py` 模块。

### Fallback（LLM 不可用时）

规则引擎的 findings 本身就有 detail 字段，直接拼接成列表形式的简要报告，不会空白：

```
数据特征归纳：
1. 超时率1.31%，XX部门32件最多
2. 复发率29.29%，无照经营游商占首位
3. ...
```

## 五、集成到流水线

### pipeline.py 改动

在 `run_pipeline()` 中，analyze.py 跑完后、make_word.py 跑之前，插入两个新步骤：

```python
# 新增步骤：提取发现 + LLM 润色
_findings = extract_findings(workdir, engine, batch)  # 规则引擎
_ai_chapters = generate_ai_chapters(findings, batch, engine)  # LLM 润色

# 写入 workdir 供 make_word.py / template.html 读取
with open(os.path.join(workdir, 'ai_chapters.json'), 'w', encoding='utf-8') as f:
    json.dump(_ai_chapters, f, ensure_ascii=False)
```

### make_word.py 改动

第7、8章的 `para(...)` 调用改为读取 `ai_chapters.json`：

```python
# 原来：固定模板
# 改为：优先读 ai_chapters.json，不存在则用 fallback 模板
ai = {}
try:
    ai = json.load(open(os.path.join(BASE, 'ai_chapters.json'), encoding='utf-8'))
except: pass

if ai.get('chapter7'):
    h1('七、数据特征归纳')
    for para_text in ai['chapter7']:
        para(para_text)
else:
    # 原有 fallback 模板
    ...

if ai.get('chapter8'):
    h1('八、工作建议')
    for para_text in ai['chapter8']:
        para(para_text)
else:
    # 原有 fallback 模板
    ...
```

### template.html 改动

同样的逻辑：JS 优先读 `D.ai_chapters`（注入到 analysis.json 中），不存在则用原有固定文案。

```javascript
if (D.ai_chapters && D.ai_chapters.chapter7) {
    document.getElementById('n-summary').innerHTML = D.ai_chapters.chapter7.map(p => '<p>' + p + '</p>').join('');
} else {
    // 原有固定文案
}
```

## 六、异常日配置存储（anomalies）

### 问题
前端生成报告时不传 anomalies，导致异常日信息丢失。

### 方案
按 batch 存储 anomalies 到 `backend/monthly_report/config/<batch>.json`：

```
backend/monthly_report/config/
    202608.json   ← {"anomalies": [...]}
    202607.json
    ...
```

### 逻辑
1. 生成时：优先用前端传的 anomalies → 其次读 config/<batch>.json → 最后为空
2. 生成后：将 anomalies 持久化到 config/<batch>.json（如果前端传了）
3. 前端：在"生成报告"按钮旁加一个小编辑入口，可以维护当月的异常日

### 前端 UI
在月度报告卡片下方加一个可折叠的"异常日设置"区域：
- 日期选择器 + 类型下拉（降雨/系统故障/其他）+ 说明输入
- 添加/删除按钮
- 保存后持久化到后端

## 七、文件改动清单

| 文件 | 改动 |
|------|------|
| `backend/monthly_report/findings_extractor.py` | **新增** 规则引擎 |
| `backend/monthly_report/llm_writer.py` | **新增** LLM 润色模块 |
| `backend/monthly_report/pipeline.py` | 插入 extract + LLM 步骤，存储 ai_chapters.json |
| `backend/monthly_report/make_word.py` | 第7、8章改为读 ai_chapters.json |
| `backend/monthly_report/template.html` | 第7、8章改为读 D.ai_chapters |
| `backend/monthly_report/monthly_report_routes.py` | anomalies 存储/读取，generate 接口增加 anomalies 参数 |
| `frontend/src/views/DataAnalysis.vue` | 异常日输入 UI |

## 八、实施顺序

1. **anomalies 存储**（0.5h）：后端 config/<batch>.json 读写 + 前端传参 → 先解决8月异常日缺失
2. **findings_extractor.py**（1h）：规则引擎，纯 Python，从 analysis.json 提取发现
3. **llm_writer.py**（1h）：LLM 调用 + prompt + fallback
4. **pipeline 集成**（0.5h）：插入新步骤，写 ai_chapters.json
5. **make_word.py + template.html**（0.5h）：第7、8章改为动态读取
6. **前端异常日 UI**（0.5h）：日期+类型+说明的输入组件
7. **验证**（0.5h）：8月报告对比原有模板 vs AI 生成效果

估时合计：约 4.5h

## 九、风险与兜底

| 风险 | 应对 |
|------|------|
| LLM API 不可用 | fallback 到规则引擎 bullets，不会空白 |
| LLM 输出数字不准 | prompt 严格要求数字原样引用，不给计算任务；后端可加正则校验 |
| LLM 输出格式不符 | prompt 限定输出格式（段落数、每段句数），post-process 截断/补全 |
| 生成耗时增加 | LLM 调用约 5-10s，对总耗时影响小 |
| 规则引擎遗漏重要发现 | 初始规则覆盖8类常见场景，后续根据实际报告反馈迭代 |
