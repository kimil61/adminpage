"""
결제 콜백 라우터 (카카오페이 등)
- 결제 성공/실패/취소 처리
- 포인트 충전/상품구매/구독 등 결제 후 처리
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Order
from app.services.payment_service import PaymentService
from app.services.fortune_service import FortuneService
from app.utils.error_handlers import PaymentError
from app.template import templates

router = APIRouter(prefix="/payment", tags=["payment"])

@router.get("/success", response_class=HTMLResponse)
async def payment_success(
    request: Request,
    order_id: str = Query(...),
    pg_token: str = Query(None),
    db: Session = Depends(get_db)
):
    """카카오페이 결제 성공 콜백"""
    try:
        # 주문 조회
        order = db.query(Order).filter(Order.partner_order_id == order_id).first()
        if not order:
            return HTMLResponse("<h2>주문 정보를 찾을 수 없습니다.</h2>", status_code=404)
        
        # 결제 승인 처리
        payment_service = PaymentService(db)
        result = payment_service.verify_kakaopay_payment(
            tid=str(order.kakao_tid),
            pg_token=pg_token,
            idempotency_key=None
        )
        
        # 포인트 충전(패키지)라면 적립 처리
        if order.order_type == 'fortune_points' and order.package_id:
            fortune_service = FortuneService(db)
            fortune_service.process_package_purchase(
                user_id=int(order.user_id),
                package_id=int(order.package_id),
                order_id=int(order.id)
            )
        
        return templates.TemplateResponse(
            "payment/success.html",
            {"request": request, "order": order, "result": result}
        )
    except Exception as e:
        return HTMLResponse(f"<h2>결제 처리 중 오류: {e}</h2>", status_code=500)

@router.get("/fail", response_class=HTMLResponse)
async def payment_fail(request: Request):
    """카카오페이 결제 실패 콜백"""
    return templates.TemplateResponse(
        "payment/fail.html", {"request": request}
    )

@router.get("/cancel", response_class=HTMLResponse)
async def payment_cancel(request: Request):
    """카카오페이 결제 취소 콜백"""
    return request.app.state.templates.TemplateResponse(
        "payment/cancel.html", {"request": request}
    ) 