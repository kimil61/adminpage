"""
구독 서비스 - 정기구독 관리
- 구독 플랜 관리
- 자동 결제 및 갱신
- 구독 혜택 제공
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from fastapi import Depends
from app.models import (
    User, Subscription, Order, UserPurchase, 
    FortuneTransaction, UserFortunePoint
)
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError
from app.services.payment_service import PaymentService
from app.services.fortune_service import FortuneService

logger = logging.getLogger(__name__)

class SubscriptionService:
    """구독 서비스 클래스"""
    
    # 구독 플랜 정의
    SUBSCRIPTION_PLANS = {
        "basic": {
            "name": "베이직",
            "monthly_price": 9900,
            "monthly_fortune_points": 100,
            "discount_rate": 5.0,
            "priority_support": False,
            "exclusive_content": False,
            "description": "기본 운세 분석 서비스"
        },
        "premium": {
            "name": "프리미엄",
            "monthly_price": 19900,
            "monthly_fortune_points": 300,
            "discount_rate": 15.0,
            "priority_support": True,
            "exclusive_content": True,
            "description": "고급 운세 분석 및 우선 지원"
        },
        "vip": {
            "name": "VIP",
            "monthly_price": 39900,
            "monthly_fortune_points": 600,
            "discount_rate": 25.0,
            "priority_support": True,
            "exclusive_content": True,
            "description": "최고급 운세 분석 및 전용 서비스"
        }
    }
    
    @staticmethod
    def get_subscription_plans() -> Dict[str, Any]:
        """구독 플랜 목록 반환"""
        return SubscriptionService.SUBSCRIPTION_PLANS
    
    @staticmethod
    def get_user_subscription(user_id: int, db: Session) -> Optional[Subscription]:
        """사용자의 활성 구독 조회"""
        try:
            subscription = db.query(Subscription).filter(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == "active"
                )
            ).first()
            
            return subscription
            
        except Exception as e:
            logger.error(f"사용자 구독 조회 실패: user_id={user_id}, error={e}")
            return None
    
    @staticmethod
    def create_subscription(
        user_id: int,
        plan_type: str,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        구독 생성
        
        Args:
            user_id: 사용자 ID
            plan_type: 구독 플랜 타입
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 플랜 유효성 검사
            if plan_type not in SubscriptionService.SUBSCRIPTION_PLANS:
                return False, "유효하지 않은 구독 플랜입니다.", {}
            
            plan_info = SubscriptionService.SUBSCRIPTION_PLANS[plan_type]
            
            # 기존 활성 구독 확인
            existing_subscription = SubscriptionService.get_user_subscription(user_id, db)
            if existing_subscription:
                return False, "이미 활성 구독이 있습니다.", {}
            
            # 구독 생성
            subscription = Subscription(
                user_id=user_id,
                plan_type=plan_type,
                status="active",
                monthly_fortune_points=plan_info["monthly_fortune_points"],
                discount_rate=plan_info["discount_rate"],
                priority_support=plan_info["priority_support"],
                exclusive_content=plan_info["exclusive_content"],
                monthly_price=plan_info["monthly_price"],
                next_billing_date=date.today() + timedelta(days=30),
                auto_renewal=True,
                started_at=datetime.now()
            )
            
            db.add(subscription)
            db.commit()
            db.refresh(subscription)
            
            # 첫 달 포인트 지급
            if plan_info["monthly_fortune_points"] > 0:
                FortuneService.add_fortune_points(
                    user_id=user_id,
                    amount=plan_info["monthly_fortune_points"],
                    source="subscription_bonus",
                    reference_id=f"sub_{subscription.id}",
                    db=db
                )
            
            logger.info(f"구독 생성 성공: user_id={user_id}, plan_type={plan_type}")
            
            return True, "구독이 성공적으로 시작되었습니다.", {
                "subscription_id": subscription.id,
                "plan_type": plan_type,
                "next_billing_date": subscription.next_billing_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"구독 생성 실패: user_id={user_id}, plan_type={plan_type}, error={e}")
            db.rollback()
            return False, "구독 생성 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def cancel_subscription(
        user_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        구독 해지
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            subscription = SubscriptionService.get_user_subscription(user_id, db)
            if not subscription:
                return False, "활성 구독이 없습니다.", {}
            
            # 구독 해지 처리
            subscription.status = "cancelled"
            subscription.cancelled_at = datetime.now()
            subscription.ends_at = subscription.next_billing_date
            subscription.auto_renewal = False
            
            db.commit()
            
            logger.info(f"구독 해지 성공: user_id={user_id}, subscription_id={subscription.id}")
            
            return True, "구독이 해지되었습니다.", {
                "subscription_id": subscription.id,
                "ends_at": subscription.ends_at.isoformat() if subscription.ends_at else None
            }
            
        except Exception as e:
            logger.error(f"구독 해지 실패: user_id={user_id}, error={e}")
            db.rollback()
            return False, "구독 해지 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def pause_subscription(
        user_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        구독 일시정지
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            subscription = SubscriptionService.get_user_subscription(user_id, db)
            if not subscription:
                return False, "활성 구독이 없습니다.", {}
            
            subscription.status = "paused"
            db.commit()
            
            logger.info(f"구독 일시정지 성공: user_id={user_id}, subscription_id={subscription.id}")
            
            return True, "구독이 일시정지되었습니다.", {
                "subscription_id": subscription.id
            }
            
        except Exception as e:
            logger.error(f"구독 일시정지 실패: user_id={user_id}, error={e}")
            db.rollback()
            return False, "구독 일시정지 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def resume_subscription(
        user_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        구독 재개
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            subscription = db.query(Subscription).filter(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status == "paused"
                )
            ).first()
            
            if not subscription:
                return False, "일시정지된 구독이 없습니다.", {}
            
            subscription.status = "active"
            db.commit()
            
            logger.info(f"구독 재개 성공: user_id={user_id}, subscription_id={subscription.id}")
            
            return True, "구독이 재개되었습니다.", {
                "subscription_id": subscription.id
            }
            
        except Exception as e:
            logger.error(f"구독 재개 실패: user_id={user_id}, error={e}")
            db.rollback()
            return False, "구독 재개 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def process_monthly_billing(db: Session) -> Dict[str, Any]:
        """
        월간 결제 처리 (스케줄러에서 호출)
        
        Args:
            db: 데이터베이스 세션
            
        Returns:
            Dict containing billing results
        """
        try:
            today = date.today()
            
            # 결제 예정인 구독 조회
            subscriptions = db.query(Subscription).filter(
                and_(
                    Subscription.status == "active",
                    Subscription.next_billing_date <= today,
                    Subscription.auto_renewal == True
                )
            ).all()
            
            results = {
                "total_subscriptions": len(subscriptions),
                "successful_billings": 0,
                "failed_billings": 0,
                "errors": []
            }
            
            for subscription in subscriptions:
                try:
                    # 결제 처리
                    success = SubscriptionService._process_subscription_payment(subscription, db)
                    
                    if success:
                        # 다음 결제일 업데이트
                        subscription.last_billing_date = subscription.next_billing_date
                        subscription.next_billing_date = subscription.next_billing_date + timedelta(days=30)
                        
                        # 월간 포인트 지급
                        if subscription.monthly_fortune_points > 0:
                            FortuneService.add_fortune_points(
                                user_id=subscription.user_id,
                                amount=subscription.monthly_fortune_points,
                                source="subscription_monthly",
                                reference_id=f"sub_{subscription.id}",
                                db=db
                            )
                        
                        results["successful_billings"] += 1
                        logger.info(f"구독 결제 성공: subscription_id={subscription.id}")
                        
                    else:
                        # 결제 실패 시 구독 상태 변경
                        subscription.status = "expired"
                        results["failed_billings"] += 1
                        logger.warning(f"구독 결제 실패: subscription_id={subscription.id}")
                        
                except Exception as e:
                    results["failed_billings"] += 1
                    results["errors"].append(f"subscription_id={subscription.id}: {str(e)}")
                    logger.error(f"구독 결제 처리 실패: subscription_id={subscription.id}, error={e}")
            
            db.commit()
            return results
            
        except Exception as e:
            logger.error(f"월간 결제 처리 실패: error={e}")
            db.rollback()
            return {"error": str(e)}
    
    @staticmethod
    def _process_subscription_payment(subscription: Subscription, db: Session) -> bool:
        """
        개별 구독 결제 처리
        
        Args:
            subscription: 구독 객체
            db: 데이터베이스 세션
            
        Returns:
            bool: 결제 성공 여부
        """
        try:
            # TODO: 실제 결제 처리 로직 구현
            # 현재는 성공으로 가정 (개발 모드)
            
            # 주문 기록 생성
            order = Order(
                user_id=subscription.user_id,
                product_id=1,  # 구독 상품 ID
                amount=subscription.monthly_price,
                kakao_tid=f"SUB_{subscription.id}_{datetime.now().strftime('%Y%m%d')}",
                saju_key="subscription",
                status="paid",
                subscription_id=subscription.id,
                payment_method="subscription",
                is_subscription_payment=True,
                billing_cycle=1
            )
            
            db.add(order)
            return True
            
        except Exception as e:
            logger.error(f"구독 결제 처리 실패: subscription_id={subscription.id}, error={e}")
            return False
    
    @staticmethod
    def get_subscription_benefits(user_id: int, db: Session) -> Dict[str, Any]:
        """
        구독 혜택 정보 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing subscription benefits
        """
        try:
            subscription = SubscriptionService.get_user_subscription(user_id, db)
            
            if not subscription:
                return {
                    "has_subscription": False,
                    "benefits": {}
                }
            
            plan_info = SubscriptionService.SUBSCRIPTION_PLANS.get(subscription.plan_type, {})
            
            return {
                "has_subscription": True,
                "subscription": {
                    "id": subscription.id,
                    "plan_type": subscription.plan_type,
                    "plan_name": plan_info.get("name", ""),
                    "status": subscription.status,
                    "next_billing_date": subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
                    "auto_renewal": subscription.auto_renewal
                },
                "benefits": {
                    "monthly_fortune_points": subscription.monthly_fortune_points,
                    "discount_rate": float(subscription.discount_rate),
                    "priority_support": subscription.priority_support,
                    "exclusive_content": subscription.exclusive_content
                }
            }
            
        except Exception as e:
            logger.error(f"구독 혜택 조회 실패: user_id={user_id}, error={e}")
            return {"has_subscription": False, "benefits": {}}
    
    @staticmethod
    def apply_subscription_discount(
        original_price: int,
        user_id: int,
        db: Session
    ) -> Tuple[int, float]:
        """
        구독 할인 적용
        
        Args:
            original_price: 원래 가격
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[int, float]: (할인된 가격, 할인율)
        """
        try:
            subscription = SubscriptionService.get_user_subscription(user_id, db)
            
            if not subscription or subscription.status != "active":
                return original_price, 0.0
            
            discount_rate = float(subscription.discount_rate)
            discount_amount = int(original_price * discount_rate / 100)
            discounted_price = original_price - discount_amount
            
            return discounted_price, discount_rate
            
        except Exception as e:
            logger.error(f"구독 할인 적용 실패: user_id={user_id}, error={e}")
            return original_price, 0.0 