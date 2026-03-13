"""
检查 app.py 的 Python 语法
"""
import py_compile
import sys

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("检查 app.py 的 Python 语法")
print("=" * 60)

try:
    py_compile.compile(file_path, doraise=True)
    print("\n✅ 语法检查通过！")
    print(f"文件：{file_path}")
except py_compile.PyCompileError as e:
    print(f"\n❌ 语法错误:")
    print(f"{e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 未知错误:")
    print(f"{e}")
    sys.exit(1)
