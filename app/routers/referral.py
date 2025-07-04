"""
추천인 라우터 - 추천인 코드 및 보상 관리
- 추천인 코드 생성 및 관리
- 추천인 보상 시스템
- 추천인 통계 및 대시보드
- 추천인 마케팅 도구
"""

from fastapi import APIRouter, Request, Depends, Query, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging

from app.database import get_db
from app.models import User
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.services.referral_service import ReferralService
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/referral", tags=["Referral"])

################################################################################
# 웹페이지 라우터 (SSR HTML)
################################################################################

@router.get("/dashboard", response_class=HTMLResponse)
async def referral_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 대시보드 페이지"""
    try:
        # 추천인 정보 조회
        referral_info = ReferralService.get_user_referral_info(user.id, db)
        
        # 추천인 통계 조회
        statistics = ReferralService.get_referral_statistics(user.id, db)
        
        return templates.TemplateResponse("referral/dashboard.html", {
            "request": request,
            "user": user,
            "referral_info": referral_info,
            "statistics": statistics
        })
        
    except Exception as e:
        logger.error(f"추천인 대시보드 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="추천인 대시보드를 불러오는 중 오류가 발생했습니다.")

@router.get("/rewards", response_class=HTMLResponse)
async def referral_rewards(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 보상 내역 페이지"""
    try:
        # 보상 내역 조회
        rewards_data = ReferralService.get_referral_rewards(
            user_id=user.id,
            db=db,
            page=page,
            per_page=10
        )
        
        return templates.TemplateResponse("referral/rewards.html", {
            "request": request,
            "user": user,
            "rewards": rewards_data["rewards"],
            "pagination": rewards_data["pagination"]
        })
        
    except Exception as e:
        logger.error(f"추천인 보상 내역 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="추천인 보상 내역을 불러오는 중 오류가 발생했습니다.")

@router.get("/marketing", response_class=HTMLResponse)
async def referral_marketing(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 마케팅 도구 페이지"""
    try:
        # 추천인 정보 조회
        referral_info = ReferralService.get_user_referral_info(user.id, db)
        
        return templates.TemplateResponse("referral/marketing.html", {
            "request": request,
            "user": user,
            "referral_info": referral_info
        })
        
    except Exception as e:
        logger.error(f"추천인 마케팅 도구 조회 실패: user_id={user.id}, error={e}")
        raise HTTPException(status_code=500, detail="추천인 마케팅 도구를 불러오는 중 오류가 발생했습니다.")

################################################################################
# API 라우터 (JSON 응답)
################################################################################

@router.post("/api/v1/generate-code")
async def api_generate_referral_code(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 코드 생성 API"""
    try:
        # 추천인 코드 생성
        code = ReferralService.generate_referral_code(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": {
                "referral_code": code
            },
            "message": "추천인 코드가 생성되었습니다."
        })
        
    except Exception as e:
        logger.error(f"추천인 코드 생성 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 코드 생성 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/info")
async def api_get_referral_info(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 정보 조회 API"""
    try:
        # 추천인 정보 조회
        referral_info = ReferralService.get_user_referral_info(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": referral_info
        })
        
    except Exception as e:
        logger.error(f"추천인 정보 조회 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 정보를 조회할 수 없습니다."
        }, status_code=500)

@router.get("/api/v1/statistics")
async def api_get_referral_statistics(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 통계 조회 API"""
    try:
        # 추천인 통계 조회
        statistics = ReferralService.get_referral_statistics(user.id, db)
        
        return JSONResponse({
            "success": True,
            "data": statistics
        })
        
    except Exception as e:
        logger.error(f"추천인 통계 조회 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 통계를 조회할 수 없습니다."
        }, status_code=500)

@router.post("/api/v1/deactivate")
async def api_deactivate_referral_code(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 코드 비활성화 API"""
    try:
        # 추천인 코드 비활성화
        success, message = ReferralService.deactivate_referral_code(user.id, db)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"추천인 코드 비활성화 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 코드 비활성화 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/reactivate")
async def api_reactivate_referral_code(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """추천인 코드 재활성화 API"""
    try:
        # 추천인 코드 재활성화
        success, message = ReferralService.reactivate_referral_code(user.id, db)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": message
            })
        else:
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)
            
    except Exception as e:
        logger.error(f"추천인 코드 재활성화 API 실패: user_id={user.id}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 코드 재활성화 중 오류가 발생했습니다."
        }, status_code=500)

@router.get("/api/v1/validate/{code}")
async def api_validate_referral_code(
    request: Request,
    code: str,
    db: Session = Depends(get_db)
):
    """추천인 코드 유효성 검증 API"""
    try:
        # 추천인 코드 유효성 확인
        referral = ReferralService.get_referral_by_code(code, db)
        
        if referral:
            return JSONResponse({
                "success": True,
                "data": {
                    "is_valid": True,
                    "referrer_id": referral.user_id
                }
            })
        else:
            return JSONResponse({
                "success": True,
                "data": {
                    "is_valid": False
                }
            })
            
    except Exception as e:
        logger.error(f"추천인 코드 유효성 검증 API 실패: code={code}, error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 코드 유효성 검증 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/process-signup")
async def api_process_referral_signup(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """추천인 가입 처리 API"""
    try:
        referral_code = payload.get("referral_code")
        new_user_id = payload.get("new_user_id")
        
        if not all([referral_code, new_user_id]):
            return JSONResponse({
                "success": False,
                "error": "필수 항목을 모두 입력해주세요."
            }, status_code=400)
        
        # 추천인 가입 처리
        success, message, result = ReferralService.process_referral_signup(
            referral_code=referral_code,
            new_user_id=new_user_id,
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
        logger.error(f"추천인 가입 처리 API 실패: error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 가입 처리 중 오류가 발생했습니다."
        }, status_code=500)

@router.post("/api/v1/process-purchase")
async def api_process_referral_purchase(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """추천인 구매 보상 처리 API"""
    try:
        referred_user_id = payload.get("referred_user_id")
        purchase_amount = payload.get("purchase_amount")
        
        if not all([referred_user_id, purchase_amount]):
            return JSONResponse({
                "success": False,
                "error": "필수 항목을 모두 입력해주세요."
            }, status_code=400)
        
        # 추천인 구매 보상 처리
        success, message, result = ReferralService.process_referral_purchase(
            referred_user_id=referred_user_id,
            purchase_amount=purchase_amount,
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
        logger.error(f"추천인 구매 보상 처리 API 실패: error={e}")
        return JSONResponse({
            "success": False,
            "error": "추천인 구매 보상 처리 중 오류가 발생했습니다."
        }, status_code=500) 