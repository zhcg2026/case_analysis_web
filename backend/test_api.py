import requests
import json

# 测试登录获取token
def test_login():
    url = "http://localhost:5000/api/login"
    data = {
        "username": "admin",
        "password": "admin123"
    }
    response = requests.post(url, json=data)
    print(f"Login status code: {response.status_code}")
    if response.status_code == 200:
        return response.json()
    return None

# 测试获取用户信息
def test_get_user(token):
    url = "http://localhost:5000/api/user"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    print(f"Get user status code: {response.status_code}")
    print(f"Get user response: {response.json()}")

# 测试获取用户列表
def test_get_users(token):
    url = "http://localhost:5000/api/users"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    print(f"Get users status code: {response.status_code}")
    print(f"Get users response: {response.json()}")

# 测试获取栏目列表
def test_get_categories():
    url = "http://localhost:5000/api/categories"
    response = requests.get(url)
    print(f"Get categories status code: {response.status_code}")
    print(f"Get categories response: {response.json()}")

# 运行测试
if __name__ == "__main__":
    print("Testing API endpoints...")
    login_result = test_login()
    if login_result:
        token = login_result.get("token")
        print(f"Got token: {token[:50]}...")
        
        print("\nTesting authenticated endpoints:")
        test_get_user(token)
        test_get_users(token)
    
    print("\nTesting public endpoints:")
    test_get_categories()
    print("\nAll tests completed!")
