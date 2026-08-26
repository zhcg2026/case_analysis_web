"""
cleaning_rules.py —— 数据清洗规则模块
======================================
7条清洗规则 + 延期/返工案件解析
"""
import os
import re
import json
import math
import logging
import pandas as pd
from sqlalchemy import text

from coord_transform import bd09mc_to_gcj02, bd09mc_to_wgs84, gcj02_to_wgs84

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
# 注意：所属区域需要保留用于规则8（删除指定区域）
DROP_COLUMNS = ['延期理由', '处置意见', '单元网格', '延期次数']


def prepare_dataframe(df):
    """将原始Excel DataFrame转换为系统格式"""
    # 丢弃不需要的列（保留所属区域用于规则8）
    cols_to_drop = [c for c in DROP_COLUMNS if c in df.columns]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # 保存所属区域列（用于规则8删除指定区域）
    area_col = None
    if '所属区域' in df.columns:
        area_col = df['所属区域'].copy()

    # 重命名列
    df = df.rename(columns=RAW_COLUMN_MAP)

    # 只保留系统需要的列
    keep_cols = list(RAW_COLUMN_MAP.values())
    df = df[[c for c in keep_cols if c in df.columns]]

    # 恢复所属区域列
    if area_col is not None:
        df['原始所属区域'] = area_col

    # 初始化缺失的列
    if 'is_delayed' not in df.columns:
        df['is_delayed'] = 0
    if 'is_rework' not in df.columns:
        df['is_rework'] = 0
    if 'is_overtime' not in df.columns:
        df['is_overtime'] = 0

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
    """规则2：问题描述清洗 —— 清除开头无关内容（案件编号、序号、标点等）"""
    if 'description' not in df.columns:
        return df, 0
    original = df['description'].copy()

    def clean_start(text):
        """清洗开头的案件编号、序号、标点等"""
        if pd.isna(text):
            return text
        text = str(text).strip()
        # 匹配开头的案件编号格式：字母+数字+字母数字*组合，如 AP20260****9900003JY04
        # 也匹配纯数字序号、标点符号等
        pattern = r'^[A-Za-z0-9\*\-\_\.\s\，\,\。\：\:\；\;\、\（\）\(\)\【\】\[\]\「\」\『\』\〈\〉\《\》\★\●\◆\■\▲\◇\○\△\□\☆\◎\※\→\←\↑\↓\①\②\③\④\⑤\⑥\⑦\⑧\⑨\⑩]+'
        result = re.sub(pattern, '', text)
        # 如果清洗后为空，返回原文（避免误清洗纯中文内容）
        return result if result else text

    df['description'] = df['description'].apply(clean_start)
    # 处理NaN
    df['description'] = df['description'].replace('nan', pd.NA)
    # 转换为普通字符串比较，避免ArrowDtype类型问题
    changed = (original.fillna('').astype(str) != df['description'].fillna('').astype(str)).sum()
    return df, int(changed)


