# app/routers/saju.py - 완전한 작동 버전

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, Category, SajuUser, SajuAnalysisCache, SajuInterpretation
from app.template import templates
from datetime import datetime, timedelta
import uuid
import hashlib
import re
import sxtwl
import os
import secrets
from markdown import markdown
import requests
# Use SQLAlchemy ORM to query saju_wiki_contents
from app.database import SessionLocal
from app.models import SajuWikiContent
# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter(prefix="/saju")

def safe_markdown(value):
    if not value:
        return ""
    return markdown(value.replace('\n', '<br>'))


####################################################################
# 기존 사주팔자 및 십성 계산 로직을 포함한 모듈
# 천간/지지 계산 (중국 한자)
heavenly_stems = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
earthly_branches = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

GAN = heavenly_stems
ZHI = earthly_branches

# 오행 매핑 (완전 버전)
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

# === 십성 계산 ===
def stem_to_element_yinyang(stem):
    """천간을 오행/음양으로 변환"""
    mapping = {
        '甲': ('wood', 'yang'), '乙': ('wood', 'yin'),
        '丙': ('fire', 'yang'), '丁': ('fire', 'yin'),
        '戊': ('earth', 'yang'), '己': ('earth', 'yin'),
        '庚': ('metal', 'yang'), '辛': ('metal', 'yin'),
        '壬': ('water', 'yang'), '癸': ('water', 'yin'),
    }
    return mapping.get(stem, ('?', '?'))

