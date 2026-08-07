# -*- coding: utf-8 -*-
"""
dispatch_engine.py —— 案件归属判断引擎
========================================
核心流程：案件类型 → 查立结案标准责任主体 → 映射部门 → 坐标辖区比对 → 返回具体处置单位

复用模块：
  - kb_dispatch：几何判定（点面/点线）、部门关键词分类
  - kb_store：语义检索（召回立结案标准中的责任主体）

新增：
  - 案件类型→部门映射表（解决立结案标准责任主体名称与GeoJSON部门标识的对应关系）
  - 案件类型列表接口数据
"""
import logging
from typing import Dict, Any, Optional, List

from kb_dispatch import (
    match_department_dispatch,
    _classify_department,
    _extract_location_point,
    _load_department_geojson,
    _point_in_polygon,
    _point_near_line_m,
    DEPARTMENT_GEO_RULES,
    DEPARTMENT_KEYWORDS,
)

logger = logging.getLogger(__name__)


# ------------------------- 案件类型→部门映射表 -------------------------
# 立结案标准中的"责任主体"名称 → kb_dispatch 中的部门标识
# 解决两套命名不一致的问题

RESPONSIBLE_BODY_TO_DEPT = {
    "市容环卫中心": "市容环卫中心",
    "市容环卫": "市容环卫中心",
    "环卫中心": "市容环卫中心",
    "环卫": "市容环卫中心",
    "园林绿化中心": "园林绿化中心",
    "园林绿化": "园林绿化中心",
    "园林中心": "园林绿化中心",
    "园林": "园林绿化中心",
    "综合行政执法队": "综合行政执法队",
    "综合执法队": "综合行政执法队",
    "执法队": "综合行政执法队",
    "城管执法": "综合行政执法队",
    "市政公用服务中心": "市政公用服务中心",
    "市政公用": "市政公用服务中心",
    "市政中心": "市政公用服务中心",
    "市政": "市政公用服务中心",
    "排水服务中心": "排水服务中心",
    "排水中心": "排水服务中心",
    "排水": "排水服务中心",
    "节水服务中心": "节水服务中心",
    "节水中心": "节水服务中心",
    "节水": "节水服务中心",
    "供热供气服务中心": "供热供气服务中心",
    "供热供气": "供热供气服务中心",
    "供热中心": "供热供气服务中心",
    "供气中心": "供热供气服务中心",
    "供热": "供热供气服务中心",
    "供气": "供热供气服务中心",
    "建筑资源化服务中心": "建筑资源化服务中心",
    "建筑资源化": "建筑资源化服务中心",
    "资源化中心": "建筑资源化服务中心",
}


# 案件大类→典型部门映射（用于案件类型选择时的快速归类）
CASE_CATEGORY_DEPT = {
    "市容环卫": "市容环卫中心",
    "园林绿化": "园林绿化中心",
    "综合执法": "综合行政执法队",
    "市政公用": "市政公用服务中心",
    "排水管理": "排水服务中心",
    "节水管理": "节水服务中心",
    "供热供气": "供热供气服务中心",
    "建筑垃圾": "建筑资源化服务中心",
}


# 案件类型列表（前端下拉选择用）
CASE_TYPES = [
    {"id": "road_sweeping", "name": "道路清扫保洁", "category": "市容环卫", "department": "市容环卫中心"},
    {"id": "garbage_clearing", "name": "垃圾清运", "category": "市容环卫", "department": "市容环卫中心"},
    {"id": "road_spillage", "name": "道路遗撒/抛洒", "category": "市容环卫", "department": "市容环卫中心"},
    {"id": "sanitation_dirt", "name": "路面脏污/不洁", "category": "市容环卫", "department": "市容环卫中心"},
    {"id": "fruit_bin", "name": "果皮箱问题", "category": "市容环卫", "department": "市容环卫中心"},
    {"id": "tree_issue", "name": "树木/行道树问题", "category": "园林绿化", "department": "园林绿化中心"},
    {"id": "greenbelt", "name": "绿化带问题", "category": "园林绿化", "department": "园林绿化中心"},
    {"id": "park_issue", "name": "公园问题", "category": "园林绿化", "department": "园林绿化中心"},
    {"id": "illegal_construction", "name": "违法建设", "category": "综合执法", "department": "综合行政执法队"},
    {"id": "street_vending", "name": "占道经营/无照商贩", "category": "综合执法", "department": "综合行政执法队"},
    {"id": "signage", "name": "门头牌匾/广告牌", "category": "综合执法", "department": "综合行政执法队"},
    {"id": "road_damage", "name": "道路/路面损坏", "category": "市政公用", "department": "市政公用服务中心"},
    {"id": "streetlight", "name": "路灯/照明问题", "category": "市政公用", "department": "市政公用服务中心"},
    {"id": "manhole", "name": "井盖问题", "category": "市政公用", "department": "市政公用服务中心"},
    {"id": "guardrail", "name": "护栏/交通设施", "category": "市政公用", "department": "市政公用服务中心"},
    {"id": "drainage", "name": "排水/积水问题", "category": "排水管理", "department": "排水服务中心"},
    {"id": "sewage", "name": "污水/管网问题", "category": "排水管理", "department": "排水服务中心"},
    {"id": "water_leak", "name": "漏水/节水问题", "category": "节水管理", "department": "节水服务中心"},
    {"id": "heating", "name": "供热/暖气问题", "category": "供热供气", "department": "供热供气服务中心"},
    {"id": "gas", "name": "燃气/供气问题", "category": "供热供气", "department": "供热供气服务中心"},
    {"id": "construction_waste", "name": "建筑垃圾/装修垃圾", "category": "建筑垃圾", "department": "建筑资源化服务中心"},
]


