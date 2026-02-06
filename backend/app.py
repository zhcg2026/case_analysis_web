from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
import urllib.parse
import json
import requests
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
import numpy as np
import hashlib
import jwt
import datetime
from functools import wraps

# 导入处理docx文件的库
from docx import Document

# JWT配置
SECRET_KEY = 'your-secret-key-for-jwt-token'
TOKEN_EXPIRATION = 24 * 60 * 60  # 24小时

app = Flask(__name__)
# 配置CORS，允许所有跨域请求
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

# JWT令牌生成
def generate_token(user_id, username, role):
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRATION)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# JWT令牌验证
def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except:
        return None

# 保护路由的装饰器
def protected(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # 移除Bearer前缀
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # 将用户信息添加到请求上下文
        request.user_id = payload['user_id']
        request.username = payload['username']
        request.role = payload['role']
        return f(*args, **kwargs)
    return decorated

# 管理员权限装饰器
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        
        # 移除Bearer前缀
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        if payload['role'] != 'admin':
            return jsonify({'error': 'Admin permission required'}), 403
        
        # 将用户信息添加到请求上下文
        request.user_id = payload['user_id']
        request.username = payload['username']
        request.role = payload['role']
        return f(*args, **kwargs)
    return decorated

# 数据库配置
DB_USER = 'root'
DB_PASSWORD = 'MySql@2024!Root'
DB_NAME = 'case_analysis'
DB_HOST = 'localhost'
DB_PORT = '3306'

# 创建数据库引擎
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# 导入用户表模型
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Permission(Base):
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True)
    data_management = Column(Integer, nullable=False, default=0)
    assessment = Column(Integer, nullable=False, default=0)
    data_analysis = Column(Integer, nullable=False, default=0)
    spotcheck = Column(Integer, nullable=False, default=0)
    tools = Column(Integer, nullable=False, default=0)
    chengguantong = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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

# 创建数据库表
Base.metadata.create_all(engine)

# 创建会话工厂
Session = sessionmaker(bind=engine)

# 生成slug函数
def generate_slug(text):
    import re
    import hashlib
    # 转换为小写
    slug = text.lower()
    # 替换空格为连字符
    slug = re.sub(r'\s+', '-', slug)
    # 保留中文和字母数字连字符
    slug = re.sub(r'[^\u4e00-\u9fa5a-z0-9-]', '', slug)
    # 替换多个连字符为单个
    slug = re.sub(r'-+', '-', slug)
    # 移除首尾连字符
    slug = slug.strip('-')
    # 如果slug为空，使用标题的哈希值
    if not slug:
        slug = hashlib.md5(text.encode()).hexdigest()[:8]
    return slug

# 文件读取函数
def read_file_content(file):
    """读取文件内容，支持docx和xlsx文件"""
    filename = file.filename
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension == '.docx':
        # 读取docx文件
        # 对于FileStorage对象，需要先保存到临时文件再读取
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp:
            file.save(temp.name)
            temp_path = temp.name
        
        try:
            # 使用更全面的方法读取docx文件
            def extract_headers_footers(doc):
                """提取页眉和页脚"""
                texts = []
                try:
                    for section in doc.sections:
                        # 提取页眉
                        header = section.header
                        for para in header.paragraphs:
                            text = para.text.strip()
                            if text:
                                texts.append(f"页眉: {text}")
                        # 提取页脚
                        footer = section.footer
                        for para in footer.paragraphs:
                            text = para.text.strip()
                            if text:
                                texts.append(f"页脚: {text}")
                except Exception as e:
                    print(f"Error extracting headers/footers: {str(e)}")
                return texts
            
            # 尝试使用python-docx读取
            doc = Document(temp_path)
            full_text = []

            # 1. 提取页眉
            header_footer_texts = extract_headers_footers(doc)
            if header_footer_texts:
                full_text.extend(header_footer_texts)

            # 2. 提取所有段落
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    full_text.append(text)

            # 3. 提取所有表格
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        row_text.append(cell_text)
                    # 合并一行单元格（用制表符分隔）
                    row_content = '\t'.join(row_text)
                    if row_content.strip():
                        full_text.append(row_content)

            # 4. 尝试使用更直接的方法读取文件内容
            try:
                import zipfile
                import re
                
                # 直接解析docx文件（本质是zip文件）
                with zipfile.ZipFile(temp_path, 'r') as zf:
                    # 读取主要内容文件
                    if 'word/document.xml' in zf.namelist():
                        with zf.open('word/document.xml') as f:
                            xml_content = f.read().decode('utf-8')
                            # 简单提取文本
                            text_content = re.sub('<[^<]+?>', '', xml_content)
                            text_content = text_content.strip()
                            if text_content:
                                # 如果之前没有提取到内容，使用这个
                                if not full_text:
                                    full_text.append(text_content)
            except Exception as e:
                pass  # 忽略XML提取错误，继续使用python-docx的结果

            content = '\n'.join(full_text)
            # 只打印关键信息
            print(f"DOCX file processed: {len(content)} characters extracted")
            return content
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
    elif file_extension == '.xlsx':
        # 读取xlsx文件
        df = pd.read_excel(file)
        # 转换为文本格式
        content = []
        for index, row in df.iterrows():
            row_content = []
            for col in df.columns:
                if pd.notna(row[col]):
                    row_content.append(f"{col}: {row[col]}")
            if row_content:
                content.append(' | '.join(row_content))
        return '\n'.join(content)
    else:
        raise ValueError('Unsupported file type')

# 大模型API配置（火山引擎）
API_KEY = '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0'
API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
MODEL = 'doubao-seed-1-8-251228'