# 십성 매핑 테이블 (완전 버전)
TEN_GOD_MAP = {
    # 木(양)
    ('wood', 'yang', 'wood', 'yang'): '비견',
    ('wood', 'yang', 'wood', 'yin'): '겁재',
    ('wood', 'yang', 'fire', 'yang'): '식신',
    ('wood', 'yang', 'fire', 'yin'): '상관',
    ('wood', 'yang', 'earth', 'yang'): '편재',
    ('wood', 'yang', 'earth', 'yin'): '정재',
    ('wood', 'yang', 'metal', 'yang'): '편관',
    ('wood', 'yang', 'metal', 'yin'): '정관',
    ('wood', 'yang', 'water', 'yang'): '편인',
    ('wood', 'yang', 'water', 'yin'): '정인',
    # 木(음)
    ('wood', 'yin', 'wood', 'yang'): '겁재',
    ('wood', 'yin', 'wood', 'yin'): '비견',
    ('wood', 'yin', 'fire', 'yang'): '상관',
    ('wood', 'yin', 'fire', 'yin'): '식신',
    ('wood', 'yin', 'earth', 'yang'): '정재',
    ('wood', 'yin', 'earth', 'yin'): '편재',
    ('wood', 'yin', 'metal', 'yang'): '정관',
    ('wood', 'yin', 'metal', 'yin'): '편관',
    ('wood', 'yin', 'water', 'yang'): '정인',
    ('wood', 'yin', 'water', 'yin'): '편인',
    # 火(양)
    ('fire', 'yang', 'wood', 'yang'): '정인',
    ('fire', 'yang', 'wood', 'yin'): '편인',
    ('fire', 'yang', 'fire', 'yang'): '비견',
    ('fire', 'yang', 'fire', 'yin'): '겁재',
    ('fire', 'yang', 'earth', 'yang'): '식신',
    ('fire', 'yang', 'earth', 'yin'): '상관',
    ('fire', 'yang', 'metal', 'yang'): '편재',
    ('fire', 'yang', 'metal', 'yin'): '정재',
    ('fire', 'yang', 'water', 'yang'): '편관',
    ('fire', 'yang', 'water', 'yin'): '정관',
    # 火(음)
    ('fire', 'yin', 'wood', 'yang'): '편인',
    ('fire', 'yin', 'wood', 'yin'): '정인',
    ('fire', 'yin', 'fire', 'yang'): '겁재',
    ('fire', 'yin', 'fire', 'yin'): '비견',
    ('fire', 'yin', 'earth', 'yang'): '상관',
    ('fire', 'yin', 'earth', 'yin'): '식신',
    ('fire', 'yin', 'metal', 'yang'): '정재',
    ('fire', 'yin', 'metal', 'yin'): '편재',
    ('fire', 'yin', 'water', 'yang'): '정관',
    ('fire', 'yin', 'water', 'yin'): '편관',
    # 土(양)
    ('earth', 'yang', 'wood', 'yang'): '편관',
    ('earth', 'yang', 'wood', 'yin'): '정관',
    ('earth', 'yang', 'fire', 'yang'): '정인',
    ('earth', 'yang', 'fire', 'yin'): '편인',
    ('earth', 'yang', 'earth', 'yang'): '비견',
    ('earth', 'yang', 'earth', 'yin'): '겁재',
    ('earth', 'yang', 'metal', 'yang'): '식신',
    ('earth', 'yang', 'metal', 'yin'): '상관',
    ('earth', 'yang', 'water', 'yang'): '편재',
    ('earth', 'yang', 'water', 'yin'): '정재',
    # 土(음)
    ('earth', 'yin', 'wood', 'yang'): '정관',
    ('earth', 'yin', 'wood', 'yin'): '편관',
    ('earth', 'yin', 'fire', 'yang'): '편인',
    ('earth', 'yin', 'fire', 'yin'): '정인',
    ('earth', 'yin', 'earth', 'yang'): '겁재',
    ('earth', 'yin', 'earth', 'yin'): '비견',
    ('earth', 'yin', 'metal', 'yang'): '상관',
    ('earth', 'yin', 'metal', 'yin'): '식신',
    ('earth', 'yin', 'water', 'yang'): '정재',
    ('earth', 'yin', 'water', 'yin'): '편재',
    # 金(양)
    ('metal', 'yang', 'wood', 'yang'): '정재',
    ('metal', 'yang', 'wood', 'yin'): '편재',
    ('metal', 'yang', 'fire', 'yang'): '편관',
    ('metal', 'yang', 'fire', 'yin'): '정관',
    ('metal', 'yang', 'earth', 'yang'): '정인',
    ('metal', 'yang', 'earth', 'yin'): '편인',
    ('metal', 'yang', 'metal', 'yang'): '비견',
    ('metal', 'yang', 'metal', 'yin'): '겁재',
    ('metal', 'yang', 'water', 'yang'): '식신',
    ('metal', 'yang', 'water', 'yin'): '상관',
    # 金(음)
    ('metal', 'yin', 'wood', 'yang'): '편재',
    ('metal', 'yin', 'wood', 'yin'): '정재',
    ('metal', 'yin', 'fire', 'yang'): '정관',
    ('metal', 'yin', 'fire', 'yin'): '편관',
    ('metal', 'yin', 'earth', 'yang'): '편인',
    ('metal', 'yin', 'earth', 'yin'): '정인',
    ('metal', 'yin', 'metal', 'yang'): '겁재',
    ('metal', 'yin', 'metal', 'yin'): '비견',
    ('metal', 'yin', 'water', 'yang'): '상관',
    ('metal', 'yin', 'water', 'yin'): '식신',
    # 水(양)
    ('water', 'yang', 'wood', 'yang'): '상관',
    ('water', 'yang', 'wood', 'yin'): '식신',
    ('water', 'yang', 'fire', 'yang'): '정재',
    ('water', 'yang', 'fire', 'yin'): '편재',
    ('water', 'yang', 'earth', 'yang'): '편관',
    ('water', 'yang', 'earth', 'yin'): '정관',
    ('water', 'yang', 'metal', 'yang'): '정인',
    ('water', 'yang', 'metal', 'yin'): '편인',
    ('water', 'yang', 'water', 'yang'): '비견',
    ('water', 'yang', 'water', 'yin'): '겁재',
    # 水(음)
    ('water', 'yin', 'wood', 'yang'): '식신',
    ('water', 'yin', 'wood', 'yin'): '상관',
    ('water', 'yin', 'fire', 'yang'): '편재',
    ('water', 'yin', 'fire', 'yin'): '정재',
    ('water', 'yin', 'earth', 'yang'): '정관',
    ('water', 'yin', 'earth', 'yin'): '편관',
    ('water', 'yin', 'metal', 'yang'): '편인',
    ('water', 'yin', 'metal', 'yin'): '정인',
    ('water', 'yin', 'water', 'yang'): '겁재',
    ('water', 'yin', 'water', 'yin'): '비견',
}

def get_ten_god(day_stem, compare_stem):
    """십성 계산 (오행과 음양 기반)"""
    self_element, self_yin_yang = stem_to_element_yinyang(day_stem)
    other_element, other_yin_yang = stem_to_element_yinyang(compare_stem)
    return TEN_GOD_MAP.get((self_element, self_yin_yang, other_element, other_yin_yang), '')

# 십이신살 테이블
twelve_gods_table = {
    "寅午戌": ["亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌"],
    "巳酉丑": ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"],
    "申子辰": ["巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑", "寅", "卯", "辰"],
    "亥卯未": ["申", "酉", "戌", "亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未"]
}

twelve_gods_labels = [
    "지살", "천살", "역마", "육해", "화개", "겁살",
    "재살", "천역마", "월살", "망신", "장성", "반안"
]

def get_twelve_gods_group(zhi):
    """일지 기준으로 해당 그룹 반환"""
    for group, order in twelve_gods_table.items():
        if zhi in group:
            return group, order
    return None, []

def get_twelve_gods_by_day_branch(day_branch):
    """십이신살 계산"""
    result = {}
    group, order = get_twelve_gods_group(day_branch)
    if not order:
        return result
    for i, label in enumerate(twelve_gods_labels):
        result[label] = order[i]
    return result
    

