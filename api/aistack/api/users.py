# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from aistack.schemas.users import User, UserCreate, UserUpdate, UserPublic, UsersPublic
from aistack.server.deps import ListParamsDep, SessionDep, CurrentUserDep
from aistack.security import verify_hashed_secret, get_secret_hash, JWTManager
from aistack.config.config import get_global_config
from aistack.utils.parse_client import parse_client

# 安全认证
security = HTTPBearer()

router = APIRouter()

# JWT管理器
def get_jwt_manager():
    config = get_global_config()
    if config is None:
        raise RuntimeError("Configuration not initialized. Please ensure the application is properly started.")
    from aistack.security import get_global_jwt_manager
    return get_global_jwt_manager(config.jwt_secret_key)

@router.post("/login", summary="用户登录")
async def login(
    username: str,
    password: str,
    session: SessionDep
):
    """用户登录"""
    try:
        # 调用 Parse Server 登录
        parse_response = await parse_client.login(username, password)
        
        if 'error' in parse_response:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 获取 Parse Server 返回的用户信息
        parse_user = parse_response.get('user', {})
        session_token = parse_response.get('sessionToken')
        
        # 查找或创建本地用户记录
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        
        if not user:
            # 创建本地用户记录
            user = User(
                username=username,
                hashed_password="",  # Parse Server 管理密码
                is_admin=False,
                full_name=parse_user.get('nickname', username)
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        # 生成包含 session_token 的 JWT token
        jwt_manager = get_jwt_manager()
        token_payload = {
            "sub": username,
            "session_token": session_token,
            "user_id": parse_user.get('objectId')
        }
        token = jwt_manager.create_jwt_token_with_payload(token_payload)
        
        return {
            "token": token,
            "user": UserPublic.model_validate(user)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {e}")


@router.post("/register", response_model=UserPublic, summary="用户注册")
async def register(
    user_data: UserCreate,
    session: SessionDep
):
    """用户注册"""
    try:
        # 检查本地用户名是否已存在
        result = await session.execute(select(User).where(User.username == user_data.username))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")
        
        # 调用 Parse Server 注册
        parse_response = await parse_client.register(
            username=user_data.username,
            password=user_data.password,
            email=getattr(user_data, 'email', None)
        )
        
        if 'error' in parse_response:
            raise HTTPException(status_code=400, detail=parse_response.get('error', '注册失败'))
        
        # 创建本地用户记录
        user = User(
            username=user_data.username,
            hashed_password="",  # Parse Server 管理密码
            is_admin=user_data.is_admin,
            full_name=user_data.full_name or user_data.username,
            require_password_change=user_data.require_password_change
        )
        
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        return UserPublic.model_validate(user)
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"注册失败: {e}")


@router.post("/logout", summary="用户注销")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: CurrentUserDep = None
):
    """用户注销"""
    try:
        # 获取 JWT token
        token = credentials.credentials
        jwt_manager = get_jwt_manager()
        
        # 解码 JWT token 获取 session_token
        payload = jwt_manager.decode_jwt_token(token)
        session_token = payload.get("session_token")
        
        # 将 token 加入黑名单
        jwt_manager.blacklist_token(token)
        
        # 如果 Parse Server session token 存在，调用 Parse Server 注销
        if session_token:
            try:
                await parse_client.logout(session_token)
            except Exception as e:
                # Parse Server 注销失败不影响本地注销
                print(f"Parse Server logout failed: {e}")
        
        return {
            "message": "注销成功",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注销失败: {e}")


@router.get("/me", response_model=UserPublic, summary="获取当前用户信息")
async def get_current_user_info(current_user: CurrentUserDep):
    """获取当前用户信息"""
    return UserPublic.model_validate(current_user)


@router.get("", response_model=UsersPublic)
async def get_users(session: SessionDep, params: ListParamsDep, search: str = None):
    fuzzy_fields = {}
    if search:
        fuzzy_fields = {"username": search, "full_name": search}

    return await User.paginated_by_query(
        session=session,
        fuzzy_fields=fuzzy_fields,
        page=params.page,
        per_page=params.perPage,
    )