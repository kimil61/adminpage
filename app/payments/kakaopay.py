import os
import httpx

KAKAOPAY_API_HOST = "https://kapi.kakao.com/v1/payment"
KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY", "")
KAKAO_CID = os.getenv("KAKAO_CID", "TC0ONETIME")

HEADERS = {
    "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
}


def kakao_ready(order_id: int, amount: int, user_email: str = "", user_phone: str = "") -> dict:
    """Call KakaoPay ready API.

    Returns response JSON with tid and redirect URLs.
    """
    url = f"{KAKAOPAY_API_HOST}/ready"
    data = {
        "cid": KAKAO_CID,
        "partner_order_id": str(order_id),
        "partner_user_id": user_email or user_phone or "anonymous",
        "item_name": "Saju Report",
        "quantity": 1,
        "total_amount": int(amount),
        "tax_free_amount": 0,
        "approval_url": f"http://localhost:8000/order/approve?order_id={order_id}",
        "cancel_url": f"http://localhost:8000/order/cancel?order_id={order_id}",
        "fail_url": f"http://localhost:8000/order/fail?order_id={order_id}",
    }
    response = httpx.post(url, headers=HEADERS, data=data, timeout=10.0)
    response.raise_for_status()
    return response.json()


def kakao_approve(tid: str, pg_token: str) -> dict:
    """Call KakaoPay approve API and return the approval result."""
    url = f"{KAKAOPAY_API_HOST}/approve"
    data = {
        "cid": KAKAO_CID,
        "tid": tid,
        "partner_order_id": tid,
        "partner_user_id": "anonymous",
        "pg_token": pg_token,
    }
    response = httpx.post(url, headers=HEADERS, data=data, timeout=10.0)
    response.raise_for_status()
    return response.json()
