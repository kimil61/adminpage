#!/usr/bin/env python3
"""Celery 워커 실행 스크립트"""

import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

def start_celery_worker():
    """Celery 워커 시작"""
    cmd = [
        'celery', '-A', 'app.celery_app', 'worker',
        '--loglevel=info',
        '--pool=solo',  # Windows 호환성
        '--concurrency=2'
    ]
    
    print("🚀 Celery 워커 시작 중...")
    print(f"실행 명령어: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n📴 Celery 워커 종료")
    except subprocess.CalledProcessError as e:
        print(f"❌ Celery 워커 실행 실패: {e}")

def start_celery_beat():
    """Celery Beat 스케줄러 시작"""
    cmd = [
        'celery', '-A', 'app.celery_app', 'beat',
        '--loglevel=info'
    ]
    
    print("⏰ Celery Beat 시작 중...")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'beat':
        start_celery_beat()
    else:
        start_celery_worker()