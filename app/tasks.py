import os
import logging
from datetime import datetime, timedelta
from celery import current_task
from app.celery_app import celery_app
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Order, SajuAnalysisCache, SajuUser
from app.routers.saju import (
    load_prompt,
    test_ollama_connection,
    calculate_four_pillars,
    analyze_four_pillars_to_string,
    ai_sajupalja_with_ollama,
    ai_sajupalja_with_chatgpt,
    ai_sajupalja_with_chatgpt_sync
)
from markdown import markdown
import pdfkit
import asyncio
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.report_utils import (
    radar_chart_base64, 
    month_heat_table, 
    keyword_card,
    generate_2025_fortune_calendar,
    generate_lucky_keywords,
    generate_action_checklist,
    create_executive_summary,
    generate_fortune_summary,
    enhanced_radar_chart_base64
)


# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_enhanced_report_html(user_name, pillars, analysis_result, elem_dict_kr, birthdate_str=None):
    """향상된 HTML 리포트 생성 (5가지 업그레이드 적용)"""
    try:
        # 1. 임원급 요약 정보
        executive_summary = create_executive_summary(user_name, birthdate_str or "1984-06-01", pillars, elem_dict_kr)
        
        # 2. 향상된 레이더 차트 (설명 포함)
        radar_base64 = enhanced_radar_chart_base64(elem_dict_kr)
        
        # 3. 오행 기반 월별 운세 달력
        calendar_html = generate_2025_fortune_calendar(elem_dict_kr)
        
        # 4. 개인화된 행운 키워드
        birth_month = int(birthdate_str.split('-')[1]) if birthdate_str else 6
        lucky_color, lucky_numbers, lucky_stone = generate_lucky_keywords(elem_dict_kr, birth_month)
        keyword_html = keyword_card(lucky_color, lucky_numbers, lucky_stone)
        
        # 5. 맞춤형 실천 체크리스트
        checklist = generate_action_checklist(elem_dict_kr)
        
        # 6. 운세 요약 카드
        fortune_summary = generate_fortune_summary(elem_dict_kr)
        
        # 7. AI 심층 분석 결과 markdown 변환
        analysis_result_html = markdown(analysis_result.replace('\n', '\n\n'))
        
        # Jinja2 환경 설정
        env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=select_autoescape(['html'])
        )
        
        # 날짜 필터 추가
        def strftime_filter(value, format='%Y-%m-%d %H:%M'):
            if isinstance(value, str) and value == "now":
                return datetime.now().strftime(format)
            return value
        
        env.filters['strftime'] = strftime_filter
        
        # 템플릿 렌더링
        template = env.get_template('enhanced_report_base.html')
        html_content = template.render(
            user_name=user_name,
            pillars=pillars,
            executive_summary=executive_summary,
            radar_base64=radar_base64,
            calendar_html=calendar_html, 
            keyword_html=keyword_html,
            checklist=checklist,
            fortune_summary=fortune_summary,
            analysis_result=analysis_result,
            elem_dict_kr=elem_dict_kr,
            birthdate=birthdate_str
        )
        
        return html_content
        
    except Exception as e:
        logger.error(f"향상된 HTML 리포트 생성 실패: {e}")
        # 폴백 HTML
        return f"""
        <h1>🔮 {user_name}님의 사주팔자 리포트</h1>
        <h2>AI 심층 분석</h2>
        <div class="ai-analysis">
            {markdown(analysis_result.replace('\\n', '\\n\\n'))}
        </div>
        <div class="footer-note">
            본 리포트는 AI 분석 결과이며 참고용입니다.
        </div>
        """

