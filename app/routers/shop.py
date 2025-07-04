"""
운세 상점 라우터 - SSR HTML 페이지
- 상품 리스트/상세 페이지
- 구매 선택 페이지 (포인트 vs 현금)
- API 엔드포인트 (JSON 응답)
"""

from fastapi import APIRouter, Request, Depends, Query, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from app.database import get_db
from app.models import Product, User, UserPurchase
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.services.shop_service import ShopService
from app.services.fortune_service import FortuneService
from app.services.payment_service import PaymentService
from app.utils import generate_live_report_for_user, generate_live_report_from_db
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shop", tags=["Shop"])

################################################################################
# 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/", response_class=HTMLResponse)
async def shop_list(
    request: Request,
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional)
):
    """상품 리스트 페이지"""
    try:
        # 상품 목록 조회
        result = ShopService.get_products(
            category=category,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=12,
            db=db
        )
        
        # 사용자 포인트 정보 (로그인한 경우)
        user_points = 0
        if user:
            fortune_info = FortuneService.get_user_fortune_info(user.id, db)
            user_points = fortune_info["points"]
        
        return templates.TemplateResponse("shop/list.html", {
            "request": request,
            "products": result["products"],
            "pagination": result["pagination"],
            "category": category,
            "search": search,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "user": user,
            "user_points": user_points
        })
        
    except Exception as e:
        logger.error(f"상품 리스트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="상품 목록을 불러오는 중 오류가 발생했습니다.")

@router.get("/{slug}", response_class=HTMLResponse)
async def shop_detail(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional)
):
    """상품 상세 페이지"""
    try:
        # 상품 조회
        product = ShopService.get_product_by_slug(slug, db)
        if not product:
            raise NotFoundError("상품을 찾을 수 없습니다.")
        
        # 상품 상세 정보 조회
        detail_info = ShopService.get_product_detail(
            product_id=product.id,
            user_id=user.id if user else None,
            db=db
        )
        
        # 사용자 포인트 정보 (로그인한 경우)
        user_points = 0
        if user:
            fortune_info = FortuneService.get_user_fortune_info(user.id, db)
            user_points = fortune_info["points"]
        
        return templates.TemplateResponse("shop/detail.html", {
            "request": request,
            "product": detail_info["product"],
            "saju_product": detail_info["saju_product"],
            "user": user,
            "user_points": user_points,
            "can_purchase_with_points": detail_info["can_purchase_with_points"],
            "reviews": detail_info["reviews"]
        })
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"상품 상세 조회 실패: slug={slug}, error={e}")
        raise HTTPException(status_code=500, detail="상품 정보를 불러오는 중 오류가 발생했습니다.")

