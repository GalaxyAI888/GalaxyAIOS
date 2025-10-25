#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试token功能演示脚本
展示如何使用测试token进行API调用
"""

import asyncio
import aiohttp
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(project_root))

from aistack.config.config import Config, set_global_config


async def test_api_with_test_token():
    """测试使用测试token调用API"""
    
    # 初始化配置
    config = Config()
    set_global_config(config)
    
    print("=== 测试Token功能演示 ===")
    print(f"测试Token: {config.test_token}")
    print(f"测试用户ID: {config.test_user_id}")
    print()
    
    # 模拟API调用
    headers = {
        "Authorization": f"Bearer {config.test_token}",
        "Content-Type": "application/json"
    }
    
    print("使用测试token的API调用示例:")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print()
    
    # 这里可以添加实际的API调用测试
    # 例如调用 /users/me 端点
    print("可以调用的API端点示例:")
    print("GET /users/me - 获取当前用户信息")
    print("GET /users/test-token - 获取测试token信息")
    print("GET /v1/gpu - 获取GPU信息")
    print("GET /v1/k8s-apps - 获取K8s应用列表")
    print("等等...")
    
    print("\n=== 前端使用方法 ===")
    print("在前端代码中，可以这样使用测试token:")
    print(f"const token = '{config.test_token}';")
    print("const headers = {")
    print("    'Authorization': `Bearer ${token}`,")
    print("    'Content-Type': 'application/json'")
    print("};")
    print()
    print("然后就可以调用任何需要认证的API了！")


if __name__ == "__main__":
    asyncio.run(test_api_with_test_token())

