"""
使用 sed 方式修复 app.py
直接替换特定的行
"""
import subprocess
import sys

file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'

print("=" * 60)
print("修复 app.py - 火山引擎 API 错误处理")
print("=" * 60)

# 方法：读取文件，逐行处理，找到目标行后替换
with open(file_path, 'r', encoding='utf-8') as f:
    all_lines = f.readlines()

print(f"\n已读取文件，共 {len(all_lines)} 行")

# 找到需要修改的两个位置
positions = []
for i, line in enumerate(all_lines):
    if '# 调用火山引擎（默认）' in line:
        # 检查是图表需求还是报告生成
        context = ''.join(all_lines[max(0,i-2):min(len(all_lines),i+40)])
        if 'chart_requirement' in context:
            positions.append(('chart', i))
            print(f"找到图表需求部分：第 {i+1} 行")
        elif 'system_prompt' in context and 'final_prompt' in context:
            positions.append(('report', i))
            print(f"找到报告生成部分：第 {i+1} 行")

if len(positions) != 2:
    print(f"\n❌ 找到 {len(positions)} 个位置，应该是 2 个")
    sys.exit(1)

# 创建新的行列表
new_lines = []
i = 0
while i < len(all_lines):
    if i == positions[0][1]:  # 图表需求部分
        # 跳过旧的代码（34 行）
        skip_lines = 34
        indent = '        '
        
        # 添加新的代码
        new_code = f"""{indent}else:
{indent}    # 调用火山引擎（默认）
{indent}    try:
{indent}        print(f"[火山引擎 - 图表需求] 开始调用 API: {{API_URL}}")
{indent}        print(f"[火山引擎 - 图表需求] 使用模型：{{MODEL}}")
{indent}        
{indent}        headers = {{
{indent}            'Content-Type': 'application/json',
{indent}            'Authorization': f'Bearer {{API_KEY}}'
{indent}        }}
{indent}        
{indent}        payload = {{
{indent}            "model": MODEL,
{indent}            "messages": [
{indent}                {{
{indent}                    "role": "system",
{indent}                    "content": chart_requirement_system_prompt
{indent}                }},
{indent}                {{
{indent}                    "role": "user",
{indent}                    "content": chart_requirement_prompt
{indent}                }}
{indent}            ],
{indent}            "temperature": 0.3,
{indent}            "max_tokens": 2000
{indent}        }}
{indent}        
{indent}        print(f"[火山引擎 - 图表需求] 发送请求...")
{indent}        response = requests.post(
{indent}            API_URL, 
{indent}            headers=headers, 
{indent}            json=payload, 
{indent}            timeout=(10, 120)
{indent}        )
{indent}        
{indent}        print(f"[火山引擎 - 图表需求] 响应状态码：{{response.status_code}}")
{indent}        print(f"[火山引擎 - 图表需求] 响应内容前 500 字符：{{response.text[:500]}}...")
{indent}        
{indent}        response.raise_for_status()
{indent}        result = response.json()
{indent}        print(f"[火山引擎 - 图表需求] 解析响应成功")
{indent}        
{indent}        chart_requirement_text = result['choices'][0]['message']['content']
{indent}        print(f"[火山引擎 - 图表需求] 成功获取图表需求，长度：{{len(chart_requirement_text)}}")
{indent}    except requests.exceptions.Timeout as e:
{indent}        print(f"[火山引擎 - 图表需求] 调用超时：{{e}}")
{indent}        chart_requirement_text = None
{indent}        raise Exception(f"火山引擎 API 调用超时：{{str(e)}}")
{indent}    except requests.exceptions.RequestException as e:
{indent}        print(f"[火山引擎 - 图表需求] 网络错误：{{e}}")
{indent}        chart_requirement_text = None
{indent}        raise Exception(f"火山引擎 API 网络错误：{{str(e)}}")
{indent}    except Exception as e:
{indent}        print(f"[火山引擎 - 图表需求] 获取图表需求失败：{{e}}")
{indent}        import traceback
{indent}        traceback.print_exc()
{indent}        chart_requirement_text = None
{indent}        raise Exception(f"获取图表需求失败：{{str(e)}}")
"""
        new_lines.append(new_code)
        i += skip_lines
        print(f"✅ 已替换图表需求部分")
        
    elif i == positions[1][1]:  # 报告生成部分
        # 跳过旧的代码（56 行）
        skip_lines = 56
        indent = '        '
        
        new_code = f"""{indent}else:
{indent}    # 调用火山引擎（默认）
{indent}    print(f"[火山引擎 - 报告生成] 开始调用 API: {{API_URL}}")
{indent}    print(f"[火山引擎 - 报告生成] 使用模型：{{MODEL}}")
{indent}    
{indent}    headers = {{
{indent}        'Content-Type': 'application/json',
{indent}        'Authorization': f'Bearer {{API_KEY}}'
{indent}    }}
{indent}    
{indent}    payload = {{
{indent}        "model": MODEL,
{indent}        "messages": [
{indent}            {{
{indent}                "role": "system",
{indent}                "content": system_prompt
{indent}            }},
{indent}            {{
{indent}                "role": "user",
{indent}                "content": final_prompt
{indent}            }}
{indent}        ],
{indent}        "temperature": 0.3,
{indent}        "max_tokens": 4000
{indent}    }}
{indent}    
{indent}    max_retries = 3
{indent}    retry_delay = 5
{indent}    
{indent}    for attempt in range(max_retries):
{indent}        try:
{indent}            print(f"[火山引擎 - 报告生成] 发送请求 (尝试 {{attempt+1}}/{{max_retries}})...")
{indent}            combined_headers = {{
{indent}                **headers,
{indent}                'Accept': 'application/json',
{indent}                'Connection': 'keep-alive'
{indent}            }}
{indent}            
{indent}            response = requests.post(
{indent}                API_URL, 
{indent}                headers=combined_headers, 
{indent}                json=payload, 
{indent}                timeout=(10, 300)
{indent}            )
{indent}            
{indent}            print(f"[火山引擎 - 报告生成] 响应状态码：{{response.status_code}}")
{indent}            print(f"[火山引擎 - 报告生成] 响应内容前 300 字符：{{response.text[:300]}}...")
{indent}            
{indent}            response.raise_for_status()
{indent}            result = response.json()
{indent}            print(f"[火山引擎 - 报告生成] 解析响应成功")
{indent}            
{indent}            analysis_report = result['choices'][0]['message']['content']
{indent}            print(f"[火山引擎 - 报告生成] 成功获取报告，长度：{{len(analysis_report)}}")
{indent}            break
{indent}        except requests.exceptions.Timeout as e:
{indent}            print(f"[火山引擎 - 报告生成] 调用超时 (尝试 {{attempt+1}}/{{max_retries}}): {{e}}")
{indent}            if attempt < max_retries - 1:
{indent}                print(f"[火山引擎 - 报告生成] {{retry_delay}}秒后重试...")
{indent}                import time
{indent}                time.sleep(retry_delay)
{indent}                retry_delay *= 2
{indent}            else:
{indent}                analysis_report = f"API 调用失败：多次尝试后仍然超时 - {{str(e)}}"
{indent}                break
{indent}        except requests.exceptions.RequestException as e:
{indent}            print(f"[火山引擎 - 报告生成] 网络错误：{{e}}")
{indent}            analysis_report = f"API 调用失败：网络错误 - {{str(e)}}"
{indent}            break
{indent}        except Exception as e:
{indent}            print(f"[火山引擎 - 报告生成] 未知错误：{{e}}")
{indent}            import traceback
{indent}            traceback.print_exc()
{indent}            analysis_report = f"API 调用失败：{{str(e)}}"
{indent}            break
"""
        new_lines.append(new_code)
        i += skip_lines
        print(f"✅ 已替换报告生成部分")
    else:
        new_lines.append(all_lines[i])
        i += 1

# 保存新文件
print(f"\n正在保存修改后的文件...")
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"✅ 修复完成！新文件共 {len(new_lines)} 行")
print(f"\n修改内容:")
print(f"  1. 图表需求生成部分 - 增强错误处理和日志记录")
print(f"  2. 分析报告生成部分 - 增强错误处理和日志记录")
print(f"\n下一步:")
print(f"  1. 重启后端服务：python app.py")
print(f"  2. 在前端测试数据分析功能")
print(f"  3. 观察控制台日志输出（查找 [火山引擎] 开头的日志）")