@router.get("/{slug}/buy", response_class=HTMLResponse)
async def shop_buy(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매 선택 페이지 (포인트 vs 현금)"""
    try:
        # 상품 조회
        product = ShopService.get_product_by_slug(slug, db)
        if not product:
            raise NotFoundError("상품을 찾을 수 없습니다.")
        
        # 사용자 포인트 정보
        fortune_info = FortuneService.get_user_fortune_info(user.id, db)
        user_points = fortune_info["points"]
        
        # 구매 가능 여부 확인
        can_purchase_with_points = product.fortune_cost > 0 and user_points >= product.fortune_cost
        can_purchase_with_cash = product.price > 0
        
        # 중복 구매 체크
        existing_purchase = db.query(UserPurchase).filter(
            UserPurchase.user_id == user.id,
            UserPurchase.product_id == product.id
        ).first()
        
        if existing_purchase:
            return templates.TemplateResponse("shop/already_purchased.html", {
                "request": request,
                "product": product,
                "user": user,
                "purchase": existing_purchase
            })
        
        return templates.TemplateResponse("shop/buy.html", {
            "request": request,
            "product": product,
            "user": user,
            "user_points": user_points,
            "can_purchase_with_points": can_purchase_with_points,
            "can_purchase_with_cash": can_purchase_with_cash
        })
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f"구매 페이지 조회 실패: slug={slug}, error={e}")
        raise HTTPException(status_code=500, detail="구매 페이지를 불러오는 중 오류가 발생했습니다.")

################################################################################
# API 라우터 (JSON 응답)
################################################################################

@router.get("/api/v1/products")
async def api_get_products(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """상품 목록 API"""
    try:
        result = ShopService.get_products(
            category=category,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page,
            db=db
        )
        
        # 상품 데이터 직렬화
        products_data = []
        for product in result["products"]:
            products_data.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "fortune_cost": product.fortune_cost,
                "slug": product.slug,
                "category": product.category,
                "thumbnail": product.thumbnail,
                "is_featured": product.is_featured,
                "created_at": product.created_at.isoformat() if product.created_at else None
            })
        
        return JSONResponse({
            "success": True,
            "data": {
                "products": products_data,
                "pagination": result["pagination"]
            }
        })
        
    except Exception as e:
        logger.error(f"상품 목록 API 실패: {e}")
        return JSONResponse({
            "success": False,
            "error": "상품 목록을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/categories")
async def api_get_categories(db: Session = Depends(get_db)):
    """카테고리 목록 API"""
    try:
        # 상품 카테고리 조회
        categories = db.query(Product.category).filter(
            Product.is_active == True
        ).distinct().all()
        
        category_list = [cat[0] for cat in categories if cat[0]]
        
        return JSONResponse({
            "success": True,
            "data": {
                "categories": category_list
            }
        })
        
    except Exception as e:
        logger.error(f"카테고리 목록 API 실패: {e}")
        return JSONResponse({
            "success": False,
            "error": "카테고리 목록을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/purchases")
async def api_create_purchase(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """포인트 구매 처리 API (idempotency_key 포함)"""
    try:
        product_id = payload.get("product_id")
        purchase_type = payload.get("purchase_type", "fortune_points")  # fortune_points or cash
        idempotency_key = payload.get("idempotency_key")
        
        if not product_id:
            return JSONResponse({
                "success": False,
                "error": "상품 ID가 필요합니다."
            }, status_code=400)
        
        # Idempotency 체크
        if idempotency_key:
            existing_result = PaymentService.check_idempotency(db, idempotency_key, "purchase")
            if existing_result:
                return JSONResponse({
                    "success": True,
                    "data": existing_result,
                    "idempotency_hit": True
                })
        
        # 구매 처리
        if purchase_type == "fortune_points":
            success, message, purchase_info = ShopService.process_point_purchase(
                user_id=user.id,
                product_id=product_id,
                db=db
            )
        else:
            success, message, purchase_info = ShopService.process_cash_purchase(
                user_id=user.id,
                product_id=product_id,
                db=db
            )
        
        if success:
            # Idempotency 결과 저장
            if idempotency_key:
                PaymentService.store_idempotency_result(
                    db, idempotency_key, "purchase", purchase_info
                )
            
            return JSONResponse({
                "success": True,
                "data": purchase_info,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"구매 처리 API 실패: {e}")
        return JSONResponse({
            "success": False,
            "error": "구매 처리 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/orders/prepare")
async def api_prepare_order(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """카카오페이 결제 준비 API"""
    try:
        product_id = payload.get("product_id")
        idempotency_key = payload.get("idempotency_key")
        
        if not product_id:
            return JSONResponse({
                "success": False,
                "error": "상품 ID가 필요합니다."
            }, status_code=400)
        
        # 상품 조회
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.is_active == True
        ).first()
        
        if not product:
            return JSONResponse({
                "success": False,
                "error": "상품을 찾을 수 없습니다."
            }, status_code=404)
        
        # 카카오페이 결제 준비
        result = await PaymentService.prepare_kakaopay_payment(
            amount=product.price,
            item_name=product.name,
            user_id=user.id,
            order_type="cash",
            idempotency_key=idempotency_key,
            db=db
        )
        
        return JSONResponse({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"결제 준비 API 실패: {e}")
        return JSONResponse({
            "success": False,
            "error": "결제 준비 중 오류가 발생했습니다."
        }, status_code=500)

################################################################################
# 유틸리티 함수들
################################################################################

def format_price(price: int) -> str:
    """가격 포맷팅"""
    return f"{price:,}원"

def get_product_status(product: Product, user_points: int) -> Dict[str, Any]:
    """상품 상태 정보"""
    can_purchase_with_points = product.fortune_cost > 0 and user_points >= product.fortune_cost
    can_purchase_with_cash = product.price > 0
    
    return {
        "can_purchase_with_points": can_purchase_with_points,
        "can_purchase_with_cash": can_purchase_with_cash,
        "points_shortage": product.fortune_cost - user_points if product.fortune_cost > user_points else 0
    }

################################################################################
# 리포트 생성/다운로드 (기존 order.py 기능 연동)
################################################################################

@router.get("/purchase/{purchase_id}/report", response_class=HTMLResponse)
async def view_purchase_report(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매한 상품의 리포트 보기"""
    try:
        from sqlalchemy import and_
        
        # 구매 내역 확인
        purchase = db.query(UserPurchase).filter(
            and_(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user.id
            )
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="구매 내역을 찾을 수 없습니다.")
        
        # 상품 정보
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품 정보를 찾을 수 없습니다.")
        
        # 리포트 생성 (기존 order.py 로직 활용)
        try:
            report_html = generate_live_report_for_user(
                user_id=user.id,
                product_id=product.id,
                purchase_id=purchase.id
            )
            
            return templates.TemplateResponse("shop/report.html", {
                "request": request,
                "user": user,
                "product": product,
                "purchase": purchase,
                "report_html": report_html
            })
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: purchase_id={purchase_id}, error={e}")
            return templates.TemplateResponse("shop/report_error.html", {
                "request": request,
                "user": user,
                "product": product,
                "purchase": purchase,
                "error": str(e)
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 조회 실패: purchase_id={purchase_id}, error={e}")
        raise HTTPException(status_code=500, detail="리포트를 불러오는 중 오류가 발생했습니다.")

@router.get("/purchase/{purchase_id}/success", response_class=HTMLResponse)
async def purchase_success(
    request: Request,
    purchase_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매 완료 페이지"""
    try:
        from sqlalchemy import and_
        
        # 구매 내역 확인
        purchase = db.query(UserPurchase).filter(
            and_(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user.id
            )
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="구매 내역을 찾을 수 없습니다.")
        
        # 상품 정보
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품 정보를 찾을 수 없습니다.")
        
        return templates.TemplateResponse("shop/purchase_success.html", {
            "request": request,
            "user": user,
            "product": product,
            "purchase": purchase
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"구매 완료 페이지 조회 실패: purchase_id={purchase_id}, error={e}")
        raise HTTPException(status_code=500, detail="구매 완료 페이지를 불러오는 중 오류가 발생했습니다.")

@router.get("/api/v1/purchase/{purchase_id}/status")
async def get_purchase_status(
    purchase_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매 상태 확인 API"""
    try:
        from sqlalchemy import and_
        
        # 구매 내역 확인
        purchase = db.query(UserPurchase).filter(
            and_(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user.id
            )
        ).first()
        
        if not purchase:
            return JSONResponse({
                "success": False,
                "error": "구매 내역을 찾을 수 없습니다."
            }, status_code=404)
        
        return JSONResponse({
            "success": True,
            "data": {
                "purchase_id": purchase.id,
                "status": purchase.status,
                "report_status": purchase.report_status,
                "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
                "completed_at": purchase.completed_at.isoformat() if purchase.completed_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"구매 상태 확인 실패: purchase_id={purchase_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구매 상태 확인 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/purchase/{purchase_id}/retry")
async def retry_purchase_report(
    purchase_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리포트 생성 재시도 API"""
    try:
        from sqlalchemy import and_
        
        # 구매 내역 확인
        purchase = db.query(UserPurchase).filter(
            and_(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user.id
            )
        ).first()
        
        if not purchase:
            return JSONResponse({
                "success": False,
                "error": "구매 내역을 찾을 수 없습니다."
            }, status_code=404)
        
        # 상품 정보
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        if not product:
            return JSONResponse({
                "success": False,
                "error": "상품 정보를 찾을 수 없습니다."
            }, status_code=404)
        
        # 리포트 생성 재시도
        try:
            PaymentService.process_payment_completion(
                purchase_id=purchase.id,
                user_id=user.id,
                product_id=product.id,
                payment_type=purchase.payment_type,
                db=db
            )
            
            return JSONResponse({
                "success": True,
                "message": "리포트 생성이 시작되었습니다."
            })
            
        except Exception as e:
            logger.error(f"리포트 생성 재시도 실패: purchase_id={purchase_id}, error={e}")
            return JSONResponse({
                "success": False,
                "error": "리포트 생성 재시도에 실패했습니다."
            }, status_code=500)
        
    except Exception as e:
        logger.error(f"리포트 생성 재시도 실패: purchase_id={purchase_id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "리포트 생성 재시도 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/purchase/{purchase_id}/download")
async def download_purchase_report(
    purchase_id: int,
    format: str = Query("html", regex="^(html|pdf)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매한 상품의 리포트 다운로드"""
    try:
        from sqlalchemy import and_
        
        # 구매 내역 확인
        purchase = db.query(UserPurchase).filter(
            and_(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user.id
            )
        ).first()
        
        if not purchase:
            raise HTTPException(status_code=404, detail="구매 내역을 찾을 수 없습니다.")
        
        # 상품 정보
        product = db.query(Product).filter(Product.id == purchase.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품 정보를 찾을 수 없습니다.")
        
        # 리포트 생성 및 다운로드 (기존 order.py 로직 활용)
        try:
            if format == "html":
                report_html = generate_live_report_for_user(
                    user_id=user.id,
                    product_id=product.id,
                    purchase_id=purchase.id
                )
                
                filename = f"{product.name}_{purchase.created_at.strftime('%Y%m%d')}.html"
                return HTMLResponse(
                    content=report_html,
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:  # PDF
                # TODO: PDF 생성 로직 구현
                raise HTTPException(status_code=501, detail="PDF 다운로드는 준비 중입니다.")
                
        except Exception as e:
            logger.error(f"리포트 다운로드 실패: purchase_id={purchase_id}, format={format}, error={e}")
            raise HTTPException(status_code=500, detail="리포트 다운로드 중 오류가 발생했습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 다운로드 실패: purchase_id={purchase_id}, error={e}")
        raise HTTPException(status_code=500, detail="리포트 다운로드 중 오류가 발생했습니다.") 