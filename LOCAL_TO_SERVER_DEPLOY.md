# 本地代码上传到服务器部署指南

## 概述

本文档说明如何将本地开发的代码更新部署到服务器上。

## 📦 步骤 1: 提交代码到 Git

### 1.1 检查变更
```bash
git status
```

### 1.2 添加需要提交的文件
```bash
git add backend/app.py
git add frontend/vite.config.js
git add frontend/src/App.vue
git add DEPLOYMENT.md
git add Dockerfile
git add deploy.sh
git add docker-compose.yml
git add quick_deploy.sh
git add requirements.txt
```

### 1.3 提交代码
```bash
git commit -m "优化配置管理: 使用环境变量区分本地和服务器"
```

### 1.4 推送到远程仓库
```bash
git push origin main
```

---

## 🚀 步骤 2: 登录服务器并部署

### 2.1 SSH 连接到服务器
```bash
ssh root@81.70.163.116
```

### 2.2 进入项目目录
```bash
cd /root/case_analysis_web
```

### 2.3 拉取最新代码
```bash
git pull origin main
```

### 2.4 重新构建前端（重要！）
在本地构建前端，然后上传，或者在服务器上构建：

**方式 A: 本地构建后上传**
```bash
# 在本地执行
cd frontend
npm run build
```
然后将 `frontend/dist` 目录上传到服务器。

**方式 B: 在服务器上构建（需要 Node.js）**
```bash
# 在服务器上执行
cd frontend
npm install
npm run build
cd ..
```

### 2.5 快速重新部署
使用快速部署脚本：
```bash
./quick_deploy.sh
```

或者手动执行：
```bash
# 停止旧容器
docker-compose down

# 重新构建镜像
docker build -t case-analysis-web:latest .

# 启动新容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 🔍 验证部署

### 检查服务状态
```bash
docker-compose ps
```

### 查看服务日志
```bash
docker-compose logs -f
```

### 访问应用
- 前端界面: http://81.70.163.116:5000
- 健康检查: http://81.70.163.116:5000/health

---

## 📋 常用命令速查

| 命令 | 说明 |
|------|------|
| `docker-compose ps` | 查看容器状态 |
| `docker-compose logs -f` | 实时查看日志 |
| `docker-compose restart` | 重启服务 |
| `docker-compose down` | 停止服务 |
| `docker build -t case-analysis-web:latest .` | 重新构建镜像 |

---

## ⚠️ 注意事项

1. **前端构建**: 每次修改前端代码后，必须重新运行 `npm run build`
2. **环境变量**: 服务器端使用默认配置（DB_HOST=mysql-case-analysis）
3. **.env.local**: 本地的 `.env.local` 文件不会被提交到 Git
4. **数据库**: 确保 MySQL 容器正常运行

---

## 🔧 故障排查

### 容器无法启动
```bash
docker-compose logs case-analysis-app
```

### 前端无法访问
检查 `frontend/dist` 目录是否存在且包含最新构建的文件。

### API 调用失败
检查后端日志，确认数据库连接正常。
