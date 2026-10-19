from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_health_is_public():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_auth_configured(client):
    assert client.get("/health").json() == {"status": "ok", "auth_configured": True}
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, supabase_jwt_secret="", supabase_jwks_url="")
    assert client.get("/health").json() == {"status": "ok", "auth_configured": False}
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, supabase_jwt_secret="", supabase_jwks_url="https://x/jwks")
    body = client.get("/health").json()
    assert body["auth_configured"] is True and "jwks" not in str(body)
