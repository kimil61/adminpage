from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.models import UserPurchase, Order, UserReview, ReferralReward, Subscription

class MypageService:
    @staticmethod
    def get_dashboard(user_id: int, db: Session) -> Dict[str, Any]:
        purchases_count = db.query(UserPurchase).filter(UserPurchase.user_id == user_id).count()
        orders_count = db.query(Order).filter(Order.user_id == user_id).count()
        reviews_count = db.query(UserReview).filter(UserReview.user_id == user_id).count()
        referrals_count = db.query(ReferralReward).filter(ReferralReward.referrer_user_id == user_id).count()
        subscription = db.query(Subscription).filter(Subscription.user_id == user_id, Subscription.status == "active").first()
        return {
            "purchases_count": purchases_count,
            "orders_count": orders_count,
            "reviews_count": reviews_count,
            "referrals_count": referrals_count,
            "subscription": subscription,
        }

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