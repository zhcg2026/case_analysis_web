"""
测试火山引擎 API 连接的脚本
"""
import requests
import json

# 火山引擎配置
API_KEY = '58a51ac5-3b75-4c5e-85ac-1fb4ef652bd0'
API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions'
MODEL = 'doubao-seed-1-8-251228'

def test_volcengine():
    print("=" * 60)
    print("开始测试火山引擎 API 连接")
    print("=" * 60)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个 AI 助手"
            },
            {
                "role": "user",
                "content": "你好，请回复'测试成功'"
            }
        ],
        "temperature": 0.3,
        "max_tokens": 100
    }
    
    print(f"\nAPI URL: {API_URL}")
    print(f"模型：{MODEL}")
    print(f"\n发送请求...")
    
    try:
        response = requests.post(
            API_URL, 
            headers=headers, 
            json=payload, 
            timeout=(10, 120)
        )
        
        print(f"\n响应状态码：{response.status_code}")
        print(f"响应头：{dict(response.headers)}")
        print(f"\n完整响应内容:\n{response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n解析成功!")
            print(f"回复内容：{result['choices'][0]['message']['content']}")
            print("\n✅ 火山引擎 API 连接正常!")
            return True
        else:
            print(f"\n❌ API 返回错误状态码：{response.status_code}")
            try:
                error_data = response.json()
                print(f"错误详情：{json.dumps(error_data, ensure_ascii=False)}")
            except:
                print(f"错误内容（非 JSON）: {response.text}")
            return False
            
    except requests.exceptions.Timeout as e:
        print(f"\n❌ 请求超时：{e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接错误：{e}")
        print("可能的原因:")
        print("  1. 网络连接问题")
        print("  2. 防火墙阻止")
        print("  3. DNS 解析失败")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 未知错误：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_volcengine()
