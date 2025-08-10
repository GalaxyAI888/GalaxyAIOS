import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Set
import jwt
from argon2 import PasswordHasher

ph = PasswordHasher()

API_KEY_PREFIX = "gpustack"
JWT_TOKEN_EXPIRE_MINUTES = 120


def verify_hashed_secret(hashed: Union[str, bytes], plain: Union[str, bytes]) -> bool:
    try:
        return ph.verify(hashed, plain)
    except Exception:
        return False


def get_secret_hash(plain: Union[str, bytes]):
    return ph.hash(plain)


def generate_secure_password(length=12):
    if length < 8:
        raise ValueError("Password length should be at least 8 characters")

    special_characters = "!@#$%^&*_+"
    characters = string.ascii_letters + string.digits + special_characters
    while True:
        password = ''.join(secrets.choice(characters) for i in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in special_characters for c in password)
        ):
            return password


class JWTManager:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        expires_delta: Optional[timedelta] = None,
    ):
        if expires_delta is None:
            expires_delta = timedelta(minutes=JWT_TOKEN_EXPIRE_MINUTES)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expires_delta = expires_delta
        # Token 黑名单（在生产环境中应该使用 Redis 等持久化存储）
        self._blacklisted_tokens: Set[str] = set()

    def create_jwt_token(self, username: str):
        to_encode = {"sub": username}
        expire = datetime.now(timezone.utc) + self.expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_jwt_token_with_payload(self, payload: dict):
        """创建包含自定义载荷的JWT token"""
        to_encode = payload.copy()
        expire = datetime.now(timezone.utc) + self.expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_jwt_token(self, token: str):
        # 检查 token 是否在黑名单中
        if token in self._blacklisted_tokens:
            raise jwt.InvalidTokenError("Token has been revoked")
        
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
    
    def blacklist_token(self, token: str):
        """将 token 加入黑名单"""
        self._blacklisted_tokens.add(token)
    
    def is_token_blacklisted(self, token: str) -> bool:
        """检查 token 是否在黑名单中"""
        return token in self._blacklisted_tokens
    
    def clear_expired_tokens(self):
        """清理过期的 token（可选，用于内存管理）"""
        # 这里可以实现清理逻辑，比如定期清理过期的 token
        # 在生产环境中，建议使用 Redis 的 TTL 功能
        pass


# 全局 JWT 管理器实例（用于维护黑名单）
_global_jwt_manager: Optional[JWTManager] = None


def get_global_jwt_manager(secret_key: str) -> JWTManager:
    """获取全局 JWT 管理器实例"""
    global _global_jwt_manager
    if _global_jwt_manager is None:
        _global_jwt_manager = JWTManager(secret_key=secret_key)
    return _global_jwt_manager
