"""
案件管理模块数据库迁移脚本 - MySQL版本
执行前请备份数据库
"""
import pymysql
import os

# 数据库配置（与 app.py 保持一致）
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = 'MySql@2024!Root'
DB_NAME = 'case_analysis'

def migrate_database():
    print(f"正在连接数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        print("数据库连接成功")

        # 1. 检查并添加 cases 表的新字段
        new_columns = [
            ("category", "VARCHAR(20) COMMENT '案件分类: 非我局管辖/挂账案件/疑难案件'"),
            ("status", "VARCHAR(20) DEFAULT '跟进中' COMMENT '状态: 跟进中/已结案'"),
            ("owner_unit", "VARCHAR(100) COMMENT '权属单位'"),
            ("contact_person", "VARCHAR(50) COMMENT '联系人'"),
            ("contact_phone", "VARCHAR(20) COMMENT '联系电话'"),
            ("pending_reason", "TEXT COMMENT '挂账原因'"),
            ("pending_deadline", "DATE COMMENT '预计处置时间'"),
            ("difficult_type", "VARCHAR(50) COMMENT '疑难类型'"),
            ("last_follow_time", "DATETIME COMMENT '最近跟进时间'"),
            ("follow_count", "INT DEFAULT 0 COMMENT '跟进次数'"),
            ("close_time", "DATETIME COMMENT '结案时间'"),
            ("close_remark", "TEXT COMMENT '结案说明'"),
            ("remark", "TEXT COMMENT '备注'"),
        ]

        # 获取现有列名
        cursor.execute("SHOW COLUMNS FROM cases")
        existing_columns = [col[0] for col in cursor.fetchall()]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE cases ADD COLUMN {col_name} {col_type}")
                    print(f"  添加列: {col_name}")
                except Exception as e:
                    print(f"  添加列 {col_name} 失败: {e}")

        # 2. 创建跟进记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_follows (
                id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                follow_type VARCHAR(20) COMMENT '跟进类型: 发函/协调/督办/其他',
                content TEXT COMMENT '跟进内容',
                attachments TEXT COMMENT '附件路径JSON',
                follow_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                follow_user VARCHAR(50) COMMENT '跟进人',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='案件跟进记录表'
        """)
        print("  创建表: case_follows")

        # 3. 创建索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cases_category ON cases(category)",
            "CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)",
            "CREATE INDEX IF NOT EXISTS idx_cases_pending_deadline ON cases(pending_deadline)",
            "CREATE INDEX IF NOT EXISTS idx_case_follows_case_id ON case_follows(case_id)",
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                # MySQL 不支持 IF NOT EXISTS，忽略已存在的索引错误
                pass
        print("  创建索引完成")

        conn.commit()
        print("\n迁移完成！")
        return True

    except Exception as e:
        print(f"\n迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'conn' in dir():
            conn.close()

if __name__ == "__main__":
    migrate_database()