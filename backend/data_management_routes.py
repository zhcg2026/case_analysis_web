# -*- coding: utf-8 -*-
"""数据管理路由模块 - 业务平台、数据表管理、配置管理"""
import json
from flask import request, jsonify
from sqlalchemy import text, inspect
from helpers import protected, admin_required

def register_data_management_routes(app, Session, engine, BusinessPlatform, SystemConfig):
    """注册数据管理相关路由"""
    
    # ==================== 业务平台路由 ====================
    
    # 获取所有业务平台
    @app.route('/api/business-platforms', methods=['GET'])
    @protected
    def get_business_platforms():
        # 如果没有数据库连接，返回空列表
        if engine is None:
            return jsonify({'platforms': []}), 200
        
        session = Session()
        try:
            platforms = session.query(BusinessPlatform).all()
            platform_list = []
            for platform in platforms:
                platform_list.append({
                    'id': platform.id,
                    'name': platform.name,
                    'url': platform.url,
                    'image_path': platform.image_path,
                    'created_at': platform.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': platform.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            session.commit()
            return jsonify({'platforms': platform_list}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_business_platforms: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 添加业务平台
    @app.route('/api/business-platforms', methods=['POST'])
    @admin_required
    def add_business_platform():
        # 如果没有数据库连接，返回提示
        if engine is None:
            return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
        
        session = Session()
        try:
            data = request.json
            name = data.get('name')
            url = data.get('url')
            image_path = data.get('image_path')
            
            if not name or not url:
                return jsonify({'error': 'Missing name or url'}), 400
            
            # 检查平台名称是否已存在
            existing_platform = session.query(BusinessPlatform).filter_by(name=name).first()
            if existing_platform:
                return jsonify({'error': 'Platform name already exists'}), 400
            
            # 创建新平台
            new_platform = BusinessPlatform(
                name=name,
                url=url,
                image_path=image_path
            )
            session.add(new_platform)
            session.commit()
            
            return jsonify({
                'id': new_platform.id,
                'name': new_platform.name,
                'url': new_platform.url,
                'image_path': new_platform.image_path
            }), 201
        except Exception as e:
            session.rollback()
            print(f"Error in add_business_platform: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 更新业务平台
    @app.route('/api/business-platforms/<int:platform_id>', methods=['PUT'])
    @admin_required
    def update_business_platform(platform_id):
        # 如果没有数据库连接，返回提示
        if engine is None:
            return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
        
        session = Session()
        try:
            data = request.json
            platform = session.query(BusinessPlatform).filter_by(id=platform_id).first()
            if not platform:
                return jsonify({'error': 'Platform not found'}), 404
            
            # 更新平台信息
            if 'name' in data:
                # 检查新名称是否与其他平台重复
                if data['name'] != platform.name:
                    existing_platform = session.query(BusinessPlatform).filter_by(name=data['name']).first()
                    if existing_platform:
                        return jsonify({'error': 'Platform name already exists'}), 400
                platform.name = data['name']
            if 'url' in data:
                platform.url = data['url']
            if 'image_path' in data:
                platform.image_path = data['image_path']
            
            session.commit()
            
            return jsonify({
                'id': platform.id,
                'name': platform.name,
                'url': platform.url,
                'image_path': platform.image_path
            }), 200
        except Exception as e:
            session.rollback()
            print(f"Error in update_business_platform: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 删除业务平台
    @app.route('/api/business-platforms/<int:platform_id>', methods=['DELETE'])
    @admin_required
    def delete_business_platform(platform_id):
        # 如果没有数据库连接，返回提示
        if engine is None:
            return jsonify({'error': 'Database not connected. Business platform management is disabled.'}), 503
        
        session = Session()
        try:
            platform = session.query(BusinessPlatform).filter_by(id=platform_id).first()
            if not platform:
                return jsonify({'error': 'Platform not found'}), 404
            
            session.delete(platform)
            session.commit()
            
            return jsonify({'message': 'Platform deleted successfully'}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in delete_business_platform: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ==================== 数据表管理路由 ====================
    
    @app.route('/api/tables', methods=['GET'])
    @protected
    def get_tables():
        """获取数据表列表 - 根据可见性配置过滤"""
        # 如果没有数据库连接，返回空列表
        if engine is None:
            return jsonify({'tables': []}), 200

        session = Session()
        try:
            # 获取数据库中所有表名
            inspector = inspect(engine)
            all_tables = inspector.get_table_names()

            # 根据可见性配置过滤
            config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()
            if config and config.config_value:
                visibility = json.loads(config.config_value)
                # 只返回可见的表（visibility[table] !== False）
                tables = [t for t in all_tables if visibility.get(t, True) != False]
            else:
                # 没有配置则全部可见
                tables = all_tables

            session.commit()
            return jsonify({'tables': tables}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_tables: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    @app.route('/api/tables/all', methods=['GET'])
    @admin_required
    def get_all_tables():
        """获取所有数据表列表（仅管理员，用于系统管理页面）"""
        if engine is None:
            return jsonify({'tables': []}), 200

        session = Session()
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            session.commit()
            return jsonify({'tables': tables}), 200
        except Exception as e:
            session.rollback()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 获取数据表中可用的月份列表
    @app.route('/api/available-months', methods=['GET'])
    @protected
    def get_available_months():
        """从指定表中查询已有的月份值"""
        table_name = request.args.get('table_name')
        if not table_name:
            return jsonify({'error': 'Missing table_name parameter'}), 400

        if engine is None:
            return jsonify({'months': []}), 200

        session = Session()
        try:
            # 查询数据表中的月份列
            inspector = inspect(engine)
            columns = inspector.get_columns(table_name)
            column_names = [col['name'] for col in columns]

            # 查找月份列
            month_col = None
            for col in ['月份', 'data_month', 'month']:
                if col in column_names:
                    month_col = col
                    break

            if month_col:
                # 查询所有不同的月份值
                query = text(f"SELECT DISTINCT {month_col} FROM {table_name} WHERE {month_col} IS NOT NULL ORDER BY {month_col} DESC")
                result_proxy = session.execute(query)
                months = [row[0] for row in result_proxy if row[0]]
                session.commit()
                return jsonify({'months': months}), 200
            else:
                session.commit()
                return jsonify({'months': []}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_available_months: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 获取数据表的列名
    @app.route('/api/table-columns', methods=['GET'])
    @protected
    def get_table_columns():
        """获取指定数据表的所有列名"""
        table_name = request.args.get('table_name')
        if not table_name:
            return jsonify({'error': 'Missing table_name parameter'}), 400

        if engine is None:
            return jsonify({'columns': []}), 200

        try:
            inspector = inspect(engine)
            columns = inspector.get_columns(table_name)
            column_names = [col['name'] for col in columns]
            return jsonify({'columns': column_names}), 200
        except Exception as e:
            print(f"Error in get_table_columns: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # 获取数据表某列的唯一值
    @app.route('/api/column-values', methods=['GET'])
    @protected
    def get_column_values():
        """获取指定数据表某列的唯一值"""
        table_name = request.args.get('table_name')
        column = request.args.get('column')

        if not table_name or not column:
            return jsonify({'error': 'Missing parameters'}), 400

        if engine is None:
            return jsonify({'values': []}), 200

        session = Session()
        try:
            # 查询该列的唯一值
            query = text(f"SELECT DISTINCT `{column}` FROM `{table_name}` WHERE `{column}` IS NOT NULL LIMIT 100")
            result = session.execute(query)
            values = [row[0] for row in result.fetchall()]
            return jsonify({'values': values}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_column_values: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 删除数据表接口
    @app.route('/api/tables/<table_name>', methods=['DELETE'])
    @protected
    def delete_table(table_name):
        # 如果没有数据库连接，返回提示
        if engine is None:
            return jsonify({'error': 'Database not connected. Table management is disabled.'}), 503

        session = Session()
        try:
            # 防止删除系统表
            protected_tables = ['users', 'permissions']
            if table_name in protected_tables:
                return jsonify({'error': f'不能删除系统表 {table_name}'}), 403

            # 删除数据表（使用反引号包裹表名，处理外键约束）
            session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
            session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            session.commit()
            return jsonify({'message': f'Table {table_name} deleted successfully'})
        except Exception as e:
            session.rollback()
            print(f"Error in delete_table: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # ==================== 配置管理路由 ====================
    
    # 获取表格可见性配置
    @app.route('/api/config/table-visibility', methods=['GET'])
    @protected
    def get_table_visibility():
        """获取表格可见性配置"""
        if engine is None:
            return jsonify({'config': {}}), 200

        session = Session()
        try:
            config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()
            if config and config.config_value:
                config_data = json.loads(config.config_value)
                return jsonify({'config': config_data}), 200
            else:
                return jsonify({'config': {}}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in get_table_visibility: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # 保存表格可见性配置
    @app.route('/api/config/table-visibility', methods=['POST'])
    @admin_required
    def save_table_visibility():
        """保存表格可见性配置（仅管理员）"""
        if engine is None:
            return jsonify({'error': 'Database not connected. Config management is disabled.'}), 503

        session = Session()
        try:
            data = request.json
            config_value = data.get('config', {})

            # 查找现有配置
            config = session.query(SystemConfig).filter_by(config_key='table_visibility').first()

            if config:
                # 更新现有配置
                config.config_value = json.dumps(config_value)
            else:
                # 创建新配置
                config = SystemConfig(
                    config_key='table_visibility',
                    config_value=json.dumps(config_value)
                )
                session.add(config)

            session.commit()
            return jsonify({'message': '配置保存成功', 'config': config_value}), 200
        except Exception as e:
            session.rollback()
            print(f"Error in save_table_visibility: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
