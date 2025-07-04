"""
CSRF 토큰 유틸리티
"""

import secrets
from fastapi import Request, HTTPException, status
from typing import Optional


def generate_csrf_token(request: Request) -> str:
    """Generate or retrieve a CSRF token from session."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(16)
        request.session["csrf_token"] = token
    return token


def validate_csrf_token(request: Request, token: str) -> None:
    """Validate CSRF token from form against session."""
    session_token = request.session.get("csrf_token")
    if not session_token or token != session_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")


def verify_csrf_token(token: str, expected_token: str) -> bool:
    """CSRF 토큰 검증"""
    if not token or not expected_token:
        return False
    return secrets.compare_digest(token, expected_token)
