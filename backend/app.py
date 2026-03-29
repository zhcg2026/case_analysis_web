from flask import Flask, request, jsonify, send_from_directory
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
import bcrypt

# 加载环境变量
from dotenv import load_dotenv
# 优先加载 .env.local，其次 .env
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists('../.env.local'):
    load_dotenv('../.env.local')
load_dotenv()  # 加载默认 .env
try:
    from backend.cases_helpers import (
        CASE_CATEGORIES,
        parse_pending_deadline,
        serialize_case,
        apply_case_category_fields,
    )
except ImportError:
    # 兼容在 backend 目录直接执行 python app.py
    from cases_helpers import (
        CASE_CATEGORIES,
        parse_pending_deadline,
        serialize_case,
        apply_case_category_fields,
    )

try:
    from backend.cases_routes import register_case_management_routes
except ImportError:
    from cases_routes import register_case_management_routes

# 导入处理docx文件的库
from docx import Document

# JWT配置（支持环境变量，默认值保持兼容现有部署）
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-for-jwt-token')
TOKEN_EXPIRATION = int(os.getenv('TOKEN_EXPIRATION_SECONDS', str(24 * 60 * 60)))  # 24小时

# 登录失败限制配置
LOGIN_ATTEMPTS = {}  # {username: {'count': int, 'lock_until': timestamp}}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5分钟

