# -*- coding: utf-8 -*-
"""种入202607测试人工数据（取自7月月报真实数值），测完用 --clean 清理"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BACKEND = os.path.dirname(os.path.abspath(__file__))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv
load_dotenv()

import urllib.parse
from sqlalchemy import create_engine, text

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{urllib.parse.quote_plus(os.getenv('DB_PASSWORD'))}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?charset=utf8mb4",
    pool_pre_ping=True,
)

BATCH = '202607'

WORK_NOTE = """提升防汛实战能力。紧扣“七下八上”防汛关键期，围绕汛前、汛中、汛后实操及应急处置流程，组织开展专题培训，补齐严判能力短板，提升应急实战能力。
加强部门协调联动。针对排查发现棉科西路3处雨水箅子堵塞、中银北路博鑫苑小区小游园座椅破损等问题，第一时间对接水投公司、城投公司完成问题转办。
常态运行提醒机制。紧盯12345热线重复投诉、二次回访不满意事项，采取“梳理研判+责任提醒”提升办理质效，同时针对雨污分流施工遗留、燃气停气相关问题开展专项提醒。
强化正面宣传引导。梳理各部门问题处置、诉求办理情况，筛选8件高效处置典型案例，依托“城市管理在线”公众号推送宣传，营造城市治理共治共享良好氛围。
推进网络安全及等保整改。完成视频智能分析系统渗透测试漏洞闭环整改；配合公安开展等保检查，建立整改台账、形成整改报告；常态化开展网络数据安全自查，筑牢安全防线。
统筹报送低空安全信息。按照发改委工作部署推进低空安全专项工作，归集汇总各单位相关信息按时上报，扎实做好低空安全基础管控。"""

DATA = {
    'monthly': (18323, WORK_NOTE, '未到 18:00 准许出摊时间，饭店提前店外经营，1处扣0.1分'),
    'collector': 17277,
    # 片区: 件数（得分=100-件数*0.01）
    'garbage': {'环卫中片区': ('中', 1927), '环卫西片区': ('西', 1792), '环卫南片区': ('南', 1949),
                '环卫东片区': ('东', 2545), '环卫北片区': ('北', 2088)},
    # (unit_name, unit_type, score_type, value)
    'scores': [
        # 执法分队 team/street/extra
        ('姚孟执法分队', 'dispatch', 'team', 100), ('姚孟执法分队', 'dispatch', 'street', 100), ('姚孟执法分队', 'dispatch', 'extra', 0),
        ('大渠执法分队', 'dispatch', 'team', 100), ('大渠执法分队', 'dispatch', 'street', 100), ('大渠执法分队', 'dispatch', 'extra', 0),
        ('西城执法分队', 'dispatch', 'team', 100), ('西城执法分队', 'dispatch', 'street', 100), ('西城执法分队', 'dispatch', 'extra', -0.1),
        ('南城执法分队', 'dispatch', 'team', 100), ('南城执法分队', 'dispatch', 'street', 100), ('南城执法分队', 'dispatch', 'extra', -0.1),
        ('北城执法分队', 'dispatch', 'team', 100), ('北城执法分队', 'dispatch', 'street', 100), ('北城执法分队', 'dispatch', 'extra', -0.1),
        ('中城执法分队', 'dispatch', 'team', 99), ('中城执法分队', 'dispatch', 'street', 100), ('中城执法分队', 'dispatch', 'extra', -0.1),
        ('东城执法分队', 'dispatch', 'team', 99), ('东城执法分队', 'dispatch', 'street', 100), ('东城执法分队', 'dispatch', 'extra', -0.7),
        ('安邑执法分队', 'dispatch', 'team', 99.5), ('安邑执法分队', 'dispatch', 'street', 100), ('安邑执法分队', 'dispatch', 'extra', -1),
        # 环卫中心分
        ('环卫中片区', 'sanitation', 'center', 91), ('环卫西片区', 'sanitation', 'center', 88),
        ('环卫南片区', 'sanitation', 'center', 85), ('环卫东片区', 'sanitation', 'center', 90),
        ('环卫北片区', 'sanitation', 'center', 84),
        # 园林片区/公园中心分
        ('园林东片区', 'garden', 'center', 92.5), ('园林中片区', 'garden', 'center', 92),
        ('园林北片区', 'garden', 'center', 85.5), ('园林南片区', 'garden', 'center', 94),
        ('园林西片区', 'garden', 'center', 88.5),
        ('圣惠公园', 'garden_park', 'center', 94.5), ('南风广场', 'garden_park', 'center', 93.5),
        ('天逸公园', 'garden_park', 'center', 92.5), ('体育公园', 'garden_park', 'center', 92),
        ('禹都公园', 'garden_park', 'center', 91.5), ('航天公园', 'garden_park', 'center', 86.5),
        ('人民公园', 'garden_park', 'center', 92),
    ],
    # 加减分项默认 0（未录入会导致缺项、总分置空）
    '_extras': [
        *[(d, 'sanitation', 'extra', 0) for d in
          ['环卫东片区', '环卫西片区', '环卫南片区', '环卫北片区', '环卫中片区']],
        *[(d, 'garden', 'extra', 0) for d in
          ['园林东片区', '园林中片区', '园林北片区', '园林南片区', '园林西片区']],
        *[(p, 'garden_park', 'extra', 0) for p in
          ['圣惠公园', '南风广场', '天逸公园', '体育公园', '禹都公园', '航天公园', '人民公园']],
        *[(u, 'municipal', 'extra', 0) for u in
          ['城市照明部', '市政设施维护部', '排水服务中心', '应急执法分队']],
    ],
    'special': [('建筑垃圾专项', 114), ('垃圾收集清运', 84), ('雨水篦子堵塞专项', 77),
                ('自建房', 73), ('设施残留物专项', 63)],
    # ledger: (type, unit_name, dept_name, source, cnt, content, reason, deadline)
    'ledger': [
        ('pending', '园林绿化服务中心', '', '', 73, '园路破损23、补植补栽17、墙皮脱落16、设施破损13、公共厕所4', '需财政资金到位', '2026-10-31'),
        ('pending', '园林东片区', '', '', 8, '', '', ''),
        ('pending', '园林中片区', '', '', 15, '', '', ''),
        ('pending', '园林北片区', '', '', 1, '', '', ''),
        ('pending', '园林西片区', '', '', 7, '', '', ''),
        ('pending', '圣惠公园', '', '', 3, '', '', ''),
        ('pending', '南风广场', '', '', 10, '', '', ''),
        ('pending', '天逸公园', '', '', 2, '', '', ''),
        ('pending', '禹都公园', '', '', 17, '', '', ''),
        ('pending', '航天公园', '', '', 5, '', '', ''),
        ('pending', '人民公园', '', '', 5, '', '', ''),
        ('backlog', '市政设施维护部', '市政公用服务中心（150）', '', 145, '维护部：路面破损49、路沿石倾斜39、隔离桩缺失38、路灯不亮5、设施残留物4、护树瓷砖4、过街天桥4、路名牌破损1、护栏破损1', '', ''),
        ('backlog', '', '市政公用服务中心（150）', '', 4, '河东西街项目：补植补栽4', '', ''),
        ('backlog', '', '市政公用服务中心（150）', '', 1, '圣惠南路项目：护栏破损1', '', ''),
        ('praise', '市容环卫中心', '', '12345政务热线转办', None, '市民表扬：盐湖区市政道路环卫东2组工作人员（介雪娥）捡到本人手机后主动联系归还，希望相关部门予以表扬。', '', ''),
    ],
}


def seed():
    with engine.begin() as conn:
        cnt, note, extra = DATA['monthly']
        conn.execute(text(
            "INSERT INTO assessment_manual_monthly (batch, assessment_case_cnt, work_note, extra_note, updated_by) "
            "VALUES (:b,:c,:w,:e,'test') ON DUPLICATE KEY UPDATE assessment_case_cnt=:c, work_note=:w, extra_note=:e"
        ), {'b': BATCH, 'c': cnt, 'w': note, 'e': extra})
        conn.execute(text(
            "INSERT INTO assessment_manual_collector (batch, self_dispose_cnt, updated_by) "
            "VALUES (:b,:c,'test') ON DUPLICATE KEY UPDATE self_dispose_cnt=:c"
        ), {'b': BATCH, 'c': DATA['collector']})
        for dist, (region, n) in DATA['garbage'].items():
            conn.execute(text(
                "INSERT INTO assessment_manual_garbage (batch, region, district_name, piece_count, updated_by) "
                "VALUES (:b,:r,:d,:n,'test') ON DUPLICATE KEY UPDATE piece_count=:n"
            ), {'b': BATCH, 'r': region, 'd': dist, 'n': n})
        conn.execute(text("DELETE FROM assessment_manual_score WHERE batch=:b"), {'b': BATCH})
        for un, ut, st, v in DATA['scores'] + DATA['_extras']:
            conn.execute(text(
                "INSERT INTO assessment_manual_score (batch, unit_name, unit_type, score_type, score_value, updated_by) "
                "VALUES (:b,:u,:t,:s,:v,'test')"
            ), {'b': BATCH, 'u': un, 't': ut, 's': st, 'v': v})
        conn.execute(text("DELETE FROM assessment_manual_special_detail WHERE batch=:b"), {'b': BATCH})
        for minor, n in DATA['special']:
            conn.execute(text(
                "INSERT INTO assessment_manual_special_detail (batch, major_name, minor_name, piece_cnt, updated_by) "
                "VALUES (:b,'专项采集',:m,:n,'test')"
            ), {'b': BATCH, 'm': minor, 'n': n})
        conn.execute(text("DELETE FROM assessment_manual_ledger WHERE batch=:b"), {'b': BATCH})
        for t, un, dn, src, n, content, reason, dl in DATA['ledger']:
            conn.execute(text(
                "INSERT INTO assessment_manual_ledger (batch, ledger_type, unit_name, dept_name, source, piece_cnt, content, reason, deadline, updated_by) "
                "VALUES (:b,:t,:un,:dn,:src,:n,:c,:r,:dl,'test')"
            ), {'b': BATCH, 't': t, 'un': un or None, 'dn': dn or None, 'src': src or None,
                'n': n, 'c': content or None, 'r': reason or None, 'dl': dl or None})
    print('seeded', BATCH)


def clean():
    with engine.begin() as conn:
        for tb in ['assessment_manual_monthly', 'assessment_manual_collector',
                   'assessment_manual_garbage', 'assessment_manual_score',
                   'assessment_manual_special_detail', 'assessment_manual_ledger']:
            conn.execute(text(f"DELETE FROM {tb} WHERE batch=:b"), {'b': BATCH})
    print('cleaned', BATCH)


if __name__ == '__main__':
    if '--clean' in sys.argv:
        clean()
    else:
        seed()
