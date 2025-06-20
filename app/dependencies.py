# app/dependencies.py
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """현재 로그인된 사용자 반환"""
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")
    
    return user

def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """로그인 선택사항 - 로그인되지 않아도 None 반환"""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    return user