# 역방향 십이신살 매핑
reverse_twelve_gods_table = {
    '寅午戌': {
        '亥': '지살', '子': '천살', '丑': '역마', '寅': '육해', '卯': '화개', '辰': '겁살',
        '巳': '재살', '午': '천역마', '未': '월살', '申': '망신', '酉': '장성', '戌': '반안'
    },
    '申子辰': {
        '巳': '지살', '午': '천살', '未': '역마', '申': '육해', '酉': '화개', '戌': '겁살',
        '亥': '재살', '子': '천역마', '丑': '월살', '寅': '망신', '卯': '장성', '辰': '반안'
    },
    '亥卯未': {
        '申': '지살', '酉': '천살', '戌': '역마', '亥': '육해', '子': '화개', '丑': '겁살',
        '寅': '재살', '卯': '천역마', '辰': '월살', '巳': '망신', '午': '장성', '未': '반안'
    },
    '巳酉丑': {
        '寅': '지살', '卯': '천살', '辰': '역마', '巳': '육해', '午': '화개', '未': '겁살',
        '申': '재살', '酉': '천역마', '戌': '월살', '亥': '망신', '子': '장성', '丑': '반안'
    }
}

def get_my_twelve_god(zhi, day_branch):
    """내 지지가 어떤 신살에 해당하는가"""
    for group, mapping in reverse_twelve_gods_table.items():
        if day_branch in group:
            return mapping.get(zhi)
    return None

# 십이운성 표
twelve_stage_table = {
    '甲': {'子': '절', '丑': '태', '寅': '양', '卯': '장생', '辰': '목욕', '巳': '관대', '午': '건록', '未': '제왕', '申': '쇠', '酉': '병', '戌': '사', '亥': '묘'},
    '乙': {'子': '묘', '丑': '절', '寅': '태', '卯': '양', '辰': '장생', '巳': '목욕', '午': '관대', '未': '건록', '申': '제왕', '酉': '쇠', '戌': '병', '亥': '사'},
    '丙': {'寅': '장생', '卯': '목욕', '辰': '관대', '巳': '건록', '午': '제왕', '未': '쇠', '申': '병', '酉': '사', '戌': '묘', '亥': '절', '子': '태', '丑': '양'},
    '丁': {'寅': '묘', '卯': '장생', '辰': '목욕', '巳': '관대', '午': '건록', '未': '제왕', '申': '쇠', '酉': '병', '戌': '사', '亥': '묘', '子': '절', '丑': '태'},
    '戊': {'巳': '장생', '午': '목욕', '未': '관대', '申': '건록', '酉': '제왕', '戌': '쇠', '亥': '병', '子': '사', '丑': '묘', '寅': '절', '卯': '태', '辰': '양'},
    '己': {'巳': '묘', '午': '장생', '未': '목욕', '申': '관대', '酉': '건록', '戌': '제왕', '亥': '쇠', '子': '병', '丑': '사', '寅': '묘', '卯': '절', '辰': '태'},
    '庚': {'申': '장생', '酉': '목욕', '戌': '관대', '亥': '건록', '子': '제왕', '丑': '쇠', '寅': '병', '卯': '사', '辰': '묘', '巳': '절', '午': '태', '未': '양'},
    '辛': {'申': '묘', '酉': '장생', '戌': '목욕', '亥': '관대', '子': '건록', '丑': '제왕', '寅': '쇠', '卯': '병', '辰': '사', '巳': '묘', '午': '절', '未': '태'},
    '壬': {'亥': '장생', '子': '목욕', '丑': '관대', '寅': '건록', '卯': '제왕', '辰': '쇠', '巳': '병', '午': '사', '未': '묘', '申': '절', '酉': '태', '戌': '양'},
    '癸': {'亥': '묘', '子': '장생', '丑': '목욕', '寅': '관대', '卯': '건록', '辰': '제왕', '巳': '쇠', '午': '병', '未': '사', '申': '묘', '酉': '절', '戌': '태'},
}

def get_twelve_stage(day_gan, branch):
    """십이운성 계산 함수"""
    return twelve_stage_table.get(day_gan, {}).get(branch, '')

def get_hour_branch(hour):
    """시간대에서 지지 계산"""
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

