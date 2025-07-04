# app/services/shop_service.py
"""
운세 상점 서비스 - 상품 구매 및 결제 통합
Week 1: 핵심 인프라 - 상점 시스템 완전 구현
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from fastapi import Depends
from app.database import get_db
from app.models import (
    Product, SajuProduct, User, UserPurchase, 
    Order, UserFortunePoint, FortuneTransaction
)
from app.utils.error_handlers import ValidationError, InsufficientPointsError
from app.services.fortune_service import FortuneService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

class ShopService:
    """운세 상점 서비스 - 포인트/현금 결제 통합"""
    
    def __init__(self, db: Session):
        self.db = db
        self.fortune_service = FortuneService(db)
        self.payment_service = PaymentService(db)
    
    def get_products(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 12,
        sort_by: str = "created_at"
    ) -> Dict[str, Any]:
        """
        상품 목록 조회 (필터링, 검색, 페이징)
        
        Args:
            category: 카테고리 필터
            search: 검색어
            page: 페이지 번호
            per_page: 페이지당 항목 수
            sort_by: 정렬 기준
        
        Returns:
            Dict: 상품 목록 및 페이징 정보
        """
        try:
            offset = (page - 1) * per_page
            
            # 쿼리 구성
            query = self.db.query(Product).filter(Product.is_active.is_(True))
            
            # 카테고리 필터
            if category:
                query = query.filter(Product.category == category)
            
            # 검색 필터
            if search:
                search_filter = or_(
                    Product.name.contains(search),
                    Product.description.contains(search)
                )
                query = query.filter(search_filter)
            
            # 전체 개수 조회
            total = query.count()
            
            # 정렬
            if sort_by == "price_low":
                query = query.order_by(Product.price.asc())
            elif sort_by == "price_high":
                query = query.order_by(Product.price.desc())
            elif sort_by == "name":
                query = query.order_by(Product.name.asc())
            else:
                query = query.order_by(desc(Product.created_at))
            
            # 페이징
            products = query.offset(offset).limit(per_page).all()
            
            return {
                'products': [
                    {
                        'id': p.id,
                        'name': p.name,
                        'description': p.description,
                        'price': p.price,
                        'fortune_cost': p.fortune_cost,
                        'slug': p.slug,
                        'thumbnail': p.thumbnail,
                        'category': p.category,
                        'is_featured': p.is_featured,
                        'created_at': p.created_at
                    }
                    for p in products
                ],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"Product query error: error={e}")
            raise ValidationError("상품 목록 조회 중 오류가 발생했습니다.")
    
    def get_product_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        슬러그로 상품 상세 조회
        
        Args:
            slug: 상품 슬러그
        
        Returns:
            Dict: 상품 상세 정보
        """
        try:
            product = self.db.query(Product).filter(
                and_(
                    Product.slug == slug,
                    Product.is_active.is_(True)
                )
            ).first()
            
            if not product:
                return None
            
            # SajuProduct 정보 조회
            saju_product = self.db.query(SajuProduct).filter(
                SajuProduct.base_product_id == product.id
            ).first()
            
            result = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'fortune_cost': product.fortune_cost,
                'slug': product.slug,
                'thumbnail': product.thumbnail,
                'category': product.category,
                'features': product.features,
                'tags': product.tags,
                'difficulty_level': product.difficulty_level,
                'estimated_time': product.estimated_time,
                'is_featured': product.is_featured,
                'created_at': product.created_at
            }
            
            # SajuProduct 정보 추가
            if saju_product:
                result.update({
                    'analysis_type': saju_product.analysis_type,
                    'ai_model': saju_product.ai_model,
                    'includes_monthly_fortune': saju_product.includes_monthly_fortune,
                    'includes_compatibility': saju_product.includes_compatibility,
                    'includes_lucky_items': saju_product.includes_lucky_items,
                    'max_pages': saju_product.max_pages,
                    'template_style': saju_product.template_style
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Product detail query error: slug={slug}, error={e}")
            raise ValidationError("상품 상세 조회 중 오류가 발생했습니다.")
    
    def calculate_discount(self, user_id: int, product_id: int) -> Dict[str, Any]:
        """
        상품 할인 계산 (신규 사용자, 구독자 등)
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
        
        Returns:
            Dict: 할인 정보
        """
        try:
            # 상품 정보 조회
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return {'discount_rate': 0, 'discount_amount': 0, 'final_price': 0}
            
            original_price = product.price
            
            # 포인트 구매인 경우 할인 없음
            if product.fortune_cost > 0:
                return {
                    'discount_rate': 0,
                    'discount_amount': 0,
                    'final_price': original_price,
                    'fortune_cost': product.fortune_cost
                }
            
            # 할인 계산 (fortune_service 활용)
            discount_info = self.fortune_service.calculate_discount(user_id, original_price)
            
            return {
                **discount_info,
                'fortune_cost': product.fortune_cost
            }
            
        except Exception as e:
            logger.error(f"Discount calculation error: user_id={user_id}, product_id={product_id}, error={e}")
            return {'discount_rate': 0, 'discount_amount': 0, 'final_price': 0}
    
    def purchase_with_points(
        self,
        user_id: int,
        product_id: int,
        saju_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        포인트로 상품 구매
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            saju_key: 사주 키 (선택사항)
        
        Returns:
            Dict: 구매 결과
        """
        try:
            # 1. 상품 정보 조회
            product = self.db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.is_active.is_(True)
                )
            ).first()
            
            if not product:
                raise ValidationError("유효하지 않은 상품입니다.")
            
            if product.fortune_cost <= 0:
                raise ValidationError("이 상품은 포인트로 구매할 수 없습니다.")
            
            # 2. 포인트 사용
            success = self.fortune_service.use_points_safely(
                user_id=user_id,
                amount=product.fortune_cost,
                source='product_purchase',
                reference_id=f'product_{product_id}'
            )
            
            if not success:
                raise ValidationError("포인트 사용 처리에 실패했습니다.")
            
            # 3. 구매 기록 생성
            purchase = UserPurchase(
                user_id=user_id,
                product_id=product_id,
                purchase_type='fortune_points',
                original_price=0,  # 포인트 구매는 0원
                paid_amount=0,
                fortune_points_used=product.fortune_cost,
                saju_key=saju_key,
                created_at=datetime.now()
            )
            
            self.db.add(purchase)
            self.db.commit()
            
            logger.info(f"Point purchase completed: user_id={user_id}, product_id={product_id}, points={product.fortune_cost}")
            
            return {
                'success': True,
                'purchase_id': purchase.id,
                'product_name': product.name,
                'points_used': product.fortune_cost,
                'message': '포인트 구매가 완료되었습니다.'
            }
            
        except InsufficientPointsError as e:
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Point purchase error: {e}")
            self.db.rollback()
            raise ValidationError("포인트 구매 중 오류가 발생했습니다.")
    
    def prepare_cash_payment(
        self,
        user_id: int,
        product_id: int,
        saju_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        현금 결제 준비
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            saju_key: 사주 키 (선택사항)
        
        Returns:
            Dict: 결제 준비 결과
        """
        try:
            # 1. 상품 정보 조회
            product = self.db.query(Product).filter(
                and_(
                    Product.id == product_id,
                    Product.is_active.is_(True)
                )
            ).first()
            
            if not product:
                raise ValidationError("유효하지 않은 상품입니다.")
            
            # 2. 할인 계산
            discount_info = self.calculate_discount(user_id, product_id)
            final_price = discount_info['final_price']
            
            # 3. 카카오페이 결제 준비
            result = self.payment_service.prepare_kakaopay_payment(
                amount=final_price,
                item_name=product.name,
                user_id=user_id,
                order_type='cash',
                product_id=product_id,
                saju_key=saju_key
            )
            
            return {
                'success': True,
                'tid': result['tid'],
                'redirect_url': result['redirect_url'],
                'order_id': result['order_id'],
                'amount': final_price,
                'discount_info': discount_info
            }
            
        except Exception as e:
            logger.error(f"Cash payment preparation error: {e}")
            raise ValidationError("결제 준비 중 오류가 발생했습니다.")
    
    def process_purchase_completion(
        self,
        order_id: int,
        user_id: int,
        product_id: int
    ) -> Dict[str, Any]:
        """
        구매 완료 후 처리 (리포트 생성 등)
        
        Args:
            order_id: 주문 ID
            user_id: 사용자 ID
            product_id: 상품 ID
        
        Returns:
            Dict: 처리 결과
        """
        try:
            # 1. 주문 정보 조회
            order = self.db.query(Order).filter(
                and_(
                    Order.id == order_id,
                    Order.user_id == user_id,
                    Order.status == 'paid'
                )
            ).first()
            
            if not order:
                raise ValidationError("유효하지 않은 주문입니다.")
            
            # 2. 구매 기록 생성
            purchase = UserPurchase(
                user_id=user_id,
                product_id=product_id,
                order_id=order_id,
                purchase_type='cash',
                original_price=order.amount,
                paid_amount=order.amount,
                fortune_points_used=0,
                saju_key=order.saju_key,
                created_at=datetime.now()
            )
            
            self.db.add(purchase)
            self.db.commit()
            
            # 3. 추천인 보상 처리 (추후 referral_service.py와 연동)
            # TODO: 추천인 보상 로직
            
            logger.info(f"Purchase completion processed: order_id={order_id}, user_id={user_id}")
            
            return {
                'success': True,
                'purchase_id': purchase.id,
                'order_id': order_id,
                'message': '구매가 완료되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"Purchase completion error: {e}")
            self.db.rollback()
            raise ValidationError("구매 완료 처리 중 오류가 발생했습니다.")
    
    def get_user_purchases(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        사용자 구매 내역 조회
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수
        
        Returns:
            Dict: 구매 내역 및 페이징 정보
        """
        try:
            offset = (page - 1) * per_page
            
            # 구매 내역 조회
            query = self.db.query(UserPurchase).filter(
                UserPurchase.user_id == user_id
            )
            
            total = query.count()
            
            purchases = query.order_by(
                desc(UserPurchase.created_at)
            ).offset(offset).limit(per_page).all()
            
            result = []
            for purchase in purchases:
                # 상품 정보 조회
                product = self.db.query(Product).filter(Product.id == purchase.product_id).first()
                
                purchase_data = {
                    'id': purchase.id,
                    'product_name': product.name if product else 'Unknown',
                    'product_slug': product.slug if product else '',
                    'purchase_type': purchase.purchase_type,
                    'original_price': purchase.original_price,
                    'paid_amount': purchase.paid_amount,
                    'fortune_points_used': purchase.fortune_points_used,
                    'created_at': purchase.created_at,
                    'last_accessed_at': purchase.last_accessed_at
                }
                
                result.append(purchase_data)
            
            return {
                'purchases': result,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"User purchases query error: user_id={user_id}, error={e}")
            raise ValidationError("구매 내역 조회 중 오류가 발생했습니다.")

# 의존성 주입
def get_shop_service(db: Session = Depends(get_db)) -> ShopService:
    return ShopService(db) 