# -*- coding: utf-8 -*-
"""工具函数模块 - 从app.py提取的通用工具函数"""
import os
import re
import hashlib
import time
import datetime
import requests
from functools import wraps
from flask import request, jsonify

# 登录失败限制配置
LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300

def hash_password(password):
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password, hashed):
    import bcrypt
    if hashed.startswith("$2b$"):
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    else:
        return hashlib.sha256(password.encode()).hexdigest() == hashed

def is_strong_password(password):
    if len(password) < 8:
        return False, "密码长度至少8位"
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "密码必须包含字母和数字"
    return True, None

def check_login_attempts(username):
    if username not in LOGIN_ATTEMPTS:
        return True, None
    attempt = LOGIN_ATTEMPTS[username]
    if attempt["count"] >= MAX_LOGIN_ATTEMPTS:
        if time.time() < attempt["lock_until"]:
            remaining = int(attempt["lock_until"] - time.time())
            return False, f"账户已锁定，请{remaining}秒后再试"
        else:
            LOGIN_ATTEMPTS[username] = {"count": 0, "lock_until": 0}
    return True, None

def record_failed_login(username):
    if username not in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[username] = {"count": 0, "lock_until": 0}
    LOGIN_ATTEMPTS[username]["count"] += 1
    if LOGIN_ATTEMPTS[username]["count"] >= MAX_LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[username]["lock_until"] = time.time() + LOCKOUT_DURATION

def clear_login_attempts(username):
    if username in LOGIN_ATTEMPTS:
        del LOGIN_ATTEMPTS[username]

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError('JWT_SECRET_KEY 未配置，禁止启动')
TOKEN_EXPIRATION = int(os.getenv("TOKEN_EXPIRATION_SECONDS", str(24 * 60 * 60)))

def generate_token(user_id, username, role):
    import jwt
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRATION)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    import jwt
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None



def generate_slug(text):
    slug = text.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^\u4e00-\u9fa5a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = hashlib.md5(text.encode()).hexdigest()[:8]
    return slug

def protected(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        if token.startswith("Bearer "):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.user_id = payload["user_id"]
        request.username = payload["username"]
        request.role = payload["role"]
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        if token.startswith("Bearer "):
            token = token[7:]
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        if payload["role"] != "admin":
            return jsonify({"error": "Admin permission required"}), 403
        request.user_id = payload["user_id"]
        request.username = payload["username"]
        request.role = payload["role"]
        return f(*args, **kwargs)
    return decorated

def get_json_payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

