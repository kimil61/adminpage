from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR
from app.template import templates


def prefers_json(request: Request) -> bool:
    """Return True if the client expects a JSON response."""
    accept = request.headers.get("accept", "").lower()

    # 1) If the request path looks like an API endpoint (e.g. /order/**),
    #    return JSON regardless of the Accept header.
    if request.url.path.startswith("/order"):
        return True

    # 2) Otherwise determine preference based on the Accept header.
    if "application/json" not in accept:
        return False
    if "text/html" not in accept:
        return True
    return accept.index("application/json") < accept.index("text/html")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if prefers_json(request):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.status_code == HTTP_404_NOT_FOUND:
            return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
        return templates.TemplateResponse(
            "errors/error.html",
            {"request": request, "code": exc.status_code},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        print(f"서버 오류: {exc}")
        if prefers_json(request):
            return JSONResponse(
                {"detail": "서버 오류가 발생했습니다."},
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return templates.TemplateResponse(
            "errors/500.html",
            {"request": request},
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        )


"""
에러 핸들러 유틸리티
"""

class PaymentError(Exception):
    """결제 관련 에러"""
    pass

class InsufficientPointsError(Exception):
    """포인트 부족 에러"""
    pass

class ValidationError(Exception):
    """검증 에러"""
    pass

def get_flashed_messages(request):
    """세션에서 flash 메시지 목록을 꺼내온다 ([(category, message), ...])"""
    return request.session.pop("_flashes", [])
