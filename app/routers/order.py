"""주문 / 결제 Router - 간소화 버전"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query, Header
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product, User
from app.template import templates
from app.dependencies import get_current_user
import logging
from celery.result import AsyncResult


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
    csrf_token: str = Header(None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 생성 - 일단 간단하게 성공 응답만"""
    try:
        logger.info(f"주문 생성 요청: user_id={user.id}, payload={payload}")
        
        # CSRF 검증
        session_token = request.session.get("csrf_token") if hasattr(request, "session") else None
        if not csrf_token or csrf_token != session_token:
            raise HTTPException(status_code=403, detail="CSRF token invalid or missing.")
        
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


# app/routers/order.py의 결제 완료 부분에 추가

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
        # 카카오페이 결제 승인 (나중에 구현)
        # approve_result = kakao_approve(order.kakao_tid, pg_token)
        
        # 주문 상태 업데이트
        order.status = "paid"
        db.commit()
        
        # 🎯 여기서 Celery 태스크 호출!
        from app.tasks import generate_full_report
        task = generate_full_report.delay(order_id=order.id, saju_key=order.saju_key)
        
        print(f"✅ 리포트 생성 태스크 시작: {task.id}")
        
        # 처리 중 페이지로 리다이렉트
        return RedirectResponse(f"/order/processing/{order.id}")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"결제 승인 실패: {str(e)}")
    

@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """태스크 진행 상황 확인"""
    try:
        from app.celery_app import celery_app
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state == 'pending':
            response = {
                'state': result.state,
                'current': 0,
                'total': 1,
                'status': '대기 중...'
            }
        elif result.state == 'progress':
            response = {
                'state': result.state,
                'current': result.info.get('current', 0),
                'total': result.info.get('total', 1),
                'status': result.info.get('status', '')
            }
        elif result.state == 'success':
            response = {
                'state': result.state,
                'current': 100,
                'total': 100,
                'status': '완료!',
                'result': result.info
            }
        else:  # FAILURE
            response = {
                'state': result.state,
                'current': 1,
                'total': 1,
                'status': f'오류: {str(result.info)}'
            }
        return response
    except Exception as e:
        return {'state': 'FAILURE', 'status': f'상태 확인 오류: {str(e)}'}

# app/routers/order.py에 임시 테스트 엔드포인트 추가

@router.get("/test-report/{order_id}")
async def test_report_generation(
    order_id: int,
    db: Session = Depends(get_db)
):
    """리포트 생성 테스트"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    from app.tasks import generate_full_report
    task = generate_full_report.delay(order_id=order.id, saju_key=order.saju_key)
    
    return {"task_id": task.id, "message": "리포트 생성 시작"}