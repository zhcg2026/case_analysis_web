"""
修复 app.py 中火山引擎 API 调用的错误处理
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("修复 app.py 中火山引擎 API 调用的错误处理")
print("=" * 60)

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\n已读取文件，共 {len(lines)} 行")

# 找到需要修改的行号
chart_req_start = None
report_start = None

for i, line in enumerate(lines):
    if i >= 3588 and i <= 3592 and '# 调用火山引擎（默认）' in line and chart_req_start is None:
        chart_req_start = i
        print(f"找到图表需求部分起始位置：第 {i+1} 行")
    if i >= 3878 and i <= 3882 and '# 调用火山引擎（默认）' in line and report_start is None:
        report_start = i
        print(f"找到报告生成部分起始位置：第 {i+1} 行")

if chart_req_start:
    print(f"\n✅ 找到两处需要修改的位置")
    print(f"   1. 图表需求生成：第 {chart_req_start+1} 行")
    print(f"   2. 分析报告生成：第 {report_start+1} 行")
else:
    print(f"\n❌ 未找到需要修改的位置")
    print(f"   chart_req_start: {chart_req_start}")
    print(f"   report_start: {report_start}")

# 显示找到的位置附近的代码
if chart_req_start:
    print(f"\n图表需求部分附近代码:")
    for i in range(max(0, chart_req_start-1), min(len(lines), chart_req_start+35)):
        print(f"{i+1}: {lines[i]}", end='')

if report_start:
    print(f"\n\n报告生成部分附近代码:")
    for i in range(max(0, report_start-1), min(len(lines), report_start+60)):
        print(f"{i+1}: {lines[i]}", end='')

print("\n\n由于自动修复失败，请手动修改文件")
print("详细步骤请参考 backend/app_fix.py")
