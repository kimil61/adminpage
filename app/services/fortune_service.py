"""
행운 포인트 관리 서비스 - 트랜잭션 안전성 보장
Week 1: 핵심 인프라 - 포인트 시스템 완전 구현
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.database import get_db
from app.models import (
    User, UserFortunePoint, FortuneTransaction, 
    FortunePackage, UserPurchase, Order
)
from app.utils.error_handlers import InsufficientPointsError, ValidationError

logger = logging.getLogger(__name__)

class FortuneService:
    """행운 포인트 관리 서비스 - SELECT FOR UPDATE 락으로 동시성 제어"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_balance(self, user_id: int) -> Dict[str, Any]:
        """
        사용자 포인트 잔액 및 통계 조회
        
        Args:
            user_id: 사용자 ID
        
        Returns:
            Dict: 포인트 잔액 및 통계 정보
        """
        try:
            user_points = self.db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).first()
            
            if not user_points:
                return {
                    'points': 0,
                    'total_earned': 0,
                    'total_spent': 0,
                    'last_updated': None
                }
            
            return {
                'points': user_points.points,
                'total_earned': user_points.total_earned,
                'total_spent': user_points.total_spent,
                'last_updated': user_points.last_updated
            }
            
        except Exception as e:
            logger.error(f"Balance query error: user_id={user_id}, error={e}")
            raise ValidationError("포인트 잔액 조회 중 오류가 발생했습니다.")
    
    def use_points_safely(
        self,
        user_id: int,
        amount: int,
        source: str,
        reference_id: str
    ) -> bool:
        """
        포인트 사용 - SELECT FOR UPDATE 락으로 동시성 제어
        
        Args:
            user_id: 사용자 ID
            amount: 사용할 포인트 양
            source: 사용 소스 (purchase, subscription 등)
            reference_id: 참조 ID
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 사용자 포인트 잔액 락 (SELECT FOR UPDATE)
            user_points = self.db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).with_for_update().first()
            
            if not user_points:
                # 포인트 레코드가 없으면 생성
                user_points = UserFortunePoint(
                    user_id=user_id,
                    points=0,
                    total_earned=0,
                    total_spent=0
                )
                self.db.add(user_points)
                self.db.flush()  # ID 생성
                self.db.refresh(user_points)
            
            # 2. 잔액 확인
            if user_points.points < amount:
                raise InsufficientPointsError(f"포인트가 부족합니다. 필요: {amount}, 보유: {user_points.points}")
            
            # 3. 포인트 차감
            user_points.points -= amount
            user_points.total_spent += amount
            user_points.last_updated = datetime.now()
            
            # 4. 거래 내역 생성
            transaction = FortuneTransaction(
                user_id=user_id,
                transaction_type='spend',
                amount=-amount,  # 음수로 기록
                balance_after=user_points.points,
                source=source,
                reference_id=reference_id,
                description=f"{source} 포인트 사용"
            )
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(f"Points used: user_id={user_id}, amount={amount}, source={source}")
            return True
            
        except InsufficientPointsError:
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Point usage error: {e}")
            self.db.rollback()
            raise ValidationError("포인트 사용 중 오류가 발생했습니다.")
    
    def earn_points_safely(
        self,
        user_id: int,
        amount: int,
        source: str,
        reference_id: str,
        expires_days: int = 365
    ) -> bool:
        """
        포인트 적립 - 트랜잭션 안전성 보장
        
        Args:
            user_id: 사용자 ID
            amount: 적립할 포인트 양
            source: 적립 소스 (purchase, referral, daily_bonus 등)
            reference_id: 참조 ID
            expires_days: 만료일 (일)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 사용자 포인트 잔액 락 (SELECT FOR UPDATE)
            user_points = self.db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).with_for_update().first()
            
            if not user_points:
                # 포인트 레코드가 없으면 생성
                user_points = UserFortunePoint(
                    user_id=user_id,
                    points=0,
                    total_earned=0,
                    total_spent=0
                )
                self.db.add(user_points)
                self.db.flush()  # ID 생성
                self.db.refresh(user_points)
            
            # 2. 포인트 적립
            user_points.points += amount
            user_points.total_earned += amount
            user_points.last_updated = datetime.now()
            
            # 3. 거래 내역 생성
            expires_at = datetime.now() + timedelta(days=expires_days) if expires_days > 0 else None
            
            transaction = FortuneTransaction(
                user_id=user_id,
                transaction_type='earn',
                amount=amount,
                balance_after=user_points.points,
                source=source,
                reference_id=reference_id,
                description=f"{source} 포인트 적립",
                expires_at=expires_at
            )
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(f"Points earned: user_id={user_id}, amount={amount}, source={source}")
            return True
            
        except Exception as e:
            logger.error(f"Point earning error: {e}")
            self.db.rollback()
            raise ValidationError("포인트 적립 중 오류가 발생했습니다.")
    
    def get_transactions(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        transaction_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        포인트 거래 내역 조회 (페이징)
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수
            transaction_type: 거래 타입 필터 (earn, spend, refund, expire)
        
        Returns:
            Dict: 거래 내역 및 페이징 정보
        """
        try:
            offset = (page - 1) * per_page
            
            # 쿼리 구성
            query = self.db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            )
            
            # 거래 타입 필터
            if transaction_type:
                query = query.filter(FortuneTransaction.transaction_type == transaction_type)
            
            # 전체 개수 조회
            total = query.count()
            
            # 거래 내역 조회 (최신순)
            transactions = query.order_by(
                desc(FortuneTransaction.created_at)
            ).offset(offset).limit(per_page).all()
            
            return {
                'transactions': [
                    {
                        'id': t.id,
                        'type': t.transaction_type,
                        'amount': t.amount,
                        'balance_after': t.balance_after,
                        'source': t.source,
                        'description': t.description,
                        'expires_at': t.expires_at,
                        'created_at': t.created_at
                    }
                    for t in transactions
                ],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"Transaction query error: user_id={user_id}, error={e}")
            raise ValidationError("거래 내역 조회 중 오류가 발생했습니다.")
    
    def get_packages(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        포인트 충전 패키지 목록 조회
        
        Args:
            user_id: 사용자 ID (할인 적용을 위해)
        
        Returns:
            List: 패키지 목록
        """
        try:
            packages = self.db.query(FortunePackage).filter(
                FortunePackage.is_active.is_(True)
            ).order_by(FortunePackage.sort_order, FortunePackage.id).all()
            
            result = []
            for package in packages:
                package_data = {
                    'id': package.id,
                    'name': package.name,
                    'description': package.description,
                    'fortune_points': package.fortune_points,
                    'bonus_points': package.bonus_points,
                    'total_points': package.fortune_points + package.bonus_points,
                    'price': package.price,
                    'discount_rate': float(package.discount_rate),
                    'expires_days': package.expires_days,
                    'is_featured': package.is_featured
                }
                
                # 할인 적용
                if package.discount_rate > 0:
                    discounted_price = int(package.price * (1 - package.discount_rate / 100))
                    package_data['original_price'] = package.price
                    package_data['discounted_price'] = discounted_price
                    package_data['savings'] = package.price - discounted_price
                
                result.append(package_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Package query error: error={e}")
            raise ValidationError("패키지 목록 조회 중 오류가 발생했습니다.")
    
    def process_package_purchase(
        self,
        user_id: int,
        package_id: int,
        order_id: int
    ) -> bool:
        """
        패키지 구매 완료 후 포인트 적립 처리
        
        Args:
            user_id: 사용자 ID
            package_id: 패키지 ID
            order_id: 주문 ID
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 패키지 정보 조회
            package = self.db.query(FortunePackage).filter(
                FortunePackage.id == package_id,
                FortunePackage.is_active.is_(True)
            ).first()
            
            if not package:
                raise ValidationError("유효하지 않은 패키지입니다.")
            
            # 2. 주문 정보 조회
            order = self.db.query(Order).filter(
                Order.id == order_id,
                Order.user_id == user_id,
                Order.status == 'paid'
            ).first()
            
            if not order:
                raise ValidationError("유효하지 않은 주문입니다.")
            
            # 3. 포인트 적립
            total_points = package.fortune_points + package.bonus_points
            
            success = self.earn_points_safely(
                user_id=user_id,
                amount=total_points,
                source='package_purchase',
                reference_id=str(order_id),
                expires_days=package.expires_days
            )
            
            if success:
                logger.info(f"Package purchase processed: user_id={user_id}, package_id={package_id}, points={total_points}")
            
            return success
            
        except Exception as e:
            logger.error(f"Package purchase processing error: {e}")
            raise ValidationError("패키지 구매 처리 중 오류가 발생했습니다.")
    
    def get_expiring_points(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        만료 예정 포인트 조회
        
        Args:
            user_id: 사용자 ID
            days: 만료 예정일 (일)
        
        Returns:
            List: 만료 예정 포인트 목록
        """
        try:
            expiry_date = datetime.now() + timedelta(days=days)
            
            transactions = self.db.query(FortuneTransaction).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == 'earn',
                    FortuneTransaction.expires_at.isnot(None),
                    FortuneTransaction.expires_at <= expiry_date,
                    FortuneTransaction.expires_at > datetime.now()
                )
            ).order_by(FortuneTransaction.expires_at).all()
            
            return [
                {
                    'id': t.id,
                    'amount': t.amount,
                    'source': t.source,
                    'expires_at': t.expires_at,
                    'days_until_expiry': (t.expires_at - datetime.now()).days
                }
                for t in transactions
            ]
            
        except Exception as e:
            logger.error(f"Expiring points query error: user_id={user_id}, error={e}")
            raise ValidationError("만료 예정 포인트 조회 중 오류가 발생했습니다.")
    
    def calculate_discount(self, user_id: int, original_price: int) -> Dict[str, Any]:
        """
        포인트 할인 계산 (신규 사용자, 구독자 등)
        
        Args:
            user_id: 사용자 ID
            original_price: 원래 가격
        
        Returns:
            Dict: 할인 정보
        """
        try:
            # 1. 사용자 정보 조회
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {'discount_rate': 0, 'discount_amount': 0, 'final_price': original_price}
            
            # 2. 신규 사용자 할인 (첫 구매)
            purchase_count = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id
            ).count()
            
            discount_rate = 0
            if purchase_count == 0:
                discount_rate = 10  # 신규 사용자 10% 할인
            
            # 3. 구독자 할인 (추후 subscription_service.py와 연동)
            # TODO: 구독 등급별 할인율 적용
            
            # 4. 할인 계산
            discount_amount = int(original_price * discount_rate / 100)
            final_price = original_price - discount_amount
            
            return {
                'discount_rate': discount_rate,
                'discount_amount': discount_amount,
                'final_price': final_price,
                'is_new_user': purchase_count == 0
            }
            
        except Exception as e:
            logger.error(f"Discount calculation error: user_id={user_id}, error={e}")
            return {'discount_rate': 0, 'discount_amount': 0, 'final_price': original_price}

# 의존성 주입
def get_fortune_service(db: Session = Depends(get_db)) -> FortuneService:
    return FortuneService(db) 