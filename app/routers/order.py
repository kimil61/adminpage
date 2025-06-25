# app/routers/order.py - 카카오페이 결제 플로우 버전

"""주문 / 결제 / 구매내역 Router - 카카오페이 연동 버전"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query, Header
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
            raise HTTPException(status_code=400, detail="사주 정보가 필요합니다.")
        
        # 중복 구매 체크
        existing = db.query(Order).filter(
            Order.user_id == user.id,
            Order.saju_key == saju_key,
            Order.status == "paid"
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 구매한 리포트입니다.")
        
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
            raise HTTPException(status_code=400, detail=f"결제 준비 실패: {e.message}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 생성 실패: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"주문 생성 실패: {str(e)}")


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
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    # 본인 주문이 아니면 접근 제한 (로그인한 경우만)
    if user and order.user_id != user.id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")
    
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
        "user": user
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
        raise HTTPException(status_code=404, detail="생성 실패한 리포트를 찾을 수 없습니다.")

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
        raise HTTPException(status_code=500, detail="리포트 재생성 시작에 실패했습니다.")

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
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
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
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    
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
        raise HTTPException(status_code=404, detail=f"{format.upper()} 리포트가 아직 생성되지 않았습니다.")

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
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    
    if not order.report_html:
        raise HTTPException(status_code=404, detail="HTML 리포트가 아직 생성되지 않았습니다.")
    
    try:
        # HTML 파일 읽어서 직접 반환
        import os
        if not os.path.exists(order.report_html):
            raise HTTPException(status_code=404, detail="리포트 파일이 존재하지 않습니다.")
            
        with open(order.report_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"리포트 HTML 읽기 실패: {e}")
        raise HTTPException(status_code=500, detail="리포트를 불러오는 중 오류가 발생했습니다.")

################################################################################
# 9-2) 빠른 리포트 보기 (기존 generate_enhanced_report_html 재사용)
################################################################################
@router.get("/report/live/{order_id}", response_class=HTMLResponse)
async def view_live_report(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """실시간 리포트 생성 및 표시 (수정된 버전)"""
    from app.models import SajuAnalysisCache, SajuUser
    import logging
    
    logger = logging.getLogger(__name__)
    
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.id,
        Order.status == "paid"
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    
    # 캐시에서 AI 분석 결과 확인
    cache = db.query(SajuAnalysisCache).filter_by(saju_key=order.saju_key).first()
    if not cache or not cache.analysis_full:
        return HTMLResponse("""
            <div style="text-align: center; padding: 3rem; font-family: 'Noto Sans KR', sans-serif;">
                <h2>🔄 리포트를 준비 중입니다</h2>
                <p>AI 분석이 완료되면 자동으로 표시됩니다.</p>
                <div style="margin: 2rem 0;">
                    <div style="width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 2s linear infinite; margin: 0 auto;"></div>
                </div>
                <script>
                    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                    setTimeout(() => location.reload(), 5000);
                </script>
            </div>
        """)
    
    try:
        # 필요한 모듈들 import
        from app.routers.saju import calculate_four_pillars, analyze_four_pillars_to_string
        from datetime import datetime
        from app.report_utils import (
            enhanced_radar_chart_base64,
            generate_2025_fortune_calendar,
            generate_lucky_keywords,
            keyword_card,
            generate_action_checklist,
            generate_fortune_summary,
            create_executive_summary
        )
        from markdown import markdown
        
        # 사주 정보 파싱
        parts = order.saju_key.split('_')
        if len(parts) == 5:
            calendar, birth_raw, hour_part, tz_part, gender = parts
            birthdate_str = f"{birth_raw[:4]}-{birth_raw[4:6]}-{birth_raw[6:]}"
            birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        elif len(parts) == 3:
            birthdate_str, hour_part, gender = parts
            birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        else:
            raise ValueError(f"잘못된 saju_key 형식: {order.saju_key}")

        if birth_hour is None:
            birth_hour = 12

        birth_year, birth_month, birth_day = map(int, birthdate_str.split('-'))
        pillars = calculate_four_pillars(datetime(birth_year, birth_month, birth_day, birth_hour))
        elem_dict_kr, result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1], 
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )

        # 사용자 이름
        saju_user = db.query(SajuUser).filter_by(saju_key=order.saju_key).first()
        user_name = saju_user.name if saju_user and getattr(saju_user, "name", None) else "고객"

        # 리포트 구성요소들 생성
        try:
            executive_summary = create_executive_summary(user_name, birthdate_str, pillars, elem_dict_kr)
            radar_base64 = enhanced_radar_chart_base64(elem_dict_kr)
            calendar_html = generate_2025_fortune_calendar(elem_dict_kr)
            
            birth_month = int(birthdate_str.split('-')[1]) if birthdate_str else 6
            lucky_color, lucky_numbers, lucky_stone = generate_lucky_keywords(elem_dict_kr, birth_month)
            keyword_html = keyword_card(lucky_color, lucky_numbers, lucky_stone)
            
            checklist = generate_action_checklist(elem_dict_kr)
            fortune_summary = generate_fortune_summary(elem_dict_kr)
        except Exception as comp_error:
            logger.error(f"리포트 구성요소 생성 실패: {comp_error}")
            # 기본값들로 대체
            executive_summary = {"summary": "리포트 준비 중", "key_points": []}
            radar_base64 = ""
            calendar_html = "<p>달력 준비 중</p>"
            keyword_html = "<p>키워드 준비 중</p>"
            checklist = []
            fortune_summary = {"summary": "운세 준비 중"}

        # pillars 형식을 템플릿에 맞게 변환
        pillars_display = {
            'year': pillars['year'][0] + pillars['year'][1],    # 갑자
            'month': pillars['month'][0] + pillars['month'][1], # 정미  
            'day': pillars['day'][0] + pillars['day'][1],       # 병인
            'hour': pillars['hour'][0] + pillars['hour'][1]     # 무술
        }

        # AI 분석 결과를 마크다운으로 변환
        analysis_result_html = markdown(cache.analysis_full.replace('\n', '\n\n'))

        # Jinja2 환경 설정 (markdown 필터 추가)
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        
        env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=select_autoescape(['html'])
        )
        
        # 필터 추가
        def markdown_filter(text):
            if not text:
                return ""
            return markdown(str(text).replace('\n', '\n\n'))
        
        def strftime_filter(value, format='%Y-%m-%d %H:%M'):
            if isinstance(value, str) and value == "now":
                return datetime.now().strftime(format)
            return value
        
        env.filters['markdown'] = markdown_filter
        env.filters['strftime'] = strftime_filter
        
        # 템플릿 렌더링
        template = env.get_template('enhanced_report_base.html')
        html_content = template.render(
            request=request,
            user_name=user_name,
            pillars=pillars_display,  # 수정된 형식
            executive_summary=executive_summary,
            radar_base64=radar_base64,
            calendar_html=calendar_html, 
            keyword_html=keyword_html,
            checklist=checklist,
            fortune_summary=fortune_summary,
            analysis_result=cache.analysis_full,  # 원본 텍스트
            elem_dict_kr=elem_dict_kr,
            birthdate=birthdate_str
        )
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"실시간 리포트 생성 실패: {e}")
        import traceback
        traceback.print_exc()  # 디버깅용
        
        # 에러가 발생하면 간단한 AI 분석 결과만 보여주기
        analysis_html = markdown(cache.analysis_full.replace('\n', '\n\n'))
        
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{user_name}님의 사주팔자 리포트</title>
            <style>
                body {{ 
                    font-family: 'Noto Sans KR', sans-serif; 
                    line-height: 1.6; 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 2rem; 
                    background: #f8fafc;
                }}
                .container {{ 
                    background: white; 
                    padding: 2rem; 
                    border-radius: 12px; 
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #2d3748; margin-bottom: 1rem; }}
                h2 {{ color: #4a5568; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
                .ai-analysis {{ 
                    background: #f7fafc; 
                    padding: 1.5rem; 
                    border-radius: 8px; 
                    border-left: 4px solid #4299e1;
                }}
                .footer-note {{ 
                    text-align: center; 
                    color: #718096; 
                    font-size: 0.9rem; 
                    margin-top: 2rem; 
                    padding-top: 1rem; 
                    border-top: 1px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔮 {user_name}님의 사주팔자 리포트</h1>
                <h2>🧠 AI 심층 분석</h2>
                <div class="ai-analysis">
                    {analysis_html}
                </div>
                <div class="footer-note">
                    본 리포트는 AI 분석 결과이며 참고용입니다. 🌟<br>
                    <small>리포트 생성 중 일부 기능에서 오류가 발생하여 간소화된 버전을 표시합니다.</small>
                </div>
            </div>
        </body>
        </html>
        """, status_code=200)

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
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
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