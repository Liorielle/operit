import os
from fastapi import HTTPException

async def auth_check(authorization: str):
    """
    鉴权检查逻辑
    
    参数：
    - authorization: 来自 Authorization header 的值
    
    如果鉴权失败，抛出 HTTPException
    """
    gateway_key = os.getenv("GATEWAY_KEY")
    if authorization != f"Bearer {gateway_key}":
        raise HTTPException(status_code=401, detail="网关密钥错误")
