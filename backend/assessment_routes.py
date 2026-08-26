# -*- coding: utf-8 -*-
"""考核计分路由模块 - 部门/片区考核得分计算"""
import logging
from flask import request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required

# ============================================================
# 部门分组映射规则
# ============================================================
DEPT_GROUP_RULES = {
    '执法队': lambda d: '执法' in d,
    '市容环卫中心': lambda d: '环卫' in d,
    '园林绿化服务中心': lambda d: '园林' in d or '公园' in d or '广场' in d,
    '市政公用服务中心': lambda d: '市政' in d or '照明' in d,
}

# 执法分队映射（department -> 分队名称）
DISPATCH_TEAM_MAP = {
    '姚孟执法分队': '姚孟执法分队',
    '大渠执法分队': '大渠执法分队',
    '执法西片区': '西城执法分队',
    '执法南片区': '南城执法分队',
    '执法北片区': '北城执法分队',
    '执法中片区': '中城执法分队',
    '执法东片区': '东城执法分队',
    '安邑执法分队': '安邑执法分队',
}

# 园林片区映射（department -> 片区名称）
GARDEN_DISTRICT_MAP = {
    '园林东片区': '园林东片区',
    '园林中片区': '园林中片区',
    '园林北片区': '园林北片区',
    '园林南片区': '园林南片区',
    '园林西片区': '园林西片区',
}

# 公园广场映射
PARK_MAP = {
    '人民公园': '人民公园',
    '体育公园': '体育公园',
    '南风广场': '南风广场',
    '天逸公园': '天逸公园',
    '圣惠公园': '圣惠公园',
    '禹都公园': '禹都公园',
    '航天公园': '航天公园',
}

# 市政子单位映射
MUNICIPAL_UNIT_MAP = {
    '城市照明服务中心': '城市照明部',
    '市政设施维护队': '市政设施维护部',
    '排水服务中心': '排水服务中心',
    '应急执法分队': '应急执法分队',
}


