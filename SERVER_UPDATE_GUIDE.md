# 服务器端更新指南

## ✅ 本地代码已推送

代码已成功推送到 GitHub: `https://github.com/zhcg2026/case_analysis_web.git`

---

## 🚀 服务器端更新步骤

### 1. SSH 连接到服务器
```bash
ssh root@81.70.163.116
```

### 2. 进入项目目录
```bash
cd /root/case_analysis_web
```

### 3. 拉取最新代码
```bash
git pull origin main
```

### 4. 重新构建前端
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. 快速重新部署
```bash
./quick_deploy.sh
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

## 📋 本次更新的内容

- ✅ 后端配置：使用环境变量 `DB_HOST` 区分本地和服务器
- ✅ 前端配置：Vite 代理支持环境变量 `VITE_API_TARGET`
- ✅ 添加部署文档和脚本
- ✅ .gitignore 配置，保护本地配置文件

---

## ⚠️ 重要提示

1. **服务器端**使用默认配置，无需设置环境变量
2. 确保 MySQL 容器（`mysql-case-analysis`）正常运行
3. 如果部署失败，查看日志：`docker-compose logs case-analysis-app`
