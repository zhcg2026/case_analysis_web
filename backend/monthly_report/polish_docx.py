# -*- coding: utf-8 -*-
"""Word 成稿美化：把 charts_opt/ 的高清图替换进 docx，并统一表格样式
用法：python polish_docx.py <config.json>
替换原有的 build_optimized.py：不再依赖外部解包目录，直接用 python-docx 操作，可移植
"""
import json, os, sys
from docx import Document
from docx.shared import Cm, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CFG = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else {}
BASE = CFG.get('workdir', os.getcwd())
SK = os.path.dirname(os.path.abspath(__file__))


def _p(*a):
    return os.path.join(BASE, *a)


SRC = _p(CFG.get('out_docx', 'report.docx'))
CHARTS = _p('charts_opt')
PROP = os.path.join(CHARTS, 'proportions.json')

# 图表替换顺序：与 make_word.py 中 pic(F1)..pic(F9) 的插入顺序一致
MEDIA_MAP = [
    'fig1_dalei.png', 'fig2_pareto.png', 'fig3_daily.png', 'fig4_hour.png',
    'fig7_dalei_dur.png', 'fig8_dept_dur.png',
    'fig5_recur_scatter.png', 'fig6_recur_top.png', 'fig9_sup.png',
]
FULL_WIDTH = CFG.get('img_width_cm', 13.6)      # 通栏图宽度（厘米）
NARROW_WIDTH = CFG.get('img_narrow_cm', 12.2)   # 竖图（如监督员分布）宽度

if not os.path.exists(PROP):
    print('!! 未找到 %s，请先运行 polish_charts.py' % PROP)
    sys.exit(1)
props = json.load(open(PROP, encoding='utf-8'))

doc = Document(SRC)

# ---------- 1 替换图片 ----------
shapes = doc.inline_shapes
n = min(len(shapes), len(MEDIA_MAP))
for i in range(n):
    fname = MEDIA_MAP[i]
    fp = os.path.join(CHARTS, fname)
    if not os.path.exists(fp):
        print('  !! 缺图:', fname)
        continue
    sh = shapes[i]
    ratio = props.get(fname, {}).get('ratio') or 1.6
    try:
        blip = sh._inline.graphic.graphicData.pic.blipFill.blip
        _, rId = doc.part.get_or_add_image(fp)     # 自动去重，返回 (part, rId)
        if blip.get(qn('r:link')) is not None:     # 原图为外链时先清掉，避免与嵌入冲突
            del blip.attrib[qn('r:link')]
        blip.rEmbed = rId
    except Exception as e:
        print('  !! 替换失败 %s: %s' % (fname, e))
        continue
    w = NARROW_WIDTH if ratio < 1.35 else FULL_WIDTH
    sh.width = Cm(w)
    sh.height = Cm(w / ratio)
print('图片替换：%d/%d' % (n, len(MEDIA_MAP)))

# ---------- 2 表格样式 ----------
HEAD_FILL = CFG.get('table_head_fill', '17365D')
HEAD_FONT = CFG.get('table_head_font', 'FFFFFF')
ZEBRA = CFG.get('table_zebra', 'F3F7FC')


def shade(cell, color):
    el = OxmlElement('w:shd')
    el.set(qn('w:val'), 'clear')
    el.set(qn('w:color'), 'auto')
    el.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(el)


def set_cell(cell, text, bold=False, color=None, size=9.5, align=None):
    cell.text = ''
    p = cell.paragraphs[0]
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(1.5)
    p.paragraph_format.space_after = Pt(1.5)
    r = p.add_run(str(text))
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = '仿宋_GB2312'
    r._element.rPr.rFonts.set(qn('w:eastAsia'), '仿宋_GB2312')
    if color:
        r.font.color.rgb = color


from docx.shared import RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

for ti, tb in enumerate(doc.tables):
    for ri, row in enumerate(tb.rows):
        for ci, cell in enumerate(row.cells):
            txt = cell.text
            if ri == 0:
                set_cell(cell, txt, bold=True,
                         color=RGBColor.from_string(HEAD_FONT), size=9.5,
                         align=WD_ALIGN_PARAGRAPH.CENTER)
                shade(cell, HEAD_FILL)
            else:
                head = tb.rows[0].cells[ci].text if ci < len(tb.rows[0].cells) else ''
                is_num = txt.replace(',', '').replace('%', '').replace('.', '').replace('-', '').isdigit()
                set_cell(cell, txt, size=9.5,
                         align=WD_ALIGN_PARAGRAPH.CENTER if (ci == 0 or is_num) else WD_ALIGN_PARAGRAPH.LEFT)
                if ri % 2 == 0:
                    shade(cell, ZEBRA)
print('表格样式：%d 张' % len(doc.tables))

DST = _p(CFG.get('out_docx_final', CFG.get('out_docx', 'report.docx').replace('.docx', '_优化版.docx')))
try:
    doc.save(DST)
    print('成稿保存：', DST)
except Exception as e:
    DST = DST.replace('.docx', '_new.docx')
    doc.save(DST)
    print('原文件被占用，已另存为：', DST)
