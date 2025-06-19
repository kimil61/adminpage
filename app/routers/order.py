

"""주문 / 결제 / 구매내역 Router
- POST /order/create : 카카오페이 Ready → 결제창 Redirect URL 반환
- GET  /order/approve : 카카오페이 Approve 웹훅
- GET  /mypage/orders : 마이페이지 구매내역
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, SajuAnalysisCache
from app.template import templates

# TODO: 실제 구현된 유저 인증 디펜던시 import
from app.dependencies import get_current_user   # (User 스키마 반환)

from app.payments.kakaopay import kakao_ready, kakao_approve   # → wrappers
from app.tasks import generate_full_report   # Celery task

router = APIRouter(prefix="/order", tags=["Order"])

################################################################################
# 1) 주문 생성 (카카오 ready 반환)
################################################################################
@router.post("/create")
async def create_order(
    request: Request,
    saju_key: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    - saju_key, product 가 기본 파라미터
    - 카카오결제 준비 API 호출 후 redirect_url 과 tid 리턴
    """
    # 이미 같은 사주 Full 구매한 적 있으면 바로 리턴
    exists = (
        db.query(Order)
        .filter(Order.user_id == user.id,
                Order.saju_key == saju_key,
                Order.status == "paid")
        .first()
    )
    if exists:
        raise HTTPException(status_code=400,
                            detail="이미 결제한 리포트입니다. 마이페이지에서 확인하세요.")

    # 1) pending Order 생성
    order = Order(
        user_id=user.id,
        product_name="AI 사주 심층 리포트",
        amount=1900,
        saju_key=saju_key,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # 2) Kakao Ready 호출
    ready_res = kakao_ready(
        order_id=order.id,
        amount=order.amount,
        user_email=user.email or "",
        user_phone=user.phone or ""
    )

    # 3) tid 저장
    order.kakao_tid = ready_res["tid"]
    db.commit()

    return JSONResponse({
        "tid": ready_res["tid"],
        "redirect_url": ready_res["next_redirect_pc_url"]
    })

################################################################################
# 2) 카카오 Approve 콜백
################################################################################
@router.get("/approve", response_class=RedirectResponse)
async def kakao_approve_endpoint(
    pg_token: str,
    order_id: int,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order or order.status != "pending":
        raise HTTPException(status_code=404, detail="유효하지 않은 주문입니다.")

    # 1) Approve 요청
    approve_res = kakao_approve(order.kakao_tid, pg_token)
    if approve_res.get("code") != 0:
        raise HTTPException(status_code=400, detail="결제 승인 실패")

    # 2) 주문 상태 변경
    order.status = "paid"
    order.paid_at = datetime.utcnow()
    db.commit()

    # 3) 심층 AI 리포트 생성 Celery Task
    generate_full_report.delay(order_id=order.id, saju_key=order.saju_key)

    # 4) 프론트 Processing 페이지로
    return RedirectResponse(f"/order/processing/{order.id}")

################################################################################
# 3) 마이페이지 구매내역
################################################################################
@router.get("/mypage", response_class=HTMLResponse)
async def mypage_orders(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == user.id, Order.status == "paid")
        .order_by(Order.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("mypage/orders.html", {
        "request": request,
        "orders": orders
    })