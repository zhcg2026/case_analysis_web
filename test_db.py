import urllib.parse
from sqlalchemy import create_engine, inspect

# 数据库配置
DB_USER = 'root'
DB_PASSWORD = 'MySql@2024!Root'
DB_NAME = 'case_analysis'
DB_HOST = 'localhost'
DB_PORT = '3306'

# 创建数据库引擎
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

print("测试数据库连接...")
try:
    # 测试连接
    with engine.connect() as conn:
        print("数据库连接成功!")
    
    # 获取表列表
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"数据库中的表: {tables}")
    
    if not tables:
        print("警告: 数据库中没有表，请先上传Excel文件")
    else:
        print(f"找到 {len(tables)} 个表")
        
        # 查看第一个表的结构
        if tables:
            first_table = tables[0]
            print(f"\n第一个表 {first_table} 的结构:")
            columns = inspector.get_columns(first_table)
            for col in columns:
                print(f"- {col['name']} ({col['type']})")
                
except Exception as e:
    print(f"数据库操作失败: {str(e)}")
finally:
    engine.dispose()
