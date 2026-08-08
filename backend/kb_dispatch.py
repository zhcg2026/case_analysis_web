"""
kb_dispatch.py —— 地理派单逻辑（阶段0 平移，不重写）
================================================
业务核心：根据市民问题文本 + 地图点选坐标，判定归属部门/管辖片区。
- 点面判定（Polygon / MultiPolygon）：判断坐标是否落在某部门辖区
- 点线判定（LineString / MultiLineString，带 buffer 米）：判断坐标是否靠近某条市政道路
- 关键词兜底归类：无坐标时按问题中部门关键词粗分

本模块**纯标准库依赖**，与检索/向量库解耦——召回标准之后才调用。
原代码位于 case_standards.py（约 401-850 行），此处整体平移，业务规则保持不变。

公开 API：
  match_department_dispatch(question, location, force_dispatch=False) -> dict | None
  pre_analyze_question(question) -> dict
  is_dispatch_question(question) -> bool
"""
import os
import re
import json
import math
from typing import Dict, Any, Optional, Tuple, List

# ------------------------- 派单常量（与业务一致，勿随意改） -------------------------

DISPATCH_INTENT_WORDS = [
    "处置部门", "归哪个部门", "归谁", "谁负责", "哪个单位", "由谁处置", "负责部门"
]

DEPARTMENT_KEYWORDS = {
    # 环卫类关键词：包含"遗撒/抛洒/洒落"，用于覆盖"道路遗撒/路面抛洒"等提问
    "市容环卫中心": ["环卫", "垃圾", "保洁", "清扫", "污物", "脏污", "果皮箱", "清运", "遗撒", "抛洒", "洒落", "不洁", "积存", "积冰", "积雪", "清洁", "粪便", "排泄物", "呕吐物", "动物尸体", "死禽", "死畜", "脏乱差", "脏乱", "环境差", "卫生差"],
    "园林绿化中心": ["园林", "绿化", "树木", "草坪", "花坛", "绿化带", "公园", "行道树", "绿化垃圾"],
    "综合行政执法队": ["执法", "占道", "违建", "商贩", "广告牌", "渣土车", "门头牌匾", "无照经营"],
    "市政公用服务中心": ["市政", "路灯", "灯杆", "道路", "路面", "井盖", "护栏", "交通设施"],
    "排水服务中心": ["排水", "雨水", "污水", "积水", "下水道", "雨污", "管网", "窨井"],
    "节水服务中心": ["节水", "用水", "漏水", "节约用水", "非常规水", "水资源"],
    "供热供气服务中心": ["供热", "供气", "燃气", "热力", "暖气", "管道燃气", "供暖"],
    "建筑资源化服务中心": ["建筑垃圾", "资源化", "装修垃圾", "再生利用", "渣土处置", "消纳场"],
}

# 环卫优先词：当问题中包含这些词时，即使匹配了市政的"道路/路面"，也强制归为环卫
_SANITATION_OVERRIDE = ["不洁", "脏", "污", "积存", "积冰", "积雪", "垃圾", "保洁", "清扫", "遗撒", "抛洒", "洒落", "清洁", "粪便", "排泄物", "呕吐物", "动物尸体", "死禽", "死畜"]

PARK_NAMES = ["人民公园", "航天公园", "禹都公园", "圣惠公园", "体育公园", "天逸公园", "南风广场"]

_here = os.path.dirname(os.path.abspath(__file__))
_MAP_DATA_PUBLIC = os.path.normpath(os.path.join(_here, "..", "frontend", "public", "data"))
_MAP_DATA_DIST = os.path.normpath(os.path.join(_here, "..", "frontend", "dist", "data"))
MAP_DATA_DIR = _MAP_DATA_PUBLIC if os.path.isdir(_MAP_DATA_PUBLIC) else _MAP_DATA_DIST

DEPARTMENT_GEO_RULES = {
    "市容环卫中心": {
        "ready": True,
        "file": "guanxia.geojson",
        "geometry_mode": "polygon",
        "unit_type": "片区",
    },
    "园林绿化中心": {
        "ready": True,
        "file": "园林片区.geojson",
        "geometry_mode": "polygon",
        "unit_type": "片区",
        # 公园范围图层（你提到“公园的还没画”）：先预留配置位，未就绪时走片区兜底
        "park_ready": False,
        "park_file": None,
    },
    "综合行政执法队": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "分队"},
    "市政公用服务中心": {
        "ready": True,
        "file": "市政管辖道路.geojson",
        "geometry_mode": "line",
        "unit_type": "部门",
        "line_buffer_m": 80.0,
    },
    "排水服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "节水服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "供热供气服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
    "建筑资源化服务中心": {"ready": False, "file": None, "geometry_mode": "polygon", "unit_type": "部门"},
}

