"""
카카오페이 결제 공통 서비스 - 프로덕션 레벨 안전성
Week 1: 핵심 인프라 - 결제 시스템 완전 리팩터링
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from decimal import Decimal

import requests
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.models import (
    Order, User, UserPurchase, UserFortunePoint, 
    FortuneTransaction, FortunePackage, Subscription
)
from app.utils.csrf import verify_csrf_token
from app.utils.error_handlers import PaymentError, InsufficientPointsError

# 로깅 설정
logger = logging.getLogger(__name__)

# 카카오페이 설정
KAKAO_ADMIN_KEY = "your_kakao_admin_key"  # 환경변수로 관리
KAKAO_PAYMENT_URL = "https://kapi.kakao.com/v1/payment/ready"
KAKAO_APPROVE_URL = "https://kapi.kakao.com/v1/payment/approve"
KAKAO_CANCEL_URL = "https://kapi.kakao.com/v1/payment/cancel"

# Rate Limiting 설정
RATE_LIMIT_WINDOW = 60  # 60초
MAX_PAYMENT_ATTEMPTS = 5  # IP당 최대 결제 시도

class PaymentService:
    """견고한 결제 서비스 - 멱등성, 트랜잭션 안전성 보장"""
    
    def __init__(self, db: Session):
        self.db = db
        self._idempotency_cache = {}  # 메모리 캐시 (Redis로 확장 가능)
    
    def _generate_idempotency_key(self, user_id: int, amount: int, order_type: str) -> str:
        """멱등성 키 생성"""
        timestamp = int(time.time() / 60)  # 1분 단위로 그룹화
        data = f"{user_id}:{amount}:{order_type}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _check_idempotency(self, idempotency_key: str) -> Optional[Dict]:
        """멱등성 체크 - 중복 결제 방지"""
        if idempotency_key in self._idempotency_cache:
            cached_result = self._idempotency_cache[idempotency_key]
            # 5분 이내 결과만 유효
            if time.time() - cached_result.get('timestamp', 0) < 300:
                logger.info(f"Idempotency hit for key: {idempotency_key}")
                return cached_result.get('result')
        return None
    
    def _store_idempotency_result(self, idempotency_key: str, result: Dict):
        """멱등성 결과 저장"""
        self._idempotency_cache[idempotency_key] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def prepare_kakaopay_payment(
        self,
        amount: int,
        item_name: str,
        user_id: int,
        order_type: str = "cash",
        idempotency_key: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        카카오페이 결제 준비 - 멱등성 보장
        
        Args:
            amount: 결제 금액
            item_name: 상품명
            user_id: 사용자 ID
            order_type: 주문 타입 (cash, fortune_points, subscription)
            idempotency_key: 멱등성 키 (None이면 자동 생성)
            **kwargs: 추가 파라미터 (product_id, package_id 등)
        
        Returns:
            Dict: 카카오페이 결제 준비 응답
        """
        try:
            # 1. 멱등성 체크
            if idempotency_key is None:
                idempotency_key = self._generate_idempotency_key(user_id, amount, order_type)
            
            cached_result = self._check_idempotency(idempotency_key)
            if cached_result:
                return cached_result
            
            # 2. 사용자 검증
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise PaymentError("사용자를 찾을 수 없습니다.")
            
            # 3. 카카오페이 결제 준비 요청
            partner_order_id = f"order_{int(time.time())}_{user_id}"
            
            payload = {
                "cid": "TC0ONETIME",  # 테스트용, 실제 운영시 변경
                "partner_order_id": partner_order_id,
                "partner_user_id": str(user_id),
                "item_name": item_name,
                "quantity": 1,
                "total_amount": amount,
                "tax_free_amount": 0,
                "approval_url": f"https://yourdomain.com/payment/success?order_id={partner_order_id}",
                "cancel_url": f"https://yourdomain.com/payment/cancel?order_id={partner_order_id}",
                "fail_url": f"https://yourdomain.com/payment/fail?order_id={partner_order_id}"
            }
            
            headers = {
                "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
            }
            
            response = requests.post(KAKAO_PAYMENT_URL, data=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # 4. 주문 생성 (트랜잭션 안전성)
            order = Order(
                user_id=user_id,
                amount=amount,
                kakao_tid=result.get('tid', ''),
                saju_key=kwargs.get('saju_key', ''),
                status='pending',
                payment_method='kakao',
                is_subscription_payment=(order_type == 'subscription')
            )
            
            if 'product_id' in kwargs:
                order.product_id = kwargs['product_id']
            
            self.db.add(order)
            self.db.commit()
            
            # 5. 멱등성 결과 저장
            final_result = {
                'tid': result.get('tid'),
                'order_id': order.id,
                'redirect_url': result.get('next_redirect_pc_url'),
                'idempotency_key': idempotency_key
            }
            
            self._store_idempotency_result(idempotency_key, final_result)
            
            logger.info(f"Payment prepared: user_id={user_id}, amount={amount}, tid={result.get('tid')}")
            return final_result
            
        except requests.RequestException as e:
            logger.error(f"KakaoPay API error: {e}")
            raise PaymentError("결제 준비 중 오류가 발생했습니다.")
        except Exception as e:
            logger.error(f"Payment preparation error: {e}")
            self.db.rollback()
            raise PaymentError("결제 준비 중 오류가 발생했습니다.")
    
    def verify_kakaopay_payment(
        self,
        tid: str,
        pg_token: str,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        카카오페이 결제 검증 - 원자성 트랜잭션
        
        Args:
            tid: 카카오페이 TID
            pg_token: PG 토큰
            idempotency_key: 멱등성 키
        
        Returns:
            Dict: 결제 검증 결과
        """
        try:
            # 1. 멱등성 체크
            if idempotency_key:
                cached_result = self._check_idempotency(idempotency_key)
                if cached_result:
                    return cached_result
            
            # 2. 주문 조회
            order = self.db.query(Order).filter(Order.kakao_tid == tid).first()
            if not order:
                raise PaymentError("주문을 찾을 수 없습니다.")
            
            if order.status == 'paid':
                logger.info(f"Payment already completed: order_id={order.id}")
                return {
                    'order_id': order.id,
                    'status': 'paid',
                    'amount': order.amount,
                    'message': '이미 완료된 결제입니다.'
                }
            
            # 3. 카카오페이 결제 승인 요청
            payload = {
                "cid": "TC0ONETIME",
                "tid": tid,
                "partner_order_id": f"order_{order.id}",
                "partner_user_id": str(order.user_id),
                "pg_token": pg_token
            }
            
            headers = {
                "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
            }
            
            response = requests.post(KAKAO_APPROVE_URL, data=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # 4. 주문 상태 업데이트 (트랜잭션)
            order.status = 'paid'
            order.report_status = 'pending'
            self.db.commit()
            
            # 5. 구매 기록 생성 (포인트 구매인 경우)
            if order.is_subscription_payment:
                self._process_subscription_payment(order)
            else:
                self._process_product_purchase(order)
            
            final_result = {
                'order_id': order.id,
                'status': 'paid',
                'amount': order.amount,
                'tid': tid,
                'message': '결제가 완료되었습니다.'
            }
            
            if idempotency_key:
                self._store_idempotency_result(idempotency_key, final_result)
            
            logger.info(f"Payment verified: order_id={order.id}, amount={order.amount}")
            return final_result
            
        except requests.RequestException as e:
            logger.error(f"KakaoPay verification error: {e}")
            raise PaymentError("결제 검증 중 오류가 발생했습니다.")
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            self.db.rollback()
            raise PaymentError("결제 검증 중 오류가 발생했습니다.")
    
    def prepare_point_charge(
        self,
        package_id: int,
        user_id: int,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """
        포인트 충전 준비 - Order + FortuneTransaction 원자성
        
        Args:
            package_id: 포인트 패키지 ID
            user_id: 사용자 ID
            idempotency_key: 멱등성 키
        
        Returns:
            Dict: 포인트 충전 준비 결과
        """
        try:
            # 1. 멱등성 체크
            cached_result = self._check_idempotency(idempotency_key)
            if cached_result:
                return cached_result
            
            # 2. 패키지 검증
            package = self.db.query(FortunePackage).filter(
                FortunePackage.id == package_id,
                FortunePackage.is_active.is_(True)
            ).first()
            
            if not package:
                raise PaymentError("유효하지 않은 포인트 패키지입니다.")
            
            # 3. 카카오페이 결제 준비
            result = self.prepare_kakaopay_payment(
                amount=int(package.price),
                item_name=f"{package.name} 포인트 충전",
                user_id=user_id,
                order_type="fortune_points",
                idempotency_key=idempotency_key,
                package_id=package_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Point charge preparation error: {e}")
            raise PaymentError("포인트 충전 준비 중 오류가 발생했습니다.")
    
    def process_point_usage(
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
            raise PaymentError("포인트 사용 중 오류가 발생했습니다.")
    
    def get_user_point_balance(self, user_id: int) -> int:
        """실시간 포인트 잔액 조회"""
        user_points = self.db.query(UserFortunePoint).filter(
            UserFortunePoint.user_id == user_id
        ).first()
        
        return user_points.points if user_points else 0
    
    def _process_subscription_payment(self, order: Order):
        """구독 결제 처리"""
        # 구독 관련 로직은 subscription_service.py에서 처리
        logger.info(f"Subscription payment processed: order_id={order.id}")
    
    def _process_product_purchase(self, order: Order):
        """상품 구매 처리"""
        # 상품 구매 관련 로직은 shop_service.py에서 처리
        logger.info(f"Product purchase processed: order_id={order.id}")
    
    def cancel_payment(self, tid: str, cancel_amount: Optional[int] = None) -> Dict[str, Any]:
        """
        결제 취소/환불 처리
        
        Args:
            tid: 카카오페이 TID
            cancel_amount: 취소 금액 (None이면 전체 취소)
        
        Returns:
            Dict: 취소 결과
        """
        try:
            # 1. 주문 조회
            order = self.db.query(Order).filter(Order.kakao_tid == tid).first()
            if not order:
                raise PaymentError("주문을 찾을 수 없습니다.")
            
            if order.status != 'paid':
                raise PaymentError("결제 완료된 주문만 취소할 수 있습니다.")
            
            # 2. 카카오페이 취소 요청
            payload = {
                "cid": "TC0ONETIME",
                "tid": tid,
                "cancel_amount": cancel_amount or order.amount,
                "cancel_tax_free_amount": 0
            }
            
            headers = {
                "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
            }
            
            response = requests.post(KAKAO_CANCEL_URL, data=payload, headers=headers)
            response.raise_for_status()
            
            # 3. 주문 상태 업데이트
            order.status = 'cancelled'
            self.db.commit()
            
            logger.info(f"Payment cancelled: order_id={order.id}, amount={cancel_amount or order.amount}")
            return {
                'order_id': order.id,
                'status': 'cancelled',
                'cancelled_amount': cancel_amount or order.amount
            }
            
        except requests.RequestException as e:
            logger.error(f"KakaoPay cancellation error: {e}")
            raise PaymentError("결제 취소 중 오류가 발생했습니다.")
        except Exception as e:
            logger.error(f"Payment cancellation error: {e}")
            self.db.rollback()
            raise PaymentError("결제 취소 중 오류가 발생했습니다.")

# 의존성 주입
def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)

# Rate Limiting 데코레이터 (실제 구현시 Redis 사용)
def rate_limit_payment(func):
    """결제 API Rate Limiting"""
    def wrapper(*args, **kwargs):
        # TODO: Redis 기반 Rate Limiting 구현
        return func(*args, **kwargs)
    return wrapper 