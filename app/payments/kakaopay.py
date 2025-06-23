# app/payments/kakaopay.py
"""
카카오페이 결제 API 모듈
- 카카오페이 공식 API 스펙 100% 준수
- ready → approve → verification 3단계 결제 플로우 구현
"""

import os
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 로깅 설정
logger = logging.getLogger(__name__)

# 카카오페이 API 설정
KAKAOPAY_API_HOST = "https://open-api.kakaopay.com"
KAKAO_CID = os.getenv("KAKAO_CID", "CT00000000")  # 실제 가맹점 코드
SECRET_KEY = os.getenv("KAKAO_SECRET_KEY")  # 실제 시크릿 키
SITE_URL = os.getenv("SITE_URL", "https://sazu.mp4korea.com")

# 테스트용 설정 (개발 시에만 사용)
if os.getenv("ENVIRONMENT", "production") == "development":
    KAKAO_CID = "TC0ONETIME"  # 테스트용 CID
    SECRET_KEY = os.getenv("KAKAO_SECRET_KEY_DEV", "DEV_SECRET_KEY")


class KakaoPayError(Exception):
    """카카오페이 API 에러"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


async def kakao_ready(
    order_id: int,
    amount: int,
    user_email: str = "",
    item_name: str = "AI 심층 사주 리포트",
    partner_user_id: str = None
) -> Dict[str, Any]:
    """
    카카오페이 결제 준비 - TID 발급 및 결제 URL 반환
    
    Args:
        order_id: 주문 ID
        amount: 결제 금액
        user_email: 사용자 이메일 (선택)
        item_name: 상품명
        partner_user_id: 가맹점 회원 ID
    
    Returns:
        Dict containing tid, redirect_urls, etc.
    
    Raises:
        KakaoPayError: API 호출 실패 시
    """
    try:
        if not SECRET_KEY:
            raise KakaoPayError("카카오페이 시크릿 키가 설정되지 않았습니다.")
        
        # 파트너 사용자 ID 생성 (이메일 앞부분 사용 또는 order_id 기반)
        if not partner_user_id:
            if user_email:
                partner_user_id = user_email.split('@')[0]
            else:
                partner_user_id = f"user_{order_id}"
        
        # 요청 데이터
        payload = {
            "cid": KAKAO_CID,
            "partner_order_id": str(order_id),
            "partner_user_id": partner_user_id,
            "item_name": item_name,
            "quantity": 1,
            "total_amount": amount,
            "tax_free_amount": 0,
            "approval_url": f"{SITE_URL}/order/approve?order_id={order_id}",
            "cancel_url": f"{SITE_URL}/order/cancel?order_id={order_id}",
            "fail_url": f"{SITE_URL}/order/fail?order_id={order_id}"
        }
        
        # API 헤더
        headers = {
            "Authorization": f"SECRET_KEY {SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"카카오페이 결제 준비 요청: order_id={order_id}, amount={amount}")
        
        # HTTP 요청
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{KAKAOPAY_API_HOST}/online/v1/payment/ready",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                logger.error(f"카카오페이 ready API 실패: {response.status_code}, {error_data}")
                raise KakaoPayError(
                    message=f"결제 준비 요청이 실패했습니다. (코드: {response.status_code})",
                    code=error_data.get("error_code"),
                    details=error_data
                )
            
            result = response.json()
            logger.info(f"카카오페이 결제 준비 성공: tid={result.get('tid')}")
            return result
            
    except httpx.TimeoutException:
        logger.error("카카오페이 ready API 타임아웃")
        raise KakaoPayError("결제 요청 시간이 초과되었습니다. 다시 시도해주세요.")
    except httpx.RequestError as e:
        logger.error(f"카카오페이 ready API 네트워크 오류: {e}")
        raise KakaoPayError("네트워크 오류가 발생했습니다. 다시 시도해주세요.")
    except Exception as e:
        logger.error(f"카카오페이 ready API 예외: {e}")
        raise KakaoPayError("결제 준비 중 오류가 발생했습니다.")


async def kakao_approve(
    tid: str,
    pg_token: str,
    order_id: int,
    partner_user_id: str
) -> Dict[str, Any]:
    """
    카카오페이 결제 승인 - 실제 결제 완료 처리
    
    Args:
        tid: 결제 고유번호 (ready에서 받은 값)
        pg_token: 결제 승인 토큰
        order_id: 주문 ID
        partner_user_id: 가맹점 회원 ID
    
    Returns:
        Dict containing payment result
    
    Raises:
        KakaoPayError: API 호출 실패 시
    """
    try:
        if not SECRET_KEY:
            raise KakaoPayError("카카오페이 시크릿 키가 설정되지 않았습니다.")
        
        # 요청 데이터
        payload = {
            "cid": KAKAO_CID,
            "tid": tid,
            "partner_order_id": str(order_id),
            "partner_user_id": partner_user_id,
            "pg_token": pg_token
        }
        
        # API 헤더
        headers = {
            "Authorization": f"SECRET_KEY {SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"카카오페이 결제 승인 요청: tid={tid}, order_id={order_id}")
        
        # HTTP 요청
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{KAKAOPAY_API_HOST}/online/v1/payment/approve",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                logger.error(f"카카오페이 approve API 실패: {response.status_code}, {error_data}")
                raise KakaoPayError(
                    message=f"결제 승인이 실패했습니다. (코드: {response.status_code})",
                    code=error_data.get("error_code"),
                    details=error_data
                )
            
            result = response.json()
            logger.info(f"카카오페이 결제 승인 성공: aid={result.get('aid')}")
            return result
            
    except httpx.TimeoutException:
        logger.error("카카오페이 approve API 타임아웃")
        raise KakaoPayError("결제 승인 시간이 초과되었습니다.")
    except httpx.RequestError as e:
        logger.error(f"카카오페이 approve API 네트워크 오류: {e}")
        raise KakaoPayError("네트워크 오류가 발생했습니다.")
    except Exception as e:
        logger.error(f"카카오페이 approve API 예외: {e}")
        raise KakaoPayError("결제 승인 중 오류가 발생했습니다.")


async def kakao_order_inquiry(tid: str) -> Dict[str, Any]:
    """
    카카오페이 주문 조회 - 결제 상태 확인
    
    Args:
        tid: 결제 고유번호
    
    Returns:
        Dict containing order status
    
    Raises:
        KakaoPayError: API 호출 실패 시
    """
    try:
        if not SECRET_KEY:
            raise KakaoPayError("카카오페이 시크릿 키가 설정되지 않았습니다.")
        
        # 요청 데이터
        payload = {
            "cid": KAKAO_CID,
            "tid": tid
        }
        
        # API 헤더
        headers = {
            "Authorization": f"SECRET_KEY {SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"카카오페이 주문 조회 요청: tid={tid}")
        
        # HTTP 요청
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{KAKAOPAY_API_HOST}/online/v1/payment/order",
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                logger.error(f"카카오페이 order inquiry API 실패: {response.status_code}, {error_data}")
                raise KakaoPayError(
                    message=f"주문 조회가 실패했습니다. (코드: {response.status_code})",
                    code=error_data.get("error_code"),
                    details=error_data
                )
            
            result = response.json()
            logger.info(f"카카오페이 주문 조회 성공: status={result.get('status')}")
            return result
            
    except httpx.TimeoutException:
        logger.error("카카오페이 order inquiry API 타임아웃")
        raise KakaoPayError("주문 조회 시간이 초과되었습니다.")
    except httpx.RequestError as e:
        logger.error(f"카카오페이 order inquiry API 네트워크 오류: {e}")
        raise KakaoPayError("네트워크 오류가 발생했습니다.")
    except Exception as e:
        logger.error(f"카카오페이 order inquiry API 예외: {e}")
        raise KakaoPayError("주문 조회 중 오류가 발생했습니다.")


def verify_payment(order_amount: int, kakao_response: Dict[str, Any]) -> bool:
    """
    결제 검증 함수 - 서버사이드에서 결제 정보 검증
    
    Args:
        order_amount: 주문 시 요청한 금액
        kakao_response: 카카오페이 승인 응답
    
    Returns:
        bool: 검증 성공 여부
    
    Raises:
        KakaoPayError: 검증 실패 시
    """
    try:
        # 1. 결제 금액 검증
        paid_amount = kakao_response.get("amount", {}).get("total", 0)
        if paid_amount != order_amount:
            raise KakaoPayError(
                f"결제 금액이 일치하지 않습니다. (요청: {order_amount}원, 결제: {paid_amount}원)"
            )
        
        # 2. 결제 상태 검증
        payment_method = kakao_response.get("payment_method_type")
        if payment_method not in ["CARD", "MONEY"]:
            raise KakaoPayError("지원하지 않는 결제 수단입니다.")
        
        # 3. 결제 시각 검증 (최근 30분 이내)
        approved_at_str = kakao_response.get("approved_at")
        if approved_at_str:
            approved_at = datetime.fromisoformat(approved_at_str.replace('Z', '+00:00'))
            time_diff = (datetime.now().replace(tzinfo=approved_at.tzinfo) - approved_at).total_seconds()
            if time_diff > 1800:  # 30분 = 1800초
                raise KakaoPayError("결제 시간이 너무 오래되었습니다.")
        
        logger.info(f"결제 검증 성공: amount={paid_amount}, method={payment_method}")
        return True
        
    except Exception as e:
        logger.error(f"결제 검증 실패: {e}")
        if isinstance(e, KakaoPayError):
            raise
        raise KakaoPayError("결제 검증 중 오류가 발생했습니다.")


# 유틸리티 함수
def get_payment_method_name(method_type: str) -> str:
    """결제 수단 코드를 한국어 이름으로 변환"""
    methods = {
        "CARD": "카드",
        "MONEY": "카카오머니"
    }
    return methods.get(method_type, method_type)


def is_mobile_user_agent(user_agent: str) -> bool:
    """User-Agent로 모바일 여부 판단"""
    mobile_indicators = [
        'Mobile', 'Android', 'iPhone', 'iPad', 
        'BlackBerry', 'Windows Phone', 'webOS'
    ]
    return any(indicator in user_agent for indicator in mobile_indicators)