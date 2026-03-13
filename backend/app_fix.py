# 火山引擎 API 调用错误修复说明

## 问题原因

`ERR_EMPTY_RESPONSE` 错误通常是因为后端在处理请求时发生未捕获的异常，导致连接被直接关闭。

## 需要修改的位置

### 修改 1：增强图表需求生成部分的错误处理（第 3589-3623 行）

将原来的代码：

```python
else:
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
        print(f"获取图表需求失败：{e}")
```

替换为：

```python
else:
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
```

### 修改 2：增强分析报告生成部分的错误处理（第 3879-3934 行）

将原来的代码：

```python
else:
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
            break
```

替换为：

```python
else:
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
```

## 手动修改步骤

1. 打开文件 `c:\Users\Administrator\Documents\trae_projects\case_analysis_web\backend\app.py`

2. 找到第 3589-3623 行（图表需求生成部分）

3. 按照上面的"修改 1"替换代码

4. 找到第 3879-3934 行（报告生成部分）

5. 按照上面的"修改 2"替换代码

6. 保存文件并重启后端服务

## 测试方法

1. 启动后端服务：
   ```bash
   cd backend
   python app.py
   ```

2. 观察控制台日志，应该看到类似这样的输出：
   ```
   [火山引擎 - 图表需求] 开始调用 API: https://ark.cn-beijing.volces.com/api/v3/chat/completions
   [火山引擎 - 图表需求] 使用模型：doubao-seed-1-8-251228
   [火山引擎 - 图表需求] 发送请求...
   [火山引擎 - 图表需求] 响应状态码：200
   [火山引擎 - 图表需求] 响应内容前 500 字符：...
   [火山引擎 - 图表需求] 解析响应成功
   [火山引擎 - 图表需求] 成功获取图表需求，长度：xxx
   ```

3. 如果出错，会看到详细的错误信息，例如：
   ```
   [火山引擎 - 图表需求] 调用超时：...
   [火山引擎 - 图表需求] 网络错误：...
   ```

## 已创建的辅助工具

1. **test_volcengine.py** - 测试火山引擎 API 直连是否正常
   ```bash
   python test_volcengine.py
   ```

2. **debug_analyze_v2.py** - 端到端测试 /api/analyze-v2 接口
   ```bash
   python debug_analyze_v2.py
   ```

3. **火山引擎错误诊断与修复方案.md** - 详细的诊断和修复文档

## 快速解决方案

如果问题仍然存在，可以临时将默认模型切换为阿里云百炼：

修改 `app.py` 第 3512 行：

```python
# 原来
model_choice = data.get('model', 'volcengine')  # 默认使用火山引擎

# 修改为
model_choice = data.get('model', 'bailian')  # 默认使用阿里云百炼
```

或者在前端默认选择阿里云百炼。
