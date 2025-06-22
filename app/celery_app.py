from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Celery 앱 생성
celery_app = Celery(
    'saju_website',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['app.tasks']  # 태스크 모듈 포함
)

# Celery 설정
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10분 타임아웃
    task_soft_time_limit=540,  # 9분 소프트 타임아웃
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
)

# 태스크 스케줄링 (필요시)
celery_app.conf.beat_schedule = {
    'cleanup-old-cache': {
        'task': 'app.tasks.cleanup_old_cache',
        'schedule': 3600.0,  # 1시간마다 실행
    },
}