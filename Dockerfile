# 多阶段构建 - 使用官方 Python 运行时作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置 pip 镜像源（加速下载）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装系统依赖（一次性安装，利用缓存）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ffmpeg \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区为北京时间
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制后端需求文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建的文件
COPY frontend/dist/ ./frontend/dist/

# 创建上传目录
RUN mkdir -p ./backend/uploads

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV FLASK_APP=backend/app.py
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 启动应用
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "gthread", "--threads", "4", "--timeout", "300", "--graceful-timeout", "60", "backend.app:app"]
