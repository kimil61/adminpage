from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
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

@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_detail(
    request: Request,
    slug: str,  # post_id에서 slug로 변경
    db: Session = Depends(get_db)
):
    # slug로 포스트 찾기
    post = db.query(Post).filter(
        Post.slug == slug,  # ID 대신 slug로 검색
        Post.is_published == True
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")
    
    # 조회수 증가
    if post.views is None:
        post.views = 0
    post.views += 1
    db.commit()
    
    # 같은 카테고리의 관련 포스트
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

# @router.get("/blog/{post_id}", response_class=HTMLResponse)
# async def blog_detail(
#     request: Request,
#     post_id: int,
#     db: Session = Depends(get_db)
# ):
#     post = db.query(Post).filter(
#         Post.id == post_id,
#         Post.is_published == True
#     ).first()
    
#     if not post:
#         raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")
    
#     # 🔒 None 방어 처리
#     if post.views is None:
#         post.views = 0
#     post.views += 1
#     db.commit()
    
#     related_posts = db.query(Post).filter(
#         Post.category_id == post.category_id,
#         Post.id != post.id,
#         Post.is_published == True
#     ).limit(3).all()
    
#     return templates.TemplateResponse("blog/detail.html", {
#         "request": request,
#         "post": post,
#         "related_posts": related_posts
#     })

@router.get("/category/{category_slug}", response_class=HTMLResponse)
async def blog_category(
    request: Request,
    category_slug: str,
    page: int = 1,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.slug == category_slug).first()
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    
    per_page = 6
    offset = (page - 1) * per_page
    
    posts = db.query(Post).filter(
        Post.category_id == category.id,
        Post.is_published == True
    ).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    return templates.TemplateResponse("blog/category.html", {
        "request": request,
        "posts": posts,
        "category": category,
        "page": page
    })