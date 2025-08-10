# -*- coding: utf-8 -*-
import aiohttp
import json
from typing import Optional, Dict, Any
from aistack.config.config import get_global_config

class ParseClient:
    """Parse Server 客户端"""
    
    def __init__(self):
        self._config = None
        self._initialized = False
    
    def _ensure_initialized(self):
        if not self._initialized:
            config = get_global_config()
            if config is None:
                raise RuntimeError("Configuration not initialized. Please ensure the application is properly started.")
            self._config = config
            self.base_url = config.api_base_url
            self.app_id = config.parse_app_id
            self.api_key = config.parse_api_key
            self.headers = {
                'X-Parse-Application-Id': self.app_id,
                'X-Parse-REST-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }
            self._initialized = True
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                           session_token: Optional[str] = None) -> Dict[str, Any]:
        """发送请求到 Parse Server"""
        self._ensure_initialized()
        url = f"{self.base_url}/parseapi{endpoint}"
        headers = self.headers.copy()
        
        if session_token:
            headers['X-Parse-Session-Token'] = session_token
        
        async with aiohttp.ClientSession() as session:
            if method.upper() == 'GET':
                async with session.get(url, headers=headers) as response:
                    return await response.json()
            elif method.upper() == 'POST':
                async with session.post(url, headers=headers, json=data) as response:
                    return await response.json()
            elif method.upper() == 'PUT':
                async with session.put(url, headers=headers, json=data) as response:
                    return await response.json()
            elif method.upper() == 'DELETE':
                async with session.delete(url, headers=headers) as response:
                    return await response.json()
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        data = {
            "username": username,
            "password": password
        }
        return await self._make_request('POST', '/parse/login', data)
    
    async def register(self, username: str, password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """用户注册"""
        data = {
            "username": username,
            "password": password
        }
        if email:
            data["email"] = email
        return await self._make_request('POST', '/parse/users', data)
    
    async def get_user_info(self, user_id: str, session_token: str) -> Dict[str, Any]:
        """获取用户信息"""
        return await self._make_request('GET', f'/parse/users/{user_id}', session_token=session_token)
    
    async def update_user(self, user_id: str, session_token: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户信息"""
        return await self._make_request('PUT', f'/parse/users/{user_id}', data, session_token)
    
    async def change_password(self, user_id: str, session_token: str, new_password: str) -> Dict[str, Any]:
        """修改密码"""
        data = {"password": new_password}
        return await self._make_request('PUT', f'/parse/users/{user_id}', data, session_token)
    
    async def update_user_permissions(self, user_id: str, session_token: str) -> Dict[str, Any]:
        """更新用户权限（设置公开读取权限）"""
        data = {
            "ACL": {
                "*": {
                    "read": True
                }
            }
        }
        return await self._make_request('PUT', f'/parse/users/{user_id}', data, session_token)
    
    async def logout(self, session_token: str) -> Dict[str, Any]:
        """用户登出"""
        return await self._make_request('POST', '/parse/logout', session_token=session_token)
    
    async def query_user(self, username: str) -> Dict[str, Any]:
        """根据用户名查询用户"""
        self._ensure_initialized()
        params = {
            'where': json.dumps({"username": username})
        }
        url = f"{self.base_url}/parseapi/parse/users"
        headers = self.headers.copy()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                return await response.json()


# 全局 Parse 客户端实例
parse_client = ParseClient()
