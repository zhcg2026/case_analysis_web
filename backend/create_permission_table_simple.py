from sqlalchemy import create_engine
import urllib.parse

# 数据库配置
DB_USER = 'root'
DB_PASSWORD = 'MySql@2024!Root'
DB_NAME = 'case_analysis'
DB_HOST = 'localhost'
DB_PORT = '3306'

# 创建数据库引擎
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# 连接数据库
conn = engine.connect()

# 检查users表是否存在
from sqlalchemy import text
users_table_exists = conn.execute(text("SHOW TABLES LIKE 'users'")).fetchone()
print(f"Users table exists: {users_table_exists is not None}")

# 创建权限表（不使用外键约束）
create_table_sql = """
CREATE TABLE IF NOT EXISTS permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    data_management BOOLEAN DEFAULT FALSE,
    assessment BOOLEAN DEFAULT FALSE,
    data_analysis BOOLEAN DEFAULT FALSE,
    spotcheck BOOLEAN DEFAULT FALSE,
    tools BOOLEAN DEFAULT FALSE,
    chengguantong BOOLEAN DEFAULT FALSE
)
"""

conn.execute(text(create_table_sql))
print("权限表创建成功！")

# 为现有用户添加默认权限
if users_table_exists:
    # 查询所有用户
    users = conn.execute(text("SELECT id FROM users")).fetchall()
    
    for user in users:
        user_id = user[0]
        # 检查是否已存在权限记录
        existing_permission = conn.execute(text("SELECT id FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
        if not existing_permission:
            # 添加默认权限
            conn.execute(text("INSERT INTO permissions (user_id, data_management, assessment, data_analysis, spotcheck, tools, chengguantong) VALUES (:user_id, :data_management, :assessment, :data_analysis, :spotcheck, :tools, :chengguantong)"), {
                'user_id': user_id,
                'data_management': False,
                'assessment': False,
                'data_analysis': False,
                'spotcheck': False,
                'tools': False,
                'chengguantong': False
            })
            print(f"为用户ID {user_id} 添加了默认权限")
    
    conn.commit()
    print("默认权限添加完成！")
else:
    print("未找到users表，跳过默认权限添加")

conn.close()
