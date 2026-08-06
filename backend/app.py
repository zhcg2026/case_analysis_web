# -*- coding: utf-8 -*-
"""智慧平台一站通 v2.0 - 精简版后端"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
import urllib.parse
import json
import requests
from sqlalchemy import create_engine, text
import datetime
from functools import wraps
import bcrypt

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists('../.env.local'):
    load_dotenv('../.env.local')
load_dotenv()

# 导入工具函数
try:
    from backend.helpers import (
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token, protected, admin_required,
        get_json_payload
    )
except ImportError:
    from helpers import (
        hash_password, verify_password, is_strong_password,
        check_login_attempts, record_failed_login, clear_login_attempts,
        generate_token, verify_token, protected, admin_required,
        get_json_payload
    )

# 导入路由注册
try:
    from backend.auth_routes import register_auth_routes
except ImportError:
    from auth_routes import register_auth_routes



try:
    from backend.cms_routes import register_cms_routes
except ImportError:
    from cms_routes import register_cms_routes


# 旧通用知识库路由 knowledge_routes、立结案标准库路由 case_standards_routes 均已废弃
# （改由统一库 unified_kb 的 /api/kb/admin/* 承接），不再 import 与注册。

try:
    from backend.kb_routes import register_kb_routes
except ImportError:
    from kb_routes import register_kb_routes

try:
    from backend.map_routes import register_map_routes
except ImportError:
    from map_routes import register_map_routes

try:
    from backend.analysis_routes import register_analysis_routes
except ImportError:
    from analysis_routes import register_analysis_routes

try:
    from backend.report_routes import register_report_routes
except ImportError:
    from report_routes import register_report_routes

try:
    from backend.template_export_routes import register_template_export_routes
except ImportError:
    from template_export_routes import register_template_export_routes

try:
    from backend.case_map_routes import register_case_map_routes
except ImportError:
    from case_map_routes import register_case_map_routes
# 数据管理路由
try:
    from backend.data_management_routes import register_data_management_routes
except ImportError:
    from data_management_routes import register_data_management_routes
# JWT配置
SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('JWT_SECRET_KEY 未配置，禁止启动')
TOKEN_EXPIRATION = int(os.getenv('TOKEN_EXPIRATION_SECONDS', str(24 * 60 * 60)))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 文件上传限制
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
if CORS_ORIGINS == '*':
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"], "expose_headers": ["Content-Disposition"]}})
else:
    origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/*": {"origins": origins_list, "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"], "expose_headers": ["Content-Disposition"]}})

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200

# 数据库配置
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'case_analysis')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '3306')

engine = None
Session = None
Base = None

try:
    from sqlalchemy.orm import declarative_base
    from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
    from sqlalchemy.sql import func
    from sqlalchemy.orm import sessionmaker

    if not all([DB_USER, DB_PASSWORD, DB_HOST]):
        logger.warning("数据库配置不完整")
        raise Exception("数据库配置缺失")

    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    engine = create_engine(f'mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4', pool_pre_ping=True, pool_recycle=3600)
    logger.info("数据库连接成功")

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
        data_analysis = Column(Integer, nullable=False, default=0)
        knowledge = Column(Integer, nullable=False, default=0)
        map = Column(Integer, nullable=False, default=0)
        case_map = Column(Integer, nullable=False, default=0)
        business = Column(Integer, nullable=False, default=0)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    class Category(Base):
        __tablename__ = 'categories'
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(100), unique=True, nullable=False)
        slug = Column(String(100), unique=True, nullable=False)
        description = Column(String(500))
        order = Column(Integer, default=0)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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

    class BusinessPlatform(Base):
        __tablename__ = 'business_platforms'
        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String(100), nullable=False, unique=True)
        url = Column(String(500), nullable=False)
        image_path = Column(String(500))
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    class SystemConfig(Base):
        __tablename__ = 'system_config'
        id = Column(Integer, primary_key=True, autoincrement=True)
        config_key = Column(String(100), unique=True, nullable=False)
        config_value = Column(Text)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

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
                logger.warning(f"数据库表创建跳过: {e}")
            else:
                raise

    Session = sessionmaker(bind=engine)

    # 注册认证路由
    register_auth_routes(app=app, Session=Session, User=User, engine=engine)
    logger.info("认证路由注册成功")



    # 注册CMS路由
    register_cms_routes(app=app, Session=Session, Category=Category, Article=Article)
    logger.info("CMS路由注册成功")


    # 旧通用知识库路由（knowledge_routes / rag.knowledge_base）与立结案标准库路由
    #（case_standards_routes / case_standards.*）均已废弃：
    # 前端"系统管理-知识库管理"现已对接统一库 unified_kb 的 /api/kb/admin/* 接口，
    # 立结案标准内容并入 unified_kb 的 doc_type=standard，由统一库管理接口接管。
    # 故不再注册 knowledge_routes 与 case_standards_routes。

    # 注册地图路由
    try:
        register_map_routes(app=app)
        logger.info("地图路由注册成功")
    except Exception as e:
        logger.warning(f"地图路由注册失败: {e}")

    # 注册数据分析路由
    try:
        register_analysis_routes(app=app, engine=engine)
        logger.info("数据分析路由注册成功")
    except Exception as e:
        logger.warning(f"数据分析路由注册失败: {e}")

    # 注册报告模板路由
    try:
        register_report_routes(app=app, engine=engine)
    except Exception as e:
        logger.warning(f"报告模板路由注册失败: {e}")

    # 注册模板导出路由
    try:
        register_template_export_routes(app=app, engine=engine)
        logger.info("模板导出路由注册成功")
    except Exception as e:
        logger.warning(f"模板导出路由注册失败: {e}")

    try:
        register_case_map_routes(app=app, engine=engine, protected=protected)
        logger.info("案件地图路由注册成功")
    except Exception as e:
        logger.warning(f"案件地图路由注册失败: {e}")

    # 数据管理路由
    try:
        register_data_management_routes(app=app, engine=engine, protected=protected, admin_required=admin_required)
        logger.info("数据管理路由注册成功")
    except Exception as e:
        logger.warning(f"数据管理路由注册失败: {e}")

except Exception as e:
    logger.error(f"数据库初始化失败: {e}")
    engine = None
    Session = None

# 注册统一知识库路由（不依赖 MySQL，独立可用，便于本地单独测试 KB 模块）
try:
    register_kb_routes(app=app, protected=protected, admin_required=admin_required)
    logger.info("统一知识库路由注册成功")
except Exception as e:
    logger.warning(f"统一知识库路由注册失败: {e}")

# 文件上传路由
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    return send_from_directory(upload_dir, filename)


# ===================== 图片上传（系统 Logo / 文章配图等） =====================
# 接收 multipart 文件（字段名 file），保存至 backend/uploads/，返回可访问 URL。
# 返回字段兼容前端：location（wangEditor 文章配图用）与 url（系统设置回填用）。
ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

@app.route('/api/upload/image', methods=['POST'])
@admin_required
def upload_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '请选择图片文件'}), 400
        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'error': '请选择图片文件'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXT:
            return jsonify({'error': '仅支持 jpg/png/gif/webp/bmp 图片格式'}), 400
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        import uuid
        save_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(upload_dir, save_name)
        file.save(save_path)
        url = f"/uploads/{save_name}"
        return jsonify({'success': True, 'location': url, 'url': url})
    except Exception as e:
        logger.warning(f"上传图片失败: {e}")
        return jsonify({'error': '上传失败'}), 500


# ===================== 附件上传（文章附件等） =====================
# 接收 multipart 文件（字段名 file），保存至 backend/uploads/，返回 file_path。
# 前端 Admin.vue handleFileUpload 期望 response.data.file_path。
ALLOWED_FILE_EXT = {'.doc', '.docx', '.xls', '.xlsx', '.pdf', '.ppt', '.pptx',
                    '.txt', '.csv', '.zip', '.rar', '.md',
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

@app.route('/api/upload/file', methods=['POST'])
@admin_required
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400
        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'error': '请选择文件'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_FILE_EXT:
            return jsonify({'error': '不支持的文件类型，仅允许文档/表格/压缩包/图片'}), 400
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        import uuid
        save_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(upload_dir, save_name)
        file.save(save_path)
        url = f"/uploads/{save_name}"
        return jsonify({'success': True, 'file_path': url, 'url': url})
    except Exception as e:
        logger.warning(f"上传文件失败: {e}")
        return jsonify({'error': '上传失败'}), 500


# ===================== 业务平台管理 =====================
@app.route('/api/business-platforms', methods=['GET'])
@protected
def get_business_platforms():
    try:
        if Session is None:
            return jsonify({'platforms': []})
        with Session() as session:
            platforms = session.query(BusinessPlatform).order_by(BusinessPlatform.created_at.desc()).all()
            result = []
            for p in platforms:
                result.append({
                    'id': p.id,
                    'name': p.name,
                    'url': p.url,
                    'image_path': p.image_path,
                    'created_at': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else None,
                    'updated_at': p.updated_at.strftime('%Y-%m-%d %H:%M:%S') if p.updated_at else None
                })
            return jsonify({'platforms': result})
    except Exception as e:
        logger.warning(f"获取业务平台失败: {e}")
        return jsonify({'error': '获取失败'}), 500


@app.route('/api/business-platforms', methods=['POST'])
@protected
def create_business_platform():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        image_path = data.get('image_path', '')

        if not name:
            return jsonify({'error': '平台名称不能为空'}), 400
        if not url:
            return jsonify({'error': '链接地址不能为空'}), 400

        if Session is None:
            return jsonify({'error': '数据库未连接'}), 503

        with Session() as session:
            existing = session.query(BusinessPlatform).filter_by(name=name).first()
            if existing:
                return jsonify({'error': '平台名称已存在'}), 400

            platform = BusinessPlatform(name=name, url=url, image_path=image_path)
            session.add(platform)
            session.commit()

            return jsonify({'id': platform.id, 'name': platform.name, 'message': '创建成功'}), 201
    except Exception as e:
        logger.warning(f"创建业务平台失败: {e}")
        return jsonify({'error': '创建失败'}), 500


@app.route('/api/business-platforms/<int:id>', methods=['PUT'])
@protected
def update_business_platform(id):
    try:
        if Session is None:
            return jsonify({'error': '数据库未连接'}), 503

        with Session() as session:
            platform = session.query(BusinessPlatform).filter_by(id=id).first()
            if not platform:
                return jsonify({'error': '平台不存在'}), 404

            data = request.get_json()
            if 'name' in data:
                platform.name = data['name'].strip()
            if 'url' in data:
                platform.url = data['url'].strip()
            if 'image_path' in data:
                platform.image_path = data['image_path']

            session.commit()
            return jsonify({'message': '更新成功'})
    except Exception as e:
        logger.warning(f"更新业务平台失败: {e}")
        return jsonify({'error': '更新失败'}), 500


@app.route('/api/business-platforms/<int:id>', methods=['DELETE'])
@protected
def delete_business_platform(id):
    try:
        if Session is None:
            return jsonify({'error': '数据库未连接'}), 503

        with Session() as session:
            platform = session.query(BusinessPlatform).filter_by(id=id).first()
            if not platform:
                return jsonify({'error': '平台不存在'}), 404

            session.delete(platform)
            session.commit()
            return jsonify({'message': '删除成功'})
    except Exception as e:
        logger.warning(f"删除业务平台失败: {e}")
        return jsonify({'error': '删除失败'}), 500


# ===================== 系统配置（系统名称 / Logo） =====================
# GET 公开：仅用于前端展示品牌，不含敏感信息；POST 需管理员
@app.route('/api/system/config', methods=['GET'])
def get_system_config():
    default = {'system_name': '智慧平台一站通', 'system_logo': ''}
    try:
        if Session is None:
            return jsonify(default)
        with Session() as session:
            rows = session.query(SystemConfig).all()
            cfg = {r.config_key: r.config_value for r in rows}
            result = {
                'system_name': (cfg.get('system_name') or default['system_name']),
                'system_logo': (cfg.get('system_logo') or default['system_logo']),
            }
            # 首次访问补种默认值，保证设置页有可读写数据
            need_seed = []
            if 'system_name' not in cfg:
                need_seed.append(('system_name', default['system_name']))
            if 'system_logo' not in cfg:
                need_seed.append(('system_logo', default['system_logo']))
            if need_seed:
                for k, v in need_seed:
                    session.add(SystemConfig(config_key=k, config_value=v))
                session.commit()
            return jsonify(result)
    except Exception as e:
        logger.warning(f"获取系统配置失败: {e}")
        return jsonify(default)


@app.route('/api/system/config', methods=['POST'])
@admin_required
def update_system_config():
    try:
        data = request.get_json(force=True, silent=True) or {}
        name = (data.get('system_name') or '').strip()
        logo = (data.get('system_logo') or '').strip()
        if not name:
            return jsonify({'error': '系统名称不能为空'}), 400
        if Session is None:
            return jsonify({'error': '数据库未连接'}), 503
        with Session() as session:
            for key, val in (('system_name', name), ('system_logo', logo)):
                row = session.query(SystemConfig).filter_by(config_key=key).first()
                if row:
                    row.config_value = val
                else:
                    session.add(SystemConfig(config_key=key, config_value=val))
            session.commit()
        return jsonify({'system_name': name, 'system_logo': logo, 'message': '保存成功'})
    except Exception as e:
        logger.warning(f"更新系统配置失败: {e}")
        return jsonify({'error': '保存失败'}), 500

# 前端静态文件路由
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
    if not path or not os.path.exists(os.path.join(frontend_dist, path)):
        response = send_from_directory(frontend_dist, 'index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    resp = send_from_directory(frontend_dist, path)
    if '.' in path and any(path.endswith(ext) for ext in ('.js', '.css', '.woff2', '.woff', '.ttf')):
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    else:
        resp.headers['Cache-Control'] = 'no-cache'
    return resp

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', '5000'))
    )
