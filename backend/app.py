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
    from backend.helpers import call_llm_api
except ImportError:
    from helpers import call_llm_api

try:
    from backend.cases_routes import register_case_management_routes
except ImportError:
    from cases_routes import register_case_management_routes

try:
    from backend.flood_routes import register_flood_monitor_routes
except ImportError:
    from flood_routes import register_flood_monitor_routes

try:
    from backend.auth_routes import register_auth_routes
except ImportError:
    from auth_routes import register_auth_routes

try:
    from backend.upload_routes import register_upload_routes
except ImportError:
    from upload_routes import register_upload_routes

try:
    from backend.data_management_routes import register_data_management_routes
except ImportError:
    from data_management_routes import register_data_management_routes

try:
    from backend.assessment_routes import register_assessment_routes
except ImportError:
    from assessment_routes import register_assessment_routes

try:
    from backend.analysis_routes import register_analysis_routes
except ImportError:
    from analysis_routes import register_analysis_routes

try:
    from backend.cms_routes import register_cms_routes
except ImportError:
    from cms_routes import register_cms_routes

try:
    from backend.data_edit_routes import register_data_edit_routes
except ImportError:
    from data_edit_routes import register_data_edit_routes

try:
    from backend.knowledge_routes import register_knowledge_routes
except ImportError:
    from knowledge_routes import register_knowledge_routes

try:
    from backend.case_standards_routes import register_case_standards_routes
except ImportError:
    from case_standards_routes import register_case_standards_routes

try:
    from backend.report_routes import register_report_routes
except ImportError:
    from report_routes import register_report_routes

try:
    from backend.tools_routes import register_tools_routes
except ImportError:
    from tools_routes import register_tools_routes

try:
    from backend.kb_routes import register_kb_routes
except ImportError:
    from kb_routes import register_kb_routes

try:
    from backend.map_routes import register_map_routes
except ImportError:
    from map_routes import register_map_routes

try:
    from backend.analysis_v2_routes import register_analysis_v2_routes
except ImportError:
    from analysis_v2_routes import register_analysis_v2_routes

try:
    from backend.chart_routes import register_chart_routes
except ImportError:
    from chart_routes import register_chart_routes

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

    # 注册认证路由
    register_auth_routes(
        app=app,
        Session=Session,
        User=User,
        engine=engine,
    )
    print("认证路由注册成功")

    # 注册数据上传路由
    register_upload_routes(
        app=app,
        Session=Session,
        engine=engine,
    )
    print("数据上传路由注册成功")

    # 注册数据管理路由
    register_data_management_routes(
        app=app,
        Session=Session,
        engine=engine,
        BusinessPlatform=BusinessPlatform,
        SystemConfig=SystemConfig,
    )
    print("数据管理路由注册成功")

    # 注册数据分析路由
    register_analysis_routes(
        app=app,
        Session=Session,
        engine=engine,
    )
    print("数据分析路由注册成功")

    # 注册CMS路由
    register_cms_routes(
        app=app,
        Session=Session,
        Category=Category,
        Article=Article,
    )
    print("CMS路由注册成功")

    # 注册数据编辑路由
    register_data_edit_routes(
        app=app,
        Session=Session,
        engine=engine,
        OperationLog=OperationLog,
    )
    print("数据编辑路由注册成功")

    # 注册知识库路由
    register_knowledge_routes(
        app=app,
        Session=Session,
        engine=engine,
        get_collection_stats=get_collection_stats,
        list_documents=list_documents,
        delete_document=delete_document,
        insert_document=insert_document,
        search_similar=search_similar,
        ask_question=ask_question,
        init_rag=init_rag,
    )
    print("知识库路由注册成功")

    # 注册立结案标准库路由
    register_case_standards_routes(
        app=app,
        Session=Session,
        engine=engine,
        protected=protected,
        admin_required=admin_required,
    )
    print("立结案标准库路由注册成功")

    # ===== Phase 9: 逐步激活新模块 =====
    # 激活地图/管辖区域路由
    try:
        register_map_routes(app=app, protected=protected)
        print("地图路由注册成功")
    except Exception as e:
        print(f"地图路由注册失败: {e}")

    # 激活小工具路由
    try:
        from helpers import extract_location_from_text
        register_tools_routes(
            app=app,
            protected=protected,
            extract_location_from_text=extract_location_from_text,
        )
        print("小工具路由注册成功")
    except Exception as e:
        print(f"小工具路由注册失败: {e}")

    # 激活统一知识库路由
    try:
        from kb_unified import (
            unified_ask,
            unified_search,
            get_unified_stats,
            migrate_general_to_unified,
            get_migration_status,
        )
        register_kb_routes(
            app=app,
            protected=protected,
            admin_required=admin_required,
            unified_ask=unified_ask,
            unified_search=unified_search,
            get_unified_stats=get_unified_stats,
            migrate_general_to_unified=migrate_general_to_unified,
            get_migration_status=get_migration_status,
        )
        print("统一知识库路由注册成功")
    except Exception as e:
        print(f"统一知识库路由注册失败: {e}")

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
# read_file_content 已移至 helpers.py
from helpers import read_file_content

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

