# -*- coding: utf-8 -*-
"""月度城市管理案件数据分析（通用版，v3 口径）
用法：python analyze.py <config.json>
口径：
  1. 考核口径 = 处置截止时间在本月的案件（含上报于往月、经延期后截止落在本月的挂账案件）
  2. 结案判定 = 当前阶段名称 [办结]
  3. 超时/延期/返工 = 对应字段（is_overtime / 延期案件 / 返工案件）；
     超时以 is_overtime 字段认定（平台已认定口径）；处置截止时间数据质量不佳，不作为超时判定依据
  4. 法定考核时限 = 来自《立案、处置和结案标准》的小类固定时限，用于说明各小类考核要求，不用于反推超时
  5. 监督员分析仅纳入采集量 ≥ min_cases_supervisor 件的专职人员
  6. 复发识别 v3：以问题描述点位签名为核心 + 坐标 R 米圆确认 + 地址描述仅作参考；剔除单位默认地址
  7. 时段分析对照配置的作业时间窗，节假日不休息
"""
import json, re, math, os, sys
from collections import defaultdict, Counter
import pandas as pd
import numpy as np

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
os.makedirs(BASE, exist_ok=True)


def _p(*a):
    return os.path.join(BASE, *a)


MONTH = CFG.get('month', '2026-08')
_y, _m = int(MONTH[:4]), int(MONTH[5:7])
M0 = MONTH + '-01'
M1 = ('%04d-%02d-01' % (_y + 1, 1)) if _m == 12 else ('%04d-%02d-01' % (_y, _m + 1))

SRC = CFG.get('src', '案件数据.xlsx')
if not os.path.isabs(SRC):
    SRC = _p(SRC)
OUT = _p(CFG.get('out_json', 'analysis.json'))
R_METER = CFG.get('recur_radius_m', 50)     # 复发聚类距离阈值（米）
LAT_M = 110540.0
LON_M = 111320.0 * math.cos(math.radians(CFG.get('lat', 35.03)))

POI_RE = re.compile(r'^(.*?)的(?:正东|正西|正南|正北|东北|东南|西北|西南|东|西|南|北)方向[\d.]+米$')
NEAR_RE = re.compile(r'^(.*?)的附近$')
ALT_RE = re.compile(r'^(.*?)[(（](?:正东|正西|正南|正北|东北|东南|西北|西南|东|西|南|北)[)）]$')
NO_ADDR = {'无位置描述', '没有相关位置描述', 'nan', ''}

df = pd.read_excel(SRC)
df.columns = [c.strip() for c in df.columns]
for c in ['上报时间', '结案时间', '处置截止时间', '捆绑处置截止时间']:
    df[c] = pd.to_datetime(df[c])

df['阶段'] = df['当前阶段名称'].astype(str).str.strip()
df['已办结'] = df['阶段'] == '[办结]'
df['片区'] = df['所属片区'].fillna('未标注')
df['街道'] = df['所属街道'].fillna('未标注')
df['社区'] = df['所属社区'].fillna('未标注')
df['部门'] = df['处置部门'].fillna('未派发')
df['监督员'] = df['监督员'].fillna('无（非采集员渠道）')
df['时长h'] = (df['结案时间'] - df['上报时间']).dt.total_seconds() / 3600
df['期限h'] = (df['处置截止时间'] - df['上报时间']).dt.total_seconds() / 3600
df['日期'] = df['上报时间'].dt.date

TOTAL = len(df)
CLOSED = int(df['已办结'].sum())
UNCLOSED = TOTAL - CLOSED
DUR = df[df['时长h'].notna()].copy()
import json as _json
try:
    STD = _json.load(open(_p('std_limits.json'), encoding='utf-8'))
except Exception:
    STD = {}
AUG = df[(df['上报时间'] >= M0) & (df['上报时间'] < M1)]
PREV = df[df['上报时间'] < M0]

D = {}


def vlist(col, top=None):
    s = df[col].value_counts()
    return [[str(k), int(v)] for k, v in (s.head(top).items() if top else s.items())]


def pct(a, b):
    return round(a / b * 100, 2) if b else 0


