"""
修复 /api/analyze-v2 中火山引擎 API 调用的错误处理
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("修复 app.py - 火山引擎 API 错误处理")
print("=" * 60)

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\n已读取文件，共 {len(lines)} 行")

# 找到需要修改的位置（第 3589-3623 行）
# 查找特征：else: 后面跟着 # 调用火山引擎（默认）
target_line = None
for i in range(3580, 3600):
    if i < len(lines) and '调用火山引擎（默认）' in lines[i]:
        target_line = i
        print(f"找到目标位置：第 {i+1} 行")
        break

if target_line is None:
    print("❌ 未找到目标位置")
    exit(1)

# 找到结束位置（except Exception 块结束）
end_line = None
for i in range(target_line, min(len(lines), target_line + 50)):
    if 'print(f"获取图表需求失败：{e}")' in lines[i]:
        end_line = i
        print(f"找到结束位置：第 {i+1} 行")
        break

if end_line is None:
    print("❌ 未找到结束位置")
    exit(1)

# 创建新的代码
new_code = """        else:
            # 调用火山引擎（默认）
            try:
                print(f"[火山引擎 - 图表需求] 开始调用 API")
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {API_KEY}'
                }
                
                payload = {
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": chart_requirement_system_prompt
                        },
                        {
                            "role": "user",
                            "content": chart_requirement_prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }
                
                print(f"[火山引擎 - 图表需求] 发送请求...")
                response = requests.post(
                    API_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=(10, 120)
                )
                
                print(f"[火山引擎 - 图表需求] 响应状态码：{response.status_code}")
                response.raise_for_status()
                result = response.json()
                chart_requirement_text = result['choices'][0]['message']['content']
                print(f"[火山引擎 - 图表需求] 成功获取图表需求")
            except requests.exceptions.Timeout as e:
                print(f"[火山引擎 - 图表需求] 调用超时：{e}")
                chart_requirement_text = None
                raise Exception(f"火山引擎 API 调用超时：{str(e)}")
            except requests.exceptions.RequestException as e:
                print(f"[火山引擎 - 图表需求] 网络错误：{e}")
                chart_requirement_text = None
                raise Exception(f"火山引擎 API 网络错误：{str(e)}")
            except Exception as e:
                print(f"[火山引擎 - 图表需求] 获取图表需求失败：{e}")
                import traceback
                traceback.print_exc()
                chart_requirement_text = None
                raise Exception(f"获取图表需求失败：{str(e)}")
        
"""

# 替换代码
print(f"\n正在替换第 {target_line+1} 到 {end_line+1} 行...")
new_lines = lines[:target_line] + [new_code] + lines[end_line+1:]

# 保存
print(f"正在保存文件...")
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n✅ 修复完成！")
print(f"\n修改内容:")
print(f"  - 添加详细的日志输出")
print(f"  - 区分处理超时、网络错误和其他异常")
print(f"  - 异常时重新抛出，避免 worker 超时")
print(f"\n下一步:")
print(f"  1. 提交到 Git: git add backend/app.py && git commit -m 'Fix: 增强火山引擎 API 错误处理'")
print(f"  2. 推送到远程：git push origin main")
print(f"  3. 在服务器上更新：git pull origin main && docker-compose restart")
