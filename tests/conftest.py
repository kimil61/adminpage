import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models import User
from app.utils import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # create admin user
    with TestingSessionLocal() as db:
        admin = User(
            username="admin",
            email="admin@example.com",
            password=hash_password("admin123"),
            is_admin=True,
        )
        db.add(admin)
        db.commit()

    with TestClient(app) as c:
        yield c, TestingSessionLocal

    app.dependency_overrides.clear()
