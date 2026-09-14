# -*- coding: utf-8 -*-
"""值班表路由 - 文本解析 + 排班查询/导入/删除

数据按 (日期, 班次, 人员) 结构化存储，不存整段文本：
- 班次名不写死（白班/夜班/中班/节假日班…均可），新增班次无需改表；
- is_holiday / note 两列为节假日排班预留：解析时支持在日期后用括号写节假日名
  （如「10月1日（国庆节） 白班：张三」），含"节/假/休"字样的备注自动置 is_holiday=1。
  未来做节假日排班时，查询端按 is_holiday 优先展示即可，无需动表结构。

支持的文本格式（每行一天，也支持"日期行 + 班次行"分行走法）：
  9月13日 白班：张三、李四、王五，夜班：赵六
  2026-09-13 白班：张三 李四 王五 夜班：赵六
  10月1日（国庆节） 白班：张三
"""
import os
import re
import datetime
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

# 行首日期：2026年9月13日 / 2026-9-13 / 2026.9.13 / 2026/9/13
_DATE_FULL_RE = re.compile(r'^(?P<y>\d{4})\s*[年\-/.]\s*(?P<m>\d{1,2})\s*[月\-/.]\s*(?P<d>\d{1,2})\s*[日号]?')
# 行首日期（无年份）：9月13日 / 9-13 / 9.13 / 9/13
_DATE_SHORT_RE = re.compile(r'^(?P<m>\d{1,2})\s*[月\-/.]\s*(?P<d>\d{1,2})\s*[日号]?')
# 日期后的括号备注（节假日名等）
_NOTE_RE = re.compile(r'^[（(]\s*(?P<note>[^（）()]{1,50})\s*[）)]')
# 班次名：以"班"结尾的短词（白班/夜班/中班/早班/节假日白班…），后接中英文冒号
_SHIFT_RE = re.compile(r'(?P<shift>[^\s：:、，,；;（）()]{1,8}?班)\s*[:：]')
# 人员分隔：顿号/逗号/分号/空格均可
_NAME_SPLIT_RE = re.compile(r'[、，,;；\s]+')
# 名字末尾的括号注记（如"张三（替班）"）剥离
_NAME_TAIL_RE = re.compile(r'[（(][^（）()]{1,20}[）)]$')
# 备注含这些字样视为节假日（预留字段，未来节假日排班用）
_HOLIDAY_HINT_RE = re.compile(r'节|假|休')

WEEKDAY_NAMES = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']


def _parse_date_arg(s, default=None):
    try:
        return datetime.date.fromisoformat((s or '').strip())
    except (TypeError, ValueError):
        return default


def _clean_name(name):
    name = name.strip()
    stripped = _NAME_TAIL_RE.sub('', name).strip()
    return stripped or name


def _parse_shifts(text):
    """从一行中解析 [(班次, [人员...]), ...]，班次段以"班次名："引导"""
    matches = list(_SHIFT_RE.finditer(text))
    result = []
    for i, m in enumerate(matches):
        shift = m.group('shift').strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.end():end]
        names = [n for n in (_clean_name(x) for x in _NAME_SPLIT_RE.split(seg.strip())) if n]
        names = [n for n in names if len(n) <= 20]
        if names:
            result.append((shift, names))
    return result


