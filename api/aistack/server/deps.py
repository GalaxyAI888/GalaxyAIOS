# -*- coding: utf-8 -*-
from typing import Annotated, Optional
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from aistack.schemas.users import User
from aistack.server.auth import get_admin_user, get_current_user, get_optional_user
from aistack.server.db import get_session
from aistack.schemas.common import ListParams

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ListParamsDep = Annotated[ListParams, Depends(ListParams)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentAdminUserDep = Annotated[User, Depends(get_admin_user)]
OptionalUserDep = Annotated[Optional[User], Depends(get_optional_user)]

# 默认测试用户依赖 - 用于K8s应用服务，暂时绕过用户验证
async def get_default_test_user(session: SessionDep) -> User:
    """获取默认测试用户，用于K8s应用服务"""
    from sqlalchemy import select
    
    # 尝试获取ID为1的用户（通常是admin用户）
    result = await session.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    
    if user is None:
        # 如果用户不存在，创建一个默认测试用户
        user = User(
            id=1,
            username="test_user",
            hashed_password="",  # 测试用户不需要密码
            is_admin=True,  # 测试用户设为管理员
            full_name="默认测试用户"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user

DefaultTestUserDep = Annotated[User, Depends(get_default_test_user)]

