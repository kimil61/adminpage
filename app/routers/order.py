"""주문 / 결제 Router - 간소화 버전"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query, Header
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product, User, SajuAnalysisCache
from app.template import templates
from app.dependencies import get_current_user
import logging
from celery.result import AsyncResult
import markdown

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
    """개선된 테스트 성공 페이지 - 실제 AI 분석 결과 표시"""
    order = db.query(Order).filter(
        Order.id == order_id, 
        Order.user_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    try:
        # 필요한 import들
        from app.saju_utils import SajuKeyManager
        from app.routers.saju import calculate_four_pillars, analyze_four_pillars_to_string
        from app.routers.saju import load_prompt, ai_sajupalja_with_ollama, test_ollama_connection
        from app.tasks import generate_enhanced_report_html
        from app.models import SajuUser, SajuAnalysisCache
        from app.report_utils import radar_chart_base64
        
        # 사주 키로 계산 정보 추출
        calc_datetime, orig_date, gender = SajuKeyManager.get_birth_info_for_calculation(order.saju_key)
        
        # 사주 계산
        pillars = calculate_four_pillars(calc_datetime)
        elem_dict_kr, result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1], 
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )
        
        # 사용자 이름 찾기
        saju_user = db.query(SajuUser).filter_by(saju_key=order.saju_key).first()
        user_name = saju_user.name if saju_user and saju_user.name else "고객"
        
        # 🎯 실제 AI 분석 결과 가져오기
        dummy_analysis = None
        
        # 1. 캐시에서 기존 AI 분석 확인
        cached_analysis = db.query(SajuAnalysisCache).filter_by(saju_key=order.saju_key).first()
        
        if cached_analysis and cached_analysis.analysis_full:
            # 캐시된 AI 분석이 있으면 사용
            dummy_analysis = cached_analysis.analysis_full
            print(f"✅ 캐시된 AI 분석 사용: {order.saju_key}")
        else:
            # 2. 캐시가 없으면 즉시 AI 생성 시도
            try:
                print(f"🤖 새로운 AI 분석 생성 시도: {order.saju_key}")
                
                # Ollama 연결 확인
                if test_ollama_connection():
                    prompt = load_prompt()
                    if prompt:
                        # 사주 정보를 AI 입력용 텍스트로 조합
                        combined_text = "\n".join([
                            "오행 분포:",
                            ", ".join([f"{k}:{v}" for k, v in elem_dict_kr.items()]),
                            "",
                            result_text,  # 사주 기본 해석
                        ])
                        
                        # AI 분석 실행
                        ai_result = ai_sajupalja_with_ollama(prompt=prompt, content=combined_text)
                        
                        if ai_result:
                            # 새 분석 결과를 캐시에 저장
                            if cached_analysis:
                                cached_analysis.analysis_full = ai_result
                            else:
                                new_cache = SajuAnalysisCache(
                                    saju_key=order.saju_key,
                                    analysis_full=ai_result
                                )
                                db.add(new_cache)
                            db.commit()
                            
                            dummy_analysis = ai_result
                            print(f"✅ 새 AI 분석 생성 완료 및 캐시 저장")
                        else:
                            print(f"❌ AI 분석 생성 실패")
                    else:
                        print(f"❌ 프롬프트 로드 실패")
                else:
                    print(f"❌ Ollama 연결 실패")
                    
            except Exception as e:
                print(f"❌ AI 분석 생성 중 오류: {e}")
        

        # 🍀 행운 키워드 생성
        lucky_keywords = ["성장", "도전", "소통", "안정", "창조", "조화", "발전", "인내"]
        selected_keywords = [lucky_keywords[i] for i in range(0, min(4, len(lucky_keywords)), 2)]
        
        keyword_html = f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0;">
            {' '.join([f'''
            <div style="background: linear-gradient(135deg, #a855f7 0%, #8b5cf6 100%); color: white; padding: 1.5rem; border-radius: 12px; text-align: center; box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🌟</div>
                <div style="font-size: 1.2rem; font-weight: 600;">{keyword}</div>
                <div style="font-size: 0.9rem; opacity: 0.9; margin-top: 0.5rem;">핵심 키워드</div>
            </div>
            ''' for keyword in selected_keywords])}
        </div>
        
        <div style="background: #f8fafc; padding: 1.5rem; border-radius: 12px; margin-top: 1rem; border-left: 4px solid #8b5cf6;">
            <p style="margin: 0; color: #4a5568; line-height: 1.6;">
                <strong style="color: #8b5cf6;">💡 활용법:</strong> 
                이 키워드들을 일상에서 의식적으로 떠올려보세요. 
                중요한 결정을 내릴 때나 새로운 일을 시작할 때 참고하시면 도움이 될 것입니다.
            </p>
        </div>
        """
        
        # 📅 월별 운세 생성
        months = [
            ("1월", "새로운 시작", "좋음", "#10b981"),
            ("2월", "인간관계 확장", "보통", "#f59e0b"), 
            ("3월", "창의적 아이디어", "좋음", "#10b981"),
            ("4월", "재정 관리 중요", "주의", "#ef4444"),
            ("5월", "건강 관리", "보통", "#f59e0b"),
            ("6월", "새로운 도전", "좋음", "#10b981"),
            ("7월", "여름 휴식기", "보통", "#f59e0b"),
            ("8월", "인내의 시기", "주의", "#ef4444"),
            ("9월", "수확의 계절", "좋음", "#10b981"),
            ("10월", "안정된 발전", "좋음", "#10b981"),
            ("11월", "마무리 준비", "보통", "#f59e0b"),
            ("12월", "성과 정리", "좋음", "#10b981")
        ]
        
        monthly_fortune = f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin: 1rem 0;">
            {' '.join([f'''
            <div style="background: white; border: 2px solid {color}; border-radius: 12px; padding: 1rem; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-weight: 600; font-size: 1.1rem; color: {color};">{month}</span>
                    <span style="background: {color}; color: white; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 500;">{status}</span>
                </div>
                <p style="margin: 0; color: #4a5568; line-height: 1.5;">{desc}</p>
            </div>
            ''' for month, desc, status, color in months])}
        </div>
        
        <div style="background: #f0f9ff; padding: 1.5rem; border-radius: 12px; margin-top: 1rem; border-left: 4px solid #0ea5e9;">
            <p style="margin: 0; color: #0c4a6e; line-height: 1.6;">
                <strong>📊 운세 가이드:</strong> 
                <span style="color: #10b981;"><strong>● 좋음:</strong> 적극 추진</span> | 
                <span style="color: #f59e0b;"><strong>▲ 보통:</strong> 신중하게</span> | 
                <span style="color: #ef4444;"><strong>■ 주의:</strong> 보수적으로</span>
            </p>
        </div>
        """
        
        # ✅ 실천 체크리스트 생성
        checklist_items = [
            {"cat": "💰 재물", "action": "가계부 작성하여 수입/지출 관리하기"},
            {"cat": "❤️ 인간관계", "action": "가족/친구와 깊은 대화 나누기"}, 
            {"cat": "🎯 목표", "action": "월간 목표 설정하고 주간 점검하기"},
            {"cat": "💪 건강", "action": "규칙적인 운동 루틴 만들기"},
            {"cat": "📚 학습", "action": "새로운 기술이나 지식 하나 익히기"},
            {"cat": "🧘 마음", "action": "명상이나 독서로 내면 성찰하기"}
        ]
        
        # 오행 차트 생성
        try:
            radar_base64_img = radar_chart_base64(elem_dict_kr)
        except Exception as e:
            print(f"차트 생성 실패: {e}")
            radar_base64_img = None
        analysis_html = markdown.markdown(dummy_analysis) if dummy_analysis else None
        # 🎨 개선된 HTML 템플릿 렌더링
        return templates.TemplateResponse(
            "enhanced_report_base.html",
            {
                "request": request,
                "user_name": user_name,
                "pillars": pillars,
                "analysis": analysis_html,  # 실제 AI 분석 또는 더미 데이터
                "element_counts": elem_dict_kr,
                "radar_base64": radar_base64_img,
                "monthly_fortune": monthly_fortune,
                "keyword_html": keyword_html,
                "checklist": checklist_items,
                "order": order
            }
        )
        
    except Exception as e:
        logger.error(f"리포트 생성 실패: {str(e)}")
        return templates.TemplateResponse(
            "errors/500.html",
            {"request": request, "error": str(e)},
            status_code=500
        )



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