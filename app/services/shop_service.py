# app/services/shop_service.py
"""
운세 상점 서비스 - 상품 구매 로직
- 상품 목록/상세 조회
- 구매 처리 (포인트/현금)
- 상품 검색/필터링
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc

from app.models import (
    Product, SajuProduct, User, UserPurchase, Order,
    UserFortunePoint, FortunePackage, UserReview
)
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError, InternalServerError
from app.services.payment_service import PaymentService
from app.services.fortune_service import FortuneService
from app.services.subscription_service import SubscriptionService
from app.services.referral_service import ReferralService
from app.utils import generate_live_report_for_user
from app.services.cache_service import CacheService, cached, invalidate_cache, CacheKeys

logger = logging.getLogger(__name__)

class ShopService:
    """운세 상점 서비스"""
    
    @staticmethod
    def get_products(
        db: Session,
        category: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        per_page: int = 12
    ) -> Dict[str, Any]:
        """
        상품 목록 조회 (필터링, 검색, 페이징)
        
        Args:
            category: 카테고리 필터
            search: 검색어
            sort_by: 정렬 기준
            sort_order: 정렬 순서 (asc/desc)
            page: 페이지 번호
            per_page: 페이지당 항목 수
            db: 데이터베이스 세션
            
        Returns:
            Dict containing products and pagination info
        """
        try:
            offset = (page - 1) * per_page
            
            # 기본 쿼리
            query = db.query(Product).filter(Product.is_active == True)
            
            # 카테고리 필터
            if category:
                query = query.filter(Product.category == category)
            
            # 검색 필터
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Product.name.like(search_term),
                        Product.description.like(search_term),
                        Product.tags.contains([search])
                    )
                )
            
            # 정렬
            if sort_by == "price":
                order_func = asc(Product.price) if sort_order == "asc" else desc(Product.price)
            elif sort_by == "name":
                order_func = asc(Product.name) if sort_order == "asc" else desc(Product.name)
            elif sort_by == "popularity":
                # TODO: 인기도 기준 정렬 구현
                order_func = desc(Product.id)
            else:
                order_func = desc(Product.created_at) if sort_order == "desc" else asc(Product.created_at)
            
            query = query.order_by(order_func)
            
            # 상품 조회
            products = query.offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total_query = db.query(Product).filter(Product.is_active == True)
            if category:
                total_query = total_query.filter(Product.category == category)
            if search:
                search_term = f"%{search}%"
                total_query = total_query.filter(
                    or_(
                        Product.name.like(search_term),
                        Product.description.like(search_term),
                        Product.tags.contains([search])
                    )
                )
            
            total = total_query.count()
            
            return {
                "products": products,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"상품 목록 조회 실패: error={e}")
            raise InternalServerError("상품 목록 조회 중 오류가 발생했습니다.")

    @staticmethod
    def get_product_by_slug(slug: str, db: Session) -> Optional[Product]:
        """
        슬러그로 상품 조회
        
        Args:
            slug: 상품 슬러그
            db: 데이터베이스 세션
            
        Returns:
            Product object or None
        """
        try:
            product = db.query(Product).filter(
                and_(
                    Product.slug == slug,
                    Product.is_active == True
                )
            ).first()
            
            return product
            
        except Exception as e:
            logger.error(f"상품 조회 실패: slug={slug}, error={e}")
            return None

    @staticmethod
    def get_product_detail(db: Session, product_id: int, user_id: int = None) -> Dict[str, Any]:
        """
        상품 상세 정보 조회
        
        Args:
            product_id: 상품 ID
            user_id: 사용자 ID (선택)
            db: 데이터베이스 세션
            
        Returns:
            Dict containing product detail information
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                raise NotFoundError("상품을 찾을 수 없습니다.")
            
            # 사주 상품 정보 조회
            saju_product = db.query(SajuProduct).filter(
                SajuProduct.base_product_id == product_id
            ).first()
            
            # 사용자 포인트 잔액 조회
            user_points = 0
            if user_id:
                user_points = FortuneService.get_user_fortune_info(user_id, db)["points"]
            
            # 리뷰 통계 조회
            reviews = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product_id,
                    UserReview.is_visible == True
                )
            ).all()
            
            avg_rating = 0
            if reviews:
                total_rating = sum(review.rating for review in reviews)
                avg_rating = round(total_rating / len(reviews), 1)
            
            # 구매 가능 여부 확인
            can_purchase_with_points = False
            if user_id and product.fortune_cost > 0:
                can_purchase_with_points = user_points >= product.fortune_cost
            
            # 할인 정보 계산
            discount_info = ShopService.calculate_discount(product, user_id, db)
            
            return {
                "product": product,
                "saju_product": saju_product,
                "user_points": user_points,
                "can_purchase_with_points": can_purchase_with_points,
                "discount_info": discount_info,
                "reviews": {
                    "count": len(reviews),
                    "average_rating": avg_rating,
                    "recent_reviews": reviews[:3]  # 최근 3개 리뷰
                }
            }
            
        except Exception as e:
            logger.error(f"상품 상세 조회 실패: product_id={product_id}, error={e}")
            raise

    @staticmethod
    def process_point_purchase(
        user_id: int,
        product_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        포인트 구매 처리
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                return False, "상품을 찾을 수 없습니다.", {}
            
            # 포인트 비용 확인
            if product.fortune_cost <= 0:
                return False, "이 상품은 포인트로 구매할 수 없습니다.", {}
            
            # 사용자 포인트 잔액 확인
            user_points = FortuneService.get_user_fortune_info(user_id, db)["points"]
            if user_points < product.fortune_cost:
                return False, f"포인트가 부족합니다. (보유: {user_points}P, 필요: {product.fortune_cost}P)", {}
            
            # 중복 구매 체크
            existing_purchase = db.query(UserPurchase).filter(
                and_(
                    UserPurchase.user_id == user_id,
                    UserPurchase.product_id == product_id,
                    UserPurchase.purchase_type == "fortune_points"
                )
            ).first()
            
            if existing_purchase:
                return False, "이미 구매한 상품입니다.", {}
            
            # 포인트 사용 처리
            success, message = FortuneService.use_points_for_purchase(
                user_id=user_id,
                product_id=product_id,
                points_needed=product.fortune_cost,
                db=db
            )
            
            if success:
                # 구매 내역 조회
                purchase = db.query(UserPurchase).filter(
                    and_(
                        UserPurchase.user_id == user_id,
                        UserPurchase.product_id == product_id,
                        UserPurchase.purchase_type == "fortune_points"
                    )
                ).first()
                
                # 결제 완료 후 리포트 생성 처리
                if purchase:
                    try:
                        PaymentService.process_payment_completion(
                            purchase_id=purchase.id,
                            user_id=user_id,
                            product_id=product_id,
                            payment_type="fortune_points",
                            db=db
                        )
                        
                        # 추천인 구매 보상 처리
                        user = db.query(User).filter(User.id == user_id).first()
                        if user and user.referred_by:
                            ReferralService.process_referral_purchase(
                                referred_user_id=user.id,
                                purchase_amount=product.fortune_cost * 100,  # 1P = 100원 기준
                                db=db
                            )
                    except Exception as e:
                        logger.error(f"결제 완료 후 처리 실패: purchase_id={purchase.id}, error={e}")
                        # 리포트 생성 실패해도 구매는 성공으로 처리
                
                # 구매 완료 정보
                purchase_info = {
                    "purchase_id": purchase.id if purchase else None,
                    "product_name": product.name,
                    "points_used": product.fortune_cost,
                    "remaining_points": user_points - product.fortune_cost,
                    "purchase_date": datetime.now()
                }
                
                return True, "포인트 구매가 완료되었습니다.", {
                    **purchase_info,
                    "redirect_url": f"/shop/purchase/{purchase.id}/success"
                }
            else:
                return False, message, {}
                
        except Exception as e:
            logger.error(f"포인트 구매 처리 실패: user_id={user_id}, product_id={product_id}, error={e}")
            return False, "구매 처리 중 오류가 발생했습니다.", {}

    @staticmethod
    def process_cash_purchase(
        user_id: int,
        product_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        현금 구매 처리
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                return False, "상품을 찾을 수 없습니다.", {}
            
            # 현금 비용 확인
            if product.cash_cost <= 0:
                return False, "이 상품은 현금으로 구매할 수 없습니다.", {}
            
            # 중복 구매 체크
            existing_purchase = db.query(UserPurchase).filter(
                and_(
                    UserPurchase.user_id == user_id,
                    UserPurchase.product_id == product_id,
                    UserPurchase.purchase_type == "cash"
                )
            ).first()
            
            if existing_purchase:
                return False, "이미 구매한 상품입니다.", {}
            
            # 구매 완료 정보
            purchase_info = {
                "purchase_id": existing_purchase.id if existing_purchase else None,
                "product_name": product.name,
                "cash_used": product.cash_cost,
                "remaining_cash": 0,  # 현금 구매는 남은 현금이 없음
                "purchase_date": datetime.now()
            }
            
            return True, "현금 구매가 완료되었습니다.", {
                **purchase_info,
                "redirect_url": f"/shop/purchase/{existing_purchase.id}/success" if existing_purchase else None
            }
            
        except Exception as e:
            logger.error(f"현금 구매 처리 실패: user_id={user_id}, product_id={product_id}, error={e}")
            return False, "구매 처리 중 오류가 발생했습니다.", {}

    @staticmethod
    def calculate_discount(product: Product, user_id: int = None, db: Session = None) -> Dict[str, Any]:
        """
        상품 할인 정보 계산
        
        Args:
            product: 상품 객체
            user_id: 사용자 ID (선택)
            db: 데이터베이스 세션
            
        Returns:
            Dict containing discount information
        """
        try:
            discount_info = {
                "has_discount": False,
                "discount_rate": 0,
                "original_price": 0,
                "discounted_price": 0,
                "discount_amount": 0,
                "discount_type": None,
                "discount_reason": None
            }
            
            # 기본 가격 설정
            if product.price > 0:
                discount_info["original_price"] = product.price
                discount_info["discounted_price"] = product.price
            
            # 1. 신규 사용자 할인 (첫 구매 시 10% 할인)
            if user_id:
                # 사용자의 첫 구매 여부 확인
                first_purchase = db.query(UserPurchase).filter(
                    UserPurchase.user_id == user_id
                ).first()
                
                if not first_purchase:
                    discount_rate = 10
                    discount_amount = int(product.price * discount_rate / 100)
                    discounted_price = product.price - discount_amount
                    
                    if discounted_price < discount_info["discounted_price"]:
                        discount_info.update({
                            "has_discount": True,
                            "discount_rate": discount_rate,
                            "discounted_price": discounted_price,
                            "discount_amount": discount_amount,
                            "discount_type": "new_user",
                            "discount_reason": "신규 사용자 할인"
                        })
            
            # 2. 포인트 구매 할인 (현금 대비 20% 할인)
            if product.fortune_cost > 0 and product.price > 0:
                # 포인트 구매 시 할인율 계산 (1P = 100원 기준)
                point_discount_rate = 20
                point_discount_amount = int(product.price * point_discount_rate / 100)
                point_discounted_price = product.price - point_discount_amount
                
                if point_discounted_price < discount_info["discounted_price"]:
                    discount_info.update({
                        "has_discount": True,
                        "discount_rate": point_discount_rate,
                        "discounted_price": point_discounted_price,
                        "discount_amount": point_discount_amount,
                        "discount_type": "point_purchase",
                        "discount_reason": "포인트 구매 할인"
                    })
            
            # 3. 구독 할인
            if user_id and db:
                discounted_price, discount_rate = SubscriptionService.apply_subscription_discount(
                    original_price=discount_info["discounted_price"],
                    user_id=user_id,
                    db=db
                )
                
                if discounted_price < discount_info["discounted_price"]:
                    discount_amount = discount_info["discounted_price"] - discounted_price
                    discount_info.update({
                        "has_discount": True,
                        "discount_rate": discount_rate,
                        "discounted_price": discounted_price,
                        "discount_amount": discount_amount,
                        "discount_type": "subscription",
                        "discount_reason": f"구독 할인 ({discount_rate}%)"
                    })
            
            # 3. 시즌 할인 (임시 - 나중에 할인 이벤트 테이블로 확장)
            # TODO: 할인 이벤트 테이블 연동
            
            return discount_info
            
        except Exception as e:
            logger.error(f"할인 계산 실패: product_id={product.id}, user_id={user_id}, error={e}")
            return {
                "has_discount": False,
                "discount_rate": 0,
                "original_price": product.price,
                "discounted_price": product.price,
                "discount_amount": 0,
                "discount_type": None,
                "discount_reason": None
            } 