#!/usr/bin/env python3
# migration_saju_phase1.py
"""
Phase 1: SajuUser 테이블에 컬럼 추가 및 기존 데이터 마이그레이션
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import SajuUser
from app.services.saju_service import SajuService
from sqlalchemy import text

def add_columns_to_saju_users():
    """SajuUser 테이블에 새 컬럼 추가"""
    print("🔄 SajuUser 테이블에 컬럼 추가 중...")
    
    with engine.connect() as conn:
        try:
            # JSON 컬럼 추가
            conn.execute(text("""
                ALTER TABLE saju_users 
                ADD COLUMN calculated_pillars JSON
            """))
            print("✅ calculated_pillars 컬럼 추가됨")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("⏭️  calculated_pillars 컬럼 이미 존재")
            else:
                print(f"❌ calculated_pillars 컬럼 추가 실패: {e}")
        
        try:
            conn.execute(text("""
                ALTER TABLE saju_users 
                ADD COLUMN elem_dict_kr JSON
            """))
            print("✅ elem_dict_kr 컬럼 추가됨")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("⏭️  elem_dict_kr 컬럼 이미 존재")
            else:
                print(f"❌ elem_dict_kr 컬럼 추가 실패: {e}")
        
        try:
            conn.execute(text("""
                ALTER TABLE saju_users 
                ADD COLUMN calculated_at DATETIME
            """))
            print("✅ calculated_at 컬럼 추가됨")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("⏭️  calculated_at 컬럼 이미 존재")
            else:
                print(f"❌ calculated_at 컬럼 추가 실패: {e}")
        
        # 트랜잭션 커밋
        conn.commit()

def migrate_existing_data():
    """기존 사주 데이터를 새 컬럼으로 마이그레이션"""
    print("\n🔄 기존 사주 데이터 마이그레이션 중...")
    
    db = SessionLocal()
    try:
        # saju_key가 있고 calculated_pillars가 없는 사용자들 조회
        users_to_migrate = db.query(SajuUser).filter(
            SajuUser.saju_key.isnot(None),
            SajuUser.calculated_pillars.is_(None)
        ).limit(10).all()  # 첫 10개만 테스트
        
        print(f"📊 마이그레이션 대상: {len(users_to_migrate)}명")
        
        success_count = 0
        error_count = 0
        
        for user in users_to_migrate:
            try:
                print(f"🔄 사용자 {user.id} ({user.saju_key}) 처리 중...")
                
                # SajuService를 통해 계산
                pillars, elem_dict_kr = SajuService.get_or_calculate_saju(
                    user.saju_key, db
                )
                
                success_count += 1
                print(f"✅ 사용자 {user.id} 완료")
                
            except Exception as e:
                error_count += 1
                print(f"❌ 사용자 {user.id} 실패: {e}")
        
        print(f"\n📊 마이그레이션 완료: 성공 {success_count}명, 실패 {error_count}명")
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        db.rollback()
    finally:
        db.close()

def verify_migration():
    """마이그레이션 결과 검증"""
    print("\n🔍 마이그레이션 결과 검증 중...")
    
    db = SessionLocal()
    try:
        # 통계 조회
        total_users = db.query(SajuUser).filter(
            SajuUser.saju_key.isnot(None)
        ).count()
        
        migrated_users = db.query(SajuUser).filter(
            SajuUser.saju_key.isnot(None),
            SajuUser.calculated_pillars.isnot(None)
        ).count()
        
        print(f"📊 전체 사주 사용자: {total_users}명")
        print(f"📊 마이그레이션 완료: {migrated_users}명")
        print(f"📊 완료율: {(migrated_users/max(total_users,1)*100):.1f}%")
        
        # 샘플 검증
        sample = db.query(SajuUser).filter(
            SajuUser.calculated_pillars.isnot(None)
        ).first()
        
        if sample:
            print(f"✅ 샘플 데이터 확인:")
            print(f"   - 사주키: {sample.saju_key}")
            print(f"   - 사주팔자: {sample.calculated_pillars}")
            print(f"   - 오행분포: {sample.elem_dict_kr}")
        
    except Exception as e:
        print(f"❌ 검증 실패: {e}")
    finally:
        db.close()

def main():
    """메인 마이그레이션 실행"""
    print("🚀 Phase 1 사주 마이그레이션 시작")
    print("=" * 50)
    
    # 1. 컬럼 추가
    add_columns_to_saju_users()
    
    # 2. 데이터 마이그레이션
    migrate_existing_data()
    
    # 3. 검증
    verify_migration()
    
    print("\n" + "=" * 50)
    print("🎉 Phase 1 마이그레이션 완료!")
    print("\n다음 단계:")
    print("1. GitHub에 커밋 & 푸시")
    print("2. 코드 확인 후 Phase 2 진행")

if __name__ == "__main__":
    main()