# -*- coding: utf-8 -*-
"""ORM模型模块 - 从app.py提取的数据库模型定义"""
import os
import urllib.parse
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# 数据库配置
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'case_analysis')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '3306')

# 占位符变量
engine = None
Session = None
Base = None

def init_database():
    """初始化数据库连接和模型"""
    global engine, Session, Base
    
    try:
        # 检查必要的数据库配置
        if not all([DB_USER, DB_PASSWORD, DB_HOST]):
            print("警告: 数据库配置不完整，请设置 DB_USER, DB_PASSWORD, DB_HOST 环境变量")
            raise Exception("数据库配置缺失")
        
        # 创建数据库引擎
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
        engine = create_engine(
            f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4',
            pool_pre_ping=True,
            pool_recycle=3600
        )
        print("数据库连接成功")
        
        # 定义模型基类
        Base = declarative_base()
        
        # 导入所有模型
        from models import (
            User, Permission, Category, Article, BusinessPlatform,
            Case, SystemConfig, CaseFollow, OperationLog,
            FloodWeatherRecord, FloodRainEvent, FloodWaterloggingPoint,
            FloodDispatchRecord, FloodDutyShift, FloodWarning,
            FloodDutyLeader, FloodEmergencySupply, FloodPersonnel,
            FloodDutyAssignment, FloodStaffingLog
        )
        
        # 创建数据库表
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
        
        # 数据库迁移
        _run_migrations(engine)
        
        # 初始化人员花名册数据
        _init_personnel_data(engine)
        
        # 创建会话工厂
        Session = sessionmaker(bind=engine)
        
        return True
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        print("应用将以无数据库模式运行（登录和用户管理功能不可用）")
        engine = None
        Session = None
        return False

def _run_migrations(engine):
    """执行数据库迁移"""
    # 添加 dashboard 列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM permissions LIKE 'dashboard'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE permissions ADD COLUMN dashboard INT NOT NULL DEFAULT 0 AFTER user_id"))
                conn.commit()
                print("数据库迁移：已添加 dashboard 列")
    except Exception as e:
        print(f"数据库迁移检查: {e}")
    
    # 确保 data_management 和 spotcheck 列存在
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
    
    # 添加 flood_monitor 权限列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM permissions LIKE 'flood_monitor'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE permissions ADD COLUMN flood_monitor INT NOT NULL DEFAULT 0"))
                conn.commit()
                print("数据库迁移：已添加 flood_monitor 列")
    except Exception as e:
        print(f"数据库迁移检查(flood_monitor): {e}")
    
    # 添加 flood_warnings 表的 report_snapshot 列
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM flood_warnings LIKE 'report_snapshot'"))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE flood_warnings ADD COLUMN report_snapshot TEXT"))
                conn.commit()
                print("数据库迁移：已添加 report_snapshot 列")
    except Exception as e:
        print(f"数据库迁移检查(report_snapshot): {e}")

def _init_personnel_data(engine):
    """初始化人员花名册数据"""
    try:
        from models import FloodPersonnel
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

def get_engine():
    """获取数据库引擎"""
    return engine

def get_session():
    """获取会话工厂"""
    return Session

def get_base():
    """获取模型基类"""
    return Base
