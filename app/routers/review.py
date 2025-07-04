"""
리뷰 라우터 - 상품 리뷰 관리
- 리뷰 작성/수정/삭제
- 리뷰 목록 조회
- 리뷰 신고 및 관리
"""

from fastapi import APIRouter, Request, Depends, Query, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from app.database import get_db
from app.models import User, Product, UserReview
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.services.review_service import ReviewService
from app.services.shop_service import ShopService
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["Review"])

################################################################################
# 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/write/{product_slug}", response_class=HTMLResponse)
async def review_write_form(
    request: Request,
    product_slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 작성 폼 페이지"""
    try:
        # 상품 조회
        product = ShopService.get_product_by_slug(product_slug, db)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        # 리뷰 작성 가능 여부 확인
        can_write, message = ReviewService.can_write_review(user.id, product.id, db)
        
        return templates.TemplateResponse("review/write.html", {
            "request": request,
            "user": user,
            "product": product,
            "can_write": can_write,
            "message": message
        })
        
    except Exception as e:
        logger.error(f"리뷰 작성 폼 조회 실패: product_slug={product_slug}, error={e}")
        raise HTTPException(status_code=500, detail="리뷰 작성 페이지를 불러오는 중 오류가 발생했습니다.")

@router.get("/edit/{review_id}", response_class=HTMLResponse)
async def review_edit_form(
    request: Request,
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 수정 폼 페이지"""
    try:
        # 리뷰 조회
        review = db.query(UserReview).filter(
            and_(
                UserReview.id == review_id,
                UserReview.user_id == user.id,
                UserReview.is_visible == True
            )
        ).first()
        
        if not review:
            raise HTTPException(status_code=404, detail="수정할 리뷰를 찾을 수 없습니다.")
        
        # 상품 정보 조회
        product = db.query(Product).filter(Product.id == review.product_id).first()
        
        return templates.TemplateResponse("review/edit.html", {
            "request": request,
            "user": user,
            "review": review,
            "product": product
        })
        
    except Exception as e:
        logger.error(f"리뷰 수정 폼 조회 실패: review_id={review_id}, error={e}")
        raise HTTPException(status_code=500, detail="리뷰 수정 페이지를 불러오는 중 오류가 발생했습니다.")

@router.get("/list/{product_slug}", response_class=HTMLResponse)
async def review_list(
    request: Request,
    product_slug: str,
    page: int = Query(1, ge=1),
    sort_by: str = Query("created_at", regex="^(created_at|rating|helpful)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional)
):
    """상품 리뷰 목록 페이지"""
    try:
        # 상품 조회
        product = ShopService.get_product_by_slug(product_slug, db)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        # 리뷰 목록 조회
        reviews_data = ReviewService.get_product_reviews(
            product_id=product.id,
            db=db,
            page=page,
            per_page=10,
            sort_by=sort_by,
            sort_order=sort_order,
            rating_filter=rating_filter
        )
        
        return templates.TemplateResponse("review/list.html", {
            "request": request,
            "user": user,
            "product": product,
            "reviews": reviews_data["reviews"],
            "pagination": reviews_data["pagination"],
            "statistics": reviews_data["statistics"],
            "current_sort": sort_by,
            "current_order": sort_order,
            "current_rating_filter": rating_filter
        })
        
    except Exception as e:
        logger.error(f"리뷰 목록 조회 실패: product_slug={product_slug}, error={e}")
        raise HTTPException(status_code=500, detail="리뷰 목록을 불러오는 중 오류가 발생했습니다.")

@router.get("/my", response_class=HTMLResponse)
async def my_reviews(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """내 리뷰 목록 페이지"""
    try:
        # 사용자 리뷰 목록 조회
        reviews_data = ReviewService.get_user_reviews(
            user_id=user.id,
            db=db,
            page=page,
            per_page=10
        )
        
        return templates.TemplateResponse("review/my.html", {
            "request": request,
            "user": user,
            "reviews": reviews_data["reviews"],
            "pagination": reviews_data["pagination"]
        })
        
    except Exception as e:
        logger.error(f"내 리뷰 목록 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="내 리뷰 목록을 불러오는 중 오류가 발생했습니다.")

################################################################################
# API 라우터 (JSON 응답)
################################################################################

@router.post("/api/v1/create")
async def api_create_review(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 작성 API"""
    try:
        product_id = payload.get("product_id")
        rating = payload.get("rating")
        content = payload.get("content")
        title = payload.get("title")
        accuracy_rating = payload.get("accuracy_rating")
        satisfaction_rating = payload.get("satisfaction_rating")
        recommendation_rating = payload.get("recommendation_rating")
        
        if not all([product_id, rating, content]):
            return JSONResponse({
                "success": False,
                "error": "필수 항목을 모두 입력해주세요."
            }, status_code=400)
        
        # 리뷰 작성
        success, message, result = ReviewService.create_review(
            user_id=user.id,
            product_id=product_id,
            rating=rating,
            content=content,
            title=title,
            accuracy_rating=accuracy_rating,
            satisfaction_rating=satisfaction_rating,
            recommendation_rating=recommendation_rating,
            db=db
        )
        
        if success:
            return JSONResponse({
                "success": True,
                "data": result,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"리뷰 작성 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 작성 중 오류가 발생했습니다."
        }, status_code=500)

@router.put("/api/v1/update/{review_id}")
async def api_update_review(
    request: Request,
    review_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 수정 API"""
    try:
        rating = payload.get("rating")
        content = payload.get("content")
        title = payload.get("title")
        accuracy_rating = payload.get("accuracy_rating")
        satisfaction_rating = payload.get("satisfaction_rating")
        recommendation_rating = payload.get("recommendation_rating")
        
        # 리뷰 수정
        success, message, result = ReviewService.update_review(
            user_id=user.id,
            review_id=review_id,
            rating=rating,
            content=content,
            title=title,
            accuracy_rating=accuracy_rating,
            satisfaction_rating=satisfaction_rating,
            recommendation_rating=recommendation_rating,
            db=db
        )
        
        if success:
            return JSONResponse({
                "success": True,
                "data": result,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"리뷰 수정 API 실패: user_id={user.id}, review_id={review_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 수정 중 오류가 발생했습니다."
        }, status_code=500)

@router.delete("/api/v1/delete/{review_id}")
async def api_delete_review(
    request: Request,
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 삭제 API"""
    try:
        # 리뷰 삭제
        success, message = ReviewService.delete_review(
            user_id=user.id,
            review_id=review_id,
            db=db
        )
        
        if success:
            return JSONResponse({
                "success": True,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"리뷰 삭제 API 실패: user_id={user.id}, review_id={review_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 삭제 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/helpful/{review_id}")
async def api_mark_helpful(
    request: Request,
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 도움됨 표시 API"""
    try:
        # 도움됨 표시
        success, message = ReviewService.mark_helpful(
            review_id=review_id,
            user_id=user.id,
            db=db
        )
        
        if success:
            return JSONResponse({
                "success": True,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"리뷰 도움됨 표시 API 실패: user_id={user.id}, review_id={review_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "도움됨 표시 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/report/{review_id}")
async def api_report_review(
    request: Request,
    review_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 신고 API"""
    try:
        reason = payload.get("reason")
        description = payload.get("description")
        
        if not reason:
            return JSONResponse({
                "success": False,
                "error": "신고 사유를 입력해주세요."
            }, status_code=400)
        
        # 리뷰 신고
        success, message = ReviewService.report_review(
            review_id=review_id,
            user_id=user.id,
            reason=reason,
            description=description,
            db=db
        )
        
        if success:
            return JSONResponse({
                "success": True,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"리뷰 신고 API 실패: user_id={user.id}, review_id={review_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 신고 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/product/{product_id}")
async def api_get_product_reviews(
    request: Request,
    product_id: int,
    page: int = Query(1, ge=1),
    sort_by: str = Query("created_at", regex="^(created_at|rating|helpful)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db)
):
    """상품 리뷰 목록 API"""
    try:
        # 리뷰 목록 조회
        reviews_data = ReviewService.get_product_reviews(
            product_id=product_id,
            db=db,
            page=page,
            per_page=10,
            sort_by=sort_by,
            sort_order=sort_order,
            rating_filter=rating_filter
        )
        
        return JSONResponse({
            "success": True,
            "data": reviews_data
        })
        
    except Exception as e:
        logger.error(f"상품 리뷰 목록 API 실패: product_id={product_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 목록을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/can-write/{product_id}")
async def api_can_write_review(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리뷰 작성 가능 여부 확인 API"""
    try:
        # 작성 가능 여부 확인
        can_write, message = ReviewService.can_write_review(
            user_id=user.id,
            product_id=product_id,
            db=db
        )
        
        return JSONResponse({
            "success": True,
            "data": {
                "can_write": can_write,
                "message": message
            }
        })
        
    except Exception as e:
        logger.error(f"리뷰 작성 가능 여부 확인 API 실패: user_id={user.id}, product_id={product_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리뷰 작성 가능 여부를 확인할 수 없습니다."
        }, status_code=500) 