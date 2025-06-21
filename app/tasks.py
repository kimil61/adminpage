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
)
from markdown import markdown
import pdfkit
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.report_utils import radar_chart_base64, month_heat_table, keyword_card

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def html_to_pdf_improved(html: str, output_path: str) -> bool:
    """HTML을 PDF로 변환 (개선된 버전)"""
    try:
        # wkhtmltopdf 옵션 설정 (개선됨)
        options = {
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm', 
            'margin-bottom': '20mm',
            'margin-left': '20mm',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None,  # CSS @media print 적용
            'disable-smart-shrinking': None,  # 자동 축소 비활성화
            'zoom': 1.0,
            'dpi': 300,  # 고해상도
            'image-quality': 100,
            'javascript-delay': 1000,  # JS 실행 대기
        }
        
        # HTML에 인라인 스타일 추가
        styled_html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
                
                body {{ 
                    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif; 
                    line-height: 1.6; 
                    margin: 40px;
                    color: #333;
                    background: white;
                }}
                
                h1 {{ 
                    color: #8B5CF6; 
                    text-align: center; 
                    font-size: 28px;
                    margin-bottom: 30px;
                    border-bottom: 3px solid #8B5CF6;
                    padding-bottom: 15px;
                }}
                
                h2 {{ 
                    color: #7C3AED; 
                    margin-top: 32px; 
                    margin-bottom: 16px;
                    font-size: 20px;
                    border-left: 4px solid #7C3AED;
                    padding-left: 12px;
                }}
                
                .mini-cal {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                }}
                
                .mini-cal td, .mini-cal th {{ 
                    padding: 8px 12px; 
                    text-align: center; 
                    font-size: 12px; 
                    border: 1px solid #ddd;
                }}
                
                .mini-cal th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                
                .card {{ 
                    background: #FFF7ED; 
                    border-radius: 8px; 
                    padding: 20px; 
                    margin: 15px 0;
                    border: 1px solid #F3E8FF;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                
                .card h3 {{
                    color: #7C3AED;
                    margin-top: 0;
                    margin-bottom: 15px;
                }}
                
                .card ul {{
                    list-style: none;
                    padding: 0;
                    margin: 0;
                }}
                
                .card li {{
                    padding: 5px 0;
                    border-bottom: 1px solid #E5E7EB;
                }}
                
                .card li:last-child {{
                    border-bottom: none;
                }}
                
                .checklist {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                }}
                
                .checklist td, .checklist th {{ 
                    padding: 10px 12px; 
                    font-size: 13px; 
                    border: 1px solid #ddd;
                    text-align: left;
                }}
                
                .checklist th {{
                    background-color: #7C3AED;
                    color: white;
                    font-weight: bold;
                }}
                
                .checklist tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                
                .ai-analysis {{
                    background: #F8FAFC;
                    border-left: 4px solid #3B82F6;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 0 8px 8px 0;
                }}
                
                .ai-analysis p {{
                    margin-bottom: 15px;
                    line-height: 1.7;
                }}
                
                .footer-note {{
                    margin-top: 40px; 
                    text-align: center; 
                    color: #6B7280; 
                    font-size: 11px;
                    border-top: 1px solid #E5E7EB;
                    padding-top: 20px;
                }}
                
                /* 이미지 최적화 */
                img {{
                    max-width: 100%;
                    height: auto;
                    display: block;
                    margin: 20px auto;
                }}
                
                /* 프린트용 최적화 */
                @media print {{
                    body {{ margin: 15mm; }}
                    h1 {{ page-break-after: avoid; }}
                    .card {{ page-break-inside: avoid; }}
                    .checklist {{ page-break-inside: avoid; }}
                }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        
        pdfkit.from_string(styled_html, output_path, options=options)
        logger.info(f"✅ PDF 생성 성공: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ wkhtmltopdf 실패: {e}")
        logger.info("🔄 FPDF로 대체 시도 중...")
        
        try:
            # FPDF 대체 방법 (개선됨)
            class UTF8PDF(FPDF):
                def __init__(self):
                    super().__init__()
                    self.add_font('malgun', '', 'malgun.ttf', uni=True)  # 한글 폰트 추가 시도
                
                def header(self):
                    if hasattr(self, 'title_text'):
                        self.set_font('Arial', 'B', 15)
                        self.cell(0, 10, self.title_text.encode('latin-1', 'ignore').decode('latin-1'), 0, 1, 'C')
                        self.ln(10)
                
                def add_text(self, text):
                    try:
                        self.set_font('malgun', size=12)
                    except:
                        self.set_font('Arial', size=12)
                    
                    # HTML 태그 제거
                    import re
                    clean_text = re.sub('<[^<]+?>', '', text)
                    clean_text = clean_text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
                    
                    # 텍스트를 줄 단위로 처리
                    for line in clean_text.split('\n'):
                        if line.strip():
                            try:
                                self.multi_cell(0, 8, txt=line.strip(), align='L')
                                self.ln(2)
                            except UnicodeEncodeError:
                                # 한글 처리 실패 시 ASCII만 추출
                                ascii_line = ''.join(char for char in line if ord(char) < 128)
                                if ascii_line.strip():
                                    self.multi_cell(0, 8, txt=ascii_line.strip(), align='L')
                                    self.ln(2)
            
            pdf = UTF8PDF()
            pdf.title_text = "사주팔자 리포트"
            pdf.add_page()
            pdf.add_text(html)
            pdf.output(output_path)
            
            logger.info(f"✅ FPDF로 PDF 생성 완료: {output_path}")
            return True
            
        except Exception as e2:
            logger.error(f"❌ PDF 생성 완전 실패: {e2}")
            return False

def generate_enhanced_report_html(user_name, pillars, analysis_result, elem_dict_kr):
    """향상된 HTML 리포트 생성"""
    try:
        # 레이더 차트 생성
        radar_base64 = radar_chart_base64({
            'Wood': elem_dict_kr.get('목', 0),
            'Fire': elem_dict_kr.get('화', 0), 
            'Earth': elem_dict_kr.get('토', 0),
            'Metal': elem_dict_kr.get('금', 0),
            'Water': elem_dict_kr.get('수', 0),
        })
        
        # 월별 운세 데모 데이터 (실제로는 AI 분석 결과로 교체)
        status_demo = {
            'Love': ['G', 'R', '-', 'G', 'Y', '-', 'G', 'Y', '-', 'G', 'R', '-'],
            'Money': ['-', 'G', 'R', 'Y', '-', 'G', '-', 'G', 'Y', '-', 'G', 'R'],
            'Career': ['Y', '-', 'G', 'G', 'R', '-', 'Y', '-', 'G', 'Y', '-', 'G'],
        }
        calendar_html = month_heat_table(status_demo)
        keyword_html = keyword_card('자주색', [3, 7, 9], '자수정')
        
        checklist = [
            {'cat': '습관 개선', 'action': '매일 아침 10분 명상하기'},
            {'cat': '재물 관리', 'action': '월 소비 예산 5% 줄이기'},
            {'cat': '인간관계', 'action': '매주 가족/친구에게 안부 묻기'},
            {'cat': '건강 관리', 'action': '주 3회 이상 운동하기'},
            {'cat': '자기계발', 'action': '한 달에 책 1권 읽기'},
        ]
        
        # Jinja2 환경 설정
        env = Environment(
            loader=FileSystemLoader('templates'),
            autoescape=select_autoescape(['html'])
        )
        
        # 템플릿 렌더링
        template = env.get_template('report_base.html')
        html_content = template.render(
            user_name=user_name,
            pillars=pillars,
            radar_base64=radar_base64,
            calendar_html=calendar_html, 
            keyword_html=keyword_html,
            checklist=checklist,
            analysis_result=analysis_result,
            elem_dict_kr=elem_dict_kr
        )
        
        return html_content
        
    except Exception as e:
        logger.error(f"HTML 리포트 생성 실패: {e}")
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

@celery_app.task(bind=True, name='app.tasks.generate_full_report')
def generate_full_report(self, order_id: int, saju_key: str):
    """완전한 AI 리포트 생성 태스크 (개선된 버전)"""
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

        # 사용자 이름 확인
        saju_user = db.query(SajuUser).filter_by(saju_key=order.saju_key).first()
        user_name = saju_user.name if saju_user and getattr(saju_user, "name", None) else "고객"

        # HTML & PDF 생성
        self.update_state(state='progress', meta={'current': 5, 'total': 6, 'status': '리포트 파일 생성 중...'})
        
        # 향상된 HTML 생성
        html_content = generate_enhanced_report_html(user_name, pillars, analysis_result, elem_dict_kr)
        
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
        pdf_success = html_to_pdf_improved(html_content, pdf_path)
        
        # 파일 경로 업데이트
        order.report_html = html_path
        if pdf_success:
            order.report_pdf = pdf_path
        db.commit()

        # 이메일 발송
        self.update_state(state='progress', meta={'current': 6, 'total': 6, 'status': '이메일 발송 중...'})
        
        if order.pdf_send_email:
            email_subject = f'🔮 {user_name}님의 사주팔자 심층 분석 리포트가 준비되었습니다'
            email_body = f"""
            <h2>안녕하세요, {user_name}님!</h2>
            <p>주문하신 사주팔자 심층 분석 리포트가 완성되었습니다.</p>
            <p>첨부된 PDF 파일을 확인해주세요.</p>
            <p>좋은 하루 되세요! 🌟</p>
            """
            
            attachments = [pdf_path] if pdf_success else []
            send_email_improved(order.pdf_send_email, email_subject, email_body, attachments)
        
        logger.info(f"🎉 리포트 생성 완료: order_id={order_id}")
        return {'status': 'SUCCESS', 'order_id': order_id, 'pdf_generated': pdf_success}
        
    except Exception as e:
        logger.error(f"💥 리포트 생성 실패: {e}")
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
        cutoff_date = datetime.utcnow() - timedelta(days=30)
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