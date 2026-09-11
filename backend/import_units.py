# -*- coding: utf-8 -*-
"""导入单位组织架构到 dict_unit（幂等）。源：单位组织架构.txt"""
from __future__ import annotations

import os
import re
from dotenv import load_dotenv
import pymysql

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BACKEND_DIR)
load_dotenv()

# 默认解析桌面文件；可用 UNIT_TXT 覆盖
UNIT_TXT = os.environ.get(
    'UNIT_TXT',
    r'C:\Users\Administrator\Desktop\单位组织架构.txt',
)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS dict_unit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    unit_name VARCHAR(100) NOT NULL,
    unit_code VARCHAR(50) NULL,
    unit_type VARCHAR(30) NOT NULL DEFAULT 'other' COMMENT 'org/bureau_dept/bureau_unit/dispatch/garden/park/municipal/sanitation/other',
    parent_id INT NULL,
    sort_order INT DEFAULT 0,
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name_type (unit_name, unit_type),
    KEY idx_type (unit_type),
    KEY idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='单位组织架构字典'
"""

# 子单位归类规则
def classify(name: str, parent: str) -> str:
    n = name.strip()
    if '执法' in n and ('片区' in n or '分队' in n):
        return 'dispatch'
    if n.startswith('园林') and ('片区' in n or '公园' in n or '广场' in n or n.endswith('园')):
        return 'garden' if '片区' in n else 'park'
    if n in ('南风广场', '人民公园', '圣惠公园', '航天公园', '天逸公园', '体育公园', '禹都公园', '植物园'):
        return 'park'
    if any(k in n for k in ('市政技术部', '市政工程部', '市政设施维护部', '城市照明部')):
        return 'municipal'
    if n.startswith('环卫') and '片区' in n:
        return 'sanitation'
    if '科' in n and not n.startswith('运城市'):
        return 'bureau_dept'
    if parent.startswith('运城市') or n.startswith('运城市'):
        return 'bureau_unit'
    return 'other'


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_SQL)
    conn.commit()


def parse_units(path: str):
    """返回 list of {unit_name, unit_code, unit_type, parent_name}"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, encoding='utf-8') as f:
        lines = [ln.rstrip('\n') for ln in f]

    units = []
    # 当前局属单位（第二层父）
    current_parent = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        # 去 markdown 加粗/列表
        line = re.sub(r'^\*\*|\*\*$', '', line).strip()
        m = re.match(r'^-\s*([\d.]+)\s*(.+)$', line)
        if not m:
            # 标题行 **运城市城市管理局**
            if line.startswith('运城市') or line == '运城市城市管理局':
                units.append({
                    'unit_name': '运城市城市管理局',
                    'unit_code': '',
                    'unit_type': 'org',
                    'parent_name': '',
                })
            continue
        code, name = m.group(1).strip(), m.group(2).strip()
        if not name:
            continue
        # 层级：1.x 一层，1.x.y 二层
        if re.fullmatch(r'\d+\.\d+', code):
            # 局属单位/科室
            ut = classify(name, '运城市城市管理局')
            # 特殊：机关科室
            if code in ('1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8'):
                ut = 'bureau_dept'
            current_parent = name
            parent = '运城市城市管理局'
        else:
            # 1.x.y 子单位
            parent = current_parent or '运城市城市管理局'
            ut = classify(name, parent)
        units.append({
            'unit_name': name,
            'unit_code': code,
            'unit_type': ut,
            'parent_name': parent,
        })
    return units


def import_units():
    units = parse_units(UNIT_TXT)
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '3306'))
    db_name = os.getenv('DB_NAME', 'case_analysis')
    conn = pymysql.connect(
        host=db_host, port=db_port, user=db_user, password=db_password,
        database=db_name, charset='utf8mb4', autocommit=False,
    )
    try:
        ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute('DELETE FROM dict_unit')  # 全量重导
            name_to_id = {}
            # 先插入顶层
            for i, u in enumerate(units, 1):
                parent_id = name_to_id.get(u['parent_name']) if u['parent_name'] else None
                # 保证父先存在：若父不在 map 且不是局，跳过 parent
                cur.execute(
                    """INSERT INTO dict_unit (unit_name, unit_code, unit_type, parent_id, sort_order)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (u['unit_name'], u['unit_code'] or None, u['unit_type'], parent_id, i),
                )
                name_to_id[u['unit_name']] = cur.lastrowid
        conn.commit()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM dict_unit')
            n = cur.fetchone()[0]
            cur.execute(
                "SELECT unit_type, COUNT(*) FROM dict_unit GROUP BY unit_type ORDER BY unit_type"
            )
            by_type = cur.fetchall()
        print(f'[done] dict_unit={n}')
        for t, c in by_type:
            print(f'  {t}: {c}')
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import_units()