def get_saju_details(pillars):
    """사주 각 기둥에 대한 세부 정보 정리"""
    day_gan = pillars['day'][0]  # 일간 기준
    saju_info = {}

    # 전체 지장간(藏干) 매핑
    hidden_gan_dict = {
        '子': ['癸'],
        '丑': ['己', '癸', '辛'],
        '寅': ['甲', '丙', '戊'],
        '卯': ['乙'],
        '辰': ['戊', '乙', '癸'],
        '巳': ['丙', '戊', '庚'],
        '午': ['丁', '己'],
        '未': ['己', '丁', '乙'],
        '申': ['庚', '壬', '戊'],
        '酉': ['辛'],
        '戌': ['戊', '辛', '丁'],
        '亥': ['壬', '甲']
    }

    for pillar_name in ['year', 'month', 'day', 'hour']:
        gan = pillars[pillar_name][0]
        zhi = pillars[pillar_name][1]
        el_gan, yin_gan = element_map.get(gan, ('?', '?'))
        el_zhi, yin_zhi = element_map.get(zhi, ('?', '?'))
        
        # 십성 계산 (일간 기준)
        ten_god = get_ten_god(day_gan, gan)
        
        # 지지의 모든 지장간으로 십성 계산
        hidden_gans = hidden_gan_dict.get(zhi, [])
        ten_god_zhi = [get_ten_god(day_gan, hg) for hg in hidden_gans]
        
        twelve_stage = get_twelve_stage(day_gan, zhi)
        twelve_god = get_my_twelve_god(zhi, pillars['day'][1])

        saju_info[pillar_name] = {
            'gan': gan,
            'zhi': zhi,
            'element_gan': el_gan,
            'yin_gan': yin_gan,
            'element_zhi': el_zhi,
            'yin_zhi': yin_zhi,
            'ten_god': ten_god,
            'ten_god_zhi': ', '.join(ten_god_zhi),
            'twelve_stage': twelve_stage,
            'twelve_god': twelve_god
        }

    return saju_info
# 기존 사주팔자 및 십성 계산 로직을 포함한 모듈 끝
####################################################################

####################################################################
# 새로운 사주 해석 및 운세 관련 로직
# 사주 4주 십신 자동 분석기 (지지 + 정통 격국/용신/희신)
# 정통 격국 성립 판단 추가: 得令, 通氣, 得地 기준 반영

# 오행 구분표
stem_elements = {
    '甲': '목', '乙': '목', '丙': '화', '丁': '화',
    '戊': '토', '己': '토', '庚': '금', '辛': '금',
    '壬': '수', '癸': '수'
}

# 음양 구분표
stem_yinyang = {
    '甲': '양', '乙': '음', '丙': '양', '丁': '음',
    '戊': '양', '己': '음', '庚': '양', '辛': '음',
    '壬': '양', '癸': '음'
}

sheng = {'목': '화', '화': '토', '토': '금', '금': '수', '수': '목'}
ke = {'목': '토', '토': '수', '수': '화', '화': '금', '금': '목'}

branch_hidden_stems = {
    '子': ['癸'], '丑': ['己', '癸', '辛'], '寅': ['甲', '丙', '戊'],
    '卯': ['乙'], '辰': ['戊', '乙', '癸'], '巳': ['丙', '庚', '戊'],
    '午': ['丁', '己'], '未': ['己', '丁', '乙'], '申': ['庚', '壬', '戊'],
    '酉': ['辛'], '戌': ['戊', '辛', '丁'], '亥': ['壬', '甲']
}

# 십신 판단 함수
def get_sipsin(day_gan, target_gan):
    day_elem = stem_elements[day_gan]
    day_yy = stem_yinyang[day_gan]
    target_elem = stem_elements[target_gan]
    target_yy = stem_yinyang[target_gan]
    if day_elem == target_elem:
        return '비견' if day_yy == target_yy else '겁재'
    elif sheng[day_elem] == target_elem:
        return '식신' if day_yy == target_yy else '상관'
    elif sheng[target_elem] == day_elem:
        return '정인' if day_yy != target_yy else '편인'
    elif ke[day_elem] == target_elem:
        return '정재' if day_yy != target_yy else '편재'
    elif ke[target_elem] == day_elem:
        return '정관' if day_yy != target_yy else '칠살'
    return '관계 없음'

# 격국 및 용신/희신 판단 (정통 방식: 得令, 通氣, 得地 고려)
def guess_gek_guk_yongshin(day_gan, month_branch, month_gan, day_branch, hour_branch):
    day_elem = stem_elements[day_gan]
    month_stems = branch_hidden_stems.get(month_branch, [])
    all_hidden = month_stems + branch_hidden_stems.get(day_branch, []) + branch_hidden_stems.get(hour_branch, [])
    heavenly_stems = [month_gan]

    freq = {}
    for s in month_stems:
        el = stem_elements[s]
        freq[el] = freq.get(el, 0) + 1
    max_elem = max(freq, key=freq.get, default=None)

    # 격 판단
    if not max_elem:
        return '혼잡격', None, [], []

    if sheng[max_elem] == day_elem:
        gek = '인성격'
    elif sheng[day_elem] == max_elem:
        gek = '식상격'
    elif ke[day_elem] == max_elem:
        gek = '재격'
    elif ke[max_elem] == day_elem:
        gek = '관격'
    else:
        gek = '혼잡격'

    # 得令: 월지 지장간에 용신 있음
    deokryeong = max_elem in [stem_elements[s] for s in month_stems]
    # 通氣: 천간에 용신이 있음
    tonggi = max_elem in [stem_elements[s] for s in heavenly_stems]
    # 得地: 일지/시지에 용신 있음
    deokji = max_elem in [stem_elements[s] for s in all_hidden]

    # 용신 = 격국의 중심 오행
    yong = max_elem
    heesin = [sheng[day_elem], ke[day_elem]]
    gishin = [ke[max_elem]] if max_elem in ke else []

    return gek + (" (得令)" if deokryeong else "") + (" (通氣)" if tonggi else "") + (" (得地)" if deokji else ""), yong, heesin, gishin