_department_geojson_cache: Dict[str, Dict[str, Any]] = {}


# ------------------------- 文本归一化 -------------------------

def _normalize_cn_text(text: str) -> str:
    """中文归一化：移除空白和常见标点，提升匹配稳定性"""
    if not text:
        return ''
    return re.sub(r'[\s，。；：、,.!?！？()（）【】\[\]{}"\'“”‘’\-—_/\\]+', '', text)


def _is_dispatch_question(question: str) -> bool:
    normalized = _normalize_cn_text(question)
    return any(_normalize_cn_text(w) in normalized for w in DISPATCH_INTENT_WORDS)


def _classify_department(question: str) -> Optional[str]:
    normalized = _normalize_cn_text(question)
    # 对"遗撒/抛洒/洒落"这类典型环卫问题，直接优先归类到环卫中心，
    # 避免"道路/路面"等市政关键词抢占最高分。
    if "遗撒" in normalized or "抛洒" in normalized or "洒落" in normalized:
        return "市容环卫中心"

    best_dept = None
    best_score = 0
    for dept, words in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for w in words if _normalize_cn_text(w) in normalized)
        if score > best_score:
            best_score = score
            best_dept = dept

    # 环卫优先覆盖：如果问题包含环卫核心词（如"不洁""积存"），
    # 即使市政的"道路/路面"得分更高，也强制归为环卫
    if best_dept == "市政公用服务中心" and best_score > 0:
        has_sanitation = any(_normalize_cn_text(w) in normalized for w in _SANITATION_OVERRIDE)
        if has_sanitation:
            return "市容环卫中心"

    return best_dept if best_score > 0 else None


def pre_analyze_question(question: str) -> Dict[str, Any]:
    """
    预分析市民问题，提取关键信息，辅助LLM分析

    Returns:
        {
            "location_area": str,      # 区域（如"盐湖区"）
            "location_road": str,      # 道路（如"圣惠路"）
            "location_landmark": str,  # 地标（如"明珠快捷酒店门口"）
            "problem_type": str,       # 问题类型（如"损坏""脏污""缺失"）
            "facility": str,           # 涉及设施（如"护栏""井盖""路灯"）
            "department": str,         # 匹配的部门（如"市政公用服务中心"）
            "keywords": list,          # 关键词列表
        }
    """
    result = {
        "location_area": "",
        "location_road": "",
        "location_landmark": "",
        "problem_type": "",
        "facility": "",
        "department": "",
        "keywords": [],
    }

    # 提取区域信息
    area_patterns = [
        r'([\u4e00-\u9fa5]{2,4}区)',  # 盐湖区、临猗县
        r'([\u4e00-\u9fa5]{2,4}县)',
        r'([\u4e00-\u9fa5]{2,4}市)',
    ]
    for pattern in area_patterns:
        match = re.search(pattern, question)
        if match:
            result["location_area"] = match.group(1)
            break

    # 提取道路信息
    road_match = re.search(r'([\u4e00-\u9fa5]{2,8}(?:路|街|巷|道|大道|街道))', question)
    if road_match:
        result["location_road"] = road_match.group(1)

    # 提取地标信息（门口、附近、旁边等）
    landmark_match = re.search(r'([\u4e00-\u9fa5]{2,15}(?:门口|附近|旁边|对面|处|侧))', question)
    if landmark_match:
        result["location_landmark"] = landmark_match.group(1)

    # 提取问题类型
    problem_types = ["损坏", "破损", "缺失", "丢失", "断裂", "弯曲", "变形",
                     "脏污", "不洁", "积存", "垃圾", "污染",
                     "倾斜", "倒塌", "松动", "脱落",
                     "堵塞", "积水", "漏水", "溢水",
                     "噪音", "异味", "扬尘",
                     "坑洼", "不平", "凸起", "凹陷"]
    for pt in problem_types:
        if pt in question:
            result["problem_type"] = pt
            break

    # 提取涉及设施
    facility_keywords = {
        "护栏": ["护栏", "交通护栏", "隔离栏", "围栏"],
        "井盖": ["井盖", "窨井盖", "下水道盖"],
        "路灯": ["路灯", "灯杆", "照明", "灯"],
        "树木": ["树木", "行道树", "树枝", "绿化"],
        "广告牌": ["广告牌", "招牌", "门头牌匾", "户外广告"],
        "垃圾桶": ["垃圾桶", "果皮箱", "垃圾箱"],
        "路面": ["路面", "道路", "地面", "人行道"],
        "排水": ["排水", "下水道", "雨水", "污水", "管网"],
        "健身器材": ["健身器材", "体育设施", "运动器材"],
    }
    for facility, keywords in facility_keywords.items():
        if any(kw in question for kw in keywords):
            result["facility"] = facility
            break

    # 匹配部门
    result["department"] = _classify_department(question) or ""

    # 提取关键词（用于辅助搜索）
    # 移除常见停用词
    stop_words = ["市民", "建议", "反映", "问题", "希望", "予以", "采纳", "及时",
                  "维护", "处理", "解决", "相关", "部门", "单位", "应该", "需要"]
    keywords = question
    for sw in stop_words:
        keywords = keywords.replace(sw, "")
    # 提取2-4字词组
    extracted_kw = []
    for length in [4, 3, 2]:
        for i in range(len(keywords) - length + 1):
            seg = keywords[i:i + length]
            if all('\u4e00' <= c <= '\u9fa5' for c in seg) and seg not in extracted_kw:
                extracted_kw.append(seg)
                if len(extracted_kw) >= 5:
                    break
        if len(extracted_kw) >= 5:
            break
    result["keywords"] = extracted_kw

    return result


