from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from app.template import templates
from app.database import engine, get_db
from app.models import Base, Post, Category
from app.routers import auth, blog, admin
from app.routers import auth, blog, admin, saju  # saju 추가
from app.utils import get_flashed_messages

import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="My Website", version="1.0.0")

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "your-super-secret-key-change-this")
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

templates.env.globals.update({
    "get_flashed_messages": get_flashed_messages,
})

app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(admin.router)
app.include_router(saju.router)  # 이 라인 추가

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
