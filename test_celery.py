"""Celery 테스트 스크립트"""

from app.celery_app import celery_app
from app.tasks import test_task, generate_full_report
import redis
import pytest

def redis_available():
    try:
        r = redis.Redis()
        r.ping()
        return True
    except Exception:
        return False

@pytest.mark.skipif(not redis_available(), reason="Redis not available")
def test_basic_task():
    """기본 태스크 테스트"""
    print("📝 기본 태스크 테스트...")
    result = test_task.delay("테스트 작업")
    print(f"태스크 ID: {result.id}")
    
    # 결과 대기
    try:
        result_data = result.get(timeout=30)
        print(f"✅ 태스크 완료: {result_data}")
    except Exception as e:
        print(f"❌ 태스크 실패: {e}")

def test_report_generation():
    """리포트 생성 테스트"""
    print("📊 리포트 생성 테스트...")
    
    # 실제 주문 ID와 사주 키로 테스트
    # 주의: 실제 데이터가 필요합니다
    # result = generate_full_report.delay(1, "1984-06-01_12_male")
    # print(f"리포트 태스크 ID: {result.id}")

if __name__ == "__main__":
    # Celery 연결 확인
    inspect = celery_app.control.inspect()
    active_workers = inspect.active()
    
    if active_workers:
        print("✅ Celery 워커가 실행 중입니다")
        print(f"활성 워커: {list(active_workers.keys())}")
        
        # 기본 테스트 실행
        test_basic_task()
    else:
        print("❌ Celery 워커를 찾을 수 없습니다")
        print("먼저 'python start_celery.py'로 워커를 실행해주세요")