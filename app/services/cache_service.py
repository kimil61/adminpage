"""
캐싱 서비스 - 성능 최적화
- Redis 기반 캐싱
- 메모리 캐싱 (Redis 없을 때)
- 캐시 무효화 전략
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from functools import wraps
import os

logger = logging.getLogger(__name__)

# Redis 사용 가능 여부 확인
try:
    import redis
    REDIS_AVAILABLE = True
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True
    )
    # 연결 테스트
    redis_client.ping()
    logger.info("Redis 연결 성공")
except Exception as e:
    REDIS_AVAILABLE = False
    logger.warning(f"Redis 연결 실패, 메모리 캐시 사용: {e}")

class CacheService:
    """캐싱 서비스 클래스"""
    
    # 메모리 캐시 (Redis 없을 때 사용)
    _memory_cache: Dict[str, Dict[str, Any]] = {}
    
    @staticmethod
    def generate_cache_key(prefix: str, *args, **kwargs) -> str:
        """캐시 키 생성"""
        content = f"{prefix}:{':'.join(map(str, args))}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @staticmethod
    def get(key: str, default: Any = None) -> Optional[Any]:
        """캐시에서 값 조회"""
        try:
            if REDIS_AVAILABLE:
                value = redis_client.get(key)
                return json.loads(value) if value else default
            else:
                cache_item = CacheService._memory_cache.get(key)
                if cache_item and cache_item['expires_at'] > datetime.now():
                    return cache_item['value']
                else:
                    # 만료된 항목 제거
                    CacheService._memory_cache.pop(key, None)
                    return default
        except Exception as e:
            logger.error(f"캐시 조회 실패: key={key}, error={e}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = 3600) -> bool:
        """캐시에 값 저장"""
        try:
            if REDIS_AVAILABLE:
                return redis_client.setex(key, ttl, json.dumps(value))
            else:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                CacheService._memory_cache[key] = {
                    'value': value,
                    'expires_at': expires_at
                }
                return True
        except Exception as e:
            logger.error(f"캐시 저장 실패: key={key}, error={e}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """캐시에서 값 삭제"""
        try:
            if REDIS_AVAILABLE:
                return bool(redis_client.delete(key))
            else:
                return bool(CacheService._memory_cache.pop(key, None))
        except Exception as e:
            logger.error(f"캐시 삭제 실패: key={key}, error={e}")
            return False
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """패턴에 맞는 캐시 삭제"""
        try:
            if REDIS_AVAILABLE:
                keys = redis_client.keys(pattern)
                if keys:
                    return redis_client.delete(*keys)
                return 0
            else:
                # 메모리 캐시에서는 패턴 매칭 구현
                deleted_count = 0
                keys_to_delete = []
                for key in CacheService._memory_cache.keys():
                    if pattern.replace('*', '') in key:
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    if CacheService._memory_cache.pop(key, None):
                        deleted_count += 1
                
                return deleted_count
        except Exception as e:
            logger.error(f"패턴 캐시 삭제 실패: pattern={pattern}, error={e}")
            return 0
    
    @staticmethod
    def clear_all() -> bool:
        """모든 캐시 삭제"""
        try:
            if REDIS_AVAILABLE:
                redis_client.flushdb()
            else:
                CacheService._memory_cache.clear()
            return True
        except Exception as e:
            logger.error(f"캐시 전체 삭제 실패: error={e}")
            return False
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """캐시 통계 정보"""
        try:
            if REDIS_AVAILABLE:
                info = redis_client.info()
                return {
                    "type": "redis",
                    "connected_clients": info.get('connected_clients', 0),
                    "used_memory_human": info.get('used_memory_human', '0B'),
                    "keyspace_hits": info.get('keyspace_hits', 0),
                    "keyspace_misses": info.get('keyspace_misses', 0)
                }
            else:
                return {
                    "type": "memory",
                    "total_items": len(CacheService._memory_cache),
                    "memory_usage": "N/A"
                }
        except Exception as e:
            logger.error(f"캐시 통계 조회 실패: error={e}")
            return {"type": "unknown", "error": str(e)}

# 캐시 데코레이터
def cached(prefix: str, ttl: int = 3600):
    """
    함수 결과를 캐시하는 데코레이터
    
    Args:
        prefix: 캐시 키 접두사
        ttl: 캐시 유효 시간 (초)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = CacheService.generate_cache_key(prefix, *args, **kwargs)
            
            # 캐시에서 조회
            cached_result = CacheService.get(cache_key)
            if cached_result is not None:
                logger.debug(f"캐시 히트: {cache_key}")
                return cached_result
            
            # 함수 실행
            result = func(*args, **kwargs)
            
            # 결과 캐시
            CacheService.set(cache_key, result, ttl)
            logger.debug(f"캐시 저장: {cache_key}")
            
            return result
        return wrapper
    return decorator

# 특정 캐시 무효화 데코레이터
def invalidate_cache(prefix: str):
    """
    함수 실행 후 특정 캐시를 무효화하는 데코레이터
    
    Args:
        prefix: 무효화할 캐시 키 접두사
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # 캐시 무효화
            pattern = f"{prefix}:*"
            deleted_count = CacheService.delete_pattern(pattern)
            logger.debug(f"캐시 무효화: {pattern}, 삭제된 항목: {deleted_count}")
            
            return result
        return wrapper
    return decorator

# 상품 관련 캐시 키 상수
class CacheKeys:
    """캐시 키 상수"""
    PRODUCT_LIST = "product:list"
    PRODUCT_DETAIL = "product:detail"
    PRODUCT_CATEGORIES = "product:categories"
    USER_POINTS = "user:points"
    USER_PURCHASES = "user:purchases"
    FORTUNE_PACKAGES = "fortune:packages"
    SHOP_STATS = "shop:stats" 