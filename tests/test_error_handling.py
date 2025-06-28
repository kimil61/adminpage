from app.main import app


def test_blog_detail_404_html(client):
    res = client.get('/blog/nonexistent-post', headers={'accept': 'text/html'})
    assert res.status_code == 404
    assert '페이지를 찾을 수 없습니다' in res.text

def test_generic_exception_html(client):
    async def trigger_error():
        raise Exception('boom')
    app.add_api_route('/trigger-error', trigger_error)
    try:
        res = client.get('/trigger-error', headers={'accept': 'text/html'})
        assert res.status_code == 500
        assert '서버 오류가 발생했습니다' in res.text
    finally:
        app.router.routes.pop()

def test_generic_exception_json(client):
    async def trigger_error():
        raise Exception('boom')
    app.add_api_route('/trigger-error', trigger_error)
    try:
        res = client.get('/trigger-error', headers={'accept': 'application/json'})
        assert res.status_code == 500
        assert res.json()['detail'] == '서버 오류가 발생했습니다.'
    finally:
        app.router.routes.pop()

