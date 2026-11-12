"""考核受理来源：独立存储、严格校验，不从应结案件推算。"""
import re
from sqlalchemy import text

SOURCE_GROUPS = ('采集上报', '视频上报', '公众诉求')
DEFAULT_SOURCES = [
    {'name': n, 'group': g, 'count': None}
    for n, g in [('采集上报', '采集上报'), ('视频上报', '视频上报'),
                 ('12345政务转办', '公众诉求'), ('12345热线', '公众诉求'),
                 ('值班电话', '公众诉求'), ('民呼我应', '公众诉求'), ('微信举报', '公众诉求')]
]
SOURCE_DDL = """
CREATE TABLE IF NOT EXISTS assessment_manual_source (
    batch VARCHAR(10) NOT NULL,
    channel_name VARCHAR(80) NOT NULL,
    source_group VARCHAR(20) NOT NULL,
    received_count INT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    updated_by VARCHAR(50) NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (batch, channel_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考核人工-各渠道受理数'
"""


def count_value(value, label):
    if value is None or value == '':
        return None
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError(f'{label}须为非负整数')
    number = int(value)
    if number > 2147483647:
        raise ValueError(f'{label}超出允许范围')
    return number


def normalize_sources(rows):
    if not isinstance(rows, list) or len(rows) > 50:
        raise ValueError('来源渠道须为数组，最多50项')
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('来源渠道格式无效')
        name = str(row.get('name') or '').strip()
        group = row.get('group')
        if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise ValueError('渠道名称须为1至80字且不能含换行等控制字符')
        key = name.casefold()
        if key in seen:
            raise ValueError(f'渠道名称重复：{name}')
        if group not in SOURCE_GROUPS:
            raise ValueError(f'{name}须选择有效的来源大类')
        seen.add(key)
        result.append({'name': name, 'group': group,
                       'count': count_value(row.get('count'), f'{name}受理数')})
    return result


def read_sources(conn, batch):
    return [{'name': r[0], 'group': r[1], 'count': r[2]} for r in conn.execute(text(
        'SELECT channel_name,source_group,received_count FROM assessment_manual_source '
        'WHERE batch=:b ORDER BY sort_order,channel_name'), {'b': batch})]


def save_sources(conn, batch, rows, user):
    conn.execute(text('DELETE FROM assessment_manual_source WHERE batch=:b'), {'b': batch})
    for i, row in enumerate(rows):
        conn.execute(text('INSERT INTO assessment_manual_source '
                          '(batch,channel_name,source_group,received_count,sort_order,updated_by) '
                          'VALUES (:b,:n,:g,:c,:i,:u)'),
                     {'b': batch, 'n': row['name'], 'g': row['group'],
                      'c': row['count'], 'i': i, 'u': user})


def source_warning(received, rows):
    if received is None:
        return '请填写当月考核案件数（月报受理数）'
    if not rows or any(r['count'] is None for r in rows):
        return '渠道受理数尚未填写完整，请在平台数据录入中补齐（无案件请填0）'
    total = sum(r['count'] for r in rows)
    if total != received:
        return f'渠道受理数合计{total}件，与月报受理数{received}件不一致（差额{received-total}件），请核对'
    return ''


def chart_sources(received, rows):
    rows = normalize_sources(rows)
    received = count_value(received, '月报受理数')
    warning = source_warning(received, rows)
    if warning:
        raise ValueError(warning)
    groups = {g: sum(r['count'] for r in rows if r['group'] == g) for g in SOURCE_GROUPS}
    return {'groups': groups, 'channels': rows,
            'subs': [[r['name'], r['count']] for r in rows if r['group'] == '公众诉求'],
            'total': received}
