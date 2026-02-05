from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
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

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')  # admin or user
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 创建表
Base.metadata.create_all(engine)

print("用户表创建成功！")

# 插入默认管理员用户
from sqlalchemy.orm import sessionmaker
import hashlib

Session = sessionmaker(bind=engine)
session = Session()

# 检查是否已存在管理员用户
existing_admin = session.query(User).filter_by(username='admin').first()
if not existing_admin:
    # 创建默认管理员用户，密码为admin123
    admin_user = User(
        username='admin',
        password=hashlib.sha256('admin123'.encode()).hexdigest(),
        role='admin'
    )
    session.add(admin_user)
    session.commit()
    print("默认管理员用户创建成功！用户名: admin, 密码: admin123")
else:
    print("管理员用户已存在，跳过创建。")

session.close()
