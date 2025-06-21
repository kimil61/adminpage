# app/report_utils.py
import io
import base64
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import os

# 한글 폰트 설정
def setup_korean_font():
    """한글 폰트 설정"""
    try:
        # Windows 환경
        if os.name == 'nt':
            font_path = 'C:/Windows/Fonts/malgun.ttf'  # 맑은 고딕
            if os.path.exists(font_path):
                fm.fontManager.addfont(font_path)
                plt.rcParams['font.family'] = 'Malgun Gothic'
            else:
                plt.rcParams['font.family'] = 'DejaVu Sans'
        else:
            # Linux/Mac 환경
            plt.rcParams['font.family'] = 'DejaVu Sans'
        
        plt.rcParams['axes.unicode_minus'] = False  # 마이너스 폰트 깨짐 방지
        
    except Exception as e:
        print(f"폰트 설정 실패: {e}")
        plt.rcParams['font.family'] = 'DejaVu Sans'

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