# 注册数据分析V2和图表分析路由（需要在API配置和call_llm_api定义之后）
try:
    register_analysis_v2_routes(
        app=app,
        engine=engine,
        protected=protected,
        call_llm_api=call_llm_api,
        API_URL=API_URL,
        API_KEY=API_KEY,
        MODEL=MODEL,
        BAILIAN_GENERAL_API_URL=BAILIAN_GENERAL_API_URL,
        BAILIAN_GENERAL_API_KEY=BAILIAN_GENERAL_API_KEY,
        BAILIAN_GENERAL_MODEL=BAILIAN_GENERAL_MODEL,
    )
    print("数据分析V2路由注册成功")
except Exception as e:
    print(f"数据分析V2路由注册失败: {e}")

try:
    register_chart_routes(app=app, engine=engine, protected=protected)
    print("图表分析路由注册成功")
except Exception as e:
    print(f"图表分析路由注册失败: {e}")

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

# 数据上传路由已提取到 upload_routes.py
# 请查看 backend/upload_routes.py

# 认证路由已提取到 auth_routes.py
# 请查看 backend/auth_routes.py

# 数据管理路由已提取到 data_management_routes.py
# 请查看 backend/data_management_routes.py

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

# 注册考核评分路由（需要在V2评分函数定义之后）
if Session is not None:
    register_assessment_routes(
        app=app,
        Session=Session,
        engine=engine,
        protected=protected,
        call_llm_api=call_llm_api,
        API_URL=API_URL,
        API_KEY=API_KEY,
        MODEL=MODEL,
        calculate_law_enforcement_score=calculate_law_enforcement_score,
        calculate_huanwei_score=calculate_huanwei_score,
        calculate_garden_score=calculate_garden_score,
        calculate_park_score=calculate_park_score,
        calculate_generic_score=calculate_generic_score,
        calculate_law_enforcement_score_v2=calculate_law_enforcement_score_v2,
        calculate_huanwei_score_v2=calculate_huanwei_score_v2,
        calculate_garden_score_v2=calculate_garden_score_v2,
        calculate_park_score_v2=calculate_park_score_v2,
    )
    print("考核评分路由注册成功")

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

# 考核评分路由已提取到 assessment_routes.py
# 请查看 backend/assessment_routes.py

# 数据分析路由已提取到 analysis_routes.py
# 请查看 backend/analysis_routes.py

# CMS栏目相关API

# 数据分析V2路由已提取到 analysis_v2_routes.py
# 图表分析路由已提取到 chart_routes.py
# CMS路由已提取到 cms_routes.py
# 请查看 backend/cms_routes.py

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

# ==================== 操作日志 API ====================

# 批量上传进度存储
batch_upload_progress = {}
def get_batch_upload_progress(task_id):
    """获取批量上传进度"""
    if task_id in batch_upload_progress:
        return jsonify(batch_upload_progress[task_id]), 200
    return jsonify({'error': '任务不存在'}), 404
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
# ==================== 立结案标准索引管理 API ====================
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
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'SimSun']
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

    # 如果路径为空或者不存在文件，返回 index.html（禁止缓存，确保每次获取最新版本）
    if not path or not os.path.exists(os.path.join(frontend_dist, path)):
        response = send_from_directory(frontend_dist, 'index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # 带哈希的静态资源（JS/CSS）可长期缓存，其他文件短缓存
    resp = send_from_directory(frontend_dist, path)
    if '.' in path and any(path.endswith(ext) for ext in ('.js', '.css', '.woff2', '.woff', '.ttf')):
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    else:
        resp.headers['Cache-Control'] = 'no-cache'
    return resp

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG', '1') == '1',
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', '5000'))
    )