# ============ 0 数据底盘与考核口径 ============
dead_aug = ((df['处置截止时间'] >= M0) & (df['处置截止时间'] < M1)).sum()
D['basis'] = {
    'total': TOTAL, 'closed': CLOSED, 'unclosed': UNCLOSED, 'close_rate': pct(CLOSED, TOTAL),
    'dur_n': len(DUR), 'aug_n': len(AUG), 'prev_n': len(PREV),
    'deadline_aug': int(dead_aug), 'deadline_aug_rate': pct(int(dead_aug), TOTAL),
    'deadline_range': [str(df['处置截止时间'].min()), str(df['处置截止时间'].max())],
    'report_range': [str(df['上报时间'].min()), str(df['上报时间'].max())],
    'dur_max': round(float(DUR['时长h'].max()), 1),
    'limit_max': round(float(df['期限h'].max()), 1),
    'unclosed_stage': df[~df['已办结']]['阶段'].value_counts().to_dict(),
    'prev_profile': {
        'n': len(PREV),
        'by_month': [[str(k), int(v)] for k, v in
                     PREV['上报时间'].dt.to_period('M').value_counts().sort_index().items()],
        'dur_med': round(float(PREV['时长h'].median()), 1),
        'delay_n': int(PREV['延期案件'].sum()),
        'overtime_n': int(PREV['is_overtime'].sum()),
        'top_dept': [[str(k), int(v)] for k, v in PREV['部门'].value_counts().head(6).items()],
        'top_dalei': [[str(k), int(v)] for k, v in PREV['大类名称'].value_counts().head(6).items()],
    },
    'unclosed_detail': df[~df['已办结']][['任务号', '大类名称', '小类名称', '部门', '阶段', '上报时间']]
        .assign(上报时间=lambda t: t['上报时间'].dt.strftime('%m-%d %H:%M')).to_dict('records'),
    'oldest': df.loc[df['上报时间'].idxmin()][['任务号', '大类名称', '小类名称', '部门', '上报时间', '结案时间', '期限h']].to_dict(),
}
D['basis']['oldest']['上报时间'] = str(D['basis']['oldest']['上报时间'])
D['basis']['oldest']['结案时间'] = str(D['basis']['oldest']['结案时间'])
D['basis']['oldest']['期限h'] = round(float(D['basis']['oldest']['期限h']), 1)
D['basis']['oldest']['任务号'] = int(D['basis']['oldest']['任务号'])

# 数据质量：已核实原因的异常日（日期/类型/说明由 config.json 的 anomalies 提供，案件量自动统计）
_daily_cnt = df['上报时间'].dt.strftime('%Y-%m-%d').value_counts()
D['basis']['anomaly'] = [
    [str(a['date']), int(_daily_cnt.get(str(a['date']), 0)), str(a.get('type', '异常')), str(a.get('note', ''))]
    for a in CFG.get('anomalies', [])
]

# ============ 1 法定考核时限（来自《立案、处置和结案标准》） ============
# 各小类法定考核时限为固定值，用于说明各小类考核要求；超时以 is_overtime 字段认定，不据此反推
xl_counts = df['小类名称'].value_counts()
std_rows = []
for xl, vals in STD.items():
    n = int(xl_counts.get(xl, 0))
    std_rows.append([str(xl), n, ' / '.join(str(v) for v in vals)])
std_rows.sort(key=lambda r: -r[1])
unit_cnt = Counter()
for xl, vals in STD.items():
    has_gz = any('工作时' in str(v) for v in vals)
    has_gr = any('工作日' in str(v) for v in vals)
    if has_gz and has_gr:
        unit_cnt['工作时+工作日'] += 1
    elif has_gz:
        unit_cnt['工作时'] += 1
    elif has_gr:
        unit_cnt['工作日'] += 1
    else:
        unit_cnt['其他'] += 1
D['std'] = {
    'n_xl': len(std_rows),
    'covered': int(sum(r[1] for r in std_rows)),
    'cover_rate': pct(int(sum(r[1] for r in std_rows)), TOTAL),
    'unit_note': '时限单位：「工作时」=工作小时数；「工作日」=工作日天数；紧急类另行标注',
    'unit_dist': [[k, v] for k, v in unit_cnt.most_common()],
    'rows': std_rows,
}

# ============ 2 总量结构 ============
D['structure'] = {
    'dalei': vlist('大类名称'), 'xiaolei': vlist('小类名称', 25), 'xiaolei_n': int(df['小类名称'].nunique()),
    'source': vlist('问题来源'), 'ptype': vlist('问题类型'), 'area': vlist('片区'),
    'street': vlist('街道'), 'community': vlist('社区', 20), 'community_n': int(df['社区'].nunique()),
    'dept': vlist('部门', 25), 'dept_n': int(df['部门'].nunique()), 'stage': vlist('阶段'),
}
xl = df['小类名称'].value_counts()
cum, acc = [], 0
for v in xl:
    acc += v; cum.append(round(acc / TOTAL * 100, 1))
