from fastapi import APIRouter, Request, Form, File, UploadFile, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import User, Post, Category, Media
from app.forms import PostForm, CategoryForm
from app.utils import require_admin, save_uploaded_file, create_slug, flash_message
import os
from datetime import datetime

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_posts = db.query(Post).filter(Post.is_deleted == False).count()
    published_posts = (
        db.query(Post)
        .filter(Post.is_published == True, Post.is_deleted == False)
        .count()
    )
    total_users = db.query(User).count()
    total_categories = db.query(Category).count()
    
    recent_posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(Post.is_deleted == False)
        .order_by(Post.created_at.desc())
        .limit(5)
        .all()
    )
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_posts": total_posts,
        "published_posts": published_posts,
        "total_users": total_users,
        "total_categories": total_categories,
        "recent_posts": recent_posts
    })

@router.get("/posts", response_class=HTMLResponse)
async def admin_posts(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    per_page = 10
    offset = (page - 1) * per_page
    
    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(Post.is_deleted == False)
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    total = db.query(Post).filter(Post.is_deleted == False).count()
    pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("admin/posts.html", {
        "request": request,
        "posts": posts,
        "page": page,
        "pages": pages
    })

@router.get("/posts/create", response_class=HTMLResponse)
async def admin_create_post(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    form = PostForm()
    categories = db.query(Category).all()
    form.category_id.choices = [(0, '카테고리 선택')] + [(c.id, c.name) for c in categories]
    
    return templates.TemplateResponse("admin/post_form.html", {
        "request": request,
        "form": form,
        "action": "create"
    })

@router.post("/posts/create")
async def admin_create_post_submit(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    excerpt: str = Form(""),
    category_id: int = Form(0),
    is_published: bool = Form(False),
    featured_image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    slug = create_slug(title)
    
    existing_post = db.query(Post).filter(Post.slug == slug).first()
    if existing_post:
        slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    featured_image_url = None
    if featured_image and featured_image.filename:
        featured_image_url = await save_uploaded_file(featured_image, "posts")
    
    new_post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt,
        author_id=current_user.id,
        category_id=category_id if category_id > 0 else None,
        is_published=is_published,
        featured_image=featured_image_url,
        published_at=datetime.utcnow() if is_published else None
    )
    
    db.add(new_post)
    db.commit()
    
    flash_message(request, "포스트가 생성되었습니다.", "success")
    return RedirectResponse(url="/admin/posts", status_code=302)

@router.get("/categories", response_class=HTMLResponse)
async def admin_categories(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    categories = db.query(Category).all()
    form = CategoryForm()
    
    return templates.TemplateResponse("admin/categories.html", {
        "request": request,
        "categories": categories,
        "form": form
    })

@router.post("/categories")
async def admin_create_category(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing_category = db.query(Category).filter(
        (Category.name == name) | (Category.slug == slug)
    ).first()
    
    if existing_category:
        flash_message(request, "이미 존재하는 카테고리명 또는 슬러그입니다.", "error")
    else:
        new_category = Category(name=name, slug=slug, description=description)
        db.add(new_category)
        db.commit()
        flash_message(request, "카테고리가 생성되었습니다.", "success")
    
    return RedirectResponse(url="/admin/categories", status_code=302)
