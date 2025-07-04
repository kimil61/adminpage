from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.models import UserPurchase

class MypageService:
    @staticmethod
    def get_dashboard(user_id: int, db: Session) -> Dict[str, Any]:
        # TODO: 실제 데이터로 대시보드 정보 구성
        return {"orders": [], "points": [], "reviews": []}

    @staticmethod
    def get_orders(user_id: int, db: Session) -> List[Dict[str, Any]]:
        # TODO: 실제 주문 내역 조회
        return []

    @staticmethod
    def get_points(user_id: int, db: Session) -> List[Dict[str, Any]]:
        # TODO: 실제 포인트 내역 조회
        return []

    @staticmethod
    def get_reviews(user_id: int, db: Session) -> List[Dict[str, Any]]:
        # TODO: 실제 리뷰 내역 조회
        return []

    @staticmethod
    def get_purchases(user_id: int, db: Session):
        return db.query(UserPurchase).filter(UserPurchase.user_id == user_id).order_by(UserPurchase.created_at.desc()).all() 