D['structure']['pareto'] = cum[:25]
D['structure']['top10_cover'] = round(xl.head(10).sum() / TOTAL * 100, 1)
D['structure']['top20_cover'] = round(xl.head(20).sum() / TOTAL * 100, 1)
areas = [a for a, _ in vlist('片区')]
dls = [d for d, _ in vlist('大类名称')][:8]
mat = [[d] + [int(((df['大类名称'] == d) & (df['片区'] == a)).sum()) for a in areas] for d in dls]
D['structure']['matrix'] = {'areas': areas, 'dalei': dls, 'rows': mat}
srcs = [s for s, _ in vlist('问题来源')][:5]
D['structure']['src_matrix'] = {'srcs': srcs, 'dalei': dls,
                                'rows': [[s, int((df['问题来源'] == s).sum())] +
                                         [int(((df['问题来源'] == s) & (df['大类名称'] == d)).sum()) for d in dls]
                                         for s in srcs]}

# ============ 3 时空分布 ============
daily = df.groupby(df['上报时间'].dt.date).size()
daily = daily[daily.index >= pd.Timestamp(M0).date()]
AH = AUG['上报时间'].dt.hour                 # 时段分析仅用 8 月上报案件
D['time'] = {
    'daily': [[str(i), int(v)] for i, v in daily.items()],
    'hourly': [int(AH.value_counts().get(h, 0)) for h in range(24)],
    'weekday': [int(AUG['上报时间'].dt.dayofweek.value_counts().get(w, 0)) for w in range(7)],
    'close_hour': [int(df['结案时间'].dt.hour.value_counts().get(h, 0)) for h in range(24)],
}
wh = np.zeros((7, 24), int)
for w, hh in zip(AUG['上报时间'].dt.dayofweek, AH):
    wh[w][hh] += 1
D['time']['weekhour'] = [[int(wh[w][hh]) for hh in range(24)] for w in range(7)]
# 作息时段：按 config.json 的 work_windows（如 [[8,11.5],[14,20]]）计算各整点在班小时数
WW = [tuple(w) for w in CFG.get('work_windows', [[8, 11.5], [14, 20]])]
h = AH.value_counts()
DAYS = int(AUG['日期'].nunique())          # 节假日不休息，按实际采集天数


def _duty(x):
    """整点 x 落在作业时间窗内的有效小时数"""
    return sum(max(0.0, min(x + 1, b) - max(x, a)) for a, b in WW)


am_h = [x for x in range(24) if _duty(x) >= 1 and x < 12]
amhalf_h = [x for x in range(24) if 0 < _duty(x) < 1 and x < 12]
pm_full = [x for x in range(24) if _duty(x) >= 1 and x >= 12]
pm14_h, pm_h = pm_full[:1], pm_full[1:]
off_h = [x for x in range(24) if _duty(x) == 0]


def _agg(hs, hrs, dg=1):
    c = int(sum(h.get(x, 0) for x in hs))
    return c, (round(c / (DAYS * hrs), dg) if DAYS and hrs else 0)


am_n, am_rate = _agg(am_h, len(am_h))
am_half, amhalf_rate = _agg(amhalf_h, sum(_duty(x) for x in amhalf_h))
pm_14, pm14_rate = _agg(pm14_h, len(pm14_h), 2)
pm_n, pm_rate = _agg(pm_h, len(pm_h))
off_cases = int(sum(h.get(x, 0) for x in off_h))
D['time']['work'] = {
    'days': DAYS, 'total': len(AUG),
    'am_hours': float(len(am_h)), 'am_cases': am_n, 'am_rate': am_rate,
    'amhalf_hours': round(sum(_duty(x) for x in amhalf_h), 1),
    'amhalf_cases': am_half, 'amhalf_rate': amhalf_rate,
    'pm14_hours': float(len(pm14_h)), 'pm14_cases': pm_14, 'pm14_rate': pm14_rate,
    'pm_hours': float(len(pm_h)), 'pm_cases': pm_n, 'pm_rate': pm_rate,
    'off_cases': off_cases, 'off_rate': pct(off_cases, len(AUG)),
    'work_cases': am_n + am_half + pm_14 + pm_n,
    'work_rate': pct(am_n + am_half + pm_14 + pm_n, len(AUG)),
}
D['time']['work_windows'] = [[float(a), float(b)] for a, b in WW]
# 星期分布（节假日不休息，7 天均为工作日采集）
wk = df.groupby([df['上报时间'].dt.dayofweek, df['上报时间'].dt.date]).size().reset_index(level=0, name='n')
daycnt = wk.groupby('上报时间').size() if False else wk.index.value_counts()
D['time']['weekday_days'] = [int(daycnt.get(w, 0)) for w in range(7)]

# ============ 4 重复案件识别（问题描述为主 + 坐标确认） ============
def poi_of(s):
    s = str(s).strip()
    if s in NO_ADDR: return ''
    for r in (POI_RE, NEAR_RE, ALT_RE):
        m = r.match(s)
        if m: return m.group(1).strip()
    return ''


