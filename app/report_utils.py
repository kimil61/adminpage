# app/report_utils.py (기존 파일에 추가)
import io
import base64
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import os
import random
from datetime import datetime
import hashlib
from typing import Tuple, List

# 한글 폰트 설정
def setup_korean_font():
    """
    Robust Korean font setup for matplotlib.
    1) Try to register well‑known system font files.
    2) Fallback to font family names that may already exist in the OS.
    """
    import matplotlib as mpl
    from matplotlib import font_manager
    import platform
    import pathlib

    # ---------- 1. Candidate font files ----------
    font_files = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",        # Ubuntu/Debian Nanum
        "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.otf",  # Noto Sans (Linux)
        "/Library/Fonts/AppleSDGothicNeo.ttc",                    # macOS user
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",             # macOS system
        "C:/Windows/Fonts/malgun.ttf",                            # Windows Malgun Gothic
    ]

    registered_font_name = None

    for fp in font_files:
        if pathlib.Path(fp).is_file():
            try:
                font_manager.fontManager.addfont(fp)
                registered_font_name = font_manager.FontProperties(fname=fp).get_name()
                break
            except Exception:
                continue

    # ---------- 2. Fallback by family name ----------
    if registered_font_name is None:
        fallback_names = [
            "NanumGothic",
            "Malgun Gothic",
            "Apple SD Gothic Neo",
            "Noto Sans CJK KR",
        ]
        for fam in fallback_names:
            try:
                mpl.rcParams["font.family"] = fam
                registered_font_name = fam
                break
            except Exception:
                continue

    # ---------- 3. Final fallback ----------
    if registered_font_name is None:
        registered_font_name = "DejaVu Sans"

    mpl.rcParams["font.family"] = registered_font_name
    mpl.rcParams["axes.unicode_minus"] = False

def radar_chart_base64(ratios: dict[str, int]) -> str:
    """오행 분포를 레이더 차트로 생성하여 base64 반환"""
    try:
        setup_korean_font()
        
        # 한글 라벨
        labels_kr = {
            'Wood': '목(木)', 'Fire': '화(火)', 'Earth': '토(土)', 
            'Metal': '금(金)', 'Water': '수(水)'
        }
        
        labels = [labels_kr.get(k, k) for k in ratios.keys()]
        values = list(ratios.values())
        
        # 값이 모두 0인 경우 기본값 설정
        if all(v == 0 for v in values):
            values = [1] * len(values)
        
        # 원형으로 닫기
        values += values[:1]
        angles = np.linspace(0, 2 * np.pi, len(values))
        
        # 차트 생성
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'polar': True})
        
        # 배경색과 스타일 설정
        ax.fill(angles, values, alpha=0.25, color='#8B5CF6')
        ax.plot(angles, values, linewidth=3, color='#7C3AED', marker='o', markersize=8)
        
        # 축 설정
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
        ax.set_ylim(0, max(values[:-1]) + 1 if max(values[:-1]) > 0 else 5)
        
        # 격자선 스타일
        ax.grid(True, alpha=0.3)
        ax.set_facecolor('#FAFAFA')
        
        # 제목 추가
        plt.title('오행 밸런스 분석', fontsize=16, fontweight='bold', pad=20, color='#374151')
        
        # 이미지를 base64로 변환
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150, facecolor='white')
        plt.close(fig)
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        print(f"레이더 차트 생성 실패: {e}")
        # 폴백: 간단한 막대 차트
        return create_simple_bar_chart(ratios)