# ------------------------- 坐标解析 -------------------------

def _extract_location_point(location: Any) -> Optional[Tuple[float, float]]:
    if isinstance(location, dict):
        # 兼容 {"lat":..., "lng":...} / {"latitude":..., "longitude":...}
        lat = location.get("lat") or location.get("latitude")
        lng = location.get("lng") or location.get("longitude")
        if lat is not None and lng is not None:
            try:
                return (float(lng), float(lat))
            except (TypeError, ValueError):
                return None
    if isinstance(location, (list, tuple)) and len(location) >= 2:
        try:
            return (float(location[1]), float(location[0]))
        except (TypeError, ValueError):
            return None
    return None


def _load_department_geojson(file_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not file_name:
        return None
    if file_name in _department_geojson_cache:
        return _department_geojson_cache[file_name]
    file_path = os.path.join(MAP_DATA_DIR, file_name)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _department_geojson_cache[file_name] = data
        return data
    except Exception:
        return None


# ------------------------- 几何判定 -------------------------

def _point_in_ring(lng: float, lat: float, ring: List[List[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-15) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lng: float, lat: float, polygon_coords: List[List[List[float]]]) -> bool:
    if not polygon_coords:
        return False
    if not _point_in_ring(lng, lat, polygon_coords[0]):
        return False
    for hole in polygon_coords[1:]:
        if _point_in_ring(lng, lat, hole):
            return False
    return True


def _point_segment_distance_m(lng: float, lat: float, a: List[float], b: List[float]) -> float:
    lon_scale = 111320.0 * math.cos(math.radians(lat))
    lat_scale = 110540.0
    px, py = lng * lon_scale, lat * lat_scale
    ax, ay = a[0] * lon_scale, a[1] * lat_scale
    bx, by = b[0] * lon_scale, b[1] * lat_scale
    abx, aby = bx - ax, by - ay
    ab_len2 = abx * abx + aby * aby
    if ab_len2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * abx
    proj_y = ay + t * aby
    return math.hypot(px - proj_x, py - proj_y)


def _point_near_line_m(lng: float, lat: float, line_coords: List[List[float]], threshold_m: float) -> bool:
    if not line_coords or len(line_coords) < 2:
        return False
    for idx in range(len(line_coords) - 1):
        if _point_segment_distance_m(lng, lat, line_coords[idx], line_coords[idx + 1]) <= threshold_m:
            return True
    return False


def _extract_unit_name(department: str, props: Dict[str, Any]) -> str:
    if department == "市容环卫中心":
        area = props.get("name") or props.get("zone_name")
        if area:
            return f"环卫{str(area).replace('环卫', '').replace('片区', '')}片区"
    if department == "园林绿化中心":
        zone_name = props.get("zone_name") or props.get("name") or props.get("manager_org")
        if zone_name:
            return zone_name
    if department == "综合行政执法队":
        return props.get("zone_name") or props.get("name") or "综合行政执法队"
    if department == "市政公用服务中心":
        return "市政公用服务中心"
    return department


def _is_park_feature(props: Dict[str, Any]) -> bool:
    joined = " ".join([str(props.get(k, "")) for k in ["name", "zone_name", "manager_org", "remark"]])
    return any(p in joined for p in PARK_NAMES) or ("公园" in joined) or ("广场" in joined)


def _question_mentions_park(question: str) -> bool:
    """判断用户是否在问某个公园的责任单位/管辖"""
    normalized = _normalize_cn_text(question)
    if not normalized:
        return False
    if "公园" in normalized or "广场" in normalized:
        return True
    return any(_normalize_cn_text(p) in normalized for p in PARK_NAMES)


# ------------------------- 派单主入口 -------------------------

def match_department_dispatch(question: str, location: Any, force_dispatch: bool = False) -> Optional[Dict[str, Any]]:
    if not force_dispatch and not _is_dispatch_question(question):
        return None
    point = _extract_location_point(location)
    if not point:
        # 没有位置信息时，返回通用部门分类结果
        department = _classify_department(question)
        if department:
            return {
                "success": True,
                "department": department,
                "unit": None,
                "in_jurisdiction": False,
                "layer_status": "no_location",
                "answer": f"根据问题描述，该问题可能由{department}负责。如需精确判断管辖区域，请在地图上点选具体位置。",
            }
        return {
            "success": True,
            "department": None,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "missing_location",
            "answer": "请先在地图上定位后再查询处置部门。",
        }

    department = _classify_department(question)
    if not department:
        return {
            "success": True,
            "department": None,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "unknown_department",
            "answer": "未能识别处置部门，请补充更具体的问题描述。",
        }

    rule = DEPARTMENT_GEO_RULES.get(department, {})
    if not rule.get("ready"):
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "not_ready",
            "answer": f"{department}范围数据未完善（暂按人工研判）。",
        }

    # 园林：分"片区"与"公园"两类。公园图层未就绪时，先按片区兜底，并给出提示。
    ask_park = (department == "园林绿化中心") and _question_mentions_park(question)
    geojson_data = None
    using_park_layer = False
    if ask_park and rule.get("park_ready") and rule.get("park_file"):
        geojson_data = _load_department_geojson(rule.get("park_file"))
        using_park_layer = geojson_data is not None
    if geojson_data is None:
        geojson_data = _load_department_geojson(rule.get("file"))

    if not geojson_data:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "missing_layer_file",
            "answer": f"{department}范围数据文件缺失，暂无法自动判定。",
        }

    lng, lat = point
    polygon_hits = []
    normal_hits = []
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
            unit_name = _extract_unit_name(department, props)
            hit = {"unit": unit_name, "properties": props}
            if department == "园林绿化中心" and _is_park_feature(props):
                polygon_hits.append(hit)
            else:
                normal_hits.append(hit)

    selected = None
    if polygon_hits:
        selected = polygon_hits[0]
    elif normal_hits:
        selected = normal_hits[0]

    if not selected:
        return {
            "success": True,
            "department": department,
            "unit": None,
            "in_jurisdiction": False,
            "layer_status": "ready",
            "answer": "不属于我局管辖范围",
        }

    unit = selected["unit"]
    # 园林问公园但公园图层未画：用片区结果兜底，并明确提示（避免用户误以为是精确到公园管理方）
    if ask_park and not using_park_layer:
        return {
            "success": True,
            "department": department,
            "unit": unit,
            "in_jurisdiction": True,
            "layer_status": "park_not_ready_fallback_zone",
            "answer": f"{unit}（公园范围图层未完善，当前按园林片区兜底）",
        }

    return {
        "success": True,
        "department": department,
        "unit": unit,
        "in_jurisdiction": True,
        "layer_status": "ready",
        "answer": unit,
    }


# 公开别名（供 kb_store 统一问答入口判定派单意图）
is_dispatch_question = _is_dispatch_question
