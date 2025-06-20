"""주문 / 결제 Router - 간소화 버전"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product, User
from app.template import templates
from app.dependencies import get_current_user
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["Order"])

################################################################################
# 1) 주문 생성 (간소화 버전)
################################################################################
@router.post("/create")
async def create_order(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 생성 - 일단 간단하게 성공 응답만"""
    try:
        logger.info(f"주문 생성 요청: user_id={user.id}, payload={payload}")
        
        saju_key = payload.get("saju_key")
        if not saju_key:
            raise HTTPException(status_code=400, detail="사주 정보가 필요합니다.")
        
        logger.info(f"사주 키: {saju_key}")
        
        # 일단 기본 Product가 없으면 생성
        product = db.query(Product).filter(Product.code == "premium_saju").first()
        if not product:
            product = Product(
                name="AI 심층 사주 리포트",
                description="고서 원문 + AI 심층 분석",
                price=1900,
                code="premium_saju",
                is_active=True
            )
            db.add(product)
            db.commit()
            logger.info("기본 상품 생성됨")
        
        # 임시 주문 생성 (카카오페이 연동 전)
        order = Order(
            user_id=user.id,
            product_id=product.id,
            amount=product.price,
            saju_key=saju_key,
            status="pending",
            kakao_tid="temp_" + str(datetime.now().timestamp()),
            created_at=datetime.utcnow()
        )
        db.add(order)
        db.commit()
        
        logger.info(f"임시 주문 생성 성공: order_id={order.id}")
        
        # 일단 성공 응답 (실제 카카오페이는 나중에)
        return JSONResponse({
            "success": True,
            "order_id": order.id,
            "message": "주문이 생성되었습니다. (카카오페이 연동 예정)",
            "redirect_url": f"/order/test-success/{order.id}"  # 임시 페이지
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 생성 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"주문 생성 중 오류가 발생했습니다: {str(e)}")

################################################################################
# 2) 임시 성공 페이지
################################################################################
@router.get("/test-success/{order_id}", response_class=HTMLResponse)
async def test_success_page(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """임시 성공 페이지"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("order/test_success.html", {
        "request": request,
        "order": order
    })

################################################################################
# 3) 마이페이지 구매내역 (간소화)
################################################################################
@router.get("/mypage", response_class=HTMLResponse)
async def mypage_orders(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구매 내역 페이지"""
    orders = (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    
    return templates.TemplateResponse("mypage/orders.html", {
        "request": request,
        "orders": orders
    })