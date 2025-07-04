"""
구독 라우터 - 정기구독 관리
- 구독 플랜 조회
- 구독 신청/해지/일시정지
- 구독 혜택 확인
"""

from fastapi import APIRouter, Request, Depends, Query, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from typing import Optional, Dict, Any
import logging

from app.database import get_db
from app.models import User, Subscription, Order
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.services.subscription_service import SubscriptionService
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["Subscription"])

################################################################################
# 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/plans", response_class=HTMLResponse)
async def subscription_plans(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional)
):
    """구독 플랜 목록 페이지"""
    try:
        # 구독 플랜 정보
        plans = SubscriptionService.get_subscription_plans()
        
        # 사용자 현재 구독 정보
        current_subscription = None
        if user:
            current_subscription = SubscriptionService.get_user_subscription(user.id, db)
        
        return templates.TemplateResponse("subscription/plans.html", {
            "request": request,
            "plans": plans,
            "user": user,
            "current_subscription": current_subscription
        })
        
    except Exception as e:
        logger.error(f"구독 플랜 페이지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="구독 플랜을 불러오는 중 오류가 발생했습니다.")

@router.get("/dashboard", response_class=HTMLResponse)
async def subscription_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 대시보드 페이지"""
    try:
        # 구독 정보 조회
        subscription = SubscriptionService.get_user_subscription(user.id, db)
        
        if not subscription:
            return RedirectResponse(url="/subscription/plans")
        
        # 구독 혜택 정보
        benefits = SubscriptionService.get_subscription_benefits(user.id, db)
        
        # 구독 내역 조회
        subscription_orders = db.query(Order).filter(
            and_(
                Order.user_id == user.id,
                Order.subscription_id == subscription.id
            )
        ).order_by(desc(Order.created_at)).limit(10).all()
        
        return templates.TemplateResponse("subscription/dashboard.html", {
            "request": request,
            "user": user,
            "subscription": subscription,
            "benefits": benefits,
            "orders": subscription_orders
        })
        
    except Exception as e:
        logger.error(f"구독 대시보드 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="구독 대시보드를 불러오는 중 오류가 발생했습니다.")

@router.get("/manage", response_class=HTMLResponse)
async def subscription_manage(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 관리 페이지"""
    try:
        # 구독 정보 조회
        subscription = SubscriptionService.get_user_subscription(user.id, db)
        
        if not subscription:
            return RedirectResponse(url="/subscription/plans")
        
        # 일시정지된 구독도 조회
        paused_subscription = db.query(Subscription).filter(
            and_(
                Subscription.user_id == user.id,
                Subscription.status == "paused"
            )
        ).first()
        
        return templates.TemplateResponse("subscription/manage.html", {
            "request": request,
            "user": user,
            "subscription": subscription,
            "paused_subscription": paused_subscription
        })
        
    except Exception as e:
        logger.error(f"구독 관리 페이지 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="구독 관리 페이지를 불러오는 중 오류가 발생했습니다.")

################################################################################
# API 라우터 (JSON 응답)
################################################################################

@router.get("/api/v1/plans")
async def api_get_plans(db: Session = Depends(get_db)):
    """구독 플랜 목록 API"""
    try:
        plans = SubscriptionService.get_subscription_plans()
        
        return JSONResponse({
            "success": True,
            "data": {
                "plans": plans
            }
        })
        
    except Exception as e:
        logger.error(f"구독 플랜 API 실패: {e}")
        return JSONResponse({
            "success": False,
            "error": "구독 플랜을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/subscribe")
async def api_create_subscription(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 신청 API"""
    try:
        plan_type = payload.get("plan_type")
        
        if not plan_type:
            return JSONResponse({
                "success": False,
                "error": "구독 플랜을 선택해주세요."
            }, status_code=400)
        
        # 구독 생성
        success, message, result = SubscriptionService.create_subscription(
            user_id=user.id,
            plan_type=plan_type,
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
        logger.error(f"구독 신청 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구독 신청 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/cancel")
async def api_cancel_subscription(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 해지 API"""
    try:
        # 구독 해지
        success, message, result = SubscriptionService.cancel_subscription(
            user_id=user.id,
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
        logger.error(f"구독 해지 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구독 해지 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/pause")
async def api_pause_subscription(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 일시정지 API"""
    try:
        # 구독 일시정지
        success, message, result = SubscriptionService.pause_subscription(
            user_id=user.id,
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
        logger.error(f"구독 일시정지 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구독 일시정지 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/resume")
async def api_resume_subscription(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 재개 API"""
    try:
        # 구독 재개
        success, message, result = SubscriptionService.resume_subscription(
            user_id=user.id,
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
        logger.error(f"구독 재개 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구독 재개 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/benefits")
async def api_get_benefits(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 혜택 조회 API"""
    try:
        benefits = SubscriptionService.get_subscription_benefits(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": benefits
        })
        
    except Exception as e:
        logger.error(f"구독 혜택 조회 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "구독 혜택을 불러오는 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/calculate-discount")
async def api_calculate_discount(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """구독 할인 계산 API"""
    try:
        original_price = payload.get("original_price", 0)
        
        if original_price <= 0:
            return JSONResponse({
                "success": False,
                "error": "유효한 가격을 입력해주세요."
            }, status_code=400)
        
        # 할인 적용
        discounted_price, discount_rate = SubscriptionService.apply_subscription_discount(
            original_price=original_price,
            user_id=user.id,
            db=db
        )
        
        return JSONResponse({
            "success": True,
            "data": {
                "original_price": original_price,
                "discounted_price": discounted_price,
                "discount_rate": discount_rate,
                "discount_amount": original_price - discounted_price
            }
        })
        
    except Exception as e:
        logger.error(f"구독 할인 계산 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "할인 계산 중 오류가 발생했습니다."
        }, status_code=500) 