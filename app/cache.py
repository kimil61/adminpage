from functools import wraps
import pickle
import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0)


def cache_result(expire_time: int = 300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, expire_time, pickle.dumps(result))
            return result
        return wrapper
    return decorator
