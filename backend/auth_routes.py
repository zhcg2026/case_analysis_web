# -*- coding: utf-8 -*-
"""认证路由模块 - 用户登录、注册、权限管理"""
from flask import request, jsonify
from sqlalchemy import text
from helpers import (
    protected, admin_required, hash_password, verify_password,
    is_strong_password, check_login_attempts, record_failed_login,
    clear_login_attempts, generate_token, get_json_payload
)

def register_auth_routes(app, Session, User, engine):
    """注册认证相关路由"""
    
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
