"""
cleaning_rules.py —— 数据清洗规则模块
======================================
7条清洗规则 + 延期/返工案件解析
"""
import re
import json
import math
import logging
import pandas as pd
from sqlalchemy import text

from coord_transform import bd09mc_to_gcj02, bd09mc_to_wgs84

logger = logging.getLogger(__name__)

# 原始Excel列名 → 数据库字段的映射（24列原始格式）
RAW_COLUMN_MAP = {
    '上报时间': 'report_time',
    '任务号': 'task_no',
    '大类名称': 'big_category',
    '小类名称': 'small_category',
    '问题来源': 'source',
    '问题描述': 'description',
    '当前阶段名称': 'stage',
    '处置部门': 'department',
    '捆绑处置截止时间': 'deadline_bundled',
    '结案时间': 'close_time',
    '所属片区': 'district',
    '问题类型': 'issue_type',
    '地址描述': 'address',
    '所属街道': 'street',
    '所属社区': 'community',
    '监督员': 'supervisor',
    '处置截止时间': 'deadline',
    'X坐标': 'longitude',
    'Y坐标': 'latitude',
}

# 需要丢弃的列（原始数据有但系统不需要）
DROP_COLUMNS = ['延期理由', '处置意见', '所属区域', '单元网格', '延期次数']


def prepare_dataframe(df):
    """将原始Excel DataFrame转换为系统格式"""
    # 丢弃不需要的列
    cols_to_drop = [c for c in DROP_COLUMNS if c in df.columns]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # 重命名列
    df = df.rename(columns=RAW_COLUMN_MAP)

    # 只保留系统需要的列
    keep_cols = list(RAW_COLUMN_MAP.values())
    df = df[[c for c in keep_cols if c in df.columns]]

    # 初始化缺失的列
    if 'is_delayed' not in df.columns:
        df['is_delayed'] = 0
    if 'is_rework' not in df.columns:
        df['is_rework'] = 0

    return df


def rule_source_replace(df):
    """规则1：问题来源替换 —— 【其他问题上报】→【采集员上报】"""
    if 'source' not in df.columns:
        return df, 0
    mask = df['source'].astype(str).str.strip() == '其他问题上报'
    count = mask.sum()
    df.loc[mask, 'source'] = '采集员上报'
    return df, int(count)


def rule_clean_description(df):
    """规则2：问题描述清洗 —— 清除开头无关数字、序号、标点"""
    if 'description' not in df.columns:
        return df, 0
    original = df['description'].copy()
    # 匹配开头的纯序号/编号/标点组合
    pattern = r'^[\d\.\、\，\,\。\：\:\；\;\-\_\（\）\(\)\[\]\【\】\s]+'
    df['description'] = df['description'].astype(str).str.replace(pattern, '', regex=True)
    # 处理NaN
    df['description'] = df['description'].replace('nan', pd.NA)
    changed = (original.fillna('') != df['description'].fillna('')).sum()
    return df, int(changed)


def rule_assign_district(df, geojson_path):
    """规则3：所属片区判定 —— 根据坐标 + GeoJSON多边形判定五大片区"""
    if not geojson_path:
        return df, 0, '未提供GeoJSON文件'

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
    except Exception as e:
        return df, 0, f'GeoJSON读取失败: {e}'

    # 解析多边形
    districts = []
    for feature in geojson.get('features', []):
        name = feature['properties'].get('name', '')
        geom = feature.get('geometry', {})
        geom_type = geom.get('type', '')
        coords = geom.get('coordinates', [])

        if geom_type == 'Polygon':
            districts.append({'name': name, 'coords': coords})
        elif geom_type == 'MultiPolygon':
            for polygon in coords:
                districts.append({'name': name, 'coords': polygon})

    if not districts:
        return df, 0, 'GeoJSON中未找到有效多边形'

    # 点面匹配（复用 kb_dispatch 的射线法）
    from kb_dispatch import _point_in_polygon

    filled = 0
    for idx, row in df.iterrows():
        lng = row.get('longitude')
        lat = row.get('latitude')
        if pd.isna(lng) or pd.isna(lat):
            continue

        try:
            # 坐标转换：BD09-MC → WGS84（用于匹配WGS84的GeoJSON）
            wgs_lng, wgs_lat = bd09mc_to_wgs84(float(lng), float(lat))
        except (ValueError, TypeError):
            continue

        for d in districts:
            try:
                if _point_in_polygon(wgs_lng, wgs_lat, d['coords']):
                    df.at[idx, 'district'] = d['name']
                    filled += 1
                    break
            except Exception:
                continue

    return df, filled, f'匹配到{filled}条记录的片区'


