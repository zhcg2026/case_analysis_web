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

# 菜单级权限列（与前端 menuPermissions.js 一致）
PERMISSION_KEYS = [
    'map', 'knowledge',
    'dispatch', 'dispatch_standards', 'dispatch_query', 'dispatch_special',
    'data_mgmt', 'data_cleaning', 'data_browse', 'data_stats',
    'assessment', 'assessment_input_platform', 'assessment_input_collector', 'assessment_exemption', 'assessment_score',
    'data_analysis', 'case_map',
    'ledger', 'ledger_maintenance', 'ledger_meeting', 'ledger_training', 'ledger_docs',
    'ledger_monitor', 'ledger_drone',
    'duty', 'duty_schedule', 'duty_records',
    'business',
]
PERMISSION_COLUMNS = ', '.join(PERMISSION_KEYS)

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

            perm_values = {key: (1 if key == 'duty_records' else 0) for key in PERMISSION_KEYS}
            # 遗留列显式兜底（cases/huiwentai 等历史表结构无默认值）
            for legacy in ('cases', 'huiwentai', 'spotcheck', 'dashboard', 'data_management', 'flood_monitor'):
                perm_values.setdefault(legacy, 0)
            # 再补齐表中其它 NOT NULL 且无默认值的列，避免 1364
            try:
                with engine.connect() as conn:
                    for col in conn.execute(text("SHOW COLUMNS FROM permissions")).fetchall():
                        # Field, Type, Null, Key, Default, Extra
                        col_name = str(col[0])
                        null_flag = str(col[2] or '').upper()
                        default_val = col[4]
                        if col_name in ('id', 'user_id', 'created_at', 'updated_at'):
                            continue
                        if null_flag == 'NO' and default_val is None and col_name not in perm_values:
                            perm_values[col_name] = 1 if col_name == 'duty_records' else 0
            except Exception:
                logging.exception("Failed to inspect permissions columns for create_user")

            cols = ', '.join(perm_values.keys())
            placeholders = ', '.join([f':{key}' for key in perm_values.keys()])
            session.execute(text(f"INSERT INTO permissions (user_id, {cols}) VALUES (:user_id, {placeholders})"), {
                'user_id': new_user.id,
                **perm_values
            })
            session.commit()

            return jsonify({
                'id': new_user.id,
                'username': new_user.username,
                'role': new_user.role,
                'permissions': {key: (key == 'duty_records') for key in PERMISSION_KEYS}
            }), 201
        except Exception as e:
            session.rollback()
            logging.exception("Error in create_user")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    @app.route('/api/change-password', methods=['POST'])
    @protected
    def change_own_password():
        """登录用户修改自己的密码"""
        if engine is None:
            return jsonify({'error': '数据库未连接，无法修改密码'}), 503

        data = get_json_payload() or request.json or {}
        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or new_password

        if not current_password or not new_password:
            return jsonify({'error': '请填写当前密码与新密码'}), 400
        if new_password != confirm_password:
            return jsonify({'error': '两次输入的新密码不一致'}), 400
        if new_password == current_password:
            return jsonify({'error': '新密码不能与当前密码相同'}), 400

        is_strong, strength_error = is_strong_password(new_password)
        if not is_strong:
            return jsonify({'error': strength_error}), 400

        session = Session()
        try:
            user = session.query(User).filter_by(id=request.user_id).first()
            if not user:
                return jsonify({'error': '用户不存在'}), 404
            if not verify_password(current_password, user.password):
                return jsonify({'error': '当前密码不正确'}), 400
            user.password = hash_password(new_password)
            session.commit()
            return jsonify({'message': '密码修改成功', 'success': True}), 200
        except Exception:
            session.rollback()
            logging.exception("Error in change_own_password")
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
                **{key: (1 if data.get(key) else 0) for key in PERMISSION_KEYS}
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
