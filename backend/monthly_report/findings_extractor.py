# -*- coding: utf-8 -*-
"""规则引擎：从 analysis.json 提取结构化发现，供 LLM 生成第7、8章"""
import json
import os


def extract_findings(analysis_json_path):
    """从 analysis.json 提取结构化发现列表"""
    with open(analysis_json_path, encoding='utf-8') as f:
        d = json.load(f)

    B = d.get('basis', {})
    E = d.get('eff', {})
    R = d.get('recur', {})
    I = d.get('insight', {})
    T = d.get('time', {})
    findings = []
    total = B.get('total', 0)

    # 1. 超时
    ot = E.get('overtime', {})
    if ot.get('n'):
        top_dept = ot.get('by_dept', [])[:3]
        dept_str = '、'.join(f'{r[0]}（{r[2]}件）' for r in top_dept if r[2] > 0)
        findings.append({
            'category': '超时', 'severity': 'warning' if ot.get('rate', 0) > 2 else 'info',
            'metric': {'n': ot['n'], 'rate': ot.get('rate', 0)},
            'detail': f"超时{ot['n']}件（{ot.get('rate', 0)}%）" + (f"，集中在{dept_str}" if dept_str else '')
        })

    # 2. 延期+返工
    dl = E.get('delay', {})
    rw = E.get('rework', {})
    if dl.get('n') or rw.get('n'):
        combined = (dl.get('n', 0) or 0) + (rw.get('n', 0) or 0)
        findings.append({
            'category': '延返', 'severity': 'info',
            'metric': {'delay': dl.get('n', 0), 'rework': rw.get('n', 0)},
            'detail': f"延期{dl.get('n', 0)}件、返工{rw.get('n', 0)}件，合计占{combined / total * 100:.1f}%"
        })

    # 3. 复发
    if R.get('ge3_n'):
        top_xl = R.get('by_xl', [])[:3]
        xl_str = '、'.join(f'{r[0]}{r[1]}组' for r in top_xl)
        severity = 'alert' if R.get('ge3_rate', 0) > 30 else ('warning' if R.get('ge3_rate', 0) > 20 else 'info')
        findings.append({
            'category': '复发', 'severity': severity,
            'metric': {'ge3_n': R['ge3_n'], 'ge3_cases': R.get('ge3_cases'), 'ge3_rate': R.get('ge3_rate')},
            'detail': f"≥3件复发组{R['ge3_n']}组涉{R.get('ge3_cases')}件（{R.get('ge3_rate')}%）"
                      + (f"，{xl_str}居前" if xl_str else '')
        })

    # 4. 处置效率——同类部门互比（不跨类型比较）
    dur = E.get('dur', {})
    if dur.get('p50'):
        GROUP_PREFIX = ['环卫', '园林', '执法']
        groups = {}
        for r in E.get('dept', []):
            name = r[0]
            for prefix in GROUP_PREFIX:
                if name.startswith(prefix):
                    groups.setdefault(prefix, []).append(r)
                    break
        anomalies = []
        for prefix, members in groups.items():
            if len(members) < 2:
                continue
            vals = sorted([m[2] for m in members])
            group_median = vals[len(vals) // 2]
            for name, cnt, med in members:
                if med > group_median * 2 and med > 3:
                    anomalies.append((name, cnt, med, prefix, group_median))
        if anomalies:
            anomalies.sort(key=lambda x: -x[2])
            anom_str = '、'.join(
                f'{a[0]}（{a[2]}小时，{a[1]}件，同类中位{a[4]}小时）'
                for a in anomalies
            )
            findings.append({
                'category': '效率', 'severity': 'warning',
                'metric': {'p50': dur['p50']},
                'detail': f"全平台中位处置{dur['p50']}小时，同类部门内偏高：{anom_str}"
            })
        else:
            findings.append({
                'category': '效率', 'severity': 'info',
                'metric': {'p50': dur['p50']},
                'detail': f"全平台中位处置{dur['p50']}小时，各类部门内部差异在正常范围"
            })

    # 5. 政务渠道
    if I.get('src_gov'):
        gov_dur = I.get('gov_dur', {})
        findings.append({
            'category': '来源', 'severity': 'info',
            'metric': {'gov_n': I['src_gov'], 'gov_rate': I.get('src_gov_rate')},
            'detail': f"政务渠道{I['src_gov']}件（{I.get('src_gov_rate')}%）"
                      + (f"，中位用时{gov_dur.get('p50', '?')}小时" if gov_dur.get('p50') else '')
        })

    # 6. 采集员
    if I.get('sup_n'):
        findings.append({
            'category': '采集', 'severity': 'info',
            'metric': {'sup_n': I['sup_n'], 'cv': I.get('sup_cv')},
            'detail': f"{I['sup_n']}名专职采集员，变异系数{I.get('sup_cv')}%"
        })

    # 7. 地址质量
    if I.get('no_addr'):
        severity = 'warning' if I.get('no_addr_rate', 0) > 10 else 'info'
        findings.append({
            'category': '地址', 'severity': severity,
            'metric': {'no_addr': I['no_addr'], 'rate': I.get('no_addr_rate')},
            'detail': f"地址缺失{I['no_addr']}件（{I.get('no_addr_rate')}%）"
        })

    # 8. 异常日
    anomalies_data = B.get('anomaly', [])
    if anomalies_data:
        days_str = '、'.join(f"{a[0][5:]}日（{a[1]}件，{a[2]}）" for a in anomalies_data)
        findings.append({
            'category': '异常', 'severity': 'info',
            'metric': {'n': len(anomalies_data)},
            'detail': f"本月{len(anomalies_data)}个异常采集日：{days_str}"
        })

    return findings


def extract_key_metrics(d):
    """提取关键指标摘要（给 LLM 参考，不生成）"""
    B = d.get('basis', {})
    E = d.get('eff', {})
    R = d.get('recur', {})
    I = d.get('insight', {})
    S = d.get('std', {})
    return {
        'total': B.get('total'),
        'closed': B.get('closed'),
        'close_rate': B.get('close_rate'),
        'overtime_n': (E.get('overtime') or {}).get('n'),
        'overtime_rate': (E.get('overtime') or {}).get('rate'),
        'delay_n': (E.get('delay') or {}).get('n'),
        'rework_n': (E.get('rework') or {}).get('n'),
        'dur_p50': (E.get('dur') or {}).get('p50'),
        'ge3_n': R.get('ge3_n'),
        'ge3_cases': R.get('ge3_cases'),
        'ge3_rate': R.get('ge3_rate'),
        'hot_n': R.get('hot_n'),
        'std_n_xl': S.get('n_xl'),
        'no_addr': I.get('no_addr'),
        'no_addr_rate': I.get('no_addr_rate'),
        'sup_n': I.get('sup_n'),
        'src_gov': I.get('src_gov'),
    }
