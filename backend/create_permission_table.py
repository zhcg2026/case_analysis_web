from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
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

Base = declarative_base()

class Permission(Base):
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    data_management = Column(Boolean, default=False)
    assessment = Column(Boolean, default=False)
    data_analysis = Column(Boolean, default=False)
    spotcheck = Column(Boolean, default=False)
    tools = Column(Boolean, default=False)
    chengguantong = Column(Boolean, default=False)

# 创建表
Base.metadata.create_all(engine)

print("权限表创建成功！")

# 为现有用户添加默认权限
Session = sessionmaker(bind=engine)
session = Session()

# 查询所有用户
from sqlalchemy import text
users = session.execute(text("SELECT id FROM users")).fetchall()

for user in users:
    user_id = user[0]
    # 检查是否已存在权限记录
    existing_permission = session.execute(text("SELECT id FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
    if not existing_permission:
        # 添加默认权限
        session.execute(text("INSERT INTO permissions (user_id, data_management, assessment, data_analysis, spotcheck, tools, chengguantong) VALUES (:user_id, :data_management, :assessment, :data_analysis, :spotcheck, :tools, :chengguantong)"), {
            'user_id': user_id,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'tools': False,
            'chengguantong': False
        })
        print(f"为用户ID {user_id} 添加了默认权限")

session.commit()
session.close()

print("默认权限添加完成！")