def bigram_sim(a, b):
    if not a or not b: return 0.0
    A = {a[i:i + 2] for i in range(len(a) - 1)}
    B = {b[i:i + 2] for i in range(len(b) - 1)}
    if not A or not B: return 0.0
    return len(A & B) / len(A | B)


def ptkey_of(s):
    """从问题描述提取点位签名：取前两段（街道 + 具体点位/店铺/路口），精确到店铺级，不做到街道整段。"""
    s = str(s).strip()
    segs = re.split(r'[，,、\s]+', s)
    segs = [x for x in segs if x]
    if not segs: return ''
    return '|'.join(segs[:2])


df['POI'] = df['地址描述'].apply(poi_of)          # 地址描述核心（仅作参考）
df['描述'] = df['问题描述'].astype(str)
df['PTKEY'] = df['描述'].apply(ptkey_of)           # 问题描述点位签名（主）
# 单位默认地址：12345转办等无定位案件系统默认定位到本单位（金城大厦铺安街989号），非真实点位，剔除
_UAK = CFG.get('unit_addr_keywords', [])
df['是默认地址'] = (df['地址描述'].astype(str).str.contains('|'.join(_UAK)) if _UAK
                   else pd.Series(False, index=df.index))
DEFAULT_N = int(df['是默认地址'].sum())


def find_hotspots(sub, r=R_METER, min_n=3):
    """贪心圆形热点：每个热点是以某案件为中心、半径 r 米的圆（直径上限 2r）。
    避免连通聚类的链式效应（沿街摊点被串成一条）。返回 list of [idx...]"""
    pts = sub[['X坐标', 'Y坐标']].values
    idx = np.array(sub.index)
    n = len(pts)
    cell = r / min(LAT_M, LON_M) * 1.1
    grid = defaultdict(list)
    for i in range(n):
        grid[(int(pts[i][0] / cell), int(pts[i][1] / cell))].append(i)

    def nbhd(i, alive=None):
        cx, cy = int(pts[i][0] / cell), int(pts[i][1] / cell)
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if alive is not None and not alive[j]: continue
                    ddx = (pts[i][0] - pts[j][0]) * LON_M
                    ddy = (pts[i][1] - pts[j][1]) * LAT_M
                    if ddx * ddx + ddy * ddy <= r * r: out.append(j)
        return out

    alive = [True] * n
    counts = [len(nbhd(i)) for i in range(n)]
    hots = []
    while True:
        best, bv = -1, 0
        for i in range(n):
            if alive[i] and counts[i] > bv:
                bv, best = counts[i], i
        if best < 0 or bv < min_n: break
        members = nbhd(best, alive)
        hots.append([idx[j] for j in members])
        touched = set()
        for j in members:
            for k in nbhd(j):
                if alive[k] and k not in members: touched.add(k)
        for j in members: alive[j] = False
        for k in touched:
            counts[k] = len(nbhd(k, alive))
    return hots


clusters = []      # list of [idx...]
# 重复案件 v3：以「问题描述点位签名」为主、坐标 50m 圆确认、地址描述仅作参考。
# 剔除单位默认地址（金城大厦，系12345转办无定位案件默认定位，非真实点位）。
work = df[~df['是默认地址']]
for (xl_name, key), sub in work.groupby(['小类名称', 'PTKEY']):
    if len(sub) < 3: continue
    clusters.extend(find_hotspots(sub))
# 退路：问题描述无可用点位签名的案件，按小类坐标聚
for xl_name, sub in work[work['PTKEY'] == ''].groupby('小类名称'):
    if len(sub) < 3: continue
    clusters.extend(find_hotspots(sub))

rec = []
for c, members in enumerate(clusters):
    s = df.loc[members]
    n = len(s)
    dx = (s['X坐标'].max() - s['X坐标'].min()) * LON_M
    dy = (s['Y坐标'].max() - s['Y坐标'].min()) * LAT_M
    diam = round(math.sqrt(dx * dx + dy * dy), 1)
    days = s['日期'].nunique()
    span = (s['上报时间'].max() - s['上报时间'].min()).days + 1
    pois = [p for p in s['POI'] if p]
    top_poi = Counter(pois).most_common(1)[0] if pois else ('', 0)
    poi_rate = round(top_poi[1] / n * 100, 1) if n else 0
    keys = [k for k in s['PTKEY'] if k]
    top_key = Counter(keys).most_common(1)[0] if keys else ('', 0)
    key_rate = round(top_key[1] / n * 100, 1) if n else 0
    label = top_key[0].replace('|', '，') if top_key[0] else ''
    desc = list(s['描述'])
    rep = Counter(desc).most_common(1)[0][0]
    sim = round(sum(bigram_sim(rep, d) for d in desc) / n, 3) if n else 0
    rec.append({
        'cid': c, 'xl': str(s['小类名称'].iat[0]), 'n': n, 'days': days, 'span': span,
        'lon': round(float(s['X坐标'].mean()), 6), 'lat': round(float(s['Y坐标'].mean()), 6),
        'label': label, 'key_rate': key_rate,
        'poi': top_poi[0], 'poi_rate': poi_rate, 'sim': sim, 'diam': diam,
        'addr': str(s['地址描述'].iat[0])[:36], 'desc': rep[:36],
        'area': str(s['片区'].iat[0]), 'dept': str(s['部门'].mode().iat[0]) if len(s) else '',
        'no_addr': int((s['地址描述'].astype(str).isin(NO_ADDR)).sum()),
    })

