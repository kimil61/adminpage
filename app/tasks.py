# Celery tasks for generating full AI reports and sending them via email
import os
from datetime import datetime
from celery import Celery
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

# Celery configuration
celery_app = Celery('tasks', broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))


def html_to_pdf(html: str, output_path: str) -> None:
    """Convert HTML string to PDF file."""
    try:
        pdfkit.from_string(html, output_path)
    except Exception:
        # fallback simple pdf if wkhtmltopdf unavailable
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font('Arial', size=12)
        for line in html.split('\n'):
            pdf.multi_cell(0, 10, txt=line, align='L')
        pdf.output(output_path)


def send_email(to_email: str, subject: str, body: str, attachments=None) -> None:
    """Send an email with optional attachments."""
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')

    if not smtp_host or not smtp_user or not smtp_password:
        print('SMTP settings not configured; skipping email sending')
        return

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg.attach(MIMEText(body, 'html'))

    attachments = attachments or []
    for path in attachments:
        with open(path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
        msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], msg.as_string())


@celery_app.task
def generate_full_report(order_id: int, saju_key: str) -> None:
    """Generate a full AI report as HTML/PDF and email it to the user."""
    db: Session = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            print(f'Order {order_id} not found')
            return

        prompt = load_prompt()
        if not prompt:
            print('Prompt file missing')
            return
        if not test_ollama_connection():
            print('ollama connection failed')
            return

        birthdate_str, birth_hour, gender = saju_key.split('_')
        birth_year, birth_month, birth_day = map(int, birthdate_str.split('-'))
        birth_hour = int(birth_hour)
        pillars = calculate_four_pillars(datetime(birth_year, birth_month, birth_day, birth_hour))
        result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1],
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )

        analysis_result = ai_sajupalja_with_ollama(prompt=prompt, content=result_text)
        if not analysis_result:
            print('Failed to generate analysis')
            return

        # store in cache table
        cache = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
        if cache:
            cache.analysis_full = analysis_result
        else:
            cache = SajuAnalysisCache(saju_key=saju_key, analysis_full=analysis_result)
            db.add(cache)
        db.commit()
        order.analysis_cache_id = cache.id

        # create HTML & PDF files
        html_content = markdown(analysis_result.replace('\n', '\n\n'))
        output_dir = os.path.join('static', 'uploads', 'reports')
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f'order_{order_id}.html')
        pdf_path = os.path.join(output_dir, f'order_{order_id}.pdf')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        html_to_pdf(html_content, pdf_path)

        order.report_html = html_path
        order.report_pdf = pdf_path
        db.commit()

        if order.pdf_send_email:
            send_email(
                order.pdf_send_email,
                'Your Saju Report',
                html_content,
                attachments=[pdf_path],
            )
    finally:
        db.close()