# 전체 분석

def analyze_four_pillars_with_branches(year_gan, year_branch, month_gan, month_branch, day_gan, day_branch, hour_gan, hour_branch):
    print("=== 사주 정보 ===")
    print(f"년주: {year_gan} {year_branch} (지장간: {', '.join(branch_hidden_stems.get(year_branch, []))})")
    print(f"월주: {month_gan} {month_branch} (지장간: {', '.join(branch_hidden_stems.get(month_branch, []))})")
    print(f"일주: {day_gan} {day_branch} (지장간: {', '.join(branch_hidden_stems.get(day_branch, []))})")
    print(f"시주: {hour_gan} {hour_branch} (지장간: {', '.join(branch_hidden_stems.get(hour_branch, []))})")

    print("\n십신 관계:")
    if year_gan:
        print(f"- 년간: {get_sipsin(day_gan, year_gan)}")
    print(f"- 년지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(year_branch, [])])}")
    if month_gan:
        print(f"- 월간: {get_sipsin(day_gan, month_gan)}")
    print(f"- 월지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(month_branch, [])])}")
    print(f"- 일지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(day_branch, [])])}")
    if hour_gan:
        print(f"- 시간: {get_sipsin(day_gan, hour_gan)}")
    print(f"- 시지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(hour_branch, [])])}")

    gek, yong, heesin_list, gishin_list = guess_gek_guk_yongshin(
        day_gan, month_branch, month_gan, day_branch, hour_branch
    )
    print("\n격국:", gek)
    print("용신:", yong)
    print("희신:", ', '.join(heesin_list) if heesin_list else '없음')
    print("기신:", ', '.join(gishin_list) if gishin_list else '없음')

def analyze_four_pillars_to_string(
    year_gan, year_branch,
    month_gan, month_branch,
    day_gan, day_branch,
    hour_gan, hour_branch,
):
    """
    Returns
    -------
    tuple (dict, str)
        counts_kr : {'목':n, '화':n, '토':n, '금':n, '수':n}
        full_text : legacy multiline explanation text
    """
    # ── 오행 분포 계산 ─────────────────────────
    counts_kr = {'목': 0, '화': 0, '토': 0, '금': 0, '수': 0}
    for ch in [
        year_gan, year_branch,
        month_gan, month_branch,
        day_gan, day_branch,
        hour_gan, hour_branch,
    ]:
        elem = element_map.get(ch)  # element_map must exist globally
        if elem:
            counts_kr[elem[0]] += 1
    # ─────────────────────────────────────────

    lines: list[str] = []
    lines.append("=== 사주 정보 ===")
    lines.append(f"년주: {year_gan} {year_branch} (지장간: {', '.join(branch_hidden_stems.get(year_branch, []))})")
    lines.append(f"월주: {month_gan} {month_branch} (지장간: {', '.join(branch_hidden_stems.get(month_branch, []))})")
    lines.append(f"일주: {day_gan} {day_branch} (지장간: {', '.join(branch_hidden_stems.get(day_branch, []))})")
    lines.append(f"시주: {hour_gan} {hour_branch} (지장간: {', '.join(branch_hidden_stems.get(hour_branch, []))})")

    lines.append("\n십신 관계:")
    if year_gan:
        lines.append(f"- 년간: {get_sipsin(day_gan, year_gan)}")
    lines.append(f"- 년지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(year_branch, [])])}")
    if month_gan:
        lines.append(f"- 월간: {get_sipsin(day_gan, month_gan)}")
    lines.append(f"- 월지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(month_branch, [])])}")
    lines.append(f"- 일지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(day_branch, [])])}")
    if hour_gan:
        lines.append(f"- 시간: {get_sipsin(day_gan, hour_gan)}")
    lines.append(f"- 시지 지장간: {', '.join([f'{h}: {get_sipsin(day_gan, h)}' for h in branch_hidden_stems.get(hour_branch, [])])}")

    gek, yong, heesin_list, gishin_list = guess_gek_guk_yongshin(
        day_gan, month_branch, month_gan, day_branch, hour_branch
    )
    lines.append("\n격국: " + gek)
    lines.append("용신: " + str(yong))
    lines.append("희신: " + (', '.join(heesin_list) if heesin_list else '없음'))
    lines.append("기신: " + (', '.join(gishin_list) if gishin_list else '없음'))

    full_text = "\n".join(lines)
    return counts_kr, full_text

