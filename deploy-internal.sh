#!/bin/bash
# 内网服务器部署脚本
# 服务器: 192.168.101.3, 用户: ubuntu

set -e

echo "=== 案件分析系统部署脚本 ==="

# 检查 Docker 网络
echo "检查 Docker 网络..."
if ! sudo docker network ls | grep -q "backend_default"; then
    echo "创建 Docker 网络 backend_default..."
    sudo docker network create backend_default
else
    echo "Docker 网络 backend_default 已存在"
fi

# 在现有 MySQL 中创建数据库
echo "检查/创建数据库..."
sudo docker exec -i backend_db_1 mysql -uroot -pMySql@2024!Root -e "CREATE DATABASE IF NOT EXISTS case_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 构建镜像
echo "构建 Docker 镜像..."
sudo docker-compose -f docker-compose.internal.yml build

# 停止旧容器（如果存在）
echo "停止旧容器..."
sudo docker-compose -f docker-compose.internal.yml down 2>/dev/null || true

# 启动容器
echo "启动容器..."
sudo docker-compose -f docker-compose.internal.yml up -d

# 等待启动
echo "等待应用启动..."
sleep 5

# 检查状态
echo "检查容器状态..."
sudo docker-compose -f docker-compose.internal.yml ps

echo ""
echo "=== 部署完成 ==="
echo "访问地址: http://192.168.101.3:5001"
echo ""
echo "常用命令:"
echo "  查看日志: sudo docker-compose -f docker-compose.internal.yml logs -f"
echo "  重启服务: sudo docker-compose -f docker-compose.internal.yml restart"
echo "  停止服务: sudo docker-compose -f docker-compose.internal.yml down"