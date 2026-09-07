import pandas as pd, re, numpy as np, json, os, sys

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
os.makedirs(BASE, exist_ok=True)

def _p(*a):
    return os.path.join(BASE, *a)

STD = CFG.get('std_src', '立案、处置和结案标准.xlsx')
if not os.path.isabs(STD):
    STD = _p(STD)
_SRC = CFG.get('src', '案件数据.xlsx')
if not os.path.isabs(_SRC):
    _SRC = _p(_SRC)
df = pd.read_excel(_SRC)
for c in ['上报时间','结案时间','处置截止时间']:
    df[c]=pd.to_datetime(df[c])
df['限h']=(df['处置截止时间']-df['上报时间']).dt.total_seconds()/3600

def parse_limit(s):
    if not isinstance(s,str): return None
    s=s.strip()
    m=re.search(r'(\d+(?:\.\d+)?)\s*(紧急)?\s*(工作时|工作日|小时|天|日)', s)
    if not m: return None
    num=float(m.group(1)); unit=m.group(3)
    if unit in ('工作时','小时'): return num
    return num*24.0   # 工作日/日/天 暂按24h折算校验

xl_file=pd.ExcelFile(STD)
limit_map={}

def add(xl_name, txt, val):
    if val is not None and xl_name:
        limit_map.setdefault(xl_name,[]).append((txt,val))

# ---- 通用结构 sheet ----
for sh in ['部件','部件扩展','事件','事件扩展 ','服务事项']:
    d=pd.read_excel(STD,sheet_name=sh,header=None)
    hdr=None
    for i in range(min(6,len(d))):
        vals=[str(x) for x in d.iloc[i].tolist()]
        if '小类名称' in vals and '处置时限' in vals:
            hdr=i; break
    if hdr is None:
        print('!! 未找到表头:',repr(sh)); continue
    cols={str(x).strip():j for j,x in enumerate(d.iloc[hdr])}
    col_dalei=cols.get('大类名称'); col_xl=cols.get('小类名称'); col_limit=cols.get('处置时限')
    cur_xl=None
    for i in range(hdr+1,len(d)):
        row=d.iloc[i]
        if pd.notna(row[col_xl]): cur_xl=row[col_xl]
        if cur_xl is None: continue
        txt=str(row[col_limit]).strip() if pd.notna(row[col_limit]) else ''
        add(cur_xl, txt, parse_limit(row[col_limit]))

# ---- 最终 sheet (交通设施, A/B/C类) ----
d=pd.read_excel(STD,sheet_name='最终',header=None)
hdr=None
for i in range(min(8,len(d))):
    if '小类名称' in [str(x) for x in d.iloc[i].tolist()]: hdr=i; break
cols={str(x).strip():j for j,x in enumerate(d.iloc[hdr])}
col_xl=cols.get('小类名称')
# A/B/C 类在 hdr-1 行标注, 处置时限列即这些列
class_cols=[j for j in range(len(d.columns)) if str(d.iloc[hdr-1][j]).strip() in ('A类（紧急）','B类（重大）','C类（一般）')]
cur_xl=None
for i in range(hdr+1,len(d)):
    row=d.iloc[i]
    if pd.notna(row[col_xl]): cur_xl=row[col_xl]
    if cur_xl is None: continue
    good=[(str(row[j]).strip(), parse_limit(row[j])) for j in class_cols if pd.notna(row[j])]
    good=[(t,v) for t,v in good if v is not None]
    if good: add(cur_xl, good[-1][0], good[-1][1])

print('=== 标准时限解析: 共 %d 个小类有标准 ==='%len(limit_map))
case_xl=df['小类名称'].unique()
miss=[x for x in case_xl if x not in limit_map]
print('案件小类数:',len(case_xl),' 标准覆盖:',len(case_xl)-len(miss),' 缺失:',len(miss))
print('缺失小类:',miss)
print()
print('=== 各小类 标准时限 vs 实际 处置截止-上报(中位h) ===')
for xl in sorted(case_xl, key=lambda x:-int((df['小类名称']==x).sum())):
    st=limit_map.get(xl)
    stxt='/'.join(sorted(set(t for t,_ in st))) if st else '—'
    sub=df[(df['小类名称']==xl)&(df['延期案件']!=1)]
    med2=sub['限h'].median() if len(sub)>0 else np.nan
    print('  %-16s 标准=%-14s 非延期限h中位=%-8s n=%d'%(xl,stxt,round(med2,1) if pd.notna(med2) else '—',int((df['小类名称']==xl).sum())))

out={xl:[t for t,_ in v] for xl,v in limit_map.items()}
json.dump(out, open(_p('std_limits.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n已保存 std_limits.json, 小类数=',len(out))
