from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def decode_token(token: str, settings: Settings) -> dict:
    if settings.supabase_jwks_url:
        key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token).key
        algorithms = ["ES256", "RS256"]
    else:
        key = settings.supabase_jwt_secret
        algorithms = ["HS256"]
    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience="authenticated",
        options={"require": ["exp", "sub"]},
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if creds is None:
        raise _unauthorized("Falta el token de autenticación")
    try:
        claims = decode_token(creds.credentials, settings)
    except jwt.PyJWTError:
        raise _unauthorized("Token inválido o expirado")
    return CurrentUser(id=claims["sub"], email=claims.get("email"))
