# -*- coding: utf-8 -*-
"""从《立案、处置和结案标准.xlsx》解析并导入 MySQL。

结构约定：
- 监管主体 / 责任主体 / 采集要求 / 法规 → 挂在小类上（每个小类只存一次）
- 立案条件 / 处置时限 / 结案条件 → 挂在小类下的多条明细
用法：
  python backend/import_case_standards.py
"""
from __future__ import annotations

import os
import re
from collections import OrderedDict

import pandas as pd
from dotenv import load_dotenv
import pymysql

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
os.chdir(BACKEND_DIR)
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
elif os.path.exists(os.path.join(PROJECT_DIR, '.env.local')):
    load_dotenv(os.path.join(PROJECT_DIR, '.env.local'))
load_dotenv()

# 优先用本地拷贝；可用 CASE_STD_XLSX 覆盖
STD_PATH = os.environ.get(
    'CASE_STD_XLSX',
    os.path.join(BACKEND_DIR, 'monthly_report', 'std', '立案、处置和结案标准.xlsx'),
)

DOMAIN_MAP = {
    '部件': 'part',
    '部件扩展': 'part',
    '事件': 'event',
    '事件扩展': 'event',
    '事件扩展 ': 'event',
    '服务事项': 'service',
    '最终': 'part',
}

# 基表优先于扩展表：同名小类主体字段冲突时用 base
SHEET_PRIORITY = {
    '部件': 3, '事件': 3, '服务事项': 3,
    '部件扩展': 2, '事件扩展': 2, '事件扩展 ': 2,
    '最终': 1,
}

CREATE_SQLS = [
    """
    CREATE TABLE IF NOT EXISTS dict_category (
        id INT AUTO_INCREMENT PRIMARY KEY,
        domain VARCHAR(20) NOT NULL COMMENT 'part/event/service',
        cat_code VARCHAR(20) NOT NULL DEFAULT '',
        cat_name VARCHAR(100) NOT NULL,
        sort_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_domain_name (domain, cat_name),
        KEY idx_domain (domain)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大小类-大类字典'
    """,
    """
    CREATE TABLE IF NOT EXISTS dict_subcategory (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category_id INT NOT NULL,
        domain VARCHAR(20) NOT NULL,
        sub_code VARCHAR(20) NOT NULL DEFAULT '',
        sub_name VARCHAR(200) NOT NULL,
        regulator VARCHAR(500) NULL COMMENT '监管主体（小类级）',
        responsible VARCHAR(500) NULL COMMENT '责任主体（小类级）',
        collect_note TEXT NULL COMMENT '采集要求（小类级）',
        legal_basis TEXT NULL,
        legal_clause TEXT NULL,
        is_active TINYINT(1) DEFAULT 1,
        sort_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_domain_sub (domain, sub_name(180)),
        KEY idx_category (category_id),
        KEY idx_sub_name (sub_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大小类-小类字典（含主体字段）'
    """,
    """
    CREATE TABLE IF NOT EXISTS case_standard (
        id INT AUTO_INCREMENT PRIMARY KEY,
        subcategory_id INT NOT NULL,
        source_sheet VARCHAR(50),
        condition_order INT DEFAULT 0,
        case_condition TEXT,
        time_limit_text VARCHAR(200),
        time_limit_hours DECIMAL(10,2) NULL,
        close_condition VARCHAR(500),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_sub (subcategory_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='立结案标准-立案条件明细'
    """,
]


def _s(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    return str(v).strip()


def _norm_code(v) -> str:
    s = _s(v)
    if re.fullmatch(r'\d+\.0', s):
        s = s[:-2]
    return s


def parse_limit_hours(text: str):
    if not text:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(紧急)?\s*(工作时|工作日|小时|天|日)', text)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(3)
    if unit in ('工作时', '小时'):
        return num
    return num * 24.0


def ensure_tables(conn):
    with conn.cursor() as cur:
        for t in ('case_standard', 'dict_subcategory', 'dict_category'):
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (t,),
            )
            if cur.fetchone()[0]:
                cur.execute(f'DROP TABLE IF EXISTS {t}')
        for sql in CREATE_SQLS:
            cur.execute(sql)
    conn.commit()
    print('[db] tables ready')


def _find_header_row(df: pd.DataFrame, max_scan=8):
    for i in range(min(max_scan, len(df))):
        vals = [_s(x) for x in df.iloc[i].tolist()]
        if '小类名称' in vals and '立案条件' in vals:
            return i
    return None


