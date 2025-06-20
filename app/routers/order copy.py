"""주문 / 결제 / 구매내역 Router 완전판"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, SajuAnalysisCache, Product, User
from app.template import templates
from app.dependencies import get_current_user
from app.payments.kakaopay import kakao_ready, kakao_approve
from app.tasks import generate_full_report

router = APIRouter(prefix="/order", tags=["Order"])

################################################################################
# 1) 주문 생성 (카카오 ready 반환)
################################################################################
@router.post("/create")
async def create_order(
    request: Request,
    payload: dict = Body(...),  # saju_key 포함
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 생성 및 카카오페이 결제 준비"""
    saju_key = payload.get("saju_key")
    if not saju_key:
        raise HTTPException(status_code=400, detail="사주 정보가 필요합니다.")
    
    # 이미 같은 사주 구매한 적 있으면 차단
    existing_order = (
        db.query(Order)
        .filter(
            Order.user_id == user.id,
            Order.saju_key == saju_key,
            Order.status == "paid"
        )
        .first()
    )
    if existing_order:
        raise HTTPException(
            status_code=400,
            detail="이미 결제한 리포트입니다. 마이페이지에서 확인하세요."
        )

    # 기본 상품 확인 (또는 생성)
    product = db.query(Product).filter(Product.code == "premium_saju").first()
    if not product:
        product = Product(
            name="AI 심층 사주 리포트",
            description="고서 원문 + AI 심층 분석 15쪽 완전판",
            price=1900,
            code="premium_saju",
            is_active=True
        )
        db.add(product)
        db.flush()

    # 주문 생성 (kakao_tid는 나중에 업데이트)
    order = Order(
        user_id=user.id,
        product_id=product.id,
        amount=product.price,
        saju_key=saju_key,
        status="pending",
        kakao_tid="temp",  # 임시값 (NOT NULL 제약 때문)
        created_at=datetime.utcnow()
    )
    db.add(order)
    db.flush()  # order.id 생성

    # 카카오페이 결제 준비
    try:
        ready_result = kakao_ready(
            order_id=order.id,
            amount=order.amount,
            user_email=user.email or "",
            user_phone=getattr(user, 'phone', '') or ""
        )
        
        # 실제 tid로 업데이트
        order.kakao_tid = ready_result["tid"]
        db.commit()
        
        return JSONResponse({
            "tid": ready_result["tid"],
            "redirect_url": ready_result["next_redirect_pc_url"]
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"결제 준비 실패: {str(e)}")

################################################################################
# 2) 카카오 Approve 콜백
################################################################################
@router.get("/approve")
async def kakao_approve_callback(
    pg_token: str = Query(...),
    order_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """카카오페이 결제 승인 처리"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order or order.status != "pending":
        raise HTTPException(status_code=404, detail="유효하지 않은 주문입니다.")

    try:
        # 카카오페이 결제 승인
        approve_result = kakao_approve(order.kakao_tid, pg_token)
        
        # 주문 상태 업데이트
        order.status = "paid"
        db.commit()
        
        # 백그라운드에서 리포트 생성 시작
        generate_full_report.delay(order_id=order.id, saju_key=order.saju_key)
        
        # 처리 중 페이지로 리다이렉트
        return RedirectResponse(f"/order/processing/{order.id}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"결제 승인 실패: {str(e)}")

################################################################################
# 3) 결제 취소/실패 처리
################################################################################
@router.get("/cancel")
async def payment_cancel(order_id: int = Query(...)):
    """결제 취소"""
    return RedirectResponse("/saju/page2?message=결제가 취소되었습니다.")

@router.get("/fail")
async def payment_fail(order_id: int = Query(...)):
    """결제 실패"""
    return RedirectResponse("/saju/page2?error=결제에 실패했습니다.")

################################################################################
# 4) 처리 중 페이지
################################################################################
@router.get("/processing/{order_id}", response_class=HTMLResponse)
async def processing_page(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """결제 완료 후 리포트 생성 대기 페이지"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("order/processing.html", {
        "request": request,
        "order": order,
        "order_id": order_id
    })

################################################################################
# 5) 주문 상태 확인 API
################################################################################
@router.get("/status/{order_id}")
async def check_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 상태 확인 (AJAX)"""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    return JSONResponse({
        "status": order.status,
        "report_ready": bool(order.report_pdf),
        "report_url": order.report_pdf if order.report_pdf else None
    })

################################################################################
# 6) 마이페이지 구매내역
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
        .filter(Order.user_id == user.id, Order.status == "paid")
        .order_by(Order.created_at.desc())
        .all()
    )
    
    return templates.TemplateResponse("mypage/orders.html", {
        "request": request,
        "orders": orders
    })

################################################################################
# 7) 연락처 저장 (선택사항)
################################################################################
@router.post("/save-contact")
async def save_contact(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """결제용 이메일/전화번호 저장"""
    email = payload.get("email")
    phone = payload.get("phone")
    
    # 가장 최근 pending 주문 찾기
    order = (
        db.query(Order)
        .filter(Order.user_id == user.id, Order.status == "pending")
        .order_by(Order.created_at.desc())
        .first()
    )
    
    if order:
        if email:
            order.pdf_send_email = email
        if phone:
            order.pdf_send_phone = phone
        db.commit()
    
    return JSONResponse({"success": True})