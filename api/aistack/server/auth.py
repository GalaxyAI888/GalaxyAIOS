# -*- coding: utf-8 -*-
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select

from aistack.server.db import get_session
from aistack.schemas.users import User
from aistack.security import JWTManager
from aistack.config.config import get_global_config
from aistack.utils.parse_client import parse_client

# 安全认证
security = HTTPBearer()
# 可选安全认证（不自动抛 401）
optional_security = HTTPBearer(auto_error=False)

# JWT管理器
def get_jwt_manager():
    config = get_global_config()
    if config is None:
        raise RuntimeError("Configuration not initialized. Please ensure the application is properly started.")
    from aistack.security import get_global_jwt_manager
    return get_global_jwt_manager(config.jwt_secret_key)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """获取当前用户"""
    try:
        # 检查是否为测试token
        config = get_global_config()
        if config and config.test_token and credentials.credentials == config.test_token:
            # 使用测试token，返回写死的测试用户
            result = await session.execute(select(User).where(User.id == config.test_user_id))
            user = result.scalar_one_or_none()
            
            if user is None:
                # 如果测试用户不存在，创建一个
                user = User(
                    id=config.test_user_id,
                    username="test_user",
                    hashed_password="",  # 测试用户不需要密码
                    is_admin=True,  # 测试用户设为管理员
                    full_name="测试用户"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            return user
        
        # 解码JWT token
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.decode_jwt_token(credentials.credentials)
        username = payload.get("sub")
        session_token = payload.get("session_token")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 从数据库获取用户
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        
        if user is None:
            # 如果本地数据库中没有用户，尝试从 Parse Server 获取用户信息
            try:
                parse_user = await parse_client.query_user(username)
                if parse_user.get('results') and len(parse_user['results']) > 0:
                    # 创建本地用户记录
                    user_data = parse_user['results'][0]
                    user = User(
                        username=username,
                        hashed_password="",  # Parse Server 管理密码
                        is_admin=False,
                        full_name=user_data.get('nickname', username)
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="用户不存在",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户不存在",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """获取管理员用户"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """获取可选用户（不强制要求认证）"""
    if credentials is None:
        return None
    
    try:
        # 检查是否为测试token
        config = get_global_config()
        if config and config.test_token and credentials.credentials == config.test_token:
            # 使用测试token，返回写死的测试用户
            result = await session.execute(select(User).where(User.id == config.test_user_id))
            user = result.scalar_one_or_none()
            
            if user is None:
                # 如果测试用户不存在，创建一个
                user = User(
                    id=config.test_user_id,
                    username="test_user",
                    hashed_password="",  # 测试用户不需要密码
                    is_admin=True,  # 测试用户设为管理员
                    full_name="测试用户"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            return user
        
        return await get_current_user(credentials, session)
    except HTTPException:
        return None
