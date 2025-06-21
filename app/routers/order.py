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
    """개선된 테스트 성공 페이지 - 실제 AI 결과 표시"""
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
        ai_analysis = None
        cached_analysis = db.query(SajuAnalysisCache).filter_by(saju_key=order.saju_key).first()
        
        if cached_analysis and cached_analysis.analysis_full:
            # 기존 AI 분석이 있는 경우
            ai_analysis = cached_analysis.analysis_full
        else:
            # AI 분석이 없는 경우 - 즉시 생성하거나 더미 표시
            try:
                from app.routers.saju import load_prompt, ai_sajupalja_with_ollama, test_ollama_connection
                
                # Ollama 연결 확인
                if test_ollama_connection():
                    prompt = load_prompt()
                    if prompt:
                        # 사주 정보 조합
                        combined_text = "\n".join([
                            "오행 분포:",
                            ", ".join([f"{k}:{v}" for k, v in elem_dict_kr.items()]),
                            "",
                            result_text,
                        ])
                        
                        # AI 분석 실행
                        ai_analysis = ai_sajupalja_with_ollama(prompt=prompt, content=combined_text)
                        
                        if ai_analysis:
                            # 새 분석 결과 캐시에 저장
                            if cached_analysis:
                                cached_analysis.analysis_full = ai_analysis
                            else:
                                new_cache = SajuAnalysisCache(
                                    saju_key=order.saju_key,
                                    analysis_full=ai_analysis
                                )
                                db.add(new_cache)
                            db.commit()
                            
            except Exception as e:
                print(f"AI 분석 생성 실패: {e}")
        
        # AI 분석이 없는 경우 더미 데이터 사용
        if not ai_analysis:
            ai_analysis = f"""
            <h3 style="color: #667eea; margin-bottom: 1.5rem;">🔮 {user_name}님만을 위한 AI 심층 분석</h3>
            
            <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); padding: 1.5rem; border-radius: 12px; margin: 1rem 0; border-left: 4px solid #0ea5e9;">
                <p><strong style="color: #0369a1;">🌟 전체적인 운명의 흐름:</strong><br>
                {user_name}님의 사주를 종합적으로 분석한 결과, <strong style="color: #dc2626;">{list(elem_dict_kr.keys())[0]} 기운이 강한 특성</strong>을 보이고 있습니다. 
                이는 창의적이고 진취적인 성향으로 나타나며, 새로운 도전을 두려워하지 않는 추진력을 의미합니다.</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); padding: 1.5rem; border-radius: 12px; margin: 1rem 0; border-left: 4px solid #10b981;">
                <p><strong style="color: #047857;">💰 재물운과 사업운:</strong><br>
                2025년 하반기부터 재물운이 점진적으로 상승하는 흐름을 보입니다. 특히 인맥을 통한 기회가 많아질 것으로 예상되며, 
                꾸준한 노력이 결실을 맺는 시기입니다.</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #fef7cd 0%, #fde047 100%); padding: 1.5rem; border-radius: 12px; margin: 1rem 0; border-left: 4px solid #eab308;">
                <p><strong style="color: #a16207;">❤️ 인간관계와 사랑운:</strong><br>
                올해는 새로운 인연을 만날 가능성이 높은 해입니다. 기존 관계에서도 더욱 깊어지는 계기가 생길 것이며, 
                진솔한 소통이 관계 발전의 열쇠가 됩니다.</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #fee2e2 0%, #fca5a5 100%); padding: 1.5rem; border-radius: 12px; margin: 1rem 0; border-left: 4px solid #ef4444;">
                <p><strong style="color: #b91c1c;">⚠️ 주의사항과 조언:</strong><br>
                성급한 결정보다는 신중한 판단이 필요한 시기입니다. 특히 큰 투자나 이직 결정은 충분한 정보 수집 후 진행하시기 바랍니다. 
                건강관리에도 각별한 주의를 기울이세요.</p>
            </div>
            
            <div style="text-align: center; margin-top: 2rem; padding: 1rem; background: #f8fafc; border-radius: 8px;">
                <p style="color: #64748b; font-style: italic;">
                ⚠️ AI 분석을 로딩 중입니다. 실제 AI 분석 결과는 PDF 리포트에서 확인하실 수 있습니다.
                </p>
            </div>
            """
        
        # 오행 차트 생성
        elem_dict_eng = {
            '목': 'Wood', '화': 'Fire', '토': 'Earth', 
            '금': 'Metal', '수': 'Water'
        }
        chart_data = {elem_dict_eng.get(k, k): v for k, v in elem_dict_kr.items()}
        chart_base64 = radar_chart_base64(chart_data)
        
        # 템플릿에 전달할 데이터
        context = {
            "request": request,
            "order": order,
            "user_name": user_name,
            "pillars": pillars,
            "elem_dict_kr": elem_dict_kr,
            "ai_analysis": ai_analysis,  # 실제 AI 분석 결과
            "chart_base64": chart_base64,
            "birthdate_str": orig_date.strftime('%Y년 %m월 %d일'),
            "gender_kr": "남성" if gender == "male" else "여성",
        }
        
        return templates.TemplateResponse("order/test_success_enhanced.html", context)
        
    except Exception as e:
        print(f"test_success_page 오류: {e}")
        # 오류 발생 시 기본 페이지로 폴백
        return templates.TemplateResponse("order/test_success.html", {
            "request": request,
            "order": order
        })

# 🎯 추가: AI 분석 재생성 API
@router.post("/regenerate-ai/{order_id}")
async def regenerate_ai_analysis(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """AI 분석 재생성"""
    order = db.query(Order).filter(
        Order.id == order_id, 
        Order.user_id == user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    try:
        from app.routers.saju import load_prompt, ai_sajupalja_with_ollama, test_ollama_connection
        from app.routers.saju import calculate_four_pillars, analyze_four_pillars_to_string
        from app.saju_utils import SajuKeyManager
        from app.models import SajuAnalysisCache
        
        # Ollama 연결 확인
        if not test_ollama_connection():
            return {"success": False, "message": "AI 서버에 연결할 수 없습니다."}
        
        # 사주 계산
        calc_datetime, orig_date, gender = SajuKeyManager.get_birth_info_for_calculation(order.saju_key)
        pillars = calculate_four_pillars(calc_datetime)
        elem_dict_kr, result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1], 
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )
        
        # AI 분석 실행
        prompt = load_prompt()
        combined_text = "\n".join([
            "오행 분포:",
            ", ".join([f"{k}:{v}" for k, v in elem_dict_kr.items()]),
            "",
            result_text,
        ])
        
        ai_analysis = ai_sajupalja_with_ollama(prompt=prompt, content=combined_text)
        
        if ai_analysis:
            # 캐시 업데이트
            cached_analysis = db.query(SajuAnalysisCache).filter_by(saju_key=order.saju_key).first()
            if cached_analysis:
                cached_analysis.analysis_full = ai_analysis
            else:
                new_cache = SajuAnalysisCache(
                    saju_key=order.saju_key,
                    analysis_full=ai_analysis
                )
                db.add(new_cache)
            db.commit()
            
            return {"success": True, "message": "AI 분석이 재생성되었습니다.", "analysis": ai_analysis}
        else:
            return {"success": False, "message": "AI 분석 생성에 실패했습니다."}
            
    except Exception as e:
        return {"success": False, "message": f"오류가 발생했습니다: {str(e)}"}
    
    
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