rec.sort(key=lambda r: (-r['n'], -r['days']))
rec_ge3 = [r for r in rec if r['n'] >= 3]
rec_hot = [r for r in rec_ge3 if r['n'] >= 10 and r['days'] >= 5]
rec_mid = [r for r in rec_ge3 if not (r['n'] >= 10 and r['days'] >= 5) and (r['n'] >= 5 or r['days'] >= 3)]
DEN = TOTAL - DEFAULT_N
D['recur'] = {
    'r': R_METER, 'lat_m': round(LAT_M, 1), 'lon_m': round(LON_M, 1),
    'default_n': DEFAULT_N, 'default_rate': pct(DEFAULT_N, TOTAL), 'denom': DEN,
    'cluster_n': len(rec), 'ge3_n': len(rec_ge3),
    'ge3_cases': sum(r['n'] for r in rec_ge3),
    'ge3_rate': pct(sum(r['n'] for r in rec_ge3), DEN),
    'hot_n': len(rec_hot), 'hot_cases': sum(r['n'] for r in rec_hot), 'hot_rate': pct(sum(r['n'] for r in rec_hot), DEN),
    'mid_n': len(rec_mid), 'mid_cases': sum(r['n'] for r in rec_mid),
    'top': rec_ge3[:30], 'hot': rec_hot[:25], 'ge3_all': rec_ge3,
    'by_xl': [],
    'sens': [],
    'isolated': DEN - sum(r['n'] for r in rec),
    'isolated_rate': pct(DEN - sum(r['n'] for r in rec), DEN),
    'diam_med': round(float(np.median([r['diam'] for r in rec_ge3])), 1) if rec_ge3 else 0,
    'diam_max': round(float(max([r['diam'] for r in rec_ge3])), 1) if rec_ge3 else 0,
}
cnt = Counter()
for r in rec_ge3:
    cnt[r['xl']] += 1
cc = defaultdict(int)
for r in rec_ge3: cc[r['xl']] += r['n']
for k, v in cnt.most_common(12):
    D['recur']['by_xl'].append([k, v, cc[k]])
# 阈值敏感性（同步用 小类+问题描述点位签名 聚类口径，剔除默认地址）
for rr in (30, 50, 100, 200):
    c2, hn = 0, 0
    for (xl_name, key), sub in work.groupby(['小类名称', 'PTKEY']):
        if len(sub) < 3: continue
        for members in find_hotspots(sub, rr):
            if len(members) >= 3:
                c2 += len(members); hn += 1
    D['recur']['sens'].append([rr, c2, pct(c2, DEN), hn])

# ============ 5 处置效能 ============
d = DUR['时长h']
D['eff'] = {
    'dur': {'mean': round(float(d.mean()), 2), 'p25': round(float(d.quantile(.25)), 2),
            'p50': round(float(d.median()), 2), 'p75': round(float(d.quantile(.75)), 2),
            'p90': round(float(d.quantile(.90)), 2), 'max': round(float(d.max()), 1),
            'in4h': pct(int((d <= 4).sum()), len(d)), 'in24h': pct(int((d <= 24).sum()), len(d))},
}
D['eff']['same_day'] = int(((df['结案时间'].dt.date == df['上报时间'].dt.date) & df['结案时间'].notna()).sum())
D['eff']['same_day_rate'] = pct(D['eff']['same_day'], TOTAL)
D['eff']['ontime'] = TOTAL - int(df['is_overtime'].sum())
D['eff']['ontime_rate'] = pct(D['eff']['ontime'], TOTAL)

bins = [0, 1, 2, 4, 8, 12, 24, 48, 72, 168, 1e9]
labels = ['1小时内', '1-2小时', '2-4小时', '4-8小时', '8-12小时', '12-24小时', '1-2天', '2-3天', '3-7天', '7天以上']
D['eff']['dur_bins'] = [[str(k), int(v)] for k, v in
                        pd.cut(DUR['时长h'], bins=bins, labels=labels).value_counts().reindex(labels).items()]

