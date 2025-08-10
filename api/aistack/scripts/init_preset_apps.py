#!/usr/bin/env python3
"""
预设应用初始化脚本
用于创建一些常用的预设应用
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aistack.server.db import get_session
from aistack.server.app_service import AppService
from aistack.schemas.apps import AppCreate, AppTypeEnum, ImageSourceEnum, AppVolume, AppURL


async def init_preset_apps():
    """初始化预设应用"""
    
    # 预设应用配置
    preset_apps = [
        {
            "name": "nginx-web",
            "display_name": "Nginx Web服务器",
            "description": "轻量级的Web服务器，支持静态文件服务",
            "app_type": AppTypeEnum.WEB_APP,
            "image_source": ImageSourceEnum.PULL,
            "image_name": "nginx",
            "image_tag": "alpine",
            "image_url": "nginx:alpine",
            "container_name": "nginx-web-server",
            "ports": {"80": "8080"},
            "environment": {},
            "volumes": [
                AppVolume(
                    host_path="./data/nginx/html",
                    container_path="/usr/share/nginx/html",
                    read_only=False,
                    description="Web文件目录"
                ),
                AppVolume(
                    host_path="./data/nginx/conf",
                    container_path="/etc/nginx/conf.d",
                    read_only=False,
                    description="Nginx配置目录"
                )
            ],
            "urls": [
                AppURL(
                    name="Web界面",
                    url="http://localhost:8080",
                    port=8080,
                    path="/",
                    description="Nginx Web界面",
                    is_primary=True
                )
            ],
            "memory_limit": "256m",
            "cpu_limit": "0.5",
            "tags": ["web", "nginx", "static"],
            "category": "web_server",
            "version": "1.0.0",
            "is_active": True,
            "is_preset": True
        },
        {
            "name": "redis-cache",
            "display_name": "Redis缓存服务器",
            "description": "高性能的内存数据库，支持缓存和消息队列",
            "app_type": AppTypeEnum.API_SERVICE,
            "image_source": ImageSourceEnum.PULL,
            "image_name": "redis",
            "image_tag": "alpine",
            "image_url": "redis:alpine",
            "container_name": "redis-cache-server",
            "ports": {"6379": "6379"},
            "environment": {
                "REDIS_PASSWORD": "your_password_here"
            },
            "volumes": [
                AppVolume(
                    host_path="./data/redis",
                    container_path="/data",
                    read_only=False,
                    description="Redis数据目录"
                )
            ],
            "urls": [
                AppURL(
                    name="Redis CLI",
                    url="redis://localhost:6379",
                    port=6379,
                    path="",
                    description="Redis连接地址",
                    is_primary=True
                )
            ],
            "memory_limit": "512m",
            "cpu_limit": "0.5",
            "tags": ["cache", "redis", "database"],
            "category": "cache",
            "version": "1.0.0",
            "is_active": True,
            "is_preset": True
        },
        {
            "name": "postgres-db",
            "display_name": "PostgreSQL数据库",
            "description": "强大的开源关系型数据库",
            "app_type": AppTypeEnum.API_SERVICE,
            "image_source": ImageSourceEnum.PULL,
            "image_name": "postgres",
            "image_tag": "15-alpine",
            "image_url": "postgres:15-alpine",
            "container_name": "postgres-db-server",
            "ports": {"5432": "5432"},
            "environment": {
                "POSTGRES_DB": "myapp",
                "POSTGRES_USER": "postgres",
                "POSTGRES_PASSWORD": "your_password_here"
            },
            "volumes": [
                AppVolume(
                    host_path="./data/postgres",
                    container_path="/var/lib/postgresql/data",
                    read_only=False,
                    description="PostgreSQL数据目录"
                )
            ],
            "urls": [
                AppURL(
                    name="PostgreSQL连接",
                    url="postgresql://postgres:your_password_here@localhost:5432/myapp",
                    port=5432,
                    path="",
                    description="PostgreSQL连接字符串",
                    is_primary=True
                )
            ],
            "memory_limit": "1g",
            "cpu_limit": "1.0",
            "tags": ["database", "postgresql", "sql"],
            "category": "database",
            "version": "1.0.0",
            "is_active": True,
            "is_preset": True
        },
        {
            "name": "grafana-dashboard",
            "display_name": "Grafana监控面板",
            "description": "开源的数据可视化和监控平台",
            "app_type": AppTypeEnum.WEB_APP,
            "image_source": ImageSourceEnum.PULL,
            "image_name": "grafana/grafana",
            "image_tag": "latest",
            "image_url": "grafana/grafana:latest",
            "container_name": "grafana-dashboard",
            "ports": {"3000": "3000"},
            "environment": {
                "GF_SECURITY_ADMIN_PASSWORD": "admin"
            },
            "volumes": [
                AppVolume(
                    host_path="./data/grafana",
                    container_path="/var/lib/grafana",
                    read_only=False,
                    description="Grafana数据目录"
                )
            ],
            "urls": [
                AppURL(
                    name="Grafana界面",
                    url="http://localhost:3000",
                    port=3000,
                    path="/",
                    description="Grafana监控面板",
                    is_primary=True
                )
            ],
            "memory_limit": "512m",
            "cpu_limit": "0.5",
            "tags": ["monitoring", "grafana", "dashboard"],
            "category": "monitoring",
            "version": "1.0.0",
            "is_active": True,
            "is_preset": True
        },
        {
            "name": "jupyter-notebook",
            "display_name": "Jupyter Notebook",
            "description": "交互式Python开发环境",
            "app_type": AppTypeEnum.WEB_APP,
            "image_source": ImageSourceEnum.PULL,
            "image_name": "jupyter/datascience-notebook",
            "image_tag": "latest",
            "image_url": "jupyter/datascience-notebook:latest",
            "container_name": "jupyter-notebook",
            "ports": {"8888": "8888"},
            "environment": {
                "JUPYTER_TOKEN": "your_token_here"
            },
            "volumes": [
                AppVolume(
                    host_path="./data/jupyter/notebooks",
                    container_path="/home/jovyan/work",
                    read_only=False,
                    description="Jupyter工作目录"
                )
            ],
            "urls": [
                AppURL(
                    name="Jupyter界面",
                    url="http://localhost:8888",
                    port=8888,
                    path="/",
                    description="Jupyter Notebook界面",
                    is_primary=True
                )
            ],
            "memory_limit": "2g",
            "cpu_limit": "1.0",
            "tags": ["python", "jupyter", "development"],
            "category": "development",
            "version": "1.0.0",
            "is_active": True,
            "is_preset": True
        }
    ]
    
    async for session in get_session():
        app_service = AppService()
        
        for app_config in preset_apps:
            try:
                # 检查应用是否已存在
                existing_app = await app_service.get_app_by_name(session, app_config["name"], user_id=1)
                if existing_app:
                    print(f"应用 {app_config['name']} 已存在，跳过创建")
                    continue
                
                # 创建应用
                app_data = AppCreate(**app_config)
                # 使用默认管理员用户ID (1)
                app = await app_service.create_app(session, app_data, user_id=1)
                print(f"成功创建预设应用: {app.name} - {app.display_name}")
                
            except Exception as e:
                print(f"创建应用 {app_config['name']} 失败: {e}")
                continue
        
        break  # 只执行一次


def create_dockerfile_directories():
    """创建Dockerfile目录结构"""
    dockerfile_dirs = [
        "dockerfiles/nginx",
        "dockerfiles/redis", 
        "dockerfiles/postgres",
        "dockerfiles/grafana",
        "dockerfiles/jupyter"
    ]
    
    for dir_path in dockerfile_dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"创建目录: {dir_path}")


def create_sample_dockerfiles():
    """创建示例Dockerfile"""
    
    # Nginx Dockerfile
    nginx_dockerfile = """FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""
    
    # Redis Dockerfile
    redis_dockerfile = """FROM redis:alpine
COPY redis.conf /usr/local/etc/redis/redis.conf
EXPOSE 6379
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
"""
    
    # PostgreSQL Dockerfile
    postgres_dockerfile = """FROM postgres:13
COPY init.sql /docker-entrypoint-initdb.d/
EXPOSE 5432
"""
    
    # Grafana Dockerfile
    grafana_dockerfile = """FROM grafana/grafana:latest
COPY grafana.ini /etc/grafana/grafana.ini
EXPOSE 3000
"""
    
    # Jupyter Dockerfile
    jupyter_dockerfile = """FROM jupyter/datascience-notebook:latest
USER root
RUN pip install --no-cache-dir pandas numpy matplotlib seaborn scikit-learn
USER jovyan
EXPOSE 8888
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
"""
    
    dockerfiles = {
        "dockerfiles/nginx/Dockerfile": nginx_dockerfile,
        "dockerfiles/redis/Dockerfile": redis_dockerfile,
        "dockerfiles/postgres/Dockerfile": postgres_dockerfile,
        "dockerfiles/grafana/Dockerfile": grafana_dockerfile,
        "dockerfiles/jupyter/Dockerfile": jupyter_dockerfile
    }
    
    for file_path, content in dockerfiles.items():
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"创建文件: {file_path}")


async def main():
    """主函数"""
    print("开始初始化预设应用...")
    
    # 创建目录结构
    create_dockerfile_directories()
    create_sample_dockerfiles()
    
    # 初始化预设应用
    await init_preset_apps()
    
    print("预设应用初始化完成！")


if __name__ == "__main__":
    asyncio.run(main()) 