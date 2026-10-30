# -*- coding: utf-8 -*-
"""抽查报告点位格式直测：完整点位名称（含道路）+（监控序号），例：学苑路毕家索东（XY01）。

纯函数测试，零数据库读写——本地 `python _check_report_spot.py` 与容器内
`docker cp` 后 `python3 _check_report_spot.py` 跑的都是线上这份代码的输出。
夹具 = 服务器 cyw_spot 全量 48 行只读快照（2026-10-20）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    _here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_here, '..', '.env.local'))
    load_dotenv(os.path.join(_here, '.env.local'))
except ImportError:
    pass  # 容器内无 dotenv，环境变量由 compose 注入

from cyw_routes import _spot_full_name, _check_export_text

# (monitor_no, name, road, 期望是否拼路名) —— road/name 取服务器现值，逐行核对过
SPOTS = [
    ('HDL010', '槐东路东槐东文化苑西门北侧', '槐东路', False),
    ('TSJ026', '清河洗浴广告指示牌东侧', '条山街', True),
    ('HXL004', '韩信路铺安街往东南420米路东北侧', '韩信路', False),
    ('HXL005', '韩信路铺安街往东南220米路东北侧', '韩信路', False),
    ('SHL038', '圣惠北路环岛西北侧', '圣惠路', False),
    ('SHL013', '圣惠路东侧圣惠小区北门南侧', '圣惠路', False),
    ('SSJ045', '芭娜啦工作室对面东侧(梅苑新村小区对面）', '涑水街', True),
    ('SSJ046', '运城职业技术学校出入口东侧', '涑水街', True),
    ('SDL041', '杏上村出入口对面东侧', '舜帝街', True),
    ('SDL042', '壕头村出入口对面西侧', '舜帝街', True),
    ('HDL018', '槐东路西陈氏大虾前', '槐东路', False),
    ('TSJ012', '小哥哥烧烤海鲜北侧', '条山街', True),
    ('LCJ004', '潞村街路北山西省地球物理化学勘察院东侧', '潞村街', False),
    ('LCJ002', '潞村街路南炒鸡店东侧', '潞村街', False),
    ('JCDD055', '机场大道南侧建北桥东750米三岔口东侧', '机场大道', False),
    ('JCDD088', '机场大道路北中泽鑫上海大众东侧楼房南', '机场大道', False),
    ('KJL011', '奥梅花园出入口南侧', '康杰路', True),
    ('KJL014', '名人港湾出入口南侧', '康杰路', True),
    ('TZGJ016', '易家易购物广场出入口东侧', '陶朱公街', True),
    ('TZGJ021', '河东金叶出入口东侧', '陶朱公街', True),
    ('LHDL002', '柳河东路出呼北线路北275米', '柳河东路', False),
    ('LHDL031', '柳河东路24号大门南侧人行道', '柳河东路', False),
    ('PAJ008', '铺安街韩信路西南角', '铺安街', False),
    ('RML017', '人民北路条山路东南侧', '人民路', False),
    ('RML038', '理想学校东门往南220米', '人民路', True),
    ('HDJ037', '河东东街禹西路东北侧', '河东街', False),
    ('HDJ017', '河东东街与槐中路东南角', '河东街', False),
    ('YDJ041', '禹都东街路北海洲装饰对面东侧', '禹都街', False),
    ('YDJ044', '禹都东街路北桥西侧', '禹都街', False),
    ('YXL018', '禹西路与铺安街北50米处路西', '禹西路', False),
    ('YXL014', '禹西路河东东街西北侧150米', '禹西路', False),
    ('HDJ052', '河东西街与凤凰路交叉口西侧', '双桥路', True),
    ('HDJ028', '河东西街路东运城五金市场对面', '双桥路', True),
    ('WFJ004', '东方国旅南侧', '魏风街', True),
    ('BQL007', '步青街魏风街西南侧', '魏风街', False),
    ('HZL003', '槐中路路东广播电视台家属院对面', '槐中路', False),
    ('HZL002', '槐中路与吉祥巷东侧', '槐中路', False),
    ('HQJ001', '红旗东街东南侧山西冬枣基地门前西侧', '红旗街', False),
    ('HQJ047', '红旗东街与学苑路西北角', '红旗街', False),
    ('PAJ001', '铺安街韩信路丁字口南侧', '铺安街', False),
    ('YM02', '夜市东出入口南侧向西', '黄河夜市', False),
    ('GJ02', '运城盬街方言桥东南', '盬街', False),
    ('YM01', '夜市东出入口南侧向东', '黄河夜市', False),
    ('XY01', '毕家索东', '学苑路', True),
    ('GJ01', '运城盬街中心口2', '盬街', False),
    ('JF02', '解放路天逸公园门口', '解放路', False),
    ('JF01', '解放路萃林佳苑小区西口', '解放路', False),
    ('XY02', '通宝天际南', '学苑路', True),
]

# 关键逐条断言：编号 → (完整名, 理由)
EXPECT = {
    'XY01': ('学苑路毕家索东', '用户样例：点名不含路，拼'),
    'XY02': ('学苑路通宝天际南', '点名不含路，拼'),
    'TSJ026': ('条山街清河洗浴广告指示牌东侧', '点名不含路，拼'),
    'SHL038': ('圣惠北路环岛西北侧', '圣惠北路是圣惠路变体，再拼出「圣惠路圣惠北路」'),
    'RML017': ('人民北路条山路东南侧', '人民北路是人民路变体'),
    'HDJ037': ('河东东街禹西路东北侧', '河东东街是河东街变体'),
    'YDJ041': ('禹都东街路北海洲装饰对面东侧', '禹都东街是禹都街变体'),
    'HQJ001': ('红旗东街东南侧山西冬枣基地门前西侧', '红旗东街是红旗街变体'),
    'BQL007': ('步青街魏风街西南侧', '点名整段已含魏风街'),
    'GJ02': ('运城盬街方言桥东南', '点名已含盬街'),
    'YM02': ('夜市东出入口南侧向西', '黄河夜市拼「夜市东出入口」会叠字'),
    'HDJ052': ('双桥路河东西街与凤凰路交叉口西侧', '点名提的是另一条路，照样拼'),
    'HDL010': ('槐东路东槐东文化苑西门北侧', '点名以路名开头'),
    'TZGJ021': ('陶朱公街河东金叶出入口东侧', '河东金叶是店铺名不是路，拼'),
}

# 边界样例：与 road 同头两字但毫不相干的点名必须拼（曾经「同头两字就不拼」的糙规则
# 把冒烟测试点位「冒烟抽查点位」误放过）；真变体（学苑北路←学苑路）仍不拼
EXTRA = [
    ('冒烟抽查点位', '冒烟抽查路', '冒烟抽查路冒烟抽查点位'),
    ('学苑北路北口', '学苑路', '学苑北路北口'),
    ('毕家索东', '学苑路', '学苑路毕家索东'),
    ('河东东街', '河东街', '河东东街'),
    ('圣惠北路环岛西北侧', '圣惠路', '圣惠北路环岛西北侧'),
]


def item(iid, spot_id, no, name, road, person, status, rule, label):
    """按 _load_batch_items 的输出形态造一行（spot_full/monitor_no 同真链路算出）。"""
    return {'id': iid, 'spot_id': spot_id, 'spot_no': no, 'spot_name': name,
            'spot_road': road, 'spot_full': _spot_full_name(name, road),
            'monitor_no': no, 'person': person, 'phone': '1390000000' if person else '',
            'status': status, 'pick_rule': rule, 'dept_label': label}


def main():
    fails = []
    # 1) 48 行逐行：拼/不拼与期望一致
    for no, name, road, should_prefix in SPOTS:
        got = _spot_full_name(name, road)
        if should_prefix and got != f'{road}{name}':
            fails.append(f'{no} 应拼 {road}{name}，实得 {got}')
        if not should_prefix and got != name:
            fails.append(f'{no} 应原样 {name}，实得 {got}')
    # 2) 关键样例逐条
    for no, (want, why) in EXPECT.items():
        name, road = next((n, r) for m, n, r, _ in SPOTS if m == no)
        got = _spot_full_name(name, road)
        if got != want:
            fails.append(f'{no} 期望 {want}（{why}），实得 {got}')
    # 3) 空值兜底：road 空/name 空都不炸
    if _spot_full_name('毕家索东', None) != '毕家索东':
        fails.append('road 为 None 时应原样返回点名')
    if _spot_full_name('', '学苑路') != '':
        fails.append('name 为空时应原样返回')
    if _spot_full_name(None, None) != '':
        fails.append('双空应返回空串')
    # 3b) 边界样例：同头两字的不相干点名要拼，真变体不拼
    for nm, rd, want in EXTRA:
        got = _spot_full_name(nm, rd)
        if got != want:
            fails.append(f'边界 {nm}+{rd} 期望 {want}，实得 {got}')

    # 4) 合成批次走一遍导出文本
    batch = {'batch_no': 'CC-TEST-FMT', 'created_at': '2026-10-20 10:00:00',
             'created_by': '格式直测', 'finished_at': '2026-10-20 10:30:00'}
    items = [
        item(1, 101, 'XY01', '毕家索东', '学苑路', '张三', '在岗', '环卫%', '环卫中心·点位主管'),
        item(2, 101, 'XY01', '毕家索东', '学苑路', '李四', '不在岗', '执法%', '执法队·中城分队'),
        item(3, 102, 'YDJ041', '禹都东街路北海洲装饰对面东侧', '禹都街', '王五', '在岗', '环卫%', '环卫中心'),
        item(4, 103, 'HDJ052', '河东西街与凤凰路交叉口西侧', '双桥路', '', '待抽查', '执法%', '执法队'),
        # 点位行被删过：road/监控序号都取不到，退回建批次时的快照，不能把明细变空白
        item(5, None, 'GJ01', '运城盬街中心口2', None, '赵六', '在岗', '', '点位主管'),
    ]
    txt = _check_export_text(batch, items)
    want_lines = [
        '  1. 学苑路毕家索东（XY01）',
        '     环卫：在岗',
        '     执法：不在岗',
        '  2. 禹都东街路北海洲装饰对面东侧（YDJ041）',
        '  3. 双桥路河东西街与凤凰路交叉口西侧（HDJ052）',
        '     执法：未登记',
        '  4. 运城盬街中心口2（GJ01）',
    ]
    for w in want_lines:
        if w not in txt:
            fails.append(f'导出文本缺行：{w}')
    # 旧格式（光名称无道路无编号）必须绝迹
    for bad in ('  1. 毕家索东\n', '  2. 禹都东街路北海洲装饰对面东侧\n'):
        if bad in txt:
            fails.append(f'旧格式残行：{bad.strip()}')

    print(txt)
    if fails:
        print('\n'.join(f'  [FAIL] {f}' for f in fails))
        print(f'\n共 {len(fails)} 处不符')
        sys.exit(1)
    n_prefix = sum(1 for *_, p in SPOTS if p)
    print(f'  [PASS] 48 行拼/不拼判定 + {len(EXPECT)} 条关键样例 + 空值兜底')
    print(f'  [PASS] 导出明细格式「完整点位名称（含道路）（监控序号）」'
          f'（{n_prefix} 个点名拼路名，{len(SPOTS) - n_prefix} 个点名自带道路语义）')
    print(f'  [PASS] 点位被删退回快照值（GJ01）')


if __name__ == '__main__':
    main()
