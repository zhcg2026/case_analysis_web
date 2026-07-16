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
    from backend.helpers import (
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token, protected, admin_required,
        get_json_payload, get_case_or_404, generate_slug, convert_nan_to_null,
        desensitize_name, desensitize_phone, desensitize_landline, desensitize_address,
        read_file_content
    )
except ImportError:
    from helpers import (
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token, protected, admin_required,
        get_json_payload, get_case_or_404, generate_slug, convert_nan_to_null,
        desensitize_name, desensitize_phone, desensitize_landline, desensitize_address,
        read_file_content
    )

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
SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('JWT_SECRET_KEY 未配置，禁止启动')
TOKEN_EXPIRATION = int(os.getenv('TOKEN_EXPIRATION_SECONDS', str(24 * 60 * 60)))  # 24小时

# 登录失败限制配置
LOGIN_ATTEMPTS = {}  # {username: {'count': int, 'lock_until': timestamp}}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5分钟


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



# 文件读取函数


# 大模型API配置（火山引擎）
API_KEY = os.getenv('ARK_API_KEY', '')
API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
MODEL = 'doubao-seed-1-8-251228'

# 阿里云百炼通用模型API配置
BAILIAN_GENERAL_API_KEY = os.getenv('BAILIAN_GENERAL_API_KEY', '')
BAILIAN_GENERAL_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
BAILIAN_GENERAL_MODEL = 'qwen-plus'

# 阿里云百炼城管通专用应用API配置
BAILIAN_CHENGGUANTONG_API_KEY = os.getenv('BAILIAN_CHENGGUANTONG_API_KEY', '')
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

# 视频报告路由
try:
    from backend.video_routes import register_video_routes
except ImportError:
    from video_routes import register_video_routes


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


# 注册视频报告路由
register_video_routes(app, engine)

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG', '1') == '1',
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', '5000'))
    )