import os
import types
import pytest
from fastapi.testclient import TestClient

# Ensure environment variables so importing app works
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from app.main import app
from app.database import get_db

class DummySession:
    def query(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def commit(self):
        pass

    def close(self):
        pass

def override_get_db():
    db = DummySession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
