from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
import os
import uuid
import re
from PIL import Image
import aiofiles
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Order, SajuAnalysisCache, SajuUser
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown import markdown
import re
import html as html_module
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


logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")
    
    return user

def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user

def flash_message(request: Request, message: str, category: str = "info"):
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request):
    messages = request.session.pop("flash_messages", [])
    return [(msg["category"], msg["message"]) for msg in messages]

def create_slug(text: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9가-힣\s]', '', text)
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug.lower()

async def save_uploaded_file(file: UploadFile, folder: str = "uploads") -> str:
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise ValueError("허용되지 않는 파일 형식입니다.")
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    upload_dir = f"static/uploads/{folder}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, unique_filename)
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    if file_extension in {'.jpg', '.jpeg', '.png', '.webp'}:
        resize_image(file_path, max_width=800)
    
    return f"/static/uploads/{folder}/{unique_filename}"

def resize_image(image_path: str, max_width: int = 800):
    try:
        with Image.open(image_path) as img:
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=85)
    except Exception:
        pass

def generate_enhanced_report_html(user_name, pillars, analysis_result, elem_dict_kr, birthdate_str=None):
    """향상된 HTML 리포트 생성 (개선된 행운키워드 포함)"""
    try:
        # 1. 임원급 요약 정보
        executive_summary = create_executive_summary(user_name, birthdate_str or "1984-06-01", pillars, elem_dict_kr)
        
        # 2. 향상된 레이더 차트 (설명 포함)
        radar_base64 = enhanced_radar_chart_base64(elem_dict_kr)
        
        # 3. 오행 기반 월별 운세 달력
        calendar_html = generate_2025_fortune_calendar(elem_dict_kr)
        
        # 4. 🆕 개선된 개인화 행운 키워드 (일관성 보장 + 설명 포함)
        birth_month = int(birthdate_str.split('-')[1]) if birthdate_str else 6
        
        # 개선된 함수 사용 - 더 많은 개인화 정보 전달
        from app.report_utils import generate_lucky_keywords_with_explanation, keyword_card_improved
        
        lucky_color, lucky_numbers, lucky_stone, explanation = generate_lucky_keywords_with_explanation(
            elem_dict_kr=elem_dict_kr,
            birth_month=birth_month,
            birthdate_str=birthdate_str,
            pillars=pillars
        )
        
        # 개선된 키워드 카드 생성 (설명 포함)
        keyword_html = keyword_card_improved(lucky_color, lucky_numbers, lucky_stone, explanation)
        
        # 5. 맞춤형 실천 체크리스트
        checklist = generate_action_checklist(elem_dict_kr)
        
        # 6. 운세 요약 카드
        fortune_summary = generate_fortune_summary(elem_dict_kr)
        
        # 7. AI 심층 분석 결과를 HTML로 변환 (개선된 버전)
        def format_ai_analysis(text: str) -> str:
            """
            GPT‑4o가 줄바꿈을 제대로 넣지 못해 하나의 문장으로 붙여­나오는 문제를
            완전히 해결한다.

            1) ### 헤딩 앞뒤 줄바꿈 강제 ‑ 선행 공백 제거
            2) '### n. 제목:' → '### n. 제목' + 본문 분리
            3) 문단 내부 한국어 마침표 뒤에 <br> 삽입 (가독성↑)
            4) **A. …** 패턴을 #### 서브헤딩으로 변환
            5) 마크다운→HTML 변환 후, 기존 스타일 인라인 유지
            """
            if not text:
                return ""

            import re, html as html_module
            from markdown import markdown

            # 줄바꿈 종류 통일
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

            # ① 헤딩 앞 공백 제거 + 두 줄바꿈 보장
            #    ' … ### 2.' → '\n\n### 2.'
            text = re.sub(r'\s*###\s*', r'\n\n### ', text)

            # ② '### 1. 제목: 본문…' → '### 1. 제목\n\n본문…'
            text = re.sub(
                r'^(###\s*\d+\.\s*[^:\n]+):\s*',
                r'\1\n\n',
                text,
                flags=re.MULTILINE
            )

            # ③ **A. 소제목** → #### A. 소제목
            text = re.sub(r'\*\*([A-F])\.\s*([^*]+?)\*\*', r'#### \1. \2', text)

            # ④ 가독성용 줄바꿈: 마침표 뒤 한글/영대문자 시작이면 <br>용 두 스페이스 + \n
            text = re.sub(r'(?<!\d)\.\s+(?=[가-힣A-Z])', '.  \n', text)

            # ⑤ 과잉 빈줄 정리(3줄→2줄)
            text = re.sub(r'\n{3,}', '\n\n', text)

            # ⑥ 마크다운 → HTML
            html = markdown(
                text,
                extensions=[
                    "markdown.extensions.extra",
                    "markdown.extensions.nl2br",
                    "markdown.extensions.sane_lists",
                ],
            )

            # ⑦ HTML 엔티티 디코드
            html = html_module.unescape(html)

            # ⑧ 스타일 주입
            html = html.replace(
                "<h3>",
                '<h3 style="color: #7C3AED; margin-top: 2rem; margin-bottom: 1rem; font-size: 1.25rem; font-weight: 600;">',
            )
            html = html.replace(
                "<h4>",
                '<h4 style="color: #5B21B6; margin-top: 1.5rem; margin-bottom: 1rem; font-size: 1.1rem; font-weight: 600;">',
            )
            html = html.replace(
                "<p>",
                '<p style="margin-bottom: 1rem; line-height: 1.6;">',
            )

            return html

        analysis_result_html = format_ai_analysis(analysis_result)

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
            keyword_html=keyword_html,  # 개선된 키워드 HTML (설명 포함)
            checklist=checklist,
            fortune_summary=fortune_summary,
            analysis_result_html=analysis_result_html,  # 변환된 HTML
            analysis_result=analysis_result,  # 원본 텍스트
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