## 끝
#####################################################################
####################################################################
# 일주 해석 조회 함수
def get_ilju_interpretation(ilju):
    """일주 해석 조회 (MySQL via SQLAlchemy)"""
    try:
        db = SessionLocal()
        row = (
            db.query(SajuInterpretation)
            .filter(SajuInterpretation.ilju == ilju)
            .first()
        )
        db.close()

        if row:
            cn = row.cn.replace('\n', '<br>') if row.cn else None
            kr = row.kr.replace('\n', '<br>') if row.kr else None
            en = row.en.replace('\n', '<br>') if row.en else None
            return {"cn": cn, "kr": kr, "en": en}
        else:
            return {"cn": None, "kr": None, "en": None}
    except Exception as e:
        print(f"⚠️ 일주 해석 DB 조회 오류: {e}")
        return {"cn": None, "kr": None, "en": None}

# 삼명통회 원문 매칭 함수
def get_ctext_match(day_pillar, hour_pillar):
    """삼명통회 원문 매칭
    우선순위: (1) 완전 일치 ‑ 甲子日子 처럼 일·시가 모두 있는 형태
             (2) 간략 일치 ‑ 甲日子 처럼 일간만 있는 형태
    완전 일치가 발견되면 그 결과를 그대로 사용하고,
    없을 때만 간략 일치를 시도한다.
    """
    full_kw = f"{day_pillar}日{hour_pillar}"       # 예: 甲子日子
    stem_kw = f"{day_pillar[0]}日{hour_pillar}"    # 예: 甲日子

    try:
        db = SessionLocal()

        # 1️⃣ 완전 일치 우선 검색
        rows = (
            db.query(SajuWikiContent)
            .filter(SajuWikiContent.content.like(f"%{full_kw}%"))
            .all()
        )

        # 2️⃣ 결과가 없으면 간략 일치로 재검색
        if not rows:
            rows = (
                db.query(SajuWikiContent)
                .filter(SajuWikiContent.content.like(f"%{stem_kw}%"))
                .all()
            )

        db.close()

        if not rows:
            return None

        # 중복 content 제거 후 필요한 필드만 반환
        seen = set()
        result = []
        for r in rows:
            if r.content in seen:
                continue
            seen.add(r.content)
            result.append({
                "content": r.content,
                "kr_literal": r.kr_literal,
                "kr_explained": r.kr_explained
            })
        return result

    except Exception as e:
        print(f"⚠️ ctext.db 연결 오류: {e}")
        return None

# ai 1차 사주 분석이후 포맷을 입히는 함수
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
        self.element_map = {
            '甲': '목', '乙': '목', '丙': '화', '丁': '화', '戊': '토', '己': '토',
            '庚': '금', '辛': '금', '壬': '수', '癸': '수', '子': '수', '丑': '토',
            '寅': '목', '卯': '목', '辰': '토', '巳': '화', '午': '화', '未': '토',
            '申': '금', '酉': '금', '戌': '토', '亥': '수',
        }
        self.elements_kr = ['목', '화', '토', '금', '수']

    def analyze_saju(self, year_pillar, month_pillar, day_pillar, time_pillar):
        """네 기둥의 오행 분포와 간단한 해석"""
        pillars = [year_pillar, month_pillar, day_pillar, time_pillar]
        chars = []
        for p in pillars:
            if len(p) == 2:
                chars.extend([p[0], p[1]])
                
        # 오행 카운트
        counts = {el: 0 for el in self.elements_kr}
        for ch in chars:
            el = self.element_map.get(ch)
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

def generate_session_token(email):
    """세션 토큰 생성"""
    raw = f"{email}-{str(uuid.uuid4())}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ai 사주분석 초기버전
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
        response = client.chat.completions.create(
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

# ai 사주 첫페이지
@router.get("/page1", response_class=HTMLResponse)
async def saju_page1(request: Request):
    """사주 입력 페이지"""
    # 로그인 세션 확인
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=302)
    
    default_year = 1984
    default_month = 1
    default_day = 1
    
    return templates.TemplateResponse("saju/page1.html", {
        "request": request,
        "default_year": default_year,
        "default_month": default_month,
        "default_day": default_day
    })

