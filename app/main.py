from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from app.template import templates
from app.database import engine, get_db
from app.models import Base, Post, Category
from app.routers import auth, blog, admin, saju, order  # order 추가 ✓
from app.utils import get_flashed_messages
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR
import os


Base.metadata.create_all(bind=engine)

app = FastAPI(title="My Website", version="1.0.0")

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "your-super-secret-key-change-this-for-footjob")
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

templates.env.globals.update({
    "get_flashed_messages": get_flashed_messages,
})

# 라우터 등록
app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(admin.router)
app.include_router(saju.router)
app.include_router(order.router)  # 이 라인 추가 ✓

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    recent_posts = db.query(Post).filter(
        Post.is_published == True
    ).order_by(Post.created_at.desc()).limit(6).all()
    
    categories = db.query(Category).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_posts": recent_posts,
        "categories": categories
    })

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == HTTP_404_NOT_FOUND:
        return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse("errors/error.html", {"request": request, "code": exc.status_code}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    print(f"서버 오류: {exc}")  # 디버깅용 로그
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)