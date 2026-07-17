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
    from backend.scoring import (
        calculate_law_enforcement_score, calculate_huanwei_score,
        calculate_garden_score, calculate_park_score, calculate_generic_score,
        calculate_law_enforcement_score_v2, calculate_huanwei_score_v2,
        calculate_garden_score_v2, calculate_park_score_v2
    )
except ImportError:
    from scoring import (
        calculate_law_enforcement_score, calculate_huanwei_score,
        calculate_garden_score, calculate_park_score, calculate_generic_score,
        calculate_law_enforcement_score_v2, calculate_huanwei_score_v2,
        calculate_garden_score_v2, calculate_park_score_v2
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
        register_map_routes(app=app)
        print("地图路由注册成功")
    except Exception as e:
        print(f"地图路由注册失败: {e}")

    # 激活小工具路由
    try:
        register_tools_routes(app=app)
        print("小工具路由注册成功")
    except Exception as e:
        print(f"小工具路由注册失败: {e}")

    # 激活统一知识库路由
    try:
        register_kb_routes(app=app)
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
    register_chart_routes(app=app)
    print("图表分析路由注册成功")
except Exception as e:
    print(f"图表分析路由注册失败: {e}")


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