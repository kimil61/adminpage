import os
import types
import pytest
from fastapi.testclient import TestClient

# Set dummy API key so importing app doesn't fail
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from app.main import app
from app.dependencies import get_current_user
from app.database import get_db
from app.exceptions import UnauthorizedError


class DummySession:
    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def close(self):
        pass

def override_get_db():
    db = DummySession()
    try:
        yield db
    finally:
        db.close()


def override_unauthenticated():
    raise UnauthorizedError("로그인이 필요합니다.")


def override_user():
    return types.SimpleNamespace(id=1)


app.dependency_overrides[get_db] = override_get_db


def test_order_create_unauthenticated():
    app.dependency_overrides[get_current_user] = override_unauthenticated
    client = TestClient(app)
    res = client.post("/order/create", json={"saju_key": "test"})
    assert res.status_code == 401
    assert res.json()["detail"] == "로그인이 필요합니다."
    app.dependency_overrides.pop(get_current_user)


def test_order_status_not_found():
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)
    res = client.get("/order/status/1")
    assert res.status_code == 404
    assert res.json()["detail"] == "주문을 찾을 수 없습니다."
    app.dependency_overrides.pop(get_current_user)