# ai 사주 post 처리
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
    # ── NEW: generate saju_key (date_hour_gender) ──
    saju_key = f"{birthdate}_{birthhour}_{gender}"
    
    session_token = generate_session_token(request.session.get("user_id"))
    
    # 세션에 정보 저장
    request.session["session_token"] = session_token
    request.session["name"] = name
    request.session["gender"] = gender
    request.session["birthdate"] = birthdate
    request.session["birthhour"] = birthhour
    request.session["saju_key"] = saju_key

    # Save the submitted form data into the saju_users table using SQLAlchemy
    new_user = SajuUser(
        name=name,
        gender=gender,
        birthdate=birthdate,
        birthhour=birthhour,
        saju_key=saju_key,
        session_token=session_token,
        user_id=request.session.get("user_id")
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/saju/page2", status_code=302)

# ai 사주 결과 페이지
@router.get("/page2", response_class=HTMLResponse)
async def saju_page2(request: Request, db: Session = Depends(get_db)):
    """사주 결과 페이지"""
    if "session_token" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    name = request.session.get("name", "손님")
    birthdate_str = request.session.get("birthdate")
    birth_hour = int(request.session.get("birthhour", 12))

    try:
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
    except:
        birthdate = datetime.now()

    # 사주 계산
    pillars = calculate_four_pillars(datetime(birthdate.year, birthdate.month, birthdate.day, birth_hour))
    
    # 상세 사주 정보 계산
    saju_info = get_saju_details(pillars)
    # saju_key was already created in page1 and stored in session
    saju_key = request.session.get("saju_key")

    # ----- CSRF Token -----
    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(16)
        request.session["csrf_token"] = csrf_token

    # 일주 해석
    ilju = pillars["day"]
    ilju_interpretation = get_ilju_interpretation(ilju)

    # 사주 분석
    analyzer = SajuAnalyzer()
    saju_analyzer_result = analyzer.analyze_saju(
        pillars['year'], pillars['month'], pillars['day'], pillars['hour']
    )

    # 삼명통회 원문 해석
    ctext_rows = get_ctext_match(pillars["day"], pillars["hour"])
    ctext_explanation = None
    ctext_kr_literal = None
    ctext_kr_explained = None
    if ctext_rows:
        ctext_explanation = "\n\n".join([row["content"] for row in ctext_rows])
        ctext_kr_literal = "\n\n".join([row["kr_literal"] for row in ctext_rows if row["kr_literal"]])
        ctext_kr_explained = "\n\n".join([row["kr_explained"] for row in ctext_rows if row["kr_explained"]])
    
    # 환경변수에서 후원 링크 가져오기
    coffee_link = os.getenv("BUY_ME_A_COFFEE_LINK", "https://www.buymeacoffee.com/yourname")

    return templates.TemplateResponse("saju/page2.html", {
        "request": request,
        "name": name,
        "pillars": pillars,
        "saju_info": saju_info,
        "saju_key": saju_key,
        "csrf_token": csrf_token,
        "ilju": ilju,
        "ilju_interpretation": ilju_interpretation,
        "saju_analyzer_result": saju_analyzer_result,
        "ctext_explanation": ctext_explanation,
        "ctext_kr_literal": ctext_kr_literal,
        "ctext_kr_explained": safe_markdown(ctext_kr_explained),
        "coffee_link": coffee_link,
        "get_twelve_gods_by_day_branch": get_twelve_gods_by_day_branch,
        "birth_hour": birth_hour,
        "birthdate": birthdate
    })

# AI 사주 분석 초기버전 API
@router.post("/api/saju_ai_analysis")
async def api_saju_ai_analysis(request: Request, db: Session = Depends(get_db)):
    """AI 사주 분석 API"""
    request.session.pop("cached_saju_analysis", None)
    # print("✅ OpenAI client is set:", bool(client))
    #print("▶ client.api_key =", client.api_key)

    if "session_token" not in request.session:
        request.session["session_token"] = secrets.token_hex(16)

    # === DB 캐시 확인 ===
    birthdate_str = request.session.get("birthdate")
    birth_hour = int(request.session.get("birthhour", 12))

    # gender = request.session.get("gender", "unknown")
    saju_key = request.session.get("saju_key")

    # DB 캐시 확인
    cached_row = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
    if cached_row and cached_row.analysis_preview:
        return {"result": safe_markdown(cached_row.analysis_preview)}

    try:
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid birthdate")

    # 사주팔자가져오기
    pillars = calculate_four_pillars(datetime(birthdate.year, birthdate.month, birthdate.day, birth_hour))
    # saju_info = get_saju_details(pillars)

    # 원문 해석과 일주 해석 병합
    ilju = pillars["day"]
    ilju_interpretation = get_ilju_interpretation(ilju)
    ilju_kr = ilju_interpretation.get("kr", "")

    # 삼명통회 해석  검색하여 가져오기
    ctext_rows = get_ctext_match(pillars["day"], pillars["hour"])
    ctext = ""
    if ctext_rows:
        ctext = "\n\n".join([row["content"] for row in ctext_rows])

    # 오행/십성 분석
    analyzer = SajuAnalyzer()
    saju_analyzer_result = analyzer.analyze_saju(
        pillars['year'], pillars['month'], pillars['day'], pillars['hour']
    )

    # GPT에게 전달할 통합 프롬프트 구성
    prompt = f"""
당신은 사주 해석 전문가입니다.
다음은 한 사람의 사주 정보입니다:

- 일주: {ilju}
- 일주 해석 (DB): {ilju_kr}
- 삼명통회 원문: {ctext}
- 오행/십성 해석: {saju_analyzer_result}

이 정보를 종합하여, 이 사람의 인생 전반적 특성과 강점, 유의사항을 300자 내외로 종합 해석해주세요.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 전문 사주 해석가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=600
        )
        reply = format_fortune_text(response.choices[0].message.content)
        # DB에 preview 저장 (analysis_preview 컬럼)
        try:
            row = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
            if row:
                row.analysis_preview = reply
            else:
                db.add(SajuAnalysisCache(
                    saju_key=saju_key,
                    analysis_preview=reply
                ))
            db.commit()
        except Exception:
            db.rollback()
        return {"result": safe_markdown(reply)}
    except Exception as e:
        return {"error": str(e)}

###################################################################################
# AI 사주 2차 업그레이드 버전 API
# 프롬프트 파일 읽기

# 환경 변수에서 Ollama URL과 모델명 가져오기
OLLAMA_URL = os.getenv('OLLAMA_URL', "")  # .env에서 URL 가져오기
MODEL_NAME = os.getenv('gemma3:27b-it-q8_0',"gemma3:27b-it-q8_0")  # 사용할 모델명
BATCH_SIZE = os.getenv('BATCH_SIZE', 10)  # 한 번에 처리할 레코드 수
DELAY_BETWEEN_REQUESTS = os.getenv('DELAY_BETWEEN_REQUESTS', 2)  # 요청 간 딜레이 (초)

def load_prompt():
    """improved_saju_prompt_v2.md 파일에서 프롬프트 로드"""
    try:
        with open('improved_saju_prompt_v2.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print("❌ improved_saju_prompt_v2.md 파일을 찾을 수 없습니다.")
        return None
def test_ollama_connection():
    """ollama 서버 연결 테스트"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            if MODEL_NAME in model_names:
                print(f"✅ ollama 연결 성공 및 {MODEL_NAME} 모델 확인됨")
                return True
            else:
                print(f"❌ {MODEL_NAME} 모델을 찾을 수 없습니다.")
                print(f"사용 가능한 모델: {model_names}")
                return False
        else:
            print(f"❌ ollama 서버 응답 오류: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ ollama 서버 연결 실패: {e}")
        return False
def ai_sajupalja_with_ollama(prompt, content):
    """ollama를 사용하여 프롬프트에 기반하여 사주팔자 추리"""
    try:
        full_prompt = f"{prompt}\n\n다음 정보에 기반하여 사주팔자를 해석하세요:\n{content}"
        
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # 창의성보다 정확성 우선
                "num_predict": 3000,  # 최대 토큰 수
                "top_p": 0.9
            }
        }
        
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120  # 2분 타임아웃
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            print(f"❌ ollama API 오류: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ollama 요청 실패: {e}")
        return None
    except Exception as e:
        print(f"❌ 번역 중 오류: {e}")
        return None
    
