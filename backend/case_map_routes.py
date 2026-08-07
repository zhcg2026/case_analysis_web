# -*- coding: utf-8 -*-
"""案件地图可视化 API — 提供案件点数据、热力图聚合、分类列表、统计摘要"""

from flask import request, jsonify
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# 大类颜色映射
CATEGORY_COLORS = {
    '市容环境': '#e74c3c',
    '宣传广告': '#e67e22',
    '施工管理': '#f1c40f',
    '街面秩序': '#2ecc71',
    '突发事件': '#9b59b6',
    '其他': '#3498db',
}


def _get_color(category):
    return CATEGORY_COLORS.get(category, '#3498db')


def register_case_map_routes(app, engine=None, protected=None):
    """注册案件地图路由"""
    if protected is None:
        from helpers import protected as _protected
        protected = _protected

    @app.route('/api/case-map/categories', methods=['GET'])
    @protected
    def case_map_categories():
        """获取大类/小类列表及数量"""
        try:
            batch = request.args.get('batch', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')

            conditions = []
            params = {}

            if batch:
                batches = [b.strip() for b in batch.split(',') if b.strip()]
                if batches:
                    placeholders = ','.join([f':b{i}' for i in range(len(batches))])
                    for i, v in enumerate(batches):
                        params[f'b{i}'] = v
                    conditions.append(f"upload_batch IN ({placeholders})")

            if start_date:
                conditions.append("report_time >= :start_date")
                params['start_date'] = start_date
            if end_date:
                conditions.append("report_time <= :end_date")
                params['end_date'] = end_date + ' 23:59:59' if len(end_date) == 10 else end_date

            if not conditions:
                return jsonify({'success': False, 'error': '至少需要一个筛选条件'}), 400

            where_clause = ' AND '.join(conditions)

            with engine.connect() as conn:
                sql = text(f"""
                    SELECT big_category, small_category, COUNT(*) as cnt
                    FROM case_data
                    WHERE {where_clause}
                    GROUP BY big_category, small_category
                    ORDER BY big_category, cnt DESC
                """)
                result = conn.execute(sql, params)
                rows = result.fetchall()

            # 聚合为大类结构
            categories_map = {}
            for row in rows:
                big = row[0] or '其他'
                small = row[1] or '未知'
                cnt = row[2]
                if big not in categories_map:
                    categories_map[big] = {
                        'big_category': big,
                        'color': _get_color(big),
                        'small_categories': [],
                        'total': 0
                    }
                categories_map[big]['small_categories'].append({
                    'name': small,
                    'count': cnt
                })
                categories_map[big]['total'] += cnt

            return jsonify({
                'success': True,
                'categories': list(categories_map.values())
            })
        except Exception as e:
            logger.error(f"获取分类列表失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/case-map/points', methods=['GET'])
    @protected
    def case_map_points():
        """获取案件点数据（分页+视口过滤）"""
        try:
            batch = request.args.get('batch', '')
            if not batch:
                return jsonify({'success': False, 'error': 'batch参数必填'}), 400

            batches = [b.strip() for b in batch.split(',') if b.strip()]
            big_category = request.args.get('big_category', '')
            small_category = request.args.get('small_category', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            lng_min = request.args.get('lng_min', type=float)
            lng_max = request.args.get('lng_max', type=float)
            lat_min = request.args.get('lat_min', type=float)
            lat_max = request.args.get('lat_max', type=float)
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 2000, type=int), 5000)

            conditions = ["longitude IS NOT NULL", "latitude IS NOT NULL"]
            params = {}

            batch_placeholders = ','.join([f':b{i}' for i in range(len(batches))])
            conditions.append(f"upload_batch IN ({batch_placeholders})")
            for i, v in enumerate(batches):
                params[f'b{i}'] = v

            if big_category:
                conditions.append("big_category = :big_category")
                params['big_category'] = big_category
            if small_category:
                conditions.append("small_category = :small_category")
                params['small_category'] = small_category
            if start_date:
                conditions.append("report_time >= :start_date")
                params['start_date'] = start_date
            if end_date:
                conditions.append("report_time <= :end_date")
                params['end_date'] = end_date + ' 23:59:59' if len(end_date) == 10 else end_date
            if lng_min is not None and lng_max is not None:
                conditions.append("longitude BETWEEN :lng_min AND :lng_max")
                params['lng_min'] = lng_min
                params['lng_max'] = lng_max
            if lat_min is not None and lat_max is not None:
                conditions.append("latitude BETWEEN :lat_min AND :lat_max")
                params['lat_min'] = lat_min
                params['lat_max'] = lat_max

            where_clause = ' AND '.join(conditions)
            offset = (page - 1) * per_page

            with engine.connect() as conn:
                # 总数
                count_sql = text(f"SELECT COUNT(*) FROM case_data WHERE {where_clause}")
                total = conn.execute(count_sql, params).scalar()

                # 数据
                data_sql = text(f"""
                    SELECT id, longitude, latitude, big_category, small_category,
                           report_time, description, address, department, stage,
                           is_delayed, is_rework, task_no, district, street, community, source
                    FROM case_data
                    WHERE {where_clause}
                    ORDER BY report_time DESC
                    LIMIT :limit OFFSET :offset
                """)
                params['limit'] = per_page
                params['offset'] = offset
                result = conn.execute(data_sql, params)
                rows = result.fetchall()

            points = []
            for row in rows:
                points.append({
                    'id': row[0],
                    'lng': float(row[1]) if row[1] else None,
                    'lat': float(row[2]) if row[2] else None,
                    'big_category': row[3] or '',
                    'small_category': row[4] or '',
                    'report_time': str(row[5]) if row[5] else '',
                    'description': row[6] or '',
                    'address': row[7] or '',
                    'department': row[8] or '',
                    'stage': row[9] or '',
                    'is_delayed': bool(row[10]),
                    'is_rework': bool(row[11]),
                    'task_no': row[12] or '',
                    'district': row[13] or '',
                    'street': row[14] or '',
                    'community': row[15] or '',
                    'source': row[16] or '',
                })

            return jsonify({
                'success': True,
                'total': total,
                'page': page,
                'per_page': per_page,
                'points': points
            })
        except Exception as e:
            logger.error(f"获取案件点数据失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/case-map/heatmap', methods=['GET'])
    @protected
    def case_map_heatmap():
        """获取热力图网格聚合数据"""
        try:
            batch = request.args.get('batch', '')
            if not batch:
                return jsonify({'success': False, 'error': 'batch参数必填'}), 400

            batches = [b.strip() for b in batch.split(',') if b.strip()]
            big_category = request.args.get('big_category', '')
            small_category = request.args.get('small_category', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            grid_size = request.args.get('grid_size', 0.005, type=float)

            conditions = ["longitude IS NOT NULL", "latitude IS NOT NULL"]
            params = {}

            batch_placeholders = ','.join([f':b{i}' for i in range(len(batches))])
            conditions.append(f"upload_batch IN ({batch_placeholders})")
            for i, v in enumerate(batches):
                params[f'b{i}'] = v

            if big_category:
                conditions.append("big_category = :big_category")
                params['big_category'] = big_category
            if small_category:
                conditions.append("small_category = :small_category")
                params['small_category'] = small_category
            if start_date:
                conditions.append("report_time >= :start_date")
                params['start_date'] = start_date
            if end_date:
                conditions.append("report_time <= :end_date")
                params['end_date'] = end_date + ' 23:59:59' if len(end_date) == 10 else end_date

            where_clause = ' AND '.join(conditions)

            with engine.connect() as conn:
                sql = text(f"""
                    SELECT
                        AVG(longitude) AS lng,
                        AVG(latitude) AS lat,
                        COUNT(*) AS cnt
                    FROM case_data
                    WHERE {where_clause}
                    GROUP BY ROUND(longitude / :grid_size), ROUND(latitude / :grid_size)
                """)
                params['grid_size'] = grid_size
                result = conn.execute(sql, params)
                rows = result.fetchall()

            data = []
            max_count = 0
            for row in rows:
                cnt = row[2]
                if cnt > max_count:
                    max_count = cnt
                data.append({
                    'lng': float(row[0]),
                    'lat': float(row[1]),
                    'count': cnt
                })

            # 计算权重 (0-1)
            for d in data:
                d['weight'] = round(d['count'] / max_count, 4) if max_count > 0 else 0

            return jsonify({
                'success': True,
                'data': data,
                'max_count': max_count
            })
        except Exception as e:
            logger.error(f"获取热力图数据失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/case-map/stats', methods=['GET'])
    @protected
    def case_map_stats():
        """获取统计摘要"""
        try:
            batch = request.args.get('batch', '')
            big_category = request.args.get('big_category', '')
            small_category = request.args.get('small_category', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')

            conditions = []
            params = {}

            if batch:
                batches = [b.strip() for b in batch.split(',') if b.strip()]
                batch_placeholders = ','.join([f':b{i}' for i in range(len(batches))])
                for i, v in enumerate(batches):
                    params[f'b{i}'] = v
                conditions.append(f"upload_batch IN ({batch_placeholders})")

            if big_category:
                conditions.append("big_category = :big_category")
                params['big_category'] = big_category
            if small_category:
                conditions.append("small_category = :small_category")
                params['small_category'] = small_category
            if start_date:
                conditions.append("report_time >= :start_date")
                params['start_date'] = start_date
            if end_date:
                conditions.append("report_time <= :end_date")
                params['end_date'] = end_date + ' 23:59:59' if len(end_date) == 10 else end_date

            if not conditions:
                return jsonify({'success': False, 'error': '至少需要一个筛选条件'}), 400

            where_clause = ' AND '.join(conditions)

            with engine.connect() as conn:
                total_sql = text(f"""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN longitude IS NOT NULL AND latitude IS NOT NULL THEN 1 ELSE 0 END) AS with_coords,
                        MIN(report_time) AS min_time,
                        MAX(report_time) AS max_time,
                        SUM(CASE WHEN is_delayed=1 THEN 1 ELSE 0 END) AS `delayed`,
                        SUM(CASE WHEN is_rework=1 THEN 1 ELSE 0 END) AS `rework`
                    FROM case_data
                    WHERE {where_clause}
                """)
                row = conn.execute(total_sql, params).fetchone()

                cat_sql = text(f"""
                    SELECT big_category, COUNT(*) as cnt
                    FROM case_data
                    WHERE {where_clause}
                    GROUP BY big_category
                    ORDER BY cnt DESC
                """)
                cat_rows = conn.execute(cat_sql, params).fetchall()

                stage_sql = text(f"""
                    SELECT stage, COUNT(*) as cnt
                    FROM case_data
                    WHERE {where_clause}
                    GROUP BY stage
                    ORDER BY cnt DESC
                """)
                stage_rows = conn.execute(stage_sql, params).fetchall()

            by_category = {r[0] or '其他': r[1] for r in cat_rows}
            by_stage = {r[0] or '未知': r[1] for r in stage_rows}

            total = row[0] or 0
            closed_count = by_stage.get('[办结]', 0)
            completion_rate = round(closed_count / total * 100, 1) if total > 0 else 0

            return jsonify({
                'success': True,
                'total_cases': total,
                'with_coordinates': row[1],
                'date_range': {
                    'min': str(row[2]) if row[2] else '',
                    'max': str(row[3]) if row[3] else ''
                },
                'delayed_count': row[4],
                'rework_count': row[5],
                'completion_rate': completion_rate,
                'by_big_category': by_category,
                'by_stage': by_stage
            })
        except Exception as e:
            logger.error(f"获取统计摘要失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
