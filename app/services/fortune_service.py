"""
행운 포인트 관리 서비스 - 트랜잭션 안전성 보장
- SELECT FOR UPDATE 락
- 포인트 충전/사용/만료 관리
- 패키지 관리
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models import (
    UserFortunePoint, FortuneTransaction, FortunePackage, 
    User, UserPurchase, Order
)
from app.exceptions import BadRequestError, NotFoundError, InternalServerError
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

class FortuneService:
    """행운 포인트 관리 서비스"""
    
    @staticmethod
    def get_user_fortune_info(user_id: int, db: Session) -> Dict[str, Any]:
        """
        사용자 행운 포인트 정보 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing fortune point information
        """
        try:
            # 포인트 정보 조회
            fortune_point = db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).first()
            
            if not fortune_point:
                # 포인트 레코드가 없으면 기본값 반환
                return {
                    "points": 0,
                    "total_earned": 0,
                    "total_spent": 0,
                    "last_updated": None,
                    "expiring_soon": [],
                    "recent_transactions": []
                }
            
            # 만료 예정 포인트 조회 (30일 이내)
            expiring_soon = db.query(FortuneTransaction).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == "earn",
                    FortuneTransaction.expires_at.isnot(None),
                    FortuneTransaction.expires_at <= datetime.now() + timedelta(days=30),
                    FortuneTransaction.expires_at > datetime.now()
                )
            ).order_by(FortuneTransaction.expires_at).limit(5).all()
            
            # 최근 거래 내역 조회
            recent_transactions = db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            ).order_by(FortuneTransaction.created_at.desc()).limit(10).all()
            
            return {
                "points": fortune_point.points,
                "total_earned": fortune_point.total_earned,
                "total_spent": fortune_point.total_spent,
                "last_updated": fortune_point.last_updated,
                "expiring_soon": expiring_soon,
                "recent_transactions": recent_transactions
            }
            
        except Exception as e:
            logger.error(f"행운 포인트 정보 조회 실패: user_id={user_id}, error={e}")
            raise InternalServerError("포인트 정보 조회 중 오류가 발생했습니다.")

    @staticmethod
    def get_charge_packages(db: Session) -> List[FortunePackage]:
        """
        충전 패키지 목록 조회
        
        Args:
            db: 데이터베이스 세션
            
        Returns:
            List of FortunePackage objects
        """
        try:
            packages = db.query(FortunePackage).filter(
                FortunePackage.is_active == True
            ).order_by(FortunePackage.sort_order, FortunePackage.id).all()
            
            return packages
            
        except Exception as e:
            logger.error(f"충전 패키지 조회 실패: error={e}")
            raise InternalServerError("충전 패키지 조회 중 오류가 발생했습니다.")

    @staticmethod
    def get_package_by_id(package_id: int, db: Session) -> Optional[FortunePackage]:
        """
        패키지 ID로 조회
        
        Args:
            package_id: 패키지 ID
            db: 데이터베이스 세션
            
        Returns:
            FortunePackage object or None
        """
        try:
            package = db.query(FortunePackage).filter(
                FortunePackage.id == package_id,
                FortunePackage.is_active == True
            ).first()
            
            return package
            
        except Exception as e:
            logger.error(f"패키지 조회 실패: package_id={package_id}, error={e}")
            return None

    @staticmethod
    def process_charge_completion(
        user_id: int,
        package_id: int,
        order_id: int,
        db: Session
    ) -> bool:
        """
        충전 완료 처리 - Order + FortuneTransaction 원자성
        
        Args:
            user_id: 사용자 ID
            package_id: 패키지 ID
            order_id: 주문 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 성공 여부
        """
        try:
            with db.begin():
                # 패키지 조회
                package = db.query(FortunePackage).filter(
                    FortunePackage.id == package_id,
                    FortunePackage.is_active == True
                ).first()
                
                if not package:
                    raise NotFoundError("유효하지 않은 충전 패키지입니다.")
                
                # 주문 조회
                order = db.query(Order).filter(
                    Order.id == order_id,
                    Order.user_id == user_id,
                    Order.status == "paid"
                ).first()
                
                if not order:
                    raise NotFoundError("유효하지 않은 주문입니다.")
                
                # 포인트 적립
                total_points = package.fortune_points + package.bonus_points
                success = PaymentService.process_point_earn(
                    user_id=user_id,
                    amount=total_points,
                    source="package_charge",
                    reference_id=f"order_{order_id}",
                    expires_days=package.expires_days,
                    db=db
                )
                
                if success:
                    logger.info(f"충전 완료 처리 성공: user_id={user_id}, package_id={package_id}, points={total_points}")
                    return True
                else:
                    raise InternalServerError("포인트 적립 처리에 실패했습니다.")
                    
        except Exception as e:
            logger.error(f"충전 완료 처리 실패: user_id={user_id}, package_id={package_id}, error={e}")
            raise

    @staticmethod
    def use_points_for_purchase(
        user_id: int,
        product_id: int,
        points_needed: int,
        db: Session
    ) -> Tuple[bool, str]:
        """
        상품 구매를 위한 포인트 사용
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            points_needed: 필요한 포인트
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
        """
        try:
            # 포인트 사용 처리
            success = PaymentService.process_point_usage(
                user_id=user_id,
                amount=points_needed,
                source="product_purchase",
                reference_id=f"product_{product_id}",
                db=db
            )
            
            if success:
                # UserPurchase 생성
                purchase = UserPurchase(
                    user_id=user_id,
                    product_id=product_id,
                    purchase_type="fortune_points",
                    original_price=0,  # 포인트 구매는 0원
                    paid_amount=0,
                    fortune_points_used=points_needed,
                    created_at=datetime.now()
                )
                db.add(purchase)
                db.commit()
                
                logger.info(f"포인트 구매 성공: user_id={user_id}, product_id={product_id}, points={points_needed}")
                return True, "포인트 구매가 완료되었습니다."
            else:
                return False, "포인트 사용 처리에 실패했습니다."
                
        except BadRequestError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"포인트 구매 실패: user_id={user_id}, product_id={product_id}, error={e}")
            return False, "구매 처리 중 오류가 발생했습니다."

    @staticmethod
    def get_transaction_history(
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        transaction_type: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        거래 내역 조회 (페이징)
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수
            transaction_type: 거래 타입 필터
            db: 데이터베이스 세션
            
        Returns:
            Dict containing transactions and pagination info
        """
        try:
            offset = (page - 1) * per_page
            
            # 쿼리 구성
            query = db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            )
            
            # 거래 타입 필터
            if transaction_type:
                query = query.filter(FortuneTransaction.transaction_type == transaction_type)
            
            # 거래 내역 조회
            transactions = query.order_by(
                FortuneTransaction.created_at.desc()
            ).offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total_query = db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            )
            if transaction_type:
                total_query = total_query.filter(FortuneTransaction.transaction_type == transaction_type)
            
            total = total_query.count()
            
            return {
                "transactions": transactions,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: user_id={user_id}, error={e}")
            raise InternalServerError("거래 내역 조회 중 오류가 발생했습니다.")

    @staticmethod
    def check_expiring_points(user_id: int, db: Session) -> List[Dict[str, Any]]:
        """
        만료 예정 포인트 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            List of expiring point information
        """
        try:
            # 7일 이내 만료되는 포인트 조회
            expiring_transactions = db.query(FortuneTransaction).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == "earn",
                    FortuneTransaction.expires_at.isnot(None),
                    FortuneTransaction.expires_at <= datetime.now() + timedelta(days=7),
                    FortuneTransaction.expires_at > datetime.now()
                )
            ).order_by(FortuneTransaction.expires_at).all()
            
            result = []
            for transaction in expiring_transactions:
                days_until_expiry = (transaction.expires_at - datetime.now()).days
                result.append({
                    "transaction_id": transaction.id,
                    "amount": transaction.amount,
                    "expires_at": transaction.expires_at,
                    "days_until_expiry": days_until_expiry,
                    "source": transaction.source
                })
            
            return result
            
        except Exception as e:
            logger.error(f"만료 예정 포인트 조회 실패: user_id={user_id}, error={e}")
            return []

    @staticmethod
    def get_fortune_statistics(user_id: int, db: Session) -> Dict[str, Any]:
        """
        행운 포인트 통계 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing fortune point statistics
        """
        try:
            # 기본 포인트 정보
            fortune_point = db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).first()
            
            if not fortune_point:
                return {
                    "current_points": 0,
                    "total_earned": 0,
                    "total_spent": 0,
                    "monthly_earned": 0,
                    "monthly_spent": 0,
                    "top_sources": []
                }
            
            # 이번 달 적립/사용 통계
            current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            monthly_earned = db.query(FortuneTransaction).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == "earn",
                    FortuneTransaction.created_at >= current_month
                )
            ).with_entities(
                db.func.sum(FortuneTransaction.amount)
            ).scalar() or 0
            
            monthly_spent = db.query(FortuneTransaction).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == "spend",
                    FortuneTransaction.created_at >= current_month
                )
            ).with_entities(
                db.func.sum(FortuneTransaction.amount)
            ).scalar() or 0
            
            # 상위 적립 소스
            top_sources = db.query(
                FortuneTransaction.source,
                db.func.sum(FortuneTransaction.amount).label('total_amount')
            ).filter(
                and_(
                    FortuneTransaction.user_id == user_id,
                    FortuneTransaction.transaction_type == "earn"
                )
            ).group_by(FortuneTransaction.source).order_by(
                db.func.sum(FortuneTransaction.amount).desc()
            ).limit(5).all()
            
            return {
                "current_points": fortune_point.points,
                "total_earned": fortune_point.total_earned,
                "total_spent": fortune_point.total_spent,
                "monthly_earned": monthly_earned,
                "monthly_spent": abs(monthly_spent),  # 음수를 양수로 변환
                "top_sources": [
                    {"source": source, "amount": amount} 
                    for source, amount in top_sources
                ]
            }
            
        except Exception as e:
            logger.error(f"행운 포인트 통계 조회 실패: user_id={user_id}, error={e}")
            raise InternalServerError("포인트 통계 조회 중 오류가 발생했습니다.")

# 유틸리티 함수들
def format_points(points: int) -> str:
    """포인트 포맷팅"""
    return f"{points:,}P"

def calculate_bonus_points(base_points: int, bonus_rate: float) -> int:
    """보너스 포인트 계산"""
    return int(base_points * bonus_rate / 100)

def get_expiry_warning_days() -> int:
    """만료 경고 일수"""
    return 7  # 7일 전부터 경고 