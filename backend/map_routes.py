# -*- coding: utf-8 -*-
"""地图与管辖区域路由模块"""
import os
import json
import requests as http_requests
from flask import request, jsonify, Response

try:
    from common import protected as _protected
except ImportError:
    from helpers import protected as _protected

def register_map_routes(app, protected=None):
    """注册地图与管辖区域相关路由"""
    protected = protected or _protected
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
                    logging.warning(f"[Jurisdiction] 读取{info['path']}失败: {e}")
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
            import logging
            logging.exception("Error in check_jurisdiction")
            return jsonify({'error': '管辖范围查询失败'}), 500

    @app.route('/api/wms-proxy', methods=['GET'])
    def wms_proxy():
        """WMS 代理接口，转发 GeoServer WMS 请求以绕过 CORS。

        注意：地图瓦片由 AMap 以 <img> 方式请求，浏览器无法携带 Authorization
        头，因此该接口不做登录鉴权（与线上正常版本一致）。若需限制来源，请通过
        Nginx/网关层按 referer 或 IP 做防护，而非在此加 @protected。
        """
        try:
            wms_url = request.args.get('url', '')
            if not wms_url:
                return jsonify({'error': '缺少 url 参数'}), 400

            # URL 主机白名单：GeoServer 云主机证书为自签，需放行目标域名。
            # 默认含生产 GeoServer 域名；可通过 WMS_ALLOWED_HOSTS 追加。
            from urllib.parse import urlparse
            parsed = urlparse(wms_url)
            default_hosts = 'localhost,127.0.0.1,192.168.101.3,ycfhpl.cloudhw.cn'
            allowed_hosts = os.getenv('WMS_ALLOWED_HOSTS', default_hosts).split(',')
            if parsed.hostname not in allowed_hosts:
                return jsonify({'error': '不允许的目标地址'}), 403

            params = {}
            for key in request.args:
                if key != 'url':
                    params[key] = request.args.get(key)

            # verify=False：目标 GeoServer 使用自签证书，否则 SSL 验证会失败。
            resp = http_requests.get(
                wms_url,
                params=params,
                timeout=30,
                verify=False,
                headers={'User-Agent': 'Mozilla/5.0'}
            )

            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get('Content-Type', 'image/png'),
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Access-Control-Allow-Origin': '*'
                }
            )
        except Exception as e:
            import logging
            logging.exception("WMS proxy error")
            return jsonify({'error': 'WMS 请求失败'}), 500
