"""
调试 /api/analyze-v2 端点的脚本
用于模拟前端请求，测试后端 API 是否正常工作
"""
import requests
import json

# 后端 API 地址
BACKEND_URL = 'http://localhost:5000/api/analyze-v2'

# JWT Token（需要从前端获取或使用 admin token）
# 注意：你需要替换为有效的 token
TOKEN = 'your-jwt-token-here'

def test_analyze_v2():
    print("=" * 60)
    print("测试 /api/analyze-v2 端点")
    print("=" * 60)
    
    # 测试数据
    payload = {
        "table_name": "test_table",  # 替换为实际的表名
        "prompt": "请分析数据的趋势",
        "model": "volcengine"  # 或者 "bailian"
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TOKEN}'
    }
    
    print(f"\n请求 URL: {BACKEND_URL}")
    print(f"请求数据：{json.dumps(payload, ensure_ascii=False)}")
    print(f"\n发送请求...")
    
    try:
        response = requests.post(
            BACKEND_URL,
            headers=headers,
            json=payload,
            timeout=(10, 600)  # 连接超时 10 秒，读取超时 600 秒
        )
        
        print(f"\n响应状态码：{response.status_code}")
        print(f"响应头：{dict(response.headers)}")
        print(f"\n完整响应内容:\n{response.text[:1000]}...")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功!")
            print(f"报告长度：{len(result.get('report', ''))}")
            print(f"图表数量：{len(result.get('charts', []))}")
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
        print("建议:")
        print("  1. 检查后端服务是否正常运行")
        print("  2. 检查火山引擎 API 是否响应缓慢")
        print("  3. 增加超时时间")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接错误：{e}")
        print("可能的原因:")
        print("  1. 后端服务未启动")
        print("  2. 端口被防火墙阻止")
        print("  3. 后端服务崩溃")
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
    print("\n⚠️ 注意：在运行此脚本之前，请确保:")
    print("1. 后端服务正在运行 (python app.py)")
    print("2. 已替换有效的 JWT TOKEN")
    print("3. 数据库中有测试数据表")
    print("\n按 Enter 继续或 Ctrl+C 退出...")
    input()
    test_analyze_v2()
