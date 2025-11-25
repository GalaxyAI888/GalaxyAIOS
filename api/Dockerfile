FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/cache /app/logs

# 设置环境变量
ENV PYTHONPATH=/app \
    AISTACK_DATA_DIR=/app/data \
    AISTACK_CACHE_DIR=/app/cache

# 暴露端口
EXPOSE 9999

# 启动命令
CMD ["python", "main.py"] 