def parse_duty_text(text, today=None):
    """值班表文本 → {'entries': [...], 'errors': [...]}

    entries 按日期升序，同日内保持文本中班次出现顺序；
    同一(日期,班次)多次出现时人员合并去重。
    """
    today = today or datetime.date.today()
    days = {}  # 'YYYY-MM-DD' -> {'note':..., 'shifts': {班次: [人员]}}
    errors = []
    current_date = None  # 支持"日期行 + 班次行"的分行走法

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue

        date = None
        note = None
        rest = line

        m = _DATE_FULL_RE.match(line) or _DATE_SHORT_RE.match(line)
        if m:
            y = int(m.groupdict().get('y') or 0)
            mo, d = int(m.group('m')), int(m.group('d'))
            rest = line[m.end():]
            nm = _NOTE_RE.match(rest)
            if nm:
                note = nm.group('note').strip()
                rest = rest[nm.end():]
            try:
                date = datetime.date(y or today.year, mo, d)
                # 只写月日的跨年排班：落在过去半年以上按明年处理（如12月传次年1月的表）
                if not y and (today - date).days > 180:
                    date = datetime.date(today.year + 1, mo, d)
            except ValueError:
                errors.append(f'第{lineno}行：日期无效「{line[:30]}」')
                continue

        shifts = _parse_shifts(rest)
        if shifts and date is None:
            if current_date is None:
                errors.append(f'第{lineno}行：缺少日期「{line[:30]}」')
                continue
            date = current_date

        if not shifts:
            if date is not None:
                if not rest.strip():
                    current_date = date  # 纯日期行，后续班次行挂到这个日期
                else:
                    errors.append(f'第{lineno}行：未找到"班次：人员"「{line[:30]}」')
            else:
                errors.append(f'第{lineno}行：无法识别「{line[:30]}」')
            continue

        current_date = date
        key = date.isoformat()
        bucket = days.setdefault(key, {'note': note, 'shifts': {}})
        if note and not bucket['note']:
            bucket['note'] = note
        for shift, names in shifts:
            existing = bucket['shifts'].setdefault(shift, [])
            for n in names:
                if n not in existing:
                    existing.append(n)

    entries = []
    for key in sorted(days.keys()):
        b = days[key]
        is_holiday = 1 if b['note'] and _HOLIDAY_HINT_RE.search(b['note']) else 0
        for shift, members in b['shifts'].items():
            entries.append({
                'date': key,
                'shift': shift,
                'members': members,
                'note': b['note'] or None,
                'is_holiday': is_holiday,
            })
    return {'entries': entries, 'errors': errors}


def _extract_duty_text():
    """从请求中取值班表文本：JSON {text} 或 multipart 文件（字段 file，.txt/.csv）"""
    if 'file' in request.files:
        f = request.files['file']
        if not f or not f.filename:
            return None, '请选择文件'
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ('.txt', '.csv', '.text'):
            return None, '仅支持 .txt / .csv 文本文件'
        raw = f.read()
        for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
            try:
                text = raw.decode(enc)
                if text.strip():
                    return text, None
            except UnicodeDecodeError:
                continue
        return None, '文件内容为空或编码无法识别，请另存为 UTF-8 后重试'
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return None, '请粘贴值班表文本或选择 txt 文件'
    return text, None