# 部门：处置时长中位数（结案-上报，时间戳口径）
dept = []
for name, sub in DUR.groupby('部门'):
    dept.append([str(name), len(sub), round(float(sub['时长h'].median()), 2)])
dept.sort(key=lambda r: r[2])
D['eff']['dept_all'] = dept
D['eff']['dept'] = [r for r in dept if r[1] >= 50]
dl_dur = []
for name, sub in DUR.groupby('大类名称'):
    if len(sub) >= 30:
        dl_dur.append([str(name), len(sub), round(float(sub['时长h'].median()), 2)])
dl_dur.sort(key=lambda r: r[2])
D['eff']['dalei'] = dl_dur
xl_dur = []
for name, sub in DUR.groupby('小类名称'):
    if len(sub) >= 100:
        xl_dur.append([str(name), len(sub), round(float(sub['时长h'].median()), 2)])
xl_dur.sort(key=lambda r: -r[2])
D['eff']['xiaolei'] = xl_dur[:15]
D['eff']['xiaolei_fast'] = xl_dur[-10:][::-1]
for key, col in [('area', '片区'), ('src', '问题来源')]:
    arr = []
    for name, sub in DUR.groupby(col):
        if len(sub) >= 10:
            arr.append([str(name), len(sub), round(float(sub['时长h'].median()), 2)])
    arr.sort(key=lambda r: r[2])
    D['eff'][key] = arr
pt = []
for name, sub in DUR.groupby('问题类型'):
    pt.append([str(name), len(sub), round(float(sub['时长h'].median()), 2),
               round(float(sub['时长h'].sum() / DUR['时长h'].sum() * 100), 1)])
pt.sort(key=lambda r: -r[2])
D['eff']['ptype'] = pt


def rate(field, by):
    out = []
    for name, sub in df.groupby(by):
        out.append([str(name), len(sub), int(sub[field].sum()), pct(int(sub[field].sum()), len(sub))])
    out.sort(key=lambda r: -r[3])
    return out


D['eff']['overtime'] = {'n': int(df['is_overtime'].sum()), 'rate': pct(int(df['is_overtime'].sum()), TOTAL),
                        'by_dept': [r for r in rate('is_overtime', '部门') if r[1] >= 50],
                        'by_dalei': [r for r in rate('is_overtime', '大类名称') if r[1] >= 50],
                        'by_area': rate('is_overtime', '片区'), 'by_src': rate('is_overtime', '问题来源')}
D['eff']['delay'] = {'n': int(df['延期案件'].sum()), 'rate': pct(int(df['延期案件'].sum()), TOTAL),
                     'by_dept': [r for r in rate('延期案件', '部门') if r[1] >= 50],
                     'by_dalei': [r for r in rate('延期案件', '大类名称') if r[1] >= 50],
                     'by_area': rate('延期案件', '片区'), 'by_src': rate('延期案件', '问题来源')}
D['eff']['rework'] = {'n': int(df['返工案件'].sum()), 'rate': pct(int(df['返工案件'].sum()), TOTAL),
                      'by_dept': [r for r in rate('返工案件', '部门') if r[2] > 0],
                      'by_dalei': [r for r in rate('返工案件', '大类名称') if r[2] > 0],
                      'by_area': rate('返工案件', '片区'), 'by_src': rate('返工案件', '问题来源')}
ot = df[df['is_overtime'] == 1]
D['eff']['ot_profile'] = {
    'dur_med': round(float((ot['结案时间'] - ot['上报时间']).dt.total_seconds().dropna().median() / 3600), 1),
    'top_dept': [[str(k), int(v)] for k, v in ot['部门'].value_counts().head(8).items()],
    'top_xl': [[str(k), int(v)] for k, v in ot['小类名称'].value_counts().head(8).items()],
    'top_dalei': [[str(k), int(v)] for k, v in ot['大类名称'].value_counts().head(6).items()],
    'top_area': [[str(k), int(v)] for k, v in ot['片区'].value_counts().items()]}
dly = df[df['延期案件'] == 1]
D['eff']['delay_profile'] = {
    'dur_med': round(float((dly['结案时间'] - dly['上报时间']).dt.total_seconds().dropna().median() / 3600), 1),
    'top_dept': [[str(k), int(v)] for k, v in dly['部门'].value_counts().head(8).items()],
    'top_xl': [[str(k), int(v)] for k, v in dly['小类名称'].value_counts().head(8).items()]}

