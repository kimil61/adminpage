import pytest
from app.utils import sanitize_html
from app.routers.saju import safe_markdown


def test_sanitize_script_tag():
    html = '<p>Hello</p><script>alert("x")</script>'
    cleaned = sanitize_html(html)
    assert '<script' not in cleaned
    assert 'alert("x")' in cleaned


def test_safe_markdown_removes_script():
    text = 'Hello<script>alert(1)</script>'
    md = safe_markdown(text)
    assert '<script' not in md
