#!/usr/bin/env python3
# test_phase2.py
"""
Phase 2 검증: 모든 곳에서 SajuService 사용 확인
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import SajuUser, SajuAnalysisCache
from app.services.saju_service import SajuService
from app.saju_utils import SajuKeyManager

def test_saju_service_consistency():
    """SajuService가 일관된 결과를 반환하는지 테스트"""
    print("🔍 SajuService 일관성 테스트 중...")
    
    db = SessionLocal()
    try:
        # 테스트용 사주 키 생성
        test_saju_key = SajuKeyManager.build_saju_key(
            birth_date="1984-06-01",
            birth_hour=20,
            gender="male",
            calendar="SOL",
            timezone="Asia/Seoul"
        )
        
        print(f"📋 테스트 사주키: {test_saju_key}")
        
        # 첫 번째 호출 (계산)
        pillars1, elem_dict1 = SajuService.get_or_calculate_saju(test_saju_key, db)
        print("✅ 첫 번째 호출 (새로 계산)")
        print(f"   사주: {pillars1}")
        print(f"   오행: {elem_dict1}")
        
        # 두 번째 호출 (캐시에서 가져오기)
        pillars2, elem_dict2 = SajuService.get_or_calculate_saju(test_saju_key, db)
        print("✅ 두 번째 호출 (캐시에서)")
        print(f"   사주: {pillars2}")
        print(f"   오행: {elem_dict2}")
        
        # 일관성 확인
        if pillars1 == pillars2 and elem_dict1 == elem_dict2:
            print("🎉 일관성 테스트 통과!")
            return True
        else:
            print("❌ 일관성 테스트 실패!")
            print(f"   첫 번째: {pillars1} / {elem_dict1}")
            print(f"   두 번째: {pillars2} / {elem_dict2}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False
    finally:
        db.close()

def test_cache_invalidation():
    """캐시 무효화 테스트"""
    print("\n🔄 캐시 무효화 테스트 중...")
    
    db = SessionLocal()
    try:
        test_saju_key = SajuKeyManager.build_saju_key(
            birth_date="1990-12-25",
            birth_hour=15,
            gender="female",
            calendar="SOL",
            timezone="Asia/Seoul"
        )
        
        # 처음 계산
        pillars1, elem_dict1 = SajuService.get_or_calculate_saju(test_saju_key, db)
        print("✅ 초기 계산 완료")
        
        # 캐시 확인
        has_cache_before = SajuService.has_cached_saju(test_saju_key, db)
        print(f"   캐시 상태 (무효화 전): {has_cache_before}")
        
        # 캐시 무효화
        SajuService.invalidate_cache(test_saju_key, db)
        print("🗑️  캐시 무효화 실행")
        
        # 캐시 확인
        has_cache_after = SajuService.has_cached_saju(test_saju_key, db)
        print(f"   캐시 상태 (무효화 후): {has_cache_after}")
        
        if has_cache_before and not has_cache_after:
            print("🎉 캐시 무효화 테스트 통과!")
            return True
        else:
            print("❌ 캐시 무효화 테스트 실패!")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False
    finally:
        db.close()

def test_lunar_calendar_handling():
    """음력 처리 테스트"""
    print("\n🌙 음력 처리 테스트 중...")
    
    db = SessionLocal()
    try:
        # 음력 사주 키 생성
        lunar_saju_key = SajuKeyManager.build_saju_key(
            birth_date="1984-06-01",
            birth_hour=10,
            gender="male",
            calendar="LUN",  # 음력
            timezone="Asia/Seoul"
        )
        
        # 양력 사주 키 생성 (같은 날짜)
        solar_saju_key = SajuKeyManager.build_saju_key(
            birth_date="1984-06-01",
            birth_hour=10,
            gender="male",
            calendar="SOL",  # 양력
            timezone="Asia/Seoul"
        )
        
        print(f"📋 음력 키: {lunar_saju_key}")
        print(f"📋 양력 키: {solar_saju_key}")
        
        # 각각 계산
        lunar_pillars, lunar_elem = SajuService.get_or_calculate_saju(lunar_saju_key, db)
        solar_pillars, solar_elem = SajuService.get_or_calculate_saju(solar_saju_key, db)
        
        print(f"🌙 음력 사주: {lunar_pillars}")
        print(f"☀️  양력 사주: {solar_pillars}")
        
        # 다른 결과가 나와야 정상 (음력/양력 변환됨)
        if lunar_pillars != solar_pillars:
            print("🎉 음력/양력 처리 테스트 통과!")
            return True
        else:
            print("❌ 음력/양력 처리 테스트 실패! (같은 결과)")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False
    finally:
        db.close()

def check_migration_status():
    """마이그레이션 상태 확인"""
    print("\n📊 Phase 2 마이그레이션 상태 확인...")
    
    db = SessionLocal()
    try:
        # 전체 사주 사용자 수
        total_users = db.query(SajuUser).filter(
            SajuUser.saju_key.isnot(None)
        ).count()
        
        # SajuService로 계산된 사용자 수
        migrated_users = db.query(SajuUser).filter(
            SajuUser.saju_key.isnot(None),
            SajuUser.calculated_pillars.isnot(None)
        ).count()
        
        print(f"📈 전체 사주 사용자: {total_users}명")
        print(f"📈 마이그레이션 완료: {migrated_users}명")
        print(f"📈 완료율: {(migrated_users/max(total_users,1)*100):.1f}%")
        
        return migrated_users > 0
        
    except Exception as e:
        print(f"❌ 상태 확인 실패: {e}")
        return False
    finally:
        db.close()

def main():
    """Phase 2 전체 검증"""
    print("🚀 Phase 2 검증 시작")
    print("=" * 50)
    
    test_results = []
    
    # 1. 마이그레이션 상태 확인
    test_results.append(check_migration_status())
    
    # 2. SajuService 일관성 테스트
    test_results.append(test_saju_service_consistency())
    
    # 3. 캐시 무효화 테스트
    test_results.append(test_cache_invalidation())
    
    # 4. 음력 처리 테스트
    test_results.append(test_lunar_calendar_handling())
    
    # 결과 요약
    print("\n" + "=" * 50)
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    if passed_tests == total_tests:
        print(f"🎉 Phase 2 검증 완료! ({passed_tests}/{total_tests} 통과)")
        print("\n✅ 모든 경로에서 SajuService 사용 준비 완료")
        print("✅ 사주 계산 통일성 확보")
        print("✅ 캐싱 시스템 정상 작동")
        
        print("\n다음 단계:")
        print("1. GitHub에 커밋 & 푸시")
        print("2. 실제 서비스에서 테스트")
        print("3. Phase 3 (검증 및 정리) 진행")
    else:
        print(f"❌ Phase 2 검증 실패! ({passed_tests}/{total_tests} 통과)")
        print("문제를 수정한 후 다시 실행해주세요.")

if __name__ == "__main__":
    main()