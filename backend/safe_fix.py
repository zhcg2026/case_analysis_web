"""
安全的 app.py 修复脚本 - 使用精确的字符串替换
"""
import re

def fix_app_py():
    file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'
    
    print("=" * 60)
    print("安全修复 app.py - 火山引擎 API 错误处理")
    print("=" * 60)
    
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"原始文件大小：{len(content)} 字符")
    
    # 修复第一部分：图表需求生成
    # 使用正则表达式进行更灵活的匹配
    old_pattern1 = re.compile(
        r'(        else:\s*\n'
        r'            # 调用火山引擎（默认）\s*\n'
        r'            try:\s*\n'
        r'(?:                .*\n)*?'
        r'                response = requests\.post\(\s*\n'
        r'                    API_URL,\s*\n'
        r'                    headers=headers,\s*\n'
        r'                    json=payload,\s*\n'
        r'                    timeout=\(10, 120\)\s*\n'
        r'                \)\s*\n'
        r'                response\.raise_for_status\(\)\s*\n'
        r'                result = response\.json\(\)\s*\n'
        r'                chart_requirement_text = result\[\'choices\'\]\[0\]\[\'message\'\]\[\'content\'\]\s*\n'
        r'            except Exception as e:\s*\n'
        r'                print\(f"获取图表需求失败：\{e\}"\)\s*\n)'
    )
    
    new_code1 = '''        else:
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
                raise Exception(f"获取图表需求失败：{str(e)}")'''
    
    # 应用第一个修复
    matches1 = old_pattern1.findall(content)
    if matches1:
        print(f"✅ 找到第一部分匹配项，共 {len(matches1)} 个")
        content = old_pattern1.sub(new_code1, content, count=1)
        print("✅ 第一部分修复完成")
    else:
        print("❌ 未找到第一部分的匹配项")
        # 显示附近的代码以便调试
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '# 调用火山引擎（默认）' in line and 'chart_requirement' in ''.join(lines[i:i+20]):
                print(f"在第 {i+1} 行附近找到了图表需求部分")
                print('\\n'.join(lines[i:i+30]))
                break
        return False
    
    # 修复第二部分：报告生成
    old_pattern2 = re.compile(
        r'(        else:\s*\n'
        r'            # 调用火山引擎（默认）\s*\n'
        r'            headers = \{\s*\n'
        r'(?:                .*\n)*?'
        r'                for attempt in range\(max_retries\):\s*\n'
        r'                try:\s*\n'
        r'(?:                    .*\n)*?'
        r'                    response = requests\.post\(\s*\n'
        r'                        API_URL,\s*\n'
        r'                        headers=combined_headers,\s*\n'
        r'                        json=payload,\s*\n'
        r'                        timeout=\(10, 300\)\s*\n'
        r'                    \)\s*\n'
        r'                    response\.raise_for_status\(\)\s*\n'
        r'                    result = response\.json\(\)\s*\n'
        r'                    analysis_report = result\[\'choices\'\]\[0\]\[\'message\'\]\[\'content\'\]\s*\n'
        r'                    break\s*\n'
        r'                except requests\.exceptions\.Timeout as e:\s*\n'
        r'(?:                    .*\n)*?'
        r'                except Exception as e:\s*\n'
        r'                    analysis_report = f"API 调用失败：\{str\(e\)}"\s*\n'
        r'                    break\s*\n)'
    )
    
    new_code2 = '''        else:
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
                    break'''
    
    # 应用第二个修复
    matches2 = old_pattern2.findall(content)
    if matches2:
        print(f"✅ 找到第二部分匹配项，共 {len(matches2)} 个")
        content = old_pattern2.sub(new_code2, content, count=1)
        print("✅ 第二部分修复完成")
    else:
        print("❌ 未找到第二部分的匹配项")
        # 显示附近的代码以便调试
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '# 调用火山引擎（默认）' in line and 'system_prompt' in ''.join(lines[i:i+20]):
                print(f"在第 {i+1} 行附近找到了报告生成部分")
                print('\\n'.join(lines[i:i+30]))
                break
        return False
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"修复后文件大小：{len(content)} 字符")
    print("\\n✅ 修复完成！")
    
    # 验证语法
    import py_compile
    try:
        py_compile.compile(file_path, doraise=True)
        print("\\n✅ Python 语法检查通过！")
        return True
    except py_compile.PyCompileError as e:
        print(f"\\n❌ Python 语法错误：{e}")
        return False
    except Exception as e:
        print(f"\\n❌ 未知错误：{e}")
        return False

if __name__ == "__main__":
    success = fix_app_py()
    if success:
        print("\\n🎉 修复成功！现在可以上传到服务器了")
    else:
        print("\\n💥 修复失败，请检查错误信息")