# ============ 6 归因洞察 ============
sup_raw = df[df['监督员'] != '无（非采集员渠道）']['监督员'].value_counts()
sup = sup_raw[sup_raw >= CFG.get('min_cases_supervisor', 100)]
D['insight'] = {
    'sup_all_raw': int(len(sup_raw)), 'sup_n': int(len(sup)),
    'sup_cut': int((sup_raw < CFG.get('min_cases_supervisor', 100)).sum()),
    'sup_cut_cases': int(sup_raw[sup_raw < CFG.get('min_cases_supervisor', 100)].sum()),
    'sup_all': [[str(k), int(v)] for k, v in sup.items()],
    'sup_mean': round(float(sup.mean()), 1), 'sup_med': round(float(sup.median()), 1),
    'sup_std': round(float(sup.std()), 1), 'sup_cv': round(float(sup.std() / sup.mean() * 100), 1),
    'sup_min': int(sup.min()), 'sup_max': int(sup.max()),
    'sup_top10_share': round(float(sup.head(10).sum() / sup.sum() * 100), 1),
    'sup_gt600': int((sup > 600).sum()), 'sup_cases': int(sup.sum()),
    'raw_list': [[str(k), int(v)] for k, v in sup_raw[sup_raw < CFG.get('min_cases_supervisor', 100)].items()],
}
GOV = ['12345热线转办工单', '12345电话快办', '市民热线举报', '微信举报', '市政府民呼我应邮箱转办']
D['insight']['src_gov'] = int(df['问题来源'].isin(GOV).sum())
D['insight']['src_gov_rate'] = pct(D['insight']['src_gov'], TOTAL)
D['insight']['src_collector'] = int((df['问题来源'] == '采集员上报').sum())
D['insight']['src_collector_rate'] = pct(D['insight']['src_collector'], TOTAL)
D['insight']['src_video'] = int((df['问题来源'] == '视频上报').sum())
gov_d = DUR[DUR['问题来源'].isin(GOV)]
D['insight']['gov_dur'] = {'n': len(gov_d), 'p50': round(float(gov_d['时长h'].median()), 2),
                           'p90': round(float(gov_d['时长h'].quantile(.9)), 2)}
D['insight']['gov_by_src'] = [[str(k), int((df['问题来源'] == k).sum()),
                               round(float(DUR[DUR['问题来源'] == k]['时长h'].median()), 2)]
                              for k in GOV if (df['问题来源'] == k).sum() > 0]
we = AUG[AUG['上报时间'].dt.dayofweek >= 5]
wd = AUG[AUG['上报时间'].dt.dayofweek < 5]
we_d, wd_d = we[we['时长h'].notna()], wd[wd['时长h'].notna()]
D['insight']['weekend'] = {
    'we_n': len(we), 'wd_n': len(wd),
    'we_days': int(we['日期'].nunique()), 'wd_days': int(wd['日期'].nunique()),
    'we_avg': round(len(we) / max(we['日期'].nunique(), 1), 1),
    'wd_avg': round(len(wd) / max(wd['日期'].nunique(), 1), 1),
    'we_dur': round(float(we_d['时长h'].median()), 2), 'wd_dur': round(float(wd_d['时长h'].median()), 2),
    'we_top': [[str(k), int(v)] for k, v in we['小类名称'].value_counts().head(6).items()],
    'wd_top': [[str(k), int(v)] for k, v in wd['小类名称'].value_counts().head(6).items()]}
noad = df['地址描述'].astype(str).isin(NO_ADDR).sum()
D['insight']['no_addr'] = int(noad)
D['insight']['no_addr_rate'] = pct(int(noad), TOTAL)
D['insight']['no_addr_by_xl'] = [[str(k), int(v)] for k, v in
    df[df['地址描述'].astype(str).isin(NO_ADDR)]['小类名称'].value_counts().head(8).items()]
D['insight']['poi_cover'] = pct(int((df['POI'] != '').sum()), TOTAL)

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(D, f, ensure_ascii=False, default=str)

# ============ 摘要 ============
print('== 考核口径 ==')
print('总量 %d | 处置截止在8月 %d (%.2f%%) | 截止区间 %s ~ %s' % (
    TOTAL, D['basis']['deadline_aug'], D['basis']['deadline_aug_rate'], *D['basis']['deadline_range']))
print('上报于8月 %d | 上报于往月(挂账) %d | 未办结 %d | 办结率 %.2f%%' % (
    len(AUG), len(PREV), UNCLOSED, D['basis']['close_rate']))
print('往月挂账：中位时长 %.1fh，延期 %d 件，超时 %d 件' % (
    D['basis']['prev_profile']['dur_med'], D['basis']['prev_profile']['delay_n'],
    D['basis']['prev_profile']['overtime_n']))
