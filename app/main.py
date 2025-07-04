from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from app.template import templates
from app.database import engine, get_db
from app.models import Base, Post, Category
from app.routers import auth, blog, admin, saju, order, shop, fortune, mypage, cart, product, subscription, review, referral  # shop, fortune, mypage, cart, product, subscription, review, referral 추가
from app.utils import get_flashed_messages
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR
from app.utils.error_handlers import register_exception_handlers
import os


Base.metadata.create_all(bind=engine)

app = FastAPI(title="infoWow", version="1.0.0")

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
app.include_router(order.router)
app.include_router(shop.router)  # 상점 라우터 추가
app.include_router(fortune.router)  # 포인트 라우터 추가
app.include_router(mypage.router)  # 마이페이지 라우터 추가
app.include_router(cart.router)  # 장바구니 라우터 추가
app.include_router(product.router)  # SEO 상품 라우터 추가
app.include_router(subscription.router)  # 구독 라우터 추가
app.include_router(review.router)  # 리뷰 라우터 추가
app.include_router(referral.router)  # 추천인 라우터 추가

register_exception_handlers(app)

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
