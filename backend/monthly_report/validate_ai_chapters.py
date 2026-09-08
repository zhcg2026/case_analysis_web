# -*- coding: utf-8 -*-
"""AI 章节效果验证脚本（独立运行，不改线上代码）
用法：python validate_ai_chapters.py [analysis.json路径]
默认使用8月数据
"""
import json
import os
import sys
import requests

# API 配置从环境变量读取
API_KEY = os.getenv('DOUBAO_API_KEY', '')
API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
MODEL = os.getenv('DOUBAO_MODEL', 'deepseek-v4-flash-ga-260731')


def extract_findings(d):
    """规则引擎：从 analysis.json 提取结构化发现"""
    B = d.get('basis', {})
    E = d.get('eff', {})
    R = d.get('recur', {})
    I = d.get('insight', {})
    S = d.get('std', {})
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
            'detail': f"超时{ot['n']}件（{ot.get('rate',0)}%）" + (f"，集中在{dept_str}" if dept_str else '')
        })

    # 2. 延期+返工
    dl = E.get('delay', {})
    rw = E.get('rework', {})
    if dl.get('n') or rw.get('n'):
        combined = (dl.get('n', 0) or 0) + (rw.get('n', 0) or 0)
        findings.append({
            'category': '延返', 'severity': 'info',
            'metric': {'delay': dl.get('n', 0), 'rework': rw.get('n', 0)},
            'detail': f"延期{dl.get('n',0)}件、返工{rw.get('n',0)}件，合计占{combined/total*100:.1f}%"
        })

    # 3. 复发
    if R.get('ge3_n'):
        top_xl = R.get('by_xl', [])[:3]
        xl_str = '、'.join(f'{r[0]}{r[1]}组' for r in top_xl)
        severity = 'alert' if R.get('ge3_rate', 0) > 30 else ('warning' if R.get('ge3_rate', 0) > 20 else 'info')
        findings.append({
            'category': '复发', 'severity': severity,
            'metric': {'ge3_n': R['ge3_n'], 'ge3_cases': R.get('ge3_cases'), 'ge3_rate': R.get('ge3_rate')},
            'detail': f"≥3件复发组{R['ge3_n']}组涉{R.get('ge3_cases')}件（{R.get('ge3_rate')}%）" + (f"，{xl_str}居前" if xl_str else '')
        })

    # 4. 处置效率——同类部门互比（不跨类型比较）
    dur = E.get('dur', {})
    if dur.get('p50'):
        import re
        # 按部门名称前缀分组（环卫/园林/执法/市政/照明/排水/市容）
        GROUP_PREFIX = ['环卫', '园林', '执法']
        groups = {}
        for r in E.get('dept', []):
            name, cnt, med = r
            matched = False
            for prefix in GROUP_PREFIX:
                if name.startswith(prefix):
                    groups.setdefault(prefix, []).append(r)
                    matched = True
                    break
            # 独立类型（市政、照明、排水、市容等）不参与组内比较
        # 组内找异常：中位时长 > 组内中位值2倍的部门
        anomalies = []
        for prefix, members in groups.items():
            if len(members) < 2:
                continue
            vals = sorted([m[2] for m in members])
            group_median = vals[len(vals)//2]
            for name, cnt, med in members:
                if med > group_median * 2 and med > 3:  # 且>3小时（排除小时级的正常波动）
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
            'detail': f"政务渠道{I['src_gov']}件（{I.get('src_gov_rate')}%）" +
                      (f"，中位用时{gov_dur.get('p50', '?')}小时" if gov_dur.get('p50') else '')
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
    anomalies = B.get('anomaly', [])
    if anomalies:
        days_str = '、'.join(f"{a[0][5:]}日（{a[1]}件，{a[2]}）" for a in anomalies)
        findings.append({
            'category': '异常', 'severity': 'info',
            'metric': {'n': len(anomalies)},
            'detail': f"本月{len(anomalies)}个异常采集日：{days_str}"
        })

    return findings


def build_prompt(findings, key_metrics, month='2026年8月'):
    """构建 LLM prompt"""
    findings_text = '\n'.join(
        f"- [{f['category']}] {f['detail']}" for f in findings
    )
    metrics_text = json.dumps(key_metrics, ensure_ascii=False)

    return f"""你是城市管理案件分析报告的撰写助手。请根据以下数据发现，撰写月度分析报告的两个章节。

## 数据发现（由规则引擎从{month}案件数据中提取）
{findings_text}

## 关键指标
{metrics_text}

## 输出要求

### 第七章 数据特征归纳
总结本月数据的3-5个核心特征，每个特征一段话（2-3句）。
- 数字必须与上方数据完全一致，不要自行计算或修改
- 分析数据之间的关联（如超时集中在某部门→可能的原因）
- 指出值得关注的趋势或异常

### 第八章 工作建议
基于上述特征提出3-5条具体建议，每条一段话（2-3句）。
- 每条建议要对应一个具体的数据发现
- 建议要具体可操作，不要泛泛而谈
- 使用政务公文风格

### 格式要求
- 直接输出正文，不要加章节标题（标题由系统生成）
- 每段之间空一行
- 不要加序号、不要加"第七章"等标题前缀
- 不要输出markdown格式"""


def call_llm(prompt):
    """调用豆包 API"""
    if not API_KEY:
        raise RuntimeError('DOUBAO_API_KEY 未配置')

    resp = requests.post(
        API_URL,
        headers={
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': MODEL,
            'messages': [
                {'role': 'system', 'content': '你是城市管理案件分析报告的撰写助手，擅长政务公文写作。'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 2000
        },
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def split_chapters(text):
    """将 LLM 输出拆分为第7章和第8章"""
    # 尝试按常见分隔标记拆分
    markers = ['第八章', '工作建议', '八、工作建议']
    for marker in markers:
        idx = text.find(marker)
        if idx > 0:
            ch7 = text[:idx].strip()
            ch8 = text[idx:].strip()
            # 去掉开头的章节标题行
            for prefix in ['第七章', '数据特征归纳', '七、数据特征归纳']:
                if ch7.startswith(prefix):
                    ch7 = ch7[len(prefix):].lstrip('：: \n')
            for prefix in markers:
                if ch8.startswith(prefix):
                    ch8 = ch8[len(prefix):].lstrip('：: \n')
            return ch7, ch8
    # 拆分失败，整段作为第7章
    return text.strip(), ''


def main():
    json_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not json_path:
        # 默认查找 work/202608/analysis.json
        base = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base, 'work', '202608', 'analysis.json')

    if not os.path.exists(json_path):
        print(f'!! 找不到 {json_path}，请先运行流水线生成 analysis.json')
        sys.exit(1)

    print(f'读取: {json_path}')
    with open(json_path, encoding='utf-8') as f:
        d = json.load(f)

    findings = extract_findings(d)
    print(f'\n=== 规则引擎提取了 {len(findings)} 条发现 ===')
    for f in findings:
        print(f"  [{f['category']}] {f['detail']}")

    key_metrics = {
        'total': d['basis']['total'],
        'closed': d['basis']['closed'],
        'close_rate': d['basis']['close_rate'],
        'overtime_n': d['eff']['overtime']['n'],
        'overtime_rate': d['eff']['overtime']['rate'],
        'delay_n': d['eff']['delay']['n'],
        'rework_n': d['eff']['rework']['n'],
        'dur_p50': d['eff']['dur']['p50'],
        'ge3_n': d['recur']['ge3_n'],
        'ge3_cases': d['recur']['ge3_cases'],
        'ge3_rate': d['recur']['ge3_rate'],
        'hot_n': d['recur']['hot_n'],
        'std_n_xl': d['std']['n_xl'],
        'no_addr': d['insight']['no_addr'],
        'no_addr_rate': d['insight']['no_addr_rate'],
        'sup_n': d['insight']['sup_n'],
        'src_gov': d['insight']['src_gov'],
    }

    prompt = build_prompt(findings, key_metrics)
    print(f'\n=== 调用 LLM ({MODEL}) ===')
    print(f'Prompt 长度: {len(prompt)} 字符')

    try:
        result = call_llm(prompt)
    except Exception as e:
        print(f'\n!! LLM 调用失败: {e}')
        print('\n=== Fallback：规则引擎 bullets ===')
        for f in findings:
            print(f"• {f['detail']}")
        sys.exit(1)

    print('\n=== LLM 原始输出 ===')
    print(result)

    ch7, ch8 = split_chapters(result)
    print('\n' + '=' * 60)
    print('=== 第七章 数据特征归纳 ===')
    print(ch7)
    print('\n=== 第八章 工作建议 ===')
    print(ch8)


if __name__ == '__main__':
    main()