print('\n== 法定考核时限（来自《立案、处置和结案标准》）==')
print('覆盖小类 %d | 覆盖案件 %d (%.2f%%)' % (D['std']['n_xl'], D['std']['covered'], D['std']['cover_rate']))
print('时限单位分布:', D['std']['unit_dist'])
print('案件量 Top5 小类法定时限:', D['std']['rows'][:5])
print('\n== 处置时长（结案-上报，时间戳口径）==')
print('全平台 中位 %.2fh P75 %.2fh P90 %.2f' % (D['eff']['dur']['p50'], D['eff']['dur']['p75'], D['eff']['dur']['p90']))
for r in D['eff']['dept'][:5]: print('  快:', r)
for r in D['eff']['dept'][-5:]: print('  慢:', r)
print('\n== 大类（处置时长中位）==')
for r in D['eff']['dalei']: print('  ', r)
print('\n== 问题类型 ==')
for r in D['eff']['ptype']: print('  ', r)
print('\n== 复发（R=%dm）==' % R_METER)
print('簇 %d | ≥3件簇 %d 涉 %d 件 (%.1f%%) | 高频复发(≥10件且≥5天) %d 个涉 %d 件 (%.1f%%) | 孤立案件 %d (%.1f%%)' % (
    D['recur']['cluster_n'], D['recur']['ge3_n'], D['recur']['ge3_cases'], D['recur']['ge3_rate'],
    D['recur']['hot_n'], D['recur']['hot_cases'], D['recur']['hot_rate'],
    D['recur']['isolated'], D['recur']['isolated_rate']))
print('阈值敏感性:', D['recur']['sens'])
print('复发按小类 top8:', D['recur']['by_xl'][:8])
print('高频复发 top12:')
for r in D['recur']['hot'][:12]:
    print('   %-8s n=%3d 天数=%2d 跨度=%2d天 直径=%5.1fm POI一致=%3.0f%% 描述相似=%.2f | %s | %s' % (
        r['xl'], r['n'], r['days'], r['span'], r['diam'], r['poi_rate'], r['sim'],
        r['poi'] or '无POI', r['addr']))
print('直径分布: 中位 %.1fm 最大 %.1fm' % (
    float(np.median([r['diam'] for r in D['recur']['ge3_all']])) if D['recur']['ge3_all'] else 0,
    max([r['diam'] for r in D['recur']['ge3_all']]) if D['recur']['ge3_all'] else 0))
print('\n== 监督员（专职 ≥100 件）==')
print('原始 %d 人 → 剔除 %d 人（共 %d 件）→ 专职 %d 人' % (
    D['insight']['sup_all_raw'], D['insight']['sup_cut'], D['insight']['sup_cut_cases'], D['insight']['sup_n']))
print('人均 %.1f 中位 %.1f 标准差 %.1f 变异系数 %.1f%% | 区间 %d—%d | Top10占 %.1f%% | >600件 %d人' % (
    D['insight']['sup_mean'], D['insight']['sup_med'], D['insight']['sup_std'], D['insight']['sup_cv'],
    D['insight']['sup_min'], D['insight']['sup_max'], D['insight']['sup_top10_share'], D['insight']['sup_gt600']))
print('剔除名单:', D['insight']['raw_list'])
print('\n== 工作时段（%d 个采集日，节假日不休息）==' % D['time']['work']['days'])
w = D['time']['work']
print('8:00-11:00 (3.0h)  %5d 件  %6.1f 件/小时' % (w['am_cases'], w['am_rate']))
print('11:00-11:30(0.5h)  %5d 件  %6.1f 件/小时' % (w['amhalf_cases'], w['amhalf_rate']))
print('14:00-15:00(1.0h)  %5d 件  %6.2f 件/小时  <-- 与作息不符' % (w['pm14_cases'], w['pm14_rate']))
print('15:00-20:00(5.0h)  %5d 件  %6.1f 件/小时' % (w['pm_cases'], w['pm_rate']))
print('非工作时段 %d 件 (%.2f%%)' % (w['off_cases'], w['off_rate']))
print('\n== 周末（节假日不休息）==')
k = D['insight']['weekend']
print('周末 %d 件/%d天 = %.1f/天 | 工作日 %d 件/%d天 = %.1f/天 | 时效 %.2fh vs %.2fh' % (
    k['we_n'], k['we_days'], k['we_avg'], k['wd_n'], k['wd_days'], k['wd_avg'],
    k['we_dur'], k['wd_dur']))
print('\n== 来源 ==')
print('采集员 %d (%.1f%%) | 视频 %d | 政务渠道 %d (%.1f%%)' % (
    D['insight']['src_collector'], D['insight']['src_collector_rate'],
    D['insight']['src_video'], D['insight']['src_gov'], D['insight']['src_gov_rate']))
print('政务渠道: 中位 %.2fh' % D['insight']['gov_dur']['p50'])
for r in D['insight']['gov_by_src']: print('   ', r)
print('POI 可提取率 %.1f%% | 无位置描述 %.1f%%' % (D['insight']['poi_cover'], D['insight']['no_addr_rate']))
print('\nJSON ->', OUT)
