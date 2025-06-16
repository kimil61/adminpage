from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, Category
from app.template import templates
from datetime import datetime, timedelta
import uuid
import hashlib
import re
import sxtwl
import openai
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

router = APIRouter(prefix="/saju")

# 천간/지지 계산 (중국 한자)
heavenly_stems = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
earthly_branches = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

GAN = heavenly_stems
ZHI = earthly_branches

# 오행 매핑
element_map = {
    '甲': ('목', '木'), '乙': ('목', '木'),
    '丙': ('화', '火'), '丁': ('화', '火'),
    '戊': ('토', '土'), '己': ('토', '土'),
    '庚': ('금', '金'), '辛': ('금', '金'),
    '壬': ('수', '水'), '癸': ('수', '水'),
    '子': ('수', '水'), '丑': ('토', '土'),
    '寅': ('목', '木'), '卯': ('목', '木'),
    '辰': ('토', '土'), '巳': ('화', '火'),
    '午': ('화', '火'), '未': ('토', '土'),
    '申': ('금', '金'), '酉': ('금', '金'),
    '戌': ('토', '土'), '亥': ('수', '水'),
}

def get_hour_branch(hour):
    branches = earthly_branches
    index = ((hour + 1) // 2) % 12
    return branches[index]

def calculate_four_pillars(dt: datetime) -> dict:
    """사주 계산 함수"""
    day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    y_gz = day.getYearGZ(False)
    m_gz = day.getMonthGZ()
    d_gz = day.getDayGZ()
    h_gz = day.getHourGZ(dt.hour)

    return {
        "year": GAN[y_gz.tg] + ZHI[y_gz.dz],
        "month": GAN[m_gz.tg] + ZHI[m_gz.dz],
        "day": GAN[d_gz.tg] + ZHI[d_gz.dz],
        "hour": GAN[h_gz.tg] + ZHI[h_gz.dz],
    }

def generate_session_token(email):
    """세션 토큰 생성"""
    raw = f"{email}-{str(uuid.uuid4())}"
    return hashlib.sha256(raw.encode()).hexdigest()

def format_fortune_text(text):
    """운세 텍스트 포맷팅"""
    sentences = re.split(r'(?<=[다요]\.)\s*', text.strip())
    result = []
    for sentence in sentences:
        sentence = re.sub(r'(재물|성공|조심|노력|행운|사랑|건강|위험)', r'<b>\1</b>', sentence)
        if sentence:
            result.append(sentence.strip())
    return '<br><br>'.join(result)

class SajuAnalyzer:
    """사주 분석 클래스"""
    def __init__(self):
        self.element_map = element_map
        self.elements_kr = ['목', '화', '토', '금', '수']

    def analyze_saju(self, year_pillar, month_pillar, day_pillar, time_pillar):
        """사주 분석"""
        pillars = [year_pillar, month_pillar, day_pillar, time_pillar]
        chars = []
        for p in pillars:
            if len(p) == 2:
                chars.extend([p[0], p[1]])
        
        # 오행 카운트
        counts = {el: 0 for el in self.elements_kr}
        for ch in chars:
            el = self.element_map.get(ch, ('', ''))[0]
            if el:
                counts[el] += 1
        
        # 간단한 해석
        max_el = max(counts, key=lambda k: counts[k])
        min_el = min(counts, key=lambda k: counts[k])
        max_val = counts[max_el]
        min_val = counts[min_el]
        
        analysis = f"오행 분포: " + ", ".join([f"{k}:{v}" for k,v in counts.items()])
        if max_val - min_val >= 2:
            analysis += f"<br>가장 강한 오행은 <b>{max_el}</b>({max_val}개), 가장 약한 오행은 <b>{min_el}</b>({min_val}개)입니다.<br>"
            analysis += f"{max_el}의 기운이 두드러지므로, {max_el}의 특성을 잘 살리고 {min_el}의 기운을 보완하면 좋겠습니다."
        else:
            analysis += "<br>오행의 균형이 비교적 잘 잡혀 있습니다."

        return analysis

def generate_saju_analysis(birthdate, birth_hour):
    """GPT를 이용한 사주 분석"""
    year = birthdate.year
    year_ganji = GAN[(year - 4) % 10] + ZHI[(year - 4) % 12]
    hour_branch = get_hour_branch(birth_hour)
    
    elements = [element_map[char][0] for char in year_ganji]
    elements.append(element_map[hour_branch][0])
    counts = {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0}
    for el in elements:
        counts[el] += 1
    
    element_lines = []
    for k, v in counts.items():
        hanja = {'목': '木', '화': '火', '토': '土', '금': '金', '수': '水'}[k]
        element_lines.append(f"- {k}({hanja}): {v}개")
    element_text = "\n".join(element_lines)

    prompt = f"""
당신은 명리학을 기반으로 해석하는 전문 사주 상담가입니다.

다음은 한 사용자의 사주 정보입니다:

- 연간지: {year_ganji}
- 시지: {hour_branch}
- 오행 분포:
{element_text}

이 사주의 오행 구성과 강약을 바탕으로, 이 사람의 성격적 특징, 재물운, 인생 흐름에 대해 300자 이내로 명료하고 따뜻하게 설명해주세요.
전문가의 조언처럼 신뢰감 있게 작성해주세요.
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 정확한 사주 해석 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            max_tokens=600
        )
        reply = response.choices[0].message.content
        return format_fortune_text(reply)
    except Exception as e:
        return f"⚠️ 오류 발생: {e}"

@router.get("/page1", response_class=HTMLResponse)
async def saju_page1(request: Request):
    """사주 입력 페이지"""
    default_year = 1984
    default_month = 1
    default_day = 1
    
    return templates.TemplateResponse("saju/page1.html", {
        "request": request,
        "default_year": default_year,
        "default_month": default_month,
        "default_day": default_day
    })

@router.post("/page1")
async def saju_page1_submit(
    request: Request,
    name: str = Form(""),
    gender: str = Form(...),
    birth_year: int = Form(...),
    birth_month: int = Form(...),
    birth_day: int = Form(...),
    birthhour: int = Form(...),
    db: Session = Depends(get_db)
):
    """사주 입력 처리"""
    birthdate = f"{birth_year:04d}-{birth_month:02d}-{birth_day:02d}"
    
    # 가상 이메일 생성
    email = f"saju_{uuid.uuid4().hex[:8]}@example.com"
    if not name.strip():
        name = "손님"

    session_token = generate_session_token(email)
    
    # 세션에 정보 저장
    request.session["saju_session_token"] = session_token
    request.session["saju_email"] = email
    request.session["saju_name"] = name
    request.session["saju_gender"] = gender
    request.session["saju_birthdate"] = birthdate
    request.session["saju_birthhour"] = birthhour

    return RedirectResponse(url="/saju/page2", status_code=302)

@router.get("/page2", response_class=HTMLResponse)
async def saju_page2(request: Request, db: Session = Depends(get_db)):
    """사주 결과 페이지"""
    if "saju_session_token" not in request.session:
        return RedirectResponse(url="/saju/page1", status_code=302)

    name = request.session.get("saju_name", "손님")
    birthdate_str = request.session.get("saju_birthdate")
    birth_hour = int(request.session.get("saju_birthhour", 12))

    try:
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
    except:
        birthdate = datetime.now()

    # 사주 계산
    pillars = calculate_four_pillars(datetime(birthdate.year, birthdate.month, birthdate.day, birth_hour))
    
    # 사주 분석
    analyzer = SajuAnalyzer()
    saju_analyzer_result = analyzer.analyze_saju(
        pillars['year'], pillars['month'], pillars['day'], pillars['hour']
    )

    return templates.TemplateResponse("saju/page2.html", {
        "request": request,
        "name": name,
        "pillars": pillars,
        "saju_analyzer_result": saju_analyzer_result,
        "birth_hour": birth_hour,
        "birthdate": birthdate
    })

@router.post("/api/ai_analysis")
async def saju_ai_analysis(request: Request):
    """AI 사주 분석 API"""
    if "saju_session_token" not in request.session:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 캐시 확인
    if "cached_saju_analysis" in request.session:
        return {"result": request.session["cached_saju_analysis"]}

    birthdate_str = request.session.get("saju_birthdate")
    birth_hour = int(request.session.get("saju_birthhour", 12))

    try:
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid birthdate")

    # AI 분석 실행
    try:
        analysis = generate_saju_analysis(birthdate, birth_hour)
        request.session["cached_saju_analysis"] = analysis
        return {"result": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))