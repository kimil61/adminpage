#!/usr/bin/env python3
"""
FastAPI + Jinja2 웹사이트 실행 스크립트
"""

import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    
    # 개발/운영 모드 설정
    debug_mode = os.getenv("DEBUG", "True").lower() == "true"
    
    print("🚀 FastAPI + Jinja2 웹사이트 시작!")
    print(f"📍 모드: {'개발' if debug_mode else '운영'}")
    print("🌐 주소: http://localhost:8000")
    print("👑 관리자: http://localhost:8000/admin")
    print("📚 API 문서: http://localhost:8000/docs")
    print("\n종료하려면 Ctrl+C를 누르세요.\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=debug_mode,
        log_level="info" if debug_mode else "warning"
    )
