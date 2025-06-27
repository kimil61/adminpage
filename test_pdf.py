#!/usr/bin/env python3
"""
PDF 생성 테스트 스크립트
"""

import os
import sys
sys.path.append('.')

from app.tasks import html_to_pdf_production, generate_enhanced_report_html
from app.report_utils import radar_chart_base64

def test_simple_pdf():
    """간단한 PDF 생성 테스트"""
    simple_html = """
    <h1>테스트 PDF</h1>
    <p>이것은 PDF 생성 테스트입니다.</p>
    <p>한글이 제대로 표시되는지 확인해봅시다: 안녕하세요!</p>
    """
    
    output_path = "test_simple.pdf"
    success = html_to_pdf_production(simple_html, output_path)
    
    if success:
        print(f"✅ 간단한 PDF 생성 성공: {output_path}")
    else:
        print(f"❌ 간단한 PDF 생성 실패")
    
    return success

def test_full_report_pdf():
    """전체 리포트 PDF 생성 테스트"""
    # 테스트 데이터
    test_user_name = "홍길동"
    test_pillars = {
        'year': '갑자', 
        'month': '정미', 
        'day': '병인', 
        'hour': '무술'
    }
    test_analysis = """
    이 사주의 주인은 창의적이고 진취적인 성향을 가지고 있습니다.
    
    **주요 특징:**
    - 목의 기운이 강해 성장 지향적
    - 화의 기운으로 열정적 성격
    - 금의 기운 부족으로 체계성 보완 필요
    
    **2025년 조언:**
    상반기에는 새로운 도전을 시작하기 좋은 시기입니다.
    """
    test_elem_dict = {'목': 3, '화': 2, '토': 1, '금': 1, '수': 1}
    
    try:
        html_content = generate_enhanced_report_html(
            test_user_name, 
            test_pillars, 
            test_analysis, 
            test_elem_dict
        )
        
        output_path = "test_full_report.pdf"
        success = html_to_pdf_production(html_content, output_path)
        
        if success:
            print(f"✅ 전체 리포트 PDF 생성 성공: {output_path}")
            print(f"📄 파일 크기: {os.path.getsize(output_path)} bytes")
        else:
            print(f"❌ 전체 리포트 PDF 생성 실패")
        
        return success
        
    except Exception as e:
        print(f"❌ 전체 리포트 테스트 오류: {e}")
        return False

def test_chart_generation():
    """차트 생성 테스트"""
    try:
        test_data = {'Wood': 3, 'Fire': 2, 'Earth': 1, 'Metal': 1, 'Water': 1}
        chart_base64 = radar_chart_base64(test_data)
        
        if chart_base64 and chart_base64.startswith('data:image'):
            print("✅ 레이더 차트 생성 성공")
            return True
        else:
            print("❌ 레이더 차트 생성 실패")
            return False
            
    except Exception as e:
        print(f"❌ 차트 생성 오류: {e}")
        return False

def check_dependencies():
    """필요한 라이브러리 확인"""
    print("🔍 의존성 확인 중...")
    
    # wkhtmltopdf 확인
    try:
        import pdfkit
        print("✅ pdfkit 설치됨")
        
        # wkhtmltopdf 실행 파일 확인
        try:
            config = pdfkit.configuration()
            print("✅ wkhtmltopdf 설치됨")
        except Exception as e:
            print(f"⚠️ wkhtmltopdf 설정 문제: {e}")
            print("💡 해결 방법:")
            print("   - Windows: https://wkhtmltopdf.org/downloads.html 에서 다운로드")
            print("   - Ubuntu: sudo apt-get install wkhtmltopdf")
            print("   - Mac: brew install wkhtmltopdf")
            
    except ImportError:
        print("❌ pdfkit 미설치: pip install pdfkit")
    
    # matplotlib 확인
    try:
        import matplotlib
        print("✅ matplotlib 설치됨")
    except ImportError:
        print("❌ matplotlib 미설치: pip install matplotlib")
    
    # fpdf 확인
    try:
        from fpdf import FPDF
        print("✅ fpdf2 설치됨")
    except ImportError:
        print("❌ fpdf2 미설치: pip install fpdf2")

if __name__ == "__main__":
    print("🧪 PDF 생성 테스트 시작")
    print("=" * 50)
    
    # 1. 의존성 확인
    check_dependencies()
    print()
    
    # 2. 차트 생성 테스트
    chart_ok = test_chart_generation()
    print()
    
    # 3. 간단한 PDF 테스트
    simple_ok = test_simple_pdf()
    print()
    
    # 4. 전체 리포트 테스트
    full_ok = test_full_report_pdf()
    print()
    
    # 결과 요약
    print("=" * 50)
    print("🎯 테스트 결과 요약:")
    print(f"   차트 생성: {'✅' if chart_ok else '❌'}")
    print(f"   간단한 PDF: {'✅' if simple_ok else '❌'}")
    print(f"   전체 리포트: {'✅' if full_ok else '❌'}")
    
    if all([chart_ok, simple_ok, full_ok]):
        print("\n🎉 모든 테스트 통과! PDF 생성이 정상 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트 실패. 위의 오류 메시지를 확인해주세요.")