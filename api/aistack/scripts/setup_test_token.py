#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置测试token的脚本
用于为前端调试提供固定的测试token
"""

import os
import sys
import secrets
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aistack.config.config import Config, set_global_config


def generate_test_token():
    """生成测试token"""
    return f"test_token_{secrets.token_hex(16)}"


def setup_test_token():
    """设置测试token"""
    print("正在设置测试token...")
    
    # 创建配置实例
    config = Config()
    
    # 生成测试token
    test_token = generate_test_token()
    config.test_token = test_token
    config.test_user_id = 1
    
    # 设置全局配置
    set_global_config(config)
    
    print(f"测试token已生成: {test_token}")
    print(f"测试用户ID: {config.test_user_id}")
    print("\n使用方法:")
    print("在API请求的Authorization header中使用:")
    print(f"Authorization: Bearer {test_token}")
    print("\n这个token将自动认证为测试用户，用户ID为1，具有管理员权限")
    
    # 将token保存到文件，方便前端使用
    token_file = project_root / "data" / "test_token.txt"
    os.makedirs(project_root / "data", exist_ok=True)
    
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(f"测试Token: {test_token}\n")
        f.write(f"用户ID: {config.test_user_id}\n")
        f.write(f"用户名: test_user\n")
        f.write(f"权限: 管理员\n")
        f.write(f"\n使用方法:\n")
        f.write(f"Authorization: Bearer {test_token}\n")
    
    print(f"\n测试token已保存到: {token_file}")
    
    return test_token


if __name__ == "__main__":
    setup_test_token()
