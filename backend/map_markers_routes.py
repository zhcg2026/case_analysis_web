# -*- coding: utf-8 -*-
"""地图标记点管理路由模块 - 将标记点数据存储到服务器数据库"""
import logging
from flask import request, jsonify
from datetime import datetime

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required

logger = logging.getLogger(__name__)


def register_map_markers_routes(app, protected=None, admin_required=None, Session=None):
    """注册地图标记点管理路由"""
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    @app.route('/api/map-markers', methods=['GET'])
    @protected
    def get_map_markers():
        """获取所有标记点（支持按分类过滤）"""
        try:
            if Session is None:
                return jsonify({'markers': []})

            category = request.args.get('category')
            subcategory = request.args.get('subcategory')

            with Session() as session:
                from sqlalchemy import text
                query = "SELECT id, category, subcategory, name, description, longitude, latitude, images, created_at FROM map_markers"
                params = {}

                if category:
                    query += " WHERE category = :category"
                    params['category'] = category
                elif subcategory:
                    query += " WHERE subcategory = :subcategory"
                    params['subcategory'] = subcategory

                query += " ORDER BY created_at DESC"

                result = session.execute(text(query), params).fetchall()

                markers = []
                for row in result:
                    markers.append({
                        'id': row[0],
                        'category': row[1],
                        'subcategory': row[2],
                        'name': row[3],
                        'description': row[4] or '',
                        'longitude': float(row[5]) if row[5] else None,
                        'latitude': float(row[6]) if row[6] else None,
                        'images': row[7] or '',
                        'created_at': row[8].strftime('%Y-%m-%d %H:%M:%S') if row[8] else None
                    })

                return jsonify({'markers': markers})

        except Exception as e:
            logger.warning(f"获取标记点失败: {e}")
            return jsonify({'error': '获取失败'}), 500

    @app.route('/api/map-markers', methods=['POST'])
    @admin_required
    def create_map_marker():
        """新增标记点"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': '请提供数据'}), 400

            required_fields = ['category', 'subcategory', 'name', 'longitude', 'latitude']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field} 不能为空'}), 400

            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503

            with Session() as session:
                from sqlalchemy import text
                # 检查是否已存在同名标记
                existing = session.execute(
                    text("SELECT id FROM map_markers WHERE name = :name AND subcategory = :subcategory"),
                    {'name': data['name'], 'subcategory': data['subcategory']}
                ).fetchone()
                if existing:
                    return jsonify({'error': '该名称的标记点已存在'}), 400

                # 插入新记录
                result = session.execute(
                    text("""INSERT INTO map_markers
                        (category, subcategory, name, description, longitude, latitude, images, created_at)
                        VALUES (:category, :subcategory, :name, :description, :longitude, :latitude, :images, NOW())"""),
                    {
                        'category': data['category'],
                        'subcategory': data['subcategory'],
                        'name': data['name'],
                        'description': data.get('description', ''),
                        'longitude': float(data['longitude']),
                        'latitude': float(data['latitude']),
                        'images': data.get('images', '')
                    }
                )
                session.commit()
                marker_id = result.lastrowid

                return jsonify({
                    'id': marker_id,
                    'message': '创建成功'
                }), 201

        except Exception as e:
            logger.warning(f"创建标记点失败: {e}")
            return jsonify({'error': '创建失败'}), 500

    @app.route('/api/map-markers/<int:marker_id>', methods=['PUT'])
    @admin_required
    def update_map_marker(marker_id):
        """更新标记点"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': '请提供数据'}), 400

            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503

            with Session() as session:
                from sqlalchemy import text
                # 检查是否存在
                existing = session.execute(
                    text("SELECT id FROM map_markers WHERE id = :id"),
                    {'id': marker_id}
                ).fetchone()
                if not existing:
                    return jsonify({'error': '标记点不存在'}), 404

                # 构建更新语句
                updates = []
                params = {'id': marker_id}

                if 'name' in data:
                    updates.append("name = :name")
                    params['name'] = data['name']
                if 'description' in data:
                    updates.append("description = :description")
                    params['description'] = data['description']
                if 'longitude' in data:
                    updates.append("longitude = :longitude")
                    params['longitude'] = float(data['longitude'])
                if 'latitude' in data:
                    updates.append("latitude = :latitude")
                    params['latitude'] = float(data['latitude'])
                if 'images' in data:
                    updates.append("images = :images")
                    params['images'] = data['images']
                if 'category' in data:
                    updates.append("category = :category")
                    params['category'] = data['category']
                if 'subcategory' in data:
                    updates.append("subcategory = :subcategory")
                    params['subcategory'] = data['subcategory']

                if updates:
                    updates.append("updated_at = NOW()")
                    query = f"UPDATE map_markers SET {', '.join(updates)} WHERE id = :id"
                    session.execute(text(query), params)
                    session.commit()

                return jsonify({'message': '更新成功'})

        except Exception as e:
            logger.warning(f"更新标记点失败: {e}")
            return jsonify({'error': '更新失败'}), 500

    @app.route('/api/map-markers/<int:marker_id>', methods=['DELETE'])
    @admin_required
    def delete_map_marker(marker_id):
        """删除标记点"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503

            with Session() as session:
                from sqlalchemy import text
                # 检查是否存在
                existing = session.execute(
                    text("SELECT id FROM map_markers WHERE id = :id"),
                    {'id': marker_id}
                ).fetchone()
                if not existing:
                    return jsonify({'error': '标记点不存在'}), 404

                session.execute(text("DELETE FROM map_markers WHERE id = :id"), {'id': marker_id})
                session.commit()

                return jsonify({'message': '删除成功'})

        except Exception as e:
            logger.warning(f"删除标记点失败: {e}")
            return jsonify({'error': '删除失败'}), 500

    @app.route('/api/map-markers/batch', methods=['POST'])
    @admin_required
    def batch_create_map_markers():
        """批量导入标记点"""
        try:
            data = request.get_json()
            if not data or 'markers' not in data:
                return jsonify({'error': '请提供标记点列表'}), 400

            markers = data['markers']
            if not isinstance(markers, list) or len(markers) == 0:
                return jsonify({'error': '标记点列表不能为空'}), 400

            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503

            with Session() as session:
                from sqlalchemy import text
                count = 0
                errors = []

                for idx, marker in enumerate(markers):
                    try:
                        required_fields = ['category', 'subcategory', 'name', 'longitude', 'latitude']
                        for field in required_fields:
                            if not marker.get(field):
                                errors.append(f"第{idx+1}个标记点缺少必填字段: {field}")
                                continue

                        # 检查是否已存在
                        existing = session.execute(
                            text("SELECT id FROM map_markers WHERE name = :name AND subcategory = :subcategory"),
                            {'name': marker['name'], 'subcategory': marker['subcategory']}
                        ).fetchone()
                        if existing:
                            errors.append(f"第{idx+1}个标记点已存在: {marker['name']}")
                            continue

                        session.execute(
                            text("""INSERT INTO map_markers
                                (category, subcategory, name, description, longitude, latitude, images, created_at)
                                VALUES (:category, :subcategory, :name, :description, :longitude, :latitude, :images, NOW())"""),
                            {
                                'category': marker['category'],
                                'subcategory': marker['subcategory'],
                                'name': marker['name'],
                                'description': marker.get('description', ''),
                                'longitude': float(marker['longitude']),
                                'latitude': float(marker['latitude']),
                                'images': marker.get('images', '')
                            }
                        )
                        count += 1
                    except Exception as e:
                        errors.append(f"第{idx+1}个标记点导入失败: {str(e)}")

                session.commit()

                return jsonify({
                    'success_count': count,
                    'total': len(markers),
                    'errors': errors,
                    'message': f'成功导入 {count} 个标记点'
                })

        except Exception as e:
            logger.warning(f"批量导入标记点失败: {e}")
            return jsonify({'error': '批量导入失败'}), 500