def _col_map(row) -> dict:
    return {_s(x): j for j, x in enumerate(row) if _s(x)}


def parse_standard_sheets(xlsx_path: str):
    """返回 (categories list, sub_meta OrderedDict, conditions list)。"""
    return _parse_v2(xlsx_path)


def _parse_v2(xlsx_path: str):
    xl = pd.ExcelFile(xlsx_path)
    categories: OrderedDict = OrderedDict()
    sub_meta: OrderedDict = OrderedDict()
    conditions = []

    for sheet_name in xl.sheet_names:
        key = sheet_name if sheet_name in DOMAIN_MAP else sheet_name.strip()
        if key not in DOMAIN_MAP:
            continue
        domain = DOMAIN_MAP[key]
        priority = SHEET_PRIORITY.get(key, 0)
        raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
        hdr = _find_header_row(raw)
        if hdr is None:
            print(f'[warn] sheet {sheet_name!r} 未找到表头，跳过')
            continue
        cols = _col_map(raw.iloc[hdr])
        c_cat_code = cols.get('大类代码')
        c_cat_name = cols.get('大类名称')
        c_sub_code = cols.get('小类代码')
        c_sub_name = cols.get('小类名称')
        c_case = cols.get('立案条件')
        c_limit = cols.get('处置时限')
        c_close = cols.get('结案条件')
        c_reg = cols.get('监管主体')
        c_resp = cols.get('责任主体')
        c_legal = cols.get('法律法规依据')
        c_clause = cols.get('法律法规具体条款')
        c_note = cols.get('采集要求')

        class_cols = []
        if key == '最终':
            for probe in (hdr, hdr - 1):
                if probe < 0:
                    continue
                prev = raw.iloc[probe]
                found = [j for j in range(len(prev)) if _s(prev[j]) in ('A类（紧急）', 'B类（重大）', 'C类（一般）')]
                if found:
                    class_cols = found
                    break
            if not class_cols and c_limit is not None:
                # 时限从处置时限列起连续若干列
                class_cols = list(range(c_limit, min(c_limit + 8, len(raw.columns))))

        cur_cat_code = cur_cat_name = ''
        cur_sub_code = cur_sub_name = ''
        cond_order = 0
        n_rows = 0

        for i in range(hdr + 1, len(raw)):
            row = raw.iloc[i]
            cat_code = _norm_code(row[c_cat_code]) if c_cat_code is not None else ''
            cat_name = _s(row[c_cat_name]) if c_cat_name is not None else ''
            sub_code = _norm_code(row[c_sub_code]) if c_sub_code is not None else ''
            sub_name = _s(row[c_sub_name]) if c_sub_name is not None else ''
            if cat_code:
                cur_cat_code = cat_code
            if cat_name:
                cur_cat_name = cat_name

            new_sub = bool(sub_name) and sub_name != cur_sub_name
            if sub_name:
                cur_sub_code = sub_code or (cur_sub_code if not new_sub else sub_code)
                cur_sub_name = sub_name
            if not cur_sub_name:
                continue
            if new_sub:
                cond_order = 0

            case_condition = _s(row[c_case]) if c_case is not None else ''
            limit_text = _s(row[c_limit]) if c_limit is not None else ''
            close_condition = _s(row[c_close]) if c_close is not None else ''
            regulator = _s(row[c_reg]) if c_reg is not None else ''
            responsible = _s(row[c_resp]) if c_resp is not None else ''
            collect_note = _s(row[c_note]) if c_note is not None else ''
            legal_basis = _s(row[c_legal]) if c_legal is not None else ''
            legal_clause = _s(row[c_clause]) if c_clause is not None else ''

            if key == '最终' and class_cols:
                picked = []
                for j in class_cols:
                    if j < len(raw.columns):
                        t = _s(raw.iloc[i, j])
                        if t:
                            picked.append(t)
                if picked:
                    limit_text = picked[-1]

            cat_name_f = cur_cat_name or '未知大类'
            cat_key = (domain, cat_name_f)
            if cat_key not in categories:
                categories[cat_key] = {
                    'domain': domain,
                    'cat_code': cur_cat_code,
                    'cat_name': cat_name_f,
                }

            sub_key = (domain, cur_sub_name)
            if sub_key not in sub_meta:
                sub_meta[sub_key] = {
                    'domain': domain,
                    'cat_name': cat_name_f,
                    'sub_code': cur_sub_code,
                    'sub_name': cur_sub_name,
                    'regulator': '',
                    'responsible': '',
                    'collect_note': '',
                    'legal_basis': '',
                    'legal_clause': '',
                    'priority': -1,
                    'source_sheets': [],
                }
            meta = sub_meta[sub_key]
            if key not in meta['source_sheets']:
                meta['source_sheets'].append(key)

            # 小类级字段：只写一次；高优先级 sheet 可覆盖低优先级
            if priority >= meta['priority']:
                for field, val in (
                    ('regulator', regulator),
                    ('responsible', responsible),
                    ('collect_note', collect_note),
                    ('legal_basis', legal_basis),
                    ('legal_clause', legal_clause),
                ):
                    if val:
                        meta[field] = val
                if regulator or responsible or collect_note or legal_basis or legal_clause:
                    meta['priority'] = priority

            if not case_condition and not limit_text and not close_condition:
                continue

            cond_order += 1
            n_rows += 1
            conditions.append({
                'domain': domain,
                'sub_name': cur_sub_name,
                'source_sheet': sheet_name.strip(),
                'condition_order': cond_order,
                'case_condition': case_condition,
                'time_limit_text': limit_text,
                'time_limit_hours': parse_limit_hours(limit_text),
                'close_condition': close_condition,
            })

        print(f'sheet={sheet_name!r:12} domain={domain:7} conditions={n_rows}')

    # 法规字段过长，仅保留责任主体/监管/采集要求在小类上；法规可后续再挂
    print(f'[parse] 大类 {len(categories)}  小类 {len(sub_meta)}  条件明细 {len(conditions)}')
    return list(categories.values()), sub_meta, conditions