@app.route('/api/upload', methods=['POST'])
@admin_required
def upload_file():
    session = Session()
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename.endswith('.xlsx'):
            # 读取Excel文件
            df = pd.read_excel(file)
            
            # 用文件名作为表名（去除.xlsx后缀）
            table_name = os.path.splitext(file.filename)[0]
            
            # 写入数据库
            df.to_sql(table_name, engine, if_exists='replace', index=False)
            
            session.commit()
            return jsonify({'message': 'File uploaded successfully', 'table_name': table_name}), 200
        else:
            return jsonify({'error': 'Only Excel files are allowed'}), 400
    except Exception as e:
        session.rollback()
        print(f"Error in upload_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# CMS文件上传接口
@app.route('/api/upload/file', methods=['POST'])
@admin_required
def upload_cms_file():
    session = Session()
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # 检查文件类型
        allowed_extensions = {'docx', 'pdf'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Only DOCX and PDF files are allowed'}), 400
        
        # 生成唯一文件名
        import uuid
        import os
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # 确保uploads目录存在
        upload_folder = 'uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # 保存文件
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        session.commit()
        # 返回文件路径
        return jsonify({
            'file_path': file_path,
            'filename': file.filename
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in upload_cms_file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 图片上传接口（用于富文本编辑器）
@app.route('/api/upload/image', methods=['POST'])
@admin_required
def upload_image():
    session = Session()
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # 检查文件类型
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'error': 'Only image files are allowed'}), 400
        
        # 生成唯一文件名
        import uuid
        import os
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # 确保uploads目录存在
        upload_folder = 'uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # 保存文件
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        session.commit()
        
        # TinyMCE需要的响应格式
        return jsonify({
            'location': f"http://localhost:5000/{file_path}"
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in upload_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
    session = Session()
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Missing username or password'}), 400
        
        # 查找用户
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # 验证密码
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if user.password != hashed_password:
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # 生成令牌
        token = generate_token(user.id, user.username, user.role)
        
        # 获取用户权限
        permission = session.execute(text("SELECT data_management, assessment, data_analysis, spotcheck, tools, chengguantong FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
        permissions = {
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'tools': False,
            'chengguantong': False
        }
        if permission:
            permissions = {
                'data_management': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'spotcheck': permission[3],
                'tools': permission[4],
                'chengguantong': permission[5]
            }
        
        session.commit()
        return jsonify({
                'token': token,
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'permissions': permissions
            }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in login: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 获取当前用户信息接口
@app.route('/api/user', methods=['GET'])
@protected
def get_current_user():
    session = Session()
    try:
        # 获取用户权限
        permission = session.execute(text("SELECT data_management, assessment, data_analysis, spotcheck, tools, chengguantong FROM permissions WHERE user_id = :user_id"), {'user_id': request.user_id}).fetchone()
        permissions = {
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'tools': False,
            'chengguantong': False
        }
        if permission:
            permissions = {
                'data_management': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'spotcheck': permission[3],
                'tools': permission[4],
                'chengguantong': permission[5]
            }
        
        session.commit()
        return jsonify({
            'user_id': request.user_id,
            'username': request.username,
            'role': request.role,
            'permissions': permissions
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_current_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 获取所有用户列表接口（管理员专用）
@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    session = Session()
    try:
        users = session.query(User).all()
        user_list = []
        for user in users:
            # 获取用户权限
            permission = session.execute(text("SELECT data_management, assessment, data_analysis, spotcheck, tools, chengguantong FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
            permissions = {
                'data_management': False,
                'assessment': False,
                'data_analysis': False,
                'spotcheck': False,
                'tools': False,
                'chengguantong': False
            }
            if permission:
                permissions = {
                    'data_management': permission[0],
                    'assessment': permission[1],
                    'data_analysis': permission[2],
                    'spotcheck': permission[3],
                    'tools': permission[4],
                    'chengguantong': permission[5]
                }
            user_list.append({
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'permissions': permissions
            })
        session.commit()
        return jsonify({'users': user_list}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_users: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 创建用户接口（管理员专用）
@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    session = Session()
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')
        
        if not username or not password:
            return jsonify({'error': 'Missing username or password'}), 400
        
        # 检查用户是否已存在
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400
        
        # 创建新用户
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        new_user = User(
            username=username,
            password=hashed_password,
            role=role
        )
        session.add(new_user)
        session.commit()
        
        # 为新用户添加默认权限
        session.execute(text("INSERT INTO permissions (user_id, data_management, assessment, data_analysis, spotcheck, tools, chengguantong) VALUES (:user_id, :data_management, :assessment, :data_analysis, :spotcheck, :tools, :chengguantong)"), {
            'user_id': new_user.id,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'tools': False,
            'chengguantong': False
        })
        session.commit()
        
        return jsonify({
            'id': new_user.id,
            'username': new_user.username,
            'role': new_user.role,
            'permissions': {
                'data_management': False,
                'assessment': False,
                'data_analysis': False,
                'spotcheck': False,
                'tools': False,
                'chengguantong': False
            }
        }), 201
    except Exception as e:
        session.rollback()
        print(f"Error in create_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 修改用户接口（管理员专用）
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    session = Session()
    try:
        data = request.json
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # 更新用户信息
        if 'username' in data:
            user.username = data['username']
        if 'password' in data:
            user.password = hashlib.sha256(data['password'].encode()).hexdigest()
        if 'role' in data:
            user.role = data['role']
        
        session.commit()
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'role': user.role
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 更新用户权限接口（管理员专用）
@app.route('/api/users/<int:user_id>/permissions', methods=['PUT'])
@admin_required
def update_user_permissions(user_id):
    session = Session()
    try:
        data = request.json
        
        # 验证用户是否存在
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # 更新用户权限
        session.execute(text("UPDATE permissions SET data_management = :data_management, assessment = :assessment, data_analysis = :data_analysis, spotcheck = :spotcheck, tools = :tools, chengguantong = :chengguantong WHERE user_id = :user_id"), {
            'user_id': user_id,
            'data_management': data.get('data_management', False),
            'assessment': data.get('assessment', False),
            'data_analysis': data.get('data_analysis', False),
            'spotcheck': data.get('spotcheck', False),
            'tools': data.get('tools', False),
            'chengguantong': data.get('chengguantong', False)
        })
        session.commit()
        
        # 返回更新后的权限
        permission = session.execute(text("SELECT data_management, assessment, data_analysis, spotcheck, tools, chengguantong FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
        permissions = {
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'tools': False,
            'chengguantong': False
        }
        if permission:
            permissions = {
                'data_management': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'spotcheck': permission[3],
                'tools': permission[4],
                'chengguantong': permission[5]
            }
        
        return jsonify({
            'user_id': user_id,
            'permissions': permissions
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_user_permissions: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 删除用户接口（管理员专用）
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # 不允许删除管理员用户
        if user.role == 'admin' and user_id == 1:
            return jsonify({'error': 'Cannot delete admin user'}), 400
        
        session.delete(user)
        session.commit()
        
        return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in delete_user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/tables', methods=['GET'])
@protected
def get_tables():
    session = Session()
    try:
        # 获取数据库中所有表名
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        session.commit()
        return jsonify({'tables': tables}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_tables: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 删除数据表接口
@app.route('/api/tables/<table_name>', methods=['DELETE'])
@protected
def delete_table(table_name):
    session = Session()
    try:
        # 防止删除系统表
        protected_tables = ['users', 'permissions']
        if table_name in protected_tables:
            return jsonify({'error': f'不能删除系统表 {table_name}'}), 403
        
        # 删除数据表
        from sqlalchemy import text
        session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        session.commit()
        return jsonify({'message': f'Table {table_name} deleted successfully'})
    except Exception as e:
        session.rollback()
        print(f"Error in delete_table: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

def convert_nan_to_null(obj):
    """将数据结构中的NaN值转换为null值"""
    if isinstance(obj, dict):
        return {key: convert_nan_to_null(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_null(item) for item in obj]
    elif isinstance(obj, float) and np.isnan(obj):
        return None
    else:
        return obj

# 考核计分相关函数
import datetime

def calculate_law_enforcement_score(cases):
    """计算城市综合行政执法队8个片区的考核分数和排名"""
    # 定义8个目标执法分队
    target_departments = [
        "执法东片区", "执法北片区", "执法南片区", "执法西片区",
        "执法中片区", "大渠执法分队", "姚孟执法分队", "安邑执法分队"
    ]
    print(f"目标统计部门：{target_departments}")
    
    # 按部门分组计算各项指标
    team_results = []
    
    for dept_name in target_departments:
        # 筛选该部门的数据
        dept_cases = [c for c in cases if c.get('处置部门') == dept_name]
        
        # 计算各项指标
        total = len(dept_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in dept_cases:
            # 检查结案时间和截止时间
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            # 检查延期次数
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            # 检查返工次数
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        # 计算比率
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        # 计算得分
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        team_results.append({
            'department': dept_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {dept_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    # 按得分排名
    team_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, team in enumerate(team_results, 1):
        team['rank'] = i
    
    print(f"\n排名结果：")
    for team in team_results:
        print(f"  第{team['rank']}名：{team['department']} - {team['score']}分")
    
    # 计算总体数据
    total_cases = sum(t['total_cases'] for t in team_results)
    total_score = sum(t['score'] for t in team_results) / len(team_results)
    
    return {
        'total_cases': total_cases,
        'team_results': team_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_huanwei_score(cases):
    """计算市容环卫中心5个片区的考核分数和排名"""
    # 定义5个目标环卫片区
    target_areas = [
        "环卫东片区", "环卫北片区", "环卫南片区",
        "环卫西片区", "环卫中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    
    # 按片区分组计算各项指标
    area_results = []
    
    for area_name in target_areas:
        # 筛选该片区的数据
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        # 计算各项指标
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            # 检查结案时间和截止时间
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            # 检查延期次数
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            # 检查返工次数
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        # 计算比率
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        # 计算得分
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        area_results.append({
            'department': area_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {area_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    # 按得分排名
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    # 计算总体数据
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_garden_score(cases):
    """计算园林各片区的考核得分并排名"""
    # 定义5个目标园林片区
    target_areas = [
        "园林东片区", "园林北片区", "园林南片区",
        "园林西片区", "园林中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    
    # 按片区分组计算各项指标
    area_results = []
    
    for area_name in target_areas:
        # 筛选该片区的数据
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        # 计算各项指标
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            # 检查结案时间和截止时间
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            # 检查延期次数
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            # 检查返工次数
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        # 计算比率
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        # 计算得分
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        area_results.append({
            'department': area_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {area_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    # 按得分排名
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    # 计算总体数据
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_park_score(cases):
    """计算园林各公园考核得分（排除挂账案件）"""
    # 定义7个目标公园
    target_parks = ["南风广场", "天逸公园", "体育公园", "航天公园", "圣惠公园", "禹都公园", "人民公园"]
    print(f"目标统计公园：{target_parks}")
    
    # 过滤掉挂账案件
    non_guazhang_cases = []
    for case in cases:
        # 检查当前阶段是否包含挂账
        stage = case.get('当前阶段名称') or ''
        stage_str = str(stage).strip().lower()
        if '挂账' not in stage_str:
            non_guazhang_cases.append(case)
    
    print(f"\n挂账过滤结果：")
    print(f"   - 原始案件数：{len(cases)}")
    print(f"   - 排除挂账后案件数：{len(non_guazhang_cases)}")
    print(f"   - 排除的挂账案件数：{len(cases) - len(non_guazhang_cases)}")
    
    # 按公园分组计算各项指标
    park_results = []
    
    for park_name in target_parks:
        # 筛选该公园的数据
        park_cases = [c for c in non_guazhang_cases if c.get('处置部门') == park_name]
        
        # 计算各项指标
        total = len(park_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in park_cases:
            # 检查结案时间和截止时间
            close_time = case.get('结案时间') or case.get('handle_time')
            deadline = case.get('捆绑处置截止时间') or case.get('deadline')
            
            if close_time and deadline:
                try:
                    if isinstance(close_time, str):
                        close_time = datetime.datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
                    if isinstance(deadline, str):
                        deadline = datetime.datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
                    
                    if close_time < deadline:
                        on_time += 1
                    elif close_time > deadline:
                        overdue += 1
                except:
                    pass
            
            # 检查延期次数
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            # 检查返工次数
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        # 计算比率
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        # 计算得分
        score = (
            (on_time_rate * 1 + overdue_rate * 0.4) * 0.8 +
            (1 - delay_rate) * 0.1 +
            (1 - rework_rate) * 0.1
        ) * 100
        
        park_results.append({
            'department': park_name,
            'total_cases': total,
            'on_time_count': on_time,
            'overdue_count': overdue,
            'delay_count': delay,
            'rework_count': rework,
            'on_time_rate': round(on_time_rate * 100, 2),
            'overdue_rate': round(overdue_rate * 100, 2),
            'delay_rate': round(delay_rate * 100, 2),
            'rework_rate': round(rework_rate * 100, 2),
            'score': round(score, 2)
        })
        
        print(f"  {park_name}: 总数={total}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
    # 按得分排名
    park_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, park in enumerate(park_results, 1):
        park['rank'] = i
    
    print(f"\n排名结果：")
    for park in park_results:
        print(f"  第{park['rank']}名：{park['department']} - {park['score']}分")
    
    # 计算总体数据
    total_cases = sum(p['total_cases'] for p in park_results)
    total_score = sum(p['score'] for p in park_results) / len(park_results)
    
    return {
        'total_cases': total_cases,
        'team_results': park_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_generic_score(cases):
    """其他部门的通用计算逻辑"""
    total_cases = len(cases)
    closed_cases = 0
    total_handle_hours = 0
    valid_cases = 0
    
    for case in cases:
        # 检查状态列
        status = case.get('status') or case.get('状态')
        if status and '已结案' in str(status):
            closed_cases += 1
        
        # 计算处理时间
        create_time = case.get('create_time') or case.get('创建时间') or case.get('create_time')
        handle_time = case.get('handle_time') or case.get('处理时间') or case.get('完成时间')
        
        if create_time and handle_time:
            try:
                # 尝试解析时间
                if isinstance(create_time, str):
                    create_time = datetime.datetime.strptime(create_time, '%Y-%m-%d %H:%M:%S')
                if isinstance(handle_time, str):
                    handle_time = datetime.datetime.strptime(handle_time, '%Y-%m-%d %H:%M:%S')
                handle_hours = (handle_time - create_time).total_seconds() / 3600
                total_handle_hours += handle_hours
                valid_cases += 1
            except Exception as e:
                print(f'解析时间失败: {e}')
    
    # 计算各项指标
    avg_handle_hours = total_handle_hours / valid_cases if valid_cases > 0 else 0
    
    # 标准处理时间（示例：24小时）
    standard_hours = 24
    
    # 计算得分
    closure_rate = (closed_cases / total_cases) * 40 if total_cases > 0 else 0
    time_score = max(0, (standard_hours - avg_handle_hours) / standard_hours * 30) if standard_hours > 0 else 0
    quality_score = 30  # 示例值，实际需要根据质量评估
    
    total_score = closure_rate + time_score + quality_score
    
    return {
        'total_cases': total_cases,
        'closed_cases': closed_cases,
        'avg_handle_hours': round(avg_handle_hours, 2),
        'score': round(total_score, 2),
        'details': {
            '结案率': round(closure_rate, 2),
            '时间得分': round(time_score, 2),
            '质量得分': round(quality_score, 2)
        }
    }

def call_doubao_api(prompt, data_summary, analysis_type):
    """调用豆包大模型API进行分析"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    # 根据分析类型设置系统提示
    if analysis_type == 'time_analysis':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件时间分布数据。请根据提供的数据摘要，生成详细的时间分析报告。"
        user_prompt = f"请分析以下案件数据的时间分布特征：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 日案件量趋势分析\n2. 高峰时段分析（小时级）\n3. 提供相关数据洞察和建议\n\n注意：只需要分析日案件量趋势和高峰时段，不需要分析月度、周度或其他时间维度。"
    elif analysis_type == 'space_analysis':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件空间分布数据。请根据提供的数据摘要，生成详细的空间分析报告。"
        user_prompt = f"请分析以下案件数据的空间分布特征：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 各街道/社区/片区案件密度分析\n2. 高发区域热力图分析\n3. 重点关注地址描述、所属街道、所属社区、所属片区以及小类名称字段\n4. 提供相关数据洞察和建议"
    elif analysis_type == 'source_analysis':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件来源数据。请根据提供的数据摘要，生成详细的案件来源分析报告。"
        user_prompt = f"请分析以下案件数据的来源特征：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 案件来源分布分析\n2. 不同来源渠道的案件特征分析\n3. 重点关注问题来源字段\n4. 提供相关数据洞察和建议"
    elif analysis_type == 'type_analysis':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件类型数据。请根据提供的数据摘要，生成详细的案件类型分析报告。"
        user_prompt = f"请分析以下案件数据的类型特征：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 主要案件类型特点分析\n2. 案件类型分布规律分析\n3. 重点关注问题类型、大类名称、小类名称字段\n4. 提供相关数据洞察和建议\n5. 返回图表和分析内容"
    elif analysis_type == 'duplicate_analysis':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件重复情况。请根据提供的数据摘要，生成详细的重复案件分析报告。"
        user_prompt = f"请分析以下案件数据的重复情况：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 基于问题描述和地址描述字段分析案件重复情况\n2. 识别高重复的案件群体\n3. 分析重复案件的特征和规律\n4. 提供相关数据洞察和建议\n5. 返回高重复案件TOP列表\n6. 返回图表和分析内容"
    elif analysis_type == 'monthly_comparison':
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件月度对比数据。请根据提供的数据摘要，生成详细的月度对比分析报告。"
        user_prompt = f"请分析以下案件数据的月度对比情况：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 基于捆绑处置截止时间字段分析上月与本月案件数量的变化\n2. 分析案件大小类别变化的情况\n3. 分析哪些问题变突出了，哪些问题有所下降\n4. 提供相关数据洞察和建议\n5. 基于案件重复情况进行分析\n6. 返回图表和分析内容"
    else:
        system_prompt = "你是一个专业的数据分析助手，擅长分析案件数据。请根据提供的数据摘要，生成详细的分析报告。"
        user_prompt = f"请分析以下案件数据：\n{prompt}\n\n数据摘要：{data_summary}\n\n分析要求：\n1. 基于数据特征进行全面分析\n2. 提供相关数据洞察和建议"
    
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }
    
    # 优化：增加重试机制
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # 优化：增加连接超时和读取超时设置
            # 合并请求头
            combined_headers = {
                **headers,
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            }
            
            response = requests.post(
                API_URL, 
                headers=combined_headers, 
                json=payload, 
                timeout=(10, 300)  # 连接超时10秒，读取超时300秒
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                print(f"API调用超时，{retry_delay}秒后重试... (尝试 {attempt+1}/{max_retries})")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                return f"API调用失败: 多次尝试后仍然超时 - {str(e)}"
        except Exception as e:
            return f"API调用失败: {str(e)}"

@app.route('/api/assess', methods=['POST'])
@protected
def assess():
    try:
        data = request.json
        table_name = data.get('table_name')
        department = data.get('department')
        
        if not table_name or not department:
            return jsonify({'error': 'Missing table_name or department'}), 400
        
        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)
        cases = df.to_dict('records')
        
        # 根据部门选择计算逻辑
        if department == '城市综合行政执法队':
            result = calculate_law_enforcement_score(cases)
        elif department == '市容环卫中心':
            result = calculate_huanwei_score(cases)
        elif department == '园林绿化服务中心（片区）':
            result = calculate_garden_score(cases)
        elif department == '园林绿化服务中心（公园广场）':
            result = calculate_park_score(cases)
        else:
            result = calculate_generic_score(cases)
        
        # 添加元数据
        result['department'] = department
        result['table_name'] = table_name
        
        return jsonify(convert_nan_to_null(result)), 200
    except Exception as e:
        print(f"Error in assess: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 案件抽查模块API
@app.route('/api/spotcheck', methods=['POST'])
@protected
def spotcheck():
    session = Session()
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        # 检查文件类型
        allowed_extensions = {'.docx', '.xlsx'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            return jsonify({'error': 'Only docx and xlsx files are allowed'}), 400
        
        # 读取文件内容
        file_content = read_file_content(file)
        
        # 构建大模型提示
        prompt = f"请分析以下城市管理案件详情：\n{file_content}\n\n重要提示：处置时间是按照8小时工作时计算的，不是自然时间，且节假日和周末也不计时。\n\n分析要求：\n1、采集信息是否准确；\n2、受理、派遣、处置流程的时效（注意：处置时间按8小时工作时计算，节假日和周末不计时）；\n3、结案是否规范；\n4、是否有推诿扯皮现象；\n并分别给采集、受理、派遣、处置打分（0-100分），分析内容尽量简短。"
        
        # 调用大模型API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
        
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的城市管理案件分析助手，擅长分析案件处理流程和质量。请根据提供的案件详情，生成详细的分析报告。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        # 调用API，添加重试机制
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    API_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=(10, 300)  # 连接超时10秒，读取超时300秒
                )
                response.raise_for_status()
                result = response.json()
                analysis_content = result['choices'][0]['message']['content']
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"API调用失败，{retry_delay}秒后重试... (尝试 {attempt+1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    raise Exception(f"大模型API调用失败，请稍后重试: {str(e)}")
        
        # 解析评分结果（简化处理，实际可能需要更复杂的解析）
        scores = {
            'collection': 85,  # 默认值，实际应从分析结果中提取
            'acceptance': 80,
            'dispatch': 75,
            'disposal': 82
        }
        
        session.commit()
        return jsonify({
            'analysis': analysis_content,
            'scores': scores,
            'file_name': file.filename,
            'file_content': file_content  # 返回读取到的文件内容，用于前端显示
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in spotcheck: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/analyze', methods=['POST'])
@protected
def analyze():
    try:
        data = request.json
        table_name = data.get('table_name')
        analysis_type = data.get('analysis_type')
        
        if not table_name or not analysis_type:
            return jsonify({'error': 'Missing table_name or analysis_type'}), 400
        
        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)
        
        # 基础结果
        result = {
            'table_name': table_name,
            'analysis_type': analysis_type,
            'data_summary': f'Table has {len(df)} rows and {len(df.columns)} columns',
            'columns': df.columns.tolist(),
            'sample_data': df.head(5).to_dict('records')
        }
        
        # 案件时间分析
        if analysis_type == 'time_analysis':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 上报时间：案件的上报时间\n"
            prompt += f"- 小类名称：案件的具体类型\n"
            prompt += f"- 提取的道路名称：案件发生的位置\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '上报时间': None,
                '小类名称': None,
                '提取的道路名称': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '上报' in col:
                    # 优先匹配「上报时间」字段
                    key_fields['上报时间'] = col
                elif '小类' in col or '类型' in col_lower:
                    key_fields['小类名称'] = col
                elif '道路' in col or '路名' in col or '街' in col:
                    key_fields['提取的道路名称'] = col
            
            # 如果没有找到上报时间，再尝试其他时间字段
            if not key_fields['上报时间']:
                for col in df.columns:
                    if '时间' in col:
                        key_fields['上报时间'] = col
                        break
            
            # 保存原始数据副本
            original_df = df.copy()
            
            # 分析上报时间
            time_col = key_fields['上报时间']
            if time_col:
                try:
                    # 处理各种时间格式，包括非标准格式
                    def parse_time_string(time_str):
                        if not time_str:
                            return pd.NaT
                        
                        if isinstance(time_str, str):
                            # 处理 GMT 格式：Wed, 31 Dec 2025 15:02:18 GMT
                            if 'GMT' in time_str:
                                try:
                                    # 移除星期和 GMT 时区
                                    time_str = time_str.split(', ')[1].replace(' GMT', '')
                                    # 转换为标准格式
                                    return pd.to_datetime(time_str, format='%d %b %Y %H:%M:%S')
                                except:
                                    pass
                            
                            # 处理相对时间格式：1小时55分18秒
                            if any(unit in time_str for unit in ['小时', '分', '秒']):
                                # 对于相对时间，返回 NaT，因为无法转换为绝对时间
                                return pd.NaT
                            
                            # 尝试多种标准格式
                            formats = ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']
                            for fmt in formats:
                                try:
                                    return pd.to_datetime(time_str, format=fmt)
                                except:
                                    pass
                        
                        # 最后的尝试，让 pandas 自动解析
                        try:
                            return pd.to_datetime(time_str)
                        except:
                            return pd.NaT
                    
                    # 应用时间解析函数
                    df[time_col] = df[time_col].apply(parse_time_string)
                    
                    # 移除无法解析的时间值
                    original_count = len(df)
                    df = df.dropna(subset=[time_col])
                    valid_count = len(df)
                    
                    # 添加数据统计信息
                    prompt += f"\n数据统计信息：\n"
                    prompt += f"总记录数：{original_count}\n"
                    prompt += f"有效时间记录数：{valid_count}\n"
                    prompt += f"时间解析成功率：{valid_count/original_count:.2%}\n"
                    
                    if valid_count > 0:
                        # 统一转换为 YYYY-MM-DD HH:MM:SS 格式
                        df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
                        # 重新转换为 datetime 类型以提取特征
                        df[time_col] = pd.to_datetime(df[time_col])
                        
                        # 提取时间特征
                        df['day'] = df[time_col].dt.day
                        df['hour'] = df[time_col].dt.hour
                        
                        # 日案件量趋势
                        daily_counts = df.groupby('day').size().reset_index(name='count')
                        prompt += f"\n日案件量趋势：\n{daily_counts.to_string(index=False)}"
                        
                        # 高峰时段分析（小时级）
                        hourly_counts = df.groupby('hour').size().reset_index(name='count')
                        prompt += f"\n小时级高峰时段分析：\n{hourly_counts.to_string(index=False)}"
                        
                        # 计算高峰时段
                        peak_hours = hourly_counts.sort_values('count', ascending=False).head(3)
                        prompt += f"\nTop 3 高峰时段：\n{peak_hours.to_string(index=False)}"
                        
                        # 添加图表数据到结果
                        result['chart_data'] = {
                            'daily': daily_counts.to_dict('records'),
                            'hourly': hourly_counts.to_dict('records'),
                            'peak_hours': peak_hours.to_dict('records')
                        }
                    else:
                        prompt += "\n警告：所有时间值均无法解析，无法进行时间维度分析。\n"
                        # 使用原始数据进行其他分析
                        df = original_df
                    
                except Exception as e:
                    prompt += f"\n时间列转换失败：{str(e)}"
                    # 即使时间处理失败，也要添加基本数据统计
                    prompt += f"\n基本数据统计：\n总记录数：{len(df)}\n"
            
            # 分析小类名称
            category_col = key_fields['小类名称']
            if category_col:
                try:
                    category_counts = df[category_col].value_counts().head(10).reset_index()
                    category_counts.columns = [category_col, 'count']
                    prompt += f"\n案件类型分布（前10）：\n{category_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n类型分析失败：{str(e)}"
            
            # 分析道路名称
            road_col = key_fields['提取的道路名称']
            if road_col:
                try:
                    road_counts = df[road_col].value_counts().head(10).reset_index()
                    road_counts.columns = [road_col, 'count']
                    prompt += f"\n案件高发区域（前10）：\n{road_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n区域分析失败：{str(e)}"
            
            # 调用豆包大模型
            # 调整提示词，只关注日案件量趋势和高峰时段分析
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 案件空间分析
        elif analysis_type == 'space_analysis':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 地址描述：案件发生的详细地址\n"
            prompt += f"- 所属街道：案件所属的街道\n"
            prompt += f"- 所属社区：案件所属的社区\n"
            prompt += f"- 所属片区：案件所属的片区\n"
            prompt += f"- 小类名称：案件的具体类型\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '地址描述': None,
                '所属街道': None,
                '所属社区': None,
                '所属片区': None,
                '小类名称': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '地址' in col or '位置' in col_lower:
                    key_fields['地址描述'] = col
                elif '街道' in col:
                    key_fields['所属街道'] = col
                elif '社区' in col:
                    key_fields['所属社区'] = col
                elif '片区' in col or '区域' in col_lower:
                    key_fields['所属片区'] = col
                elif '小类' in col or '类型' in col_lower:
                    key_fields['小类名称'] = col
            
            # 分析所属街道
            street_col = key_fields['所属街道']
            if street_col:
                try:
                    street_counts = df[street_col].value_counts().head(10).reset_index()
                    street_counts.columns = [street_col, 'count']
                    prompt += f"\n各街道案件密度（前10）：\n{street_counts.to_string(index=False)}"
                    
                    # 添加街道案件密度数据到结果
                    result['chart_data'] = {
                        'street': street_counts.to_dict('records')
                    }
                except Exception as e:
                    prompt += f"\n街道分析失败：{str(e)}"
            
            # 分析所属社区
            community_col = key_fields['所属社区']
            if community_col:
                try:
                    community_counts = df[community_col].value_counts().head(10).reset_index()
                    community_counts.columns = [community_col, 'count']
                    prompt += f"\n各社区案件密度（前10）：\n{community_counts.to_string(index=False)}"
                    
                    # 添加社区案件密度数据到结果
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['community'] = community_counts.to_dict('records')
                except Exception as e:
                    prompt += f"\n社区分析失败：{str(e)}"
            
            # 分析所属片区
            area_col = key_fields['所属片区']
            if area_col:
                try:
                    area_counts = df[area_col].value_counts().head(10).reset_index()
                    area_counts.columns = [area_col, 'count']
                    prompt += f"\n各片区案件密度（前10）：\n{area_counts.to_string(index=False)}"
                    
                    # 添加片区案件密度数据到结果
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['area'] = area_counts.to_dict('records')
                except Exception as e:
                    prompt += f"\n片区分析失败：{str(e)}"
            
            # 分析地址描述
            address_col = key_fields['地址描述']
            if address_col:
                try:
                    address_counts = df[address_col].value_counts().head(10).reset_index()
                    address_counts.columns = [address_col, 'count']
                    prompt += f"\n高发地址（前10）：\n{address_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n地址分析失败：{str(e)}"
            
            # 分析小类名称
            category_col = key_fields['小类名称']
            if category_col:
                try:
                    category_counts = df[category_col].value_counts().head(10).reset_index()
                    category_counts.columns = [category_col, 'count']
                    prompt += f"\n案件类型分布（前10）：\n{category_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n类型分析失败：{str(e)}"
            
            # 调用豆包大模型
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 对比上月分析
        elif analysis_type == 'monthly_comparison':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 捆绑处置截止时间：案件的处置截止时间，用于判断案件所属月份\n"
            prompt += f"- 小类名称：案件的具体类型\n"
            prompt += f"- 问题描述：案件的问题描述\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '捆绑处置截止时间': None,
                '小类名称': None,
                '问题描述': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '捆绑' in col and '截止' in col and '时间' in col:
                    key_fields['捆绑处置截止时间'] = col
                elif '小类' in col or '类型' in col_lower:
                    key_fields['小类名称'] = col
                elif '问题' in col and '描述' in col:
                    key_fields['问题描述'] = col
            
            # 分析捆绑处置截止时间
            time_col = key_fields['捆绑处置截止时间']
            if time_col:
                try:
                    # 处理各种时间格式
                    def parse_time_string(time_str):
                        if not time_str:
                            return pd.NaT
                        
                        if isinstance(time_str, str):
                            # 处理 GMT 格式：Wed, 31 Dec 2025 15:02:18 GMT
                            if 'GMT' in time_str:
                                try:
                                    # 移除星期和 GMT 时区
                                    time_str = time_str.split(', ')[1].replace(' GMT', '')
                                    # 转换为标准格式
                                    return pd.to_datetime(time_str, format='%d %b %Y %H:%M:%S')
                                except:
                                    pass
                            
                            # 处理相对时间格式：1小时55分18秒
                            if any(unit in time_str for unit in ['小时', '分', '秒']):
                                # 对于相对时间，返回 NaT
                                return pd.NaT
                            
                            # 尝试多种标准格式
                            formats = ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']
                            for fmt in formats:
                                try:
                                    return pd.to_datetime(time_str, format=fmt)
                                except:
                                    pass
                        
                        # 最后的尝试，让 pandas 自动解析
                        try:
                            return pd.to_datetime(time_str)
                        except:
                            return pd.NaT
                    
                    # 应用时间解析函数
                    df[time_col] = df[time_col].apply(parse_time_string)
                    
                    # 移除无法解析的时间值
                    original_count = len(df)
                    df = df.dropna(subset=[time_col])
                    valid_count = len(df)
                    
                    # 添加数据统计信息
                    prompt += f"\n数据统计信息：\n"
                    prompt += f"总记录数：{original_count}\n"
                    prompt += f"有效时间记录数：{valid_count}\n"
                    prompt += f"时间解析成功率：{valid_count/original_count:.2%}\n"
                    
                    if valid_count > 0:
                        # 提取月份信息
                        df['month'] = df[time_col].dt.to_period('M')
                        
                        # 获取表中所有唯一的月份并按降序排序
                        unique_months = sorted(df['month'].unique(), reverse=True)
                        
                        # 确保有至少两个月的数据
                        if len(unique_months) >= 2:
                            # 选择最近的两个月份
                            recent_month = unique_months[0]
                            previous_month = unique_months[1]
                            
                            # 筛选两个月的数据
                            recent_month_data = df[df['month'] == recent_month]
                            previous_month_data = df[df['month'] == previous_month]
                            
                            # 计算案件数量变化
                            recent_count = len(recent_month_data)
                            previous_count = len(previous_month_data)
                            count_change = recent_count - previous_count
                            count_change_rate = (count_change / previous_count * 100) if previous_count > 0 else 0
                            
                            # 格式化月份显示
                            recent_month_str = recent_month.strftime('%Y-%m')
                            previous_month_str = previous_month.strftime('%Y-%m')
                            
                            prompt += f"\n案件数量变化：\n"
                            prompt += f"{previous_month_str}案件数：{previous_count}\n"
                            prompt += f"{recent_month_str}案件数：{recent_count}\n"
                            prompt += f"变化量：{count_change}\n"
                            prompt += f"变化率：{count_change_rate:.2f}%\n"
                            
                            # 添加案件数量对比数据到结果
                            result['chart_data'] = {
                                'monthly_comparison': [
                                    {'month': previous_month_str, 'count': previous_count},
                                    {'month': recent_month_str, 'count': recent_count}
                                ]
                            }
                            
                            # 分析案件大小类别变化
                            category_col = key_fields['小类名称']
                            if category_col:
                                try:
                                    # 计算两个月的案件类型分布
                                    previous_category_counts = previous_month_data[category_col].value_counts().head(10).reset_index()
                                    previous_category_counts.columns = [category_col, 'count']
                                    
                                    recent_category_counts = recent_month_data[category_col].value_counts().head(10).reset_index()
                                    recent_category_counts.columns = [category_col, 'count']
                                    
                                    prompt += f"\n{previous_month_str}案件类型分布（前10）：\n{previous_category_counts.to_string(index=False)}\n"
                                    prompt += f"\n{recent_month_str}案件类型分布（前10）：\n{recent_category_counts.to_string(index=False)}\n"
                                    
                                    # 分析类型变化
                                    previous_categories = set(previous_category_counts[category_col])
                                    recent_categories = set(recent_category_counts[category_col])
                                    
                                    # 新增的类型
                                    new_categories = recent_categories - previous_categories
                                    # 减少的类型
                                    reduced_categories = previous_categories - recent_categories
                                    
                                    prompt += f"\n案件类型变化：\n"
                                    prompt += f"新增类型：{list(new_categories) if new_categories else '无'}\n"
                                    prompt += f"减少类型：{list(reduced_categories) if reduced_categories else '无'}\n"
                                    
                                    # 添加案件大小类别对比数据到结果
                                    if 'chart_data' not in result:
                                        result['chart_data'] = {}
                                    result['chart_data']['case_size_comparison'] = [
                                        {'type': previous_month_str, 'categories': previous_category_counts.to_dict('records')},
                                        {'type': recent_month_str, 'categories': recent_category_counts.to_dict('records')}
                                    ]
                                    
                                except Exception as e:
                                    prompt += f"\n案件类型分析失败：{str(e)}\n"
                            
                            # 分析问题变化
                            problem_col = key_fields['问题描述']
                            if problem_col:
                                try:
                                    # 计算两个月的问题描述分布
                                    previous_problem_counts = previous_month_data[problem_col].value_counts().head(10).reset_index()
                                    previous_problem_counts.columns = [problem_col, 'count']
                                    
                                    recent_problem_counts = recent_month_data[problem_col].value_counts().head(10).reset_index()
                                    recent_problem_counts.columns = [problem_col, 'count']
                                    
                                    prompt += f"\n{previous_month_str}问题描述分布（前10）：\n{previous_problem_counts.to_string(index=False)}\n"
                                    prompt += f"\n{recent_month_str}问题描述分布（前10）：\n{recent_problem_counts.to_string(index=False)}\n"
                                    
                                    # 分析问题变化
                                    previous_problems = set(previous_problem_counts[problem_col])
                                    recent_problems = set(recent_problem_counts[problem_col])
                                    
                                    # 新增的问题
                                    new_problems = recent_problems - previous_problems
                                    # 减少的问题
                                    reduced_problems = previous_problems - recent_problems
                                    
                                    prompt += f"\n问题变化：\n"
                                    prompt += f"新增问题：{list(new_problems) if new_problems else '无'}\n"
                                    prompt += f"减少问题：{list(reduced_problems) if reduced_problems else '无'}\n"
                                    
                                    # 添加问题趋势数据到结果
                                    if 'chart_data' not in result:
                                        result['chart_data'] = {}
                                    result['chart_data']['problem_trend'] = [
                                        {'type': previous_month_str, 'problems': previous_problem_counts.to_dict('records')},
                                        {'type': recent_month_str, 'problems': recent_problem_counts.to_dict('records')}
                                    ]
                                    
                                except Exception as e:
                                    prompt += f"\n问题描述分析失败：{str(e)}\n"
                        else:
                            prompt += "\n警告：表中数据不足两个月，无法进行月度对比分析。\n"
                            prompt += f"表中包含的月份：{[m.strftime('%Y-%m') for m in unique_months] if unique_months else '无'}\n"
                    else:
                        prompt += "\n警告：所有时间值均无法解析，无法进行月度对比分析。\n"
                    
                except Exception as e:
                    prompt += f"\n时间列转换失败：{str(e)}\n"
                    # 即使时间处理失败，也要添加基本数据统计
                    prompt += f"\n基本数据统计：\n总记录数：{len(df)}\n"
            
            # 调用豆包大模型
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 案件来源分析
        elif analysis_type == 'source_analysis':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 问题来源：案件的来源渠道\n"
            prompt += f"- 小类名称：案件的具体类型\n"
            prompt += f"- 地址描述：案件发生的详细地址\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '问题来源': None,
                '小类名称': None,
                '地址描述': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '来源' in col or '渠道' in col_lower:
                    key_fields['问题来源'] = col
                elif '小类' in col or '类型' in col_lower:
                    key_fields['小类名称'] = col
                elif '地址' in col or '位置' in col_lower:
                    key_fields['地址描述'] = col
            
            # 分析问题来源
            source_col = key_fields['问题来源']
            if source_col:
                try:
                    source_counts = df[source_col].value_counts().head(10).reset_index()
                    source_counts.columns = [source_col, 'count']
                    prompt += f"\n案件来源分布（前10）：\n{source_counts.to_string(index=False)}"
                    
                    # 添加来源分布数据到结果
                    result['chart_data'] = {
                        'source': source_counts.to_dict('records')
                    }
                except Exception as e:
                    prompt += f"\n来源分析失败：{str(e)}"
            
            # 分析小类名称
            category_col = key_fields['小类名称']
            if category_col:
                try:
                    category_counts = df[category_col].value_counts().head(10).reset_index()
                    category_counts.columns = [category_col, 'count']
                    prompt += f"\n案件类型分布（前10）：\n{category_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n类型分析失败：{str(e)}"
            
            # 分析地址描述
            address_col = key_fields['地址描述']
            if address_col:
                try:
                    address_counts = df[address_col].value_counts().head(10).reset_index()
                    address_counts.columns = [address_col, 'count']
                    prompt += f"\n高发地址（前10）：\n{address_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n地址分析失败：{str(e)}"
            
            # 调用豆包大模型
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 案件类型分析
        elif analysis_type == 'type_analysis':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 问题类型：案件的问题类型\n"
            prompt += f"- 大类名称：案件的大类名称\n"
            prompt += f"- 小类名称：案件的具体类型\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '问题类型': None,
                '大类名称': None,
                '小类名称': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '问题' in col and '类型' in col:
                    key_fields['问题类型'] = col
                elif '大类' in col:
                    key_fields['大类名称'] = col
                elif '小类' in col or '类型' in col_lower:
                    key_fields['小类名称'] = col
            
            # 分析问题类型
            problem_type_col = key_fields['问题类型']
            if problem_type_col:
                try:
                    problem_type_counts = df[problem_type_col].value_counts().head(10).reset_index()
                    problem_type_counts.columns = [problem_type_col, 'count']
                    prompt += f"\n问题类型分布（前10）：\n{problem_type_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n问题类型分析失败：{str(e)}"
            
            # 分析大类名称
            category_col = key_fields['大类名称']
            if category_col:
                try:
                    category_counts = df[category_col].value_counts().head(10).reset_index()
                    category_counts.columns = [category_col, 'count']
                    prompt += f"\n大类名称分布（前10）：\n{category_counts.to_string(index=False)}"
                except Exception as e:
                    prompt += f"\n大类分析失败：{str(e)}"
            
            # 分析小类名称
            subcategory_col = key_fields['小类名称']
            if subcategory_col:
                try:
                    subcategory_counts = df[subcategory_col].value_counts().head(10).reset_index()
                    subcategory_counts.columns = [subcategory_col, 'count']
                    prompt += f"\n小类名称分布（前10）：\n{subcategory_counts.to_string(index=False)}"
                    
                    # 添加小类分布数据到结果
                    result['chart_data'] = {
                        'type': subcategory_counts.to_dict('records')
                    }
                except Exception as e:
                    prompt += f"\n小类分析失败：{str(e)}"
            
            # 调用豆包大模型
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 案件重复分析
        elif analysis_type == 'duplicate_analysis':
            # 生成分析提示
            prompt = f"数据表 {table_name} 包含以下关键字段：\n"
            prompt += f"- 问题描述：案件的问题描述\n"
            prompt += f"- 地址描述：案件发生的详细地址\n"
            prompt += f"数据总量：{len(df)} 条记录\n"
            
            # 重点分析字段
            key_fields = {
                '问题描述': None,
                '地址描述': None
            }
            
            # 查找关键字段
            for col in df.columns:
                col_lower = col.lower()
                if '问题' in col and '描述' in col:
                    key_fields['问题描述'] = col
                elif '描述' in col and '问题' in col:
                    key_fields['问题描述'] = col
                elif '地址' in col and '描述' in col:
                    key_fields['地址描述'] = col
                elif '描述' in col and '地址' in col:
                    key_fields['地址描述'] = col
                elif '问题' in col and key_fields['问题描述'] is None:
                    key_fields['问题描述'] = col
                elif '地址' in col and key_fields['地址描述'] is None:
                    key_fields['地址描述'] = col
            
            # 分析问题描述字段
            problem_col = key_fields['问题描述']
            if problem_col:
                try:
                    # 计算每个问题描述的出现次数
                    problem_counts = df[problem_col].value_counts().head(10).reset_index()
                    problem_counts.columns = [problem_col, 'count']
                    prompt += f"\n问题描述重复情况（前10）：\n{problem_counts.to_string(index=False)}"
                    
                    # 添加问题描述重复数据到结果
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['problem_duplicates'] = problem_counts.to_dict('records')
                except Exception as e:
                    prompt += f"\n问题描述分析失败：{str(e)}"
            
            # 分析地址描述字段
            address_col = key_fields['地址描述']
            if address_col:
                try:
                    # 计算每个地址描述的出现次数
                    address_counts = df[address_col].value_counts().head(10).reset_index()
                    address_counts.columns = [address_col, 'count']
                    prompt += f"\n地址描述重复情况（前10）：\n{address_counts.to_string(index=False)}"
                    
                    # 添加地址重复数据到结果
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['address_duplicates'] = address_counts.to_dict('records')
                    
                    # 分析地址描述类型占比（模糊地址vs精准地址）
                    def is_precise_address(address):
                        if not address:
                            return False
                        address_str = str(address)
                        # 简单判断：包含具体门牌号、楼栋号等信息的为精准地址
                        precise_keywords = ['号', '栋', '楼', '室', '店', '铺', '单元', '号楼']
                        vague_keywords = ['附近', '周边', '旁边', '一带', '附近区域']
                        
                        # 检查是否包含模糊关键词
                        for keyword in vague_keywords:
                            if keyword in address_str:
                                return False
                        
                        # 检查是否包含精准关键词
                        for keyword in precise_keywords:
                            if keyword in address_str:
                                return True
                        
                        # 默认判断
                        return len(address_str) > 10
                    
                    # 统计地址类型
                    address_types = []
                    for address in df[address_col].dropna():
                        if is_precise_address(address):
                            address_types.append('精准地址')
                        else:
                            address_types.append('模糊地址')
                    
                    # 计算占比
                    type_series = pd.Series(address_types)
                    type_counts = type_series.value_counts().reset_index()
                    type_counts.columns = ['type', 'count']
                    
                    prompt += f"\n地址描述类型占比：\n{type_counts.to_string(index=False)}"
                    result['chart_data']['address_type_distribution'] = type_counts.to_dict('records')
                    
                except Exception as e:
                    prompt += f"\n地址描述分析失败：{str(e)}"
            
            # 如果两个字段都存在，分析它们的组合
            if problem_col and address_col:
                try:
                    # 组合问题描述和地址描述
                    df['combined_key'] = df[problem_col].astype(str) + ' | ' + df[address_col].astype(str)
                    # 计算组合键的出现次数
                    combined_counts = df['combined_key'].value_counts().head(10).reset_index()
                    combined_counts.columns = ['combined_key', 'count']
                    prompt += f"\n问题和地址组合重复情况（前10）：\n{combined_counts.to_string(index=False)}"
                    
                    # 添加组合重复数据到结果
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['combined_duplicates'] = combined_counts.to_dict('records')
                except Exception as e:
                    prompt += f"\n组合分析失败：{str(e)}"
            
            # 分析重复案件违规类型占比
            if problem_col:
                try:
                    # 简单的违规类型分类
                    def categorize_violation(problem):
                        if not problem:
                            return '其他违规'
                        problem_str = str(problem).lower()
                        if '店外' in problem_str or '占道' in problem_str:
                            return '店外经营'
                        elif '流动' in problem_str or '摊' in problem_str:
                            return '流动摊点'
                        else:
                            return '其他违规'
                    
                    # 统计违规类型
                    violation_types = []
                    for problem in df[problem_col].dropna():
                        violation_types.append(categorize_violation(problem))
                    
                    # 计算占比
                    violation_series = pd.Series(violation_types)
                    violation_counts = violation_series.value_counts().reset_index()
                    violation_counts.columns = ['type', 'count']
                    
                    prompt += f"\n重复案件违规类型占比：\n{violation_counts.to_string(index=False)}"
                    if 'chart_data' not in result:
                        result['chart_data'] = {}
                    result['chart_data']['violation_type_distribution'] = violation_counts.to_dict('records')
                    
                except Exception as e:
                    prompt += f"\n违规类型分析失败：{str(e)}"
            
            # 调用豆包大模型
            analysis_result = call_doubao_api(prompt, result['data_summary'], analysis_type)
            result['analysis'] = analysis_result
        
        # 转换NaN值为null值，确保JSON响应有效
        result = convert_nan_to_null(result)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# CMS栏目相关API

@app.route('/api/categories', methods=['GET'])
def get_categories():
    # 创建新的session实例
    session = Session()
    try:
        # 获取所有栏目，按排序字段排序
        categories = session.query(Category).order_by(Category.order).all()
        
        # 转换为字典列表
        categories_list = []
        for category in categories:
            categories_list.append({
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'order': category.order,
                'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S') if category.created_at else None,
                'updated_at': category.updated_at.strftime('%Y-%m-%d %H:%M:%S') if category.updated_at else None
            })
        
        session.commit()
        return jsonify({'categories': categories_list}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 生成slug函数
def generate_slug(text):
    import re
    import hashlib
    # 转换为小写
    slug = text.lower()
    # 替换空格为连字符
    slug = re.sub(r'\s+', '-', slug)
    # 保留中文和字母数字连字符
    slug = re.sub(r'[^\u4e00-\u9fa5a-z0-9-]', '', slug)
    # 替换多个连字符为单个
    slug = re.sub(r'-+', '-', slug)
    # 移除首尾连字符
    slug = slug.strip('-')
    # 如果slug为空，使用标题的哈希值
    if not slug:
        slug = hashlib.md5(text.encode()).hexdigest()[:8]
    return slug

@app.route('/api/categories', methods=['POST'])
@admin_required
def create_category():
    session = Session()
    try:
        data = request.json
        
        # 验证必填字段
        if not data.get('name'):
            return jsonify({'error': '名称不能为空'}), 400
        
        # 自动生成slug
        slug = data.get('slug')
        if not slug:
            slug = generate_slug(data.get('name'))
        
        # 创建新栏目
        new_category = Category(
            name=data.get('name'),
            slug=slug,
            description=data.get('description'),
            order=data.get('order', 0)
        )
        
        session.add(new_category)
        session.commit()
        
        return jsonify({
            'id': new_category.id,
            'name': new_category.name,
            'slug': new_category.slug,
            'description': new_category.description,
            'order': new_category.order
        }), 201
    except Exception as e:
        session.rollback()
        print(f"Error in create_category: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    session = Session()
    try:
        category = session.query(Category).filter_by(id=category_id).first()
        if not category:
            return jsonify({'error': '栏目不存在'}), 404
        
        session.commit()
        return jsonify({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'order': category.order,
            'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S') if category.created_at else None,
            'updated_at': category.updated_at.strftime('%Y-%m-%d %H:%M:%S') if category.updated_at else None
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_category: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    session = Session()
    try:
        data = request.json
        category = session.query(Category).filter_by(id=category_id).first()
        
        if not category:
            return jsonify({'error': '栏目不存在'}), 404
        
        # 更新栏目信息
        if 'name' in data:
            category.name = data['name']
        if 'slug' in data:
            category.slug = data['slug']
        elif 'name' in data:
            # 如果修改了名称但没有提供slug，自动生成
            category.slug = generate_slug(data['name'])
        if 'description' in data:
            category.description = data['description']
        if 'order' in data:
            category.order = data['order']
        
        session.commit()
        
        return jsonify({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'order': category.order
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_category: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    session = Session()
    try:
        print(f"删除栏目请求，category_id: {category_id}")
        category = session.query(Category).filter_by(id=category_id).first()
        print(f"查询到的栏目: {category}")
        if not category:
            print("栏目不存在")
            return jsonify({'error': '栏目不存在'}), 404
        
        # 检查是否有文章属于该栏目
        article_count = session.query(Article).filter_by(category_id=category_id).count()
        print(f"该栏目下的文章数量: {article_count}")
        if article_count > 0:
            print(f"该栏目下还有{article_count}篇文章，无法删除")
            return jsonify({'error': f'该栏目下还有{article_count}篇文章，无法删除'}), 400
        
        # 尝试删除栏目
        session.delete(category)
        session.commit()
        print(f"栏目删除成功，ID: {category_id}")
        return jsonify({'message': '栏目删除成功'}), 200
    except Exception as e:
        session.rollback()
        print(f"删除栏目时出错: {str(e)}")
        # 检查是否是外键约束错误
        if 'foreign key constraint' in str(e).lower():
            return jsonify({'error': '该栏目下还有文章，无法删除'}), 400
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# CMS文章相关API

@app.route('/api/articles', methods=['GET'])
def get_articles():
    # 创建新的session实例
    session = Session()
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        category_id = request.args.get('category_id', type=int)
        status = request.args.get('status')
        include_drafts = request.args.get('include_drafts', 'false').lower() == 'true'
        
        # 构建查询
        query = session.query(Article)
        
        # 应用筛选条件
        if category_id:
            query = query.filter_by(category_id=category_id)
        if status:
            query = query.filter_by(status=status)
        elif not include_drafts:
            # 如果没有指定状态且不包含草稿，只获取已发布的
            query = query.filter_by(status='published')
        
        # 计算总数
        total = query.count()
        
        # 分页
        articles = query.order_by(Article.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
        
        # 转换为字典列表
        articles_list = []
        for article in articles:
            try:
                article_dict = {
                    'id': article.id,
                    'title': article.title,
                    'slug': article.slug,
                    'summary': article.summary,
                    'category_id': article.category_id,
                    'author_id': article.author_id,
                    'status': article.status,
                    'view_count': article.view_count,
                    'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None,
                    'updated_at': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else None,
                    'published_at': article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None
                }
                # 尝试获取file_path字段，如果不存在则跳过
                try:
                    article_dict['file_path'] = article.file_path
                except AttributeError:
                    article_dict['file_path'] = None
                articles_list.append(article_dict)
            except Exception as article_error:
                print(f"Error processing article {article.id}: {str(article_error)}")
                # 跳过有错误的文章，继续处理其他文章
                continue
        
        session.commit()
        return jsonify({
            'articles': articles_list,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_articles: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/articles', methods=['POST'])
@admin_required
def create_article():
    # 创建新的session实例
    session = Session()
    try:
        data = request.json
        
        # 验证必填字段
        if not data.get('title'):
            return jsonify({'error': '标题不能为空'}), 400
        
        # 自动生成slug
        slug = data.get('slug')
        print(f"Original slug from frontend: '{slug}'")
        print(f"if not slug: {not slug}")
        if not slug:
            title = data.get('title')
            print(f"Generating slug from title: '{title}'")
            slug = generate_slug(title)
            print(f"Generated slug: '{slug}'")
        
        # 确保slug唯一
        slug_base = slug
        counter = 1
        while True:
            existing_article = session.query(Article).filter_by(slug=slug).first()
            if not existing_article:
                break
            # slug已存在，添加数字后缀
            slug = f"{slug_base}-{counter}"
            counter += 1
        
        # 创建新文章
        new_article = Article(
            title=data.get('title'),
            slug=slug,
            content=data.get('content'),
            summary=data.get('summary'),
            category_id=data.get('category_id'),
            author_id=request.user_id,
            status=data.get('status', 'draft'),
            file_path=data.get('file_path')
        )
        
        # 如果状态为published，设置发布时间
        if data.get('status') == 'published':
            new_article.published_at = datetime.datetime.utcnow()
        
        session.add(new_article)
        session.commit()
        
        return jsonify({
            'id': new_article.id,
            'title': new_article.title,
            'slug': new_article.slug,
            'summary': new_article.summary,
            'category_id': new_article.category_id,
            'author_id': new_article.author_id,
            'status': new_article.status,
            'file_path': new_article.file_path
        }), 201
    except Exception as e:
        session.rollback()
        print(f"Error in create_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    # 创建新的session实例
    session = Session()
    try:
        article = session.query(Article).filter_by(id=article_id).first()
        if not article:
            return jsonify({'error': '文章不存在'}), 404
        
        # 增加浏览量
        article.view_count += 1
        session.commit()
        
        return jsonify({
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'content': article.content,
            'summary': article.summary,
            'category_id': article.category_id,
            'author_id': article.author_id,
            'status': article.status,
            'view_count': article.view_count,
            'file_path': article.file_path,
            'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None,
            'updated_at': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else None,
            'published_at': article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/articles/<int:article_id>', methods=['PUT'])
@admin_required
def update_article(article_id):
    # 创建新的session实例
    session = Session()
    try:
        data = request.json
        article = session.query(Article).filter_by(id=article_id).first()
        
        if not article:
            return jsonify({'error': '文章不存在'}), 404
        
        # 更新文章信息
        if 'title' in data:
            article.title = data['title']
        if 'slug' in data:
            article.slug = data['slug']
        elif 'title' in data:
            # 如果修改了标题但没有提供slug，自动生成
            article.slug = generate_slug(data['title'])
        if 'content' in data:
            article.content = data['content']
        if 'summary' in data:
            article.summary = data['summary']
        if 'category_id' in data:
            article.category_id = data['category_id']
        if 'status' in data:
            article.status = data['status']
            # 如果状态从draft变为published，设置发布时间
            if data['status'] == 'published' and article.status != 'published':
                article.published_at = datetime.datetime.utcnow()
        if 'file_path' in data:
            article.file_path = data['file_path']
        
        session.commit()
        
        return jsonify({
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'summary': article.summary,
            'category_id': article.category_id,
            'status': article.status
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()



@app.route('/api/articles/<int:article_id>', methods=['DELETE'])
@admin_required
def delete_article(article_id):
    session = Session()
    try:
        article = session.query(Article).filter_by(id=article_id).first()
        if not article:
            return jsonify({'error': '文章不存在'}), 404
        
        session.delete(article)
        session.commit()
        
        return jsonify({'message': '文章删除成功'}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in delete_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/articles/category/<int:category_id>', methods=['GET'])
def get_articles_by_category(category_id):
    session = Session()
    try:
        # 获取查询参数
        include_drafts = request.args.get('include_drafts', 'false').lower() == 'true'
        
        # 构建查询
        query = session.query(Article).filter_by(category_id=category_id)
        
        # 如果不包含草稿，只获取已发布的
        if not include_drafts:
            query = query.filter_by(status='published')
        
        # 执行查询
        articles = query.order_by(Article.created_at.desc()).all()
        
        # 转换为字典列表
        articles_list = []
        for article in articles:
            articles_list.append({
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'summary': article.summary,
                'category_id': article.category_id,
                'view_count': article.view_count,
                'status': article.status,
                'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None,
                'published_at': article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None
            })
        
        session.commit()
        return jsonify({'articles': articles_list}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_articles_by_category: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 配置静态文件服务
import os
app.config['UPLOAD_FOLDER'] = 'uploads'

# 静态文件服务路由
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)