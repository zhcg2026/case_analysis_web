#!/bin/bash

# 快速重新部署脚本
# 使用方法: ./quick_deploy.sh

echo "======================================"
echo "城管案件分析系统 - 快速重新部署"
echo "======================================"

# 切换到项目目录
cd /root/case_analysis_web || { echo "项目目录不存在"; exit 1; }

echo ""
echo "1. 停止旧容器..."
docker-compose down 2>/dev/null || echo "没有运行中的容器"

echo ""
echo "2. 删除旧镜像..."
docker rmi case-analysis-web:latest 2>/dev/null || echo "没有旧镜像"

echo ""
echo "3. 重新构建镜像..."
docker build -t case-analysis-web:latest . || { echo "构建失败"; exit 1; }

echo ""
echo "4. 启动新容器..."
docker-compose up -d || { echo "启动失败"; exit 1; }

echo ""
echo "======================================"
echo "部署完成！"
echo "======================================"
echo ""
echo "等待 10 秒让服务启动..."
sleep 10

echo ""
echo "检查容器状态..."
docker-compose ps

echo ""
echo "查看服务日志..."
docker-compose logs --tail=30

echo ""
echo "======================================"
echo "访问地址:"
echo "  前端界面: http://81.70.163.116:5000"
echo "  健康检查: http://81.70.163.116:5000/health"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  重启服务: docker-compose restart"
echo "  停止服务: docker-compose down"
echo "======================================"