def rule_assign_district(df, geojson_path):
    """规则3：所属片区判定 —— 根据坐标 + GeoJSON多边形判定五大片区
    功能：
    1. 补全空的片区字段
    2. 修订高铁站片区、经济开发区等错误片区为正确片区
    """
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
        name = feature['properties'].get('片区名称', '') or feature['properties'].get('name', '')
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

    logger.info(f'加载了{len(districts)}个片区多边形: {[d["name"] for d in districts]}')

    # 打印当前数据中的片区分布
    if 'district' in df.columns:
        district_counts = df['district'].value_counts()
        logger.info(f'当前片区分布: {district_counts.to_dict()}')

    # 需要修订的错误片区名称（应修正为五大片区）
    WRONG_DISTRICTS = {'高铁站片区', '高铁片区', '经济开发区', '经济开发区片区', '开发区', '全区域'}

    # 点面匹配（复用 kb_dispatch 的射线法）
    from kb_dispatch import _point_in_polygon

    # 计算点到多边形的最小距离（简化：到所有顶点的最小距离）
    def min_distance_to_polygon(lng, lat, coords):
        """计算点到多边形所有顶点的最小距离（米）"""
        min_dist = float('inf')
        for ring in coords:
            for vertex in ring:
                dist = haversine_distance(lng, lat, vertex[0], vertex[1])
                if dist < min_dist:
                    min_dist = dist
        return min_dist

    def haversine_distance(lng1, lat1, lng2, lat2):
        """计算两点间的球面距离（米）"""
        R = 6371000
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    filled = 0
    revised = 0
    skipped_wrong = 0
    convert_errors = 0
    nearest_match = 0

    for idx, row in df.iterrows():
        lng = row.get('longitude')
        lat = row.get('latitude')
        if pd.isna(lng) or pd.isna(lat):
            continue

        current_district = str(row.get('district', '')).strip()

        # 只处理：1.片区为空  2.片区是错误名称
        needs_fill = pd.isna(row.get('district')) or not current_district
        needs_revise = current_district in WRONG_DISTRICTS

        if not needs_fill and not needs_revise:
            skipped_wrong += 1
            continue

        try:
            # 坐标转换：BD09-MC → WGS84（用于匹配WGS84的GeoJSON）
            wgs_lng, wgs_lat = bd09mc_to_wgs84(float(lng), float(lat))
        except (ValueError, TypeError):
            convert_errors += 1
            continue

        # 第一步：尝试精确匹配（点在多边形内）
        matched = False
        for d in districts:
            try:
                if _point_in_polygon(wgs_lng, wgs_lat, d['coords']):
                    df.at[idx, 'district'] = d['name']
                    if needs_revise:
                        revised += 1
                    else:
                        filled += 1
                    matched = True
                    break
            except Exception:
                continue

        # 第二步：如果精确匹配失败，按就近原则分配最近的片区
        if not matched:
            min_dist = float('inf')
            nearest_name = None
            for d in districts:
                try:
                    dist = min_distance_to_polygon(wgs_lng, wgs_lat, d['coords'])
                    if dist < min_dist:
                        min_dist = dist
                        nearest_name = d['name']
                except Exception:
                    continue

            if nearest_name and min_dist < 5000:  # 5km阈值
                df.at[idx, 'district'] = nearest_name
                if needs_revise:
                    revised += 1
                else:
                    filled += 1
                nearest_match += 1

    logger.info(f'片区判定统计: 补全{filled}, 修订{revised}, 跳过{skipped_wrong}, 坐标转换失败{convert_errors}, 就近匹配{nearest_match}')

    return df, filled + revised, f'补全{filled}条，修订{revised}条（含就近匹配{nearest_match}条）'


def rule_assign_sanitation_district(df, geojson_path):
    """规则3b：环卫片区分配 —— 将"市容环卫中心"按坐标分配到东西南北中片区
    依据：环卫管辖范围GeoJSON
    """
    if 'department' not in df.columns or 'district' not in df.columns:
        return df, 0, '缺少department或district列'

    if not geojson_path:
        return df, 0, '未提供环卫GeoJSON文件'

    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
    except Exception as e:
        return df, 0, f'GeoJSON读取失败: {e}'

    # 解析环卫片区多边形
    districts = []
    for feature in geojson.get('features', []):
        name = feature['properties'].get('name', '')
        dept = feature['properties'].get('dept', '')
        if dept != '环卫':
            continue
        geom = feature.get('geometry', {})
        geom_type = geom.get('type', '')
        coords = geom.get('coordinates', [])

        if geom_type == 'Polygon':
            districts.append({'name': f'环卫{name}', 'coords': coords})
        elif geom_type == 'MultiPolygon':
            for polygon in coords:
                districts.append({'name': f'环卫{name}', 'coords': polygon})

    if not districts:
        return df, 0, 'GeoJSON中未找到环卫片区'

    logger.info(f'加载了{len(districts)}个环卫片区: {[d["name"] for d in districts]}')

    # 点面匹配
    from kb_dispatch import _point_in_polygon

    def haversine_distance(lng1, lat1, lng2, lat2):
        R = 6371000
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    assigned = 0
    for idx, row in df.iterrows():
        # 只处理 department 为 "市容环卫中心" 的记录
        dept = str(row.get('department', ''))
        if '市容环卫中心' not in dept:
            continue

        lng = row.get('longitude')
        lat = row.get('latitude')
        if pd.isna(lng) or pd.isna(lat):
            continue

        try:
            # 此时坐标已经是GCJ02格式（规则5已执行），需要转换为WGS84
            wgs_lng, wgs_lat = gcj02_to_wgs84(float(lng), float(lat))
        except (ValueError, TypeError):
            continue

        # 精确匹配 - 修改的是department字段，不是district
        matched = False
        for d in districts:
            try:
                if _point_in_polygon(wgs_lng, wgs_lat, d['coords']):
                    df.at[idx, 'department'] = d['name']
                    assigned += 1
                    matched = True
                    break
            except Exception:
                continue

        # 就近匹配
        if not matched:
            min_dist = float('inf')
            nearest_name = None
            for d in districts:
                try:
                    # 计算到片区中心点的距离
                    center_lng = sum(c[0] for c in d['coords'][0]) / len(d['coords'][0])
                    center_lat = sum(c[1] for c in d['coords'][0]) / len(d['coords'][0])
                    dist = haversine_distance(wgs_lng, wgs_lat, center_lng, center_lat)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_name = d['name']
                except Exception:
                    continue

            if nearest_name and min_dist < 10000:  # 10km阈值
                df.at[idx, 'department'] = nearest_name
                assigned += 1

    return df, assigned, f'分配了{assigned}条环卫案件到片区'


