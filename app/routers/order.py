# app/routers/order.py - 카카오페이 결제 플로우 버전

"""주문 / 결제 / 구매내역 Router - 카카오페이 연동 버전"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Body, Query, Header, HTTPException
from app.exceptions import (
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    InternalServerError,
)
from app.utils import (
    generate_live_report_for_user,
    generate_live_report_from_db,
    get_flashed_messages
)
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Order, Product, User, SajuAnalysisCache, SajuUser
from app.template import templates
from app.dependencies import get_current_user, get_current_user_optional
from app.payments.kakaopay import (
    kakao_ready, kakao_approve, verify_payment, 
    KakaoPayError, get_payment_method_name, is_mobile_user_agent
)
import logging
import os
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 개발 모드 설정 읽기
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
SKIP_PAYMENT = os.getenv("SKIP_PAYMENT", "false").lower() == "true"


router = APIRouter(prefix="/order", tags=["Order"])

################################################################################
# 1) 주문 생성 - 카카오페이 결제창 호출
################################################################################
@router.post("/create")
async def create_order(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 생성 후 카카오페이 결제창 URL 반환"""
    try:
        saju_key = payload.get("saju_key")
        if not saju_key:
            logger.warning(f"Missing saju_key: user_id={user.id}")
            raise BadRequestError("사주 정보가 필요합니다.")
        
        # 중복 구매 체크
        existing = db.query(Order).filter(
            Order.user_id == user.id,
            Order.saju_key == saju_key,
            Order.status == "paid"
        ).first()
        if existing:
            logger.warning(
                f"Duplicate purchase attempt: user_id={user.id}, saju_key={saju_key}"
            )
            raise BadRequestError("이미 구매한 리포트입니다.")
        
        # 진행 중인 주문이 있는지 체크 (30분 이내)
        recent_pending = db.query(Order).filter(
            Order.user_id == user.id,
            Order.saju_key == saju_key,
            Order.status == "pending",
            Order.created_at > datetime.now() - timedelta(minutes=30)
        ).first()
        
        if recent_pending:
            # 기존 pending 주문이 있으면 삭제하고 새로 생성
            db.delete(recent_pending)
            db.commit()
        
        # 상품 조회/생성
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
            db.refresh(product)
        
        # 임시 주문 생성 (status=pending)
        order = Order(
            user_id=user.id,
            product_id=product.id,
            amount=product.price,
            saju_key=saju_key,
            status="pending",  # 결제 대기 상태
            report_status="pending",
            kakao_tid=""  # 아직 TID 없음
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        
        ##################################################
        # 개발 모드 또는 결제 생략 설정인 경우
        if DEV_MODE and SKIP_PAYMENT:
            logger.info(f"🔧 개발 모드: 결제 건너뛰기 - order_id={order.id}")
            
            # 바로 결제 완료 상태로 변경
            order.status = "paid"
            order.report_status = "generating"
            order.kakao_tid = f"DEV_TID_{order.id}"
            db.commit()
            
            # 백그라운드 리포트 생성 시작
            try:
                from app.tasks import generate_full_report
                task = generate_full_report.delay(order.id, order.saju_key)
                order.celery_task_id = task.id
                db.commit()
                logger.info(f"🔧 개발 모드: 리포트 생성 태스크 시작 - task_id={task.id}")
            except Exception as e:
                logger.error(f"리포트 생성 태스크 시작 실패: {e}")
            
            # 개발 모드 응답 (결제창 없이 바로 성공 페이지로)
            return JSONResponse({
                "success": True,
                "dev_mode": True,
                "order_id": order.id,
                "redirect_url": f"/order/success?order_id={order.id}",
                "is_mobile": False,
                "message": "🔧 개발 모드: 결제 건너뛰기 완료"
            })

        ##################################################

        # 🏭 프로덕션 모드: 실제 카카오페이 호출
        try:
            kakao_response = await kakao_ready(
                order_id=order.id,
                amount=product.price,
                user_email=user.email,
                partner_user_id=str(user.id)
            )
            
            # TID 저장
            order.kakao_tid = kakao_response["tid"]
            db.commit()
            
            # User-Agent로 모바일/PC 구분
            user_agent = request.headers.get("user-agent", "")
            is_mobile = is_mobile_user_agent(user_agent)
            
            # 적절한 결제 URL 선택
            if is_mobile:
                redirect_url = kakao_response["next_redirect_mobile_url"]
            else:
                redirect_url = kakao_response["next_redirect_pc_url"]
            
            logger.info(f"주문 생성 성공: order_id={order.id}, tid={order.kakao_tid}")
            
            return JSONResponse({
                "success": True,
                "dev_mode": False,
                "order_id": order.id,
                "tid": order.kakao_tid,
                "redirect_url": redirect_url,
                "is_mobile": is_mobile,
                "message": "카카오페이 결제창으로 이동합니다."
            })
            
        except KakaoPayError as e:
            logger.error(f"카카오페이 ready API 실패: {e.message}")
            # 실패한 주문 삭제
            db.delete(order)
            db.commit()
            raise BadRequestError(f"결제 준비 실패: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 생성 실패: {str(e)}")
        db.rollback()
        raise InternalServerError(f"주문 생성 실패: {str(e)}")


################################################################################
# 2) 결제 승인 콜백 - 카카오페이에서 리다이렉트
################################################################################
@router.get("/approve")
async def kakao_approve_callback(
    request: Request,
    pg_token: str = Query(...),
    order_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """카카오페이 결제 승인 콜백"""
    try:
        # 주문 조회
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.status == "pending"
        ).first()
        
        if not order:
            logger.error(f"주문을 찾을 수 없음: order_id={order_id}")
            return RedirectResponse(
                url="/order/fail?message=주문을 찾을 수 없습니다.",
                status_code=302
            )
        
        # 주문 타임아웃 체크 (30분)
        if (datetime.now() - order.created_at).total_seconds() > 1800:
            logger.error(f"주문 시간 초과: order_id={order_id}")
            order.status = "cancelled"
            db.commit()
            return RedirectResponse(
                url="/order/fail?message=결제 시간이 초과되었습니다.",
                status_code=302
            )
        
        # 카카오페이 승인 API 호출
        try:
            approve_response = await kakao_approve(
                tid=order.kakao_tid,
                pg_token=pg_token,
                order_id=order.id,
                partner_user_id=str(order.user_id)
            )
            
            # 결제 검증
            verify_payment(order.amount, approve_response)
            
            # 주문 상태 업데이트
            order.status = "paid"
            order.report_status = "generating"
            db.commit()
            
            # 백그라운드 리포트 생성 시작
            try:
                from app.tasks import generate_full_report
                task = generate_full_report.delay(order.id, order.saju_key)
                order.celery_task_id = task.id
                db.commit()
                logger.info(f"리포트 생성 태스크 시작: task_id={task.id}")
            except Exception as e:
                logger.error(f"리포트 생성 태스크 시작 실패: {e}")
                # 태스크 실패해도 결제는 완료로 처리
            
            # 결제 성공 로그
            payment_method = get_payment_method_name(approve_response.get("payment_method_type", ""))
            paid_amount = approve_response.get("amount", {}).get("total", 0)
            logger.info(f"결제 승인 성공: order_id={order.id}, amount={paid_amount}, method={payment_method}")
            
            # 성공 페이지로 리다이렉트
            return RedirectResponse(
                url=f"/order/success?order_id={order.id}",
                status_code=302
            )
            
        except KakaoPayError as e:
            logger.error(f"카카오페이 승인 실패: order_id={order_id}, error={e.message}")
            order.status = "cancelled"
            db.commit()
            return RedirectResponse(
                url=f"/order/fail?message={e.message}",
                status_code=302
            )
        
    except Exception as e:
        logger.error(f"결제 승인 처리 중 오류: {e}")
        return RedirectResponse(
            url="/order/fail?message=결제 처리 중 오류가 발생했습니다.",
            status_code=302
        )

################################################################################
# 3) 결제 취소 콜백
################################################################################
@router.get("/cancel")
async def kakao_cancel_callback(
    request: Request,
    order_id: int = Query(None),
    db: Session = Depends(get_db)
):
    """카카오페이 결제 취소 콜백"""
    if order_id:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.status == "pending":
            order.status = "cancelled"
            db.commit()
            logger.info(f"결제 취소: order_id={order_id}")
    
    return templates.TemplateResponse("order/cancel.html", {
        "request": request,
        "message": "결제가 취소되었습니다."
    })

################################################################################
# 4) 결제 실패 콜백
################################################################################
@router.get("/fail")
async def kakao_fail_callback(
    request: Request,
    order_id: int = Query(None),
    message: str = Query("결제가 실패했습니다."),
    db: Session = Depends(get_db)
):
    """카카오페이 결제 실패 콜백"""
    if order_id:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order and order.status == "pending":
            order.status = "cancelled"
            db.commit()
            logger.info(f"결제 실패: order_id={order_id}")
    
    return templates.TemplateResponse("order/fail.html", {
        "request": request,
        "message": message
    })

################################################################################
# 5) 결제 성공 페이지
################################################################################
@router.get("/success", response_class=HTMLResponse)
async def payment_success(
    request: Request,
    order_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_optional)
):
    """결제 성공 페이지"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.status == "paid"
    ).first()
    
    if not order:
        logger.warning(f"Order not found: order_id={order_id}")
        raise NotFoundError("주문을 찾을 수 없습니다.")
    
    # 본인 주문이 아니면 접근 제한 (로그인한 경우만)
    if user and order.user_id != user.id:
        logger.warning(
            f"Permission denied: order_id={order_id}, user_id={user.id}"
        )
        raise PermissionDeniedError("접근 권한이 없습니다.")
    
    return templates.TemplateResponse("order/success.html", {
        "request": request,
        "order": order
    })

################################################################################
# 6) 마이페이지 - 구매 내역
################################################################################
@router.get("/mypage", response_class=HTMLResponse)
async def order_mypage(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """마이페이지 - 구매 내역 조회 (개선된 버전)"""
    orders = db.query(Order).filter(
        Order.user_id == user.id
    ).order_by(Order.created_at.desc()).all()
    
    # 각 주문에 사용자 이름과 사주 요약 정보 추가
    for order in orders:
        # SajuUser에서 이름 찾기
        saju_user = db.query(SajuUser).filter_by(saju_key=order.saju_key).first()
        order.user_name = saju_user.name if saju_user and saju_user.name else None
        
        # 사주키를 사용자 친화적으로 변환
        order.saju_summary = format_saju_key_for_display(order.saju_key)
    
    return templates.TemplateResponse("order/mypage.html", {
        "request": request,
        "orders": orders,
        "user": user,
        "get_flashed_messages": lambda req: get_flashed_messages(req)
    })

def format_saju_key_for_display(saju_key: str) -> str:
    """
    사주키를 사용자 친화적으로 변환
    예: SOL_19840301_UH_Asia-Seoul_M -> "1984년 3월 1일생 남성"
    """
    try:
        parts = saju_key.split('_')
        if len(parts) >= 5:
            calendar_type = parts[0]  # SOL/LUN
            date_part = parts[1]      # 19840301
            time_part = parts[2]      # UH (시간미상) or 숫자
            timezone_part = parts[3]  # Asia-Seoul
            gender = parts[4]         # M/F
            
            # 날짜 파싱
            year = date_part[:4]
            month = date_part[4:6]
            day = date_part[6:8]
            
            # 성별 변환
            gender_text = "남성" if gender == "M" else "여성"
            
            # 달력 타입
            calendar_text = "음력" if calendar_type == "LUN" else "양력"
            
            # 시간 정보
            if time_part == "UH":
                time_text = "시간미상"
            else:
                time_text = f"{time_part}시"
            
            return f"{calendar_text} {year}년 {int(month)}월 {int(day)}일생 {gender_text}"
        
        return "사주 정보"  # 파싱 실패시 기본값
    except:
        return "사주 정보"
################################################################################
# 7) 리포트 생성 재시도
################################################################################
@router.post("/retry/{order_id}")
async def retry_report_generation(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리포트 생성 재시도 API"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.id,
        Order.status == "paid",
        Order.report_status == "failed"
    ).first()

    if not order:
        logger.warning(
            f"Retry requested but order not found: order_id={order_id}, user_id={user.id}"
        )
        raise NotFoundError("생성 실패한 리포트를 찾을 수 없습니다.")

    # 리포트 상태 초기화
    order.report_status = "generating"
    order.report_completed_at = None
    order.celery_task_id = None

    try:
        from app.tasks import generate_full_report
        task = generate_full_report.delay(order.id, order.saju_key)
        order.celery_task_id = task.id
        db.commit()
        
        logger.info(f"리포트 재생성 태스크 시작: order_id={order_id}, task_id={task.id}")
        return JSONResponse({
            "success": True, 
            "message": "리포트 재생성이 시작되었습니다."
        })
        
    except Exception as e:
        logger.error(f"리포트 재생성 태스크 시작 실패: {e}")
        order.report_status = "failed"
        db.commit()
        raise InternalServerError("리포트 재생성 시작에 실패했습니다.")

################################################################################
# 8) 리포트 진행상황 체크 API
################################################################################
@router.get("/status/{order_id}")
async def check_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """주문 및 리포트 생성 상태 확인 API"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.id
    ).first()
    
    if not order:
        logger.warning(
            f"Order status requested but not found: order_id={order_id}, user_id={user.id}"
        )
        raise NotFoundError("주문을 찾을 수 없습니다.")
    
    # Celery 태스크 상태 확인
    task_status = None
    task_progress = None
    
    if order.celery_task_id:
        try:
            from celery.result import AsyncResult
            task_result = AsyncResult(order.celery_task_id)
            task_status = task_result.status
            
            if task_result.info:
                if isinstance(task_result.info, dict):
                    task_progress = task_result.info
                else:
                    task_progress = {"status": str(task_result.info)}
                    
        except Exception as e:
            logger.error(f"Celery 태스크 상태 확인 실패: {e}")
    
    return JSONResponse({
        "order_id": order.id,
        "order_status": order.status,
        "report_status": order.report_status,
        "task_status": task_status,
        "task_progress": task_progress,
        "report_completed_at": order.report_completed_at.isoformat() if order.report_completed_at else None,
        "has_report": bool(order.report_html or order.report_pdf)
    })

