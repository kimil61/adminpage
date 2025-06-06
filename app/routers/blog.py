from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.database import get_db, get_paginated_posts
from app.models import Post, Category

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/blog", response_class=HTMLResponse)
async def blog_list(
    request: Request, 
    page: int = 1,
    db: Session = Depends(get_db)
):
    per_page = 6

    result = get_paginated_posts(db, page, per_page)
    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "blog/list.html",
        {
            "request": request,
            "posts": result["posts"],
            "categories": categories,
            "page": page,
            "pages": result["pages"],
            "total": result["total"],
        },
    )

@router.get("/blog/{post_id}", response_class=HTMLResponse)
async def blog_detail(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db)
):
    post = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(
            Post.id == post_id,
            Post.is_published == True,
            Post.is_deleted == False,
        )
        .first()
    )
    
    if not post:
        raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")
    
    post.views += 1
    db.commit()
    
    related_posts = (
        db.query(Post)
        .filter(
            Post.category_id == post.category_id,
            Post.id != post.id,
            Post.is_published == True,
            Post.is_deleted == False,
        )
        .limit(3)
        .all()
    )
    
    return templates.TemplateResponse("blog/detail.html", {
        "request": request,
        "post": post,
        "related_posts": related_posts
    })

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

    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(
            Post.category_id == category.id,
            Post.is_published == True,
            Post.is_deleted == False,
        )
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    return templates.TemplateResponse("blog/category.html", {
        "request": request,
        "posts": posts,
        "category": category,
        "page": page
    })
