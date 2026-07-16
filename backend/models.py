# -*- coding: utf-8 -*-
"""ORM模型定义 - 从app.py提取的数据库模型"""
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from models_init import Base

# 用户模型
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 权限模型
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
    content = Column(Text)
    summary = Column(String(500))
    category_id = Column(Integer, nullable=False)
    author_id = Column(Integer, nullable=False)
    status = Column(String(20), default='draft')
    view_count = Column(Integer, default=0)
    file_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True))

# 业务平台模型
class BusinessPlatform(Base):
    __tablename__ = 'business_platforms'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    url = Column(String(500), nullable=False)
    image_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 案件管理模型
class Case(Base):
    __tablename__ = 'cases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_number = Column(String(50), unique=True, nullable=False)
    stage_light = Column(String(20))
    auth_status = Column(String(50))
    supervise_status = Column(String(50))
    report_time = Column(DateTime)
    source = Column(String(100))
    major_category = Column(String(100))
    minor_category = Column(String(100))
    problem_type = Column(String(50))
    problem_desc = Column(Text)
    address_desc = Column(String(500))
    responsible_grid = Column(String(100))
    area = Column(String(100))
    street = Column(String(100))
    community = Column(String(100))
    transfer_time = Column(DateTime)
    current_stage_time_info = Column(String(100))
    current_stage_deadline = Column(DateTime)
    current_stage_remaining_time = Column(String(100))
    area_level = Column(Integer)
    area_level_name = Column(String(50))
    responsible_area_name = Column(String(100))
    bundle_deadline = Column(DateTime)
    bundle_time_limit = Column(String(50))
    photo_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 案件管理扩展字段
    category = Column(String(20))
    status = Column(String(20), default='跟进中')
    owner_unit = Column(String(100))
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    pending_reason = Column(Text)
    pending_deadline = Column(DateTime)
    difficult_type = Column(String(50))
    last_follow_time = Column(DateTime)
    follow_count = Column(Integer, default=0)
    close_time = Column(DateTime)
    close_remark = Column(Text)
    remark = Column(Text)

# 系统配置模型
class SystemConfig(Base):
    __tablename__ = 'system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# 案件跟进模型
class CaseFollow(Base):
    __tablename__ = 'case_follows'
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, nullable=False)
    follow_type = Column(String(20))
    content = Column(Text)
    attachments = Column(Text)
    follow_time = Column(DateTime, default=datetime.datetime.now)
    follow_user = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.now)

# 操作日志模型
class OperationLog(Base):
    __tablename__ = 'operation_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    table_name = Column(String(100))
    operation_type = Column(String(20))
    record_id = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

# ======== 汛情值守模块模型 ========

# 天气记录模型
class FloodWeatherRecord(Base):
    __tablename__ = 'flood_weather_records'
    id = Column(Integer, primary_key=True, autoincrement=True)
    city_code = Column(String(20))
    weather_data = Column(Text)
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
    road_type = Column(String(50))
    longitude = Column(String(50))
    latitude = Column(String(50))
    responsible_person = Column(String(100))
    responsible_phone = Column(String(20))
    duty_persons = Column(Text)
    traffic_police = Column(String(100))
    traffic_police_phone = Column(String(20))
    water_level = Column(String(20), default='normal')
    water_depth = Column(String(20))
    management_unit = Column(String(100))
    monitoring_points = Column(Text)
    remarks = Column(Text)
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
    weather_snapshot = Column(Text)
    location = Column(String(200))
    images = Column(Text)
    operator = Column(String(50))
    warning_id = Column(Integer, nullable=True)
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
    level = Column(String(20), nullable=False)
    status = Column(String(20), default='active')
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime, nullable=True)
    report_snapshot = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

# 带班领导模型
class FloodDutyLeader(Base):
    __tablename__ = 'flood_duty_leaders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(50), default='带班领导')
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
    supplies_list = Column(Text)
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
    group_type = Column(String(20), nullable=False, default='admin')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# 每日排班明细模型
class FloodDutyAssignment(Base):
    __tablename__ = 'flood_duty_assignments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_date = Column(DateTime, nullable=False)
    shift_name = Column(String(20), nullable=False)
    person_name = Column(String(50), nullable=False)
    person_phone = Column(String(20), default='')
    source = Column(String(20), default='regular')
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
    status = Column(String(20), default='recommended')
    confirmed_by = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
