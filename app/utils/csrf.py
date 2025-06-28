import secrets
from fastapi import Request, HTTPException, status


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
