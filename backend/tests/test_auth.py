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
