import redis
import os
from dotenv import load_dotenv

load_dotenv()

def test_redis_connection():
    """Redis 연결 테스트"""
    try:
        # Redis 클라이언트 생성
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        
        # ping 테스트
        response = r.ping()
        if response:
            print("✅ Redis 연결 성공!")
            
            # 간단한 set/get 테스트
            r.set('test_key', 'test_value', ex=60)  # 60초 후 만료
            value = r.get('test_key')
            print(f"✅ Redis 읽기/쓰기 테스트 성공: {value.decode()}")
            
            # Redis 정보 확인
            info = r.info()
            print(f"📊 Redis 버전: {info['redis_version']}")
            print(f"📊 사용 메모리: {info['used_memory_human']}")
            print(f"📊 연결된 클라이언트: {info['connected_clients']}")
            
            return True
    except redis.ConnectionError as e:
        print(f"❌ Redis 연결 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ Redis 테스트 오류: {e}")
        return False

if __name__ == "__main__":
    test_redis_connection()