import os
import logging
from datetime import datetime, timedelta
from celery import current_task
from app.celery_app import celery_app
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Order, SajuAnalysisCache
from app.routers.saju import (
    load_prompt,
    test_ollama_connection,
    calculate_four_pillars,
    analyze_four_pillars_to_string,
    ai_sajupalja_with_ollama,
)
from markdown import markdown
import pdfkit
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# -------- NEW IMPORTS FOR REPORT RENDERING ------------
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.report_utils import radar_chart_base64, month_heat_table, keyword_card
# ------------------------------------------------------

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def html_to_pdf_improved(html: str, output_path: str) -> bool:
    """HTML을 PDF로 변환 (개선된 버전)"""
    try:
        # wkhtmltopdf 옵션 설정
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None
        }
        
        pdfkit.from_string(html, output_path, options=options)
        logger.info(f"PDF 생성 성공: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"wkhtmltopdf 실패: {e}, FPDF로 대체 시도")
        try:
            # FPDF 대체 방법
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font('Arial', size=12)
            
            # HTML 태그 제거 후 텍스트만 추출
            import re
            text = re.sub('<[^<]+?>', '', html)
            
            for line in text.split('\n'):
                if line.strip():
                    try:
                        pdf.multi_cell(0, 10, txt=line.strip(), align='L')
                    except:
                        # 인코딩 문제시 건너뛰기
                        continue
            
            pdf.output(output_path)
            logger.info(f"FPDF로 PDF 생성 완료: {output_path}")
            return True
            
        except Exception as e2:
            logger.error(f"PDF 생성 완전 실패: {e2}")
            return False

def send_email_improved(to_email: str, subject: str, body: str, attachments=None) -> bool:
    """이메일 발송 (개선된 버전)"""
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning('SMTP 설정이 없어 이메일 발송을 건너뜁니다')
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
        
        logger.info(f"이메일 발송 성공: {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        return False

@celery_app.task(bind=True, name='app.tasks.generate_full_report')
def generate_full_report(self, order_id: int, saju_key: str):
    """완전한 AI 리포트 생성 태스크"""
    db: Session = SessionLocal()
    
    try:
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
        
        if not test_ollama_connection():
            raise Exception('Ollama connection failed')

        # 사주 계산
        self.update_state(state='progress', meta={'current': 3, 'total': 6, 'status': '사주 분석 중...'})
        
        birthdate_str, birth_hour, gender = saju_key.split('_')
        birth_year, birth_month, birth_day = map(int, birthdate_str.split('-'))
        birth_hour = int(birth_hour)
        
        pillars = calculate_four_pillars(datetime(birth_year, birth_month, birth_day, birth_hour))
        elem_dict_kr, result_text  = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1],
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )
        combined_text = "\n".join([
            "오행 분포:",
            ", ".join([f"{k}:{v}" for k, v in elem_dict_kr.items()]),
            "",
            result_text,
        ])
        radar_base64 = radar_chart_base64({
            'Wood': elem_dict_kr.get('목', 0),
            'Fire': elem_dict_kr.get('화', 0),
            'Earth': elem_dict_kr.get('토', 0),
            'Metal': elem_dict_kr.get('금', 0),
            'Water': elem_dict_kr.get('수', 0),
        })

        # AI 분석 실행
        self.update_state(state='progress', meta={'current': 4, 'total': 6, 'status': 'AI 심층 분석 중...'})
        
        analysis_result = ai_sajupalja_with_ollama(prompt=prompt, content=combined_text)
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

        # HTML & PDF 생성
        self.update_state(state='progress', meta={'current': 5, 'total': 6, 'status': '리포트 파일 생성 중...'})
        
        # ────────────────────────────────────────────────
        #   리포트 템플릿 생성 (Jinja2 + report_utils)
        # ────────────────────────────────────────────────
        # 1) 데모/임시 데이터 준비 (후속 단계에서 실제 계산치로 교체)

        status_demo = {
            'Love':   ['G', 'R', '-', 'G', 'Y', '-', 'G', 'Y', '-', 'G', 'R', '-'],
            'Money':  ['-', 'G', 'R', 'Y', '-', 'G', '-', 'G', 'Y', '-', 'G', 'R'],
            'Career': ['Y', '-', 'G', 'G', 'R', '-', 'Y', '-', 'G', 'Y', '-', 'G'],
        }
        calendar_html = month_heat_table(status_demo)
        keyword_html  = keyword_card('Burgundy', [3, 9], 'Garnet')

        checklist = [
            {'cat': '습관', 'action': '아침 10분 스트레칭'},
            {'cat': '재물', 'action': '한 달 소비 5 % 줄이기'},
            {'cat': '관계', 'action': '매일 감사 메시지 1건 보내기'},
        ]

        # 2) Jinja2 환경 & 템플릿 렌더링
        env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=select_autoescape(['html'])
        )
        tpl = env.get_template('report_base.html')
        html_content = tpl.render(
            user_name   = getattr(order, 'buyer_name', None) or getattr(order, 'name', None) or '고객',
            radar_base64= radar_base64,
            calendar_html= calendar_html,
            keyword_html = keyword_html,
            checklist   = checklist,
        )

        # 3) AI 심층 분석 결과를 별도 섹션으로 추가
        html_content += (
            f"<hr><h2 style='color:#7C3AED;'>AI 심층 해석</h2>"
            f"{markdown(analysis_result.replace('\\n', '\\n\\n'))}"
        )
        
        # 파일 저장 경로
        output_dir = os.path.join('static', 'uploads', 'reports')
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f'report_order_{order_id}.html')
        pdf_path = os.path.join(output_dir, f'report_order_{order_id}.pdf')
        
        # HTML 저장
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # PDF 생성
        pdf_success = html_to_pdf_improved(html_content, pdf_path)
        
        # 파일 경로 업데이트
        order.report_html = html_path
        if pdf_success:
            order.report_pdf = pdf_path
        db.commit()

        # 이메일 발송
        self.update_state(state='progress', meta={'current': 6, 'total': 6, 'status': '이메일 발송 중...'})
        
        if order.pdf_send_email:
            email_subject = '🔮 사주팔자 심층 분석 리포트가 준비되었습니다'
            email_body = f"""
            <h2>안녕하세요!</h2>
            <p>주문하신 사주팔자 심층 분석 리포트가 완성되었습니다.</p>
            <p>첨부된 PDF 파일을 확인해주세요.</p>
            <p>감사합니다!</p>
            """
            
            attachments = [pdf_path] if pdf_success else []
            send_email_improved(order.pdf_send_email, email_subject, email_body, attachments)
        
        logger.info(f"리포트 생성 완료: order_id={order_id}")
        return {'status': 'SUCCESS', 'order_id': order_id}
        
    except Exception as e:
        logger.error(f"리포트 생성 실패: {e}")
        db.rollback()
        raise self.retry(countdown=60, max_retries=3, exc=e)
    finally:
        db.close()

@celery_app.task(name='app.tasks.cleanup_old_cache')
def cleanup_old_cache():
    """오래된 캐시 정리 태스크"""
    db = SessionLocal()
    try:
        # 30일 이상 된 캐시 삭제
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_cache = db.query(SajuAnalysisCache).filter(
            SajuAnalysisCache.created_at < cutoff_date
        ).delete()
        db.commit()
        logger.info(f"오래된 캐시 {old_cache}개 정리 완료")
    except Exception as e:
        logger.error(f"캐시 정리 실패: {e}")
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