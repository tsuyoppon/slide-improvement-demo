"""
Cognito JWT トークン検証モジュール
"""
import os
import json
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import urllib.request

# 環境変数から設定を取得
COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_APP_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID")

# JWT検証用の公開鍵をキャッシュ
_jwks_cache: Optional[dict] = None

security = HTTPBearer()


def get_cognito_jwks() -> dict:
    """
    Cognito の公開鍵 (JWKS) を取得
    初回のみダウンロードして、以降はキャッシュを使用
    """
    global _jwks_cache
    
    if _jwks_cache is not None:
        return _jwks_cache
    
    jwks_url = (
        f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
        f"{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    
    try:
        with urllib.request.urlopen(jwks_url) as response:
            _jwks_cache = json.loads(response.read())
            return _jwks_cache
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch JWKS: {str(e)}"
        )


def verify_cognito_token(token: str) -> dict:
    """
    Cognito ID トークンを検証してペイロードを返す
    
    Args:
        token: JWT トークン文字列
        
    Returns:
        デコードされたトークンペイロード
        
    Raises:
        HTTPException: トークンが無効な場合
    """
    if not COGNITO_USER_POOL_ID or not COGNITO_APP_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Cognito configuration is missing"
        )
    
    try:
        # JWTヘッダーをデコード（検証なし）して kid を取得
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=401,
                detail="Token header missing 'kid'"
            )
        
        # JWKS から該当する公開鍵を取得
        jwks = get_cognito_jwks()
        key = None
        for jwk_key in jwks.get("keys", []):
            if jwk_key.get("kid") == kid:
                key = jwk_key
                break
        
        if not key:
            raise HTTPException(
                status_code=401,
                detail="Public key not found in JWKS"
            )
        
        # トークンを検証してデコード
        # options で at_hash の検証をスキップ（ID tokenのみ使用時）
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID,
            issuer=f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
            options={"verify_at_hash": False}
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Token verification failed: {str(e)}"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    FastAPI Dependency: 認証されたユーザー情報を取得
    
    Usage:
        @app.get("/api/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}
    
    Returns:
        ユーザー情報を含む辞書
        - sub: ユーザーID (Cognito User Pool における一意のID)
        - email: メールアドレス
        - cognito:username: ユーザー名
        など
    """
    token = credentials.credentials
    user_payload = verify_cognito_token(token)
    return user_payload
