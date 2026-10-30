# -*- coding: utf-8 -*-
"""本地启动验证：加载 app、确认 insp_ 三表建成、users/permissions 加了 inspection 列。"""
import sys, os
root = r'D:\case_analysis_web'
sys.path.insert(0, os.path.join(root, 'backend'))
sys.path.insert(0, root)
from dotenv import load_dotenv
load_dotenv(os.path.join(root, '.env.local'))
load_dotenv(os.path.join(root, 'backend', '.env.local'))

import app as app_module
from sqlalchemy import text

app = app_module.app
engine = app_module.engine
print('app 加载 OK, engine =', engine is not None)

# 路由是否注册
rules = [str(r) for r in app.url_map.iter_rules()]
insp_rules = sorted(r for r in rules if '/api/inspection' in r)
print('\n注册到的 /api/inspection 路由:')
for r in insp_rules:
    print('  ', r)

with engine.connect() as conn:
    tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
    insp_tables = [t for t in tables if t.startswith('insp')]
    print('\ninsp_ 表:', insp_tables)
    assert {'insp_case', 'insp_photo', 'insp_dup_candidate'} <= set(insp_tables), '三张表没建全'

    # 唯一键确认
    idx = conn.execute(text("SHOW INDEX FROM insp_case")).fetchall()
    names = {r[2] for r in idx}
    print('insp_case 索引:', sorted(names))
    assert 'uk_source' in names, 'uk_source 唯一键缺失'

    # permissions 表是否加了 inspection 列
    cols = [r[0] for r in conn.execute(text("SHOW COLUMNS FROM permissions")).fetchall()]
    print('\npermissions.inspection 列存在:', 'inspection' in cols)
    assert 'inspection' in cols, '权限列没加上'

    # users 表是否被误改（只读验证）
    n = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    print('users 行数(应仍为2):', n)
    assert n == 2

print('\n=== 启动验证全部通过 ===')