def register_assessment_routes(app, engine=None, protected=None, admin_required=None):
    """注册考核计分相关路由"""
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    @app.route('/api/assessment/months', methods=['GET'])
    @protected
    def assessment_months():
        """获取可选月份列表"""
        try:
            if not engine:
                return jsonify({'success': True, 'months': []})
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT upload_batch, COUNT(*) as count "
                    "FROM case_data GROUP BY upload_batch ORDER BY upload_batch DESC"
                ))
                months = [
                    {'batch': row[0], 'count': row[1]}
                    for row in result.fetchall()
                ]
            return jsonify({'success': True, 'months': months})
        except Exception as e:
            logger.error(f"获取月份列表失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/assessment/summary', methods=['GET'])
    @protected
    def assessment_summary():
        """获取指定月份的考核统计数据"""
        batch = request.args.get('batch', '').strip()
        if not batch:
            return jsonify({'success': False, 'error': '请指定月份'}), 400

        try:
            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            with engine.connect() as conn:
                # 1. 按部门统计
                dept_stats = conn.execute(text("""
                    SELECT
                        department,
                        COUNT(*) as total,
                        SUM(CASE WHEN stage = '[办结]' THEN 1 ELSE 0 END) as closed,
                        SUM(CASE WHEN is_overtime = 1 THEN 1 ELSE 0 END) as overtime,
                        SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) as delayed_count,
                        SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) as rework
                    FROM case_data
                    WHERE upload_batch = :batch
                    GROUP BY department
                """), {'batch': batch}).fetchall()

                # 2. 整理部门数据
                departments = {}
                for row in dept_stats:
                    dept_name = row[0] or '未知'
                    departments[dept_name] = {
                        'total': row[1],
                        'closed': row[2],
                        'overtime': row[3],
                        'delayed': row[4],
                        'rework': row[5]
                    }

                # 3. 按考核部门分组汇总
                dept_groups = _group_departments(departments)

                # 4. 执法分队明细
                dispatch_teams = _get_dispatch_teams(departments)

                # 5. 环卫片区明细
                sanitation_districts = _get_sanitation_districts(departments)

                # 6. 园林片区明细（不含公园）
                garden_districts = _get_garden_districts(departments)

                # 7. 公园广场明细
                parks = _get_parks(departments)

                # 8. 市政子单位明细
                municipal_units = _get_municipal_units(departments)

            return jsonify({
                'success': True,
                'batch': batch,
                'dept_groups': dept_groups,
                'dispatch_teams': dispatch_teams,
                'sanitation_districts': sanitation_districts,
                'garden_districts': garden_districts,
                'parks': parks,
                'municipal_units': municipal_units
            })
        except Exception as e:
            logger.error(f"获取考核统计失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/assessment/calculate', methods=['POST'])
    @protected
    def assessment_calculate():
        """计算考核得分"""
        try:
            data = request.get_json(silent=True) or {}
            batch = data.get('batch', '').strip()
            external_data = data.get('external_data', {})

            if not batch:
                return jsonify({'success': False, 'error': '请指定月份'}), 400

            if not engine:
                return jsonify({'success': False, 'error': '数据库未连接'}), 500

            # 获取统计数据
            with engine.connect() as conn:
                dept_stats = conn.execute(text("""
                    SELECT
                        department,
                        COUNT(*) as total,
                        SUM(CASE WHEN stage = '[办结]' THEN 1 ELSE 0 END) as closed,
                        SUM(CASE WHEN is_overtime = 1 THEN 1 ELSE 0 END) as overtime,
                        SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) as delayed_count,
                        SUM(CASE WHEN is_rework = 1 THEN 1 ELSE 0 END) as rework
                    FROM case_data
                    WHERE upload_batch = :batch
                    GROUP BY department
                """), {'batch': batch}).fetchall()

                departments = {}
                for row in dept_stats:
                    departments[row[0] or '未知'] = {
                        'total': int(row[1]), 'closed': int(row[2]),
                        'overtime': int(row[3]), 'delayed': int(row[4]), 'rework': int(row[5])
                    }

            # 计算各部门得分
            results = _calculate_scores(departments, external_data)

            return jsonify({
                'success': True,
                'batch': batch,
                'results': results
            })
        except Exception as e:
            logger.error(f"计算考核得分失败: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


def _group_departments(departments):
    """按考核部门分组汇总"""
    # 独立部门列表（不参与分组，单独列出）
    INDEPENDENT_DEPTS = [
        '市容秩序科', '排水服务中心', '城市节约用水中心',
        '建筑垃圾资源利用服务中心', '市集中供热供气服务中心'
    ]

    groups = {}
    for dept_name, stats in departments.items():
        # 独立部门单独列出
        if dept_name in INDEPENDENT_DEPTS:
            groups[dept_name] = stats
            continue

        # 其他部门按规则分组
        group_name = '其他'
        for gname, rule in DEPT_GROUP_RULES.items():
            if rule(dept_name):
                group_name = gname
                break

        if group_name not in groups:
            groups[group_name] = {'total': 0, 'closed': 0, 'overtime': 0, 'delayed': 0, 'rework': 0}
        for key in ['total', 'closed', 'overtime', 'delayed', 'rework']:
            groups[group_name][key] += stats[key]

    return groups


def _get_dispatch_teams(departments):
    """获取执法分队明细"""
    teams = {}
    for dept_name, stats in departments.items():
        if dept_name in DISPATCH_TEAM_MAP:
            team_name = DISPATCH_TEAM_MAP[dept_name]
            teams[team_name] = stats
    return teams


def _get_sanitation_districts(departments):
    """获取环卫片区明细"""
    districts = {}
    for dept_name, stats in departments.items():
        if '环卫' in dept_name:
            districts[dept_name] = stats
    return districts


def _get_garden_districts(departments):
    """获取园林片区明细（不含公园）"""
    districts = {}
    for dept_name, stats in departments.items():
        if dept_name in GARDEN_DISTRICT_MAP:
            districts[dept_name] = stats
    return districts


def _get_parks(departments):
    """获取公园广场明细"""
    parks = {}
    for dept_name, stats in departments.items():
        if dept_name in PARK_MAP:
            parks[dept_name] = stats
    return parks


def _get_municipal_units(departments):
    """获取市政子单位明细"""
    units = {}
    for dept_name, stats in departments.items():
        if dept_name in MUNICIPAL_UNIT_MAP:
            unit_name = MUNICIPAL_UNIT_MAP[dept_name]
            units[unit_name] = stats
    return units


def _calculate_system_score(total, closed, overtime, delayed, rework, extra_points=0):
    """计算系统考核得分
    公式：(按期结案率×100% + 超期结案率×40%) × 80% + (1-延期率) × 10% + (1-返工率) × 10% ± 加减分项
    """
    if total == 0:
        return 0

    # 结案率
    close_rate = closed / total

    # 超期结案率 = 超期数 / 应结案数
    overtime_rate = overtime / total

    # 按期结案率 = (结案数 - 超期数) / 应结案数
    ontime_rate = max(0, (closed - overtime)) / total

    # 延期率
    delay_rate = delayed / total

    # 返工率
    rework_rate = rework / total

    # 系统考核得分
    score = (ontime_rate * 100 + overtime_rate * 40) * 0.8 + \
            (1 - delay_rate) * 10 + \
            (1 - rework_rate) * 10 + \
            extra_points

    return round(score, 3)


def _calculate_scores(departments, external_data):
    """计算各部门考核得分"""
    results = {}

    # 执法队
    dispatch_total = sum(
        departments.get(d, {}).get('total', 0) for d in DISPATCH_TEAM_MAP.keys()
    )
    dispatch_closed = sum(
        departments.get(d, {}).get('closed', 0) for d in DISPATCH_TEAM_MAP.keys()
    )
    dispatch_overtime = sum(
        departments.get(d, {}).get('overtime', 0) for d in DISPATCH_TEAM_MAP.keys()
    )
    dispatch_delayed = sum(
        departments.get(d, {}).get('delayed', 0) for d in DISPATCH_TEAM_MAP.keys()
    )
    dispatch_rework = sum(
        departments.get(d, {}).get('rework', 0) for d in DISPATCH_TEAM_MAP.keys()
    )

    dispatch_extra = external_data.get('dispatch_extra', 0)
    dispatch_team_score = external_data.get('dispatch_team_score', 100)
    dispatch_street_score = external_data.get('dispatch_street_score', 100)

    dispatch_system_score = _calculate_system_score(
        dispatch_total, dispatch_closed, dispatch_overtime,
        dispatch_delayed, dispatch_rework, dispatch_extra
    )
    dispatch_final_score = dispatch_system_score * 0.7 + dispatch_team_score * 0.15 + dispatch_street_score * 0.15

    results['执法队'] = {
        'total': dispatch_total,
        'closed': dispatch_closed,
        'overtime': dispatch_overtime,
        'delayed': dispatch_delayed,
        'rework': dispatch_rework,
        'system_score': dispatch_system_score,
        'team_score': dispatch_team_score,
        'street_score': dispatch_street_score,
        'extra_points': dispatch_extra,
        'final_score': round(dispatch_final_score, 3)
    }

    # 执法分队明细
    for dept_key, team_name in DISPATCH_TEAM_MAP.items():
        stats = departments.get(dept_key, {'total': 0, 'closed': 0, 'overtime': 0, 'delayed': 0, 'rework': 0})
        team_extra = external_data.get(f'dispatch_{team_name}_extra', 0)
        team_score = external_data.get(f'dispatch_{team_name}_team_score', 100)
        street_score = external_data.get(f'dispatch_{team_name}_street_score', 100)

        sys_score = _calculate_system_score(
            stats['total'], stats['closed'], stats['overtime'],
            stats['delayed'], stats['rework'], team_extra
        )
        final = sys_score * 0.7 + team_score * 0.15 + street_score * 0.15

        results[team_name] = {
            **stats,
            'system_score': sys_score,
            'team_score': team_score,
            'street_score': street_score,
            'extra_points': team_extra,
            'final_score': round(final, 3)
        }

    # 环卫
    san_total = sum(
        departments.get(d, {}).get('total', 0) for d in departments if '环卫' in d
    )
    san_closed = sum(
        departments.get(d, {}).get('closed', 0) for d in departments if '环卫' in d
    )
    san_overtime = sum(
        departments.get(d, {}).get('overtime', 0) for d in departments if '环卫' in d
    )
    san_delayed = sum(
        departments.get(d, {}).get('delayed', 0) for d in departments if '环卫' in d
    )
    san_rework = sum(
        departments.get(d, {}).get('rework', 0) for d in departments if '环卫' in d
    )

    san_extra = external_data.get('san_extra', 0)
    san_garbage_count = external_data.get('san_garbage_count', 0)
    san_center_score = external_data.get('san_center_score', 100)

    san_system_score = _calculate_system_score(
        san_total, san_closed, san_overtime,
        san_delayed, san_rework, san_extra
    )
    san_garbage_score = max(0, 100 - san_garbage_count * 0.01)
    san_final_score = san_system_score * 0.3 + san_garbage_score * 0.3 + san_center_score * 0.4

    results['市容环卫中心'] = {
        'total': san_total,
        'closed': san_closed,
        'overtime': san_overtime,
        'delayed': san_delayed,
        'rework': san_rework,
        'system_score': san_system_score,
        'garbage_score': round(san_garbage_score, 2),
        'garbage_count': san_garbage_count,
        'center_score': san_center_score,
        'extra_points': san_extra,
        'final_score': round(san_final_score, 2)
    }

    # 环卫片区明细
    for dept_name, stats in departments.items():
        if '环卫' in dept_name:
            district_extra = external_data.get(f'san_{dept_name}_extra', 0)
            district_garbage = external_data.get(f'san_{dept_name}_garbage', 0)
            district_center = external_data.get(f'san_{dept_name}_center', 100)

            sys_score = _calculate_system_score(
                stats['total'], stats['closed'], stats['overtime'],
                stats['delayed'], stats['rework'], district_extra
            )
            garbage_score = max(0, 100 - district_garbage * 0.01)
            final = sys_score * 0.3 + garbage_score * 0.3 + district_center * 0.4

            results[dept_name] = {
                **stats,
                'system_score': sys_score,
                'garbage_score': round(garbage_score, 2),
                'garbage_count': district_garbage,
                'center_score': district_center,
                'extra_points': district_extra,
                'final_score': round(final, 2)
            }

    # 园林
    garden_total = sum(
        departments.get(d, {}).get('total', 0) for d in GARDEN_DISTRICT_MAP.keys() if d in departments
    )
    garden_closed = sum(
        departments.get(d, {}).get('closed', 0) for d in GARDEN_DISTRICT_MAP.keys() if d in departments
    )
    garden_overtime = sum(
        departments.get(d, {}).get('overtime', 0) for d in GARDEN_DISTRICT_MAP.keys() if d in departments
    )
    garden_delayed = sum(
        departments.get(d, {}).get('delayed', 0) for d in GARDEN_DISTRICT_MAP.keys() if d in departments
    )
    garden_rework = sum(
        departments.get(d, {}).get('rework', 0) for d in GARDEN_DISTRICT_MAP.keys() if d in departments
    )

    garden_extra = external_data.get('garden_extra', 0)
    garden_center_score = external_data.get('garden_center_score', 100)

    garden_system_score = _calculate_system_score(
        garden_total, garden_closed, garden_overtime,
        garden_delayed, garden_rework, garden_extra
    )
    garden_final_score = garden_system_score * 0.7 + garden_center_score * 0.3

    results['园林绿化服务中心'] = {
        'total': garden_total,
        'closed': garden_closed,
        'overtime': garden_overtime,
        'delayed': garden_delayed,
        'rework': garden_rework,
        'system_score': garden_system_score,
        'center_score': garden_center_score,
        'extra_points': garden_extra,
        'final_score': round(garden_final_score, 2)
    }

    # 园林片区明细
    for dept_name in GARDEN_DISTRICT_MAP.keys():
        if dept_name in departments:
            stats = departments[dept_name]
            district_extra = external_data.get(f'garden_{dept_name}_extra', 0)
            district_center = external_data.get(f'garden_{dept_name}_center', 100)

            sys_score = _calculate_system_score(
                stats['total'], stats['closed'], stats['overtime'],
                stats['delayed'], stats['rework'], district_extra
            )
            final = sys_score * 0.7 + district_center * 0.3

            results[dept_name] = {
                **stats,
                'system_score': sys_score,
                'center_score': district_center,
                'extra_points': district_extra,
                'final_score': round(final, 2)
            }

    # 公园广场明细
    for dept_name in PARK_MAP.keys():
        if dept_name in departments:
            stats = departments[dept_name]
            park_extra = external_data.get(f'garden_{dept_name}_extra', 0)
            park_center = external_data.get(f'garden_{dept_name}_center', 100)

            sys_score = _calculate_system_score(
                stats['total'], stats['closed'], stats['overtime'],
                stats['delayed'], stats['rework'], park_extra
            )
            final = sys_score * 0.7 + park_center * 0.3

            results[dept_name] = {
                **stats,
                'system_score': sys_score,
                'center_score': park_center,
                'extra_points': park_extra,
                'final_score': round(final, 2)
            }

    # 市政
    muni_total = sum(
        departments.get(d, {}).get('total', 0) for d in MUNICIPAL_UNIT_MAP.keys()
    )
    muni_closed = sum(
        departments.get(d, {}).get('closed', 0) for d in MUNICIPAL_UNIT_MAP.keys()
    )
    muni_overtime = sum(
        departments.get(d, {}).get('overtime', 0) for d in MUNICIPAL_UNIT_MAP.keys()
    )
    muni_delayed = sum(
        departments.get(d, {}).get('delayed', 0) for d in MUNICIPAL_UNIT_MAP.keys()
    )
    muni_rework = sum(
        departments.get(d, {}).get('rework', 0) for d in MUNICIPAL_UNIT_MAP.keys()
    )

    muni_extra = external_data.get('muni_extra', 0)
    muni_system_score = _calculate_system_score(
        muni_total, muni_closed, muni_overtime,
        muni_delayed, muni_rework, muni_extra
    )

    results['市政公用服务中心'] = {
        'total': muni_total,
        'closed': muni_closed,
        'overtime': muni_overtime,
        'delayed': muni_delayed,
        'rework': muni_rework,
        'system_score': muni_system_score,
        'extra_points': muni_extra,
        'final_score': muni_system_score
    }

    # 市政子单位明细
    for dept_name, unit_name in MUNICIPAL_UNIT_MAP.items():
        if dept_name in departments:
            stats = departments[dept_name]
            unit_extra = external_data.get(f'muni_{unit_name}_extra', 0)

            sys_score = _calculate_system_score(
                stats['total'], stats['closed'], stats['overtime'],
                stats['delayed'], stats['rework'], unit_extra
            )

            results[unit_name] = {
                **stats,
                'system_score': sys_score,
                'extra_points': unit_extra,
                'final_score': sys_score
            }

    # 其他独立部门
    for dept_name in ['市容秩序科', '排水服务中心', '城市节约用水中心',
                      '建筑垃圾资源利用服务中心', '市集中供热供气服务中心']:
        if dept_name in departments:
            stats = departments[dept_name]
            dept_extra = external_data.get(f'{dept_name}_extra', 0)

            sys_score = _calculate_system_score(
                stats['total'], stats['closed'], stats['overtime'],
                stats['delayed'], stats['rework'], dept_extra
            )

            results[dept_name] = {
                **stats,
                'system_score': sys_score,
                'extra_points': dept_extra,
                'final_score': sys_score
            }

    return results
