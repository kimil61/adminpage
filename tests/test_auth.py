import pytest
from app.models import Post, KnowledgeItem, FilteredContent


def login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        allow_redirects=False,
    )


def test_login_success(client):
    client_app, SessionLocal = client
    response = login(client_app)
    assert response.status_code == 302
    assert "session=" in response.headers.get("set-cookie", "")


def test_create_post(client):
    client_app, SessionLocal = client
    login(client_app)
    response = client_app.post(
        "/admin/posts/create",
        data={"title": "Test Post", "content": "Hello"},
        allow_redirects=False,
    )
    assert response.status_code == 302
    with SessionLocal() as db:
        post = db.query(Post).filter_by(title="Test Post").first()
        assert post is not None


def test_knowledge_crud(client):
    client_app, SessionLocal = client
    login(client_app)
    # create
    resp = client_app.post(
        "/admin/knowledge/create",
        data={"title": "Item", "content": "Body"},
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        item = db.query(KnowledgeItem).filter_by(title="Item").first()
        assert item is not None
        item_id = item.id

    # update
    resp = client_app.post(
        f"/admin/knowledge/{item_id}/edit",
        data={"title": "Item Updated", "content": "New"},
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        item = db.query(KnowledgeItem).filter_by(id=item_id).first()
        assert item.title == "Item Updated"

    # delete
    resp = client_app.post(
        f"/admin/knowledge/{item_id}/delete",
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        assert db.query(KnowledgeItem).filter_by(id=item_id).first() is None


def test_filtered_content_crud(client):
    client_app, SessionLocal = client
    login(client_app)

    # create
    resp = client_app.post(
        "/admin/filtered/create",
        data={
            "filter_result": "result",
            "reasoning": "analysis",
            "confidence_score": 5,
            "suitable_for_blog": True,
        },
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        fc = db.query(FilteredContent).first()
        assert fc is not None
        fc_id = fc.id

    # update
    resp = client_app.post(
        f"/admin/filtered/{fc_id}/edit",
        data={
            "filter_result": "updated",
            "reasoning": "analysis2",
            "confidence_score": 7,
            "suitable_for_blog": False,
        },
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        fc = db.query(FilteredContent).filter_by(id=fc_id).first()
        assert fc.filter_result == "updated"
        assert fc.suitable_for_blog is False

    # delete
    resp = client_app.post(
        f"/admin/filtered/{fc_id}/delete",
        allow_redirects=False,
    )
    assert resp.status_code == 302
    with SessionLocal() as db:
        assert db.query(FilteredContent).filter_by(id=fc_id).first() is None
