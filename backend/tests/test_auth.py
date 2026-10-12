from tests.conftest import make_token


def test_me_requires_token(client):
    assert client.get("/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_me_rejects_expired_token(client):
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token(exp_in=-10)}"})
    assert r.status_code == 401


def test_me_rejects_wrong_signature(client):
    token = make_token(secret="another-secret-another-secret-0123456789ab")
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_rejects_wrong_audience(client):
    r = client.get("/me", headers={"Authorization": f"Bearer {make_token(aud='other')}"})
    assert r.status_code == 401


def test_me_returns_identity(client, auth_headers):
    r = client.get("/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == {"id": "user-a", "email": "user-a@x.com"}


import base64
import hmac
import hashlib
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings, get_settings
from app.main import app
from app.security import auth


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _forged_hs256(secret: bytes, **extra) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims = {"sub": "evil", "aud": "authenticated", "exp": int(time.time()) + 3600, **extra}
    body = _b64(json.dumps(claims).encode())
    sig = hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(sig)}"


def test_me_fails_closed_without_any_key_configured(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, supabase_jwt_secret="", supabase_jwks_url=""
    )
    r = client.get("/me", headers={"Authorization": f"Bearer {_forged_hs256(b'')}"})
    assert r.status_code == 401


def test_me_rejects_alg_none(client):
    header = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60}).encode())
    r = client.get("/me", headers={"Authorization": f"Bearer {header}.{body}."})
    assert r.status_code == 401


def test_me_rejects_missing_sub(client):
    token = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60}, "test-secret-test-secret-test-secret-0123456789", algorithm="HS256"
    )
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# --- JWKS (asymmetric) path ---

@pytest.fixture
def jwks(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeClient:
        def get_signing_key_from_jwt(self, token):
            class K:
                key = private.public_key()

            return K()

    auth._jwks_client.cache_clear()
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeClient())
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, supabase_jwks_url="https://x.test/jwks")
    return private


def _rs256(private, exp_in=3600):
    claims = {"sub": "user-r", "aud": "authenticated", "exp": int(time.time()) + exp_in, "email": "r@x.com"}
    return jwt.encode(claims, private, algorithm="RS256")


def test_jwks_valid_rs256_token(client, jwks):
    r = client.get("/me", headers={"Authorization": f"Bearer {_rs256(jwks)}"})
    assert r.status_code == 200
    assert r.json() == {"id": "user-r", "email": "r@x.com"}


def test_jwks_rejects_hs256_token(client, jwks):
    r = client.get("/me", headers={"Authorization": f"Bearer {_forged_hs256(b'k' * 32)}"})
    assert r.status_code == 401


def test_jwks_rejects_expired_rs256(client, jwks):
    r = client.get("/me", headers={"Authorization": f"Bearer {_rs256(jwks, exp_in=-10)}"})
    assert r.status_code == 401
