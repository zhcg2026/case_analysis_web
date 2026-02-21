# 城管案件分析系统部署指南

## 部署信息

- **服务器**: OpenCloudOS8-Docker26-ne3N
- **服务器 ID**: lhins-o1tmrvbe
- **地域**: 北京 (ap-beijing)
- **公网 IP**: 81.70.163.116
- **已开放端口**: 5000 (Flask API)

## 最近更新 (2026-02-20)

1. **后端已添加前端静态文件服务路由**：
   - 在 `backend/app.py` 中添加了服务前端 dist 文件的路由
   - 添加了健康检查接口 `/health`

2. **前端已修改为相对路径**：
   - 所有 API 调用从 `http://localhost:5000/` 改为 `/`
   - 重新构建了前端 dist 文件

## 部署步骤

### 1. 将项目文件上传到服务器

确保上传以下文件和目录：
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `backend/` 目录（包含 app.py）
- `frontend/dist/` 目录（最新构建的）

### 2. SSH 连接到服务器

```bash
ssh root@81.70.163.116
cd /root/case_analysis_web
```

### 3. 停止旧容器（如果有）

```bash
docker-compose down
```

### 4. 重新构建并启动 Docker 容器

```bash
# 构建镜像
docker build -t case-analysis-web:latest .

# 使用 docker-compose 启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 5. 验证部署

- 访问前端: http://81.70.163.116:5000
- API 健康检查: http://81.70.163.116:5000/health

### 6. 常用命令

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f case-analysis-app

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 完全重新部署
docker-compose down
docker build -t case-analysis-web:latest .
docker-compose up -d
```

## 文件说明

- `Dockerfile` - Docker 镜像构建配置
- `docker-compose.yml` - Docker Compose 编排配置
- `requirements.txt` - Python 依赖
- `frontend/dist/` - 前端构建输出（重要：必须包含最新构建）
- `backend/app.py` - Flask 后端应用（包含前端文件服务路由）

## 环境变量

如需自定义，可在 `docker-compose.yml` 中修改：

- `FLASK_ENV=production` - Flask 环境
- `PYTHONUNBUFFERED=1` - Python 无缓冲输出

## 数据库连接

确保后端能连接到 MySQL 数据库。在 `backend/app.py` 中配置数据库连接字符串。

## 故障排查

1. **容器无法启动**: 检查日志 `docker-compose logs`
2. **端口被占用**: 修改 `docker-compose.yml` 中的端口映射
3. **依赖缺失**: 重新构建镜像 `docker build -t case-analysis-web:latest .`
4. **前端无法访问**: 检查是否包含 `frontend/dist` 目录
5. **API 调用失败**: 确认 API 路径正确（使用相对路径 `/api/...`）
