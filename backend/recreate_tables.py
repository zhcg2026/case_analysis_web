from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
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

# CMS栏目模型
class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# CMS文章模型
class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    content = Column(Text)  # 长文本
    summary = Column(String(500))
    category_id = Column(Integer, nullable=False)
    author_id = Column(Integer, nullable=False)
    status = Column(String(20), default='draft')  # draft, published
    view_count = Column(Integer, default=0)
    file_path = Column(String(500))  # 文件路径，用于存储上传的Docx或PDF文件
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True))

# 删除旧表（如果存在）
print("删除旧表...")
Base.metadata.drop_all(engine)

# 创建新表
print("创建新表...")
Base.metadata.create_all(engine)

print("表结构重建完成！")
