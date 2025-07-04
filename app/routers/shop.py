"""
운세 상점 라우터 - SSR HTML 페이지 + JSON API
Week 1: 핵심 인프라 - 상점 시스템 완전 구현
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.shop_service import ShopService, get_shop_service
from app.services.fortune_service import FortuneService, get_fortune_service
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.error_handlers import ValidationError, InsufficientPointsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shop", tags=["shop"])

# 의존성
def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """현재 로그인한 사용자 조회"""
    user_id = request.session.get("user_id")
    if user_id:
        return db.query(User).filter(User.id == user_id).first()
    return None

################################################################################
# 🛍️ 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/", response_class=HTMLResponse)
async def shop_list(
    request: Request,
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    sort_by: str = Query("created_at"),
    db: Session = Depends(get_db)
):
    """상품 목록 페이지"""
    try:
        shop_service = ShopService(db)
        fortune_service = FortuneService(db)
        
        # 상품 목록 조회
        products_data = shop_service.get_products(
            category=category,
            search=search,
            page=page,
            sort_by=sort_by
        )
        
        # 현재 사용자 정보
        current_user = get_current_user(request, db)
        user_points = 0
        if current_user:
            balance_info = fortune_service.get_user_balance(current_user.id)
            user_points = balance_info['points']
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "shop/list.html",
            {
                "request": request,
                "products": products_data['products'],
                "pagination": products_data['pagination'],
                "current_user": current_user,
                "user_points": user_points,
                "category": category,
                "search": search,
                "sort_by": sort_by,
                "csrf_token": csrf_token
            }
        )
        
    except Exception as e:
        logger.error(f"Shop list error: {e}")
        raise HTTPException(status_code=500, detail="상품 목록을 불러오는 중 오류가 발생했습니다.")

@router.get("/{slug}", response_class=HTMLResponse)
async def shop_detail(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    """상품 상세 페이지"""
    try:
        shop_service = ShopService(db)
        fortune_service = FortuneService(db)
        
        # 상품 정보 조회
        product = shop_service.get_product_by_slug(slug)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        # 현재 사용자 정보
        current_user = get_current_user(request, db)
        user_points = 0
        discount_info = None
        
        if current_user:
            balance_info = fortune_service.get_user_balance(current_user.id)
            user_points = balance_info['points']
            
            # 할인 정보 계산
            discount_info = shop_service.calculate_discount(current_user.id, product['id'])
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "shop/detail.html",
            {
                "request": request,
                "product": product,
                "current_user": current_user,
                "user_points": user_points,
                "discount_info": discount_info,
                "csrf_token": csrf_token
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shop detail error: {e}")
        raise HTTPException(status_code=500, detail="상품 정보를 불러오는 중 오류가 발생했습니다.")

@router.get("/{slug}/buy", response_class=HTMLResponse)
async def shop_buy(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    """구매 선택 페이지"""
    try:
        # 로그인 체크
        current_user = get_current_user(request, db)
        if not current_user:
            return RedirectResponse(url=f"/auth/login?redirect=/shop/{slug}/buy", status_code=302)
        
        shop_service = ShopService(db)
        fortune_service = FortuneService(db)
        
        # 상품 정보 조회
        product = shop_service.get_product_by_slug(slug)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        # 사용자 포인트 정보
        balance_info = fortune_service.get_user_balance(current_user.id)
        user_points = balance_info['points']
        
        # 할인 정보 계산
        discount_info = shop_service.calculate_discount(current_user.id, product['id'])
        
        # 구매 가능 여부 확인
        can_buy_with_points = False
        if product['fortune_cost'] > 0:
            can_buy_with_points = user_points >= product['fortune_cost']
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "shop/buy.html",
            {
                "request": request,
                "product": product,
                "current_user": current_user,
                "user_points": user_points,
                "discount_info": discount_info,
                "can_buy_with_points": can_buy_with_points,
                "csrf_token": csrf_token
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shop buy error: {e}")
        raise HTTPException(status_code=500, detail="구매 페이지를 불러오는 중 오류가 발생했습니다.")

################################################################################
# 🔌 JSON API 라우터
################################################################################

@router.get("/api/v1/products")
async def api_get_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    sort_by: str = Query("created_at"),
    db: Session = Depends(get_db)
):
    """상품 목록 API"""
    try:
        shop_service = ShopService(db)
        products_data = shop_service.get_products(
            category=category,
            search=search,
            page=page,
            per_page=per_page,
            sort_by=sort_by
        )
        
        return {
            "success": True,
            "data": products_data
        }
        
    except Exception as e:
        logger.error(f"API products error: {e}")
        raise HTTPException(status_code=500, detail="상품 목록을 불러오는 중 오류가 발생했습니다.")

@router.get("/api/v1/products/{slug}")
async def api_get_product(
    slug: str,
    db: Session = Depends(get_db)
):
    """상품 상세 API"""
    try:
        shop_service = ShopService(db)
        product = shop_service.get_product_by_slug(slug)
        
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        return {
            "success": True,
            "data": product
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API product detail error: {e}")
        raise HTTPException(status_code=500, detail="상품 정보를 불러오는 중 오류가 발생했습니다.")

@router.post("/api/v1/purchases")
async def api_create_purchase(
    request: Request,
    product_id: int = Form(...),
    purchase_type: str = Form(...),  # "points" or "cash"
    saju_key: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """구매 생성 API"""
    try:
        # CSRF 토큰 검증
        validate_csrf_token(request, csrf_token)
        
        # 로그인 체크
        current_user = get_current_user(request, db)
        if not current_user:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        
        shop_service = ShopService(db)
        
        if purchase_type == "points":
            # 포인트 구매
            result = shop_service.purchase_with_points(
                user_id=current_user.id,
                product_id=product_id,
                saju_key=saju_key
            )
            
            return {
                "success": True,
                "data": result,
                "message": "포인트 구매가 완료되었습니다."
            }
            
        elif purchase_type == "cash":
            # 현금 결제 준비
            result = shop_service.prepare_cash_payment(
                user_id=current_user.id,
                product_id=product_id,
                saju_key=saju_key
            )
            
            return {
                "success": True,
                "data": result,
                "message": "결제 페이지로 이동합니다."
            }
            
        else:
            raise HTTPException(status_code=400, detail="유효하지 않은 구매 타입입니다.")
        
    except InsufficientPointsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API purchase error: {e}")
        raise HTTPException(status_code=500, detail="구매 처리 중 오류가 발생했습니다.")

@router.get("/api/v1/categories")
async def api_get_categories(db: Session = Depends(get_db)):
    """카테고리 목록 API"""
    try:
        # TODO: Category 모델에서 카테고리 목록 조회
        categories = [
            {"id": "saju", "name": "사주", "description": "사주 분석 서비스"},
            {"id": "tarot", "name": "타로", "description": "타로 카드 상담"},
            {"id": "fortune", "name": "운세", "description": "운세 상담 서비스"}
        ]
        
        return {
            "success": True,
            "data": categories
        }
        
    except Exception as e:
        logger.error(f"API categories error: {e}")
        raise HTTPException(status_code=500, detail="카테고리 목록을 불러오는 중 오류가 발생했습니다.")

@router.get("/api/v1/user/purchases")
async def api_get_user_purchases(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """사용자 구매 내역 API"""
    try:
        # 로그인 체크
        current_user = get_current_user(request, db)
        if not current_user:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        
        shop_service = ShopService(db)
        purchases_data = shop_service.get_user_purchases(
            user_id=current_user.id,
            page=page,
            per_page=per_page
        )
        
        return {
            "success": True,
            "data": purchases_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API user purchases error: {e}")
        raise HTTPException(status_code=500, detail="구매 내역을 불러오는 중 오류가 발생했습니다.") 