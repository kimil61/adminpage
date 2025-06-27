# tasks.py 수정 버전

import os
import logging
import re
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
from weasyprint import HTML
import asyncio
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import pdfkit

# ✅ utils.py에서 리포트 생성 함수들 import
from app.utils import generate_enhanced_report_html,generate_live_report_from_db

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.test_task')
def test_task(self, message: str):
    """테스트용 간단한 태스크"""
    logger.info(f"테스트 태스크 실행: {message}")
    return f"완료: {message}"


def html_to_pdf_production(html_content: str, output_path: str) -> bool:
    """프로덕션용 PDF 생성 (최고 호환성)"""
    try:
        options = {
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm', 
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
            'disable-smart-shrinking': None,
            'print-media-type': None,
            'image-dpi': 300,
            'image-quality': 94,
            'javascript-delay': 500,
            'no-outline': None,
            'enable-local-file-access': None,
            'title': '사주팔자 분석 리포트',
            'disable-javascript': None,  # JS 제거로 호환성 향상
        }
        
        pdfkit.from_string(html_content, output_path, options=options)
        
        # 📊 생성된 파일 검증
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"✅ PDF 생성 성공: {output_path} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            raise Exception("PDF 파일이 생성되지 않았거나 크기가 0입니다.")
            
    except Exception as e:
        logger.error(f"❌ PDF 생성 실패: {e}")
        return False
    

def html_to_pdf_production2(html_content: str, output_path: str) -> bool:
    """프로덕션용 PDF 생성 (WeasyPrint 버전)"""
    try:
        # WeasyPrint를 사용하여 PDF 생성
        HTML(string=html_content, base_url=".").write_pdf(output_path)

        # 생성된 파일 검증
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"✅ PDF 생성 성공: {output_path} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            raise Exception("PDF 파일이 생성되지 않았거나 크기가 0입니다.")
    except Exception as e:
        logger.error(f"❌ PDF 생성 실패: {e}")
        return False
    
@celery_app.task(bind=True, name='app.tasks.generate_full_report')
def generate_full_report(self, order_id: int, saju_key: str):
    """완전한 AI 리포트 생성 태스크 (개선된 버전)"""
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
        
        # 프롬프트 로드
        self.update_state(state='progress', meta={'current': 2, 'total': 6, 'status': 'AI 모델 준비 중...'})
        
        prompt = load_prompt()
        if not prompt:
            raise Exception('Prompt file missing')
        
        if not os.getenv('OPENAI_API_KEY'):
            raise Exception('OpenAI API key not configured')

        # 사주 계산
        self.update_state(state='progress', meta={'current': 3, 'total': 6, 'status': '사주 분석 중...'})
        from app.services.saju_service import SajuService
        pillars, elem_dict_kr = SajuService.get_or_calculate_saju(saju_key, db)

        # saju_key 형식 파싱 (3조각: yyyy-mm-dd_hour_gender  |  5조각: CAL_yyyymmdd_HH/UH_TZ_G)
        # parts = saju_key.split('_')

        # if len(parts) == 5:
        #     calendar, birth_raw, hour_part, tz_part, gender = parts
        #     birthdate_str = f"{birth_raw[:4]}-{birth_raw[4:6]}-{birth_raw[6:]}"
        #     birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        # elif len(parts) == 3:
        #     birthdate_str, hour_part, gender = parts
        #     birth_hour = None if hour_part in ("UH", "", "None") else int(hour_part)
        # else:
        #     raise ValueError(f"잘못된 saju_key 형식: {saju_key}")

        # # 출생 시간이 정해지지 않았으면 정오(12시)로 대체
        # if birth_hour is None:
        #     birth_hour = 12

        # birth_year, birth_month, birth_day = map(int, birthdate_str.split('-'))

        # pillars = calculate_four_pillars(datetime(birth_year, birth_month, birth_day, birth_hour))
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

        # 🎯 HTML & PDF 생성 - 새로운 방식 사용
        self.update_state(state='progress', meta={'current': 5, 'total': 6, 'status': '리포트 파일 생성 중...'})
        
        # ✅ 이미 계산된 데이터를 활용하여 HTML 생성
        # birthdate_str 추출 (리포트 생성용)
        parts = saju_key.split('_')
        if len(parts) == 5:
            calendar, birth_raw, hour_part, tz_part, gender = parts
            birthdate_str = f"{birth_raw[:4]}-{birth_raw[4:6]}-{birth_raw[6:]}"
        elif len(parts) == 3:
            birthdate_str, hour_part, gender = parts
        else:
            birthdate_str = "1984-01-01"  # 기본값

        # ✅ Option 1: 이미 계산된 데이터를 활용하여 HTML 생성
        html_content = generate_enhanced_report_html(
            user_name=user_name,
            pillars=pillars,
            analysis_result=analysis_result,
            elem_dict_kr=elem_dict_kr,
            birthdate_str=birthdate_str
        )
        
        # ✅ Option 2: DB에서 다시 조회하여 생성 (선택사항)
        html_content = generate_live_report_from_db(order_id, db)
        
        # 파일 저장 경로
        output_dir = os.path.join('static', 'uploads', 'reports')
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f'report_order_{order_id}.html')
        pdf_path = os.path.join(output_dir, f'report_order_{order_id}.pdf')
        
        # HTML 저장
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"📄 HTML 저장 완료: {html_path}")
        
        # PDF 생성 (선택사항)
        pdf_success = html_to_pdf_production(html_content, pdf_path)
        print(pdf_success)
        # 파일 경로 업데이트
        order.report_html = html_path
        db.commit()

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
    try:
        # SMTP 설정 확인
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not all([smtp_server, smtp_username, smtp_password]):
            logger.warning("SMTP 설정이 완전하지 않아 이메일 발송을 건너뜁니다.")
            return False
        
        # 이메일 생성
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # HTML 본문 추가
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # 첨부파일 추가
        if attachments:
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                        msg.attach(part)
        
        # SMTP 서버 연결 및 발송
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        logger.info(f"✅ 이메일 발송 성공: {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 이메일 발송 실패: {e}")
        return False