def rule_fill_community(df, engine):
    """规则4：所属社区补全 —— 根据坐标就近匹配社区
    策略：先用当前数据中有社区的记录做匹配，再用数据库中的历史数据补充
    """
    def haversine(lng1, lat1, lng2, lat2):
        """计算两点间的球面距离（米）"""
        R = 6371000
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    # 构建参考点列表：(经度, 纬度, 社区名)
    ref_points = []

    # 1. 从当前DataFrame中有社区的记录提取参考点
    for idx, row in df.iterrows():
        community = row.get('community')
        lng = row.get('longitude')
        lat = row.get('latitude')
        if pd.notna(community) and str(community).strip() and pd.notna(lng) and pd.notna(lat):
            try:
                ref_points.append((float(lng), float(lat), str(community).strip()))
            except (ValueError, TypeError):
                continue

    # 2. 从数据库补充历史参考点
    if engine:
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
                for row in result.fetchall():
                    ref_points.append((float(row[1]), float(row[2]), row[0]))
        except Exception as e:
            pass  # 数据库查询失败不影响当前数据匹配

    if not ref_points:
        return df, 0, '无可用社区参考数据'

    # 对缺失社区的记录做就近匹配
    filled = 0
    for idx, row in df.iterrows():
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
        for ref_lng, ref_lat, ref_comm in ref_points:
            try:
                dist = haversine(x, y, ref_lng, ref_lat)
                if dist < min_dist:
                    min_dist = dist
                    best_community = ref_comm
            except (ValueError, TypeError):
                continue

        if best_community and min_dist < 3000:  # 3km阈值
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
    """规则6：监督员规范化 —— 去除姓名周围的多余修饰字符和前缀"""
    if 'supervisor' not in df.columns:
        return df, 0
    original = df['supervisor'].copy()
    df['supervisor'] = df['supervisor'].astype(str).str.strip()
    # 去除"采集员"前缀
    df['supervisor'] = df['supervisor'].str.replace(r'^采集员', '', regex=True)
    # 去除中文/英文括号包裹
    df['supervisor'] = df['supervisor'].str.replace(r'^[（【(\[\s]+', '', regex=True)
    df['supervisor'] = df['supervisor'].str.replace(r'[）】)\]\s]+$', '', regex=True)
    # 处理NaN
    df['supervisor'] = df['supervisor'].replace('nan', pd.NA)
    # 转换为普通字符串比较，避免ArrowDtype类型问题
    changed = (original.fillna('').astype(str) != df['supervisor'].fillna('').astype(str)).sum()
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


def rule_delete_by_area(df):
    """规则8：删除指定所属区域的记录 —— 如运城市绛县"""
    if '原始所属区域' not in df.columns:
        return df, 0

    # 需要删除的区域关键词
    DELETE_AREAS = ['运城市绛县', '绛县']

    def should_delete(x):
        if pd.isna(x):
            return False
        x_str = str(x)
        return any(area in x_str for area in DELETE_AREAS)

    original_count = len(df)
    mask = df['原始所属区域'].apply(should_delete)
    df = df[~mask].reset_index(drop=True)
    deleted = original_count - len(df)

    return df, deleted


# ============================================================
# 延期/返工案件解析
# ============================================================

