import logging
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomHTTPException(HTTPException):
    def __init__(self, status_code: int, detail: str, log_message: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        if log_message:
            logger.error(f"HTTP {status_code}: {log_message}")

def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)
