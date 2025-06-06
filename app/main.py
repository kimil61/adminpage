# app/main.py
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models import Base, Post, Category
from app.routers import auth, blog, admin
from app.utils import get_flashed_messages
from app.settings import settings
from app.exception_handlers import global_exception_handler

# 테이블 생성
Base.metadata.create_all(bind=engine)

# FastAPI 앱 생성
app = FastAPI(title="My Website", version="1.0.0")

# 세션 미들웨어 (실제 운영에서는 강력한 비밀키 사용)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key
)

# 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# ✅ 템플릿 전역 함수 등록 (수정됨)
def create_url_for(name: str, **kwargs) -> str:
    """URL 생성 함수"""
    if name == "home":
        return "/"
    elif name == "blog_list":
        return "/blog"
    elif name == "blog_detail":
        return f"/blog/{kwargs.get('post_id', '')}"
    elif name == "blog_category":
        return f"/category/{kwargs.get('category_slug', '')}"
    elif name == "login":
        return "/login"
    elif name == "register":
        return "/register"
    elif name == "logout":
        return "/logout"
    elif name == "admin_dashboard":
        return "/admin/"
    else:
        return f"/{name}"

# Jinja2 전역 함수 등록
templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["url_for"] = create_url_for

# 라우터 등록
app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(admin.router)

# 홈페이지
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    # 최신 포스트 (발행된 것만)
    recent_posts = db.query(Post).filter(
        Post.is_published == True
    ).order_by(Post.created_at.desc()).limit(6).all()
    
    # 카테고리 목록
    categories = db.query(Category).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_posts": recent_posts,
        "categories": categories
    })

# 에러 핸들러
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("errors/404.html", {
        "request": request
    }, status_code=404)

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse("errors/500.html", {
        "request": request
    }, status_code=500)

app.add_exception_handler(Exception, global_exception_handler)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)