def generate_live_report_from_db(order_id: int, db: Session) -> str:
    """
    DB에서 직접 데이터를 조회해서 실시간 HTML 리포트 생성
    tasks.py와 order.py에서 공통으로 사용할 수 있는 함수
    """
    try:
        # 1. Order 조회
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise Exception(f'Order {order_id} not found')

        # 2. saju_analysis_cache에서 analysis_full 조회
        cache = db.query(SajuAnalysisCache).filter_by(saju_key=order.saju_key).first()
        if not cache or not cache.analysis_full:
            raise Exception(f'Analysis cache not found for saju_key: {order.saju_key}')

        # 3. saju_key 파싱해서 필요한 데이터 추출
        # birthdate_str, birth_hour, user_name = parse_saju_key_and_get_data(order.saju_key, db)

        # 3. 사용자 이름 조회
        user_name = get_user_name_from_saju_key(order.saju_key, db)


        # 4. 사주 계산 (pillars, elem_dict_kr)
        # pillars, elem_dict_kr = calculate_saju_data(birthdate_str, birth_hour)
        from app.services.saju_service import SajuService
        pillars, elem_dict_kr = SajuService.get_or_calculate_saju(order.saju_key, db)

        # 5. birthdate_str 추출 (리포트 생성용)
        birthdate_str = extract_birthdate_from_saju_key(order.saju_key)

        # 6. generate_enhanced_report_html 함수 호출
        html_content = generate_enhanced_report_html(
            user_name=user_name,
            pillars=pillars,
            analysis_result=cache.analysis_full,
            elem_dict_kr=elem_dict_kr,
            birthdate_str=birthdate_str
        )
        
        return html_content
        
    except Exception as e:
        logger.error(f"실시간 리포트 생성 실패: {e}")
        raise


def get_user_name_from_saju_key(saju_key: str, db: Session) -> str:
    """saju_key로 사용자 이름 조회"""
    try:
        saju_user = db.query(SajuUser).filter_by(saju_key=saju_key).first()
        return saju_user.name if saju_user and getattr(saju_user, "name", None) else "고객"
    except Exception as e:
        logger.error(f"사용자 이름 조회 실패: {e}")
        return "고객"


def extract_birthdate_from_saju_key(saju_key: str) -> str:
    """saju_key에서 birthdate_str 추출 (리포트 생성용)"""
    try:
        parts = saju_key.split('_')
        if len(parts) == 5:
            calendar, birth_raw, hour_part, tz_part, gender = parts
            return f"{birth_raw[:4]}-{birth_raw[4:6]}-{birth_raw[6:]}"
        elif len(parts) == 3:
            birthdate_str, hour_part, gender = parts
            return birthdate_str
        else:
            return "1984-01-01"  # 기본값
    except Exception as e:
        logger.error(f"생년월일 추출 실패: {e}")
        return "1984-01-01"




def parse_saju_key_and_get_data(saju_key: str, db: Session) -> tuple[str, int, str]:
    """
    saju_key를 파싱하고 관련 데이터를 조회
    Returns: (birthdate_str, birth_hour, user_name)
    """
    try:
        # saju_key 형식 파싱 (3조각: yyyy-mm-dd_hour_gender  |  5조각: CAL_yyyymmdd_HH/UH_TZ_G)
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

        # SajuUser에서 사용자 이름 조회
        saju_user = db.query(SajuUser).filter_by(saju_key=saju_key).first()
        user_name = saju_user.name if saju_user and getattr(saju_user, "name", None) else "고객"

        return birthdate_str, birth_hour, user_name
        
    except Exception as e:
        logger.error(f"saju_key 파싱 실패: {e}")
        raise


def calculate_saju_data_bak(birthdate_str: str, birth_hour: int) -> tuple[dict, dict]:
    """
    생년월일과 시간으로 사주 데이터 계산
    Returns: (pillars, elem_dict_kr)
    """
    try:
        # tasks.py에서 import
        from app.routers.saju import calculate_four_pillars, analyze_four_pillars_to_string
        
        birth_year, birth_month, birth_day = map(int, birthdate_str.split('-'))
        
        pillars = calculate_four_pillars(datetime(birth_year, birth_month, birth_day, birth_hour))
        elem_dict_kr, result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1], 
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1],
        )
        
        return pillars, elem_dict_kr
        
    except Exception as e:
        logger.error(f"사주 데이터 계산 실패: {e}")
        raise


# 추가: order.py에서 사용할 수 있는 간단한 래퍼 함수
def generate_live_report_for_user(order_id: int, user_id: int, db: Session) -> str:
    """
    사용자 권한 확인 후 실시간 리포트 생성
    order.py에서 사용
    """
    try:
        # 주문 소유권 확인
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.status == "paid"
        ).first()
        
        if not order:
            raise Exception("리포트를 찾을 수 없거나 접근 권한이 없습니다.")
        
        return generate_live_report_from_db(order_id, db)
        
    except Exception as e:
        logger.error(f"사용자 리포트 생성 실패: {e}")
        raise