def parse_delay_rework_txt(text):
    """解析延期/返工/超时案件号txt
    格式示例：
        延期：案件号1、案件号2、案件号3
        返工：案件号4、案件号5
        超时：案件号6、案件号7
    """
    result = {'delayed': [], 'rework': [], 'overtime': []}
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
        elif '超时' in line:
            parts = line.split('：') if '：' in line else line.split(':')
            if len(parts) > 1:
                nums = re.split(r'[、，,\s]+', parts[1])
                result['overtime'] = [n.strip() for n in nums if n.strip().isdigit()]
    return result


def parse_delay_rework_excel(df):
    """从Excel解析延期/返工/超时案件号
    期望格式：两列，一列是任务号，一列是类型（延期/返工/超时）
    """
    result = {'delayed': [], 'rework': [], 'overtime': []}
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
        elif '超时' in case_type:
            result['overtime'].append(task_no)
    return result


def apply_delay_rework(df, delay_task_nos, rework_task_nos, overtime_task_nos=None):
    """根据任务号匹配写入延期/返工/超时标记"""
    task_nos = df['task_no'].astype(str)

    mask_delayed = task_nos.isin(delay_task_nos)
    df.loc[mask_delayed, 'is_delayed'] = 1

    mask_rework = task_nos.isin(rework_task_nos)
    df.loc[mask_rework, 'is_rework'] = 1

    overtime_count = 0
    if overtime_task_nos:
        mask_overtime = task_nos.isin(overtime_task_nos)
        df.loc[mask_overtime, 'is_overtime'] = 1
        overtime_count = int(mask_overtime.sum())

    return df, int(mask_delayed.sum()), int(mask_rework.sum()), overtime_count


# ============================================================
# 清洗主流程
# ============================================================

def run_cleaning(df, rules_config, engine=None, geojson_path=None,
                 delay_task_nos=None, rework_task_nos=None, overtime_task_nos=None):
    """执行清洗主流程
    Args:
        df: 原始DataFrame
        rules_config: 规则开关字典 {rule_name: enabled}
        engine: SQLAlchemy引擎（规则4需要）
        geojson_path: 五大片区GeoJSON路径（规则3需要）
        delay_task_nos: 延期案件任务号列表
        rework_task_nos: 返工案件任务号列表
        overtime_task_nos: 超时案件任务号列表
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

    # 规则5：坐标转换（必须在社区补全之前执行！）
    if rules_config.get('rule5', True):
        df, count, msg = rule_convert_coords(df)
        report['rule5'] = {'name': '坐标转换', 'changed': count, 'message': msg}

    # 规则3b：环卫片区分配（在坐标转换后执行，使用GCJ02坐标）
    sanitation_geojson = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public', 'data', 'guanxia.geojson')
    if rules_config.get('rule3', True) and os.path.exists(sanitation_geojson):
        df, count, msg = rule_assign_sanitation_district(df, sanitation_geojson)
        report['rule3b'] = {'name': '环卫片区分配', 'changed': count, 'message': msg}

    # 规则4：所属社区补全（依赖转换后的坐标）
    if rules_config.get('rule4', True) and engine:
        df, count, msg = rule_fill_community(df, engine)
        report['rule4'] = {'name': '所属社区补全', 'changed': count, 'message': msg}

    # 规则6：监督员规范化
    if rules_config.get('rule6', True):
        df, count = rule_normalize_supervisor(df)
        report['rule6'] = {'name': '监督员规范化', 'changed': count}

    # 规则7：问题描述脱敏
    if rules_config.get('rule7', False):
        df, count = rule_desensitize_description(df)
        report['rule7'] = {'name': '问题描述脱敏', 'changed': count}

    # 规则8：删除指定所属区域（运城市绛县）
    if rules_config.get('rule8', True):
        df, count = rule_delete_by_area(df)
        report['rule8'] = {'name': '删除指定区域', 'changed': count, 'message': f'删除了{count}条运城市绛县的记录'}

    # 延期/返工/超时补充
    if delay_task_nos or rework_task_nos or overtime_task_nos:
        df, d_count, r_count, o_count = apply_delay_rework(
            df, delay_task_nos or [], rework_task_nos or [], overtime_task_nos or []
        )
        report['delay_rework'] = {
            'name': '延期/返工/超时补充',
            'delayed_matched': d_count,
            'rework_matched': r_count,
            'overtime_matched': o_count
        }

    return df, report
