"""
행운 포인트 관리 라우터 - 트랜잭션 안전성 보장
Week 1: 핵심 인프라 - 포인트 시스템 완전 구현
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.fortune_service import FortuneService, get_fortune_service
from app.services.payment_service import PaymentService, get_payment_service
from app.utils.csrf import generate_csrf_token, validate_csrf_token
from app.utils.error_handlers import ValidationError, InsufficientPointsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fortune", tags=["fortune"])

# 의존성
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """현재 로그인한 사용자 조회"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")
    
    return user

################################################################################
# 💰 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/", response_class=HTMLResponse)
async def fortune_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    """포인트 대시보드"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        # 포인트 잔액 및 통계
        balance_info = fortune_service.get_user_balance(current_user.id)
        
        # 최근 거래 내역 (최근 5개)
        recent_transactions = fortune_service.get_transactions(
            user_id=current_user.id,
            page=1,
            per_page=5
        )
        
        # 만료 예정 포인트
        expiring_points = fortune_service.get_expiring_points(current_user.id, days=30)
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "fortune/dashboard.html",
            {
                "request": request,
                "current_user": current_user,
                "balance_info": balance_info,
                "recent_transactions": recent_transactions['transactions'],
                "expiring_points": expiring_points,
                "csrf_token": csrf_token
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fortune dashboard error: {e}")
        raise HTTPException(status_code=500, detail="포인트 대시보드를 불러오는 중 오류가 발생했습니다.")

@router.get("/charge", response_class=HTMLResponse)
async def fortune_charge(
    request: Request,
    db: Session = Depends(get_db)
):
    """포인트 충전 페이지"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        # 충전 패키지 목록
        packages = fortune_service.get_packages(current_user.id)
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "fortune/charge.html",
            {
                "request": request,
                "current_user": current_user,
                "packages": packages,
                "csrf_token": csrf_token
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fortune charge error: {e}")
        raise HTTPException(status_code=500, detail="충전 페이지를 불러오는 중 오류가 발생했습니다.")

@router.get("/history", response_class=HTMLResponse)
async def fortune_history(
    request: Request,
    page: int = Query(1, ge=1),
    transaction_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """포인트 거래 내역 페이지"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        # 거래 내역 조회
        transactions_data = fortune_service.get_transactions(
            user_id=current_user.id,
            page=page,
            per_page=20,
            transaction_type=transaction_type
        )
        
        # CSRF 토큰 생성
        csrf_token = generate_csrf_token(request)
        
        return request.app.state.templates.TemplateResponse(
            "fortune/history.html",
            {
                "request": request,
                "current_user": current_user,
                "transactions": transactions_data['transactions'],
                "pagination": transactions_data['pagination'],
                "transaction_type": transaction_type,
                "csrf_token": csrf_token
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fortune history error: {e}")
        raise HTTPException(status_code=500, detail="거래 내역을 불러오는 중 오류가 발생했습니다.")

################################################################################
# 🔌 JSON API 라우터
################################################################################

@router.get("/api/v1/balance")
async def api_get_balance(
    request: Request,
    db: Session = Depends(get_db)
):
    """포인트 잔액 조회 API"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        balance_info = fortune_service.get_user_balance(current_user.id)
        
        return {
            "success": True,
            "data": balance_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API balance error: {e}")
        raise HTTPException(status_code=500, detail="잔액 조회 중 오류가 발생했습니다.")

@router.post("/api/v1/charge")
async def api_prepare_charge(
    request: Request,
    package_id: int = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """포인트 충전 준비 API"""
    try:
        # CSRF 토큰 검증
        validate_csrf_token(request, csrf_token)
        
        current_user = get_current_user(request, db)
        payment_service = PaymentService(db)
        
        # 멱등성 키 생성
        import hashlib
        import time
        idempotency_key = hashlib.sha256(
            f"{current_user.id}:{package_id}:{int(time.time() / 60)}".encode()
        ).hexdigest()
        
        # 포인트 충전 준비
        result = payment_service.prepare_point_charge(
            package_id=package_id,
            user_id=current_user.id,
            idempotency_key=idempotency_key
        )
        
        return {
            "success": True,
            "data": result,
            "message": "충전 페이지로 이동합니다."
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API charge preparation error: {e}")
        raise HTTPException(status_code=500, detail="충전 준비 중 오류가 발생했습니다.")

@router.post("/api/v1/use")
async def api_use_points(
    request: Request,
    amount: int = Form(...),
    source: str = Form(...),
    reference_id: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """포인트 사용 API (내부 API, CSRF 필수)"""
    try:
        # CSRF 토큰 검증
        validate_csrf_token(request, csrf_token)
        
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        # 포인트 사용
        success = fortune_service.use_points_safely(
            user_id=current_user.id,
            amount=amount,
            source=source,
            reference_id=reference_id
        )
        
        if success:
            return {
                "success": True,
                "message": "포인트가 사용되었습니다."
            }
        else:
            raise HTTPException(status_code=400, detail="포인트 사용에 실패했습니다.")
        
    except InsufficientPointsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API point usage error: {e}")
        raise HTTPException(status_code=500, detail="포인트 사용 중 오류가 발생했습니다.")

@router.get("/api/v1/transactions")
async def api_get_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    transaction_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """거래 내역 조회 API (페이징)"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        transactions_data = fortune_service.get_transactions(
            user_id=current_user.id,
            page=page,
            per_page=per_page,
            transaction_type=transaction_type
        )
        
        return {
            "success": True,
            "data": transactions_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API transactions error: {e}")
        raise HTTPException(status_code=500, detail="거래 내역 조회 중 오류가 발생했습니다.")

@router.get("/api/v1/packages")
async def api_get_packages(
    request: Request,
    db: Session = Depends(get_db)
):
    """충전 패키지 목록 API"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        packages = fortune_service.get_packages(current_user.id)
        
        return {
            "success": True,
            "data": packages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API packages error: {e}")
        raise HTTPException(status_code=500, detail="패키지 목록 조회 중 오류가 발생했습니다.")

@router.get("/api/v1/expiring")
async def api_get_expiring_points(
    request: Request,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """만료 예정 포인트 조회 API"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        expiring_points = fortune_service.get_expiring_points(current_user.id, days=days)
        
        return {
            "success": True,
            "data": expiring_points
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API expiring points error: {e}")
        raise HTTPException(status_code=500, detail="만료 예정 포인트 조회 중 오류가 발생했습니다.")

################################################################################
# 🔄 결제 완료 처리 (Webhook 대응)
################################################################################

@router.post("/api/v1/charge/complete")
async def api_charge_completion(
    request: Request,
    order_id: int = Form(...),
    package_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """포인트 충전 완료 처리 API"""
    try:
        current_user = get_current_user(request, db)
        fortune_service = FortuneService(db)
        
        # 패키지 구매 완료 처리
        success = fortune_service.process_package_purchase(
            user_id=current_user.id,
            package_id=package_id,
            order_id=order_id
        )
        
        if success:
            return {
                "success": True,
                "message": "포인트 충전이 완료되었습니다."
            }
        else:
            raise HTTPException(status_code=400, detail="포인트 충전 처리에 실패했습니다.")
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API charge completion error: {e}")
        raise HTTPException(status_code=500, detail="포인트 충전 완료 처리 중 오류가 발생했습니다.") 