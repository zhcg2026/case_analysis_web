"""
使用行号精确替换 - 避免字符串匹配问题
"""

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("使用行号精确替换")
print("=" * 60)

# 读取所有行
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"\n已读取 {len(lines)} 行")

# 找到需要替换的行范围
# 第一部分：图表需求 (3589-3623 行)
# 第二部分：报告生成 (3879-3934 行)

# 验证行号
if '# 调用火山引擎（默认）' in lines[3589] and 'chart_requirement' in ''.join(lines[3589:3625]):
    print(f"✅ 确认第一部分位置：3589-3623 行")
    part1_start = 3589
    part1_end = 3624  # 不包含 3624
else:
    print(f"❌ 第一部分位置不对")
    print(f"3589 行内容：{lines[3589]}")
    exit(1)

if '# 调用火山引擎（默认）' in lines[3879] and 'system_prompt' in ''.join(lines[3879:3935]):
    print(f"✅ 确认第二部分位置：3879-3934 行")
    part2_start = 3879
    part2_end = 3935  # 不包含 3935
else:
    print(f"❌ 第二部分位置不对")
    print(f"3879 行内容：{lines[3879]}")
    exit(1)

# 创建新的代码
# 第一部分
part1_new = """        else:
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

# 第二部分
part2_new = """        else:
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

# 执行替换
print(f"\n正在替换第一部分...")
new_lines = lines[:part1_start] + [part1_new] + lines[part1_end:]
lines = new_lines
print(f"✅ 第一部分完成，现在共 {len(lines)} 行")

# 重新计算第二部分的位置（因为第一部分改变了行数）
# 第一部分从 35 行变成 70 行，增加了 35 行
offset = 70 - 35
part2_start_new = part2_start + offset
part2_end_new = part2_end + offset + (70 - 56)  # 第二部分从 56 行变成 74 行

print(f"\n正在替换第二部分...")
print(f"新位置：{part2_start_new}-{part2_end_new} 行")
new_lines = lines[:part2_start_new] + [part2_new] + lines[part2_end_new:]
lines = new_lines
print(f"✅ 第二部分完成，现在共 {len(lines)} 行")

# 保存
print(f"\n正在保存文件...")
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\n✅ 修复完成！")
print(f"\n下一步:")
print(f"  1. 上传文件到服务器")
print(f"  2. 重启 Docker 容器：docker-compose restart case-analysis-app")
print(f"  3. 查看日志：docker-compose logs -f case-analysis-app")