def import_all():
    if not os.path.exists(STD_PATH):
        raise FileNotFoundError(STD_PATH)

    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '3306'))
    db_name = os.getenv('DB_NAME', 'case_analysis')
    if not all([db_user, db_password, db_host]):
        raise RuntimeError('DB_USER/DB_PASSWORD/DB_HOST 未配置')

    conn = pymysql.connect(
        host=db_host, port=db_port, user=db_user, password=db_password,
        database=db_name, charset='utf8mb4', autocommit=False,
    )
    try:
        ensure_tables(conn)
        cats, sub_meta, conditions = parse_standard_sheets(STD_PATH)

        cat_id_map = {}
        with conn.cursor() as cur:
            for i, c in enumerate(cats, 1):
                cur.execute(
                    "INSERT INTO dict_category (domain, cat_code, cat_name, sort_order) VALUES (%s,%s,%s,%s)",
                    (c['domain'], c['cat_code'], c['cat_name'], i),
                )
                cat_id_map[(c['domain'], c['cat_name'])] = cur.lastrowid

            sub_id_map = {}
            for i, info in enumerate(sub_meta.values(), 1):
                cat_id = cat_id_map.get((info['domain'], info['cat_name']))
                if not cat_id:
                    print(f"[warn] 小类无大类: {info['domain']}/{info['sub_name']}")
                    continue
                cur.execute(
                    """INSERT INTO dict_subcategory
                    (category_id, domain, sub_code, sub_name, regulator, responsible,
                     collect_note, legal_basis, legal_clause, sort_order)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        cat_id, info['domain'], info['sub_code'], info['sub_name'],
                        info['regulator'], info['responsible'], info['collect_note'],
                        info['legal_basis'], info['legal_clause'], i,
                    ),
                )
                sub_id_map[(info['domain'], info['sub_name'])] = cur.lastrowid

            for st in conditions:
                sid = sub_id_map.get((st['domain'], st['sub_name']))
                if not sid:
                    continue
                cur.execute(
                    """INSERT INTO case_standard
                    (subcategory_id, source_sheet, condition_order, case_condition,
                     time_limit_text, time_limit_hours, close_condition)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        sid, st['source_sheet'], st['condition_order'], st['case_condition'],
                        st['time_limit_text'], st['time_limit_hours'], st['close_condition'],
                    ),
                )

        conn.commit()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM dict_category'); n_cat = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM dict_subcategory'); n_sub = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM case_standard'); n_std = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM dict_subcategory WHERE regulator IS NOT NULL AND regulator != ''"
            )
            n_reg = cur.fetchone()[0]
        print(f'[done] 导入完成: 大类={n_cat} 小类={n_sub} 条件明细={n_std} 含监管主体小类={n_reg}')
        return {'categories': n_cat, 'subcategories': n_sub, 'standards': n_std}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import_all()
