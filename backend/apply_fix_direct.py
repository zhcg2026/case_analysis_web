"""
直接修改 app.py 文件，修复火山引擎 API 调用的错误处理
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("修复 app.py - 火山引擎 API 错误处理")
print("=" * 60)

# 读取整个文件
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\n已读取文件，共 {len(lines)} 行")

# 定义替换内容
# 第一部分：图表需求生成（第 3589-3624 行，索引 3588-3623）
old_part1_lines = lines[3588:3624]
new_part1 = """        else:
            # 调用火山引擎（默认）
            try:
                print(f"[火山引擎 - 图表需求] 开始调用 API: {API_URL}")
                print(f"[火山引擎 - 图表需求] 使用模型：{MODEL}")
                
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
                print(f"[火山引擎 - 图表需求] 响应内容前 500 字符：{response.text[:500]}...")
                
                response.raise_for_status()
                result = response.json()
                print(f"[火山引擎 - 图表需求] 解析响应成功")
                
                chart_requirement_text = result['choices'][0]['message']['content']
                print(f"[火山引擎 - 图表需求] 成功获取图表需求，长度：{len(chart_requirement_text)}")
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

# 第二部分：报告生成部分（第 3879-3935 行，索引 3878-3934）
# 需要先找到准确的位置
report_start_idx = None
for i in range(3878, 3883):
    if i < len(lines) and '# 调用火山引擎（默认）' in lines[i]:
        report_start_idx = i
        break

if report_start_idx is None:
    print("\n❌ 未找到报告生成部分的位置")
    exit(1)

print(f"\n找到报告生成部分起始位置：第 {report_start_idx+1} 行")

# 找到这部分的结束位置（# 返回结果 之前）
report_end_idx = None
for i in range(report_start_idx, min(len(lines), report_start_idx+60)):
    if '# 返回结果' in lines[i]:
        report_end_idx = i
        break

if report_end_idx is None:
    print("\n❌ 未找到报告生成部分的结束位置")
    exit(1)

print(f"找到报告生成部分结束位置：第 {report_end_idx+1} 行")

# 替换第一部分
print(f"\n正在替换第一部分（图表需求生成）...")
new_lines = lines[:3588] + new_part1.split('\n')[:-1] + ['\n'] + lines[3624:]
lines = new_lines
print(f"✅ 第一部分替换完成，现在共 {len(lines)} 行")

# 重新计算第二部分的索引（因为第一部分已经改变了行数）
report_start_idx = None
for i in range(len(lines)):
    if i > 3800 and '# 调用火山引擎（默认）' in lines[i] and '报告生成' not in lines[i-1]:
        # 检查是否是报告生成部分（不是图表需求部分）
        if 'system_prompt' in ''.join(lines[i:i+15]):
            report_start_idx = i
            break

if report_start_idx is None:
    print("\n❌ 未找到第二部分的位置")
    exit(1)

print(f"\n找到第二部分起始位置：第 {report_start_idx+1} 行")

# 找到结束位置
report_end_idx = None
for i in range(report_start_idx, min(len(lines), report_start_idx+60)):
    if '# 返回结果' in lines[i]:
        report_end_idx = i
        break

if report_end_idx is None:
    print("\n❌ 未找到第二部分的结束位置")
    exit(1)

print(f"找到第二部分结束位置：第 {report_end_idx+1} 行")

# 替换第二部分
new_part2 = """        else:
            # 调用火山引擎（默认）
            print(f"[火山引擎 - 报告生成] 开始调用 API: {API_URL}")
            print(f"[火山引擎 - 报告生成] 使用模型：{MODEL}")
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            }
            
            payload = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": final_prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            }
            
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    print(f"[火山引擎 - 报告生成] 发送请求 (尝试 {attempt+1}/{max_retries})...")
                    combined_headers = {
                        **headers,
                        'Accept': 'application/json',
                        'Connection': 'keep-alive'
                    }
                    
                    response = requests.post(
                        API_URL, 
                        headers=combined_headers, 
                        json=payload, 
                        timeout=(10, 300)
                    )
                    
                    print(f"[火山引擎 - 报告生成] 响应状态码：{response.status_code}")
                    print(f"[火山引擎 - 报告生成] 响应内容前 300 字符：{response.text[:300]}...")
                    
                    response.raise_for_status()
                    result = response.json()
                    print(f"[火山引擎 - 报告生成] 解析响应成功")
                    
                    analysis_report = result['choices'][0]['message']['content']
                    print(f"[火山引擎 - 报告生成] 成功获取报告，长度：{len(analysis_report)}")
                    break
                except requests.exceptions.Timeout as e:
                    print(f"[火山引擎 - 报告生成] 调用超时 (尝试 {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        print(f"[火山引擎 - 报告生成] {retry_delay}秒后重试...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        analysis_report = f"API 调用失败：多次尝试后仍然超时 - {str(e)}"
                        break
                except requests.exceptions.RequestException as e:
                    print(f"[火山引擎 - 报告生成] 网络错误：{e}")
                    analysis_report = f"API 调用失败：网络错误 - {str(e)}"
                    break
                except Exception as e:
                    print(f"[火山引擎 - 报告生成] 未知错误：{e}")
                    import traceback
                    traceback.print_exc()
                    analysis_report = f"API 调用失败：{str(e)}"
                    break
        
"""

print(f"\n正在替换第二部分（分析报告生成）...")
new_lines = lines[:report_start_idx] + new_part2.split('\n')[:-1] + ['\n'] + lines[report_end_idx:]
lines = new_lines
print(f"✅ 第二部分替换完成，现在共 {len(lines)} 行")

# 保存修改后的文件
print(f"\n正在保存文件...")
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\n✅ 修复已成功应用!")
print(f"\n修改内容:")
print(f"  1. 增强图表需求生成部分的错误处理和日志记录")
print(f"  2. 增强分析报告生成部分的错误处理和日志记录")
print(f"\n下一步:")
print(f"  1. 重启后端服务：python app.py")
print(f"  2. 在前端测试数据分析功能")
print(f"  3. 观察控制台日志输出（查找 [火山引擎] 开头的日志）")