def rule_fill_community(df, engine):
    """规则4：所属社区补全 —— 根据坐标就近匹配社区"""
    if not engine:
        return df, 0, '数据库未连接'

    # 从现有数据提取社区中心点
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT community,
                       AVG(longitude) as center_lng,
                       AVG(latitude) as center_lat,
                       COUNT(*) as cnt
                FROM case_data
                WHERE community IS NOT NULL AND community != ''
                  AND longitude IS NOT NULL AND latitude IS NOT NULL
                GROUP BY community
                HAVING cnt >= 3
            """))
            community_centers = result.fetchall()
    except Exception as e:
        return df, 0, f'查询社区中心点失败: {e}'

    if not community_centers:
        return df, 0, '无可用社区中心点数据'

    def haversine(lng1, lat1, lng2, lat2):
        """计算两点间的球面距离（米）"""
        R = 6371000
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    filled = 0
    for idx, row in df.iterrows():
        # 跳过已有社区的记录
        community = row.get('community')
        if pd.notna(community) and str(community).strip():
            continue

        lng = row.get('longitude')
        lat = row.get('latitude')
        if pd.isna(lng) or pd.isna(lat):
            continue

        try:
            x = float(lng)
            y = float(lat)
        except (ValueError, TypeError):
            continue

        # 找最近的社区
        min_dist = float('inf')
        best_community = None
        for comm, c_lng, c_lat, _ in community_centers:
            try:
                dist = haversine(x, y, float(c_lng), float(c_lat))
                if dist < min_dist:
                    min_dist = dist
                    best_community = comm
            except (ValueError, TypeError):
                continue

        if best_community and min_dist < 5000:  # 5km阈值
            df.at[idx, 'community'] = best_community
            filled += 1

    return df, filled, f'补全了{filled}条记录的社区'


def rule_convert_coords(df):
    """规则5：坐标转换 —— 百度墨卡托(BD09-MC) → 高德(GCJ02)"""
    if 'longitude' not in df.columns or 'latitude' not in df.columns:
        return df, 0, '缺少坐标列'

    converted = 0
    errors = 0
    for idx, row in df.iterrows():
        x = row.get('longitude')  # 原始X坐标（BD09-MC）
        y = row.get('latitude')   # 原始Y坐标（BD09-MC）
        if pd.isna(x) or pd.isna(y):
            continue
        try:
            gcj_lng, gcj_lat = bd09mc_to_gcj02(float(x), float(y))
            # 验证转换结果在运城范围内
            if 110.0 < gcj_lng < 112.0 and 34.5 < gcj_lat < 35.5:
                df.at[idx, 'longitude'] = round(gcj_lng, 6)
                df.at[idx, 'latitude'] = round(gcj_lat, 6)
                converted += 1
            else:
                errors += 1
        except (ValueError, TypeError):
            errors += 1

    return df, converted, f'转换成功{converted}条，异常{errors}条'


def rule_normalize_supervisor(df):
    """规则6：监督员规范化 —— 去除姓名周围的多余修饰字符"""
    if 'supervisor' not in df.columns:
        return df, 0
    original = df['supervisor'].copy()
    df['supervisor'] = df['supervisor'].astype(str).str.strip()
    # 去除中文/英文括号包裹
    df['supervisor'] = df['supervisor'].str.replace(r'^[\（\【\(\[\s]+', '', regex=True)
    df['supervisor'] = df['supervisor'].str.replace(r'[\）\]\)\】\s]+$', '', regex=True)
    # 处理NaN
    df['supervisor'] = df['supervisor'].replace('nan', pd.NA)
    changed = (original.fillna('') != df['supervisor'].fillna('')).sum()
    return df, int(changed)


def rule_desensitize_description(df):
    """规则7：问题描述脱敏 —— 手机号、座机号、详细地址脱敏"""
    if 'description' not in df.columns:
        return df, 0

    count = 0

    def desensitize(text):
        nonlocal count
        if pd.isna(text):
            return text
        text = str(text)
        original = text

        # 手机号脱敏：13812345678 → 138****5678
        text = re.sub(
            r'1[3-9]\d{9}',
            lambda m: m.group()[:3] + '****' + m.group()[-4:],
            text
        )

        # 座机号脱敏：0359-1234567 → 0359-****567
        text = re.sub(
            r'0\d{2,3}-?\d{7,8}',
            lambda m: m.group()[:4] + '****' + m.group()[-3:],
            text
        )

        # 详细地址脱敏：保留到街道级，隐藏具体门牌号
        text = re.sub(r'(\S+路)\S*号\S*', r'\1**号', text)

        if text != original:
            count += 1
        return text

    df['description'] = df['description'].apply(desensitize)
    return df, count


# ============================================================
# 延期/返工案件解析
# ============================================================

def parse_delay_rework_txt(text):
    """解析延期/返工案件号txt
    格式示例：
        延期：案件号1、案件号2、案件号3
        返工：案件号4、案件号5
    """
    result = {'delayed': [], 'rework': []}
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if '延期' in line:
            # 提取冒号后的案件号
            parts = line.split('：') if '：' in line else line.split(':')
            if len(parts) > 1:
                nums = re.split(r'[、，,\s]+', parts[1])
                result['delayed'] = [n.strip() for n in nums if n.strip().isdigit()]
        elif '返工' in line:
            parts = line.split('：') if '：' in line else line.split(':')
            if len(parts) > 1:
                nums = re.split(r'[、，,\s]+', parts[1])
                result['rework'] = [n.strip() for n in nums if n.strip().isdigit()]
    return result


def parse_delay_rework_excel(df):
    """从Excel解析延期/返工案件号
    期望格式：两列，一列是任务号，一列是类型（延期/返工）
    """
    result = {'delayed': [], 'rework': []}
    if len(df.columns) < 2:
        return result

    task_col = df.columns[0]
    type_col = df.columns[1]

    for _, row in df.iterrows():
        task_no = str(row[task_col]).strip()
        case_type = str(row[type_col]).strip()
        if not task_no.isdigit():
            continue
        if '延期' in case_type:
            result['delayed'].append(task_no)
        elif '返工' in case_type:
            result['rework'].append(task_no)
    return result


def apply_delay_rework(df, delay_task_nos, rework_task_nos):
    """根据任务号匹配写入延期/返工标记"""
    task_nos = df['task_no'].astype(str)

    mask_delayed = task_nos.isin(delay_task_nos)
    df.loc[mask_delayed, 'is_delayed'] = 1

    mask_rework = task_nos.isin(rework_task_nos)
    df.loc[mask_rework, 'is_rework'] = 1

    return df, int(mask_delayed.sum()), int(mask_rework.sum())


# ============================================================
# 清洗主流程
# ============================================================

def run_cleaning(df, rules_config, engine=None, geojson_path=None,
                 delay_task_nos=None, rework_task_nos=None):
    """执行清洗主流程
    Args:
        df: 原始DataFrame
        rules_config: 规则开关字典 {rule_name: enabled}
        engine: SQLAlchemy引擎（规则4需要）
        geojson_path: 五大片区GeoJSON路径（规则3需要）
        delay_task_nos: 延期案件任务号列表
        rework_task_nos: 返工案件任务号列表
    Returns:
        df: 清洗后的DataFrame
        report: 清洗报告字典
    """
    report = {}

    # 先做列映射和格式转换
    df = prepare_dataframe(df)

    # 规则1：问题来源替换
    if rules_config.get('rule1', True):
        df, count = rule_source_replace(df)
        report['rule1'] = {'name': '问题来源替换', 'changed': count}

    # 规则2：问题描述清洗
    if rules_config.get('rule2', True):
        df, count = rule_clean_description(df)
        report['rule2'] = {'name': '问题描述清洗', 'changed': count}

    # 规则3：所属片区判定
    if rules_config.get('rule3', True) and geojson_path:
        df, count, msg = rule_assign_district(df, geojson_path)
        report['rule3'] = {'name': '所属片区判定', 'changed': count, 'message': msg}

    # 规则4：所属社区补全
    if rules_config.get('rule4', True) and engine:
        df, count, msg = rule_fill_community(df, engine)
        report['rule4'] = {'name': '所属社区补全', 'changed': count, 'message': msg}

    # 规则5：坐标转换
    if rules_config.get('rule5', True):
        df, count, msg = rule_convert_coords(df)
        report['rule5'] = {'name': '坐标转换', 'changed': count, 'message': msg}

    # 规则6：监督员规范化
    if rules_config.get('rule6', True):
        df, count = rule_normalize_supervisor(df)
        report['rule6'] = {'name': '监督员规范化', 'changed': count}

    # 规则7：问题描述脱敏
    if rules_config.get('rule7', False):
        df, count = rule_desensitize_description(df)
        report['rule7'] = {'name': '问题描述脱敏', 'changed': count}

    # 延期/返工补充
    if delay_task_nos or rework_task_nos:
        df, d_count, r_count = apply_delay_rework(
            df, delay_task_nos or [], rework_task_nos or []
        )
        report['delay_rework'] = {
            'name': '延期/返工补充',
            'delayed_matched': d_count,
            'rework_matched': r_count
        }

    return df, report
