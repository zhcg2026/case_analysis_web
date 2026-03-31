#!/bin/bash
# 内网服务器一键部署脚本
# 服务器: 192.168.101.3
# 用户: ubuntu

set -e  # 遇到错误立即退出

# 配置
SERVER="192.168.101.3"
USER="ubuntu"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "案件分析系统 - 内网部署脚本"
echo "=========================================="
echo "服务器: $SERVER"
echo "用户: $USER"
echo "本地目录: $LOCAL_DIR"
echo "=========================================="

# 步骤1: 本地构建前端
echo ""
echo "[步骤 1/5] 构建前端..."
cd "$LOCAL_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "  安装 npm 依赖..."
    npm install
fi
echo "  执行 npm run build..."
npm run build
echo "  前端构建完成 ✓"

# 步骤2: 上传项目到服务器
echo ""
echo "[步骤 2/5] 上传项目到服务器..."
echo "  正在上传..."
scp -r \
    "$LOCAL_DIR/backend" \
    "$LOCAL_DIR/frontend/dist" \
    "$LOCAL_DIR/docker-compose.internal.yml" \
    "$LOCAL_DIR/.env.production" \
    "$LOCAL_DIR/requirements.txt" \
    "$LOCAL_DIR/Dockerfile" \
    "$USER@$SERVER:~/case_analysis_web/"
echo "  上传完成 ✓"

# 步骤3-5: SSH到服务器执行所有远程操作
echo ""
echo "[步骤 3/5] 重建 Docker 容器..."
echo "[步骤 4/5] 执行数据库迁移..."
echo "[步骤 5/5] 验证部署..."
echo ""
echo "=========================================="
echo "现在将 SSH 到服务器执行后续步骤..."
echo "请输入密码（SSH密码和sudo密码可能各需输入一次）"
echo "=========================================="
echo ""

# 使用单次SSH连接执行所有操作（-t启用终端交互）
ssh -t "$USER@$SERVER" 'bash -s' << 'REMOTE_SCRIPT'
set -e
cd ~/case_analysis_web

echo ""
echo "--- [步骤 3/5] 重建 Docker 容器 ---"
echo "停止旧容器..."
sudo docker-compose -f docker-compose.internal.yml down
echo "重新构建并启动..."
sudo docker-compose -f docker-compose.internal.yml up -d --build
echo "等待容器启动..."
sleep 10
echo "Docker 容器重建完成 ✓"

echo ""
echo "--- [步骤 4/5] 执行数据库迁移 ---"
echo "执行 migrate_cases.py..."
sudo docker exec -i case-analysis-web python backend/migrate_cases.py || echo "migrate_cases.py 已执行或跳过"
echo "执行 migrate_db.py..."
sudo docker exec -i case-analysis-web python backend/migrate_db.py || echo "migrate_db.py 已执行或跳过"

echo "手动补充迁移（创建新表和字段）..."
sudo docker exec -i backend_db_1 mysql -uroot -proot123 case_analysis << 'SQL_SCRIPT'
-- 确保 articles 表存在
CREATE TABLE IF NOT EXISTS articles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    content TEXT,
    summary VARCHAR(500),
    category_id INT NOT NULL,
    author_id INT NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    view_count INT DEFAULT 0,
    file_path VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 确保 operation_logs 表存在
CREATE TABLE IF NOT EXISTS operation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    table_name VARCHAR(100),
    operation_type VARCHAR(20),
    record_id VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 确保 system_config 表存在
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 确保 case_follows 表存在
CREATE TABLE IF NOT EXISTS case_follows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    follow_type VARCHAR(20),
    content TEXT,
    attachments TEXT,
    follow_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    follow_user VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 为 permissions 表添加新字段
SET @dbname = DATABASE();
SET @tablename = 'permissions';
SET @columnname = 'dashboard';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' INT DEFAULT 0')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'map';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' INT DEFAULT 0')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'huiwentai';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' INT DEFAULT 0')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 为 cases 表添加扩展字段
SET @tablename = 'cases';
SET @columnname = 'category';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(20) COMMENT ''案件分类''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'status';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(20) DEFAULT ''跟进中'' COMMENT ''状态''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'owner_unit';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(100) COMMENT ''权属单位''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'contact_person';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(50) COMMENT ''联系人''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'contact_phone';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(20) COMMENT ''联系电话''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'pending_reason';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' TEXT COMMENT ''挂账原因''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'pending_deadline';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' DATETIME COMMENT ''预计处置时间''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'difficult_type';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(50) COMMENT ''疑难类型''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'last_follow_time';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' DATETIME COMMENT ''最近跟进时间''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'follow_count';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' INT DEFAULT 0 COMMENT ''跟进次数''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'close_time';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' DATETIME COMMENT ''结案时间''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'close_remark';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' TEXT COMMENT ''结案说明''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @columnname = 'remark';
SET @preparedStatement = (SELECT IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0, 'SELECT 1', CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' TEXT COMMENT ''备注''')));
PREPARE stmt FROM @preparedStatement; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SQL_SCRIPT
echo "数据库迁移完成 ✓"

echo ""
echo "--- [步骤 5/5] 验证部署 ---"
echo "检查容器状态..."
sudo docker ps | grep case
echo "检查应用健康状态..."
curl -s http://localhost:5001/health && echo " ✓ 健康检查通过" || echo "健康检查失败"
echo "查看最近日志..."
sudo docker logs case-analysis-web --tail 20

echo ""
echo "=========================================="
echo "部署完成！"
echo "访问地址: http://192.168.101.3:5001"
echo "管理员账号: admin / admin123"
echo "=========================================="
REMOTE_SCRIPT

echo ""
echo "=========================================="
echo "全部完成！"
echo "=========================================="