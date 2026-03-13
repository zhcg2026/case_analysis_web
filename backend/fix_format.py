"""
重新修复 app.py - 正确的换行处理
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("重新修复 app.py - 火山引擎 API 错误处理")
print("=" * 60)

# 先恢复原始文件的部分（从备份或重新下载）
# 这里我们直接覆盖错误的部分

# 读取当前文件
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到并替换第一部分（图表需求）
old_part1_marker = "else:            # 调用火山引擎（默认）            try:                print(f\"[火山引擎 - 图表需求]"

if old_part1_marker in content:
    print("\n发现第一部分格式错误，正在修复...")
    
    # 找到错误代码的起始和结束位置
    start_idx = content.find("        else:            # 调用火山引擎（默认）")
    end_marker = "        # 尝试解析 JSON"
    end_idx = content.find(end_marker, start_idx)
    
    if start_idx != -1 and end_idx != -1:
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
        
        content = content[:start_idx] + new_part1 + content[end_idx:]
        print("✅ 第一部分修复完成")
    else:
        print(f"❌ 无法定位第一部分：start={start_idx}, end={end_idx}")
        exit(1)

# 找到并替换第二部分（报告生成）
old_part2_marker = "else:            # 调用火山引擎（默认）            print(f\"[火山引擎 - 报告生成]"

if old_part2_marker in content:
    print("\n发现第二部分格式错误，正在修复...")
    
    start_idx = content.find("        else:            # 调用火山引擎（默认）            print", content.find("分析报告生成"))
    end_marker = "        # 返回结果"
    end_idx = content.find(end_marker, start_idx)
    
    if start_idx != -1 and end_idx != -1:
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
        
        content = content[:start_idx] + new_part2 + content[end_idx:]
        print("✅ 第二部分修复完成")
    else:
        print(f"❌ 无法定位第二部分：start={start_idx}, end={end_idx}")
        exit(1)

# 保存修复后的文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ 所有修复已完成!")
print("\n下一步:")
print("1. 重启后端服务：python app.py")
print("2. 在前端测试数据分析功能")
print("3. 观察控制台日志输出")
