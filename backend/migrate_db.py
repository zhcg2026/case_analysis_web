import pymysql
import urllib.parse

# 数据库配置
DB_USER = 'root'
DB_PASSWORD = 'MySql@2024!Root'
DB_NAME = 'case_analysis'
DB_HOST = 'localhost'
DB_PORT = '3306'

encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

try:
    # 连接数据库
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    
    cursor = conn.cursor()
    
    print("开始数据库迁移...")
    
    # 检查 map 列是否存在
    cursor.execute("SHOW COLUMNS FROM permissions LIKE 'map'")
    map_column_exists = cursor.fetchone()
    
    if not map_column_exists:
        print("添加 map 列...")
        cursor.execute("ALTER TABLE permissions ADD COLUMN map INT NOT NULL DEFAULT 0 AFTER chengguantong")
        print("map 列添加成功")
    else:
        print("map 列已存在")
    
    # 检查 huiwentai 列是否存在
    cursor.execute("SHOW COLUMNS FROM permissions LIKE 'huiwentai'")
    huiwentai_column_exists = cursor.fetchone()
    
    if not huiwentai_column_exists:
        print("添加 huiwentai 列...")
        cursor.execute("ALTER TABLE permissions ADD COLUMN huiwentai INT NOT NULL DEFAULT 0 AFTER map")
        print("huiwentai 列添加成功")
    else:
        print("huiwentai 列已存在")
    
    # 检查 business_platforms 表是否存在
    cursor.execute("SHOW TABLES LIKE 'business_platforms'")
    business_platforms_table_exists = cursor.fetchone()
    
    if not business_platforms_table_exists:
        print("创建 business_platforms 表...")
        cursor.execute("""
        CREATE TABLE business_platforms (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            url VARCHAR(255) NOT NULL,
            image_path VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("business_platforms 表创建成功")
    else:
        print("business_platforms 表已存在")
    
    # 提交更改
    conn.commit()
    
    print("数据库迁移完成！")
    
except Exception as e:
    print(f"数据库迁移失败: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    if 'conn' in locals():
        cursor.close()
        conn.close()