def get_case_types() -> List[Dict[str, str]]:
    """返回案件类型列表（供前端下拉选择）"""
    return CASE_TYPES


def get_case_categories() -> List[Dict[str, str]]:
    """返回案件大类列表"""
    return [{"name": k, "department": v} for k, v in CASE_CATEGORY_DEPT.items()]


def resolve_department(responsible_body: str) -> Optional[str]:
    """将立结案标准中的责任主体名称映射为统一部门标识"""
    if not responsible_body:
        return None
    body = responsible_body.strip()
    if body in RESPONSIBLE_BODY_TO_DEPT:
        return RESPONSIBLE_BODY_TO_DEPT[body]
    # 模糊匹配：责任主体包含部门名
    for key, dept in RESPONSIBLE_BODY_TO_DEPT.items():
        if key in body or body in key:
            return dept
    return None


def dispatch(case_type_id: str = None,
             question: str = None,
             location: Any = None) -> Dict[str, Any]:
    """
    归属判断主入口

    参数：
      case_type_id: 案件类型ID（可选，来自前端下拉选择）
      question: 自然语言问题描述（可选）
      location: 坐标信息，支持 {"lat":..., "lng":...} 或 [lat, lng] 格式

    返回：
      {
        "success": bool,
        "department": str | None,     # 归属部门
        "unit": str | None,           # 具体处置单位（片区/分队）
        "in_jurisdiction": bool,      # 是否在管辖范围内
        "case_type": dict | None,     # 匹配到的案件类型信息
        "layer_status": str,          # 图层状态
        "answer": str,                # 归属结论文字
      }
    """
    # 1. 确定部门
    department = None
    case_type_info = None

    if case_type_id:
        case_type_info = next((ct for ct in CASE_TYPES if ct["id"] == case_type_id), None)
        if case_type_info:
            department = case_type_info["department"]

    if not department and question:
        department = _classify_department(question)

    if not department:
        return {
            "success": True,
            "department": None,
            "unit": None,
            "in_jurisdiction": False,
            "case_type": case_type_info,
            "layer_status": "unknown_department",
            "answer": "未能识别处置部门，请选择案件类型或补充更具体的问题描述。",
        }

    # 2. 无坐标时返回部门级结果
    point = _extract_location_point(location) if location else None
    if not point:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "case_type": case_type_info,
            "layer_status": "no_location",
            "answer": f"该问题由{department}负责。请在地图上点选具体位置，以精确判断管辖片区。",
        }

    # 3. 有坐标时，复用 kb_dispatch 的几何判定逻辑
    # 构造一个虚拟问题来触发派单（force_dispatch=True 跳过意图检测）
    dispatch_result = match_department_dispatch(
        question=question or case_type_info.get("name", "") if case_type_info else department,
        location=location,
        force_dispatch=True,
    )

    if dispatch_result and dispatch_result.get("department") == department:
        # 派单结果与预期部门一致，直接使用
        dispatch_result["case_type"] = case_type_info
        return dispatch_result

    # 派单结果与预期部门不一致时，以案件类型指定的部门为准，
    # 但仍尝试用该部门的图层做坐标比对
    rule = DEPARTMENT_GEO_RULES.get(department, {})
    if not rule.get("ready"):
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "case_type": case_type_info,
            "layer_status": "not_ready",
            "answer": f"{department}范围数据未完善（暂按人工研判）。",
        }

    geojson_data = _load_department_geojson(rule.get("file"))
    if not geojson_data:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "case_type": case_type_info,
            "layer_status": "missing_layer_file",
            "answer": f"{department}范围数据文件缺失，暂无法自动判定。",
        }

    lng, lat = point
    mode = rule.get("geometry_mode", "polygon")
    line_buffer_m = float(rule.get("line_buffer_m", 80.0))

    for feature in geojson_data.get("features", []):
        geometry = feature.get("geometry", {}) or {}
        props = feature.get("properties", {}) or {}
        geo_type = geometry.get("type")
        coords = geometry.get("coordinates", [])
        matched = False

        if mode == "polygon":
            if geo_type == "Polygon":
                matched = _point_in_polygon(lng, lat, coords)
            elif geo_type == "MultiPolygon":
                matched = any(_point_in_polygon(lng, lat, poly) for poly in coords)
        elif mode == "line":
            if geo_type == "LineString":
                matched = _point_near_line_m(lng, lat, coords, line_buffer_m)
            elif geo_type == "MultiLineString":
                matched = any(_point_near_line_m(lng, lat, line, line_buffer_m) for line in coords)

        if matched:
            from kb_dispatch import _extract_unit_name
            unit = _extract_unit_name(department, props)
            return {
                "success": True,
                "department": department,
                "unit": unit,
                "in_jurisdiction": True,
                "case_type": case_type_info,
                "layer_status": "ready",
                "answer": unit,
            }

    return {
        "success": True,
        "department": department,
        "unit": None,
        "in_jurisdiction": False,
        "case_type": case_type_info,
        "layer_status": "ready",
        "answer": "不属于我局管辖范围",
    }