################################################################################
# 9) 리포트 다운로드
################################################################################
@router.get("/download/{order_id}")
async def download_report(
    order_id: int,
    format: str = Query("html", regex="^(html|pdf)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리포트 다운로드 (HTML 또는 PDF)"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.id,
        Order.status == "paid",
        Order.report_status == "completed"
    ).first()
    
    if not order:
        logger.warning(
            f"Report download requested but not found: order_id={order_id}, user_id={user.id}"
        )
        raise NotFoundError("리포트를 찾을 수 없습니다.")
    
    if format == "html" and order.report_html:
        from fastapi.responses import FileResponse
        return FileResponse(
            path=order.report_html,
            filename=f"saju_report_{order_id}.html",
            media_type="text/html"
        )
    elif format == "pdf" and order.report_pdf:
        from fastapi.responses import FileResponse
        return FileResponse(
            path=order.report_pdf,
            filename=f"saju_report_{order_id}.pdf",
            media_type="application/pdf"
        )
    else:
        logger.warning(
            f"Requested report format not ready: order_id={order_id}, format={format}"
        )
        raise NotFoundError(f"{format.upper()} 리포트가 아직 생성되지 않았습니다.")



################################################################################
# 9-1) 생성된 리포트 HTML 직접 보기 (새로 추가)
################################################################################
@router.get("/report/{order_id}", response_class=HTMLResponse)
async def view_report(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """리포트 HTML을 브라우저에서 직접 보기"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.id,
        Order.status == "paid",
        Order.report_status == "completed"
    ).first()
    
    if not order:
        logger.warning(
            f"Report view requested but not found: order_id={order_id}, user_id={user.id}"
        )
        raise NotFoundError("리포트를 찾을 수 없습니다.")
    
    if not order.report_html:
        logger.warning(
            f"HTML report missing: order_id={order_id}, user_id={user.id}"
        )
        raise NotFoundError("HTML 리포트가 아직 생성되지 않았습니다.")
    
    try:
        # HTML 파일 읽어서 직접 반환
        import os
        if not os.path.exists(order.report_html):
            logger.warning(
                f"Report file missing: order_id={order_id}, path={order.report_html}"
            )
            raise NotFoundError("리포트 파일이 존재하지 않습니다.")
            
        with open(order.report_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"리포트 HTML 읽기 실패: {e}")
        raise InternalServerError("리포트를 불러오는 중 오류가 발생했습니다.")

################################################################################
# 9-2) 빠른 리포트 보기 (새로운 utils.py 함수 사용)
################################################################################
templates = templates  # Use the imported global instance

@router.get("/report/live/{report_id}", response_class=HTMLResponse)
async def view_live_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """실시간 리포트 생성 및 표시 (utils.py 함수 사용)"""
    import logging

    logger = logging.getLogger(__name__)

    from app.models import Post
    report = db.query(Post).get(report_id)
    if report is None:
        logger.warning(f"Live report not found: report_id={report_id}")
        raise NotFoundError("리포트를 찾을 수 없습니다.")
    from app.models import User as ReportUser
    report_user = db.query(ReportUser).get(report.user_id)

    try:
        # ✅ utils.py의 새로운 함수 사용 - 권한 확인 포함

        html_content = generate_live_report_for_user(
            order_id=report_id,
            user_id=user.id,
            db=db
        )

        logger.info(f"✅ 실시간 리포트 생성 성공: order_id={report_id}, user_id={user.id}")
        return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        logger.error(f"❌ 실시간 리포트 생성 실패: order_id={report_id}, user_id={user.id}, error={e}")
        return templates.TemplateResponse("error/500.html", {
            "request": request,
            "error_message": "리포트를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        }, status_code=500)


################################################################################
# 추가: 개발용 리포트 보기 (선택사항)
################################################################################
@router.get("/dev/report/{order_id}", response_class=HTMLResponse)
async def dev_view_report(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """개발용 리포트 보기 (관리자 전용)"""
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 관리자 권한 확인 (선택사항)
    if not getattr(user, 'is_admin', False):
        logger.warning(
            f"Dev report access denied: order_id={order_id}, user_id={user.id}"
        )
        raise PermissionDeniedError("관리자 권한이 필요합니다.")
    
    try:
        # ✅ DB에서 직접 조회하는 방식 사용
        
        html_content = generate_live_report_from_db(order_id, db)
        
        logger.info(f"✅ 개발용 리포트 생성 성공: order_id={order_id}")
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"❌ 개발용 리포트 생성 실패: order_id={order_id}, error={e}")
        raise InternalServerError(f"개발용 리포트 생성 실패: {str(e)}")


################################################################################
# 10) 관리자용 주문 관리 (선택사항)
################################################################################
@router.get("/admin/list", response_class=HTMLResponse)
async def admin_order_list(
    request: Request,
    page: int = Query(1, ge=1),
    status: str = Query("all"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """관리자용 주문 목록"""
    if not user.is_admin:
        logger.warning(
            f"Admin order list access denied: user_id={user.id}"
        )
        raise PermissionDeniedError("관리자 권한이 필요합니다.")
    
    per_page = 20
    offset = (page - 1) * per_page
    
    query = db.query(Order)
    if status != "all":
        query = query.filter(Order.status == status)
    
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(per_page).all()
    total = query.count()
    pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("admin/orders.html", {
        "request": request,
        "orders": orders,
        "page": page,
        "pages": pages,
        "total": total,
        "current_status": status
    })

################################################################################
# 11) 웹훅 처리 (선택사항 - 추후 구현)
################################################################################
@router.post("/webhook/kakaopay")
async def kakaopay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """카카오페이 웹훅 처리 (추후 구현 예정)"""
    # 웹훅 데이터 처리 로직
    # 결제 상태 변경, 환불 처리 등
    return JSONResponse({"status": "ok"})