@router.post("/api/saju_ai_analysis_2")
async def api_saju_ai_analysis_2(request: Request, db: Session = Depends(get_db)):
    """AI 사주 분석 API"""
    request.session.pop("cached_saju_analysis", None)

    # === DB 캐시 확인 ===
    birthdate_str = request.session.get("birthdate")
    birth_hour = int(request.session.get("birthhour", 12))

    # gender = request.session.get("gender", "unknown")
    saju_key = request.session.get("saju_key")

    # DB 캐시 확인
    cached_row = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
    if cached_row and cached_row.analysis_full:
        return {"result": safe_markdown(cached_row.analysis_full)}

    try:
        birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
        prompt = load_prompt()
        if not prompt:
            return
        # 2. ollama 연결 테스트
        if not test_ollama_connection():
            return
        # 사주팔자가져오기
        pillars = calculate_four_pillars(datetime(birthdate.year, birthdate.month, birthdate.day, birth_hour))

        # Use string-based analysis for result_text
        elem_line, result_text = analyze_four_pillars_to_string(
            pillars['year'][0], pillars['year'][1],
            pillars['month'][0], pillars['month'][1],
            pillars['day'][0], pillars['day'][1],
            pillars['hour'][0], pillars['hour'][1])
        analysis_result = ai_sajupalja_with_ollama(prompt=prompt, content=result_text)

        # DB에 캐시 저장 (analysis_full 컬럼)
        existing = db.query(SajuAnalysisCache).filter_by(saju_key=saju_key).first()
        if existing:
            existing.analysis_full = analysis_result
        else:
            db.add(SajuAnalysisCache(
                saju_key=saju_key,
                analysis_full=analysis_result
            ))
        db.commit()
        return {"result": safe_markdown(analysis_result)}
    except:
        raise HTTPException(status_code=400, detail="Invalid birthdate")

# AI 사주 2차 업그레이드 버전 API 끝
#######################################################################
