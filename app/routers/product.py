from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.services.product_service import ProductService
from app.dependencies import get_db, get_current_user
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/product", tags=["product"])
templates = Jinja2Templates(directory="templates")

# Pydantic 모델
class ReviewRequest(BaseModel):
    rating: int
    title: Optional[str] = None
    content: str
    csrf_token: str
    idempotency_key: str

# SSR: SEO 최적화된 상품 상세 페이지
@router.get("/{slug}", response_class=HTMLResponse)
def product_detail(request: Request, slug: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    SEO 최적화된 상품 상세 페이지 (canonical URL)
    - shop.py와 역할 분담: 정보 제공 중심
    - 구매는 shop.py로 연결
    """
    product_data = ProductService.get_product_detail_seo(slug, user.id if user else None, db)
    
    if not product_data:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("product/detail.html", {
        "request": request,
        "user": user,
        **product_data
    })

# SSR: 상품 리뷰 목록
@router.get("/{slug}/reviews", response_class=HTMLResponse)
def product_reviews(request: Request, slug: str, page: int = 1, db: Session = Depends(get_db)):
    """
    상품별 리뷰 목록 페이지
    """
    reviews_data = ProductService.get_product_reviews(slug, page, db)
    
    if not reviews_data:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("product/reviews.html", {
        "request": request,
        "page": page,
        **reviews_data
    })

# API: 리뷰 작성 (구매자 검증 포함)
@router.post("/{slug}/review")
def create_review(slug: str, review: ReviewRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    상품 리뷰 작성 (구매자만 가능)
    """
    result = ProductService.create_product_review(
        slug=slug,
        user_id=user.id,
        rating=review.rating,
        title=review.title,
        content=review.content,
        db=db
    )
    
    return result

# API: 리뷰 도움됨 표시
@router.post("/reviews/{review_id}/helpful")
def mark_review_helpful(review_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    리뷰 도움됨 표시
    """
    result = ProductService.mark_review_helpful(review_id, user.id, db)
    return result

# API: 리뷰 신고
@router.post("/reviews/{review_id}/report")
def report_review(review_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    리뷰 신고
    """
    result = ProductService.report_review(review_id, user.id, db)
    return result 