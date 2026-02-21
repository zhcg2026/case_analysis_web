#!/bin/bash

# 部署脚本
set -e

echo "开始部署城管案件分析系统..."

# 进入应用目录
cd /root/case_analysis_web || mkdir -p /root/case_analysis_web && cd /root/case_analysis_web

# 拉取或更新项目文件
if [ -d ".git" ]; then
    echo "更新现有项目..."
    git pull origin main
else
    echo "初始化项目..."
    # 这里可以替换为你的仓库地址
    # git clone <your-repo-url> .
fi

# 创建必要的目录
mkdir -p backend/uploads

# 构建 Docker 镜像
echo "构建 Docker 镜像..."
docker build -t case-analysis-web:latest .

# 停止并删除旧容器
echo "清理旧容器..."
docker-compose down || true

# 启动新容器
echo "启动应用..."
docker-compose up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查健康状态
if docker ps | grep -q case-analysis-web; then
    echo "✓ 应用启动成功！"
    echo "服务地址: http://81.70.163.116:5000"
else
    echo "✗ 应用启动失败，请检查日志"
    docker-compose logs
    exit 1
fi

echo "部署完成！"
