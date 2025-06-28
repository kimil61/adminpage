# app/routers/blog.py 수정본 - 라우터 순서 중요!

from fastapi import APIRouter, Request, Depends
from app.exceptions import NotFoundError
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from urllib.parse import unquote
from app.database import get_db
from app.models import Post, Category
from app.template import templates

router = APIRouter()

@router.get("/blog", response_class=HTMLResponse)
async def blog_list(
    request: Request, 
    page: int = 1,
    db: Session = Depends(get_db)
):
    per_page = 6
    offset = (page - 1) * per_page
    
    posts = db.query(Post).filter(
        Post.is_published == True
    ).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    total = db.query(Post).filter(Post.is_published == True).count()
    pages = (total + per_page - 1) // per_page
    
    categories = db.query(Category).all()
    
    return templates.TemplateResponse("blog/list.html", {
        "request": request,
        "posts": posts,
        "categories": categories,
        "page": page,
        "pages": pages,
        "total": total
    })

# 🔥 중요! category 라우터를 먼저 정의
@router.get("/blog/category/{category_slug:path}", response_class=HTMLResponse)
async def blog_category(
    request: Request,
    category_slug: str,
    page: int = 1,
    db: Session = Depends(get_db)
):
    # 한국어 디코딩 지원
    decoded_slug = unquote(category_slug)
    
    print(f"🔍 카테고리 검색: {category_slug} / {decoded_slug}")  # 디버깅용
    
    category = db.query(Category).filter(
        (Category.slug == category_slug) | (Category.slug == decoded_slug)
    ).first()
    
    if not category:
        # 디버깅: 존재하는 카테고리들 출력
        existing_categories = db.query(Category).all()
        print(f"📋 존재하는 카테고리들: {[c.slug for c in existing_categories]}")
        raise NotFoundError("카테고리를 찾을 수 없습니다.")
    
    per_page = 6
    offset = (page - 1) * per_page
    
    posts = db.query(Post).filter(
        Post.category_id == category.id,
        Post.is_published == True
    ).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    total = db.query(Post).filter(
        Post.category_id == category.id,
        Post.is_published == True
    ).count()
    pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("blog/category.html", {
        "request": request,
        "posts": posts,
        "category": category,
        "page": page,
        "pages": pages,
        "total": total
    })

# 🔥 blog 개별 포스트는 맨 마지막에! (가장 구체적인 패턴이 뒤에)
@router.get("/blog/{slug:path}", response_class=HTMLResponse)
async def blog_detail(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    # 한국어 디코딩 지원
    decoded_slug = unquote(slug)
    
    # slug 또는 ID로 검색 (기존 호환성 유지)
    post = None
    
    # 먼저 slug로 검색
    post = db.query(Post).filter(
        (Post.slug == slug) | (Post.slug == decoded_slug),
        Post.is_published == True
    ).first()
    
    # slug로 없으면 숫자 ID로 검색 (기존 호환성)
    if not post and slug.isdigit():
        post = db.query(Post).filter(
            Post.id == int(slug),
            Post.is_published == True
        ).first()
    
    if not post:
        raise NotFoundError("포스트를 찾을 수 없습니다.")
    
    # 조회수 증가
    if post.views is None:
        post.views = 0
    post.views += 1
    db.commit()
    
    # 관련 포스트
    related_posts = db.query(Post).filter(
        Post.category_id == post.category_id,
        Post.id != post.id,
        Post.is_published == True
    ).limit(3).all()
    
    return templates.TemplateResponse("blog/detail.html", {
        "request": request,
        "post": post,
        "related_posts": related_posts
    })