def create_simple_bar_chart(ratios: dict[str, int]) -> str:
    """폴백용 간단한 막대 차트"""
    try:
        setup_korean_font()
        
        labels_kr = {
            'Wood': '목', 'Fire': '화', 'Earth': '토', 
            'Metal': '금', 'Water': '수'
        }
        
        labels = [labels_kr.get(k, k) for k in ratios.keys()]
        values = list(ratios.values())
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        colors = ['#10B981', '#EF4444', '#F59E0B', '#6B7280', '#3B82F6']
        bars = ax.bar(labels, values, color=colors[:len(labels)], alpha=0.8)
        
        # 값 표시
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{value}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylabel('개수', fontsize=12)
        ax.set_title('오행 분포', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close(fig)
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        print(f"막대 차트 생성도 실패: {e}")
        return ""

def month_heat_table(status: dict[str, list[str]]) -> str:
    """
    월별 운세 히트맵 테이블 생성
    status example:
        {
          'Love':  ['G','R','-','G','Y','-','G','Y','-','G','R','-'],
          'Money': ['-','G','R','Y','-','G','-','G','Y','-','G','R'],
          'Career':['Y','-','G','G','R','-','Y','-','G','Y','-','G']
        }
    """
    try:
        months = ['1월', '2월', '3월', '4월', '5월', '6월',
                  '7월', '8월', '9월', '10월', '11월', '12월']
        
        color_map = {
            'G': '#DCFCE7',   # 좋음 (연초록)
            'Y': '#FEFCE8',   # 주의 (연노랑)
            'R': '#FEE2E2',   # 조심 (연빨강)
            '-': '#F9FAFB',   # 보통 (연회색)
        }
        
        category_names = {
            'Love': '💕 애정운',
            'Money': '💰 재물운',
            'Career': '💼 직업운'
        }
        
        html = '<table class="mini-cal" style="width: 100%; border-collapse: collapse; margin: 15px 0;">'
        
        # 헤더 (월)
        html += '<tr style="background-color: #F3F4F6;">'
        html += '<th style="padding: 8px; border: 1px solid #D1D5DB; font-weight: bold;">구분</th>'
        for month in months:
            html += f'<th style="padding: 6px; border: 1px solid #D1D5DB; font-size: 11px; font-weight: bold;">{month}</th>'
        html += '</tr>'
        
        # 각 카테고리별 행
        for category, values in status.items():
            category_display = category_names.get(category, category)
            html += f'<tr>'
            html += f'<td style="padding: 8px; border: 1px solid #D1D5DB; font-weight: bold; background-color: #F9FAFB;">{category_display}</td>'
            
            for value in values:
                bg_color = color_map.get(value, '#FFFFFF')
                symbol = {'G': '●', 'Y': '▲', 'R': '■', '-': '○'}.get(value, '○')
                html += f'<td style="padding: 6px; border: 1px solid #D1D5DB; text-align: center; background-color: {bg_color}; font-size: 14px;">{symbol}</td>'
            
            html += '</tr>'
        
        html += '</table>'
        return html
        
    except Exception as e:
        print(f"월별 테이블 생성 실패: {e}")
        return '<p>월별 운세 표를 생성할 수 없습니다.</p>'

def keyword_card(color: str, numbers: list[int], stone: str) -> str:
    """행운 키워드 카드 생성"""
    try:
        nums = ", ".join(map(str, numbers))
        
        # 색상별 배경색 매핑
        color_bg_map = {
            '빨강': '#FEE2E2', '빨간색': '#FEE2E2',
            '파랑': '#DBEAFE', '파란색': '#DBEAFE', '블루': '#DBEAFE',
            '초록': '#D1FAE5', '녹색': '#D1FAE5', '그린': '#D1FAE5',
            '노랑': '#FEF3C7', '노란색': '#FEF3C7', '옐로우': '#FEF3C7',
            '보라': '#E9D5FF', '보라색': '#E9D5FF', '퍼플': '#E9D5FF',
            '자주': '#F3E8FF', '자주색': '#F3E8FF',
            '주황': '#FED7AA', '주황색': '#FED7AA', '오렌지': '#FED7AA',
            '분홍': '#FCE7F3', '핑크': '#FCE7F3',
            '검정': '#F3F4F6', '검은색': '#F3F4F6', '블랙': '#F3F4F6',
            '흰색': '#FFFFFF', '화이트': '#FFFFFF',
            '회색': '#F3F4F6', '그레이': '#F3F4F6',
        }
        
        bg_color = color_bg_map.get(color, '#F8FAFC')
        
        html = f'''
        <div class="card" style="background: {bg_color}; border: 2px solid #E5E7EB;">
            <h3 style="color: #374151; margin-bottom: 15px; font-size: 18px;">🍀 2025년 행운 키워드</h3>
            <div style="display: grid; gap: 12px;">
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-size: 20px; margin-right: 12px;">🎨</span>
                    <div>
                        <strong style="color: #374151;">행운의 색상:</strong> 
                        <span style="font-weight: bold; color: {color.lower()}; font-size: 16px;">{color}</span>
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-size: 20px; margin-right: 12px;">🔢</span>
                    <div>
                        <strong style="color: #374151;">행운의 숫자:</strong> 
                        <span style="font-weight: bold; color: #7C3AED; font-size: 16px;">{nums}</span>
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; padding: 8px 0;">
                    <span style="font-size: 20px; margin-right: 12px;">💎</span>
                    <div>
                        <strong style="color: #374151;">행운의 보석:</strong> 
                        <span style="font-weight: bold; color: #059669; font-size: 16px;">{stone}</span>
                    </div>
                </div>
            </div>
            
            <div style="margin-top: 15px; padding: 10px; background-color: rgba(255,255,255,0.5); border-radius: 6px; font-size: 12px; color: #6B7280;">
                💡 <strong>활용법:</strong> 중요한 결정을 내릴 때나 새로운 시작을 할 때 이 키워드들을 활용해보세요!
            </div>
        </div>
        '''
        return html
        
    except Exception as e:
        print(f"키워드 카드 생성 실패: {e}")
        return '<div class="card"><h3>행운 키워드를 생성할 수 없습니다.</h3></div>'

def generate_fortune_summary(elem_dict_kr: dict) -> str:
    """오행 분포를 기반으로 간단한 운세 요약 생성"""
    try:
        total = sum(elem_dict_kr.values())
        if total == 0:
            return "오행 정보가 부족합니다."
        
        # 가장 강한 오행과 약한 오행 찾기
        max_element = max(elem_dict_kr, key=elem_dict_kr.get)
        min_element = min(elem_dict_kr, key=elem_dict_kr.get)
        
        element_meanings = {
            '목': {'성격': '성장지향적이고 창의적', '조언': '끈기와 인내심을 발휘'},
            '화': {'성격': '열정적이고 사교적', '조언': '감정 조절과 차분함 유지'},
            '토': {'성격': '안정적이고 신뢰할 만한', '조언': '새로운 도전과 변화 시도'},
            '금': {'성격': '체계적이고 원칙적', '조언': '유연성과 적응력 기르기'},
            '수': {'성격': '지혜롭고 유동적', '조언': '실행력과 결단력 강화'}
        }
        
        max_info = element_meanings.get(max_element, {'성격': '', '조언': ''})
        
        summary = f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin: 15px 0;">
            <h4 style="margin: 0 0 15px 0; font-size: 18px;">🌟 운세 한눈에 보기</h4>
            <p style="margin: 8px 0; font-size: 14px;">
                ✨ <strong>주도적 기질:</strong> {max_element}({elem_dict_kr[max_element]}개) - {max_info['성격']}
            </p>
            <p style="margin: 8px 0; font-size: 14px;">
                💡 <strong>개발 포인트:</strong> {min_element} 기운 보완 - {element_meanings.get(min_element, {}).get('조언', '균형 잡기')}
            </p>
            <p style="margin: 8px 0 0 0; font-size: 12px; opacity: 0.9;">
                🔮 전체적으로 균형잡힌 발전을 위해 부족한 부분을 보완하며 강점을 살려나가세요.
            </p>
        </div>
        """
        return summary
        
    except Exception as e:
        print(f"운세 요약 생성 실패: {e}")
        return ""
    
def generate_2025_fortune_calendar(elem_dict_kr: dict) -> str:
    """2025년 월별 운세 달력 생성 (오행 기반 알고리즘)"""
    try:
        months = ['1월', '2월', '3월', '4월', '5월', '6월', 
                 '7월', '8월', '9월', '10월', '11월', '12월']
        
        # 오행 기반 운세 생성 알고리즘
        def calculate_fortune_by_element(month_idx, category):
            """오행 분포를 기반으로 월별 운세 계산"""
            wood = elem_dict_kr.get('목', 0)
            fire = elem_dict_kr.get('화', 0)
            earth = elem_dict_kr.get('토', 0)
            metal = elem_dict_kr.get('금', 0)
            water = elem_dict_kr.get('수', 0)
            
            # 계절별 기본 점수 (봄=목, 여름=화, 가을=금, 겨울=수)
            season_bonus = {
                'love': [wood*0.3, wood*0.5, fire*0.4, fire*0.6, fire*0.8, fire*0.6, 
                        fire*0.4, earth*0.3, metal*0.4, metal*0.6, water*0.3, water*0.5],
                'money': [water*0.4, earth*0.5, wood*0.6, wood*0.8, fire*0.6, fire*0.4,
                         metal*0.3, metal*0.5, metal*0.7, earth*0.6, water*0.5, water*0.3],
                'career': [metal*0.3, water*0.4, wood*0.7, wood*0.6, fire*0.5, earth*0.4,
                          earth*0.6, metal*0.6, metal*0.8, water*0.4, water*0.6, earth*0.5]
            }
            
            base_score = season_bonus[category][month_idx]
            # 랜덤 요소 추가 (개인차)
            random.seed(month_idx + sum(elem_dict_kr.values()) * (1 if category == 'love' else 2 if category == 'money' else 3))
            variance = random.uniform(-0.3, 0.3)
            final_score = base_score + variance
            
            # 점수를 심볼로 변환
            if final_score >= 1.5:
                return 'G'  # Good
            elif final_score >= 0.8:
                return 'Y'  # Caution
            elif final_score >= 0.3:
                return '-'  # Normal
            else:
                return 'R'  # Risk
        
        # 카테고리별 연간 운세 생성
        fortune_data = {
            'Love': [calculate_fortune_by_element(i, 'love') for i in range(12)],
            'Money': [calculate_fortune_by_element(i, 'money') for i in range(12)],
            'Career': [calculate_fortune_by_element(i, 'career') for i in range(12)]
        }
        
        return month_heat_table(fortune_data)
        
    except Exception as e:
        print(f"운세 달력 생성 실패: {e}")
        return '<p>월별 운세를 생성할 수 없습니다.</p>'


def generate_lucky_keywords_improved(elem_dict_kr: dict, birth_month: int = 6, birthdate_str: str = None, pillars: dict = None) -> Tuple[str, List[int], str]:
    """
    개선된 행운 키워드 생성 - 완전 개인화된 알고리즘
    
    Args:
        elem_dict_kr: 오행 분포 {'목': 2, '화': 1, ...}
        birth_month: 출생월 (1-12)
        birthdate_str: 출생일 문자열 "YYYY-MM-DD" 
        pillars: 사주 정보 {'year': '갑자', 'month': '정미', ...}
    
    Returns:
        (행운색상, 행운숫자리스트, 행운보석)
    """
    try:
        # 1. 개인화 해시 생성 (일관된 결과 보장)
        hash_input = f"{elem_dict_kr}{birth_month}"
        if birthdate_str:
            hash_input += birthdate_str
        if pillars:
            hash_input += str(pillars)
        
        personal_hash = hashlib.md5(hash_input.encode()).hexdigest()
        
        # 2. 오행 분석 강화
        total_elements = sum(elem_dict_kr.values())
        if total_elements == 0:
            # 기본값 반환
            return '자주색', [3, 7, 9], '자수정'
        
        # 가장 강한 오행과 약한 오행
        max_element = max(elem_dict_kr, key=elem_dict_kr.get)
        min_element = min(elem_dict_kr, key=elem_dict_kr.get)
        
        # 오행 균형도 계산 (0~1, 1에 가까울수록 균형)
        element_values = list(elem_dict_kr.values())
        balance_score = 1 - (max(element_values) - min(element_values)) / max(total_elements, 1)
        
        # 3. 확장된 오행별 키워드 매핑
        element_keywords = {
            '목': {
                'colors': ['초록', '연두', '연갈색', '올리브', '카키', '민트'],
                'stones': ['에메랄드', '말라카이트', '아벤투린', '페리도트', '아마존석', '녹색벽옥'],
                'personality': 'growth'  # 성장형
            },
            '화': {
                'colors': ['빨강', '주황', '분홍', '코랄', '진홍', '자홍'],
                'stones': ['루비', '가넷', '카넬리안', '홍마노', '선스톤', '로즈쿼츠'],
                'personality': 'passionate'  # 열정형
            },
            '토': {
                'colors': ['노랑', '베이지', '갈색', '황토', '샴페인', '골드'],
                'stones': ['황수정', '호박', '타이거아이', '황옥', '토파즈', '황철석'],
                'personality': 'stable'  # 안정형
            },
            '금': {
                'colors': ['흰색', '은색', '회색', '플래티넘', '진주', '크림'],
                'stones': ['다이아몬드', '수정', '문스톤', '진주', '백옥', '화이트사파이어'],
                'personality': 'systematic'  # 체계형
            },
            '수': {
                'colors': ['파랑', '검정', '자주', '네이비', '인디고', '티파니블루'],
                'stones': ['사파이어', '청금석', '자수정', '라피스라줄리', '블루토파즈', '아쿠아마린'],
                'personality': 'wise'  # 지혜형
            }
        }
        
        # 4. 해시 기반 deterministic 선택
        def hash_select(options: list, offset: int = 0) -> any:
            """해시값을 이용한 일관된 선택"""
            hash_val = int(personal_hash[offset:offset+8], 16)
            return options[hash_val % len(options)]
        
        # 5. 메인 오행의 키워드 선택
        main_keywords = element_keywords[max_element]
        
        # 6. 보완 오행 고려 (균형이 좋지 않을 때)
        if balance_score < 0.5:  # 불균형이 심할 때
            # 부족한 오행의 키워드도 일부 반영
            complement_keywords = element_keywords[min_element]
            
            # 색상: 메인 오행 80% + 보완 오행 20% 확률로 선택  
            hash_mod = int(personal_hash[8:10], 16) % 100
            if hash_mod < 20:  # 20% 확률로 보완 색상
                lucky_color = hash_select(complement_keywords['colors'], 2)
            else:  # 80% 확률로 메인 색상
                lucky_color = hash_select(main_keywords['colors'], 0)
                
            # 보석: 메인 위주지만 보완도 고려
            if hash_mod < 30:  # 30% 확률로 보완 보석
                lucky_stone = hash_select(complement_keywords['stones'], 4)
            else:
                lucky_stone = hash_select(main_keywords['stones'], 1)
        else:
            # 균형이 좋을 때는 메인 오행 위주
            lucky_color = hash_select(main_keywords['colors'], 0)
            lucky_stone = hash_select(main_keywords['stones'], 1)
        
        # 7. 개인화된 행운 숫자 생성
        base_numbers = {
            '목': [1, 3, 8], '화': [2, 7, 9], '토': [5, 6, 8], 
            '금': [4, 7, 9], '수': [1, 6, 9]
        }
        
        lucky_numbers = base_numbers[max_element].copy()
        
        # 생월 추가 (if not already in)
        if birth_month not in lucky_numbers:
            lucky_numbers.append(birth_month)
        
        # 개인화 숫자 추가 (해시 기반)
        personal_number = (int(personal_hash[10:12], 16) % 9) + 1
        if personal_number not in lucky_numbers:
            lucky_numbers.append(personal_number)
        
        # 오행 균형 기반 보너스 숫자
        if balance_score > 0.7:  # 균형이 매우 좋을 때
            lucky_numbers.append(0)  # 완성의 숫자
        
        # 최대 4개까지만
        lucky_numbers = lucky_numbers[:4]
        
        # 8. 정렬 (일관성)
        lucky_numbers.sort()
        
        return lucky_color, lucky_numbers, lucky_stone
        
    except Exception as e:
        print(f"개선된 행운 키워드 생성 실패: {e}")
        # 안전한 기본값
        return '자주색', [3, 7, 9], '자수정'


def generate_lucky_keywords_with_explanation(elem_dict_kr: dict, birth_month: int = 6, birthdate_str: str = None, pillars: dict = None) -> Tuple[str, List[int], str, str]:
    """
    행운 키워드 + 설명 생성
    
    Returns:
        (행운색상, 행운숫자리스트, 행운보석, 선택이유설명)
    """
    try:
        lucky_color, lucky_numbers, lucky_stone = generate_lucky_keywords_improved(
            elem_dict_kr, birth_month, birthdate_str, pillars
        )
        
        # 가장 강한/약한 오행
        max_element = max(elem_dict_kr, key=elem_dict_kr.get)
        min_element = min(elem_dict_kr, key=elem_dict_kr.get)
        
        total_elements = sum(elem_dict_kr.values())
        balance_score = 1 - (max(elem_dict_kr.values()) - min(elem_dict_kr.values())) / max(total_elements, 1)
        
        # 설명 생성
        explanation = f"""
        <div style="margin-top: 1rem; padding: 1rem; background: #f8fafc; border-radius: 8px; border-left: 4px solid #667eea;">
            <h4 style="margin: 0 0 0.5rem 0; color: #4c51bf;">🔍 키워드 선택 이유</h4>
            <p style="margin: 0; font-size: 0.9rem; line-height: 1.5; color: #4a5568;">
                <strong>주력 오행:</strong> {max_element}({elem_dict_kr[max_element]}개) - 
                {'균형이 잘 잡혀 있어' if balance_score > 0.7 else '강한 편이라'} 
                {max_element} 기운을 활용한 <span style="color: {lucky_color.lower()}; font-weight: bold;">{lucky_color}</span>과 
                <strong>{lucky_stone}</strong>을 추천합니다.
                {f'부족한 {min_element} 기운을 보완하는 요소도 포함했습니다.' if balance_score < 0.5 else ''}
            </p>
        </div>
        """
        
        return lucky_color, lucky_numbers, lucky_stone, explanation
        
    except Exception as e:
        print(f"설명 포함 키워드 생성 실패: {e}")
        return '자주색', [3, 7, 9], '자수정', ""


# utils.py에서 사용할 래퍼 함수 (기존 호환성 유지)
def generate_lucky_keywords(elem_dict_kr: dict, birth_month: int = 6, birthdate_str: str = None, pillars: dict = None) -> Tuple[str, List[int], str]:
    """기존 함수명 유지 - 개선된 버전으로 리다이렉트"""
    return generate_lucky_keywords_improved(elem_dict_kr, birth_month, birthdate_str, pillars)


# 키워드 카드 HTML 생성도 개선
def keyword_card_improved(color: str, numbers: List[int], stone: str, explanation: str = "") -> str:
    """개선된 행운 키워드 카드 생성 (설명 포함)"""
    try:
        nums = ", ".join(map(str, numbers))
        
        # 색상별 배경색 매핑
        color_bg_map = {
            '빨강': '#FEE2E2', '빨간색': '#FEE2E2', '진홍': '#FEE2E2', '자홍': '#FEE2E2',
            '파랑': '#DBEAFE', '파란색': '#DBEAFE', '블루': '#DBEAFE', '네이비': '#1E3A8A', '티파니블루': '#0891B2',
            '초록': '#D1FAE5', '녹색': '#D1FAE5', '그린': '#D1FAE5', '연두': '#DCFCE7', '올리브': '#EF4444', '민트': '#A7F3D0',
            '노랑': '#FEF3C7', '노란색': '#FEF3C7', '옐로우': '#FEF3C7', '골드': '#FDE68A', '샴페인': '#FEF3C7',
            '보라': '#E9D5FF', '보라색': '#E9D5FF', '퍼플': '#E9D5FF', '자주': '#F3E8FF', '인디고': '#E0E7FF',
            '주황': '#FED7AA', '주황색': '#FED7AA', '오렌지': '#FED7AA', '코랄': '#FECACA',
            '분홍': '#FCE7F3', '핑크': '#FCE7F3',
            '검정': '#F3F4F6', '검은색': '#F3F4F6',
            '흰색': '#FFFFFF', '화이트': '#FFFFFF', '크림': '#FFFBEB', '진주': '#F8FAFC',
            '회색': '#F3F4F6', '그레이': '#F3F4F6', '은색': '#F1F5F9', '플래티넘': '#F8FAFC',
            '갈색': '#FEF3C7', '연갈색': '#F7FAFC', '황토': '#FEF3C7', '카키': '#EF4444', '베이지': '#FEF7ED'
        }
        
        bg_color = color_bg_map.get(color, '#F8FAFC')
        from app.utils import contrast_text
        color_text = contrast_text(bg_color)
        
        html = f'''
        <div class="info-card" style="background: {bg_color}; border: 2px solid #E5E7EB;">
            <h3 style="color: #374151; margin-bottom: 15px; font-size: 18px;">🍀 2025년 맞춤 행운 키워드</h3>
            <div style="display: grid; gap: 12px;">
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-size: 20px; margin-right: 12px;">🎨</span>
                    <div>
                        <strong style="color: #374151;">행운의 색상:</strong> 
                        <span style="font-weight: bold; font-size: 16px; padding: 4px 8px; background: white; border-radius: 4px; color: {color_text};">{color}</span>
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #E5E7EB;">
                    <span style="font-size: 20px; margin-right: 12px;">🔢</span>
                    <div>
                        <strong style="color: #374151;">행운의 숫자:</strong> 
                        <span style="font-weight: bold; color: #7C3AED; font-size: 16px; padding: 4px 8px; background: white; border-radius: 4px;">{nums}</span>
                    </div>
                </div>
                
                <div style="display: flex; align-items: center; padding: 8px 0;">
                    <span style="font-size: 20px; margin-right: 12px;">💎</span>
                    <div>
                        <strong style="color: #374151;">행운의 보석:</strong> 
                        <span style="font-weight: bold; color: #059669; font-size: 16px; padding: 4px 8px; background: white; border-radius: 4px;">{stone}</span>
                    </div>
                </div>
            </div>
            
            {explanation}
            
            <div style="margin-top: 15px; padding: 10px; background-color: rgba(255,255,255,0.7); border-radius: 6px; font-size: 12px; color: #6B7280;">
                💡 <strong>활용법:</strong> 중요한 결정을 내릴 때나 새로운 시작을 할 때 이 키워드들을 활용해보세요! 
                옷이나 액세서리 선택, 중요한 날짜 정하기 등에 참고하시면 됩니다.
            </div>
        </div>
        '''
        return html
        
    except Exception as e:
        print(f"개선된 키워드 카드 생성 실패: {e}")
        return '<div class="info-card"><h3>행운 키워드를 생성할 수 없습니다.</h3></div>'

def generate_action_checklist(elem_dict_kr: dict) -> list[dict]:
    """오행 기반 실천 체크리스트 생성"""
    try:
        # 가장 약한 오행 찾기 (보완 필요)
        min_element = min(elem_dict_kr, key=elem_dict_kr.get)
        max_element = max(elem_dict_kr, key=elem_dict_kr.get)
        
        # 오행별 맞춤 조언
        element_advice = {
            '목': {
                'habit': '매일 15분 산책하며 자연 관찰하기 🌱',
                'money': '장기 투자 계획 세우고 월 적금 시작하기 💰',
                'relationship': '새로운 모임이나 동호회 참여하기 🤝',
                'health': '스트레칭과 요가로 유연성 기르기 🧘',
                'growth': '새로운 기술이나 언어 배우기 📚'
            },
            '화': {
                'habit': '일찍 자고 일찍 일어나는 수면 패턴 만들기 ⏰',
                'money': '충동구매 줄이고 가계부 작성하기 📊',
                'relationship': '가족, 친구와 정기 모임 갖기 ❤️',
                'health': '명상이나 심호흡으로 마음 안정 찾기 🧘‍♀️',
                'growth': '감정 일기 쓰며 자기 이해 높이기 ✍️'
            },
            '토': {
                'habit': '정리정돈과 미니멀 라이프 실천하기 🏠',
                'money': '비상금 모으고 안전한 투자 위주로 하기 🛡️',
                'relationship': '진솔한 대화 시간 늘리기 💬',
                'health': '규칙적인 식사와 영양 관리하기 🥗',
                'growth': '독서와 깊이 있는 사고 시간 갖기 📖'
            },
            '금': {
                'habit': '계획표 작성하고 체계적으로 실행하기 📅',
                'money': '투자 포트폴리오 다양화하기 📈',
                'relationship': '약속 시간 잘 지키고 신뢰 쌓기 ⏱️',
                'health': '근력 운동으로 체력 기르기 💪',
                'growth': '전문 분야 깊이 있게 공부하기 🎯'
            },
            '수': {
                'habit': '충분한 수분 섭취와 휴식 취하기 💧',
                'money': '다양한 수입원 개발하기 🌊',
                'relationship': '경청하는 습관 기르기 👂',
                'health': '스트레스 해소 방법 찾기 🎵',
                'growth': '창의적 취미 활동 시작하기 🎨'
            }
        }
        
        # 부족한 오행의 조언을 우선 선택
        advice = element_advice.get(min_element, element_advice['목'])
        
        checklist = [
            {'cat': '습관 개선', 'action': advice['habit']},
            {'cat': '재물 관리', 'action': advice['money']},
            {'cat': '인간관계', 'action': advice['relationship']},
            {'cat': '건강 관리', 'action': advice['health']},
            {'cat': '자기계발', 'action': advice['growth']},
        ]
        
        return checklist
        
    except Exception as e:
        print(f"체크리스트 생성 실패: {e}")
        return [
            {'cat': '습관 개선', 'action': '매일 아침 10분 명상하기 🧘'},
            {'cat': '재물 관리', 'action': '월 소비 예산 5% 줄이기 💰'},
            {'cat': '인간관계', 'action': '매주 가족/친구에게 안부 묻기 📞'},
            {'cat': '건강 관리', 'action': '주 3회 이상 운동하기 🏃'},
            {'cat': '자기계발', 'action': '한 달에 책 1권 읽기 📚'},
        ]

def create_executive_summary(user_name: str, birthdate: str, pillars: dict, elem_dict_kr: dict) -> str:
    """임원급 요약 정보 생성"""
    try:
        # 오행 기반 핵심 특성 분석
        max_element = max(elem_dict_kr, key=elem_dict_kr.get)
        min_element = min(elem_dict_kr, key=elem_dict_kr.get)
        
        element_traits = {
            '목': '성장지향적, 창의적',
            '화': '열정적, 사교적', 
            '토': '안정적, 신뢰감',
            '금': '체계적, 원칙적',
            '수': '지혜로운, 유연한'
        }
        
        # 연도별 띠 계산
        birth_year = int(birthdate.split('-')[0])
        zodiac_animals = ['원숭이', '닭', '개', '돼지', '쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양']
        zodiac = zodiac_animals[birth_year % 12]
        
        # 3줄 요약 생성
        summary_lines = [
            f"🔥 {element_traits.get(max_element, '균형잡힌')} 성향이 강한 {zodiac}띠",
            f"💰 2025년 하반기 {max_element} 기운으로 성장 기회",
            f"❤️ {min_element} 에너지 보완으로 관계운 상승"
        ]
        
        html = f'''
        <div class="executive-summary" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 15px; margin: 20px 0;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="margin: 0; font-size: 24px; font-weight: bold;">{user_name} 님</h2>
                <p style="margin: 5px 0; font-size: 14px; opacity: 0.9;">{birthdate} • {pillars.get('day', '')} 일주 • {zodiac}띠</p>
                <div style="height: 2px; background: rgba(255,255,255,0.3); margin: 15px auto; width: 80%;"></div>
            </div>
            <div style="font-size: 16px; line-height: 1.8;">
                {'<br>'.join(summary_lines)}
            </div>
        </div>
        '''
        
        return html
        
    except Exception as e:
        print(f"요약 정보 생성 실패: {e}")
        return f'<div class="executive-summary"><h2>{user_name} 님의 사주 리포트</h2></div>'

def enhanced_radar_chart_base64(elem_dict_kr: dict) -> str:
    """향상된 레이더 차트 (설명 포함)"""
    try:
        setup_korean_font()
        
        # 기본 레이더 차트 생성
        labels_kr = ['목(木)', '화(火)', '토(土)', '금(金)', '수(水)']
        values = [elem_dict_kr.get(k, 0) for k in ['목', '화', '토', '금', '수']]
        
        if all(v == 0 for v in values):
            values = [1] * 5
        
        values += values[:1]  # 원형으로 닫기
        angles = np.linspace(0, 2 * np.pi, len(values))
        
        # 차트 생성
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), 
                                       gridspec_kw={'width_ratios': [2, 1]})
        
        # 레이더 차트
        ax1 = plt.subplot(121, projection='polar')
        ax1.fill(angles, values, alpha=0.25, color='#8B5CF6')
        ax1.plot(angles, values, linewidth=3, color='#7C3AED', marker='o', markersize=8)
        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels(labels_kr, fontsize=12, fontweight='bold')
        ax1.set_ylim(0, max(values[:-1]) + 1 if max(values[:-1]) > 0 else 5)
        ax1.grid(True, alpha=0.3)
        ax1.set_title('오행 밸런스', fontsize=16, fontweight='bold', pad=20)
        
        # 텍스트 설명
        ax2.axis('off')
        max_element = max(['목', '화', '토', '금', '수'], key=lambda x: elem_dict_kr.get(x, 0))
        min_element = min(['목', '화', '토', '금', '수'], key=lambda x: elem_dict_kr.get(x, 0))
        
        explanation = [
            f"🔥 가장 강함: {max_element} ({elem_dict_kr.get(max_element, 0)}개)",
            f"💧 보완 필요: {min_element} ({elem_dict_kr.get(min_element, 0)}개)",
            "",
            "📊 해석:",
            f"• {max_element} 기운이 강해 관련 특성 부각",
            f"• {min_element} 에너지 보완으로 균형 개선",
            "• 전체적 조화로 운세 상승 가능"
        ]
        
        for i, line in enumerate(explanation):
            ax2.text(0.05, 0.9 - i*0.12, line, fontsize=11, 
                    transform=ax2.transAxes, fontweight='bold' if line.startswith(('🔥', '💧', '📊')) else 'normal')
        
        # 이미지 저장
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150, facecolor='white')
        plt.close(fig)
        
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
        
    except Exception as e:
        print(f"향상된 레이더 차트 생성 실패: {e}")
        return radar_chart_base64({'Wood': elem_dict_kr.get('목', 0), 'Fire': elem_dict_kr.get('화', 0), 
                                  'Earth': elem_dict_kr.get('토', 0), 'Metal': elem_dict_kr.get('금', 0), 
                                  'Water': elem_dict_kr.get('수', 0)})