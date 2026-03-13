"""
自动应用火山引擎 API 错误处理修复的脚本
"""
import re

def fix_chart_requirement_section(content):
    """修复图表需求生成部分的错误处理"""
    
    # 查找并替换图表需求生成部分
    old_pattern = r"""(        else:
            # 调用火山引擎（默认）
            try:
                headers = \{
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer \{API_KEY\}'
                \}
                
                payload = \{
                    "model": MODEL,
                    "messages": \[
                        \{
                            "role": "system",
                            "content": chart_requirement_system_prompt
                        \},
                        \{
                            "role": "user",
                            "content": chart_requirement_prompt
                        \}
                    \],
                    "temperature": 0\.3,
                    "max_tokens": 2000
                \}
                
                response = requests\.post\(
                    API_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=\(10, 120\)
                \)
                response\.raise_for_status\(\)
                result = response\.json\(\)
                chart_requirement_text = result\['choices'\]\[0\]\['message'\]\['content'\]
            except Exception as e:
                print\(f"获取图表需求失败：\{e\}"\)
        \)"""
    
    new_code = r"""        else:
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
        )"""
    
    # 使用更简单的方法：直接字符串替换
    old_code = """        else:
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
    
    new_code_simple = """        else:
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
    
    if old_code in content:
        content = content.replace(old_code, new_code_simple)
        print("✅ 已修复图表需求生成部分")
        return content, True
    else:
        print("❌ 未找到图表需求生成部分的代码")
        return content, False

def main():
    print("=" * 60)
    print("自动应用火山引擎 API 错误处理修复")
    print("=" * 60)
    
    # 读取文件
    file_path = r'c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py'
    
    print(f"\n正在读取文件：{file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"文件大小：{len(content)} 字符")
    
    # 应用修复
    print("\n正在应用修复...")
    content, success = fix_chart_requirement_section(content)
    
    if success:
        # 保存修改后的文件
        print(f"\n正在保存修改...")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ 修复已成功应用!")
        print("\n下一步:")
        print("1. 重启后端服务：python app.py")
        print("2. 在前端测试数据分析功能")
        print("3. 观察控制台日志输出")
    else:
        print("\n❌ 修复应用失败")
        print("请手动修改 app.py 文件")
        print("参考文件：backend/app_fix.py")

if __name__ == '__main__':
    main()
