# -*- coding: utf-8 -*-
"""地图与管辖区域路由模块"""
import os
import json
from flask import request, jsonify

def register_map_routes(app, protected):
    """注册地图与管辖区域相关路由"""

    @app.route('/api/jurisdiction/check', methods=['POST'])
    @protected
    def check_jurisdiction():
        """根据坐标判断管辖范围和责任部门"""
        try:
            data = request.get_json()
            lng = data.get('lng')
            lat = data.get('lat')

            if lng is None or lat is None:
                return jsonify({'error': '请提供经纬度坐标'}), 400

            def point_in_polygon(x, y, polygon):
                """射线法判断点是否在多边形内"""
                n = len(polygon)
                inside = False
                j = n - 1
                for i in range(n):
                    xi, yi = polygon[i]
                    xj, yj = polygon[j]
                    if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                        inside = not inside
                    j = i
                return inside

            def extract_coords(geometry):
                """从GeoJSON几何体提取坐标"""
                geom_type = geometry.get('type', '')
                coords = geometry.get('coordinates', [])
                if geom_type == 'Polygon':
                    return coords[0] if coords else []
                elif geom_type == 'MultiPolygon':
                    return coords[0][0] if coords and coords[0] else []
                return []

            point_lng = float(lng)
            point_lat = float(lat)

            geojson_files = {
                'huanwei': {'path': '/app/frontend/dist/data/guanxia.geojson', 'dept': '市容环卫中心', 'category': '环卫'},
                'yuanlin': {'path': '/app/frontend/dist/data/园林片区.geojson', 'dept': '园林绿化服务中心', 'category': '园林'},
            }

            matched = []

            for key, info in geojson_files.items():
                try:
                    with open(info['path'], 'r', encoding='utf-8') as f:
                        geojson = json.load(f)

                    for feature in geojson.get('features', []):
                        coords = extract_coords(feature['geometry'])
                        if coords and point_in_polygon(point_lng, point_lat, coords):
                            props = feature.get('properties', {})
                            name = props.get('name') or props.get('zone_name') or info['category']
                            matched.append({
                                'category': info['category'],
                                'department': info['dept'],
                                'area_name': name,
                                'properties': props
                            })
                except Exception as e:
                    print(f"[Jurisdiction] 读取{info['path']}失败: {e}")

            if matched:
                return jsonify({
                    'matched': True,
                    'jurisdictions': matched,
                    'message': f"该位置属于{'、'.join(m['area_name'] for m in matched)}管辖范围"
                }), 200
            else:
                return jsonify({
                    'matched': False,
                    'jurisdictions': [],
                    'message': '该位置未匹配到我局管辖范围，可能属于外单位（如街办）管辖'
                }), 200

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
