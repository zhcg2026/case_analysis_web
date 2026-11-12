# 城管案件分析平台

城市管理案件数据分析系统，支持案件数据上传、AI 智能分析、知识库检索、案件归属判断、地图可视化等功能。

## 技术栈

- **前端**: Vue 3 + Vite + Element Plus + ECharts + Pinia
- **后端**: Flask + SQLAlchemy + Milvus（向量检索）+ jieba（中文分词）
- **AI**: 火山引擎 ARK（豆包/DeepSeek）用于数据分析与知识库问答
- **数据库**: MySQL 8.0+

## 快速开始

以下步骤用于独立的本地开发环境。运行中的生产实例请先阅读下方“部署与恢复说明”，不要在现网执行初始化或照搬历史部署命令。

### 1. 环境准备

- Python 3.11+
- Node.js 18+
- MySQL 8.0+

### 2. 克隆项目

```bash
git clone https://github.com/zhcg2026/case_analysis_web.git
cd case_analysis_web
```

### 3. 数据库初始化

```sql
CREATE DATABASE case_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 应用启动时会自动建表，无需手动创建表结构。

### 4. 后端配置与启动

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入数据库连接信息和 API Key
pip install -r ../requirements.txt
python app.py
```

`backend/.env` 需要配置的关键项：

| 变量 | 说明 |
|------|------|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接信息 |
| `JWT_SECRET_KEY` | JWT 密钥（至少 32 位，可用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成）|
| `ARK_API_KEY` | 火山引擎 ARK API Key（[控制台申请](https://console.volcengine.com/ark)）|

### 5. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，代理 API 请求到后端 `http://localhost:5000`。

## 部署与恢复说明

当前生产容器的脱敏运行基线和只读预检统一从 [ops/recovery/README.md](ops/recovery/README.md) 查阅。

- 根目录 `docker-compose.internal.yml` 是**已过期的历史配置**，不能完整描述当前生产挂载和环境；不要直接用于现网重建或容器接管。
- `ops/recovery/compose.recovery.reference.yml` 是经过参数核对的**备查参考**，要求明确指定经过验证的恢复镜像，不会自动接管现网。静态检查通过也不代表已完成恢复演练。
- 当前 `Dockerfile` 和 `requirements.txt` 不等于已验证的可复现构建方案；镜像与运行层的后装依赖有差异，不能据此重新构建后直接替换正常容器。
- 密钥、环境文件、镜像、数据库及业务文件备份独立受控保存，不进入仓库。恢复前必须核对挂载数据、凭据、镜像和回退依据。

日常保持现有正常容器运行。任何生产变更或恢复另行制定方案并确认授权，本节不提供可直接作用于现网的生命周期命令。

## 项目结构

```
├── backend/
│   ├── app.py                    # Flask 应用入口
│   ├── auth_routes.py            # 登录/认证/用户管理
│   ├── analysis_routes.py        # 数据分析（AI 生成 SQL + 图表）
│   ├── kb_routes.py              # 知识库检索
│   ├── kb_store.py               # 知识库核心（向量+BM25混合检索）
│   ├── dispatch_engine.py        # 案件归属判断引擎
│   ├── template_export_routes.py # 报告模板与导出
│   ├── case_map_routes.py        # 案件地图
│   └── helpers.py                # 工具函数（JWT、密码等）
├── frontend/
│   ├── src/views/                # 页面组件
│   ├── src/stores/               # Pinia 状态管理
│   └── public/data/              # GeoJSON 地图数据
├── Dockerfile
└── requirements.txt
```

## 主要功能

- **数据分析**: 上传 Excel 案件数据，AI 自动生成 SQL 查询、图表和分析结论
- **知识库**: RAG 混合检索（向量 + BM25 + RRF），支持法规、职责、标准查询
- **案件归属**: 根据案件类型和坐标，自动判断归属部门和管辖片区
- **案件地图**: 地图可视化展示案件分布、热力图、管辖范围
- **报告模板**: 可配置的分析报告模板，支持导出 Word

## 默认账号

管理员默认账号密码请查看首次启动日志，或通过数据库直接创建。
