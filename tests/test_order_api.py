import types
import pytest

from app.main import app
from app.dependencies import get_current_user
from app.exceptions import UnauthorizedError


def override_unauthenticated():
    raise UnauthorizedError("로그인이 필요합니다.")


def override_user():
    return types.SimpleNamespace(id=1)


def test_order_create_unauthenticated(client):
    app.dependency_overrides[get_current_user] = override_unauthenticated
    res = client.post("/order/create", json={"saju_key": "test"})
    assert res.status_code == 401
    assert res.json()["detail"] == "로그인이 필요합니다."
    app.dependency_overrides.pop(get_current_user)


def test_order_status_not_found(client):
    app.dependency_overrides[get_current_user] = override_user
    res = client.get("/order/status/1")
    assert res.status_code == 404
    assert res.json()["detail"] == "주문을 찾을 수 없습니다."
    app.dependency_overrides.pop(get_current_user)
