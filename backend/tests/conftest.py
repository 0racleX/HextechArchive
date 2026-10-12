import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

SECRET = "test-secret-test-secret-test-secret-0123456789"


def make_token(sub="user-a", secret=SECRET, exp_in=3600, aud="authenticated"):
    payload = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_in, "email": f"{sub}@x.com"}
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def _settings_override():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, supabase_jwt_secret=SECRET)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token()}"}
