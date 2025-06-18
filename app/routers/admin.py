from fastapi import APIRouter, Request, Form, File, UploadFile, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    User,
    Post,
    Category,
    Media,
    InPost,
    FilteredContent,
)
from app.forms import (
    PostForm,
    CategoryForm,
    InPostForm,
    FilteredContentForm,
)
from app.utils import require_admin, save_uploaded_file, create_slug, flash_message
import os
from datetime import datetime
from app.template import templates

router = APIRouter(prefix="/admin")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_posts = db.query(Post).count()
    published_posts = db.query(Post).filter(Post.is_published == True).count()
    total_users = db.query(User).count()
    total_categories = db.query(Category).count()
    
    recent_posts = db.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    
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
    
    # 전체 포스트 수 조회
    total = db.query(Post).count()
    
    # 페이지별 포스트 조회
    posts = db.query(Post).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    # 총 페이지 수 계산
    pages = (total + per_page - 1) // per_page
    
    # 페이지네이션 정보 계산
    has_prev = page > 1
    has_next = page < pages
    prev_page = page - 1 if has_prev else None
    next_page = page + 1 if has_next else None
    
    return templates.TemplateResponse("admin/posts.html", {
        "request": request,
        "posts": posts,
        "page": page,
        "pages": pages,
        "total": total,
        "per_page": per_page,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": prev_page,
        "next_page": next_page
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
        try:
            featured_image_url = await save_uploaded_file(featured_image, "posts")
        except ValueError as e:
            flash_message(request, str(e), "error")
            formdata = await request.form()
            form = PostForm(formdata)
            categories = db.query(Category).all()
            form.category_id.choices = [(0, '카테고리 선택')] + [(c.id, c.name) for c in categories]
            return templates.TemplateResponse(
                "admin/post_form.html",
                {"request": request, "form": form, "action": "create"},
                status_code=400,
            )
    
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

@router.get("/posts/{post_id}/edit", response_class=HTMLResponse)
async def admin_edit_post(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")

    form = PostForm(obj=post)
    categories = db.query(Category).all()
    form.category_id.choices = [(0, '카테고리 선택')] + [(c.id, c.name) for c in categories]

    return templates.TemplateResponse("admin/post_form.html", {
        "request": request,
        "form": form,
        "post": post,
        "action": "edit"
    })


# POST route for editing a post
from fastapi import File  # Ensure File is imported (already in imports)
from fastapi import Form  # Ensure Form is imported (already in imports)

@router.post("/posts/{post_id}/edit")
async def admin_edit_post_submit(
    request: Request,
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    excerpt: str = Form(""),
    category_id: int = Form(0),
    is_published: bool = Form(False),
    featured_image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")

    slug = create_slug(title)
    if slug != post.slug:
        existing_post = db.query(Post).filter(Post.slug == slug).first()
        if existing_post:
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        post.slug = slug

    if featured_image and featured_image.filename:
        try:
            featured_image_url = await save_uploaded_file(featured_image, "posts")
            post.featured_image = featured_image_url
        except ValueError as e:
            flash_message(request, str(e), "error")
            formdata = await request.form()
            form = PostForm(formdata)
            categories = db.query(Category).all()
            form.category_id.choices = [(0, '카테고리 선택')] + [(c.id, c.name) for c in categories]
            return templates.TemplateResponse(
                "admin/post_form.html",
                {"request": request, "form": form, "post": post, "action": "edit"},
                status_code=400,
            )

    post.title = title
    post.content = content
    post.excerpt = excerpt
    post.category_id = category_id if category_id > 0 else None
    post.is_published = is_published
    post.updated_at = datetime.utcnow()
    if is_published and not post.published_at:
        post.published_at = datetime.utcnow()

    db.commit()
    flash_message(request, "포스트가 수정되었습니다.", "success")
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/posts/{post_id}/delete")
async def admin_delete_post(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        db.delete(post)
        db.commit()
        flash_message(request, "포스트가 삭제되었습니다.", "success")
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


@router.post("/categories/{category_id}/delete")
async def admin_delete_category(
    request: Request,
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if category:
        db.delete(category)
        db.commit()
        flash_message(request, "카테고리가 삭제되었습니다.", "success")
    return RedirectResponse(url="/admin/categories", status_code=302)



@router.get("/in_posts", response_class=HTMLResponse)
async def admin_in_posts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    items = db.query(InPost).order_by(InPost.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin/in_posts.html",
        {"request": request, "items": items},
    )


@router.get("/in_posts/create", response_class=HTMLResponse)
async def admin_create_in_post(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    form = InPostForm()
    return templates.TemplateResponse(
        "admin/in_posts_form.html",
        {"request": request, "form": form, "action": "create"},
    )


@router.post("/in_posts/create")
async def admin_create_in_post_submit(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    gen_content1: str = Form(None),
    gen_content2: str = Form(None),
    gen_content3: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Create InPost with additional generated content fields
    item = InPost(
        title=title,
        content=content,
        gen_content1=gen_content1,
        gen_content2=gen_content2,
        gen_content3=gen_content3,
    )
    db.add(item)
    db.commit()
    flash_message(request, "지식 항목이 생성되었습니다.", "success")
    return RedirectResponse("/admin/in_posts", status_code=302)


@router.get("/in_posts/{item_id}/edit", response_class=HTMLResponse)
async def admin_edit_in_post(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = db.query(InPost).filter(InPost.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    form = InPostForm(obj=item)
    return templates.TemplateResponse(
        "admin/in_posts_form.html",
        {"request": request, "form": form, "item": item, "action": "edit"},
    )


@router.post("/in_posts/{item_id}/edit")
async def admin_edit_in_post_submit(
    request: Request,
    item_id: int,
    title: str = Form(...),
    content: str = Form(...),
    gen_content1: str = Form(None),
    gen_content2: str = Form(None),
    gen_content3: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = db.query(InPost).filter(InPost.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    item.title = title
    item.content = content
    item.gen_content1 = gen_content1
    item.gen_content2 = gen_content2
    item.gen_content3 = gen_content3
    db.commit()
    flash_message(request, "지식 항목이 수정되었습니다.", "success")
    return RedirectResponse("/admin/in_posts", status_code=302)


@router.post("/in_posts/{item_id}/delete")
async def admin_delete_in_post(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = db.query(InPost).filter(InPost.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
        flash_message(request, "지식 항목이 삭제되었습니다.", "success")
    return RedirectResponse("/admin/in_posts", status_code=302)


@router.get("/filtered", response_class=HTMLResponse)
async def admin_filtered_contents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    contents = (
        db.query(FilteredContent)
        .order_by(FilteredContent.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin/filtered_contents.html",
        {"request": request, "contents": contents},
    )


@router.get("/filtered/create", response_class=HTMLResponse)
async def admin_create_filtered(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    form = FilteredContentForm()
    return templates.TemplateResponse(
        "admin/filtered_content_form.html",
        {"request": request, "form": form, "action": "create"},
    )


@router.post("/filtered/create")
async def admin_create_filtered_submit(
    request: Request,
    filter_result: str = Form(...),
    reasoning: str = Form(""),
    confidence_score: int = Form(None),
    suitable_for_blog: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = FilteredContent(
        filter_result=filter_result,
        reasoning=reasoning,
        confidence_score=confidence_score,
        suitable_for_blog=suitable_for_blog,
    )
    db.add(content)
    db.commit()
    flash_message(request, "필터링된 콘텐츠가 저장되었습니다.", "success")
    return RedirectResponse("/admin/filtered", status_code=302)


@router.get("/filtered/{content_id}/edit", response_class=HTMLResponse)
async def admin_edit_filtered(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(FilteredContent).filter(FilteredContent.id == content_id).first()
    )
    if not content:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")
    form = FilteredContentForm(obj=content)
    return templates.TemplateResponse(
        "admin/filtered_content_form.html",
        {
            "request": request,
            "form": form,
            "content": content,
            "action": "edit",
        },
    )


@router.post("/filtered/{content_id}/edit")
async def admin_edit_filtered_submit(
    request: Request,
    content_id: int,
    filter_result: str = Form(...),
    reasoning: str = Form(""),
    confidence_score: int = Form(None),
    suitable_for_blog: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(FilteredContent).filter(FilteredContent.id == content_id).first()
    )
    if not content:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")
    content.filter_result = filter_result
    content.reasoning = reasoning
    content.confidence_score = confidence_score
    content.suitable_for_blog = suitable_for_blog
    db.commit()
    flash_message(request, "콘텐츠가 수정되었습니다.", "success")
    return RedirectResponse("/admin/filtered", status_code=302)


@router.post("/filtered/{content_id}/delete")
async def admin_delete_filtered(
    request: Request,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    content = (
        db.query(FilteredContent).filter(FilteredContent.id == content_id).first()
    )
    if content:
        db.delete(content)
        db.commit()
        flash_message(request, "콘텐츠가 삭제되었습니다.", "success")
    return RedirectResponse("/admin/filtered", status_code=302)
