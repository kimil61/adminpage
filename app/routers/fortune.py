"""
행운 포인트 관리 라우터 - 트랜잭션 안전성 보장
- 포인트 대시보드 (SSR)
- 충전 페이지 (패키지 목록)
- 거래 내역 (페이징)
- API 엔드포인트 (JSON, CSRF 보호)
"""

from fastapi import APIRouter, Request, Depends, Query, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
import secrets

from app.database import get_db
from app.models import User, UserFortunePoint, FortuneTransaction, FortunePackage
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.services.fortune_service import FortuneService
from app.services.payment_service import PaymentService
from app.exceptions import BadRequestError, NotFoundError, InternalServerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fortune", tags=["Fortune"])

################################################################################
# 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/", response_class=HTMLResponse)
async def fortune_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """포인트 대시보드 (SSR)"""
    try:
        # 사용자 포인트 정보 조회
        fortune_info = FortuneService.get_user_fortune_info(user.id, db)
        
        # 통계 정보 조회
        statistics = FortuneService.get_fortune_statistics(user.id, db)
        
        # 만료 예정 포인트 조회
        expiring_points = FortuneService.check_expiring_points(user.id, db)
        
        # CSRF 토큰 생성
        csrf_token = request.session.get("csrf_token")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(16)
            request.session["csrf_token"] = csrf_token
        
        return templates.TemplateResponse("fortune/dashboard.html", {
            "request": request,
            "user": user,
            "fortune_info": fortune_info,
            "statistics": statistics,
            "expiring_points": expiring_points,
            "csrf_token": csrf_token
        })
        
    except Exception as e:
        logger.error(f"포인트 대시보드 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="포인트 정보를 불러오는 중 오류가 발생했습니다.")

@router.get("/charge", response_class=HTMLResponse)
async def fortune_charge(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """충전 페이지 (패키지 목록)"""
    try:
        # 충전 패키지 목록 조회
        packages = FortuneService.get_charge_packages(db)
        
        # 사용자 포인트 정보
        fortune_info = FortuneService.get_user_fortune_info(user.id, db)
        
        # CSRF 토큰 생성
        csrf_token = request.session.get("csrf_token")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(16)
            request.session["csrf_token"] = csrf_token
        
        return templates.TemplateResponse("fortune/charge.html", {
            "request": request,
            "user": user,
            "packages": packages,
            "fortune_info": fortune_info,
            "csrf_token": csrf_token
        })
        
    except Exception as e:
        logger.error(f"충전 페이지 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="충전 패키지를 불러오는 중 오류가 발생했습니다.")

@router.get("/history", response_class=HTMLResponse)
async def fortune_history(
    request: Request,
    page: int = Query(1, ge=1),
    transaction_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """포인트 거래 내역 (페이징)"""
    try:
        # 거래 내역 조회
        result = FortuneService.get_transaction_history(
            user_id=user.id,
            page=page,
            per_page=20,
            transaction_type=transaction_type,
            db=db
        )
        
        # 사용자 포인트 정보
        fortune_info = FortuneService.get_user_fortune_info(user.id, db)
        
        return templates.TemplateResponse("fortune/history.html", {
            "request": request,
            "user": user,
            "transactions": result["transactions"],
            "pagination": result["pagination"],
            "fortune_info": fortune_info,
            "transaction_type": transaction_type
        })
        
    except Exception as e:
        logger.error(f"거래 내역 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="거래 내역을 불러오는 중 오류가 발생했습니다.")

################################################################################
# API 라우터 (JSON, CSRF 보호)
################################################################################

@router.get("/api/v1/balance")
async def api_get_balance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """잔액 조회 API"""
    try:
        balance = PaymentService.get_user_point_balance(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": {
                "balance": balance,
                "formatted_balance": f"{balance:,}P"
            }
        })
        
    except Exception as e:
        logger.error(f"잔액 조회 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "잔액 조회 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/charge")
async def api_charge_points(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """패키지 충전 (idempotency_key, 카카오페이)"""
    try:
        package_id = payload.get("package_id")
        idempotency_key = payload.get("idempotency_key")
        csrf_token = payload.get("csrf_token")
        
        # CSRF 토큰 검증
        session_csrf = request.session.get("csrf_token")
        if not csrf_token or not session_csrf or csrf_token != session_csrf:
            return JSONResponse({
                "success": False,
                "error": "보안 토큰이 유효하지 않습니다."
            }, status_code=403)
        
        if not package_id:
            return JSONResponse({
                "success": False,
                "error": "패키지 ID가 필요합니다."
            }, status_code=400)
        
        # Idempotency 체크
        if idempotency_key:
            existing_result = PaymentService.check_idempotency(db, idempotency_key, "point_charge")
            if existing_result:
                return JSONResponse({
                    "success": True,
                    "data": existing_result,
                    "idempotency_hit": True
                })
        
        # 포인트 충전 준비
        result = await PaymentService.prepare_point_charge(
            package_id=package_id,
            user_id=user.id,
            idempotency_key=idempotency_key,
            db=db
        )
        
        # Idempotency 결과 저장
        if idempotency_key:
            PaymentService.store_idempotency_result(
                db, idempotency_key, "point_charge", result
            )
        
        return JSONResponse({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"포인트 충전 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "포인트 충전 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/use")
async def api_use_points(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """포인트 사용 처리 (내부 API, CSRF 필수)"""
    try:
        amount = payload.get("amount")
        source = payload.get("source")
        reference_id = payload.get("reference_id")
        csrf_token = payload.get("csrf_token")
        
        # CSRF 토큰 검증
        session_csrf = request.session.get("csrf_token")
        if not csrf_token or not session_csrf or csrf_token != session_csrf:
            return JSONResponse({
                "success": False,
                "error": "보안 토큰이 유효하지 않습니다."
            }, status_code=403)
        
        if not all([amount, source, reference_id]):
            return JSONResponse({
                "success": False,
                "error": "필수 파라미터가 누락되었습니다."
            }, status_code=400)
        
        # 포인트 사용 처리
        success = PaymentService.process_point_usage(
            user_id=user.id,
            amount=amount,
            source=source,
            reference_id=reference_id,
            db=db
        )
        
        if success:
            # 업데이트된 잔액 조회
            new_balance = PaymentService.get_user_point_balance(user.id, db)
            
            return JSONResponse({
                "success": True,
                "data": {
                    "amount_used": amount,
                    "new_balance": new_balance,
                    "formatted_balance": f"{new_balance:,}P"
                }
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "포인트 사용 처리에 실패했습니다."
            }, status_code=400)
            
    except BadRequestError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"포인트 사용 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "포인트 사용 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/transactions")
async def api_get_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    transaction_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """거래 내역 API (페이징)"""
    try:
        result = FortuneService.get_transaction_history(
            user_id=user.id,
            page=page,
            per_page=per_page,
            transaction_type=transaction_type,
            db=db
        )
        
        # 거래 내역 직렬화
        transactions_data = []
        for transaction in result["transactions"]:
            transactions_data.append({
                "id": transaction.id,
                "transaction_type": transaction.transaction_type,
                "amount": transaction.amount,
                "balance_after": transaction.balance_after,
                "source": transaction.source,
                "reference_id": transaction.reference_id,
                "description": transaction.description,
                "expires_at": transaction.expires_at.isoformat() if transaction.expires_at else None,
                "created_at": transaction.created_at.isoformat() if transaction.created_at else None
            })
        
        return JSONResponse({
            "success": True,
            "data": {
                "transactions": transactions_data,
                "pagination": result["pagination"]
            }
        })
        
    except Exception as e:
        logger.error(f"거래 내역 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "거래 내역을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/statistics")
async def api_get_statistics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """포인트 통계 API"""
    try:
        statistics = FortuneService.get_fortune_statistics(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": statistics
        })
        
    except Exception as e:
        logger.error(f"포인트 통계 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "포인트 통계를 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/expiring")
async def api_get_expiring_points(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """만료 예정 포인트 API"""
    try:
        expiring_points = FortuneService.check_expiring_points(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": {
                "expiring_points": expiring_points,
                "count": len(expiring_points)
            }
        })
        
    except Exception as e:
        logger.error(f"만료 예정 포인트 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "만료 예정 포인트를 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

################################################################################
# 유틸리티 함수들
################################################################################

def format_points(points: int) -> str:
    """포인트 포맷팅"""
    return f"{points:,}P"

def get_transaction_type_display(transaction_type: str) -> str:
    """거래 타입 표시명"""
    type_map = {
        "earn": "적립",
        "spend": "사용",
        "refund": "환불",
        "expire": "만료"
    }
    return type_map.get(transaction_type, transaction_type)

def get_source_display(source: str) -> str:
    """거래 소스 표시명"""
    source_map = {
        "package_charge": "패키지 충전",
        "product_purchase": "상품 구매",
        "daily_bonus": "일일 보너스",
        "referral": "추천 보상",
        "subscription": "구독 혜택"
    }
    return source_map.get(source, source) 