# generate_full_report 함수도 약간 수정 (birthdate_str 전달)
@celery_app.task(bind=True, name='app.tasks.generate_full_report')
def generate_full_report(self, order_id: int, saju_key: str):
    """완전한 AI 리포트 생성 태스크 (향상된 버전)"""
    db: Session = SessionLocal()
    
    try:
        # 🎯 주문 상태를 generating으로 업데이트
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise Exception(f'Order {order_id} not found')
        
        order.report_status = "generating"
        db.commit()

        # 진행 상황 업데이트
        self.update_state(state='progress', meta={'current': 1, 'total': 6, 'status': '주문 정보 확인 중...'})
        
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise Exception(f'Order {order_id} not found')

        # 프롬프트 로드
        self.update_state(state='progress', meta={'current': 2, 'total': 6, 'status': 'AI 모델 준비 중...'})
        
        prompt = load_prompt()
        if not prompt:
            raise Exception('Prompt file missing')
        
        if not os.getenv('OPENAI_API_KEY'):
            raise Exception('OpenAI API key not configured')

        # if not test_ollama_connection():
        #     raise Exception('Ollama connection failed')

        # 사주 계산
        self.update_state(state='progress', meta={'current': 3, 'total': 6, 'status': '사주 분석 중...'})
        
        # saju_key 형식 파싱 (3조각: yyyy-mm-dd_hour_gender  |  5조각: CAL_yyyymmdd_HH/UH_TZ_G)
        parts = saju_key.split('_')

        if len(parts) == 5:
            calendar, birth_raw, hour_part, tz_part, gender = parts
            birthdate_str = f"{birth_raw[:4]}-{birth_raw[4:6]}-{birth_raw[6:]}"
            birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        elif len(parts) == 3:
            birthdate_str, hour_part, gender = parts
            birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        else:
            raise ValueError(f"잘못된 saju_key 형식: {saju_key}")

        # 출생 시간이 정해지지 않았으면 정오(12시)로 대체
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

        # AI 분석 실행
        self.update_state(state='progress', meta={'current': 4, 'total': 6, 'status': 'AI 심층 분석 중...'})
        
        combined_text = "\n".join([
            "오행 분포:",
            ", ".join([f"{k}:{v}" for k, v in elem_dict_kr.items()]),
            "",
            result_text,
        ])
        
        # 기존 asyncio.run 코드를 동기 함수로 교체
        analysis_result = ai_sajupalja_with_chatgpt_sync(prompt=prompt, content=combined_text)

        if not analysis_result:
            raise Exception('Failed to generate AI analysis')

        # 캐시에 저장
        cache = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
        if cache:
            cache.analysis_full = analysis_result
        else:
            cache = SajuAnalysisCache(saju_key=saju_key, analysis_full=analysis_result)
            db.add(cache)
        db.commit()
        order.analysis_cache_id = cache.id

        # 사용자 이름 확인
        saju_user = db.query(SajuUser).filter_by(saju_key=order.saju_key).first()
        user_name = saju_user.name if saju_user and getattr(saju_user, "name", None) else "고객"

        # HTML & PDF 생성
        self.update_state(state='progress', meta={'current': 5, 'total': 6, 'status': '리포트 파일 생성 중...'})
        
        # 향상된 HTML 생성 (birthdate_str 전달)
        html_content = generate_enhanced_report_html(
            user_name, pillars, analysis_result, elem_dict_kr, birthdate_str
        )
        
        # 파일 저장 경로
        output_dir = os.path.join('static', 'uploads', 'reports')
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f'report_order_{order_id}.html')
        pdf_path = os.path.join(output_dir, f'report_order_{order_id}.pdf')
        
        # HTML 저장
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"📄 HTML 저장 완료: {html_path}")
        
        # PDF 생성
        # pdf_success = html_to_pdf_improved(html_content, pdf_path)
        
        # 파일 경로 업데이트
        order.report_html = html_path

        db.commit()

        # 이메일 발송
        # self.update_state(state='progress', meta={'current': 6, 'total': 6, 'status': '이메일 발송 중...'})
        
        # if order.pdf_send_email:
        #     email_subject = f'🔮 {user_name}님의 사주팔자 심층 분석 리포트가 준비되었습니다'
        #     email_body = f"""
        #     <h2>안녕하세요, {user_name}님!</h2>
        #     <p>주문하신 사주팔자 심층 분석 리포트가 완성되었습니다.</p>
        #     <p><strong>포함 내용:</strong></p>
        #     <ul>
        #         <li>🎯 개인 맞춤 요약 정보</li>
        #         <li>📊 오행 밸런스 차트 + 해석</li>
        #         <li>📅 2025년 월별 운세 달력</li>
        #         <li>🍀 행운 키워드 & 실천 가이드</li>
        #         <li>🤖 AI 심층 분석 결과</li>
        #     </ul>
        #     <p>첨부된 PDF 파일을 확인해주세요.</p>
        #     <p>좋은 하루 되세요! 🌟</p>
        #     """
            
        #     attachments = [pdf_path] if pdf_success else []
        #     send_email_improved(order.pdf_send_email, email_subject, email_body, attachments)
        
        # AI 분석 완료 후 상태 업데이트
        order.report_status = "completed"
        order.report_completed_at = datetime.now()
        db.commit()

        logger.info(f"🎉 리포트 생성 완료: order_id={order_id}")
        return {
            'status': 'SUCCESS', 
            'order_id': order_id, 
            'report_status': 'completed',
            'completed_at': order.report_completed_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"💥 리포트 생성 실패: {e}")
        
        # 🎯 실패 시 상태 업데이트
        if 'order' in locals():
            order.report_status = "failed"
            db.commit()
        
        db.rollback()
        raise self.retry(countdown=60, max_retries=3, exc=e)
    finally:
        db.close()

def send_email_improved(to_email: str, subject: str, body: str, attachments=None) -> bool:
    """이메일 발송 (개선된 버전)"""
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning('⚠️ SMTP 설정이 없어 이메일 발송을 건너뜁니다')
        return False

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg.attach(MIMEText(body, 'html', 'utf-8'))

        attachments = attachments or []
        for file_path in attachments:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        
        logger.info(f"📧 이메일 발송 성공: {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"💥 이메일 발송 실패: {e}")
        return False

# 기존 다른 태스크들...
@celery_app.task(name='app.tasks.cleanup_old_cache')
def cleanup_old_cache():
    """오래된 캐시 정리 태스크"""
    db = SessionLocal()
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        old_cache = db.query(SajuAnalysisCache).filter(
            SajuAnalysisCache.created_at < cutoff_date
        ).delete()
        db.commit()
        logger.info(f"🗑️ 오래된 캐시 {old_cache}개 정리 완료")
    except Exception as e:
        logger.error(f"💥 캐시 정리 실패: {e}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(bind=True, name='app.tasks.test_task')
def test_task(self, name: str):
    """테스트용 태스크"""
    import time
    for i in range(5):
        time.sleep(1)
        self.update_state(state='progress', meta={'current': i+1, 'total': 5, 'status': f'Processing {name}...'})
    return {'status': 'Task completed!', 'name': name}