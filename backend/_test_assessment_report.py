# -*- coding: utf-8 -*-
"""本地验证：生成202607考核月报并渲染成PNG检查"""
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

# 确保 extra_note 列存在
from assessment_manual_routes import ensure_manual_tables
ensure_manual_tables(engine)

from assessment_report.report_data import collect_report_data
from assessment_report.make_charts import make_charts
from assessment_report.make_docx import generate_word

batch = sys.argv[1] if len(sys.argv) > 1 else '202607'
print(f'== 收集数据 {batch} ...')
data = collect_report_data(engine, batch)
print('期号:', data['issue'])
print('overview:', {k: v for k, v in data['overview'].items() if k != 'special_breakdown'})
print('sources groups:', data['sources']['groups'])
print('disposal rows:', len(data['disposal']['rows']))
print('scores units:', sorted(data['scores'].keys()))
print('work_note lines:', len([l for l in (data['work_note'] or '').splitlines() if l.strip()]))

print('== 出图 ...')
img1, img2 = make_charts(data, os.path.join(BACKEND, 'reports', 'assess_charts'))
print('图1:', img1)
print('图2:', img2)

out = os.path.join(BACKEND, 'reports', f'assessment_{batch}.docx')
print('== 生成Word ...')
generate_word(data, img1, img2, out)
print('OK:', out)

# 渲染检查
if '--render' in sys.argv:
    import win32com.client
    import pymupdf
    pdf_path = out.replace('.docx', '.pdf')
    if not os.path.exists(pdf_path) or '--force' in sys.argv:
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        try:
            doc = word.Documents.Open(out.replace('/', '\\'))
            doc.SaveAs2(pdf_path, FileFormat=17)
            doc.Close(False)
        finally:
            try:
                word.Quit()
            except Exception:
                pass
    pdf = pymupdf.open(pdf_path)
    print(f'PDF页数: {len(pdf)}')
    for i, page in enumerate(pdf):
        pix = page.get_pixmap(dpi=110)
        png = out.replace('.docx', f'_p{i + 1}.png')
        pix.save(png)
        print('页图:', png)
    pdf.close()
