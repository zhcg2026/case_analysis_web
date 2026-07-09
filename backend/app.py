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
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
from jinja2 import Template

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

try:
    from backend.flood_routes import register_flood_monitor_routes
except ImportError:
    from flood_routes import register_flood_monitor_routes

# 导入处理docx文件的库
from docx import Document

# 导入RAG模块
try:
    from backend.rag import (
        init_rag,
        insert_document,
        search_similar,
        delete_document,
        ask_question,
        list_documents,
        get_collection_stats
    )
except ImportError:
    from rag import (
        init_rag,
        insert_document,
        search_similar,
        delete_document,
        ask_question,
        list_documents,
        get_collection_stats
    )

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

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200

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
    from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
    from sqlalchemy.sql import func
    from sqlalchemy.orm import sessionmaker

    # 检查必要的数据库配置
    if not all([DB_USER, DB_PASSWORD, DB_HOST]):
        print("警告: 数据库配置不完整，请设置 DB_USER, DB_PASSWORD, DB_HOST 环境变量")
        raise Exception("数据库配置缺失")

    # 创建数据库引擎
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4', pool_pre_ping=True, pool_recycle=3600)
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

    # ======== 汛情值守模块模型 ========

    # 天气记录模型
    class FloodWeatherRecord(Base):
        __tablename__ = 'flood_weather_records'
        id = Column(Integer, primary_key=True, autoincrement=True)
        city_code = Column(String(20))
        weather_data = Column(Text)          # JSON: 完整天气数据快照
        temperature = Column(String(20))
        humidity = Column(String(20))
        wind_direction = Column(String(20))
        wind_power = Column(String(20))
        weather_text = Column(String(50))
        rainfall_1h = Column(String(20))
        recorded_at = Column(DateTime)
        created_at = Column(DateTime, server_default=func.now())

    # 降雨事件模型
    class FloodRainEvent(Base):
        __tablename__ = 'flood_rain_events'
        id = Column(Integer, primary_key=True, autoincrement=True)
        start_time = Column(DateTime)
        end_time = Column(DateTime)
        max_rainfall_1h = Column(String(20))
        total_rainfall = Column(String(20))
        intensity = Column(String(20))
        status = Column(String(20), default='active')
        created_at = Column(DateTime, server_default=func.now())

    # 积水点模型
    class FloodWaterloggingPoint(Base):
        __tablename__ = 'flood_waterlogging_points'
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(100), nullable=False)
        road_type = Column(String(50))        # 道路类型：桥涵/路口路段/城中村
        longitude = Column(String(50))
        latitude = Column(String(50))
        responsible_person = Column(String(100))  # 积水点责任人
        responsible_phone = Column(String(20))
        duty_persons = Column(Text)           # 值守人员(JSON数组，支持多人)
        traffic_police = Column(String(100))  # 交警责任人
        traffic_police_phone = Column(String(20))
        water_level = Column(String(20), default='normal')
        water_depth = Column(String(20))
        management_unit = Column(String(100)) # 管理单位
        monitoring_points = Column(Text)      # 监控点位(JSON数组)
        remarks = Column(Text)                # 备注
        last_updated = Column(DateTime)
        created_at = Column(DateTime, server_default=func.now())
        updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 调度台账模型
    class FloodDispatchRecord(Base):
        __tablename__ = 'flood_dispatch_records'
        id = Column(Integer, primary_key=True, autoincrement=True)
        record_type = Column(String(50))
        title = Column(String(200))
        content = Column(Text)
        event_time = Column(DateTime)
        weather_snapshot = Column(Text)      # JSON: 当时天气快照
        location = Column(String(200))
        images = Column(Text)                # JSON: 图片路径数组
        operator = Column(String(50))
        warning_id = Column(Integer, nullable=True)  # 关联预警ID
        status = Column(String(20), default='active')
        created_at = Column(DateTime, server_default=func.now())

    # 值班排班模型
    class FloodDutyShift(Base):
        __tablename__ = 'flood_duty_shifts'
        id = Column(Integer, primary_key=True, autoincrement=True)
        shift_date = Column(DateTime, nullable=False)
        shift_name = Column(String(50))
        person1 = Column(String(50))
        person1_phone = Column(String(20))
        person2 = Column(String(50))
        person2_phone = Column(String(20))
        created_at = Column(DateTime, server_default=func.now())
        updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 预警状态模型
    class FloodWarning(Base):
        __tablename__ = 'flood_warnings'
        id = Column(Integer, primary_key=True, autoincrement=True)
        level = Column(String(20), nullable=False)  # blue, yellow, orange, red
        status = Column(String(20), default='active')  # active, ended
        start_time = Column(DateTime, default=func.now())
        end_time = Column(DateTime, nullable=True)
        report_snapshot = Column(Text)  # 预警结束时自动生成的报告
        created_at = Column(DateTime, server_default=func.now())

    # 带班领导模型
    class FloodDutyLeader(Base):
        __tablename__ = 'flood_duty_leaders'
        id = Column(Integer, primary_key=True, autoincrement=True)
        title = Column(String(50), default='带班领导')  # 职务名称，如"副局长"、"局长"
        name = Column(String(50), default='')
        phone = Column(String(20), default='')
        duty_date = Column(DateTime, nullable=True)
        created_at = Column(DateTime, server_default=func.now())
        updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 应急物资存放点模型
    class FloodEmergencySupply(Base):
        __tablename__ = 'flood_emergency_supplies'
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(100), nullable=False)
        longitude = Column(String(50))
        latitude = Column(String(50))
        supplies_list = Column(Text)          # JSON: 物资清单
        contact_person = Column(String(50))
        contact_phone = Column(String(20))
        remark = Column(Text)
        created_at = Column(DateTime, server_default=func.now())
        updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 人员花名册模型
    class FloodPersonnel(Base):
        __tablename__ = 'flood_personnel'
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(50), nullable=False, unique=True)
        phone = Column(String(20), default='')
        group_type = Column(String(20), nullable=False, default='admin')  # admin/group_a/group_b/night
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, server_default=func.now())
        updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 每日排班明细模型（一人一条记录）
    class FloodDutyAssignment(Base):
        __tablename__ = 'flood_duty_assignments'
        id = Column(Integer, primary_key=True, autoincrement=True)
        assignment_date = Column(DateTime, nullable=False)
        shift_name = Column(String(20), nullable=False)  # 白班/夜班
        person_name = Column(String(50), nullable=False)
        person_phone = Column(String(20), default='')
        source = Column(String(20), default='regular')  # regular=正常排班/added=增援
        warning_id = Column(Integer, nullable=True)
        created_at = Column(DateTime, server_default=func.now())

    # 增援操作日志模型
    class FloodStaffingLog(Base):
        __tablename__ = 'flood_staffing_logs'
        id = Column(Integer, primary_key=True, autoincrement=True)
        warning_id = Column(Integer, nullable=True)
        recommended_person = Column(String(50), nullable=False)
        recommended_phone = Column(String(20), default='')
        reason = Column(Text)
        status = Column(String(20), default='recommended')  # recommended/confirmed/rejected
        confirmed_by = Column(String(50))
        created_at = Column(DateTime, server_default=func.now())

    # 创建数据库表
    # 只创建不存在的表，保留现有数据
    # 多worker并发时可能冲突，加重试
    import time as _time
    for _retry in range(5):
        try:
            Base.metadata.create_all(engine)
            break
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "concurrent" in err_str or "being modified" in err_str:
                if _retry < 4:
                    _time.sleep(1 + _retry)
                    continue
                print(f"数据库表创建跳过（重试后）: {e}")
            else:
                raise

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

    # 数据库迁移：确保 data_management 和 spotcheck 列存在
    try:
        with engine.connect() as conn:
            for col_name in ['data_management', 'spotcheck']:
                result = conn.execute(text(f"SHOW COLUMNS FROM permissions LIKE '{col_name}'"))
                if result.fetchone() is None:
                    conn.execute(text(f"ALTER TABLE permissions ADD COLUMN {col_name} INT NOT NULL DEFAULT 0"))
                    conn.commit()
                    print(f"数据库迁移：已添加 {col_name} 列")
    except Exception as e:
        print(f"数据库迁移检查(data_management/spotcheck): {e}")

    # 数据库迁移：添加 flood_monitor 权限列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM permissions LIKE 'flood_monitor'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE permissions ADD COLUMN flood_monitor INT NOT NULL DEFAULT 0"))
                conn.commit()
                print("数据库迁移：已添加 flood_monitor 列")
    except Exception as e:
        print(f"数据库迁移检查(flood_monitor): {e}")

    # 数据库迁移：添加 flood_warnings 表的 report_snapshot 列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM flood_warnings LIKE 'report_snapshot'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE flood_warnings ADD COLUMN report_snapshot TEXT"))
                conn.commit()
                print("数据库迁移：已添加 report_snapshot 列")
    except Exception as e:
        print(f"数据库迁移检查(report_snapshot): {e}")

    # 初始化人员花名册数据
    try:
        SessionInit = sessionmaker(bind=engine)
        session_init = SessionInit()
        existing = session_init.query(FloodPersonnel).count()
        if existing == 0:
            initial_persons = [
                ('王亮', '', 'admin'), ('杜婧楠', '', 'admin'), ('韩司宇辰', '', 'admin'),
                ('白雪', '', 'admin'), ('裴迎', '', 'admin'), ('秦碧霞', '', 'admin'),
                ('杨雅茜', '', 'admin'), ('范倩', '', 'admin'),
                ('李瑞瑶', '', 'group_a'), ('展晓瑞', '', 'group_a'), ('茹佳兆', '', 'group_a'),
                ('张萌', '', 'group_b'), ('张金龙', '', 'group_b'),
                ('王康乐', '', 'night'), ('常家仪', '', 'night'), ('张青', '', 'night'),
            ]
            for name, phone, gtype in initial_persons:
                session_init.add(FloodPersonnel(name=name, phone=phone, group_type=gtype))
            session_init.commit()
            print(f"已初始化 {len(initial_persons)} 名人员花名册")
        session_init.close()
    except Exception as e:
        print(f"人员花名册初始化: {e}")

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

    # 注册汛情值守路由
    register_flood_monitor_routes(
        app=app,
        Session=Session,
        FloodWeatherRecord=FloodWeatherRecord,
        FloodRainEvent=FloodRainEvent,
        FloodWaterloggingPoint=FloodWaterloggingPoint,
        FloodDispatchRecord=FloodDispatchRecord,
        FloodDutyShift=FloodDutyShift,
        FloodEmergencySupply=FloodEmergencySupply,
        protected=protected,
        FloodWarning=FloodWarning,
        FloodDutyLeader=FloodDutyLeader,
        FloodPersonnel=FloodPersonnel,
        FloodDutyAssignment=FloodDutyAssignment,
        FloodStaffingLog=FloodStaffingLog,
    )

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
        permission = session.execute(text("SELECT dashboard, data_management, assessment, data_analysis, spotcheck, cases, map, huiwentai, business, flood_monitor FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
        permissions = {
            'dashboard': False,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False,
            'flood_monitor': False
        }
        if permission:
            permissions = {
                'dashboard': permission[0],
                'data_management': permission[1],
                'assessment': permission[2],
                'data_analysis': permission[3],
                'spotcheck': permission[4],
                'cases': permission[5],
                'map': permission[6],
                'huiwentai': permission[7],
                'business': permission[8],
                'flood_monitor': permission[9]
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
                'data_management': True,
                'assessment': True,
                'data_analysis': True,
                'spotcheck': True,
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
        permission = session.execute(text("SELECT dashboard, data_management, assessment, data_analysis, spotcheck, cases, map, huiwentai, business, flood_monitor FROM permissions WHERE user_id = :user_id"), {'user_id': request.user_id}).fetchone()

        permissions = {
            'dashboard': False,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False,
            'flood_monitor': False
        }

        if permission:
            permissions = {
                'dashboard': permission[0],
                'data_management': permission[1],
                'assessment': permission[2],
                'data_analysis': permission[3],
                'spotcheck': permission[4],
                'cases': permission[5],
                'map': permission[6],
                'huiwentai': permission[7],
                'business': permission[8],
                'flood_monitor': permission[9]
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
            'data_management': True,
            'assessment': True,
            'data_analysis': True,
            'spotcheck': True,
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
            permission = session.execute(text("SELECT dashboard, data_management, assessment, data_analysis, spotcheck, cases, map, huiwentai, business, flood_monitor FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
            permissions = {
                'dashboard': False,
                'data_management': False,
                'assessment': False,
                'data_analysis': False,
                'spotcheck': False,
                'cases': False,
                'map': False,
                'huiwentai': False,
                'business': False
            }
            if permission:
                permissions = {
                    'dashboard': permission[0],
                    'data_management': permission[1],
                    'assessment': permission[2],
                    'data_analysis': permission[3],
                    'spotcheck': permission[4],
                    'cases': permission[5],
                    'map': permission[6],
                    'huiwentai': permission[7],
                    'business': permission[8]
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
        session.flush()  # 获取 new_user.id 但不提交事务
        
        # 为新用户添加默认权限（包含所有权限列）
        session.execute(text("INSERT INTO permissions (user_id, dashboard, data_management, assessment, data_analysis, spotcheck, cases, map, huiwentai, business, flood_monitor) VALUES (:user_id, :dashboard, :data_management, :assessment, :data_analysis, :spotcheck, :cases, :map, :huiwentai, :business, :flood_monitor)"), {
            'user_id': new_user.id,
            'dashboard': False,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False,
            'flood_monitor': False
        })
        session.commit()

        return jsonify({
            'id': new_user.id,
            'username': new_user.username,
            'role': new_user.role,
            'permissions': {
                'dashboard': False,
                'data_management': False,
                'assessment': False,
                'data_analysis': False,
                'spotcheck': False,
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
        session.execute(text("UPDATE permissions SET dashboard = :dashboard, data_management = :data_management, assessment = :assessment, data_analysis = :data_analysis, spotcheck = :spotcheck, cases = :cases, map = :map, huiwentai = :huiwentai, business = :business, flood_monitor = :flood_monitor WHERE user_id = :user_id"), {
            'user_id': user_id,
            'dashboard': data.get('dashboard', False),
            'data_management': data.get('data_management', False),
            'assessment': data.get('assessment', False),
            'data_analysis': data.get('data_analysis', False),
            'spotcheck': data.get('spotcheck', False),
            'cases': data.get('cases', False),
            'map': data.get('map', False),
            'huiwentai': data.get('huiwentai', False),
            'business': data.get('business', False),
            'flood_monitor': data.get('flood_monitor', False)
        })
        session.commit()

        # 返回更新后的权限
        permission = session.execute(text("SELECT dashboard, data_management, assessment, data_analysis, spotcheck, cases, map, huiwentai, business, flood_monitor FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
        permissions = {
            'dashboard': False,
            'data_management': False,
            'assessment': False,
            'data_analysis': False,
            'spotcheck': False,
            'cases': False,
            'map': False,
            'huiwentai': False,
            'business': False,
            'flood_monitor': False
        }
        if permission:
            permissions = {
                'dashboard': permission[0],
                'data_management': permission[1],
                'assessment': permission[2],
                'data_analysis': permission[3],
                'spotcheck': permission[4],
                'cases': permission[5],
                'map': permission[6],
                'huiwentai': permission[7],
                'business': permission[8],
                'flood_monitor': permission[9]
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

# 获取数据表某列的唯一值
@app.route('/api/column-values', methods=['GET'])
@protected
def get_column_values():
    """获取指定数据表某列的唯一值"""
    table_name = request.args.get('table_name')
    column = request.args.get('column')

    if not table_name or not column:
        return jsonify({'error': 'Missing parameters'}), 400

    if engine is None:
        return jsonify({'values': []}), 200

    session = Session()
    try:
        # 查询该列的唯一值
        query = text(f"SELECT DISTINCT `{column}` FROM `{table_name}` WHERE `{column}` IS NOT NULL LIMIT 100")
        result = session.execute(query)
        values = [row[0] for row in result.fetchall()]
        return jsonify({'values': values}), 200
    except Exception as e:
        session.rollback()
        print(f"Error in get_column_values: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

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
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
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
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
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
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
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
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass
        
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

    # 调试：打印当前阶段名称的唯一值
    if len(cases) > 0:
        stage_vals = set()
        for c in cases:
            val = c.get('当前阶段名称')
            if val is not None and pd.notna(val):
                stage_vals.add(str(val))
        print(f"[调试] 当前阶段名称的唯一值: {sorted(stage_vals)}")

    team_results = []

    for dept_name in target_departments:
        dept_cases = [c for c in cases if c.get('处置部门') == dept_name]

        total = len(dept_cases)
        # 办结案件：当前阶段名称 = "[办结]" 或 "办结"
        closed_cases = [c for c in dept_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        # 按期结案：只统计办结案件中不超时的
        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        # 超期结案、延期次数、返工次数：统计全部案件
        overdue = 0
        delay = 0
        rework = 0

        for case in dept_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            # 返工次数：0=没返工，非0=有返工
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        # 按期率基于总案件数，其他基于总案件数
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
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
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

        print(f"  {dept_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")
    
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
        # 办结案件：当前阶段名称 = "[办结]" 或 "办结"
        closed_cases = [c for c in area_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        # 按期结案：只统计办结案件中不超时的
        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        # 超期结案、延期次数、返工次数：统计全部案件
        overdue = 0
        delay = 0
        rework = 0

        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            # 返工次数：0=没返工，非0=有返工
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        # 按期率基于总案件数，其他基于总案件数
        on_time_rate = on_time / total if total > 0 else 0
        overdue_rate = overdue / total if total > 0 else 0
        delay_rate = delay / total if total > 0 else 0
        rework_rate = rework / total if total > 0 else 0

        score = (
            (on_time_rate * coefficients['on_time'] + overdue_rate * coefficients['overdue']) * coefficients['closure_weight'] +
            (1 - delay_rate) * coefficients['delay_weight'] +
            (1 - rework_rate) * coefficients['rework_weight']
        ) * 100

        # 详细计算过程
        detail = f"""
=== {area_name} 计算详情 ===
  总案件数: {total}
  办结案件数: {closed_count}
  结案率: {closed_count}/{total} = {closure_rate:.4f}
  按期结案: {on_time} (基于总案件数)
  超期结案: {overdue} (基于全部案件)
  延期次数: {delay} (基于全部案件)
  返工次数: {rework} (基于全部案件)
  按期率: {on_time}/{total} = {on_time_rate:.4f}
  超期率: {overdue}/{total} = {overdue_rate:.4f}
  延期率: {delay}/{total} = {delay_rate:.4f}
  返工率: {rework}/{total} = {rework_rate:.4f}
  得分计算:
    = ({on_time_rate:.4f} * {coefficients['on_time']} + {overdue_rate:.4f} * {coefficients['overdue']}) * {coefficients['closure_weight']}
      + (1 - {delay_rate:.4f}) * {coefficients['delay_weight']}
      + (1 - {rework_rate:.4f}) * {coefficients['rework_weight']}
    = {score:.4f} * 100 = {score:.2f}
"""
        print(detail)
        with open('debug.log', 'a', encoding='utf-8') as f:
            f.write(detail)

        area_results.append({
            'department': area_name,
            'total_cases': total,
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
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

        print(f"  {area_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

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
        # 办结案件：当前阶段名称 = "[办结]" 或 "办结"
        closed_cases = [c for c in area_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        # 按期结案：只统计办结案件中不超时的
        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        # 超期结案、延期次数、返工次数：统计全部案件
        overdue = 0
        delay = 0
        rework = 0

        for case in area_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            # 返工次数：0=没返工，非0=有返工
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        # 按期率基于总案件数，其他基于总案件数
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
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
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

        print(f"  {area_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

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

    # 排除挂账案件
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
        # 办结案件：当前阶段名称 = "[办结]" 或 "办结"
        closed_cases = [c for c in park_cases if c.get('当前阶段名称') in ['[办结]', '办结']]
        closed_count = len(closed_cases)
        closure_rate = closed_count / total if total > 0 else 0

        # 按期结案：只统计办结案件中不超时的
        on_time = 0
        for case in closed_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')
            if not (pd.notna(is_overdue) and str(is_overdue).strip() != ''):
                on_time += 1

        # 超期结案、延期次数、返工次数：统计全部案件（已排除挂账）
        overdue = 0
        delay = 0
        rework = 0

        for case in park_cases:
            is_overdue = case.get('是否超时') or case.get('is_overdue')

            if pd.notna(is_overdue) and str(is_overdue).strip() != '':
                overdue += 1

            delay_val = case.get('延期次数') or case.get('delay')
            try:
                if delay_val is not None:
                    delay_num = int(delay_val)
                    if delay_num != 0:
                        delay += 1
            except (ValueError, TypeError):
                pass

            # 返工次数：0=没返工，非0=有返工
            rework_val = case.get('返工次数') or case.get('rework')
            try:
                if rework_val is not None:
                    rework_num = int(rework_val)
                    if rework_num != 0:
                        rework += 1
            except (ValueError, TypeError):
                pass

        # 按期率基于总案件数，其他基于总案件数
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
            'closed_cases': closed_count,
            'closure_rate': round(closure_rate * 100, 2),
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

        print(f"  {park_name}: 总数={total}, 办结={closed_count}, 按期={on_time}, 超期={overdue}, 延期={delay}, 返工={rework}, 得分={score:.2f}")

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

        # 调试：打印当前阶段名称的唯一值
        if len(cases) > 0:
            stage_vals = set()
            for c in cases:
                val = c.get('当前阶段名称')
                if val is not None and pd.notna(val):
                    stage_vals.add(str(val))
            debug_msg = f"[调试] 当前阶段名称的唯一值: {sorted(stage_vals)}"
            print(debug_msg)
            with open('debug.log', 'a', encoding='utf-8') as f:
                f.write(debug_msg + '\n')

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

# 小工具模块API - 数据脱敏获取字段
@app.route('/api/tools/data-desensitization/fields', methods=['POST'])
@protected
def get_desensitization_fields():
    """获取Excel文件的所有字段名"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        # 读取Excel文件
        df = pd.read_excel(file)

        # 获取所有字段名
        fields = list(df.columns)

        return jsonify({'fields': fields}), 200
    except Exception as e:
        print(f"Error in get_desensitization_fields: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 小工具模块API - 数据脱敏处理
@app.route('/api/tools/data-desensitization', methods=['POST'])
@protected
def process_desensitization():
    """处理数据脱敏并返回处理后的文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        # 读取字段配置
        fields_config = {}
        if 'fields' in request.form:
            import json
            fields_config = json.loads(request.form['fields'])

        # 读取Excel文件
        df = pd.read_excel(file)

        # 执行数据脱敏
        processed_df = clean_and_desensitize_data(df, fields_config)

        # 保存处理后的文件
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
            output_file = temp.name

        processed_df.to_excel(output_file, index=False)

        # 返回文件
        from flask import send_file
        return send_file(output_file, as_attachment=True, download_name='desensitized_data.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        print(f"Error in process_desensitization: {str(e)}")
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

# ==================== 知识库 RAG API ====================

@app.route('/api/knowledge/stats', methods=['GET'])
@protected
def knowledge_stats():
    """获取知识库统计信息"""
    try:
        stats = get_collection_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/documents', methods=['GET'])
@protected
def knowledge_list_documents():
    """列出知识库中的所有文档"""
    try:
        docs = list_documents()
        return jsonify({'documents': docs, 'total': len(docs)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/documents/<doc_id>', methods=['DELETE'])
@protected
def knowledge_delete_document(doc_id):
    """删除指定文档"""
    try:
        result = delete_document(doc_id)
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/documents/batch-delete', methods=['POST'])
@protected
def knowledge_batch_delete():
    """批量删除文档"""
    try:
        data = request.get_json()
        doc_ids = data.get('doc_ids', [])

        if not doc_ids:
            return jsonify({'error': '请提供要删除的文档ID列表'}), 400

        success_count = 0
        failed_count = 0
        results = []

        for doc_id in doc_ids:
            result = delete_document(doc_id)
            if result['success']:
                success_count += 1
                results.append({'doc_id': doc_id, 'success': True})
            else:
                failed_count += 1
                results.append({'doc_id': doc_id, 'success': False, 'error': result.get('message', '删除失败')})

        return jsonify({
            'success': True,
            'message': f'成功删除 {success_count} 个文档，失败 {failed_count} 个',
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/documents/delete-all', methods=['POST'])
@protected
def knowledge_delete_all():
    """删除所有文档"""
    try:
        from rag import delete_all_documents
        result = delete_all_documents()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/upload', methods=['POST'])
@protected
def knowledge_upload_document():
    """上传文档到知识库"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            # 也支持直接上传文本内容
            data = request.get_json()
            if data and 'content' in data:
                doc_id = data.get('doc_id', f'doc_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}')
                source = data.get('source', '手动输入')
                content = data['content']
                metadata = data.get('metadata', {})

                result = insert_document(doc_id, content, source, metadata)
                if result['success']:
                    return jsonify(result), 200
                else:
                    return jsonify(result), 400

            return jsonify({'error': '没有文件或内容'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        # 生成文档ID（限制长度不超过64字符）
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # doc_前缀(4) + 时间戳(14) + _(1) = 19字符，filename最多44字符
        truncated_name = file.filename[:44] if len(file.filename) > 44 else file.filename
        doc_id = f'doc_{timestamp}_{truncated_name}'
        source = file.filename
        metadata = {
            'filename': file.filename,
            'uploaded_by': request.username,
            'upload_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 读取文件内容
        content = ''
        filename_lower = file.filename.lower()

        if filename_lower.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore')
        elif filename_lower.endswith('.md'):
            content = file.read().decode('utf-8', errors='ignore')
        elif filename_lower.endswith('.docx'):
            # 处理docx文件
            doc = Document(file)
            for para in doc.paragraphs:
                content += para.text + '\n'
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        content += cell.text + '\t'
                    content += '\n'
        elif filename_lower.endswith('.pdf'):
            # PDF处理需要额外库，暂时返回错误提示
            return jsonify({'error': 'PDF文件支持即将添加，请暂时使用txt或docx格式'}), 400
        elif filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
            # 处理Excel文件 - 使用pandas智能处理合并单元格
            import pandas as pd
            import io
            file_bytes = file.read()
            xlsx = pd.ExcelFile(io.BytesIO(file_bytes))

            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)

                # 跳过空表
                if df.empty or len(df.columns) == 0:
                    continue

                # 智能识别表头：检查第一行是否为有效表头
                # 如果第一行大部分是"Unnamed"，说明第一行是标题，需要跳过
                unnamed_count = sum(1 for col in df.columns if 'Unnamed' in str(col) or pd.isna(col))
                if unnamed_count > len(df.columns) * 0.5:
                    # 第一行是标题，重新读取，跳过第一行作为表头
                    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=1)

                # 再次检查空表
                if df.empty:
                    continue

                # 向上填充合并单元格（关键步骤）
                df_filled = df.ffill()

                content += f'【工作表: {sheet_name}】\n'

                # 每行生成完整描述
                for idx, row in df_filled.iterrows():
                    row_desc = []
                    for col in df_filled.columns:
                        val = row[col]
                        if pd.notna(val) and str(val).strip():
                            # 处理浮点数显示（如1.0显示为1）
                            if isinstance(val, float) and val == int(val):
                                val = int(val)
                            row_desc.append(f'{col}: {val}')
                    if row_desc:
                        content += ' | '.join(row_desc) + '\n\n'

                content += '\n'
        else:
            # 尝试作为文本读取
            content = file.read().decode('utf-8', errors='ignore')

        if not content.strip():
            return jsonify({'error': '文件内容为空'}), 400

        # 插入到向量库
        result = insert_document(doc_id, content, source, metadata)

        if result['success']:
            return jsonify({
                'success': True,
                'doc_id': doc_id,
                'chunks': result['chunks'],
                'message': result['message']
            }), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        print(f"Error in knowledge_upload_document: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 批量上传进度存储
batch_upload_progress = {}

@app.route('/api/knowledge/batch-upload', methods=['POST'])
@protected
def knowledge_batch_upload():
    """批量上传知识库文档（支持zip包）- 异步处理"""
    import zipfile
    import tempfile
    import shutil
    import threading
    import uuid

    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        if not file.filename.lower().endswith('.zip'):
            return jsonify({'error': '只支持zip文件'}), 400

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()

        # 保存zip文件
        zip_path = os.path.join(temp_dir, 'upload.zip')
        file.save(zip_path)

        # 解压
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)

        # 统计文件数
        total_files = 0
        for root, dirs, files in os.walk(temp_dir):
            for filename in files:
                if filename.lower().endswith('.txt') or filename.lower().endswith('.md'):
                    total_files += 1

        # 生成任务ID
        task_id = str(uuid.uuid4())[:8]

        # 在启动线程前捕获用户名（request对象在线程中不可用）
        username = request.username

        # 初始化进度
        batch_upload_progress[task_id] = {
            'status': 'processing',
            'total': total_files,
            'processed': 0,
            'success': 0,
            'failed': 0
        }

        def process_files():
            success_count = 0
            failed_count = 0
            processed = 0

            for root, dirs, files in os.walk(temp_dir):
                for filename in files:
                    if filename.lower().endswith('.txt') or filename.lower().endswith('.md'):
                        filepath = os.path.join(root, filename)
                        processed += 1

                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            if not content.strip():
                                continue

                            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
                            name_part = os.path.splitext(filename)[0][:40]
                            doc_id = f'doc_{timestamp}_{name_part}'

                            metadata = {
                                'filename': filename,
                                'uploaded_by': username,
                                'upload_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'batch_upload': True
                            }

                            print(f"[批量上传] 处理 {processed}/{total_files}: {filename}")

                            result = insert_document(doc_id, content, filename, metadata)

                            if result['success']:
                                success_count += 1
                            else:
                                failed_count += 1

                            import time
                            time.sleep(0.2)

                        except Exception as e:
                            failed_count += 1
                            print(f"[批量上传] 处理失败: {filename}, {e}")

                        # 更新进度
                        batch_upload_progress[task_id] = {
                            'status': 'processing',
                            'total': total_files,
                            'processed': processed,
                            'success': success_count,
                            'failed': failed_count
                        }

            # 完成
            batch_upload_progress[task_id] = {
                'status': 'completed',
                'total': total_files,
                'processed': processed,
                'success': success_count,
                'failed': failed_count
            }

            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[批量上传] 任务完成: {task_id}, 成功={success_count}, 失败={failed_count}")

        # 启动后台线程
        thread = threading.Thread(target=process_files)
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': f'已开始处理 {total_files} 个文件，请稍后刷新查看结果',
            'task_id': task_id,
            'total_files': total_files
        }), 200

    except Exception as e:
        print(f"Error in knowledge_batch_upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/batch-upload/progress/<task_id>', methods=['GET'])
@protected
def get_batch_upload_progress(task_id):
    """获取批量上传进度"""
    if task_id in batch_upload_progress:
        return jsonify(batch_upload_progress[task_id]), 200
    return jsonify({'error': '任务不存在'}), 404

@app.route('/api/knowledge/search', methods=['POST'])
@protected
def knowledge_search():
    """搜索知识库"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        top_k = data.get('top_k', 5)

        if not query:
            return jsonify({'error': '请提供查询内容'}), 400

        results = search_similar(query, top_k)
        return jsonify({'results': results, 'total': len(results)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/ask', methods=['POST'])
@protected
def knowledge_ask():
    """RAG问答 - 同时搜索通用知识库和立结案标准库"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        top_k = data.get('top_k', 5)

        if not question:
            return jsonify({'error': '请提供问题'}), 400

        # 使用统一问答入口，同时搜索两个库
        try:
            from backend.kb_unified import unified_ask
            result = unified_ask(question, top_k=top_k)
        except ImportError:
            from kb_unified import unified_ask
            result = unified_ask(question, top_k=top_k)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/init', methods=['POST'])
@admin_required
def knowledge_init():
    """初始化RAG模块（管理员权限）"""
    try:
        init_rag()
        return jsonify({'message': 'RAG模块初始化完成'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== 立结案标准父子索引 API ====================
try:
    from backend.case_standards import (
        index_all_standards,
        index_standard_file,
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        clear_case_standards,
        list_indexed_standards,
        delete_single_standard,
        incremental_index,
        index_single_file_upload
    )
except ImportError:
    from case_standards import (
        index_all_standards,
        index_standard_file,
        search_case_standards,
        ask_case_standard,
        get_case_standards_stats,
        clear_case_standards,
        list_indexed_standards,
        delete_single_standard,
        incremental_index,
        index_single_file_upload
    )

@app.route('/api/case-standards/stats', methods=['GET'])
@admin_required
def case_standards_stats():
    """获取立结案标准库统计信息"""
    try:
        stats = get_case_standards_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/index', methods=['POST'])
@admin_required
def case_standards_index():
    """索引立结案标准文件目录"""
    try:
        data = request.get_json() or {}
        directory = data.get('directory', 'D:/常用/立案结案标准')

        result = index_all_standards(directory)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/clear', methods=['POST'])
@admin_required
def case_standards_clear():
    """清空立结案标准库"""
    try:
        result = clear_case_standards()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/search', methods=['POST'])
@protected
def case_standards_search():
    """搜索立结案标准"""
    try:

        data = request.get_json()
        query = data.get('query', '')
        top_k = data.get('top_k', 5)

        if not query:
            return jsonify({'error': '请提供查询内容'}), 400

        results = search_case_standards(query, top_k)
        return jsonify({'results': results, 'total': len(results)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards-debug/search', methods=['POST'])
def case_standards_debug_search():
    """调试端点：搜索立结案标准（无需认证）"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        top_k = data.get('top_k', 5)

        if not query:
            return jsonify({'error': '请提供查询内容'}), 400

        try:
            from backend.case_standards import search_case_standards
        except ImportError:
            from case_standards import search_case_standards

        results = search_case_standards(query, top_k)

        return jsonify({
            'results': results,
            'total': len(results)
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/case-standards-debug/ask', methods=['POST'])
def case_standards_debug_ask():
    """调试端点：立结案标准问答（无需认证）"""
    try:
        import os

        data = request.get_json(silent=True) or {}
        question = data.get('question', '')
        top_k = data.get('top_k', 5)
        location = data.get('location')

        if not question:
            return jsonify({'error': '请提供问题'}), 400

        # 直接导入
        try:
            from backend.case_standards import ask_case_standard
        except ImportError:
            from case_standards import ask_case_standard

        result = ask_case_standard(question, top_k, location)
        if isinstance(result, dict) and 'matches' in result:
            result.pop('matches', None)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/case-standards/ask', methods=['POST'])
@protected
def case_standards_ask():
    """立结案标准问答"""
    try:

        data = request.get_json(silent=True) or {}
        question = data.get('question', '')
        top_k = data.get('top_k', 5)
        location = data.get('location')
        history = data.get('history', None)

        if not question:
            return jsonify({'error': '请提供问题'}), 400

        result = ask_case_standard(question, top_k, location, history)
        if isinstance(result, dict) and 'matches' in result:
            result.pop('matches', None)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

# ==================== 立结案标准索引管理 API ====================

@app.route('/api/case-standards/list', methods=['GET'])
@admin_required
def case_standards_list():
    """获取已索引的标准列表"""
    try:

        standards = list_indexed_standards()
        return jsonify({
            'standards': standards,
            'total': len(standards)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/delete/<parent_id>', methods=['DELETE'])
@admin_required
def case_standards_delete_single(parent_id):
    """删除单个已索引的标准"""
    try:

        result = delete_single_standard(parent_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/incremental', methods=['POST'])
@admin_required
def case_standards_incremental_index():
    """增量索引立结案标准"""
    try:

        data = request.get_json() or {}
        directory = data.get('directory', 'D:/常用/立案结案标准')

        result = incremental_index(directory)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/case-standards/index-single', methods=['POST'])
@admin_required
def case_standards_index_single():
    """上传并索引单个标准文件"""
    try:

        # 检查是否有文件上传
        if 'file' not in request.files:
            # 也支持通过JSON内容上传
            data = request.get_json()
            if data and 'content' in data and 'filename' in data:
                result = index_single_file_upload(data['content'], data['filename'])
                return jsonify(result), 200
            return jsonify({'error': '请上传文件或提供文件内容'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400

        if not file.filename.endswith('.txt'):
            return jsonify({'error': '只支持.txt文件'}), 400

        # 读取文件内容
        content = file.read().decode('utf-8')
        filename = file.filename

        result = index_single_file_upload(content, filename)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== 统一知识库 API ====================

try:
    from backend.kb_unified import (
        unified_ask,
        unified_search,
        get_unified_stats,
        migrate_general_to_unified,
        get_migration_status,
    )
except Exception:
    try:
        from kb_unified import (
            unified_ask,
            unified_search,
            get_unified_stats,
            migrate_general_to_unified,
            get_migration_status,
        )
    except Exception:
        print("[WARNING] kb_unified 模块加载失败，统一知识库功能不可用")
        unified_ask = None
        unified_search = None
        get_unified_stats = None
        migrate_general_to_unified = None
        get_migration_status = None

@app.route('/api/kb/ask', methods=['POST'])
@protected
def kb_unified_ask():
    """统一知识库问答"""
    try:
        data = request.get_json(silent=True) or {}
        question = data.get('question', '')
        location = data.get('location')
        history = data.get('history', [])
        top_k = data.get('top_k', 5)

        if not question:
            return jsonify({'error': '请提供问题'}), 400

        result = unified_ask(question, location, history, top_k)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/kb/search', methods=['POST'])
@protected
def kb_unified_search():
    """统一知识库检索"""
    try:
        data = request.get_json(silent=True) or {}
        query = data.get('query', '')
        top_k = data.get('top_k', 10)

        if not query:
            return jsonify({'error': '请提供搜索内容'}), 400

        results = unified_search(query, top_k)
        return jsonify({'results': results, 'total': len(results)}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/kb/stats', methods=['GET'])
@protected
def kb_unified_stats():
    """获取统一知识库统计信息"""
    try:
        stats = get_unified_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/kb/migrate', methods=['POST'])
@admin_required
def kb_unified_migrate():
    """迁移通用知识库到统一库"""
    try:
        result = migrate_general_to_unified()
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/kb/migration-status', methods=['GET'])
@admin_required
def kb_migration_status():
    """获取迁移状态"""
    try:
        status = get_migration_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smart-report', methods=['POST'])
@protected
def smart_report():
    """智能报告生成API"""
    try:
        import re

        data = request.json
        table_name = data.get('table_name')
        template_type = data.get('template_type')  # monthly_comparison, yearly_summary, special_analysis, full_analysis
        months = data.get('months', [])  # 月度对比：选中的月份列表
        year = data.get('year', '')  # 年度总结：选中的年份
        dimension = data.get('dimension', '')  # 专项分析：分析维度字段
        dimension_values = data.get('dimension_values', [])  # 专项分析：选中的值列表

        if not table_name or not template_type:
            return jsonify({'error': 'Missing required parameters'}), 400

        print(f"[智能报告] 开始生成报告, 表: {table_name}, 模板: {template_type}")

        # 从数据库读取数据
        df = pd.read_sql_table(table_name, engine)
        original_count = len(df)

        # 根据模板类型筛选数据
        filter_desc = ""
        if template_type == 'monthly_comparison' and months:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col].isin(months)]
                filter_desc = f"筛选月份: {', '.join(months)}"

        elif template_type == 'yearly_summary' and year:
            # 从时间字段提取年份
            time_col = None
            for col in ['上报时间', '捆绑处置截止时间', 'created_time']:
                if col in df.columns:
                    time_col = col
                    break
            if time_col:
                df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                df = df[df[time_col].dt.year == int(year)]
                filter_desc = f"筛选年份: {year}年"

        elif template_type == 'special_analysis' and dimension and dimension_values:
            if dimension in df.columns:
                df = df[df[dimension].isin(dimension_values)]
                filter_desc = f"筛选{dimension}: {', '.join(dimension_values)}"

        filtered_count = len(df)
        print(f"[智能报告] 数据筛选: {original_count} -> {filtered_count} 条")

        if filtered_count == 0:
            return jsonify({'error': '筛选后无数据，请调整筛选条件'}), 400

        # ===== 生成图表 =====
        charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)

        # ===== 调用LLM生成分析洞察 =====
        insights = generate_report_insights(df, template_type, months, year, dimension, dimension_values)

        # ===== 生成HTML报告 =====
        html_report = render_smart_report_html(
            df=df,
            template_type=template_type,
            months=months,
            year=year,
            dimension=dimension,
            dimension_values=dimension_values,
            charts_base64=charts_base64,
            insights=insights,
            filter_desc=filter_desc,
            original_count=original_count,
            filtered_count=filtered_count
        )

        print(f"[智能报告] 报告生成完成")
        return jsonify({'html': html_report}), 200

    except Exception as e:
        print(f"Error in smart_report: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500


@app.route('/api/video-test', methods=['GET'])
def video_test():
    """视频生成测试端点 - 不需要认证"""
    try:
        print("[视频测试] 开始测试...")

        from video_report import VideoReportGenerator
        from flask import send_file
        import tempfile

        # 创建测试视频
        generator = VideoReportGenerator()
        output_path = tempfile.mktemp(suffix='.mp4')

        # 模拟图表数据
        charts_data = []
        try:
            # 生成简单的测试图表
            import matplotlib.pyplot as plt
            import io
            import base64

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(['A', 'B', 'C'], [100, 150, 80])
            ax.set_title('测试图表')
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            charts_data.append(('测试图表', img_b64))
            plt.close(fig)
        except Exception as e:
            print(f"[视频测试] 图表生成失败: {e}")

        print("[视频测试] 生成视频...")
        video_path = generator.generate_video(
            report_title="测试报告",
            charts_data=charts_data,
            insights={'summary': '这是一个测试视频报告', 'key_findings': ['发现一：测试数据正常', '发现二：视频生成成功']},
            output_path=output_path
        )

        print(f"[视频测试] 视频生成完成: {video_path}")

        if video_path and os.path.exists(video_path):
            # 返回视频文件
            response = send_file(
                video_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name='test_report.mp4'
            )

            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                except:
                    pass

            return response
        else:
            return jsonify({'success': False, 'error': '视频生成失败'})

    except Exception as e:
        print(f"[视频测试] 错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/video-debug', methods=['GET'])
def video_debug():
    """视频报告调试端点 - 模拟完整流程，不需要认证"""
    try:
        print("[视频调试] 开始调试...")
        from video_report import VideoReportGenerator
        from flask import send_file
        import tempfile

        # 模拟真实请求参数
        table_name = 'cases'
        template_type = 'monthly_comparison'
        months = ['202603', '202602']

        print(f"[视频调试] 参数: table={table_name}, template={template_type}")
        report_title = f"{months[0]}与{months[1]}对比分析报告"

        # 测试数据库读取
        try:
            df = pd.read_sql_table(table_name, engine)
            print(f"[视频调试] 数据库读取成功: {len(df)} 条记录")
            print(f"[视频调试] 列名: {list(df.columns)}")
        except Exception as e:
            print(f"[视频调试] 数据库读取失败: {e}")
            import traceback
            traceback.print_exc()
            # 使用模拟数据继续测试
            df = pd.DataFrame({
                '大类名称': ['市容环境', '市容环境', '市政设施'],
                '所属片区': ['片区A', '片区B', '片区A'],
                '当前阶段名称': ['[办结]', '[办结]', '处置中']
            })
            print(f"[视频调试] 使用模拟数据: {len(df)} 条")

        # 测试图表生成
        try:
            charts_base64 = generate_smart_report_charts(df, template_type, months, '', [])
            print(f"[视频调试] 图表生成成功: {len(charts_base64)} 个")
        except Exception as e:
            print(f"[视频调试] 图表生成失败: {e}")
            import traceback
            traceback.print_exc()
            charts_base64 = []

        # 测试洞察生成
        # 计算结案率
        if '当前阶段名称' in df.columns:
            completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
        else:
            completion_rate = 0

        insights = {
            'summary': f'共分析{len(df)}条数据',
            'key_findings': [],
            'chart_insights': {}
        }
        if '大类名称' in df.columns:
            top = df['大类名称'].value_counts().head(1)
            if len(top) > 0:
                insights['key_findings'].append(f"主要问题: {top.index[0]}")

        # 为每个图表生成分析结论
        for chart_name, _ in charts_base64:
            if '综合仪表盘' in chart_name:
                insight = f"综合仪表盘展示了整体数据概况。共{len(df)}条数据，结案率{completion_rate:.1f}%。"
            elif '案件总量对比' in chart_name:
                insight = f"案件总量对比图表展示了两个月的数据对比情况。"
            elif '问题类型' in chart_name:
                if '大类名称' in df.columns and len(df['大类名称'].value_counts()) > 0:
                    top = df['大类名称'].value_counts().head(3)
                    insight = f"问题类型分布显示，{top.index[0]}占比最高，共{top.values[0]}件。"
                else:
                    insight = f"问题类型分布图表展示了各类问题的占比情况。"
            elif 'TOP10小类' in chart_name:
                if '小类名称' in df.columns and len(df['小类名称'].value_counts()) > 0:
                    top5 = df['小类名称'].value_counts().head(3)
                    insight = f"排名前五的小类问题分别是：{top5.index[0]}、{top5.index[1] if len(top5)>1 else ''}等。"
                else:
                    insight = f"排名图表展示了高频小类问题的分布情况。"
            elif '片区案件' in chart_name:
                if '所属片区' in df.columns and len(df['所属片区'].value_counts()) > 0:
                    top = df['所属片区'].value_counts().head(3)
                    insight = f"片区案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件。"
                else:
                    insight = f"片区案件分布图表展示了各区域的案件分布情况。"
            elif '问题来源' in chart_name:
                if '问题来源' in df.columns and len(df['问题来源'].value_counts()) > 0:
                    top = df['问题来源'].value_counts().head(3)
                    insight = f"问题来源分布显示，主要来源为{top.index[0]}。"
                else:
                    insight = f"问题来源分布图表展示了案件的来源渠道。"
            elif '街道案件' in chart_name:
                if '所属街道' in df.columns and len(df['所属街道'].value_counts()) > 0:
                    top = df['所属街道'].value_counts().head(3)
                    insight = f"街道案件分布显示，{top.index[0]}案件最多。"
                else:
                    insight = f"街道案件分布图表展示了各街道的案件分布情况。"
            elif '处置部门' in chart_name:
                if '处置部门' in df.columns and len(df['处置部门'].value_counts()) > 0:
                    top = df['处置部门'].value_counts().head(3)
                    insight = f"处置部门排名显示，{top.index[0]}处理案件最多。"
                else:
                    insight = f"处置部门排名图表展示了各部门的工作量。"
            elif '案件状态' in chart_name:
                insight = f"案件状态分布显示，已办结{(df['当前阶段名称'] == '[办结]').sum() if '当前阶段名称' in df.columns else 0}件。"
            else:
                insight = f"该图表展示了数据分析结果。"
            insights['chart_insights'][chart_name] = insight
            print(f"[视频调试] 图表分析 {chart_name}: {insight[:40]}...")

        print(f"[视频调试] 洞察生成完成")

        # 测试视频生成
        print("[视频调试] 开始生成视频...")
        generator = VideoReportGenerator()
        output_path = tempfile.mktemp(suffix='.mp4')

        video_path = generator.generate_video(
            report_title=report_title,
            charts_data=charts_base64,
            insights=insights,
            output_path=output_path
        )

        print(f"[视频调试] 视频完成: {video_path}, 大小: {os.path.getsize(video_path) if video_path else 0}")

        if video_path and os.path.exists(video_path):
            response = send_file(
                video_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name='debug_report.mp4'
            )
            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(video_path):
                        os.remove(video_path)
                except:
                    pass
            return response
        else:
            return jsonify({'error': '视频生成失败'}), 500

    except Exception as e:
        print(f"[视频调试] 总错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/video-report', methods=['POST'])
@protected
def video_report():
    """
    视频报告生成API
    将智能报告转化为视频报告
    """
    try:
        from video_report import VideoReportGenerator
        from flask import send_file
        import tempfile

        data = request.json
        table_name = data.get('table_name')
        template_type = data.get('template_type')
        months = data.get('months', [])
        year = data.get('year', '')
        dimension = data.get('dimension', '')
        dimension_values = data.get('dimension_values', [])

        print(f"[视频报告] 请求参数: table={table_name}, template={template_type}, months={months}")

        if not table_name or not template_type:
            return jsonify({'error': 'Missing required parameters'}), 400

        print(f"[视频报告] 开始生成视频, 表: {table_name}, 模板: {template_type}")

        # 从数据库读取数据
        try:
            df = pd.read_sql_table(table_name, engine)
            original_count = len(df)
            print(f"[视频报告] 读取数据: {original_count} 条")
        except Exception as e:
            print(f"[视频报告] 数据库读取失败: {e}")
            return jsonify({'error': f'数据库读取失败: {str(e)}'}), 500

        # 根据模板类型筛选数据
        filter_desc = ""
        if template_type == 'monthly_comparison' and months:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break
            if month_col:
                df = df[df[month_col].isin(months)]
                filter_desc = f"筛选月份: {', '.join(months)}"

        elif template_type == 'yearly_summary' and year:
            time_col = None
            for col in ['上报时间', '捆绑处置截止时间', 'created_time']:
                if col in df.columns:
                    time_col = col
                    break
            if time_col:
                df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                df = df[df[time_col].dt.year == int(year)]
                filter_desc = f"筛选年份: {year}年"

        elif template_type == 'special_analysis' and dimension and dimension_values:
            if dimension in df.columns:
                df = df[df[dimension].isin(dimension_values)]
                filter_desc = f"筛选{dimension}: {', '.join(dimension_values)}"

        filtered_count = len(df)
        print(f"[视频报告] 数据筛选: {original_count} -> {filtered_count} 条")

        if filtered_count == 0:
            return jsonify({'error': '筛选后无数据，请调整筛选条件'}), 400

        # 生成图表（带错误处理）
        try:
            charts_base64 = generate_smart_report_charts(df, template_type, months, dimension, dimension_values)
            print(f"[视频报告] 图表生成完成: {len(charts_base64)} 个")
        except Exception as e:
            print(f"[视频报告] 图表生成失败: {e}")
            charts_base64 = []

        # 生成洞察（带错误处理，简化）
        try:
            # 简化洞察生成，不调用LLM
            insights = {
                'summary': f'共分析{filtered_count}条数据' + (f'，{filter_desc}' if filter_desc else ''),
                'key_findings': [],
                'chart_insights': {}  # 图表分析结论
            }

            # 添加基本统计发现
            if '大类名称' in df.columns:
                top_type = df['大类名称'].value_counts().head(1)
                if len(top_type) > 0:
                    insights['key_findings'].append(f"主要问题类型: {top_type.index[0]}, 共{top_type.values[0]}件")

            if '所属片区' in df.columns:
                top_district = df['所属片区'].value_counts().head(1)
                if len(top_district) > 0:
                    insights['key_findings'].append(f"案件集中区域: {top_district.index[0]}, 共{top_district.values[0]}件")

            # 计算结案率
            if '当前阶段名称' in df.columns:
                completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
            else:
                completion_rate = 0

            # 判断是否月度对比模式
            is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2

            # 为每个图表生成分析结论
            for chart_name, _ in charts_base64:
                chart_display = chart_name
                if len(chart_name) > 3 and chart_name[2] == '_':
                    chart_display = chart_name[3:]

                # 根据图表名称精确匹配
                if '综合仪表盘' in chart_name:
                    insight = f"综合仪表盘展示了整体数据概况。共{filtered_count}条数据，结案率{completion_rate:.1f}%。"
                elif '案件总量对比' in chart_name:
                    if is_monthly_comparison and months:
                        insight = f"案件总量对比图表展示了两个月的数据对比情况。左侧为{months[0]}，右侧为{months[1]}。"
                    else:
                        insight = f"案件总量图表展示了数据的基本情况。"
                elif '问题类型对比' in chart_name or '问题类型分布' in chart_name:
                    if '大类名称' in df.columns and len(df['大类名称'].value_counts()) > 0:
                        top = df['大类名称'].value_counts().head(3)
                        insight = f"问题类型分布显示，{top.index[0]}占比最高，共{top.values[0]}件。"
                    else:
                        insight = f"问题类型分布图表展示了各类问题的占比情况。"
                elif 'TOP10小类' in chart_name:
                    if '小类名称' in df.columns and len(df['小类名称'].value_counts()) > 0:
                        top5 = df['小类名称'].value_counts().head(5)
                        insight = f"排名前五的小类问题分别是：{top5.index[0]}、{top5.index[1] if len(top5)>1 else ''}、{top5.index[2] if len(top5)>2 else ''}。"
                    else:
                        insight = f"排名图表展示了高频小类问题的分布情况。"
                elif '片区案件' in chart_name:
                    if '所属片区' in df.columns and len(df['所属片区'].value_counts()) > 0:
                        top = df['所属片区'].value_counts().head(3)
                        insight = f"片区案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件，其次是{top.index[1] if len(top)>1 else '其他'}。"
                    else:
                        insight = f"片区案件分布图表展示了各区域的案件分布情况。"
                elif '问题来源' in chart_name:
                    if '问题来源' in df.columns and len(df['问题来源'].value_counts()) > 0:
                        top = df['问题来源'].value_counts().head(3)
                        insight = f"问题来源分布显示，主要来源为{top.index[0]}，占比{top.values[0]/filtered_count*100:.1f}%。"
                    else:
                        insight = f"问题来源分布图表展示了案件的来源渠道。"
                elif '街道案件' in chart_name:
                    if '所属街道' in df.columns and len(df['所属街道'].value_counts()) > 0:
                        top = df['所属街道'].value_counts().head(3)
                        insight = f"街道案件分布显示，{top.index[0]}案件最多，共{top.values[0]}件。"
                    else:
                        insight = f"街道案件分布图表展示了各街道的案件分布情况。"
                elif '处置部门' in chart_name:
                    if '处置部门' in df.columns and len(df['处置部门'].value_counts()) > 0:
                        top = df['处置部门'].value_counts().head(3)
                        insight = f"处置部门排名显示，{top.index[0]}处理案件最多，共{top.values[0]}件。"
                    else:
                        insight = f"处置部门排名图表展示了各部门的工作量。"
                elif '案件状态' in chart_name:
                    if '当前阶段名称' in df.columns:
                        done_count = (df['当前阶段名称'] == '[办结]').sum()
                        insight = f"案件状态分布显示，已办结{done_count}件，结案率{completion_rate:.1f}%。"
                    else:
                        insight = f"案件状态分布图表展示了案件的处理进度。"
                else:
                    insight = f"该图表展示了{chart_display}的分析结果。"

                insights['chart_insights'][chart_name] = insight

            print(f"[视频报告] 洞察生成完成，含{len(insights['chart_insights'])}个图表结论")
        except Exception as e:
            print(f"[视频报告] 洞察生成失败: {e}")
            insights = {'summary': f'数据分析报告，共{filtered_count}条数据', 'key_findings': []}

        # 构建报告标题（简洁的副标题格式）
        if template_type == 'monthly_comparison' and months:
            report_title = f"{months[0]}与{months[1]}对比分析报告"
        elif template_type == 'yearly_summary' and year:
            report_title = f"{year}年度数据分析报告"
        elif template_type == 'special_analysis' and dimension:
            report_title = f"{dimension}专项分析报告"
        elif template_type == 'full_analysis':
            report_title = "全量数据分析报告"
        else:
            report_title = "数据分析报告"

        # 生成视频
        print("[视频报告] 开始生成视频文件...")
        generator = VideoReportGenerator()

        # 设置输出路径
        output_path = tempfile.mktemp(suffix='.mp4')

        try:
            video_path = generator.generate_video(
                report_title=report_title,
                charts_data=charts_base64,
                insights=insights,
                output_path=output_path
            )
        except Exception as e:
            print(f"[视频报告] 视频生成失败: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'视频生成失败: {str(e)}'}), 500

        if not video_path or not os.path.exists(video_path):
            return jsonify({'error': '视频生成失败'}), 500

        print(f"[视频报告] 视频生成完成: {video_path}, 大小: {os.path.getsize(video_path)} bytes")

        # 返回视频文件
        response = send_file(
            video_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f'{report_title}.mp4'
        )

        # 请求结束后删除临时文件
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except:
                pass

        return response

    except Exception as e:
        print(f"Error in video_report: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500


def generate_smart_report_charts(df, template_type, months, dimension, dimension_values):
    """生成精美图表，返回base64编码列表"""
    charts = []

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']
    plt.rcParams['axes.unicode_minus'] = False

    # 列名映射（英文 -> 中文）
    column_mapping = {
        'major_category': '大类名称',
        'minor_category': '小类名称',
        'area': '所属片区',
        'source': '问题来源',
        'street': '所属街道',
        'owner_unit': '处置部门',
        'status': '当前阶段名称',
        'report_time': '上报时间',
        'responsible_area_name': '责任区域',
        'community': '所属社区'
    }
    # 重命名列（如果存在）
    df = df.rename(columns=column_mapping)

    # 配色方案
    colors_palette = ['#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
    color_m1 = '#4ECDC4'  # 第一个月颜色
    color_m2 = '#FF6B6B'  # 第二个月颜色

    # 获取月份列
    month_col = None
    for col in ['月份', 'data_month']:
        if col in df.columns:
            month_col = col
            break

    # 是否是月度对比模式
    is_monthly_comparison = template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col

    try:
        # ===== 综合仪表盘（总体情况，无对比） =====
        # 创建一个综合仪表盘图表，展示总体数据情况
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('案件数据分析综合仪表盘', fontsize=22, fontweight='bold', y=0.98)

        # 创建子图网格
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.25)

        # 子图1：案件总量（数字展示）
        ax1 = fig.add_subplot(gs[0, 0])
        total_count = len(df)
        ax1.text(0.5, 0.6, f'{total_count:,}', ha='center', va='center', fontsize=36, fontweight='bold', color='#667eea')
        ax1.text(0.5, 0.3, '案件总量', ha='center', va='center', fontsize=16, color='#666')
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.axis('off')
        ax1.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#667eea', linewidth=2, transform=ax1.transAxes))

        # 子图2：结案率
        ax2 = fig.add_subplot(gs[0, 1])
        if '当前阶段名称' in df.columns:
            completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
        else:
            completion_rate = 0
        ax2.text(0.5, 0.6, f'{completion_rate:.1f}%', ha='center', va='center', fontsize=36, fontweight='bold',
                 color='#27ae60' if completion_rate > 95 else '#f39c12')
        ax2.text(0.5, 0.3, '结案率', ha='center', va='center', fontsize=16, color='#666')
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.axis('off')
        ax2.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#27ae60', linewidth=2, transform=ax2.transAxes))

        # 子图3：问题类型数
        ax3 = fig.add_subplot(gs[0, 2])
        type_count = len(df['大类名称'].unique()) if '大类名称' in df.columns else 0
        ax3.text(0.5, 0.6, f'{type_count}', ha='center', va='center', fontsize=36, fontweight='bold', color='#FF6B6B')
        ax3.text(0.5, 0.3, '问题类型', ha='center', va='center', fontsize=16, color='#666')
        ax3.set_xlim(0, 1)
        ax3.set_ylim(0, 1)
        ax3.axis('off')
        ax3.add_patch(plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False, edgecolor='#FF6B6B', linewidth=2, transform=ax3.transAxes))

        # 子图4：问题类型分布饼图
        ax4 = fig.add_subplot(gs[1, 0:2])
        if '大类名称' in df.columns:
            type_counts = df['大类名称'].value_counts().head(6)
            colors_pie = colors_palette[:len(type_counts)]
            wedges, texts, autotexts = ax4.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                               colors=colors_pie, startangle=90, textprops={'fontsize': 11})
            ax4.set_title('问题类型分布', fontsize=14, fontweight='bold', pad=10)

        # 子图5：片区分布条形图
        ax5 = fig.add_subplot(gs[1, 2])
        if '所属片区' in df.columns:
            district_counts = df['所属片区'].value_counts().head(5)
            bars = ax5.barh(range(len(district_counts)), district_counts.values[::-1],
                           color=colors_palette[:len(district_counts)])
            ax5.set_yticks(range(len(district_counts)))
            ax5.set_yticklabels(district_counts.index[::-1], fontsize=11)
            ax5.set_xlabel('案件数', fontsize=11)
            ax5.set_title('片区分布', fontsize=14, fontweight='bold', pad=10)

        # 子图6：TOP5小类问题
        ax6 = fig.add_subplot(gs[2, 0:2])
        if '小类名称' in df.columns:
            top5 = df['小类名称'].value_counts().head(5)
            colors_bar = plt.cm.Blues(np.linspace(0.4, 0.9, len(top5)))[::-1]
            bars = ax6.barh(range(len(top5)), top5.values[::-1], color=colors_bar)
            ax6.set_yticks(range(len(top5)))
            ax6.set_yticklabels(top5.index[::-1], fontsize=11)
            ax6.set_xlabel('案件数', fontsize=11)
            ax6.set_title('TOP5小类问题', fontsize=14, fontweight='bold', pad=10)
            for i, (bar, val) in enumerate(zip(bars, top5.values[::-1])):
                ax6.text(bar.get_width() + max(top5.values)*0.02, bar.get_y() + bar.get_height()/2,
                        f'{int(val)}', ha='left', va='center', fontsize=10)

        # 子图7：问题来源分布
        ax7 = fig.add_subplot(gs[2, 2])
        if '问题来源' in df.columns:
            source_counts = df['问题来源'].value_counts().head(4)
            colors_src = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'][:len(source_counts)]
            wedges, texts, autotexts = ax7.pie(source_counts.values, labels=source_counts.index, autopct='%1.1f%%',
                                               colors=colors_src, startangle=90, textprops={'fontsize': 9})
            ax7.set_title('问题来源', fontsize=14, fontweight='bold', pad=10)

        charts.append(('00_综合仪表盘', fig_to_base64(fig)))
        plt.close(fig)

        # ===== 图1: 案件总量对比 =====
        if months and month_col:
            fig, ax = plt.subplots(figsize=(10, 8))

            month_counts = df[month_col].value_counts().reindex(months)
            x = np.arange(len(months))
            bars = ax.bar(x, month_counts.values, color=[color_m1, color_m2][:len(months)], width=0.5, edgecolor='white', linewidth=2)
            ax.set_title('案件总量对比', fontsize=20, fontweight='bold', pad=20)
            ax.set_ylabel('案件数量', fontsize=14)
            ax.set_xticks(x)
            ax.set_xticklabels(months, fontsize=14)
            ax.tick_params(axis='y', labelsize=12)

            for bar, val in zip(bars, month_counts.values):
                if pd.notna(val):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(month_counts.values)*0.02,
                            f'{int(val):,}', ha='center', va='bottom', fontsize=16, fontweight='bold')

            # 添加环比变化
            if len(months) == 2 and month_counts.values[0] > 0:
                change = month_counts.values[1] - month_counts.values[0]
                change_pct = change / month_counts.values[0] * 100
                color = '#e74c3c' if change > 0 else '#27ae60'
                ax.text(0.5, 0.95, f'环比变化: {change:+,} ({change_pct:+.1f}%)',
                        transform=ax.transAxes, ha='center', fontsize=14, color=color, fontweight='bold')

            plt.tight_layout()
            charts.append(('01_案件总量对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图2: 问题类型对比 =====
        if '大类名称' in df.columns:
            if is_monthly_comparison:
                # 月度对比模式：分组柱状图
                fig, ax = plt.subplots(figsize=(14, 8))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                type_counts1 = df1['大类名称'].value_counts()
                type_counts2 = df2['大类名称'].value_counts()

                # 合并所有类型
                all_types = list(set(type_counts1.index) | set(type_counts2.index))
                all_types.sort(key=lambda x: type_counts2.get(x, 0) + type_counts1.get(x, 0), reverse=True)

                x = np.arange(len(all_types))
                width = 0.35

                vals1 = [type_counts1.get(t, 0) for t in all_types]
                vals2 = [type_counts2.get(t, 0) for t in all_types]

                bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_xticks(x)
                ax.set_xticklabels(all_types, rotation=45, ha='right', fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('各类型案件数量对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                # 非对比模式：饼图
                fig, ax = plt.subplots(figsize=(10, 8))
                type_counts = df['大类名称'].value_counts()
                colors = colors_palette[:len(type_counts)]
                wedges, texts, autotexts = ax.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
                                                   colors=colors, startangle=90, textprops={'fontsize': 10})
                ax.set_title('问题类型分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('02_问题类型对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图3: TOP10小类问题对比 =====
        if '小类名称' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(14, 8))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                # 获取两个月份完整的统计，不只是TOP10
                all_counts1 = df1['小类名称'].value_counts()
                all_counts2 = df2['小类名称'].value_counts()

                # 取两个月份TOP10的并集
                top10_1_names = set(all_counts1.head(10).index)
                top10_2_names = set(all_counts2.head(10).index)
                all_items = list(top10_1_names | top10_2_names)
                all_items.sort(key=lambda x: all_counts2.get(x, 0) + all_counts1.get(x, 0), reverse=True)
                all_items = all_items[:10]  # 取TOP10

                y = np.arange(len(all_items))
                width = 0.35

                # 使用完整统计数据获取值
                vals1 = [all_counts1.get(t, 0) for t in all_items]
                vals2 = [all_counts2.get(t, 0) for t in all_items]

                bars1 = ax.barh(y - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.barh(y + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_yticks(y)
                ax.set_yticklabels(all_items, fontsize=10)
                ax.set_xlabel('案件数量', fontsize=12)
                ax.set_title('TOP10小类问题对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(12, 6))
                top10 = df['小类名称'].value_counts().head(10)
                colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(top10)))[::-1]
                bars = ax.barh(range(len(top10)), top10.values[::-1], color=colors)
                ax.set_yticks(range(len(top10)))
                ax.set_yticklabels(top10.index[::-1], fontsize=10)
                ax.set_xlabel('案件数量', fontsize=12)
                ax.set_title('TOP10小类问题', fontsize=16, fontweight='bold', pad=15)
            charts.append(('03_TOP10小类问题对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图4: 片区案件对比 =====
        if '所属片区' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(12, 6))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                district_counts1 = df1['所属片区'].value_counts()
                district_counts2 = df2['所属片区'].value_counts()

                all_districts = list(set(district_counts1.index) | set(district_counts2.index))
                all_districts.sort(key=lambda x: district_counts2.get(x, 0) + district_counts1.get(x, 0), reverse=True)

                x = np.arange(len(all_districts))
                width = 0.35

                vals1 = [district_counts1.get(d, 0) for d in all_districts]
                vals2 = [district_counts2.get(d, 0) for d in all_districts]

                bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_xticks(x)
                ax.set_xticklabels(all_districts, fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('各片区案件对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(10, 6))
                district_counts = df['所属片区'].value_counts()
                colors = colors_palette[:len(district_counts)]
                bars = ax.bar(district_counts.index, district_counts.values, color=colors, edgecolor='white')
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('各片区案件分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('04_片区案件对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图5: 问题来源对比 =====
        if '问题来源' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(12, 6))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                source_counts1 = df1['问题来源'].value_counts()
                source_counts2 = df2['问题来源'].value_counts()

                all_sources = list(set(source_counts1.index) | set(source_counts2.index))
                all_sources.sort(key=lambda x: source_counts2.get(x, 0) + source_counts1.get(x, 0), reverse=True)

                x = np.arange(len(all_sources))
                width = 0.35

                vals1 = [source_counts1.get(s, 0) for s in all_sources]
                vals2 = [source_counts2.get(s, 0) for s in all_sources]

                bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_xticks(x)
                ax.set_xticklabels(all_sources, rotation=45, ha='right', fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('问题来源对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(10, 6))
                source_counts = df['问题来源'].value_counts()
                colors = colors_palette[:len(source_counts)]
                wedges, texts, autotexts = ax.pie(source_counts.values, labels=source_counts.index, autopct='%1.1f%%',
                                                   colors=colors, startangle=90, textprops={'fontsize': 10})
                ax.set_title('问题来源分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('05_问题来源对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图6: 街道案件对比 =====
        if '所属街道' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(14, 6))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                street_counts1 = df1['所属街道'].value_counts()
                street_counts2 = df2['所属街道'].value_counts()

                all_streets = list(set(street_counts1.index) | set(street_counts2.index))
                all_streets.sort(key=lambda x: street_counts2.get(x, 0) + street_counts1.get(x, 0), reverse=True)

                x = np.arange(len(all_streets))
                width = 0.35

                vals1 = [street_counts1.get(s, 0) for s in all_streets]
                vals2 = [street_counts2.get(s, 0) for s in all_streets]

                bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_xticks(x)
                ax.set_xticklabels(all_streets, rotation=45, ha='right', fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('各街道案件对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(12, 6))
                street_counts = df['所属街道'].value_counts()
                colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(street_counts)))[::-1]
                bars = ax.bar(range(len(street_counts)), street_counts.values, color=colors)
                ax.set_xticks(range(len(street_counts)))
                ax.set_xticklabels(street_counts.index, rotation=45, ha='right', fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('各街道案件分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('06_街道案件对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图7: 处置部门TOP10对比 =====
        if '处置部门' in df.columns:
            if is_monthly_comparison:
                # 月度对比模式：分组柱状图
                fig, ax = plt.subplots(figsize=(14, 8))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                # 获取完整统计，不只是TOP10
                all_dept_counts1 = df1['处置部门'].value_counts()
                all_dept_counts2 = df2['处置部门'].value_counts()

                # 取两个月份TOP10的并集
                top10_1_names = set(all_dept_counts1.head(10).index)
                top10_2_names = set(all_dept_counts2.head(10).index)
                all_depts = list(top10_1_names | top10_2_names)
                all_depts.sort(key=lambda x: all_dept_counts2.get(x, 0) + all_dept_counts1.get(x, 0), reverse=True)
                all_depts = all_depts[:10]  # 取TOP10

                y = np.arange(len(all_depts))
                width = 0.35

                # 使用完整统计数据获取值
                vals1 = [all_dept_counts1.get(d, 0) for d in all_depts]
                vals2 = [all_dept_counts2.get(d, 0) for d in all_depts]

                bars1 = ax.barh(y - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.barh(y + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_yticks(y)
                ax.set_yticklabels(all_depts, fontsize=10)
                ax.set_xlabel('案件数量', fontsize=12)
                ax.set_title('处置部门TOP10对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                # 非对比模式：普通条形图
                fig, ax = plt.subplots(figsize=(12, 6))
                dept_counts = df['处置部门'].value_counts().head(10)
                colors = plt.cm.Greens(np.linspace(0.4, 0.9, len(dept_counts)))[::-1]
                bars = ax.barh(range(len(dept_counts)), dept_counts.values[::-1], color=colors)
                ax.set_yticks(range(len(dept_counts)))
                ax.set_yticklabels(dept_counts.index[::-1], fontsize=10)
                ax.set_xlabel('案件数量', fontsize=12)
                ax.set_title('处置部门TOP10', fontsize=16, fontweight='bold', pad=15)
            charts.append(('07_处置部门TOP10对比', fig_to_base64(fig)))
            plt.close(fig)

        # ===== 图8: 案件状态对比 =====
        if '当前阶段名称' in df.columns:
            if is_monthly_comparison:
                fig, ax = plt.subplots(figsize=(10, 6))

                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                status_counts1 = df1['当前阶段名称'].value_counts()
                status_counts2 = df2['当前阶段名称'].value_counts()

                all_status = list(set(status_counts1.index) | set(status_counts2.index))

                x = np.arange(len(all_status))
                width = 0.35

                vals1 = [status_counts1.get(s, 0) for s in all_status]
                vals2 = [status_counts2.get(s, 0) for s in all_status]

                bars1 = ax.bar(x - width/2, vals1, width, label=months[0], color=color_m1, edgecolor='white')
                bars2 = ax.bar(x + width/2, vals2, width, label=months[1], color=color_m2, edgecolor='white')

                ax.set_xticks(x)
                ax.set_xticklabels(all_status, fontsize=10)
                ax.set_ylabel('案件数量', fontsize=12)
                ax.set_title('案件状态对比', fontsize=16, fontweight='bold', pad=15)
                ax.legend(fontsize=12)

                plt.tight_layout()
            else:
                fig, ax = plt.subplots(figsize=(8, 6))
                status_counts = df['当前阶段名称'].value_counts()
                colors = ['#27ae60', '#f39c12', '#e74c3c'][:len(status_counts)]
                wedges, texts, autotexts = ax.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%',
                                                   colors=colors, startangle=90, textprops={'fontsize': 11})
                ax.set_title('案件状态分布', fontsize=16, fontweight='bold', pad=15)
            charts.append(('08_案件状态对比', fig_to_base64(fig)))
            plt.close(fig)

    except Exception as e:
        print(f"[智能报告] 图表生成失败: {e}")
        import traceback
        traceback.print_exc()

    return charts


def fig_to_base64(fig):
    """将matplotlib图表转换为base64字符串"""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def generate_report_insights(df, template_type, months, year, dimension, dimension_values):
    """调用LLM生成分析洞察"""
    try:
        # 准备数据摘要
        data_summary = f"""
数据总量: {len(df)}
字段数量: {len(df.columns)}
主要字段:
"""

        # 月度对比时，添加详细的对比数据
        if template_type == 'monthly_comparison' and months and len(months) >= 2:
            month_col = None
            for col in ['月份', 'data_month']:
                if col in df.columns:
                    month_col = col
                    break

            if month_col:
                data_summary += f"\n对比月份: {months[0]} vs {months[1]}"
                data_summary += f"\n各月数据量:"
                for m in months:
                    count = len(df[df[month_col] == m])
                    data_summary += f"\n  - {m}: {count}件"

                # 类型变化
                if '大类名称' in df.columns:
                    data_summary += f"\n各类型月度变化:"
                    for m_idx in range(len(months)-1):
                        m1, m2 = months[m_idx], months[m_idx+1]
                        df1 = df[df[month_col] == m1]
                        df2 = df[df[month_col] == m2]
                        for cat in df['大类名称'].unique()[:5]:
                            c1 = len(df1[df1['大类名称'] == cat])
                            c2 = len(df2[df2['大类名称'] == cat])
                            change = c2 - c1
                            pct = (c2 - c1) / c1 * 100 if c1 > 0 else 0
                            data_summary += f"\n  - {cat}: {c1}→{c2} ({change:+d}, {pct:+.1f}%)"

        # 添加关键统计
        for col in ['大类名称', '小类名称', '所属片区', '问题来源', '处置部门']:
            if col in df.columns:
                top3 = df[col].value_counts().head(3)
                data_summary += f"\n{col} TOP3: {dict(top3)}"

        # 构建提示词
        if template_type == 'monthly_comparison':
            prompt = f"""请分析以下案件数据的月度对比情况：

{data_summary}

对比月份: {months[0]} 与 {months[1]}

重要说明：
- "所属片区"字段（如东、西、南、北、中片区）表示案件发生的地理位置区域
- "处置部门"字段（如执法东片区、执法南片区等）表示负责处置案件的部门
- 这两者是不同的概念，不要混淆或关联分析

请生成以下内容（以JSON格式返回）：
{{
    "summary": "数据概况，明确说明对比的是哪两个月，各有多少案件，环比变化百分比",
    "key_findings": [
        "发现1：具体说明哪个问题类型增长/下降最多，引用具体数字和百分比",
        "发现2：案件数量变化趋势分析",
        "发现3：片区或来源变化分析"
    ],
    "recommendations": [
        "建议1：针对变化趋势的具体管理建议",
        "建议2：资源配置建议"
    ]
}}

注意：
1. key_findings和recommendations数组只包含有实际价值的分析和建议
2. 如果某方面数据不足或无法分析，不要强行编造发现，可以减少数组元素数量
3. 每个发现都必须引用具体数据，不要说"暂无数据"、"无法分析"等空话
"""
        elif template_type == 'yearly_summary':
            prompt = f"""请分析以下案件数据的年度总结：

{data_summary}

分析年份: {year}年

请生成以下内容（以JSON格式返回）：
{{
    "summary": "数据概况（2-3句话）",
    "key_findings": ["发现1", "发现2", "发现3"],
    "recommendations": ["建议1", "建议2", "建议3"]
}}
"""
        elif template_type == 'special_analysis':
            prompt = f"""请分析以下专项数据：

{data_summary}

分析维度: {dimension}
分析范围: {', '.join(dimension_values) if dimension_values else '全部'}

请生成以下内容（以JSON格式返回）：
{{
    "summary": "数据概况（2-3句话）",
    "key_findings": ["发现1", "发现2", "发现3"],
    "recommendations": ["建议1", "建议2", "建议3"]
}}
"""
        else:
            prompt = f"""请分析以下案件数据：

{data_summary}

请生成以下内容（以JSON格式返回）：
{{
    "summary": "数据概况（2-3句话）",
    "key_findings": ["发现1", "发现2", "发现3"],
    "recommendations": ["建议1", "建议2", "建议3"]
}}
"""

        messages = [
            {"role": "system", "content": "你是一个数据分析专家，擅长从数据中发现规律并给出建议。"},
            {"role": "user", "content": prompt}
        ]

        # 调用LLM
        success, result = call_llm_api(
            API_URL, API_KEY, MODEL,
            messages,
            max_tokens=1500,
            provider_name="火山引擎-智能报告"
        )

        if success:
            # 解析JSON
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                return json.loads(json_match.group())

        return {"summary": "分析生成中...", "key_findings": [], "recommendations": []}

    except Exception as e:
        print(f"[智能报告] LLM调用失败: {e}")
        return {"summary": "分析生成中...", "key_findings": [], "recommendations": []}


def render_smart_report_html(df, template_type, months, year, dimension, dimension_values,
                              charts_base64, insights, filter_desc, original_count, filtered_count):
    """渲染精美HTML报告 - 按照模板结构组织"""

    # 获取模板名称
    template_names = {
        'monthly_comparison': '月度对比分析报告',
        'yearly_summary': '年度总结报告',
        'special_analysis': '专项分析报告',
        'full_analysis': '全量分析报告'
    }
    report_title = template_names.get(template_type, '数据分析报告')

    # 月度对比时，标题显示对比月份
    if template_type == 'monthly_comparison' and months and len(months) >= 2:
        report_title = f'{months[0]}与{months[1]}对比分析报告'

    # 获取月份列
    month_col = None
    for col in ['月份', 'data_month']:
        if col in df.columns:
            month_col = col
            break

    # 解析图表，按名称分类
    charts_dict = {}
    for title, img_base64 in charts_base64:
        charts_dict[title] = img_base64

    # 生成核心数据概览（汇总）
    summary_box_html = ""
    if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
        m1_count = len(df[df[month_col] == months[0]])
        m2_count = len(df[df[month_col] == months[1]])
        total_count = m1_count + m2_count
        change = m2_count - m1_count
        change_pct = (m2_count - m1_count) / m1_count * 100 if m1_count > 0 else 0
        change_color = 'positive' if change > 0 else 'negative'

        summary_box_html = f'''
        <div class="summary-box">
            <div class="summary-item">
                <div class="value">{total_count:,}</div>
                <div class="label">总案件量</div>
            </div>
            <div class="summary-item">
                <div class="value">{m1_count:,}</div>
                <div class="label">{months[0]}案件</div>
            </div>
            <div class="summary-item highlight">
                <div class="value">{m2_count:,}</div>
                <div class="label">{months[1]}案件</div>
            </div>
            <div class="summary-item">
                <div class="value {change_color}">{change_pct:+.2f}%</div>
                <div class="label">环比增长</div>
            </div>
        </div>
        '''
    else:
        # 非月度对比模式
        completion_rate = 0
        if '当前阶段名称' in df.columns:
            completion_rate = (df['当前阶段名称'] == '[办结]').sum() / len(df) * 100
        summary_box_html = f'''
        <div class="summary-box">
            <div class="summary-item highlight">
                <div class="value">{filtered_count:,}</div>
                <div class="label">案件总数</div>
            </div>
            <div class="summary-item">
                <div class="value">{len(df["大类名称"].unique()) if "大类名称" in df.columns else 0}</div>
                <div class="label">问题类型</div>
            </div>
            <div class="summary-item">
                <div class="value">{completion_rate:.1f}%</div>
                <div class="label">结案率</div>
            </div>
            <div class="summary-item">
                <div class="value">{len(df["所属片区"].unique()) if "所属片区" in df.columns else 0}</div>
                <div class="label">涉及片区</div>
            </div>
        </div>
        '''

    # 生成关键发现HTML
    findings_html = ""
    findings_list = insights.get('key_findings', [])
    for finding in findings_list:
        if finding and finding.strip():
            findings_html += f'''
        <div class="finding-item">
            <h4>关键发现</h4>
            <p>{finding}</p>
        </div>
        '''

    # 只有有发现时才显示关键发现部分
    findings_section = ""
    if findings_html.strip():
        findings_section = f'''
        <div class="section">
            <h2 class="section-title">关键发现</h2>
            <div class="key-findings">
                {findings_html}
            </div>
        </div>
        '''

    # 生成综合仪表盘HTML
    dashboard_html = ""
    if '00_综合仪表盘' in charts_dict:
        dashboard_html = f'''
        <div class="section">
            <h2 class="section-title">综合仪表盘</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['00_综合仪表盘']}" class="dashboard-img" alt="综合仪表盘">
                <div class="chart-caption">案件数据分析综合仪表盘 - 展示各维度数据概况</div>
            </div>
        </div>
        '''

    # 生成各部分图表和分析HTML
    sections_html = ""

    # 一、月份案件总量对比
    if '01_案件总量对比' in charts_dict:
        # 生成分析文本和数据表格
        analysis_text = ""
        data_table = ""
        if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
            m1_count = len(df[df[month_col] == months[0]])
            m2_count = len(df[df[month_col] == months[1]])
            change = m2_count - m1_count
            change_pct = (m2_count - m1_count) / m1_count * 100 if m1_count > 0 else 0

            # 计算延期次数和返工次数
            df1 = df[df[month_col] == months[0]]
            df2 = df[df[month_col] == months[1]]
            delay1 = pd.to_numeric(df1['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df1.columns else 0
            delay2 = pd.to_numeric(df2['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df2.columns else 0
            rework1 = pd.to_numeric(df1['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df1.columns else 0
            rework2 = pd.to_numeric(df2['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df2.columns else 0

            analysis_text = f'{months[1]}案件总量{m2_count}件，较{months[0]}的{m1_count}件增长{change_pct:.2f}%。案件量增长可能与季节性因素和监管力度有关。建议关注案件增长趋势，合理调配处置资源。'

            data_table = f'''
            <table class="data-table">
                <tr>
                    <th>月份</th>
                    <th>案件数量</th>
                    <th>延期次数</th>
                    <th>返工次数</th>
                    <th>环比变化</th>
                </tr>
                <tr>
                    <td>{months[0]}</td>
                    <td>{m1_count:,}</td>
                    <td>{int(delay1)}</td>
                    <td>{int(rework1)}</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>{months[1]}</td>
                    <td>{m2_count:,}</td>
                    <td>{int(delay2)}</td>
                    <td>{int(rework2)}</td>
                    <td class="{'positive' if change > 0 else 'negative'}">{change_pct:+.2f}%</td>
                </tr>
            </table>
            '''

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">一、月份案件总量对比</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['01_案件总量对比']}" alt="月份案件总量对比">
                <div class="chart-caption">{months[0] if months else ''}与{months[1] if months else ''}案件总量对比及占比分布</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 二、问题类型分布对比
    if '02_问题类型对比' in charts_dict:
        # 生成分析文本和数据表格
        analysis_text = ""
        data_table = ""
        if '大类名称' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                type_counts1 = df1['大类名称'].value_counts()
                type_counts2 = df2['大类名称'].value_counts()

                # 找出变化最大的类型
                max_change_type = ""
                max_change_val = 0
                for cat in df['大类名称'].unique():
                    c1 = type_counts1.get(cat, 0)
                    c2 = type_counts2.get(cat, 0)
                    change = c2 - c1
                    if abs(change) > abs(max_change_val):
                        max_change_val = change
                        max_change_type = cat

                analysis_text = f'{max_change_type}类案件变化最显著，从{type_counts1.get(max_change_type, 0)}件变化至{type_counts2.get(max_change_type, 0)}件。建议重点关注变化显著的类型。'

                data_table = '<table class="data-table"><tr><th>大类名称</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化数量</th><th>变化率</th></tr>'
                for cat in df['大类名称'].value_counts().head(6).index:
                    c1 = type_counts1.get(cat, 0)
                    c2 = type_counts2.get(cat, 0)
                    change = c2 - c1
                    pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                    color_class = 'positive' if change > 0 else ('negative' if change < 0 else '')
                    data_table += f'<tr><td>{cat}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{change:+,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">二、问题类型分布对比</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['02_问题类型对比']}" alt="问题类型分布对比">
                <div class="chart-caption">{months[0] if months else ''}与{months[1] if months else ''}各问题类型占比分布对比</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 三、TOP10小类问题对比
    if '03_TOP10小类问题对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '小类名称' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                # 获取两个月份各自所有的统计，不只是TOP10
                all_counts1 = df1['小类名称'].value_counts()
                all_counts2 = df2['小类名称'].value_counts()

                # 获取两个月TOP10的并集
                top10_1_names = set(all_counts1.head(10).index)
                top10_2_names = set(all_counts2.head(10).index)
                all_items = list(top10_1_names | top10_2_names)
                all_items.sort(key=lambda x: all_counts2.get(x, 0) + all_counts1.get(x, 0), reverse=True)

                # 找出变化最大的小类
                max_change_name = ""
                max_change_val = 0
                for name in all_items:
                    c1 = all_counts1.get(name, 0)
                    c2 = all_counts2.get(name, 0)
                    change = c2 - c1
                    if abs(change) > abs(max_change_val):
                        max_change_val = change
                        max_change_name = name

                analysis_text = f'{max_change_name}问题变化最显著，从{months[0]}的{all_counts1.get(max_change_name, 0)}件变化至{months[1]}的{all_counts2.get(max_change_name, 0)}件。建议针对高频问题制定专项治理方案，加强源头管控。'

                data_table = '<table class="data-table"><tr><th>排名</th><th>小类名称</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化</th></tr>'
                for i, name in enumerate(all_items[:10], 1):
                    c1 = all_counts1.get(name, 0)
                    c2 = all_counts2.get(name, 0)
                    change = c2 - c1
                    color_class = 'positive' if change > 0 else ('negative' if change < 0 else '')
                    data_table += f'<tr><td>{i}</td><td>{name}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{change:+,}</td></tr>'
                data_table += '</table>'
            else:
                top10 = df['小类名称'].value_counts().head(10)
                analysis_text = "小类问题案件量前10名分析。建议针对高频问题制定专项治理方案。"
                data_table = '<table class="data-table"><tr><th>排名</th><th>小类名称</th><th>案件数量</th><th>占比</th></tr>'
                for i, (name, count) in enumerate(top10.items(), 1):
                    pct = count / filtered_count * 100
                    data_table += f'<tr><td>{i}</td><td>{name}</td><td>{count:,}</td><td>{pct:.1f}%</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">三、TOP10小类问题对比</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['03_TOP10小类问题对比']}" alt="TOP10小类问题对比">
                <div class="chart-caption">小类问题案件量前10名对比分析</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 四、片区案件分析
    if '04_片区案件对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '所属片区' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                district_counts1 = df1['所属片区'].value_counts()
                district_counts2 = df2['所属片区'].value_counts()

                # 找出变化最大的片区
                max_change_district = ""
                max_change_pct = 0
                for district in df['所属片区'].unique():
                    c1 = district_counts1.get(district, 0)
                    c2 = district_counts2.get(district, 0)
                    pct = (c2 - c1) / c1 * 100 if c1 > 0 else 0
                    if abs(pct) > abs(max_change_pct):
                        max_change_pct = pct
                        max_change_district = district

                analysis_text = f'{max_change_district}案件量变化最显著({max_change_pct:+.1f}%)。建议根据片区案件分布调整资源配置。'

                data_table = '<table class="data-table"><tr><th>片区</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                for district in df['所属片区'].value_counts().index:
                    c1 = district_counts1.get(district, 0)
                    c2 = district_counts2.get(district, 0)
                    pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                    color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                    data_table += f'<tr><td>{district}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">四、片区案件分析</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['04_片区案件对比']}" alt="片区案件分析">
                <div class="chart-caption">各片区案件数量对比及变化率分析</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 五、问题来源分析
    if '05_问题来源对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '问题来源' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                source_counts1 = df1['问题来源'].value_counts()
                source_counts2 = df2['问题来源'].value_counts()

                main_source = df['问题来源'].value_counts().index[0] if len(df['问题来源'].value_counts()) > 0 else ''
                main_pct = df['问题来源'].value_counts().values[0] / len(df) * 100 if len(df['问题来源'].value_counts()) > 0 else 0

                analysis_text = f'{main_source}是主要案件来源，占比约{main_pct:.1f}%。建议优化监督员巡查路线，提升案件发现效率。'

                data_table = '<table class="data-table"><tr><th>问题来源</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                for source in df['问题来源'].value_counts().head(5).index:
                    c1 = source_counts1.get(source, 0)
                    c2 = source_counts2.get(source, 0)
                    pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                    color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                    data_table += f'<tr><td>{source}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">五、问题来源分析</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['05_问题来源对比']}" alt="问题来源分析">
                <div class="chart-caption">各问题来源渠道案件量对比</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 六、处置部门分析（月度对比）
    if '07_处置部门TOP10对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '处置部门' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                dept_counts1 = df1['处置部门'].value_counts()
                dept_counts2 = df2['处置部门'].value_counts()

                # 获取两个月TOP10的并集，确保数据完整
                all_depts = list(set(dept_counts1.head(10).index) | set(dept_counts2.head(10).index))
                all_depts.sort(key=lambda x: dept_counts2.get(x, 0) + dept_counts1.get(x, 0), reverse=True)

                main_dept = all_depts[0] if all_depts else ''
                main_count1 = dept_counts1.get(main_dept, 0)
                main_count2 = dept_counts2.get(main_dept, 0)

                analysis_text = f'{main_dept}承担案件量最多，{months[0]}为{main_count1}件，{months[1]}为{main_count2}件。建议根据案件分布调整人力配置，优化案件分流机制。'

                data_table = '<table class="data-table"><tr><th>处置部门</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>变化率</th></tr>'
                for dept in all_depts[:10]:
                    c1 = dept_counts1.get(dept, 0)
                    c2 = dept_counts2.get(dept, 0)
                    pct = (c2 - c1) / c1 * 100 if c1 > 0 else (100 if c2 > 0 else 0)
                    color_class = 'positive' if pct > 0 else ('negative' if pct < 0 else '')
                    data_table += f'<tr><td>{dept}</td><td>{c1:,}</td><td>{c2:,}</td><td class="{color_class}">{pct:+.1f}%</td></tr>'
                data_table += '</table>'
            else:
                dept_counts = df['处置部门'].value_counts().head(6)
                main_dept = dept_counts.index[0] if len(dept_counts) > 0 else ''
                main_count = dept_counts.values[0] if len(dept_counts) > 0 else 0
                analysis_text = f'{main_dept}承担案件量最多({main_count}件)。建议根据案件分布调整人力配置。'
                data_table = '<table class="data-table"><tr><th>处置部门</th><th>案件数</th></tr>'
                for dept, count in dept_counts.items():
                    data_table += f'<tr><td>{dept}</td><td>{count:,}</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">六、处置部门分析</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['07_处置部门TOP10对比']}" alt="处置部门TOP10对比">
                <div class="chart-caption">处置部门案件量TOP10对比</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 七、街道案件分布
    if '06_街道案件对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '所属街道' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]
                street_counts1 = df1['所属街道'].value_counts()
                street_counts2 = df2['所属街道'].value_counts()

                main_street = df['所属街道'].value_counts().index[0] if len(df['所属街道'].value_counts()) > 0 else ''
                main_count = df['所属街道'].value_counts().values[0] if len(df['所属街道'].value_counts()) > 0 else 0

                analysis_text = f'{main_street}案件量最高({main_count}件)。建议重点关注案件量高的街道区域城市管理问题。'

                data_table = '<table class="data-table"><tr><th>街道</th><th>' + months[0] + '案件</th><th>' + months[1] + '案件</th><th>合计</th></tr>'
                for street in df['所属街道'].value_counts().head(5).index:
                    c1 = street_counts1.get(street, 0)
                    c2 = street_counts2.get(street, 0)
                    total = c1 + c2
                    data_table += f'<tr><td>{street}</td><td>{c1:,}</td><td>{c2:,}</td><td>{total:,}</td></tr>'
                data_table += '</table>'

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">七、街道案件分布</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['06_街道案件对比']}" alt="街道案件分布">
                <div class="chart-caption">各街道案件量对比分析</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 八、效率指标分析（案件状态）
    if '08_案件状态对比' in charts_dict:
        analysis_text = ""
        data_table = ""
        if '当前阶段名称' in df.columns:
            if template_type == 'monthly_comparison' and months and len(months) >= 2 and month_col:
                df1 = df[df[month_col] == months[0]]
                df2 = df[df[month_col] == months[1]]

                # 计算结案率
                rate1 = (df1['当前阶段名称'] == '[办结]').sum() / len(df1) * 100 if len(df1) > 0 else 0
                rate2 = (df2['当前阶段名称'] == '[办结]').sum() / len(df2) * 100 if len(df2) > 0 else 0

                delay1 = pd.to_numeric(df1['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df1.columns else 0
                delay2 = pd.to_numeric(df2['延期次数'], errors='coerce').fillna(0).sum() if '延期次数' in df2.columns else 0
                rework1 = pd.to_numeric(df1['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df1.columns else 0
                rework2 = pd.to_numeric(df2['返工次数'], errors='coerce').fillna(0).sum() if '返工次数' in df2.columns else 0

                analysis_text = f'结案率从{months[0]}的{rate1:.2f}%变化至{months[1]}的{rate2:.2f}%。延期次数从{int(delay1)}次变化至{int(delay2)}次，返工次数从{int(rework1)}次变化至{int(rework2)}次。'

                data_table = f'''
                <table class="data-table">
                    <tr>
                        <th>效率指标</th>
                        <th>{months[0]}</th>
                        <th>{months[1]}</th>
                        <th>变化</th>
                    </tr>
                    <tr>
                        <td>结案率</td>
                        <td>{rate1:.2f}%</td>
                        <td>{rate2:.2f}%</td>
                        <td class="{'positive' if rate2 > rate1 else 'negative'}">{rate2 - rate1:+.2f}%</td>
                    </tr>
                    <tr>
                        <td>延期次数</td>
                        <td>{int(delay1)}</td>
                        <td>{int(delay2)}</td>
                        <td class="{'positive' if delay2 < delay1 else 'negative'}">{int(delay2 - delay1):+}</td>
                    </tr>
                    <tr>
                        <td>返工次数</td>
                        <td>{int(rework1)}</td>
                        <td>{int(rework2)}</td>
                        <td class="{'negative' if rework2 > rework1 else 'positive'}">{int(rework2 - rework1):+}</td>
                    </tr>
                </table>
                '''

        sections_html += f'''
        <div class="section">
            <h2 class="section-title">八、效率指标分析</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{charts_dict['08_案件状态对比']}" alt="效率指标分析">
                <div class="chart-caption">结案率与超时情况对比分析</div>
            </div>
            <div class="analysis-text">
                <strong>分析结论：</strong>{analysis_text}
            </div>
            {data_table}
        </div>
        '''

    # 九、管理建议
    recommendations_html = ""
    recommendations_list = insights.get('recommendations', [])
    border_colors = ['#e74c3c', '#27ae60', '#9b59b6', '#f39c12']
    for i, rec in enumerate(recommendations_list):
        if rec and rec.strip():
            color = border_colors[i % len(border_colors)]
            recommendations_html += f'''
        <div class="finding-item" style="border-left-color: {color};">
            <h4>管理建议</h4>
            <p>{rec}</p>
        </div>
        '''

    # 只有有建议时才显示管理建议部分
    if recommendations_html.strip():
        sections_html += f'''
    <div class="section">
        <h2 class="section-title">九、管理建议</h2>
        <div class="key-findings">
            {recommendations_html}
        </div>
    </div>
    '''

    # HTML模板
    # CSS样式（独立变量，避免f-string转义问题）
    css_styles = '''
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }

        .header {
            text-align: center;
            padding-bottom: 30px;
            border-bottom: 3px solid #667eea;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 36px;
            color: #333;
            margin-bottom: 10px;
        }

        .header .subtitle {
            font-size: 18px;
            color: #666;
        }

        .header .date {
            font-size: 14px;
            color: #999;
            margin-top: 10px;
        }

        .summary-box {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }

        .summary-item {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s ease;
        }

        .summary-item:hover {
            transform: translateY(-5px);
        }

        .summary-item .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }

        .summary-item .label {
            font-size: 14px;
            color: #666;
        }

        .summary-item.highlight {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .summary-item.highlight .value,
        .summary-item.highlight .label {
            color: white;
        }

        .section {
            margin-bottom: 50px;
        }

        .section-title {
            font-size: 24px;
            color: #333;
            margin-bottom: 20px;
            padding-left: 15px;
            border-left: 4px solid #667eea;
        }

        .chart-container {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
        }

        .chart-container img {
            width: 100%;
            border-radius: 10px;
        }

        .chart-caption {
            text-align: center;
            color: #666;
            margin-top: 15px;
            font-size: 14px;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }

        .data-table th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 14px;
        }

        .data-table td {
            padding: 12px;
            text-align: center;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }

        .data-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .data-table tr:hover {
            background: #e9ecef;
        }

        .positive {
            color: #27ae60;
            font-weight: bold;
        }

        .negative {
            color: #e74c3c;
            font-weight: bold;
        }

        .analysis-text {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            border-radius: 0 10px 10px 0;
            margin-bottom: 20px;
            font-size: 14px;
            line-height: 1.8;
        }

        .key-findings {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }

        .finding-item {
            background: linear-gradient(to right, #e3f2fd, #f3e5f5);
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #2196f3;
        }

        .finding-item h4 {
            color: #333;
            margin-bottom: 10px;
            font-size: 16px;
        }

        .finding-item p {
            color: #666;
            font-size: 13px;
            line-height: 1.6;
        }

        .dashboard-img {
            width: 100%;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .footer {
            text-align: center;
            padding-top: 30px;
            border-top: 1px solid #eee;
            color: #999;
            font-size: 12px;
        }

        @media (max-width: 768px) {
            .summary-box {
                grid-template-columns: repeat(2, 1fr);
            }
            .key-findings {
                grid-template-columns: 1fr;
            }
        }
    '''

    html_template = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>案件数据分析报告 - {report_title}</title>
    <style>
    {css_styles}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>案件数据分析报告</h1>
            <div class="subtitle">{report_title}</div>
            <div class="date">生成日期: {datetime.datetime.now().strftime('%Y年%m月%d日')}</div>
        </div>

        <!-- 核心数据概览 -->
        {summary_box_html}

        <!-- 关键发现 -->
        {findings_section}

        <!-- 综合仪表盘 -->
        {dashboard_html}

        <!-- 各部分分析 -->
        {sections_html}

        <div class="footer">
            <p>数据分析报告 - 自动生成 | 数据来源: 案件管理系统</p>
            <p>如有疑问请联系相关部门核实数据准确性</p>
        </div>
    </div>
</body>
</html>
    '''

    return html_template


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