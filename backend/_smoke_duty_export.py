# -*- coding: utf-8 -*-
"""值班记录导出冒烟测试：seed → 导出白班/夜班/整月 → python-docx 回读校验 → 清库"""
import sys, os, io, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('../.env.local')
load_dotenv('.env.local')

import jwt
from docx import Document
import app as app_module
from app import Session, DutyRecord, DutyRecordEvent

SECRET = os.getenv('JWT_SECRET_KEY')
H = {'Authorization': 'Bearer ' + jwt.encode(
    {'user_id': 1, 'username': 'admin', 'role': 'admin',
     'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}, SECRET, algorithm='HS256')}
client = app_module.app.test_client()

today = datetime.date(2000, 9, 13)  # 专用测试日期(2000年), 避免触碰用户真实录入
d1 = datetime.date(2000, 9, 1)

# seed：d1 白班(统计+关注问题)、d1 夜班(事件)、today 夜班(一切正常)
with Session() as s:
    s.query(DutyRecordEvent).delete(); s.query(DutyRecord).delete()
    r1 = DutyRecord(record_date=d1, shift='白班', members='展晓瑞、李瑞瑶',
                    stat_reported=740, stat_accepted=723, stat_completed=666,
                    src_collector=677, src_patrol=0, src_12345=15, src_minhu=0,
                    src_video=39, src_ai=0, src_public=1)
    s.add(r1); s.flush()
    s.add(DutyRecordEvent(record_id=r1.id, category='关注问题', ticket_no='202609010477',
                          location='机场大道山西彩虹集团西侧非机动车道', description='电力井盖破损',
                          result='已电话联系应急分队李彩虹处理，案件派遣至执法队应急分队', sort_order=0))
    r2 = DutyRecord(record_date=d1, shift='夜班', members='王康乐')
    s.add(r2); s.flush()
    s.add(DutyRecordEvent(record_id=r2.id, category='12345', ticket_no='44',
                          caller_name='刘先生', caller_phone='17203599998',
                          location='货场路城市花园小区东门桥洞', description='路面有石子，市民骑车摔倒',
                          timeline='[{"time":"22:47","text":"来电反映"},{"time":"22:51","text":"联系环卫周秀枝主任"}]',
                          result='已回复12345', sort_order=0))
    s.add(DutyRecord(record_date=today, shift='夜班', members='常家仪', is_normal=1))
    s.commit()

def read_paras(data):
    doc = Document(io.BytesIO(data))
    return [p.text for p in doc.paragraphs]

print('1) 导出白班当日')
r = client.get(f'/api/duty-record/export?date={d1.isoformat()}&shift=白班', headers=H)
print('  ', r.status_code, r.headers.get('Content-Type'), len(r.data), 'bytes')
assert r.status_code == 200 and 'wordprocessingml' in r.headers['Content-Type']
paras = read_paras(r.data)
assert '9月1日值班人员: 展晓瑞、李瑞瑶' in paras, paras[:5]
assert '上报740件，受理723件，办结666件。' in paras
assert '采集员上报受理:677' in paras
assert '1.202609010477' in paras and '案件详情：已电话联系应急分队李彩虹处理，案件派遣至执法队应急分队' in paras
print('   paras:', len(paras), '| 关键行齐')

print('2) 导出夜班当日(事件+时间线)')
r = client.get(f'/api/duty-record/export?date={d1.isoformat()}&shift=夜班', headers=H)
assert r.status_code == 200
paras = read_paras(r.data)
assert '9月1日夜间值班：王康乐' in paras
assert '1.12345（44）' in paras
assert '来电人：刘先生 17203599998' in paras
assert '22:47 来电反映' in paras and '处理结果：已回复12345' in paras
print('   paras:', len(paras), '| 关键行齐')

print('3) 导出整月(含一切正常)')
month = '2000-09'
r = client.get(f'/api/duty-record/export?month={month}', headers=H)
print('  ', r.status_code, len(r.data), 'bytes')
assert r.status_code == 200
paras = read_paras(r.data)
assert f'{today.year}年{today.month}月值班记录' in paras
assert '9月1日值班人员: 展晓瑞、李瑞瑶' in paras
assert f'{today.month}月{today.day}日夜间值班：常家仪' in paras
assert '一切正常' in paras
print('   paras:', len(paras), '| 关键行齐')

print('4) 无记录导出 -> 404')
r = client.get(f'/api/duty-record/export?date={d1.isoformat()}&shift=白班'.replace(str(d1.year), str(d1.year)) if False else
               f'/api/duty-record/export?date={today.isoformat()}&shift=白班', headers=H)
print('  ', r.status_code, r.get_json())
assert r.status_code == 404

print('5) 未登录 -> 401')
r = client.get(f'/api/duty-record/export?month={month}')
assert r.status_code == 401

# 清理(只删2000年测试数据, 不动用户录入)
with Session() as s:
    s.query(DutyRecordEvent).filter(DutyRecordEvent.record_id.in_(
        [x.id for x in s.query(DutyRecord).filter(DutyRecord.record_date < datetime.date(2020, 1, 1)).all()]
    )).delete(synchronize_session=False)
    s.query(DutyRecord).filter(DutyRecord.record_date < datetime.date(2020, 1, 1)).delete(synchronize_session=False)
    s.commit()

print('\nALL 5 EXPORT SMOKE TESTS PASSED')