# 密码工具函数
def hash_password(password):
    """使用 bcrypt 对密码进行哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """验证密码，支持 bcrypt 和旧版 SHA256 向后兼容"""
    # 检查是否为 bcrypt 哈希（以 $2b$ 开头）
    if hashed.startswith('$2b$'):
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    else:
        # 旧版 SHA256 兼容验证
        return hashlib.sha256(password.encode()).hexdigest() == hashed

def is_strong_password(password):
    """验证密码强度：至少8位，包含字母和数字"""
    if len(password) < 8:
        return False, '密码长度至少8位'
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, '密码必须包含字母和数字'
    return True, None

def check_login_attempts(username):
    """检查登录尝试次数，返回是否允许登录"""
    if username not in LOGIN_ATTEMPTS:
        return True, None

    attempt = LOGIN_ATTEMPTS[username]
    if attempt['count'] >= MAX_LOGIN_ATTEMPTS:
        import time
        if time.time() < attempt['lock_until']:
            remaining = int(attempt['lock_until'] - time.time())
            return False, f'账户已锁定，请{remaining}秒后再试'
        else:
            # 锁定期已过，重置
            LOGIN_ATTEMPTS[username] = {'count': 0, 'lock_until': 0}

    return True, None

def record_failed_login(username):
    """记录登录失败"""
    import time
    if username not in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[username] = {'count': 0, 'lock_until': 0}
    LOGIN_ATTEMPTS[username]['count'] += 1
    if LOGIN_ATTEMPTS[username]['count'] >= MAX_LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[username]['lock_until'] = time.time() + LOCKOUT_DURATION

def clear_login_attempts(username):
    """清除登录失败记录"""
    if username in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[username]
def get_json_payload():
    """获取 JSON 请求体，统一空值处理。"""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def get_case_or_404(session, case_id):
    """统一案件查询，减少重复代码。"""
    case = session.query(Case).filter_by(id=case_id).first()
    if not case:
        return None, (jsonify({'error': '案件不存在'}), 404)
    return case, None


app = Flask(__name__)
# 配置CORS（通过环境变量控制允许的域名）
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')  # 生产环境应设置为具体域名，如 'https://example.com'
if CORS_ORIGINS == '*':
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})
else:
    # 支持多个域名（逗号分隔）
    origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/*": {"origins": origins_list, "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

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

# 数据库配置（必须通过环境变量配置）
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'case_analysis')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '3306')

# 定义占位符类和变量
engine = None
Session = None
Base = None
User = None
Permission = None
Category = None
Article = None

# 尝试初始化数据库（可选）
try:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, Integer, String, DateTime, Text
    from sqlalchemy.sql import func
    from sqlalchemy.orm import sessionmaker

    # 检查必要的数据库配置
    if not all([DB_USER, DB_PASSWORD, DB_HOST]):
        print("警告: 数据库配置不完整，请设置 DB_USER, DB_PASSWORD, DB_HOST 环境变量")
        raise Exception("数据库配置缺失")

    # 创建数据库引擎
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}', pool_pre_ping=True, pool_recycle=3600)
    print("数据库连接成功")
    
    # 定义模型
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
        cases = Column(Integer, nullable=False, default=0)
        map = Column(Integer, nullable=False, default=0)
        huiwentai = Column(Integer, nullable=False, default=0)
        business = Column(Integer, nullable=False, default=0)
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
    
    # 业务平台模型
    class BusinessPlatform(Base):
        __tablename__ = 'business_platforms'
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(100), nullable=False, unique=True)  # 平台名称
        url = Column(String(500), nullable=False)  # 平台地址
        image_path = Column(String(500))  # 封面图片路径
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 案件管理模型
    class Case(Base):
        __tablename__ = 'cases'

        id = Column(Integer, primary_key=True, autoincrement=True)
        task_number = Column(String(50), unique=True, nullable=False)  # 任务号
        stage_light = Column(String(20))  # 阶段红绿灯
        auth_status = Column(String(50))  # 阶段授权状态图标
        supervise_status = Column(String(50))  # 阶段督办状态图标
        report_time = Column(DateTime)  # 上报时间
        source = Column(String(100))  # 问题来源
        major_category = Column(String(100))  # 大类名称
        minor_category = Column(String(100))  # 小类名称
        problem_type = Column(String(50))  # 问题类型
        problem_desc = Column(Text)  # 问题描述
        address_desc = Column(String(500))  # 地址描述
        responsible_grid = Column(String(100))  # 责任网格
        area = Column(String(100))  # 所属区域
        street = Column(String(100))  # 所属街道
        community = Column(String(100))  # 所属社区
        transfer_time = Column(DateTime)  # 批转时间
        current_stage_time_info = Column(String(100))  # 当前阶段时限信息
        current_stage_deadline = Column(DateTime)  # 当前阶段截止时间
        current_stage_remaining_time = Column(String(100))  # 当前阶段剩余时间
        area_level = Column(Integer)  # 区域级别
        area_level_name = Column(String(50))  # 区域级别名称
        responsible_area_name = Column(String(100))  # 责属区域名称
        bundle_deadline = Column(DateTime)  # 捆绑截止时间
        bundle_time_limit = Column(String(50))  # 捆绑截止时限
        photo_path = Column(String(500))  # 图片路径
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

        # 案件管理扩展字段
        category = Column(String(20))           # 案件分类: 非我局管辖/挂账案件/疑难案件
        status = Column(String(20), default='跟进中')  # 状态: 跟进中/已结案
        owner_unit = Column(String(100))        # 权属单位(非我局管辖)
        contact_person = Column(String(50))     # 联系人
        contact_phone = Column(String(20))      # 联系电话
        pending_reason = Column(Text)           # 挂账原因
        pending_deadline = Column(DateTime)     # 预计处置时间
        difficult_type = Column(String(50))     # 疑难类型
        last_follow_time = Column(DateTime)     # 最近跟进时间
        follow_count = Column(Integer, default=0)  # 跟进次数
        close_time = Column(DateTime)           # 结案时间
        close_remark = Column(Text)             # 结案说明
        remark = Column(Text)                   # 备注

    # 系统配置模型
    class SystemConfig(Base):
        __tablename__ = 'system_config'

        id = Column(Integer, primary_key=True, autoincrement=True)
        config_key = Column(String(100), unique=True, nullable=False)  # 配置键
        config_value = Column(Text)  # 配置值（JSON格式）
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 案件跟进模型
    class CaseFollow(Base):
        __tablename__ = 'case_follows'
        id = Column(Integer, primary_key=True, autoincrement=True)
        case_id = Column(Integer, nullable=False)
        follow_type = Column(String(20))      # 发函/协调/督办/其他
        content = Column(Text)
        attachments = Column(Text)            # JSON格式附件路径
        follow_time = Column(DateTime, default=datetime.datetime.now)
        follow_user = Column(String(50))
        created_at = Column(DateTime, default=datetime.datetime.now)

    # 操作日志模型
    class OperationLog(Base):
        __tablename__ = 'operation_logs'
        id = Column(Integer, primary_key=True, autoincrement=True)
        user_id = Column(Integer, nullable=False)
        table_name = Column(String(100))
        operation_type = Column(String(20))   # create, update, delete
        record_id = Column(String(100))       # 任务号或记录ID
        old_value = Column(Text)              # JSON格式，修改前的值
        new_value = Column(Text)              # JSON格式，修改后的值
        created_at = Column(DateTime, default=datetime.datetime.now)

    # 创建数据库表
    # 只创建不存在的表，保留现有数据
    Base.metadata.create_all(engine)

    # 数据库迁移：添加 dashboard 列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM permissions LIKE 'dashboard'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE permissions ADD COLUMN dashboard INT NOT NULL DEFAULT 0 AFTER user_id"))
                conn.commit()
                print("数据库迁移：已添加 dashboard 列")
    except Exception as e:
        print(f"数据库迁移检查: {e}")

    # 创建会话工厂
    Session = sessionmaker(bind=engine)

    # 注册案件管理路由
    register_case_management_routes(
        app=app,
        Session=Session,
        Case=Case,
        CaseFollow=CaseFollow,
        protected=protected,
        get_json_payload=get_json_payload,
        get_case_or_404=get_case_or_404,
        serialize_case=serialize_case,
        CASE_CATEGORIES=CASE_CATEGORIES,
        apply_case_category_fields=apply_case_category_fields,
        parse_pending_deadline=parse_pending_deadline,
    )
    print("案件管理路由注册成功")

except Exception as e:
    print(f"数据库初始化失败: {e}")
    print("应用将以无数据库模式运行（登录和用户管理功能不可用）")
    # 确保这些变量为 None，避免后续出错
    engine = None
    Session = None

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

# 阿里云百炼通用模型API配置
BAILIAN_GENERAL_API_KEY = 'sk-8f9b17ffd00148868cdadcac65220930'
BAILIAN_GENERAL_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
BAILIAN_GENERAL_MODEL = 'qwen-plus'

# 阿里云百炼城管通专用应用API配置
BAILIAN_CHENGGUANTONG_API_KEY = 'sk-9ee20f6ad5dd459aa8952e5ae979bead'
BAILIAN_CHENGGUANTONG_API_URL = 'https://dashscope.aliyuncs.com/api/v1/apps/b608e4ed05c44c19bf7e71679c859689/completion'

# 统一的超时配置
API_CONNECT_TIMEOUT = 10  # 连接超时（秒）
API_READ_TIMEOUT = 300    # 读取超时（秒）- 增加到5分钟
API_MAX_RETRIES = 3       # 最大重试次数
API_RETRY_DELAY = 5       # 重试延迟（秒）

def call_llm_api(api_url, api_key, model, messages, max_tokens=3000, temperature=0.3, provider_name="LLM"):
    """
    统一的大模型 API 调用函数，带重试机制和完善的错误处理

    Args:
        api_url: API 地址
        api_key: API 密钥
        model: 模型名称
        messages: 消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数
        provider_name: 提供商名称（用于日志）

    Returns:
        tuple: (success: bool, content: str or error_message: str)
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
        'Connection': 'keep-alive'
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    retry_delay = API_RETRY_DELAY

    for attempt in range(API_MAX_RETRIES):
        try:
            print(f"[{provider_name}] 尝试调用 API ({attempt + 1}/{API_MAX_RETRIES})...")

            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=(API_CONNECT_TIMEOUT, API_READ_TIMEOUT),
                proxies={"http": None, "https": None}  # 禁用代理，直连API
            )

            print(f"[{provider_name}] 响应状态码: {response.status_code}")

            # 检查 HTTP 状态码
            if response.status_code != 200:
                error_text = response.text[:500] if response.text else "无响应内容"
                print(f"[{provider_name}] HTTP 错误: {response.status_code}, 响应: {error_text}")

                # 4xx 错误不重试
                if 400 <= response.status_code < 500:
                    return False, f"API 请求错误 ({response.status_code}): {error_text}"

                # 5xx 错误重试
                response.raise_for_status()

            result = response.json()

            # 检查响应结构
            if 'choices' not in result or len(result['choices']) == 0:
                print(f"[{provider_name}] 响应结构异常: {result}")
                return False, "API 响应格式异常: 缺少 choices 字段"

            if 'message' not in result['choices'][0] or 'content' not in result['choices'][0]['message']:
                print(f"[{provider_name}] 响应结构异常: {result['choices'][0]}")
                return False, "API 响应格式异常: 缺少 message.content 字段"

            content = result['choices'][0]['message']['content']
            print(f"[{provider_name}] API 调用成功, 响应长度: {len(content)}")
            return True, content

        except requests.exceptions.Timeout as e:
            print(f"[{provider_name}] 请求超时: {e}")
            if attempt < API_MAX_RETRIES - 1:
                print(f"[{provider_name}] {retry_delay}秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return False, f"API 调用超时，已重试 {API_MAX_RETRIES} 次"

        except requests.exceptions.ConnectionError as e:
            print(f"[{provider_name}] 连接错误: {e}")
            if attempt < API_MAX_RETRIES - 1:
                print(f"[{provider_name}] {retry_delay}秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return False, f"网络连接失败: {str(e)}"

        except requests.exceptions.RequestException as e:
            print(f"[{provider_name}] 请求异常: {e}")
            return False, f"API 请求失败: {str(e)}"

        except Exception as e:
            print(f"[{provider_name}] 未知异常: {e}")
            import traceback
            traceback.print_exc()
            return False, f"API 调用异常: {str(e)}"

    return False, "API 调用失败: 超过最大重试次数"

# 数据清洗脱敏相关函数
import re

def clean_problem_description(text):
    """清理问题描述字段，删除所有任务编号、姓名、电话号码、详细地址和车牌号"""
    if pd.isna(text) or text.strip() == "":
        return text
    
    text_str = str(text)
    
    # 1. 删除电话号码
    # 匹配手机号码
    text_str = re.sub(r'1[3-9]\d{9}', '', text_str)
    # 匹配座机号码
    text_str = re.sub(r'0\d{2,3}-?\d{7,8}', '', text_str)
    
    # 2. 删除车牌号
    # 匹配车牌号格式，如"晋M·E5191"、"晋ME5191"等
    text_str = re.sub(r'[\u4e00-\u9fa5][A-Za-z]·?[A-Za-z0-9]{4,6}', '', text_str)
    
    # 3. 删除任务编号
    # 匹配明确的编号格式
    # 格式1: 数字字母组合的编号
    text_str = re.sub(r'[0-9A-Za-z]{4,}', '', text_str)
    # 格式2: 转办编号等特定格式
    text_str = re.sub(r'原转办编号：\d+', '', text_str)
    
    # 4. 删除姓名（删除明确的姓名标记，如"张先生"、"李女士"等）
    text_str = re.sub(r'[\u4e00-\u9fa5]{1,2}[先生|女士|小姐|同志]', '', text_str)
    
    # 5. 删除精细地址（如几单元几室）
    text_str = re.sub(r'[0-9]+[单元|号楼|楼|室|房|号]', '', text_str)
    
    # 6. 清理多余的空格
    text_str = re.sub(r'\s+', ' ', text_str).strip()
    
    return text_str

def desensitize_name(name):
    """对姓名进行脱敏，隐去名"""
    if pd.isna(name) or str(name).strip() == "":
        return name
    
    name_str = str(name).strip()
    if len(name_str) <= 1:
        return name_str
    return name_str[0] + '*' * (len(name_str) - 1)

def desensitize_phone(phone):
    """对电话号码进行脱敏，隐去后8位"""
    if pd.isna(phone) or str(phone).strip() == "":
        return phone
    
    phone_str = str(phone).strip()
    if len(phone_str) <= 3:
        return phone_str
    return phone_str[:3] + '*' * 8

def desensitize_landline(landline):
    """对座机号码进行脱敏，隐去后4位"""
    if pd.isna(landline) or str(landline).strip() == "":
        return landline
    
    landline_str = str(landline).strip()
    if len(landline_str) <= 4:
        return landline_str
    return landline_str[:-4] + '*' * 4

def desensitize_address(address):
    """对地址进行脱敏，隐去详细地址"""
    if pd.isna(address) or str(address).strip() == "":
        return address
    
    address_str = str(address).strip()
    # 只保留省市县，隐去详细地址
    parts = address_str.split(' ')
    if len(parts) <= 1:
        # 如果没有空格，尝试按常见地址分隔符分割
        parts = re.split(r'[,，]', address_str)
    
    if len(parts) >= 3:
        return ' '.join(parts[:3]) + ' ****'
    elif len(parts) >= 2:
        return ' '.join(parts[:2]) + ' ****'
    else:
        return address_str[:4] + ' ****'

# 数据清洗脱敏主函数
def clean_and_desensitize_data(df, fields_config):
    """对数据进行清洗和脱敏处理"""
    result_df = df.copy()
    
    for field, field_types in fields_config.items():
        if field not in result_df.columns:
            continue
        
        # 确保 field_types 是一个列表
        if not isinstance(field_types, list):
            field_types = [field_types]
        
        # 对同一个字段应用多种处理方式
        for field_type in field_types:
            if field_type == 'problem_description':
                result_df[field] = result_df[field].apply(clean_problem_description)
            elif field_type == 'name':
                result_df[field] = result_df[field].apply(desensitize_name)
            elif field_type == 'phone':
                result_df[field] = result_df[field].apply(desensitize_phone)
            elif field_type == 'landline':
                result_df[field] = result_df[field].apply(desensitize_landline)
            elif field_type == 'address':
                result_df[field] = result_df[field].apply(desensitize_address)
    
    return result_df

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

# 追加数据到现有表接口
@app.route('/api/append-data', methods=['POST'])
@admin_required
def append_data():
    """追加Excel数据到现有表"""
    session = Session()
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        if not file.filename.endswith('.xlsx'):
            return jsonify({'error': '只支持Excel文件'}), 400

        # 获取参数
        target_table = request.form.get('target_table')
        data_month = request.form.get('data_month', '')

        if not target_table:
            return jsonify({'error': '未指定目标表'}), 400

        # 读取Excel文件
        df = pd.read_excel(file)

        # 检查目标表是否存在
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if target_table not in existing_tables:
            return jsonify({'error': f'目标表 {target_table} 不存在'}), 400

        # 获取目标表的列结构
        existing_columns = [col['name'] for col in inspector.get_columns(target_table)]

        # 检查是否有月份列，如果有则添加月份值
        has_month_column = '月份' in existing_columns or 'data_month' in existing_columns
        month_column_name = '月份' if '月份' in existing_columns else 'data_month' if 'data_month' in existing_columns else None

        # 新增的列（Excel有但表没有的）
        new_columns = [col for col in df.columns if col not in existing_columns]

        # 添加新列到表
        if new_columns:
            for col in new_columns:
                col_type = 'TEXT'  # 默认使用TEXT类型
                session.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `{col}` {col_type}"))
            session.commit()
            print(f"添加了新列: {new_columns}")

        # 准备数据
        df_to_insert = df.copy()

        # 添加月份值
        if month_column_name and data_month:
            df_to_insert[month_column_name] = data_month

        # 获取更新后的列列表
        updated_columns = [col['name'] for col in inspector.get_columns(target_table)]

        # 只保留目标表中存在的列
        common_columns = [col for col in df_to_insert.columns if col in updated_columns]
        df_to_insert = df_to_insert[common_columns]

        # 追加数据到表
        df_to_insert.to_sql(target_table, engine, if_exists='append', index=False)

        inserted_count = len(df_to_insert)

        return jsonify({
            'message': f'成功追加 {inserted_count} 条数据到表 {target_table}',
            'inserted_count': inserted_count,
            'new_columns': new_columns
        }), 200

    except Exception as e:
        session.rollback()
        print(f"Error in append_data: {str(e)}")
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
        upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # 保存文件
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        session.commit()
        # 返回文件路径（只返回相对路径）
        return jsonify({
            'file_path': f'uploads/{unique_filename}',
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
        upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # 保存文件
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        session.commit()
        
        # TinyMCE需要的响应格式（返回相对路径）
        return jsonify({
            'location': f"/uploads/{unique_filename}"
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
    # 如果没有数据库连接，返回错误
    if engine is None:
        return jsonify({'error': '数据库未连接，请检查配置'}), 503

    session = Session()
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Missing username or password'}), 400

        # 检查登录尝试次数
        allowed, lock_msg = check_login_attempts(username)
        if not allowed:
            return jsonify({'error': lock_msg}), 429

        # 查找用户
        user = session.query(User).filter_by(username=username).first()
        if not user:
            record_failed_login(username)
            return jsonify({'error': 'Invalid username or password'}), 401

        # 验证密码（支持 bcrypt 和旧版 SHA256）
        if not verify_password(password, user.password):
            record_failed_login(username)
            return jsonify({'error': 'Invalid username or password'}), 401

        # 登录成功，清除失败记录
        clear_login_attempts(username)

        # 生成令牌
        token = generate_token(user.id, user.username, user.role)

        # 获取用户权限
        permission = session.execute(text("SELECT dashboard, assessment, data_analysis, cases, map, huiwentai, business FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
        permissions = {
            'dashboard': False,
            'assessment': False,
            'data_analysis': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False
        }
        if permission:
            permissions = {
                'dashboard': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'cases': permission[3],
                'map': permission[4],
                'huiwentai': permission[5],
                'business': permission[6]
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
    # 如果没有数据库连接，返回默认权限
    if engine is None:
        permissions = {
                'dashboard': True,
                'assessment': True,
                'data_analysis': True,
                'cases': True,
                'map': True,
                'huiwentai': True,
                'business': True
            }
        return jsonify({
            'user_id': request.user_id,
            'username': request.username,
            'role': request.role,
            'permissions': permissions
        }), 200

    session = Session()
    try:
        # 获取用户权限
        permission = session.execute(text("SELECT dashboard, assessment, data_analysis, cases, map, huiwentai, business FROM permissions WHERE user_id = :user_id"), {'user_id': request.user_id}).fetchone()

        permissions = {
            'dashboard': False,
            'assessment': False,
            'data_analysis': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False
        }

        if permission:
            permissions = {
                'dashboard': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'cases': permission[3],
                'map': permission[4],
                'huiwentai': permission[5],
                'business': permission[6]
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
    # 如果没有数据库连接，返回默认用户
    if engine is None:
        permissions = {
            'dashboard': True,
            'assessment': True,
            'data_analysis': True,
            'cases': True,
            'map': True,
            'huiwentai': True,
            'business': True
        }
        user_list = [{
            'id': 1,
            'username': 'admin',
            'role': 'admin',
            'created_at': '2024-01-01 00:00:00',
            'permissions': permissions
        }]
        return jsonify({'users': user_list}), 200
    
    session = Session()
    try:
        users = session.query(User).all()
        user_list = []
        for user in users:
            # 获取用户权限
            permission = session.execute(text("SELECT dashboard, assessment, data_analysis, cases, map, huiwentai, business FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
            permissions = {
                'dashboard': False,
                'assessment': False,
                'data_analysis': False,
                'cases': False,
                'map': False,
                'huiwentai': False,
                'business': False
            }
            if permission:
                permissions = {
                    'dashboard': permission[0],
                    'assessment': permission[1],
                    'data_analysis': permission[2],
                    'cases': permission[3],
                    'map': permission[4],
                    'huiwentai': permission[5],
                    'business': permission[6]
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
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
    
    session = Session()
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')
        
        if not username or not password:
            return jsonify({'error': 'Missing username or password'}), 400

        # 验证密码强度
        is_strong, strength_error = is_strong_password(password)
        if not is_strong:
            return jsonify({'error': strength_error}), 400

        # 检查用户是否已存在
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400

        # 创建新用户（使用 bcrypt 哈希密码）
        hashed_password = hash_password(password)
        new_user = User(
            username=username,
            password=hashed_password,
            role=role
        )
        session.add(new_user)
        session.commit()
        
        # 为新用户添加默认权限
        session.execute(text("INSERT INTO permissions (user_id, dashboard, assessment, data_analysis, cases, map, huiwentai, business) VALUES (:user_id, :dashboard, :assessment, :data_analysis, :cases, :map, :huiwentai, :business)"), {
            'user_id': new_user.id,
            'dashboard': False,
            'assessment': False,
            'data_analysis': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False
        })
        session.commit()

        return jsonify({
            'id': new_user.id,
            'username': new_user.username,
            'role': new_user.role,
            'permissions': {
                'dashboard': False,
                'assessment': False,
                'data_analysis': False,
                'cases': False,
                'map': False,
                'huiwentai': False,
                'business': False
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
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
    
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
            new_password = data['password']
            # 验证密码强度
            is_strong, strength_error = is_strong_password(new_password)
            if not is_strong:
                return jsonify({'error': strength_error}), 400
            user.password = hash_password(new_password)
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
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
    
    session = Session()
    try:
        data = request.json
        
        # 验证用户是否存在
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # 更新用户权限
        session.execute(text("UPDATE permissions SET dashboard = :dashboard, assessment = :assessment, data_analysis = :data_analysis, cases = :cases, map = :map, huiwentai = :huiwentai, business = :business WHERE user_id = :user_id"), {
            'user_id': user_id,
            'dashboard': data.get('dashboard', False),
            'assessment': data.get('assessment', False),
            'data_analysis': data.get('data_analysis', False),
            'cases': data.get('cases', False),
            'map': data.get('map', False),
            'huiwentai': data.get('huiwentai', False),
            'business': data.get('business', False)
        })
        session.commit()

        # 返回更新后的权限
        permission = session.execute(text("SELECT dashboard, assessment, data_analysis, cases, map, huiwentai, business FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
        permissions = {
            'dashboard': False,
            'assessment': False,
            'data_analysis': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False
        }
        if permission:
            permissions = {
                'dashboard': permission[0],
                'assessment': permission[1],
                'data_analysis': permission[2],
                'cases': permission[3],
                'map': permission[4],
                'huiwentai': permission[5],
                'business': permission[6]
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
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
    
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

# 业务平台API接口

# 获取所有业务平台
@app.route('/api/business-platforms', methods=['GET'])
@protected
def get_business_platforms():
    # 如果没有数据库连接，返回空列表
    if engine is None:
        return jsonify({'platforms': []}), 200
    
    session = Session()
    try:
        platforms = session.query(BusinessPlatform).all()
        platform_list = []
        for platform in platforms:
            platform_list.append({
                'id': platform.id,
                'name': platform.name,
                'url': platform.url,
                'image_path': platform.image_path,
                'created_at': platform.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': platform.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        session.commit()
        return jsonify({'platforms': platform_list}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_business_platforms: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 添加业务平台
@app.route('/api/business-platforms', methods=['POST'])
@admin_required
def add_business_platform():
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
    
    session = Session()
    try:
        data = request.json
        name = data.get('name')
        url = data.get('url')
        image_path = data.get('image_path')
        
        if not name or not url:
            return jsonify({'error': 'Missing name or url'}), 400
        
        # 检查平台名称是否已存在
        existing_platform = session.query(BusinessPlatform).filter_by(name=name).first()
        if existing_platform:
            return jsonify({'error': 'Platform name already exists'}), 400
        
        # 创建新平台
        new_platform = BusinessPlatform(
            name=name,
            url=url,
            image_path=image_path
        )
        session.add(new_platform)
        session.commit()
        
        return jsonify({
            'id': new_platform.id,
            'name': new_platform.name,
            'url': new_platform.url,
            'image_path': new_platform.image_path
        }), 201
    except Exception as e:
        session.rollback()
        print(f"Error in add_business_platform: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 更新业务平台
@app.route('/api/business-platforms/<int:platform_id>', methods=['PUT'])
@admin_required
def update_business_platform(platform_id):
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
    
    session = Session()
    try:
        data = request.json
        platform = session.query(BusinessPlatform).filter_by(id=platform_id).first()
        if not platform:
            return jsonify({'error': 'Platform not found'}), 404
        
        # 更新平台信息
        if 'name' in data:
            # 检查新名称是否与其他平台重复
            if data['name'] != platform.name:
                existing_platform = session.query(BusinessPlatform).filter_by(name=data['name']).first()
                if existing_platform:
                    return jsonify({'error': 'Platform name already exists'}), 400
            platform.name = data['name']
        if 'url' in data:
            platform.url = data['url']
        if 'image_path' in data:
            platform.image_path = data['image_path']
        
        session.commit()
        
        return jsonify({
            'id': platform.id,
            'name': platform.name,
            'url': platform.url,
            'image_path': platform.image_path
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_business_platform: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 删除业务平台
@app.route('/api/business-platforms/<int:platform_id>', methods=['DELETE'])
@admin_required
def delete_business_platform(platform_id):
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
    
    session = Session()
    try:
        platform = session.query(BusinessPlatform).filter_by(id=platform_id).first()
        if not platform:
            return jsonify({'error': 'Platform not found'}), 404
        
        session.delete(platform)
        session.commit()
        
        return jsonify({'message': 'Platform deleted successfully'}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in delete_business_platform: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/tables', methods=['GET'])
@protected
def get_tables():
    """获取数据表列表 - 根据可见性配置过滤"""
    # 如果没有数据库连接，返回空列表
    if engine is None:
        return jsonify({'tables': []}), 200

    session = Session()
    try:
        # 获取数据库中所有表名
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()

        # 根据可见性配置过滤
        config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()
        if config and config.config_value:
            visibility = json.loads(config.config_value)
            # 只返回可见的表（visibility[table] !== False）
            tables = [t for t in all_tables if visibility.get(t, True) != False]
        else:
            # 没有配置则全部可见
            tables = all_tables

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


@app.route('/api/tables/all', methods=['GET'])
@admin_required
def get_all_tables():
    """获取所有数据表列表（仅管理员，用于系统管理页面）"""
    if engine is None:
        return jsonify({'tables': []}), 200

    session = Session()
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        session.commit()
        return jsonify({'tables': tables}), 200
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 获取数据表中可用的月份列表
@app.route('/api/available-months', methods=['GET'])
@protected
def get_available_months():
    """从指定表中查询已有的月份值"""
    table_name = request.args.get('table_name')
    if not table_name:
        return jsonify({'error': 'Missing table_name parameter'}), 400

    if engine is None:
        return jsonify({'months': []}), 200

    session = Session()
    try:
        # 查询数据表中的月份列
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in columns]

        # 查找月份列
        month_col = None
        for col in ['月份', 'data_month', 'month']:
            if col in column_names:
                month_col = col
                break

        if month_col:
            # 查询所有不同的月份值
            query = text(f"SELECT DISTINCT {month_col} FROM {table_name} WHERE {month_col} IS NOT NULL ORDER BY {month_col} DESC")
            result_proxy = session.execute(query)
            months = [row[0] for row in result_proxy if row[0]]
            session.commit()
            return jsonify({'months': months}), 200
        else:
            session.commit()
            return jsonify({'months': []}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_available_months: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# 获取数据表的列名
@app.route('/api/table-columns', methods=['GET'])
@protected
def get_table_columns():
    """获取指定数据表的所有列名"""
    table_name = request.args.get('table_name')
    if not table_name:
        return jsonify({'error': 'Missing table_name parameter'}), 400

    if engine is None:
        return jsonify({'columns': []}), 200

    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in columns]
        return jsonify({'columns': column_names}), 200
    except Exception as e:
        print(f"Error in get_table_columns: {str(e)}")
        return jsonify({'error': str(e)}), 500

    try:
        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'months': []}), 200

        # 获取所有列名
        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 检查是否有月份列（支持多种命名）
        month_column = None
        month_column_names = ['data_month', '月份', 'month', 'Month', 'dataMonth', 'data_monthly', 'report_month']
        for col in month_column_names:
            if col in columns:
                month_column = col
                break

        if not month_column:
            print(f"表 {table_name} 未找到月份字段，现有字段: {columns}")
            return jsonify({'months': [], 'available_columns': columns}), 200

        # 查询月份值
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT DISTINCT `{month_column}` FROM `{table_name}` WHERE `{month_column}` IS NOT NULL AND `{month_column}` != '' ORDER BY `{month_column}` DESC"))
            months = [row[0] for row in result.fetchall()]

        return jsonify({'months': months}), 200
    except Exception as e:
        print(f"Error in get_available_months: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 删除数据表接口
@app.route('/api/tables/<table_name>', methods=['DELETE'])
@protected
def delete_table(table_name):
    # 如果没有数据库连接，返回提示
    if engine is None:
        return jsonify({'error': 'Database not connected. Table management is disabled.'}), 503

    session = Session()
    try:
        # 防止删除系统表
        protected_tables = ['users', 'permissions']
        if table_name in protected_tables:
            return jsonify({'error': f'不能删除系统表 {table_name}'}), 403

        # 删除数据表（使用反引号包裹表名，处理外键约束）
        from sqlalchemy import text
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
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

# 获取表格可见性配置
@app.route('/api/config/table-visibility', methods=['GET'])
@protected
def get_table_visibility():
    """获取表格可见性配置"""
    if engine is None:
        return jsonify({'config': {}}), 200

    session = Session()
    try:
        config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()
        if config and config.config_value:
            config_data = json.loads(config.config_value)
            return jsonify({'config': config_data}), 200
        else:
            return jsonify({'config': {}}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_table_visibility: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 保存表格可见性配置
@app.route('/api/config/table-visibility', methods=['POST'])
@admin_required
def save_table_visibility():
    """保存表格可见性配置（仅管理员）"""
    if engine is None:
        return jsonify({'error': 'Database not connected. Config management is disabled.'}), 503

    session = Session()
    try:
        data = request.json
        config_value = data.get('config', {})

        # 查找现有配置
        config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()

        if config:
            # 更新现有配置
            config.config_value = json.dumps(config_value)
        else:
            # 创建新配置
            config = SystemConfig(
                config_key='table_visibility',
                config_value=json.dumps(config_value)
            )
            session.add(config)

        session.commit()
        return jsonify({'message': '配置保存成功', 'config': config_value}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in save_table_visibility: {str(e)}")
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
import re

def extract_location_from_text(text):
    """
    从问题描述中精准提取地点信息（过滤垃圾、经营等非地点关键词）
    """
    if pd.isna(text) or text.strip() == "":
        return "未提取到地址"
    
    # 按标点分割文本，只保留前半段地点部分
    parts = re.split(r"，|,|。|；|：", str(text).strip())
    # 定义非地点关键词（遇到这些词则停止提取）
    stop_words = [
        "绿地内", "人行道", "非机动车道", "主干道", "垃圾", "经营", "乱放",
        "晾晒", "粪便", "摊点", "尘土", "满溢", "不洁", "摆乱放", "果皮箱外",
        "成袋垃圾", "动物粪便", "流动", "道路尘土", "外观不洁", "把式车辆",
        "机动车道","店外经营", "路面", "底盖", "小广告", "广告", "乱晾",
        "乱晒", "外墙", "线体", "车轮", "违规", "主次干道", "配电箱", "干枝", "户外"
    ]
    
    location_parts = []
    for part in parts:
        # 若当前片段包含非地点关键词，停止提取
        if any(word in part for word in stop_words):
            break
        # 过滤空片段，保留有效地点
        if part.strip():
            location_parts.append(part.strip())
    
    # 兜底：若过滤后无内容，取前2段原始内容
    if not location_parts:
        location_parts = [p.strip() for p in parts[:2] if p.strip()]
    
    # 拼接成完整地址
    return "，".join(location_parts) if location_parts else "未提取到地址"

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

def calculate_law_enforcement_score_v2(cases, coefficients=None):
    """计算城市综合行政执法队8个片区的考核分数和排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }
    
    target_departments = [
        "执法东片区", "执法北片区", "执法南片区", "执法西片区",
        "执法中片区", "大渠执法分队", "姚孟执法分队", "安邑执法分队"
    ]
    print(f"目标统计部门：{target_departments}")
    print(f"使用的计分系数：{coefficients}")
    
    team_results = []
    
    for dept_name in target_departments:
        dept_cases = [c for c in cases if c.get('处置部门') == dept_name]
        
        total = len(dept_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in dept_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            
            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1
            else:
                on_time += 1
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
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
    
    team_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, team in enumerate(team_results, 1):
        team['rank'] = i
    
    print(f"\n排名结果：")
    for team in team_results:
        print(f"  第{team['rank']}名：{team['department']} - {team['score']}分")
    
    total_cases = sum(t['total_cases'] for t in team_results)
    total_score = sum(t['score'] for t in team_results) / len(team_results)
    
    return {
        'total_cases': total_cases,
        'team_results': team_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_huanwei_score_v2(cases, coefficients=None):
    """计算市容环卫中心5个片区的考核分数和排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }
    
    target_areas = [
        "环卫东片区", "环卫北片区", "环卫南片区",
        "环卫西片区", "环卫中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    print(f"使用的计分系数：{coefficients}")
    
    area_results = []
    
    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            
            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1
            else:
                on_time += 1
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
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
    
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_garden_score_v2(cases, coefficients=None):
    """计算园林各片区的考核得分并排名（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }
    
    target_areas = [
        "园林东片区", "园林北片区", "园林南片区",
        "园林西片区", "园林中片区"
    ]
    print(f"目标统计片区：{target_areas}")
    print(f"使用的计分系数：{coefficients}")
    
    area_results = []
    
    for area_name in target_areas:
        area_cases = [c for c in cases if c.get('处置部门') == area_name]
        
        total = len(area_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            
            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1
            else:
                on_time += 1
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
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
    
    area_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, area in enumerate(area_results, 1):
        area['rank'] = i
    
    print(f"\n排名结果：")
    for area in area_results:
        print(f"  第{area['rank']}名：{area['department']} - {area['score']}分")
    
    total_cases = sum(a['total_cases'] for a in area_results)
    total_score = sum(a['score'] for a in area_results) / len(area_results)
    
    return {
        'total_cases': total_cases,
        'team_results': area_results,
        'score': round(total_score, 2),
        'details': {}
    }

def calculate_park_score_v2(cases, coefficients=None):
    """计算园林各公园考核得分（排除挂账案件）（新版：使用是否超时字段判定）"""
    if coefficients is None:
        coefficients = {
            'on_time': 1.0,
            'overdue': 0.4,
            'closure_weight': 0.8,
            'delay_weight': 0.1,
            'rework_weight': 0.1
        }
    
    target_parks = ["南风广场", "天逸公园", "体育公园", "航天公园", "圣惠公园", "禹都公园", "人民公园"]
    print(f"目标统计公园：{target_parks}")
    print(f"使用的计分系数：{coefficients}")
    
    non_guazhang_cases = []
    for case in cases:
        stage = case.get('当前阶段名称') or ''
        stage_str = str(stage).strip().lower()
        if '挂账' not in stage_str:
            non_guazhang_cases.append(case)
    
    print(f"\n挂账过滤结果：")
    print(f"   - 原始案件数：{len(cases)}")
    print(f"   - 排除挂账后案件数：{len(non_guazhang_cases)}")
    print(f"   - 排除的挂账案件数：{len(cases) - len(non_guazhang_cases)}")
    
    park_results = []
    
    for park_name in target_parks:
        park_cases = [c for c in non_guazhang_cases if c.get('处置部门') == park_name]
        
        total = len(park_cases)
        on_time = 0
        overdue = 0
        delay = 0
        rework = 0
        
        for case in park_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            
            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1
            else:
                on_time += 1
            
            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass
            
            rework_val = case.get('返工次数') or case.get('rework')
            if rework_val and str(rework_val) == '是':
                rework += 1
        
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0
        
        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
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
    
    park_results.sort(key=lambda x: x['score'], reverse=True)
    
    for i, park in enumerate(park_results, 1):
        park['rank'] = i
    
    print(f"\n排名结果：")
    for park in park_results:
        print(f"  第{park['rank']}名：{park['department']} - {park['score']}分")
    
    total_cases = sum(p['total_cases'] for p in park_results)
    total_score = sum(p['score'] for p in park_results) / len(park_results)
    
    return {
        'total_cases': total_cases,
        'team_results': park_results,
        'score': round(total_score, 2),
        'details': {}
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
                timeout=(10, 300),  # 连接超时10秒，读取超时300秒
                proxies={"http": None, "https": None}  # 禁用代理
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
        month = data.get('month', '')  # 新增：月份筛选

        if not table_name or not department:
            return jsonify({'error': 'Missing table_name or department'}), 400

        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)

        # 月份筛选
        if month:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col] == month]
                print(f"[考核计分] 筛选月份 {month}，剩余 {len(df)} 条数据")

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

import json
import os

# 系数配置文件路径
COEFFICIENTS_FILE = os.path.join(os.path.dirname(__file__), 'assessment_coefficients.json')

# 部门列表
DEPARTMENTS = [
    '城市综合行政执法队',
    '市容环卫中心',
    '园林绿化服务中心（片区）',
    '园林绿化服务中心（公园广场）'
]

# 默认系数
DEFAULT_COEFFICIENTS = {
    'on_time': 1.0,
    'overdue': 0.4,
    'closure_weight': 0.8,
    'delay_weight': 0.1,
    'rework_weight': 0.1
}

def load_coefficients():
    """从文件加载系数配置"""
    try:
        if os.path.exists(COEFFICIENTS_FILE):
            with open(COEFFICIENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 检查是否是旧格式（单个系数对象）
            if 'on_time' in data and not any(dept in data for dept in DEPARTMENTS):
                # 转换为新格式：将旧系数应用到所有部门
                new_coefficients = {dept: data.copy() for dept in DEPARTMENTS}
                # 保存转换后的格式
                save_coefficients_to_file(new_coefficients)
                return new_coefficients
            # 检查是否是新格式但缺少某些部门
            if isinstance(data, dict):
                for dept in DEPARTMENTS:
                    if dept not in data:
                        data[dept] = DEFAULT_COEFFICIENTS.copy()
                return data
    except Exception as e:
        print(f"Error loading coefficients: {e}")
    # 返回每个部门的默认系数
    return {dept: DEFAULT_COEFFICIENTS.copy() for dept in DEPARTMENTS}

def save_coefficients_to_file(coefficients):
    """保存系数配置到文件"""
    try:
        with open(COEFFICIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(coefficients, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving coefficients: {e}")
        return False

# 加载初始系数
assessment_coefficients = load_coefficients()

@app.route('/api/assessment-coefficients', methods=['GET'])
@protected
def get_assessment_coefficients():
    global assessment_coefficients
    # 每次都从文件重新加载，确保获取最新配置
    assessment_coefficients = load_coefficients()
    return jsonify(assessment_coefficients), 200

@app.route('/api/assessment-coefficients', methods=['PUT'])
@protected
def save_assessment_coefficients():
    global assessment_coefficients
    try:
        data = request.json
        department = data.get('department')
        
        if not department or department not in DEPARTMENTS:
            return jsonify({'error': 'Invalid department'}), 400
        
        # 加载当前所有系数
        all_coefficients = load_coefficients()
        
        # 更新指定部门的系数
        all_coefficients[department] = {
            'on_time': float(data.get('on_time', 1.0)),
            'overdue': float(data.get('overdue', 0.4)),
            'closure_weight': float(data.get('closure_weight', 0.8)),
            'delay_weight': float(data.get('delay_weight', 0.1)),
            'rework_weight': float(data.get('rework_weight', 0.1))
        }
        
        # 保存到文件
        if save_coefficients_to_file(all_coefficients):
            assessment_coefficients = all_coefficients
            return jsonify({'message': 'Coefficients saved successfully', 'coefficients': assessment_coefficients}), 200
        else:
            return jsonify({'error': 'Failed to save coefficients to file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/assess/v2', methods=['POST'])
@protected
def assess_v2():
    try:
        data = request.json
        table_name = data.get('table_name')
        department = data.get('department')
        month = data.get('month', '')  # 新增：月份筛选

        if not table_name or not department:
            return jsonify({'error': 'Missing table_name or department'}), 400

        # 每次都从文件重新加载最新的系数
        current_coefficients = load_coefficients()

        # 获取该部门的系数
        if department in current_coefficients:
            coefficients = current_coefficients[department]
        else:
            coefficients = DEFAULT_COEFFICIENTS.copy()

        df = pd.read_sql_table(table_name, engine)

        # 月份筛选
        if month:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col] == month]
                print(f"[考核计分V2] 筛选月份 {month}，剩余 {len(df)} 条数据")

        cases = df.to_dict('records')
        
        if department == '城市综合行政执法队':
            result = calculate_law_enforcement_score_v2(cases, coefficients)
        elif department == '市容环卫中心':
            result = calculate_huanwei_score_v2(cases, coefficients)
        elif department == '园林绿化服务中心（片区）':
            result = calculate_garden_score_v2(cases, coefficients)
        elif department == '园林绿化服务中心（公园广场）':
            result = calculate_park_score_v2(cases, coefficients)
        else:
            result = calculate_generic_score(cases)
        
        result['department'] = department
        result['table_name'] = table_name
        
        return jsonify(convert_nan_to_null(result)), 200
    except Exception as e:
        print(f"Error in assess_v2: {str(e)}")
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
                    timeout=(10, 300),  # 连接超时10秒，读取超时300秒
                    proxies={"http": None, "https": None}  # 禁用代理
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
        month = data.get('month', '')  # 新增：月份筛选

        if not table_name or not analysis_type:
            return jsonify({'error': 'Missing table_name or analysis_type'}), 400

        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)

        # 月份筛选
        if month:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col] == month]
                print(f"[数据分析] 筛选月份 {month}，剩余 {len(df)} 条数据")

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
                    
                    # 分析前五类问题类型的详细情况
                    top5_problem_types = problem_type_counts.head(5)
                    prompt += f"\n\n前五类问题类型详细分析：\n"
                    for index, row in top5_problem_types.iterrows():
                        problem_type = row[problem_type_col]
                        count = row['count']
                        percentage = (count / len(df)) * 100
                        prompt += f"{index + 1}. {problem_type}：{count} 件，占比 {percentage:.2f}%\n"
                except Exception as e:
                    prompt += f"\n问题类型分析失败：{str(e)}"
            
            # 分析大类名称
            category_col = key_fields['大类名称']
            if category_col:
                try:
                    category_counts = df[category_col].value_counts().head(10).reset_index()
                    category_counts.columns = [category_col, 'count']
                    prompt += f"\n大类名称分布（前10）：\n{category_counts.to_string(index=False)}"
                    
                    # 分析前五类大类的详细情况
                    top5_categories = category_counts.head(5)
                    prompt += f"\n\n前五大大类详细分析：\n"
                    for index, row in top5_categories.iterrows():
                        category = row[category_col]
                        count = row['count']
                        percentage = (count / len(df)) * 100
                        prompt += f"{index + 1}. {category}：{count} 件，占比 {percentage:.2f}%\n"
                except Exception as e:
                    prompt += f"\n大类分析失败：{str(e)}"
            
            # 分析小类名称
            subcategory_col = key_fields['小类名称']
            if subcategory_col:
                try:
                    subcategory_counts = df[subcategory_col].value_counts().head(10).reset_index()
                    subcategory_counts.columns = [subcategory_col, 'count']
                    prompt += f"\n小类名称分布（前10）：\n{subcategory_counts.to_string(index=False)}"
                    
                    # 分析前five类小类的详细情况
                    top5_subcategories = subcategory_counts.head(5)
                    prompt += f"\n\n前五类小类详细分析：\n"
                    for index, row in top5_subcategories.iterrows():
                        subcategory = row[subcategory_col]
                        count = row['count']
                        percentage = (count / len(df)) * 100
                        prompt += f"{index + 1}. {subcategory}：{count} 件，占比 {percentage:.2f}%\n"
                    
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
@protected
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

# 小工具模块API - 自然语言查询转换为SQL
@app.route('/api/tools/natural-language-query', methods=['POST'])
@protected
def natural_language_query():
    try:
        data = request.json
        natural_language = data.get('natural_language')
        table_name = data.get('table_name')
        
        if not natural_language or not table_name:
            return jsonify({'error': 'Missing natural_language or table_name'}), 400
        
        # 从数据库读取表结构信息
        df = pd.read_sql_table(table_name, engine)
        columns = df.columns.tolist()
        
        # 构建大模型提示
        prompt = f"请将以下自然语言查询转换为SQL语句，针对数据表 '{table_name}'。\n"
        prompt += f"数据表 {table_name} 包含以下字段：\n"
        for col in columns:
            prompt += f"- {col}\n"
        prompt += f"\n自然语言查询：{natural_language}\n"
        prompt += "\n要求：\n"
        prompt += "1. 只返回SQL语句，不要包含任何解释或其他内容\n"
        prompt += "2. 使用正确的SQL语法，针对MySQL数据库\n"
        prompt += "3. 确保SQL语句能够正确执行\n"
        prompt += "4. 不要包含任何多余的字符或注释\n"
        prompt += "5. 直接返回最终的SQL语句，不要有任何前缀或后缀\n"
        
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
                    "content": "你是一个专业的SQL生成助手，擅长将自然语言查询转换为标准的SQL语句。请根据提供的数据表结构和自然语言查询，生成正确的SQL语句。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        # 调用API，添加重试机制
        max_retries = 3
        retry_delay = 5
        generated_sql = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    API_URL,
                    headers=headers,
                    json=payload,
                    timeout=(10, 300),  # 连接超时10秒，读取超时300秒
                    proxies={"http": None, "https": None}  # 禁用代理
                )
                response.raise_for_status()
                result = response.json()
                generated_sql = result['choices'][0]['message']['content'].strip()
                break
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"API调用失败，{retry_delay}秒后重试... (尝试 {attempt+1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    raise Exception(f"大模型API调用失败，请稍后重试: {str(e)}")
        
        if not generated_sql:
            return jsonify({'error': '大模型未返回有效的SQL语句'}), 500
        
        # 执行SQL查询
        try:
            # 使用text()包装SQL语句，防止SQL注入
            query_result = pd.read_sql(text(generated_sql), engine)
            # 转换为字典列表
            result_records = query_result.to_dict('records')
            # 转换NaN值为null值
            result_records = convert_nan_to_null(result_records)
        except Exception as e:
            return jsonify({'error': f'SQL执行失败: {str(e)}', 'sql': generated_sql}), 500
        
        return jsonify({
            'sql': generated_sql,
            'result': result_records
        }), 200
    except Exception as e:
        print(f"Error in natural_language_query: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 数据分析（新版）API - 优化版：合并3次大模型调用为1次
@app.route('/api/analyze-v2', methods=['POST'])
@protected
def analyze_v2():
    def make_json_serializable(obj):
        """递归转换所有 int64/float64 为 Python 原生类型"""
        import numpy as np
        if isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    try:
        import json
        import re

        data = request.json
        table_name = data.get('table_name')
        user_prompt = data.get('prompt')
        model_choice = data.get('model', 'volcengine')
        month = data.get('month', '')

        if not table_name or not user_prompt:
            return jsonify({'error': 'Missing table_name or prompt'}), 400

        print(f"[数据分析V2] 开始分析, 表: {table_name}, 模型: {model_choice}")

        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)
        original_count = len(df)

        # 月份筛选
        if month:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col] == month]
                print(f"[数据分析V2] 筛选月份 {month}，剩余 {len(df)} 条数据")

        # 准备列信息（供大模型参考）
        columns_info = []
        for col in df.columns:
            unique_vals = df[col].dropna().unique()
            sample_vals = list(unique_vals[:5]) if len(unique_vals) > 0 else []
            columns_info.append({
                'name': col,
                'type': str(df[col].dtype),
                'unique_count': int(len(unique_vals)),
                'sample_values': [str(v)[:50] for v in sample_vals]  # 截断长文本
            })

        # 准备数据摘要（用于统计分析，使用完整数据）
        data_summary = f"""数据表：{table_name}
总记录数：{original_count}
列数：{len(df.columns)}
列信息：
"""
        for col_info in columns_info:
            data_summary += f"  - {col_info['name']} (类型: {col_info['type']}, 唯一值数: {col_info['unique_count']})\n"
            if col_info['sample_values']:
                data_summary += f"    示例: {', '.join(col_info['sample_values'][:3])}\n"

        # ===== 一次性调用大模型：同时获取筛选条件、图表需求和初步分析 =====
        combined_prompt = f"""你是一个数据分析专家。请根据用户需求和数据信息，完成以下任务：

{data_summary}

用户分析需求：{user_prompt}

请以JSON格式返回结果，格式如下：
{{
    "filter": {{
        "has_filter": true或false,
        "conditions": [
            {{"field": "字段名", "operator": "等于|包含|不等于|大于|小于", "value": "值"}}
        ],
        "description": "筛选条件描述"
    }},
    "charts": [
        {{"title": "图表标题", "chart_type": "bar|pie|line", "x_field": "X轴字段名", "description": "图表说明"}}
    ],
    "analysis": "初步分析见解（2-3句话概括数据特点）",
    "report": "详细分析报告，包含：数据概况、关键发现、趋势分析、建议措施等内容，使用Markdown格式，需要详细专业并引用具体统计数据"
}}

重要规则：
1. 字段名必须与上面列信息中的字段名完全一致
2. chart_type 只能是 bar（柱状图）、pie（饼图）、line（折线图）
3. 图表数量建议1-3个，选择最合适的类型
4. 如果用户没有明确筛选条件，has_filter设为false，conditions留空数组
5. report字段需要详细、专业，包含具体的统计数据引用和分析见解
6. 只返回JSON，不要有其他文字"""

        messages = [
            {"role": "system", "content": "你是一个数据分析专家，擅长理解用户意图并生成结构化的分析结果。"},
            {"role": "user", "content": combined_prompt}
        ]

        # 选择大模型
        if model_choice == 'bailian':
            success, result = call_llm_api(
                BAILIAN_GENERAL_API_URL,
                BAILIAN_GENERAL_API_KEY,
                BAILIAN_GENERAL_MODEL,
                messages,
                max_tokens=3000,
                provider_name="百炼-综合分析"
            )
        else:
            success, result = call_llm_api(
                API_URL,
                API_KEY,
                MODEL,
                messages,
                max_tokens=3000,
                provider_name="火山引擎-综合分析"
            )

        if not success:
            raise Exception(f"大模型调用失败: {result}")

        print(f"[数据分析V2] 大模型返回结果: {result[:500]}...")

        # 解析返回结果
        llm_result = {}
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            llm_result = json.loads(json_match.group())

        # ===== 执行筛选 =====
        filtered_df = df.copy()
        filter_applied = False
        filter_summary = ""

        if llm_result.get('filter', {}).get('has_filter', False):
            conditions = llm_result.get('filter', {}).get('conditions', [])
            filter_parts = []

            for cond in conditions:
                field = cond.get('field')
                operator = cond.get('operator', '等于')
                value = cond.get('value')

                if not field or field not in df.columns:
                    print(f"[数据分析V2] 警告: 字段 '{field}' 不存在，跳过")
                    continue

                before_count = len(filtered_df)

                if operator == '等于':
                    if isinstance(value, list):
                        filtered_df = filtered_df[filtered_df[field].astype(str).isin([str(v) for v in value])]
                        filter_parts.append(f"{field} 在 {value} 中")
                    else:
                        filtered_df = filtered_df[filtered_df[field].astype(str) == str(value)]
                        filter_parts.append(f"{field}={value}")
                elif operator == '包含':
                    if isinstance(value, list):
                        mask = filtered_df[field].astype(str).apply(lambda x: any(str(v) in x for v in value))
                        filtered_df = filtered_df[mask]
                    else:
                        filtered_df = filtered_df[filtered_df[field].astype(str).str.contains(str(value), na=False)]
                    filter_parts.append(f"{field}包含{value}")
                elif operator == '不等于':
                    if isinstance(value, list):
                        filtered_df = filtered_df[~filtered_df[field].astype(str).isin([str(v) for v in value])]
                    else:
                        filtered_df = filtered_df[filtered_df[field].astype(str) != str(value)]
                    filter_parts.append(f"{field}!={value}")
                elif operator == '大于':
                    filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') > float(value)]
                    filter_parts.append(f"{field}>{value}")
                elif operator == '小于':
                    filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') < float(value)]
                    filter_parts.append(f"{field}<{value}")

                print(f"[数据分析V2] 筛选: {field} {operator} {value}, {before_count} -> {len(filtered_df)}")

            if filter_parts:
                filter_applied = True
                filter_summary = " AND ".join(filter_parts)

        filtered_count = len(filtered_df)
        print(f"[数据分析V2] 筛选完成: {original_count} -> {filtered_count} 条")

        # ===== 生成图表 =====
        charts = []
        chart_configs = llm_result.get('charts', [])

        for chart_req in chart_configs:
            try:
                chart_title = chart_req.get('title', '图表')
                chart_type = chart_req.get('chart_type', 'bar')
                x_field = chart_req.get('x_field')

                if not x_field or x_field not in filtered_df.columns:
                    continue

                if chart_type == 'pie':
                    value_counts = filtered_df[x_field].value_counts().head(15).reset_index()
                    value_counts.columns = [x_field, 'count']
                    charts.append({
                        'title': chart_title,
                        'type': 'echarts',
                        'data': {
                            'title': {'text': chart_title},
                            'tooltip': {'trigger': 'item'},
                            'legend': {'type': 'scroll', 'bottom': 0},
                            'series': [{
                                'data': [{'name': str(row[x_field]), 'value': int(row['count'])} for _, row in value_counts.iterrows()],
                                'type': 'pie',
                                'radius': ['40%', '70%'],
                                'label': {'show': False}
                            }]
                        }
                    })
                elif chart_type == 'line':
                    # 检查是否是时间字段
                    is_time = any(kw in x_field for kw in ['时间', '日期', 'date', 'time'])
                    if is_time:
                        df_temp = filtered_df.copy()
                        df_temp[x_field] = pd.to_datetime(df_temp[x_field], errors='coerce')
                        df_valid = df_temp.dropna(subset=[x_field])
                        if len(df_valid) > 0:
                            df_valid['day'] = df_valid[x_field].dt.day
                            counts = df_valid.groupby('day').size().reset_index(name='count')
                            charts.append({
                                'title': chart_title,
                                'type': 'echarts',
                                'data': {
                                    'title': {'text': chart_title},
                                    'tooltip': {'trigger': 'axis'},
                                    'xAxis': {'type': 'category', 'data': [int(x) for x in counts['day'].tolist()]},
                                    'yAxis': {'type': 'value'},
                                    'series': [{'data': [int(x) for x in counts['count'].tolist()], 'type': 'line', 'smooth': True}]
                                }
                            })
                    else:
                        counts = filtered_df[x_field].value_counts().head(15).reset_index()
                        counts.columns = [x_field, 'count']
                        charts.append({
                            'title': chart_title,
                            'type': 'echarts',
                            'data': {
                                'title': {'text': chart_title},
                                'tooltip': {'trigger': 'axis'},
                                'xAxis': {'type': 'category', 'data': [str(x) for x in counts[x_field].tolist()], 'axisLabel': {'rotate': 45}},
                                'yAxis': {'type': 'value'},
                                'series': [{'data': [int(x) for x in counts['count'].tolist()], 'type': 'line', 'smooth': True}]
                            }
                        })
                else:  # bar
                    counts = filtered_df[x_field].value_counts().head(15).reset_index()
                    counts.columns = [x_field, 'count']
                    charts.append({
                        'title': chart_title,
                        'type': 'echarts',
                        'data': {
                            'title': {'text': chart_title},
                            'tooltip': {'trigger': 'axis'},
                            'xAxis': {'type': 'category', 'data': [str(x) for x in counts[x_field].tolist()], 'axisLabel': {'rotate': 45}},
                            'yAxis': {'type': 'value'},
                            'series': [{'data': [int(x) for x in counts['count'].tolist()], 'type': 'bar'}]
                        }
                    })
            except Exception as e:
                print(f"[数据分析V2] 生成图表失败: {e}")
                continue

        # 如果没有生成图表，创建默认图表
        if not charts and len(filtered_df) > 0:
            # 尝试找时间字段
            time_col = None
            for col in filtered_df.columns:
                if '时间' in col or '日期' in col or 'date' in col.lower():
                    time_col = col
                    break
            if time_col:
                try:
                    df_temp = filtered_df.copy()
                    df_temp[time_col] = pd.to_datetime(df_temp[time_col], errors='coerce')
                    df_valid = df_temp.dropna(subset=[time_col])
                    if len(df_valid) > 0:
                        df_valid['day'] = df_valid[time_col].dt.day
                        daily_counts = df_valid.groupby('day').size().reset_index(name='count')
                        charts.append({
                            'title': '日案件量趋势',
                            'type': 'echarts',
                            'data': {
                                'title': {'text': '日案件量趋势'},
                                'tooltip': {'trigger': 'axis'},
                                'xAxis': {'type': 'category', 'data': [int(x) for x in daily_counts['day'].tolist()]},
                                'yAxis': {'type': 'value'},
                                'series': [{'data': [int(x) for x in daily_counts['count'].tolist()], 'type': 'line', 'smooth': True}]
                            }
                        })
                except:
                    pass

        # 使用第一次LLM调用返回的报告
        analysis_report = llm_result.get('report', '')

        # 如果LLM没有返回报告，生成一个基本报告
        if not analysis_report:
            stats_info = f"数据统计：\n- 总记录数：{filtered_count}\n"
            for col in filtered_df.columns[:5]:
                unique_count = filtered_df[col].nunique()
                if unique_count <= 20 and unique_count > 1:
                    top_vals = filtered_df[col].value_counts().head(3)
                    stats_info += f"- {col} TOP3: {dict(top_vals)}\n"
            analysis_report = f"""## 数据分析报告

### 数据概况
- 数据表：{table_name}
- 分析数据量：{filtered_count} 条记录

### 统计摘要
{stats_info}

### 初步分析
{llm_result.get('analysis', '暂无分析内容')}
"""

        # 返回结果
        result = {
            'table_name': table_name,
            'original_count': int(original_count),
            'filtered_count': int(filtered_count),
            'filter_applied': filter_applied,
            'filter_summary': filter_summary if filter_applied else None,
            'report': analysis_report,
            'charts': make_json_serializable(charts)
        }

        print(f"[数据分析V2] 分析完成, 图表数: {len(charts)}")
        return jsonify(result), 200

    except Exception as e:
        print(f"Error in analyze_v2: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

# 图表分析API - 获取仪表盘数据（纯统计分析，不调用大模型）
@app.route('/api/chart-analysis', methods=['POST'])
@protected
def chart_analysis():
    """图表分析API - 根据数据表生成仪表盘数据"""
    try:
        import json
        data = request.json
        table_name = data.get('table_name')
        month = data.get('month', '')

        if not table_name:
            return jsonify({'error': 'Missing table_name parameter'}), 400

        print(f"[图表分析] 开始分析数据表: {table_name}, 月份: {month}")

        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)
        total_count = len(df)

        # 月份筛选
        if month:
            month_col = None
            for col in ['月份', 'data_month', 'month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                print(f"[图表分析] 找到月份列: {month_col}, 筛选值: {month}")
                print(f"[图表分析] 筛选前月份值分布: {df[month_col].value_counts().head()}")
                df = df[df[month_col] == month]
                print(f"[图表分析] 筛选月份 {month}，剩余 {len(df)} 条数据")
            else:
                print(f"[图表分析] 未找到月份列，列名: {list(df.columns)}")

        filtered_count = len(df)

        if filtered_count == 0:
            return jsonify({'error': '筛选后数据为空'}), 400

        print(f"[图表分析] 数据总量: {total_count}, 筛选后: {filtered_count} 条")

        # 初始化结果
        result = {
            'total_count': total_count,
            'filtered_count': filtered_count,
            'month': month,
            'charts': {}
        }

        # 1. 问题来源分布（饼状图）
        source_col = None
        for col in ['问题来源', 'source', '案件来源']:
            if col in df.columns:
                source_col = col
                break
        if source_col:
            source_data = df[source_col].fillna('未知').value_counts()
            result['charts']['source_pie'] = {
                'title': '问题来源分布',
                'type': 'pie',
                'data': [{'name': str(k), 'value': int(v)} for k, v in source_data.items()]
            }

        # 2. 问题类型分布（饼状图）
        problem_type_col = None
        for col in ['问题类型', 'problem_type', '案件类型']:
            if col in df.columns:
                problem_type_col = col
                break
        if problem_type_col:
            type_data = df[problem_type_col].fillna('未知').value_counts()
            result['charts']['type_pie'] = {
                'title': '问题类型分布',
                'type': 'pie',
                'data': [{'name': str(k), 'value': int(v)} for k, v in type_data.items()]
            }

        # 3. 大类名称占比图（横向柱状图）
        major_cat_col = None
        for col in ['大类名称', 'major_category', '大类']:
            if col in df.columns:
                major_cat_col = col
                break
        if major_cat_col:
            major_data = df[major_cat_col].fillna('未知').value_counts().head(15)
            result['charts']['major_category'] = {
                'title': '大类案件分布',
                'type': 'bar',
                'data': {'categories': [str(k) for k in major_data.index], 'values': [int(v) for v in major_data.values]}
            }

        # 4. 小类名称分布图（横向柱状图）
        minor_cat_col = None
        for col in ['小类名称', 'minor_category', '小类']:
            if col in df.columns:
                minor_cat_col = col
                break
        if minor_cat_col:
            minor_data = df[minor_cat_col].fillna('未知').value_counts().head(20)
            result['charts']['minor_category'] = {
                'title': '小类案件分布',
                'type': 'bar',
                'data': {'categories': [str(k) for k in minor_data.index], 'values': [int(v) for v in minor_data.values]}
            }

        # 5. 所属片区分布图（饼状图）
        area_col = None
        for col in ['所属片区', '所属区域', 'area', '片区']:
            if col in df.columns:
                area_col = col
                break
        if area_col:
            area_data = df[area_col].fillna('未知').value_counts()
            result['charts']['area_pie'] = {
                'title': '案件采集片区分布',
                'type': 'pie',
                'data': [{'name': str(k), 'value': int(v)} for k, v in area_data.items()]
            }

        # 6. 所属街道分布图（横向柱状图）
        street_col = None
        for col in ['所属街道', 'street', '街道']:
            if col in df.columns:
                street_col = col
                break
        if street_col:
            street_data = df[street_col].fillna('未知').value_counts()
            result['charts']['street'] = {
                'title': '案件街道分布',
                'type': 'bar',
                'data': {'categories': [str(k) for k in street_data.index], 'values': [int(v) for v in street_data.values]}
            }

        # 7. 所属社区分布图（横向柱状图）
        community_col = None
        for col in ['所属社区', 'community', '社区']:
            if col in df.columns:
                community_col = col
                break
        if community_col:
            community_data = df[community_col].fillna('未知').value_counts().head(25)
            result['charts']['community'] = {
                'title': '案件社区分布',
                'type': 'bar',
                'data': {'categories': [str(k) for k in community_data.index], 'values': [int(v) for v in community_data.values]}
            }

        # 8. 处置部门案件占比图（饼状图）
        dept_col = None
        for col in ['处置部门', 'department', '处理部门', '责任部门']:
            if col in df.columns:
                dept_col = col
                break
        if dept_col:
            dept_data = df[dept_col].fillna('未知').value_counts()
            result['charts']['department_pie'] = {
                'title': '处置部门案件占比',
                'type': 'pie',
                'data': [{'name': str(k), 'value': int(v)} for k, v in dept_data.items()]
            }

        # 9. 各处置部门平均处置时间图（横向柱状图）
        close_time_col = None
        for col in ['结案时间', 'close_time', 'handle_time', '完成时间']:
            if col in df.columns:
                close_time_col = col
                break

        report_time_col = None
        for col in ['上报时间', 'report_time', '创建时间']:
            if col in df.columns:
                report_time_col = col
                break

        if close_time_col and report_time_col and dept_col:
            try:
                df['_close_time'] = pd.to_datetime(df[close_time_col], errors='coerce')
                df['_report_time'] = pd.to_datetime(df[report_time_col], errors='coerce')
                df['_handling_hours'] = (df['_close_time'] - df['_report_time']).dt.total_seconds() / 3600

                valid_df = df[(df['_handling_hours'] > 0) & (df['_handling_hours'] < 720)]
                if len(valid_df) > 0:
                    avg_time_by_dept = valid_df.groupby(dept_col)['_handling_hours'].mean().sort_values()
                    result['charts']['avg_handling_time'] = {
                        'title': '各处置部门平均处置时间',
                        'type': 'bar',
                        'data': {
                            'categories': [str(k) for k in avg_time_by_dept.index],
                            'values': [round(v, 1) for v in avg_time_by_dept.values]
                        },
                        'unit': '小时'
                    }
            except Exception as e:
                print(f"[图表分析] 计算处置时间出错: {str(e)}")

        print(f"[图表分析] 分析完成，生成 {len(result['charts'])} 个图表")
        return jsonify(result), 200

    except Exception as e:
        print(f"Error in chart_analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 小工具模块API - 市容环卫案件分配
@app.route('/api/tools/huanwei-assignment', methods=['POST'])
@protected
def huanwei_assignment():
    import tempfile
    import os
    output_file = None
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # 检查文件类型
        if not file.filename.endswith('.xlsx'):
            return jsonify({'error': 'Only xlsx files are allowed'}), 400

        print(f"Processing huanwei assignment file: {file.filename}")

        # 读取Excel文件
        try:
            df = pd.read_excel(file)
            print(f"Successfully read Excel file, rows: {len(df)}, columns: {list(df.columns)}")
        except Exception as read_error:
            print(f"Error reading Excel file: {str(read_error)}")
            return jsonify({'error': f'读取Excel文件失败: {str(read_error)}'}), 400

        # 检查必要的列是否存在
        required_cols = ['处置部门', '所属片区']
        for col in required_cols:
            if col not in df.columns:
                return jsonify({'error': f'Missing required column: {col}. 文件中必须包含以下列: {", ".join(required_cols)}'}), 400

        # 处理数据：仅更新处置部门列，所属片区列保持不变
        filter_condition = df["处置部门"] == "市容环卫中心"
        matched_count = filter_condition.sum()
        print(f"Found {matched_count} rows with '市容环卫中心' as 处置部门")

        df["所属片区"] = df["所属片区"].astype(str)  # 确保是字符串类型
        # 基于所属片区列的值更新处置部门列，添加"环卫"前缀
        df.loc[filter_condition, "处置部门"] = "环卫" + df.loc[filter_condition, "所属片区"]

        print(f"Updated {matched_count} rows with new department names")

        # 生成输出文件名
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
            output_file = temp.name

        # 保存处理后的数据
        df.to_excel(output_file, index=False)
        print(f"Successfully saved processed file to: {output_file}")

        # 读取文件内容并返回
        from flask import send_file
        response = send_file(output_file, as_attachment=True, download_name='hwcase_data_updated.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # 在响应发送后删除临时文件的回调
        @response.call_on_close
        def cleanup():
            try:
                if output_file and os.path.exists(output_file):
                    os.remove(output_file)
                    print(f"Cleaned up temporary file: {output_file}")
            except Exception as cleanup_error:
                print(f"Error cleaning up temporary file: {cleanup_error}")

        return response
    except Exception as e:
        print(f"Error in huanwei_assignment: {str(e)}")
        import traceback
        traceback.print_exc()
        # 清理临时文件
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass
        return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500

# 小工具模块API - 地址信息提取
@app.route('/api/tools/extract-location', methods=['POST'])
@protected
def extract_location():
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # 检查文件类型
        if not file.filename.endswith('.xlsx'):
            return jsonify({'error': 'Only xlsx files are allowed'}), 400

        # 读取Excel文件
        df = pd.read_excel(file)

        # 检查必要的列是否存在
        required_cols = ['问题描述', '地址描述']
        for col in required_cols:
            if col not in df.columns:
                return jsonify({'error': f'Missing required column: {col}'}), 400

        # 处理数据：提取地址信息
        updated_count = 0
        for idx, row in df.iterrows():
            addr_desc = str(row["地址描述"]).strip()
            if addr_desc in ["无位置信息", "无位置描述", "没有相关位置描述", "nan"]:
                # 从问题描述提取地址
                new_addr = extract_location_from_text(row["问题描述"])
                df.loc[idx, "地址描述"] = new_addr
                updated_count += 1

        # 生成输出文件名
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
            output_file = temp.name

        # 保存处理后的数据
        df.to_excel(output_file, index=False)

        # 读取文件内容并返回
        from flask import send_file
        return send_file(output_file, as_attachment=True, download_name='case_data_with_extracted_location.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        print(f"Error in extract_location: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
@protected
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
        category = session.query(Category).filter_by(id=category_id).first()
        if not category:
            return jsonify({'error': '栏目不存在'}), 404

        data = request.json
        if 'name' in data:
            category.name = data['name']
        if 'slug' in data:
            category.slug = data['slug']
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
@protected
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

# 获取单个文章详情
@app.route('/api/articles/<int:id>', methods=['GET'])
@protected
def get_article_detail(id):
    session = Session()
    try:
        article = session.query(Article).filter_by(id=id).first()
        if not article:
            return jsonify({'error': '文章不存在'}), 404

        # 增加阅读计数
        article.view_count = (article.view_count or 0) + 1
        session.commit()

        article_dict = {
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
        }

        return jsonify(article_dict), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_article_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 创建文章
@app.route('/api/articles', methods=['POST'])
@protected
def create_article():
    session = Session()
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        category_id = data.get('category_id')
        content = data.get('content', '')
        summary = data.get('summary', '')
        status = data.get('status', 'draft')
        file_path = data.get('file_path', '')

        if not title:
            return jsonify({'error': '标题不能为空'}), 400
        if not category_id:
            return jsonify({'error': '请选择栏目'}), 400

        slug = generate_slug(title)
        # 确保slug唯一
        existing = session.query(Article).filter_by(slug=slug).first()
        if existing:
            slug = slug + '-' + str(int(datetime.datetime.now().timestamp()))

        article = Article(
            title=title,
            slug=slug,
            content=content,
            summary=summary,
            category_id=category_id,
            author_id=request.user_id,
            status=status,
            file_path=file_path,
            published_at=datetime.datetime.now() if status == 'published' else None
        )
        session.add(article)
        session.commit()

        return jsonify({
            'id': article.id,
            'title': article.title,
            'message': '创建成功'
        }), 201
    except Exception as e:
        session.rollback()
        print(f"Error in create_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 更新文章
@app.route('/api/articles/<int:id>', methods=['PUT'])
@protected
def update_article(id):
    session = Session()
    try:
        article = session.query(Article).filter_by(id=id).first()
        if not article:
            return jsonify({'error': '文章不存在'}), 404

        data = request.get_json()
        title = data.get('title', '').strip()
        category_id = data.get('category_id')
        content = data.get('content', '')
        summary = data.get('summary', '')
        status = data.get('status', 'draft')
        file_path = data.get('file_path', '')

        if title:
            article.title = title
        if category_id:
            article.category_id = category_id
        if content is not None:
            article.content = content
        if summary is not None:
            article.summary = summary
        if status:
            article.status = status
            if status == 'published' and not article.published_at:
                article.published_at = datetime.datetime.now()
        if file_path is not None:
            article.file_path = file_path

        session.commit()

        return jsonify({
            'id': article.id,
            'title': article.title,
            'message': '更新成功'
        }), 200
    except Exception as e:
        session.rollback()
        print(f"Error in update_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# 删除文章
@app.route('/api/articles/<int:id>', methods=['DELETE'])
@protected
def delete_article(id):
    session = Session()
    try:
        article = session.query(Article).filter_by(id=id).first()
        if not article:
            return jsonify({'error': '文章不存在'}), 404

        session.delete(article)
        session.commit()

        return jsonify({'message': '删除成功'}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in delete_article: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/cms/home-columns', methods=['GET'])
@protected
def get_home_columns():
    session = Session()
    try:
        # 获取所有栏目
        categories = session.query(Category).order_by(Category.order).all()

        result = []
        for cat in categories:
            # 获取该栏目下最新的5篇已发布文章
            articles = session.query(Article).filter_by(
                category_id=cat.id,
                status='published'
            ).order_by(Article.created_at.desc()).limit(5).all()

            articles_list = []
            for article in articles:
                articles_list.append({
                    'id': article.id,
                    'title': article.title,
                    'summary': article.summary,
                    'view_count': article.view_count,
                    'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None
                })

            result.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'description': cat.description,
                'articles': articles_list
            })

        session.commit()
        return jsonify(result), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_home_columns: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ==================== 数据编辑 API ====================

# 数据编辑列表显示的字段（精简版）
DATA_EDIT_DISPLAY_FIELDS = [
    '任务号', '问题描述', '处置部门', '结案时间', '是否超时', '延期次数', '返工次数'
]

# 数据编辑弹窗可编辑的字段（完整版）
DATA_EDIT_FORM_FIELDS = [
    '任务号', '上报时间', '问题描述', '所属街道', '所属社区',
    '处置部门', '结案时间', '是否超时', '延期次数', '返工次数'
]

@app.route('/api/data-edit/records', methods=['GET'])
@admin_required
def get_data_edit_records():
    """获取数据列表（支持分页、筛选、查找）"""
    try:
        table_name = request.args.get('table_name', '')
        month = request.args.get('month', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        search_field = request.args.get('search_field', '')
        search_value = request.args.get('search_value', '')

        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        # 获取表的列名
        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 构建SQL查询
        where_clauses = []
        params = {}

        # 月份筛选
        if month and '月份' in columns:
            where_clauses.append("`月份` = :month")
            params['month'] = month

        # 字段查找
        if search_field and search_value:
            if search_field in columns:
                if search_field == '任务号':
                    # 任务号精确匹配
                    where_clauses.append(f"`{search_field}` = :search_value")
                else:
                    # 其他字段模糊匹配
                    where_clauses.append(f"`{search_field}` LIKE :search_value")
                    search_value = f"%{search_value}%"
                params['search_value'] = search_value

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        # 查询总数
        count_sql = f"SELECT COUNT(*) as cnt FROM `{table_name}` {where_sql}"
        with engine.connect() as conn:
            result = conn.execute(text(count_sql), params)
            total = result.fetchone()[0]

        # 查询数据
        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM `{table_name}` {where_sql} LIMIT {page_size} OFFSET {offset}"
        df = pd.read_sql(text(data_sql), engine, params=params)

        # 转换数据
        records = df.to_dict('records')
        # 处理 NaN 值
        for record in records:
            for key in record:
                if pd.isna(record[key]):
                    record[key] = None

        return jsonify({
            'records': records,
            'total': total,
            'page': page,
            'page_size': page_size,
            'columns': columns,
            'display_fields': [f for f in DATA_EDIT_DISPLAY_FIELDS if f in columns],
            'edit_fields': [f for f in DATA_EDIT_FORM_FIELDS if f in columns]
        }), 200

    except Exception as e:
        print(f"Error in get_data_edit_records: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/data-edit/record', methods=['POST'])
@admin_required
def create_data_edit_record():
    """新增记录"""
    session = Session()
    try:
        data = request.get_json()
        table_name = data.get('table_name')
        record_data = data.get('record_data', {})

        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        # 获取表的列名
        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 检查任务号是否重复
        if '任务号' in record_data and '任务号' in columns:
            with engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table_name}` WHERE `任务号` = :task_number"),
                    {'task_number': record_data['任务号']}
                )
                if result.fetchone()[0] > 0:
                    return jsonify({'error': '任务号已存在，不能重复添加'}), 400

        # 构建插入SQL
        fields = []
        values = []
        params = {}
        for key, value in record_data.items():
            if key in columns and value is not None and value != '':
                fields.append(f"`{key}`")
                values.append(f":{key}")
                params[key] = value

        if not fields:
            return jsonify({'error': '没有有效数据'}), 400

        insert_sql = f"INSERT INTO `{table_name}` ({', '.join(fields)}) VALUES ({', '.join(values)})"
        with engine.connect() as conn:
            conn.execute(text(insert_sql), params)
            conn.commit()

        # 记录操作日志
        log = OperationLog(
            user_id=request.user_id,
            table_name=table_name,
            operation_type='create',
            record_id=record_data.get('任务号', ''),
            old_value=None,
            new_value=json.dumps(record_data, ensure_ascii=False)
        )
        session.add(log)
        session.commit()

        return jsonify({'message': '新增成功', 'task_number': record_data.get('任务号')}), 201

    except Exception as e:
        session.rollback()
        print(f"Error in create_data_edit_record: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/data-edit/record/<task_number>', methods=['PUT'])
@admin_required
def update_data_edit_record(task_number):
    """修改记录"""
    session = Session()
    try:
        data = request.get_json()
        table_name = data.get('table_name')
        new_data = data.get('record_data', {})

        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 查询原数据
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM `{table_name}` WHERE `任务号` = :task_number"),
                {'task_number': task_number}
            )
            row = result.fetchone()
            if not row:
                return jsonify({'error': '记录不存在'}), 404

            # 转换为字典
            old_data = dict(zip(columns, row))

        # 构建更新SQL
        set_clauses = []
        params = {'task_number': task_number}
        for key, value in new_data.items():
            if key in columns and key != '任务号':  # 任务号不允许修改
                set_clauses.append(f"`{key}` = :{key}")
                params[key] = value

        if not set_clauses:
            return jsonify({'error': '没有需要更新的字段'}), 400

        update_sql = f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE `任务号` = :task_number"
        with engine.connect() as conn:
            conn.execute(text(update_sql), params)
            conn.commit()

        # 记录操作日志
        log = OperationLog(
            user_id=request.user_id,
            table_name=table_name,
            operation_type='update',
            record_id=task_number,
            old_value=json.dumps(old_data, ensure_ascii=False, default=str),
            new_value=json.dumps(new_data, ensure_ascii=False)
        )
        session.add(log)
        session.commit()

        return jsonify({'message': '修改成功'}), 200

    except Exception as e:
        session.rollback()
        print(f"Error in update_data_edit_record: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/data-edit/record/<task_number>', methods=['DELETE'])
@admin_required
def delete_data_edit_record(task_number):
    """删除单条记录"""
    session = Session()
    try:
        table_name = request.args.get('table_name')
        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 查询原数据
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM `{table_name}` WHERE `任务号` = :task_number"),
                {'task_number': task_number}
            )
            row = result.fetchone()
            if not row:
                return jsonify({'error': '记录不存在'}), 404

            old_data = dict(zip(columns, row))

        # 删除记录
        with engine.connect() as conn:
            conn.execute(
                text(f"DELETE FROM `{table_name}` WHERE `任务号` = :task_number"),
                {'task_number': task_number}
            )
            conn.commit()

        # 记录操作日志
        log = OperationLog(
            user_id=request.user_id,
            table_name=table_name,
            operation_type='delete',
            record_id=task_number,
            old_value=json.dumps(old_data, ensure_ascii=False, default=str),
            new_value=None
        )
        session.add(log)
        session.commit()

        return jsonify({'message': '删除成功'}), 200

    except Exception as e:
        session.rollback()
        print(f"Error in delete_data_edit_record: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/data-edit/batch-delete', methods=['POST'])
@admin_required
def batch_delete_data_edit_records():
    """批量删除记录"""
    session = Session()
    try:
        data = request.get_json()
        table_name = data.get('table_name')
        task_numbers = data.get('task_numbers', [])

        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400
        if not task_numbers:
            return jsonify({'error': '请选择要删除的记录'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 查询原数据用于日志
        placeholders = ','.join([f":tn{i}" for i in range(len(task_numbers))])
        params = {f"tn{i}": tn for i, tn in enumerate(task_numbers)}

        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM `{table_name}` WHERE `任务号` IN ({placeholders})"),
                params
            )
            rows = result.fetchall()
            old_records = [dict(zip(columns, row)) for row in rows]

        # 批量删除
        with engine.connect() as conn:
            conn.execute(
                text(f"DELETE FROM `{table_name}` WHERE `任务号` IN ({placeholders})"),
                params
            )
            conn.commit()

        # 记录操作日志
        for record in old_records:
            log = OperationLog(
                user_id=request.user_id,
                table_name=table_name,
                operation_type='delete',
                record_id=record.get('任务号', ''),
                old_value=json.dumps(record, ensure_ascii=False, default=str),
                new_value=None
            )
            session.add(log)
        session.commit()

        return jsonify({'message': f'成功删除 {len(task_numbers)} 条记录'}), 200

    except Exception as e:
        session.rollback()
        print(f"Error in batch_delete_data_edit_records: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@app.route('/api/data-edit/batch-update', methods=['POST'])
@admin_required
def batch_update_data_edit_records():
    """批量修改记录"""
    session = Session()
    try:
        data = request.get_json()
        table_name = data.get('table_name')
        task_numbers = data.get('task_numbers', [])
        update_data = data.get('update_data', {})

        if not table_name:
            return jsonify({'error': '请选择数据表'}), 400
        if not task_numbers:
            return jsonify({'error': '请选择要修改的记录'}), 400
        if not update_data:
            return jsonify({'error': '请提供修改内容'}), 400

        # 检查表是否存在
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if table_name not in tables:
            return jsonify({'error': '数据表不存在'}), 400

        columns = [col['name'] for col in inspector.get_columns(table_name)]

        # 构建更新SQL
        set_clauses = []
        for key, value in update_data.items():
            if key in columns and key != '任务号':
                set_clauses.append(f"`{key}` = :{key}")

        if not set_clauses:
            return jsonify({'error': '没有有效的更新字段'}), 400

        placeholders = ','.join([f":tn{i}" for i in range(len(task_numbers))])
        params = {f"tn{i}": tn for i, tn in enumerate(task_numbers)}
        params.update(update_data)

        # 查询原数据用于日志
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM `{table_name}` WHERE `任务号` IN ({placeholders})"),
                {f"tn{i}": tn for i, tn in enumerate(task_numbers)}
            )
            rows = result.fetchall()
            old_records = [dict(zip(columns, row)) for row in rows]

        # 执行更新
        update_sql = f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE `任务号` IN ({placeholders})"
        with engine.connect() as conn:
            conn.execute(text(update_sql), params)
            conn.commit()

        # 记录操作日志
        for record in old_records:
            log = OperationLog(
                user_id=request.user_id,
                table_name=table_name,
                operation_type='update',
                record_id=record.get('任务号', ''),
                old_value=json.dumps(record, ensure_ascii=False, default=str),
                new_value=json.dumps(update_data, ensure_ascii=False)
            )
            session.add(log)
        session.commit()

        return jsonify({'message': f'成功修改 {len(task_numbers)} 条记录'}), 200

    except Exception as e:
        session.rollback()
        print(f"Error in batch_update_data_edit_records: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# ==================== 操作日志 API ====================

@app.route('/api/operation-logs', methods=['GET'])
@admin_required
def get_operation_logs():
    """获取操作日志列表"""
    try:
        table_name = request.args.get('table_name', '')
        operation_type = request.args.get('operation_type', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        session = Session()
        query = session.query(OperationLog)

        if table_name:
            query = query.filter(OperationLog.table_name == table_name)
        if operation_type:
            query = query.filter(OperationLog.operation_type == operation_type)

        total = query.count()
        logs = query.order_by(OperationLog.created_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        # 获取用户名
        user_ids = list(set([log.user_id for log in logs]))
        users = session.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.username for u in users}

        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'user_id': log.user_id,
                'username': user_map.get(log.user_id, '未知'),
                'table_name': log.table_name,
                'operation_type': log.operation_type,
                'record_id': log.record_id,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else None
            })

        return jsonify({
            'logs': result,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200

    except Exception as e:
        print(f"Error in get_operation_logs: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    return send_from_directory(upload_dir, filename)

# 前端静态文件路由 - 放在最后
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # 构建前端文件路径
    frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
    
    # 如果路径为空或者不存在文件，返回 index.html
    if not path or not os.path.exists(os.path.join(frontend_dist, path)):
        return send_from_directory(frontend_dist, 'index.html')
    
    # 否则返回请求的文件
    return send_from_directory(frontend_dist, path)

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG', '1') == '1',
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', '5000'))
    )