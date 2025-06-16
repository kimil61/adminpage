from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, Category
from app.template import templates

router = APIRouter()

@router.get("/saju", response_class=HTMLResponse)
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
