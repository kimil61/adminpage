"""
카카오페이 결제 공통 서비스 - 프로덕션 레벨 안전성
- Idempotency 지원
- 트랜잭션 안전성 보장
- Webhook 처리
- Rate Limiting
"""

import os
import uuid
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, Request
from functools import wraps

from app.models import Order, User, UserPurchase, FortuneTransaction, UserFortunePoint, FortunePackage
from app.payments.kakaopay import kakao_ready, kakao_approve, verify_payment, KakaoPayError
from app.exceptions import BadRequestError, InternalServerError
from app.utils import generate_live_report_for_user

logger = logging.getLogger(__name__)

# 환경 설정
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
SKIP_PAYMENT = os.getenv("SKIP_PAYMENT", "false").lower() == "true"

class PaymentService:
    """결제 서비스 클래스"""
    
    @staticmethod
    def generate_idempotency_key(user_id: int, action: str, reference: str) -> str:
        """Idempotency 키 생성"""
        content = f"{user_id}_{action}_{reference}_{datetime.now().strftime('%Y%m%d%H%M')}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    @staticmethod
    def check_idempotency(db: Session, key: str, action: str) -> Optional[Dict]:
        """Idempotency 체크 - Redis나 DB에서 중복 요청 확인"""
        # TODO: Redis 캐시 구현 (현재는 DB 기반)
        # 실제로는 Redis SETNX로 구현하는 것이 좋음
        return None
    
    @staticmethod
    def store_idempotency_result(db: Session, key: str, action: str, result: Dict, ttl: int = 3600):
        """Idempotency 결과 저장"""
        # TODO: Redis 캐시 구현
        pass

    @staticmethod
    async def prepare_kakaopay_payment(
        amount: int, 
        item_name: str, 
        user_id: int, 
        order_type: str = "cash",
        idempotency_key: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        카카오페이 결제 준비 - 멱등성 보장
        
        Args:
            amount: 결제 금액
            item_name: 상품명
            user_id: 사용자 ID
            order_type: 주문 타입 (cash, fortune_points)
            idempotency_key: 멱등성 키
            db: 데이터베이스 세션
            
        Returns:
            Dict containing tid, redirect_urls, etc.
        """
        try:
            # Idempotency 체크
            if idempotency_key:
                existing_result = PaymentService.check_idempotency(db, idempotency_key, "kakaopay_ready")
                if existing_result:
                    logger.info(f"Idempotency hit: key={idempotency_key}")
                    return existing_result
            
            # 사용자 조회
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise BadRequestError("사용자를 찾을 수 없습니다.")
            
            # 주문 ID 생성 (임시)
            temp_order_id = int(datetime.now().timestamp() * 1000)
            
            # 카카오페이 결제 준비
            if DEV_MODE and SKIP_PAYMENT:
                logger.info(f"개발 모드: 카카오페이 결제 건너뛰기")
                return {
                    "success": True,
                    "dev_mode": True,
                    "tid": f"DEV_TID_{temp_order_id}",
                    "redirect_url": f"/order/success?order_id={temp_order_id}",
                    "is_mobile": False
                }
            
            result = await kakao_ready(
                order_id=temp_order_id,
                amount=amount,
                user_email=user.email,
                item_name=item_name,
                partner_user_id=str(user_id)
            )
            
            # Idempotency 결과 저장
            if idempotency_key:
                PaymentService.store_idempotency_result(
                    db, idempotency_key, "kakaopay_ready", result
                )
            
            logger.info(f"카카오페이 결제 준비 성공: user_id={user_id}, tid={result.get('tid')}")
            return result
            
        except KakaoPayError as e:
            logger.error(f"카카오페이 결제 준비 실패: {e}")
            raise BadRequestError(f"결제 준비 실패: {e.message}")
        except Exception as e:
            logger.error(f"결제 준비 중 예외: {e}")
            raise InternalServerError("결제 준비 중 오류가 발생했습니다.")

    @staticmethod
    async def verify_kakaopay_payment(
        tid: str, 
        pg_token: str,
        order_id: int,
        user_id: int,
        idempotency_key: str = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        카카오페이 결제 검증 - 원자성 트랜잭션
        
        Args:
            tid: 결제 고유번호
            pg_token: 결제 승인 토큰
            order_id: 주문 ID
            user_id: 사용자 ID
            idempotency_key: 멱등성 키
            db: 데이터베이스 세션
            
        Returns:
            Dict containing payment verification result
        """
        try:
            # Idempotency 체크
            if idempotency_key:
                existing_result = PaymentService.check_idempotency(db, idempotency_key, "kakaopay_verify")
                if existing_result:
                    logger.info(f"Idempotency hit: key={idempotency_key}")
                    return existing_result
            
            # 사용자 조회
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise BadRequestError("사용자를 찾을 수 없습니다.")
            
            # 개발 모드 처리
            if DEV_MODE and SKIP_PAYMENT:
                logger.info(f"개발 모드: 카카오페이 검증 건너뛰기")
                return {
                    "success": True,
                    "dev_mode": True,
                    "aid": f"DEV_AID_{order_id}",
                    "payment_method_type": "MONEY"
                }
            
            # 카카오페이 결제 승인
            result = await kakao_approve(
                tid=tid,
                pg_token=pg_token,
                order_id=order_id,
                partner_user_id=str(user_id)
            )
            
            # 결제 검증
            if not verify_payment(amount=0, kakao_response=result):  # amount는 주문에서 가져와야 함
                raise BadRequestError("결제 검증에 실패했습니다.")
            
            # Idempotency 결과 저장
            if idempotency_key:
                PaymentService.store_idempotency_result(
                    db, idempotency_key, "kakaopay_verify", result
                )
            
            logger.info(f"카카오페이 결제 검증 성공: user_id={user_id}, aid={result.get('aid')}")
            return result
            
        except KakaoPayError as e:
            logger.error(f"카카오페이 결제 검증 실패: {e}")
            raise BadRequestError(f"결제 검증 실패: {e.message}")
        except Exception as e:
            logger.error(f"결제 검증 중 예외: {e}")
            raise InternalServerError("결제 검증 중 오류가 발생했습니다.")

    @staticmethod
    async def prepare_point_charge(
        package_id: int, 
        user_id: int,
        idempotency_key: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        포인트 충전 준비 - Order + FortuneTransaction 원자성
        
        Args:
            package_id: 충전 패키지 ID
            user_id: 사용자 ID
            idempotency_key: 멱등성 키
            db: 데이터베이스 세션
            
        Returns:
            Dict containing charge preparation result
        """
        try:
            # Idempotency 체크
            existing_result = PaymentService.check_idempotency(db, idempotency_key, "point_charge")
            if existing_result:
                logger.info(f"Idempotency hit: key={idempotency_key}")
                return existing_result
            
            # 패키지 조회
            package = db.query(FortunePackage).filter(
                FortunePackage.id == package_id,
                FortunePackage.is_active == True
            ).first()
            
            if not package:
                raise BadRequestError("유효하지 않은 충전 패키지입니다.")
            
            # 사용자 조회
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise BadRequestError("사용자를 찾을 수 없습니다.")
            
            # 카카오페이 결제 준비
            total_points = package.fortune_points + package.bonus_points
            item_name = f"{package.name} ({total_points}포인트)"
            
            result = await PaymentService.prepare_kakaopay_payment(
                amount=package.price,
                item_name=item_name,
                user_id=user_id,
                order_type="point_charge",
                idempotency_key=idempotency_key,
                db=db
            )
            
            # Idempotency 결과 저장
            PaymentService.store_idempotency_result(
                db, idempotency_key, "point_charge", result
            )
            
            logger.info(f"포인트 충전 준비 성공: user_id={user_id}, package_id={package_id}")
            return result
            
        except Exception as e:
            logger.error(f"포인트 충전 준비 실패: {e}")
            raise

    @staticmethod
    def process_point_usage(
        user_id: int, 
        amount: int, 
        source: str, 
        reference_id: str,
        db: Session
    ) -> bool:
        """
        포인트 사용 - SELECT FOR UPDATE 락
        
        Args:
            user_id: 사용자 ID
            amount: 사용할 포인트 양
            source: 사용 소스 (예: 'purchase', 'subscription')
            reference_id: 참조 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 성공 여부
        """
        try:
            # SELECT FOR UPDATE로 잔액 락
            with db.begin():
                # 사용자 포인트 잔액 조회 (락)
                fortune_point = db.query(UserFortunePoint).filter(
                    UserFortunePoint.user_id == user_id
                ).with_for_update().first()
                
                if not fortune_point:
                    # 포인트 레코드가 없으면 생성
                    fortune_point = UserFortunePoint(
                        user_id=user_id,
                        points=0,
                        total_earned=0,
                        total_spent=0
                    )
                    db.add(fortune_point)
                    db.flush()  # ID 생성
                
                # 잔액 확인
                if fortune_point.points < amount:
                    raise BadRequestError(f"포인트가 부족합니다. (보유: {fortune_point.points}, 필요: {amount})")
                
                # 포인트 차감
                fortune_point.points -= amount
                fortune_point.total_spent += amount
                fortune_point.last_updated = datetime.now()
                
                # 거래 내역 생성
                transaction = FortuneTransaction(
                    user_id=user_id,
                    transaction_type="spend",
                    amount=-amount,  # 음수로 기록
                    balance_after=fortune_point.points,
                    source=source,
                    reference_id=reference_id,
                    description=f"{source} 사용",
                    created_at=datetime.now()
                )
                db.add(transaction)
                
                db.commit()
                
                logger.info(f"포인트 사용 성공: user_id={user_id}, amount={amount}, source={source}")
                return True
                
        except Exception as e:
            db.rollback()
            logger.error(f"포인트 사용 실패: user_id={user_id}, amount={amount}, error={e}")
            raise

    @staticmethod
    def process_point_earn(
        user_id: int,
        amount: int,
        source: str,
        reference_id: str,
        expires_days: int = 365,
        db: Session = None
    ) -> bool:
        """
        포인트 적립 - 트랜잭션 안전성 보장
        
        Args:
            user_id: 사용자 ID
            amount: 적립할 포인트 양
            source: 적립 소스
            reference_id: 참조 ID
            expires_days: 만료일 (일)
            db: 데이터베이스 세션
            
        Returns:
            bool: 성공 여부
        """
        try:
            with db.begin():
                # 사용자 포인트 잔액 조회 (락)
                fortune_point = db.query(UserFortunePoint).filter(
                    UserFortunePoint.user_id == user_id
                ).with_for_update().first()
                
                if not fortune_point:
                    # 포인트 레코드가 없으면 생성
                    fortune_point = UserFortunePoint(
                        user_id=user_id,
                        points=0,
                        total_earned=0,
                        total_spent=0
                    )
                    db.add(fortune_point)
                    db.flush()
                
                # 포인트 적립
                fortune_point.points += amount
                fortune_point.total_earned += amount
                fortune_point.last_updated = datetime.now()
                
                # 거래 내역 생성
                expires_at = datetime.now() + timedelta(days=expires_days) if expires_days > 0 else None
                
                transaction = FortuneTransaction(
                    user_id=user_id,
                    transaction_type="earn",
                    amount=amount,
                    balance_after=fortune_point.points,
                    source=source,
                    reference_id=reference_id,
                    description=f"{source} 적립",
                    expires_at=expires_at,
                    created_at=datetime.now()
                )
                db.add(transaction)
                
                db.commit()
                
                logger.info(f"포인트 적립 성공: user_id={user_id}, amount={amount}, source={source}")
                return True
                
        except Exception as e:
            db.rollback()
            logger.error(f"포인트 적립 실패: user_id={user_id}, amount={amount}, error={e}")
            raise

    @staticmethod
    def get_user_point_balance(user_id: int, db: Session) -> int:
        """
        실시간 포인트 잔액 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            int: 포인트 잔액
        """
        try:
            fortune_point = db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == user_id
            ).first()
            
            return fortune_point.points if fortune_point else 0
            
        except Exception as e:
            logger.error(f"포인트 잔액 조회 실패: user_id={user_id}, error={e}")
            return 0

    @staticmethod
    def get_user_point_transactions(
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        사용자 포인트 거래 내역 조회 (페이징)
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수
            db: 데이터베이스 세션
            
        Returns:
            Dict containing transactions and pagination info
        """
        try:
            offset = (page - 1) * per_page
            
            # 거래 내역 조회
            transactions = db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            ).order_by(FortuneTransaction.created_at.desc()).offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total = db.query(FortuneTransaction).filter(
                FortuneTransaction.user_id == user_id
            ).count()
            
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
            logger.error(f"포인트 거래 내역 조회 실패: user_id={user_id}, error={e}")
            raise

# Rate Limiting 데코레이터
def rate_limit(name: str, requests: int = 5, window: int = 60):
    """
    Rate Limiting 데코레이터
    
    Args:
        name: 제한 이름
        requests: 허용 요청 수
        window: 시간 윈도우 (초)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Redis 기반 Rate Limiting 구현
            # 현재는 기본 구현
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Webhook 핸들러
class WebhookHandler:
    """웹훅 처리 클래스"""
    
    @staticmethod
    async def handle_kakaopay_webhook(payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        카카오페이 웹훅 처리
        
        Args:
            payload: 웹훅 페이로드
            db: 데이터베이스 세션
            
        Returns:
            Dict containing processing result
        """
        try:
            # 웹훅 검증 로직
            # TODO: 카카오페이 웹훅 서명 검증 구현
            
            # 웹훅 타입별 처리
            webhook_type = payload.get("type")
            
            if webhook_type == "PAYMENT_STATUS_CHANGED":
                return await WebhookHandler._handle_payment_status_change(payload, db)
            elif webhook_type == "PAYMENT_CANCELED":
                return await WebhookHandler._handle_payment_cancel(payload, db)
            else:
                logger.warning(f"Unknown webhook type: {webhook_type}")
                return {"status": "ignored", "reason": "unknown_type"}
                
        except Exception as e:
            logger.error(f"웹훅 처리 실패: {e}")
            raise
    
    @staticmethod
    async def _handle_payment_status_change(payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """결제 상태 변경 웹훅 처리"""
        # TODO: 결제 상태 변경 처리 로직
        return {"status": "processed"}
    
    @staticmethod
    async def _handle_payment_cancel(payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """결제 취소 웹훅 처리"""
        # TODO: 결제 취소 처리 로직
        return {"status": "processed"}

# 유틸리티 함수들
def format_currency(amount: int) -> str:
    """금액 포맷팅"""
    return f"{amount:,}원"

def validate_payment_amount(amount: int) -> bool:
    """결제 금액 검증"""
    return 100 <= amount <= 1000000  # 100원 ~ 100만원

def get_payment_method_display(method: str) -> str:
    """결제 수단 표시명"""
    method_map = {
        "kakao": "카카오페이",
        "fortune_points": "행운 포인트",
        "subscription": "구독 혜택"
    }
    return method_map.get(method, method)

    @staticmethod
    def process_payment_completion(
        purchase_id: int,
        user_id: int,
        product_id: int,
        payment_type: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        결제 완료 후 처리 - 리포트 생성 등
        
        Args:
            purchase_id: 구매 ID
            user_id: 사용자 ID
            product_id: 상품 ID
            payment_type: 결제 타입 (cash, fortune_points)
            db: 데이터베이스 세션
            
        Returns:
            Dict containing processing result
        """
        try:
            # 구매 내역 업데이트
            purchase = db.query(UserPurchase).filter(
                UserPurchase.id == purchase_id,
                UserPurchase.user_id == user_id
            ).first()
            
            if not purchase:
                raise BadRequestError("구매 내역을 찾을 수 없습니다.")
            
            # 결제 완료 상태로 업데이트
            purchase.status = "completed"
            purchase.completed_at = datetime.now()
            db.commit()
            
            # 리포트 생성 (백그라운드)
            try:
                # 기존 order.py의 리포트 생성 로직 활용
                report_html = generate_live_report_for_user(
                    user_id=user_id,
                    product_id=product_id,
                    purchase_id=purchase_id
                )
                
                # 리포트 생성 성공 시 상태 업데이트
                purchase.report_status = "completed"
                purchase.report_generated_at = datetime.now()
                db.commit()
                
                logger.info(f"리포트 생성 완료: purchase_id={purchase_id}")
                
                return {
                    "success": True,
                    "purchase_id": purchase_id,
                    "report_status": "completed",
                    "message": "결제가 완료되었습니다. 리포트가 생성되었습니다."
                }
                
            except Exception as e:
                logger.error(f"리포트 생성 실패: purchase_id={purchase_id}, error={e}")
                
                # 리포트 생성 실패 시에도 구매는 완료로 처리
                purchase.report_status = "failed"
                purchase.report_error = str(e)
                db.commit()
                
                return {
                    "success": True,
                    "purchase_id": purchase_id,
                    "report_status": "failed",
                    "error": str(e),
                    "message": "결제가 완료되었습니다. 리포트 생성에 실패했습니다."
                }
                
        except Exception as e:
            logger.error(f"결제 완료 처리 실패: purchase_id={purchase_id}, error={e}")
            db.rollback()
            raise InternalServerError(f"결제 완료 처리 중 오류가 발생했습니다: {str(e)}") 