def register_duty_routes(app, Session, DutySchedule, protected, admin_required):

    def _members_to_str(members):
        return '、'.join(members)

    def _entry_dict(row):
        return {
            'id': row.id,
            'date': row.duty_date.isoformat() if row.duty_date else None,
            'shift': row.shift,
            'members': [m for m in (row.members or '').split('、') if m],
            'note': row.note,
            'is_holiday': row.is_holiday or 0,
        }

    @app.route('/api/duty/today', methods=['GET'])
    @protected
    def duty_today():
        """今日排班（首页欢迎区展示）"""
        try:
            if Session is None:
                return jsonify({'date': None, 'weekday': None, 'has_schedule': False, 'shifts': []})
            today = datetime.date.today()
            with Session() as session:
                rows = (session.query(DutySchedule)
                        .filter(DutySchedule.duty_date == today)
                        .order_by(DutySchedule.id)
                        .all())
                # 节假日排班（预留）：届时可在此按 is_holiday 优先/覆盖普通排班
                shifts = [_entry_dict(r) for r in rows]
            return jsonify({
                'date': today.isoformat(),
                'weekday': WEEKDAY_NAMES[today.weekday()],
                'has_schedule': bool(shifts),
                'shifts': shifts,
            })
        except Exception as e:
            logger.warning(f"查询今日值班失败: {e}")
            return jsonify({'error': '查询失败'}), 500

    @app.route('/api/duty/roster', methods=['GET'])
    @protected
    def duty_roster_by_date():
        """任意日期的排班(值班记录填写时带出当日值班人员)"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            d = _parse_date_arg(request.args.get('date'), datetime.date.today())
            if d is None:
                return jsonify({'error': '日期无效'}), 400
            with Session() as session:
                rows = (session.query(DutySchedule)
                        .filter(DutySchedule.duty_date == d)
                        .order_by(DutySchedule.id)
                        .all())
                shifts = [_entry_dict(r) for r in rows]
            return jsonify({'date': d.isoformat(), 'shifts': shifts})
        except Exception as e:
            logger.warning(f"查询排班失败: {e}")
            return jsonify({'error': '查询失败'}), 500

    @app.route('/api/duty/schedule', methods=['GET'])
    @admin_required
    def duty_list():
        """全部排班（管理页展示，按日期升序）"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                rows = (session.query(DutySchedule)
                        .order_by(DutySchedule.duty_date, DutySchedule.id)
                        .all())
                entries = [_entry_dict(r) for r in rows]
            return jsonify({'entries': entries})
        except Exception as e:
            logger.warning(f"获取值班表失败: {e}")
            return jsonify({'error': '获取失败'}), 500

    @app.route('/api/duty/preview', methods=['POST'])
    @admin_required
    def duty_preview():
        """解析值班表文本，返回预览（不落库）"""
        try:
            text, err = _extract_duty_text()
            if err:
                return jsonify({'error': err}), 400
            parsed = parse_duty_text(text)
            return jsonify({
                'entries': parsed['entries'],
                'errors': parsed['errors'],
                'total': len(parsed['entries']),
                'days': len({e['date'] for e in parsed['entries']}),
            })
        except Exception as e:
            logger.warning(f"解析值班表失败: {e}")
            return jsonify({'error': '解析失败'}), 500

    @app.route('/api/duty/upload', methods=['POST'])
    @admin_required
    def duty_upload():
        """导入值班表：JSON {text, mode} 或 multipart 文件（字段 file）。mode=replace(默认，全量替换)/append"""
        try:
            text, err = _extract_duty_text()
            if err:
                return jsonify({'error': err}), 400
            data = request.get_json(silent=True) or {}
            mode = data.get('mode', 'replace')
            if mode not in ('replace', 'append'):
                mode = 'replace'

            parsed = parse_duty_text(text)
            if not parsed['entries']:
                msg = '未能解析出任何排班，请检查格式'
                if parsed['errors']:
                    msg += '：' + '；'.join(parsed['errors'][:3])
                return jsonify({'error': msg, 'errors': parsed['errors']}), 400

            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503

            from sqlalchemy import Date as _Date
            user_id = getattr(request, 'user_id', None)
            inserted = 0
            with Session() as session:
                if mode == 'replace':
                    session.query(DutySchedule).delete()
                for e in parsed['entries']:
                    session.add(DutySchedule(
                        duty_date=datetime.date.fromisoformat(e['date']),
                        shift=e['shift'][:50],
                        members=_members_to_str(e['members'])[:500],
                        is_holiday=e['is_holiday'],
                        note=(e['note'] or None),
                        created_by=user_id,
                    ))
                    inserted += 1
                session.commit()
            return jsonify({
                'success': True,
                'mode': mode,
                'inserted': inserted,
                'days': len({e['date'] for e in parsed['entries']}),
                'errors': parsed['errors'],
                'entries': parsed['entries'][:50],
            })
        except Exception as e:
            logger.warning(f"导入值班表失败: {e}")
            return jsonify({'error': '导入失败'}), 500

    @app.route('/api/duty/schedule/<int:entry_id>', methods=['DELETE'])
    @admin_required
    def duty_delete_entry(entry_id):
        """删除单条排班（改错用）"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                row = session.query(DutySchedule).filter_by(id=entry_id).first()
                if not row:
                    return jsonify({'error': '记录不存在'}), 404
                session.delete(row)
                session.commit()
            return jsonify({'message': '删除成功'})
        except Exception as e:
            logger.warning(f"删除排班失败: {e}")
            return jsonify({'error': '删除失败'}), 500

    @app.route('/api/duty/schedule', methods=['DELETE'])
    @admin_required
    def duty_clear():
        """清空全部排班"""
        try:
            if Session is None:
                return jsonify({'error': '数据库未连接'}), 503
            with Session() as session:
                count = session.query(DutySchedule).delete()
                session.commit()
            return jsonify({'message': '已清空', 'deleted': count})
        except Exception as e:
            logger.warning(f"清空值班表失败: {e}")
            return jsonify({'error': '清空失败'}), 500
