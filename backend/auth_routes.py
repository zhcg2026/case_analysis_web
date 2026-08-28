# -*- coding: utf-8 -*-
"""认证路由模块 - 用户登录、注册、权限管理"""
from flask import request, jsonify
from sqlalchemy import text
import logging
from helpers import (
    protected, admin_required, hash_password, verify_password,
    is_strong_password, check_login_attempts, record_failed_login,
    clear_login_attempts, generate_token, get_json_payload
)

# 当前保留的权限列
PERMISSION_COLUMNS = 'data_analysis, knowledge, map, case_map, dispatch, business, ledger, assessment, data_cleaning'
PERMISSION_KEYS = ['data_analysis', 'knowledge', 'map', 'case_map', 'dispatch', 'business', 'ledger', 'assessment', 'data_cleaning']

def register_auth_routes(app, Session, User, engine):
    """注册认证相关路由"""
    
    @app.route('/api/login', methods=['POST'])
    def login():
        if engine is None:
            return jsonify({'error': '数据库未连接，请检查配置'}), 503

        session = Session()
        try:
            data = request.json
            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return jsonify({'error': 'Missing username or password'}), 400

            allowed, lock_msg = check_login_attempts(username)
            if not allowed:
                return jsonify({'error': lock_msg}), 429

            user = session.query(User).filter_by(username=username).first()
            if not user:
                record_failed_login(username)
                return jsonify({'error': 'Invalid username or password'}), 401

            if not verify_password(password, user.password):
                record_failed_login(username)
                return jsonify({'error': 'Invalid username or password'}), 401

            clear_login_attempts(username)
            token = generate_token(user.id, user.username, user.role)

            permission = session.execute(text(f"SELECT {PERMISSION_COLUMNS} FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
            permissions = {key: False for key in PERMISSION_KEYS}
            if permission:
                for i, key in enumerate(PERMISSION_KEYS):
                    permissions[key] = permission[i]

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
            logging.exception("Error in login")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/verify-token', methods=['GET'])
    @protected
    def verify_token_endpoint():
        return jsonify({'valid': True}), 200

    @app.route('/api/user', methods=['GET'])
    @protected
    def get_current_user():
        if engine is None:
            permissions = {key: True for key in PERMISSION_KEYS}
            return jsonify({
                'user_id': request.user_id,
                'username': request.username,
                'role': request.role,
                'permissions': permissions
            }), 200

        session = Session()
        try:
            permission = session.execute(text(f"SELECT {PERMISSION_COLUMNS} FROM permissions WHERE user_id = :user_id"), {'user_id': request.user_id}).fetchone()
            permissions = {key: False for key in PERMISSION_KEYS}
            if permission:
                for i, key in enumerate(PERMISSION_KEYS):
                    permissions[key] = permission[i]
            
            session.commit()
            return jsonify({
                'user_id': request.user_id,
                'username': request.username,
                'role': request.role,
                'permissions': permissions
            }), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in get_current_user")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/users', methods=['GET'])
    @admin_required
    def get_users():
        if engine is None:
            permissions = {key: True for key in PERMISSION_KEYS}
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
                permission = session.execute(text(f"SELECT {PERMISSION_COLUMNS} FROM permissions WHERE user_id = :user_id"), {'user_id': user.id}).fetchone()
                permissions = {key: False for key in PERMISSION_KEYS}
                if permission:
                    for i, key in enumerate(PERMISSION_KEYS):
                        permissions[key] = permission[i]
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
            logging.exception("Error in get_users")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/users', methods=['POST'])
    @admin_required
    def create_user():
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

            is_strong, strength_error = is_strong_password(password)
            if not is_strong:
                return jsonify({'error': strength_error}), 400

            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                return jsonify({'error': 'Username already exists'}), 400

            hashed_password = hash_password(password)
            new_user = User(
                username=username,
                password=hashed_password,
                role=role
            )
            session.add(new_user)
            session.flush()
            
            cols = ', '.join(PERMISSION_KEYS)
            placeholders = ', '.join([f':{key}' for key in PERMISSION_KEYS])
            session.execute(text(f"INSERT INTO permissions (user_id, {cols}) VALUES (:user_id, {placeholders})"), {
                'user_id': new_user.id,
                **{key: False for key in PERMISSION_KEYS}
            })
            session.commit()

            return jsonify({
                'id': new_user.id,
                'username': new_user.username,
                'role': new_user.role,
                'permissions': {key: False for key in PERMISSION_KEYS}
            }), 201
        except Exception as e:
            session.rollback()
            logging.exception("Error in create_user")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    @admin_required
    def update_user(user_id):
        if engine is None:
            return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
        
        session = Session()
        try:
            data = request.json
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if 'username' in data:
                user.username = data['username']
            if 'password' in data:
                new_password = data['password']
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
            logging.exception("Error in update_user")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/users/<int:user_id>/permissions', methods=['PUT'])
    @admin_required
    def update_user_permissions(user_id):
        if engine is None:
            return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
        
        session = Session()
        try:
            data = request.json
            
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            set_clause = ', '.join([f'{key} = :{key}' for key in PERMISSION_KEYS])
            session.execute(text(f"UPDATE permissions SET {set_clause} WHERE user_id = :user_id"), {
                'user_id': user_id,
                **{key: data.get(key, False) for key in PERMISSION_KEYS}
            })
            session.commit()

            permission = session.execute(text(f"SELECT {PERMISSION_COLUMNS} FROM permissions WHERE user_id = :user_id"), {'user_id': user_id}).fetchone()
            permissions = {key: False for key in PERMISSION_KEYS}
            if permission:
                for i, key in enumerate(PERMISSION_KEYS):
                    permissions[key] = permission[i]
            
            return jsonify({
                'user_id': user_id,
                'permissions': permissions
            }), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in update_user_permissions")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    @admin_required
    def delete_user(user_id):
        if engine is None:
            return jsonify({'error': 'Database not connected. User management is disabled.'}), 503
        
        session = Session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if user.role == 'admin' and user_id == 1:
                return jsonify({'error': 'Cannot delete admin user'}), 400
            
            session.delete(user)
            session.commit()
            
            return jsonify({'message': 'User deleted successfully'}), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in delete_user")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()
