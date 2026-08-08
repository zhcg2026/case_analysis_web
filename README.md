# 城管案件分析平台

城市管理案件数据分析系统，支持案件数据上传、AI 智能分析、知识库检索、案件归属判断、地图可视化等功能。

## 技术栈

- **前端**: Vue 3 + Vite + Element Plus + ECharts + Pinia
- **后端**: Flask + SQLAlchemy + Milvus（向量检索）+ jieba（中文分词）
- **AI**: 火山引擎 ARK（豆包/DeepSeek）用于数据分析与知识库问答
- **数据库**: MySQL 8.0+

## 快速开始

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

## Docker 部署

```bash
# 先构建前端
cd frontend && npm run build && cd ..

# 后端打包需要一个 CPU 版 PyTorch whl 文件（放在项目根目录）
# 下载地址: https://download.pytorch.org/whl/cpu/torch
# 文件名: torch-2.13.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl

docker build -t case-analysis .
docker run -d -p 5000:5000 --env-file .env.production case-analysis
```

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
