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
from sqlalchemy import Column, Integer, String, DateTime
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

# 创建会话
Session = sessionmaker(bind=engine)
session = Session()

# 大模型API配置（火山引擎）
API_KEY = '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0'
API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
MODEL = 'doubao-seed-1-8-251228'

@app.route('/api/upload', methods=['POST'])
@protected
def upload_file():
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
            
            return jsonify({'message': 'File uploaded successfully', 'table_name': table_name}), 200
        else:
            return jsonify({'error': 'Only Excel files are allowed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
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
        
        return jsonify({
                'token': token,
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'permissions': permissions
            }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取当前用户信息接口
@app.route('/api/user', methods=['GET'])
@protected
def get_current_user():
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
        
        return jsonify({
            'user_id': request.user_id,
            'username': request.username,
            'role': request.role,
            'permissions': permissions
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 获取所有用户列表接口（管理员专用）
@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
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
        return jsonify({'users': user_list}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 创建用户接口（管理员专用）
@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
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
        return jsonify({'error': str(e)}), 500

# 修改用户接口（管理员专用）
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
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
        return jsonify({'error': str(e)}), 500

# 更新用户权限接口（管理员专用）
@app.route('/api/users/<int:user_id>/permissions', methods=['PUT'])
@admin_required
def update_user_permissions(user_id):
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
        return jsonify({'error': str(e)}), 500

# 删除用户接口（管理员专用）
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/tables', methods=['GET'])
@protected
def get_tables():
    try:
        # 获取数据库中所有表名
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return jsonify({'tables': tables}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 删除数据表接口
@app.route('/api/tables/<table_name>', methods=['DELETE'])
@protected
def delete_table(table_name):
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
        return jsonify({'error': str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)