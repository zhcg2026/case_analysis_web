import requests
import json

# 测试分析API
url = "http://localhost:5000/api/analyze"
headers = {
    "Content-Type": "application/json"
}

# 测试数据
payload = {
    "table_name": "case_data",
    "analysis_type": "time_analysis"
}

print("测试分析API...")
print(f"请求URL: {url}")
print(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")

try:
    # 发送请求
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    # 解析响应
    data = response.json()
    print(f"\n响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    if response.status_code == 200:
        print("\n✅ 分析API测试成功!")
        if "analysis" in data:
            print("\n智能分析结果:")
            print(data["analysis"])
        else:
            print("\n⚠️  响应中没有分析结果")
    else:
        print("\n❌ 分析API测试失败!")
        if "error" in data:
            print(f"错误信息: {data['error']}")
            
except requests.exceptions.Timeout:
    print("\n❌ 请求超时!")
except json.JSONDecodeError as e:
    print(f"\n❌ JSON解析错误: {e}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"\n❌ 请求失败: {str(e)}")
