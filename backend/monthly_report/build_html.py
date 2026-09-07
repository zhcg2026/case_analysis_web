# -*- coding: utf-8 -*-
"""把 analysis.json 注入模板，生成最终交互式 HTML 报告
用法：python build_html.py <config.json>
"""
import json, io, os, sys

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
SK = os.path.dirname(os.path.abspath(__file__))


def _p(*a):
    return os.path.join(BASE, *a)


MC = CFG.get('month_cn', '2026年1月')
ORG = CFG.get('org', '')
TITLE = CFG.get('title', MC + '份城市管理案件数据分析报告')
MAP = {
    '__TITLE__': TITLE,
    '__ORG__': ORG,
    '__ORG_DOT__': CFG.get('org_dot', ORG),
    '__MONTH_CN__': MC,
    '__SRC_FILE__': os.path.basename(CFG.get('src', '案件数据.xlsx')),
}

data = io.open(_p(CFG.get('out_json', 'analysis.json')), encoding='utf-8').read()
tpl = io.open(os.path.join(SK, 'template.html'), encoding='utf-8').read()
out = tpl.replace('__DATA__', data)
for k, v in MAP.items():
    out = out.replace(k, v)
dst = _p(CFG.get('out_html', '案件数据分析报告.html'))
with io.open(dst, 'w', encoding='utf-8') as f:
    f.write(out)
left = [k for k in MAP if k in out]
print(('!! 未替换占位符: %s' % left) if left else '占位符替换完成')
print('HTML 生成完成：%s（%.1f KB）' % (dst, len(out.encode('utf-8')) / 1024))
