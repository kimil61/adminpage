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
# app/routers/order.py에서 test_success_page 함수 완전 교체
@router.get("/test-success/{order_id}", response_class=HTMLResponse)
async def test_success_page(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """테스트 성공 페이지 - 풀 리포트 HTML 표시 (더미 AI 분석)"""
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
        from app.tasks import generate_enhanced_report_html
        from app.models import SajuUser
        
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
        
        # 🎯 더미 AI 분석 (고품질)
        dummy_analysis = f"""
        <h3>🔮 {user_name}님만을 위한 AI 심층 분석</h3>
        
        <p><strong>🌟 전체적인 운명의 흐름:</strong><br>
        {user_name}님의 사주를 종합적으로 분석한 결과, <strong>{list(elem_dict_kr.keys())[0]} 기운이 강한 특성</strong>을 보이고 있습니다. 
        이는 창의적이고 진취적인 성향으로 나타나며, 새로운 도전을 두려워하지 않는 추진력을 의미합니다.</p>
        
        <p><strong>💰 재물운과 사업운:</strong><br>
        2025년 하반기부터 재물운이 점진적으로 상승하는 흐름을 보입니다. 
        특히 <strong>자수성가형</strong>의 운세로, 남에게 의존하기보다는 본인의 능력으로 성취해나가는 타입입니다. 
        투자보다는 실무 능력을 기반으로 한 수익이 더 안정적일 것으로 예상됩니다.</p>
        
        <p><strong>❤️ 인간관계와 애정운:</strong><br>
        따뜻하고 진실한 마음을 가지고 있어 주변 사람들에게 신뢰를 받는 편입니다. 
        다만 때로는 자신의 마음을 표현하는 데 서툴 수 있으니, 
        <strong>솔직한 소통</strong>을 통해 더 깊은 관계를 만들어나가시길 권합니다.</p>
        
        <p><strong>🎯 2025년 중점 포인트:</strong><br>
        올해는 <strong>새로운 기술 습득</strong>이나 <strong>전문성 강화</strong>에 집중하시면 좋겠습니다. 
        상반기에는 계획 수립과 준비 기간으로, 하반기부터는 본격적인 실행 단계로 접어드는 것이 이상적입니다.</p>
        
        <p><strong>⚠️ 주의사항:</strong><br>
        {list(elem_dict_kr.keys())[-1]} 기운이 다소 부족하여 균형을 맞추는 것이 중요합니다. 
        충분한 휴식과 안정적인 생활 패턴을 유지하시고, 
        성급한 결정보다는 신중한 판단을 하시길 바랍니다.</p>
        
        <div style="margin-top: 20px; padding: 15px; background: #F0F9FF; border-left: 4px solid #0EA5E9; border-radius: 8px;">
            <p style="margin: 0; font-weight: bold; color: #0F172A;">
            💡 <strong>AI의 조언:</strong> {user_name}님은 타고난 리더십과 창의력을 가지고 계십니다. 
            자신감을 가지고 목표를 향해 나아가되, 주변 사람들과의 협력을 잊지 마세요. 
            작은 성취들을 쌓아가며 큰 꿈을 이루어나가실 것입니다.
            </p>
        </div>
        """
        
        # 🎯 enhanced HTML 생성 (PDF와 동일한 품질)
        html_content = generate_enhanced_report_html(
            user_name=user_name,
            pillars=pillars,
            analysis_result=dummy_analysis,
            elem_dict_kr=elem_dict_kr,
            birthdate_str=orig_date
        )
        
        # 🌟 웹 전용 스타일과 버튼 추가
        web_enhanced_html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{user_name}님의 프리미엄 사주팔자 리포트 - 구매 완료</title>
            <style>
                /* 기본 리포트 스타일 유지 + 웹 전용 개선 */
                body {{
                    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    min-height: 100vh;
                }}
                
                .web-container {{
                    max-width: 900px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                
                .web-header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    position: relative;
                }}
                
                .web-header::before {{
                    content: '✨';
                    position: absolute;
                    top: 20px;
                    left: 30px;
                    font-size: 30px;
                    opacity: 0.7;
                }}
                
                .web-header::after {{
                    content: '🔮';
                    position: absolute;
                    top: 20px;
                    right: 30px;
                    font-size: 30px;
                    opacity: 0.7;
                }}
                
                .purchase-badge {{
                    display: inline-block;
                    background: rgba(255,255,255,0.2);
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 14px;
                    margin-top: 10px;
                    border: 1px solid rgba(255,255,255,0.3);
                }}
                
                .action-buttons {{
                    background: #f8f9fa;
                    padding: 30px;
                    text-align: center;
                    border-top: 1px solid #e9ecef;
                }}
                
                .btn {{
                    display: inline-block;
                    padding: 12px 24px;
                    margin: 0 10px 10px 0;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    border: none;
                    cursor: pointer;
                    font-size: 14px;
                }}
                
                .btn-primary {{
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                }}
                
                .btn-primary:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                }}
                
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                }}
                
                .btn-secondary:hover {{
                    background: #5a6268;
                    transform: translateY(-2px);
                }}
                
                .btn-outline {{
                    background: white;
                    color: #667eea;
                    border: 2px solid #667eea;
                }}
                
                .btn-outline:hover {{
                    background: #667eea;
                    color: white;
                    transform: translateY(-2px);
                }}
                
                @media print {{
                    .web-header, .action-buttons {{ display: none !important; }}
                    body {{ background: white; padding: 0; }}
                    .web-container {{ box-shadow: none; }}
                }}
                
                @media (max-width: 768px) {{
                    body {{ padding: 10px; }}
                    .web-header {{ padding: 20px; }}
                    .action-buttons {{ padding: 20px; }}
                    .btn {{ margin: 5px; padding: 10px 18px; }}
                }}
            </style>
        </head>
        <body>
            <div class="web-container">
                <!-- 웹 전용 헤더 -->
                <div class="web-header">
                    <h1 style="margin: 0; font-size: 28px;">🎉 구매 완료!</h1>
                    <p style="margin: 10px 0; font-size: 18px; opacity: 0.9;">
                        {user_name}님의 프리미엄 사주팔자 리포트
                    </p>
                    <div class="purchase-badge">
                        💎 Premium Report ₩1,900
                    </div>
                </div>
                
                <!-- 기존 리포트 내용 삽입 -->
                <div style="padding: 0;">
                    {html_content.split('<body>')[1].split('</body>')[0]}
                </div>
                
                <!-- 웹 전용 액션 버튼들 -->
                <div class="action-buttons">
                    <h3 style="margin: 0 0 20px 0; color: #495057;">리포트를 어떻게 활용하시겠어요?</h3>
                    
                    <a href="/order/mypage" class="btn btn-primary">
                        📋 구매 내역 확인
                    </a>
                    
                    <button onclick="window.print()" class="btn btn-secondary">
                        🖨️ 인쇄하기
                    </button>
                    
                    <a href="/saju/page1" class="btn btn-outline">
                        🔮 새로운 사주 보기
                    </a>
                    
                    <div style="margin-top: 20px; padding: 15px; background: #e8f5e8; border-radius: 8px; border-left: 4px solid #28a745;">
                        <small style="color: #155724; display: block; margin-bottom: 8px;">
                            <strong>💡 활용 팁:</strong>
                        </small>
                        <small style="color: #155724; line-height: 1.5;">
                            이 리포트를 인쇄해서 보관하시거나, 중요한 결정을 내릴 때 참고자료로 활용해보세요. 
                            가족이나 친구들과 함께 보시면 더욱 재미있을 거예요! 🌟
                        </small>
                    </div>
                </div>
            </div>
            
            <script>
                // 페이지 로드 시 축하 효과
                document.addEventListener('DOMContentLoaded', function() {{
                    // 스크롤 시 부드러운 애니메이션
                    document.querySelectorAll('.btn').forEach(btn => {{
                        btn.addEventListener('click', function(e) {{
                            if (this.onclick) return;
                            this.style.transform = 'scale(0.95)';
                            setTimeout(() => {{
                                this.style.transform = '';
                            }}, 150);
                        }});
                    }});
                    
                    // 인쇄 전 알림
                    window.addEventListener('beforeprint', function() {{
                        alert('인쇄 시 웹 전용 버튼들은 제외되고 깔끔한 리포트만 인쇄됩니다.');
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        # HTML 직접 반환
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=web_enhanced_html)
        
    except Exception as e:
        # 에러 시 기존 간단한 성공 페이지로 폴백
        logger.error(f"리포트 생성 오류: {e}")
        return templates.TemplateResponse("order/test_success.html", {
            "request": request,
            "order": order,
            "error": f"리포트 생성 중 오류가 발생했습니다: {str(e)}"
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