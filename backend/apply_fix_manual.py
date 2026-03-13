"""
手动修复 app.py - 使用精确的字符串替换
避免重复的 else 语句
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("修复 app.py - 火山引擎 API 错误处理")
print("=" * 60)

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"\n已读取文件，大小：{len(content)} 字符")

# 第一部分：图表需求生成
old_part1 = """        else:
            # 调用火山引擎（默认）
            try:
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
                
                response = requests.post(
                    API_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=(10, 120)
                )
                response.raise_for_status()
                result = response.json()
                chart_requirement_text = result['choices'][0]['message']['content']
            except Exception as e:
                print(f"获取图表需求失败：{e}")"""

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
                raise Exception(f"获取图表需求失败：{str(e)}")"""

if old_part1 in content:
    content = content.replace(old_part1, new_part1)
    print("✅ 第一部分替换成功")
else:
    print("❌ 未找到第一部分的精确匹配")
    exit(1)

# 第二部分：报告生成
old_part2 = """        else:
            # 调用火山引擎（默认）
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
                    response.raise_for_status()
                    result = response.json()
                    analysis_report = result['choices'][0]['message']['content']
                    break
                except requests.exceptions.Timeout as e:
                    if attempt < max_retries - 1:
                        print(f"API 调用超时，{retry_delay}秒后重试... (尝试 {attempt+1}/{max_retries})")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        analysis_report = f"API 调用失败：多次尝试后仍然超时 - {str(e)}"
                        break
                except Exception as e:
                    analysis_report = f"API 调用失败：{str(e)}"
                    break"""

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
                    break"""

if old_part2 in content:
    content = content.replace(old_part2, new_part2)
    print("✅ 第二部分替换成功")
else:
    print("❌ 未找到第二部分的精确匹配")
    exit(1)

# 保存文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ 修复完成！")
print(f"\n修改内容:")
print(f"  1. 图表需求生成部分 - 增强错误处理和日志记录")
print(f"  2. 分析报告生成部分 - 增强错误处理和日志记录")
print(f"\n下一步:")
print(f"  1. 上传文件到服务器")
print(f"  2. 重启 Docker 容器：docker-compose restart case-analysis-app")
print(f"  3. 查看日志：docker-compose logs -f case-analysis-app")
