import requests
import os

# 测试登录获取token
def test_login():
    url = 'http://localhost:5000/api/login'
    data = {
        'username': 'admin',
        'password': 'admin123'
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()['token']
    else:
        print(f"Login failed: {response.text}")
        return None

# 测试案件抽查API
def test_spotcheck(token):
    url = 'http://localhost:5000/api/spotcheck'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    # 准备文件
    file_path = 'test_case.xlsx'
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    # 上传文件
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f)}
        response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        result = response.json()
        print("Spotcheck API test successful!")
        print(f"File name: {result.get('file_name')}")
        print("\nAnalysis result:")
        print(result.get('analysis', ''))
        print("\nScores:")
        print(result.get('scores', {}))
    else:
        print(f"Spotcheck API test failed: {response.status_code}")
        print(f"Error: {response.text}")

if __name__ == "__main__":
    print("Testing login API...")
    token = test_login()
    if token:
        print(f"Login successful, token: {token}")
        print("\nTesting spotcheck API...")
        test_spotcheck(token)
    else:
        print("Login failed, cannot test spotcheck API")
