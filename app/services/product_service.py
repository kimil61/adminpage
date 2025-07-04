from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import Dict, Any, List, Optional
from app.models import Product, UserReview, UserPurchase, Order, User
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError
import logging

logger = logging.getLogger(__name__)

class ProductService:
    """SEO 최적화 전용 상품 서비스"""
    
    @staticmethod
    def get_product_detail_seo(slug: str, user_id: int = None, db: Session = None) -> Optional[Dict[str, Any]]:
        """
        SEO 최적화된 상품 상세 정보 조회
        
        Args:
            slug: 상품 슬러그
            user_id: 사용자 ID (선택)
            db: 데이터베이스 세션
            
        Returns:
            Dict containing SEO optimized product information
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.slug == slug,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                return None
            
            # 리뷰 통계 조회
            reviews = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product.id,
                    UserReview.is_visible == True
                )
            ).all()
            
            avg_rating = 0
            if reviews:
                total_rating = sum(review.rating for review in reviews)
                avg_rating = round(total_rating / len(reviews), 1)
            
            # 구매자 여부 확인
            is_purchaser = False
            if user_id:
                # UserPurchase 또는 Order 테이블에서 구매 내역 확인
                purchase = db.query(UserPurchase).filter(
                    and_(
                        UserPurchase.user_id == user_id,
                        UserPurchase.product_id == product.id
                    )
                ).first()
                
                if not purchase:
                    order = db.query(Order).filter(
                        and_(
                            Order.user_id == user_id,
                            Order.product_id == product.id,
                            Order.status == "completed"
                        )
                    ).first()
                    is_purchaser = order is not None
                else:
                    is_purchaser = True
            
            # 관련 상품 추천 (같은 카테고리)
            related_products = db.query(Product).filter(
                and_(
                    Product.category == product.category,
                    Product.id != product.id,
                    Product.is_active == True
                )
            ).limit(4).all()
            
            # SEO 메타데이터 생성
            seo_metadata = ProductService.generate_seo_metadata(product, avg_rating, len(reviews))
            
            # JSON-LD 구조화 데이터
            structured_data = ProductService.generate_structured_data(product, avg_rating, len(reviews))
            
            return {
                "product": product,
                "reviews": {
                    "count": len(reviews),
                    "average_rating": avg_rating,
                    "recent_reviews": reviews[:3]
                },
                "is_purchaser": is_purchaser,
                "related_products": related_products,
                "seo_metadata": seo_metadata,
                "structured_data": structured_data
            }
            
        except Exception as e:
            logger.error(f"상품 상세 SEO 조회 실패: slug={slug}, error={e}")
            return None

    @staticmethod
    def get_product_reviews(slug: str, page: int = 1, db: Session = None) -> Optional[Dict[str, Any]]:
        """
        상품 리뷰 목록 조회 (페이징)
        
        Args:
            slug: 상품 슬러그
            page: 페이지 번호
            db: 데이터베이스 세션
            
        Returns:
            Dict containing product and reviews with pagination
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.slug == slug,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                return None
            
            # 리뷰 조회 (페이징)
            per_page = 10
            offset = (page - 1) * per_page
            
            reviews = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product.id,
                    UserReview.is_visible == True
                )
            ).order_by(desc(UserReview.created_at)).offset(offset).limit(per_page).all()
            
            # 전체 리뷰 수
            total_reviews = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product.id,
                    UserReview.is_visible == True
                )
            ).count()
            
            return {
                "product": product,
                "reviews": reviews,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_reviews,
                    "pages": (total_reviews + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"상품 리뷰 조회 실패: slug={slug}, error={e}")
            return None

    @staticmethod
    def create_product_review(
        slug: str, 
        user_id: int, 
        rating: int, 
        content: str, 
        title: str = None, 
        db: Session = None
    ) -> Dict[str, Any]:
        """
        상품 리뷰 작성 (구매자 검증 포함)
        
        Args:
            slug: 상품 슬러그
            user_id: 사용자 ID
            rating: 평점 (1-5)
            content: 리뷰 내용
            title: 리뷰 제목 (선택)
            db: 데이터베이스 세션
            
        Returns:
            Dict containing success status and message
        """
        try:
            # 상품 조회
            product = db.query(Product).filter(
                and_(
                    Product.slug == slug,
                    Product.is_active == True
                )
            ).first()
            
            if not product:
                return {"success": False, "message": "상품을 찾을 수 없습니다."}
            
            # 구매자 검증
            purchase = db.query(UserPurchase).filter(
                and_(
                    UserPurchase.user_id == user_id,
                    UserPurchase.product_id == product.id
                )
            ).first()
            
            if not purchase:
                order = db.query(Order).filter(
                    and_(
                        Order.user_id == user_id,
                        Order.product_id == product.id,
                        Order.status == "completed"
                    )
                ).first()
                
                if not order:
                    return {"success": False, "message": "구매한 상품만 리뷰를 작성할 수 있습니다."}
            
            # 기존 리뷰 확인
            existing_review = db.query(UserReview).filter(
                and_(
                    UserReview.user_id == user_id,
                    UserReview.product_id == product.id
                )
            ).first()
            
            if existing_review:
                return {"success": False, "message": "이미 리뷰를 작성한 상품입니다."}
            
            # 리뷰 생성
            new_review = UserReview(
                user_id=user_id,
                product_id=product.id,
                rating=rating,
                title=title,
                content=content,
                is_visible=True
            )
            
            db.add(new_review)
            db.commit()
            
            return {"success": True, "message": "리뷰가 작성되었습니다."}
            
        except Exception as e:
            logger.error(f"리뷰 작성 실패: slug={slug}, user_id={user_id}, error={e}")
            return {"success": False, "message": "리뷰 작성 중 오류가 발생했습니다."}

    @staticmethod
    def mark_review_helpful(review_id: int, user_id: int, db: Session = None) -> Dict[str, Any]:
        """
        리뷰 도움됨 표시
        
        Args:
            review_id: 리뷰 ID
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing success status and message
        """
        try:
            # 리뷰 조회
            review = db.query(UserReview).filter(
                and_(
                    UserReview.id == review_id,
                    UserReview.is_visible == True
                )
            ).first()
            
            if not review:
                return {"success": False, "message": "리뷰를 찾을 수 없습니다."}
            
            # TODO: ReviewHelpful 모델이 있다면 여기서 처리
            # 현재는 간단히 성공 메시지만 반환
            
            return {"success": True, "message": "도움됨으로 표시되었습니다."}
            
        except Exception as e:
            logger.error(f"리뷰 도움됨 표시 실패: review_id={review_id}, user_id={user_id}, error={e}")
            return {"success": False, "message": "처리 중 오류가 발생했습니다."}

    @staticmethod
    def report_review(review_id: int, user_id: int, db: Session = None) -> Dict[str, Any]:
        """
        리뷰 신고
        
        Args:
            review_id: 리뷰 ID
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing success status and message
        """
        try:
            # 리뷰 조회
            review = db.query(UserReview).filter(
                and_(
                    UserReview.id == review_id,
                    UserReview.is_visible == True
                )
            ).first()
            
            if not review:
                return {"success": False, "message": "리뷰를 찾을 수 없습니다."}
            
            # TODO: ReviewReport 모델이 있다면 여기서 처리
            # 현재는 간단히 성공 메시지만 반환
            
            return {"success": True, "message": "신고가 접수되었습니다."}
            
        except Exception as e:
            logger.error(f"리뷰 신고 실패: review_id={review_id}, user_id={user_id}, error={e}")
            return {"success": False, "message": "신고 처리 중 오류가 발생했습니다."}
    
    @staticmethod
    def generate_seo_metadata(product: Product, avg_rating: float, review_count: int) -> Dict[str, str]:
        """SEO 메타데이터 생성"""
        return {
            "title": f"{product.name} - AI 운세 분석 | 운세 상점",
            "description": f"{product.description[:160]}... 평점 {avg_rating}/5 ({review_count}개 리뷰)",
            "keywords": f"운세,사주,타로,AI분석,{product.name}",
            "og_title": product.name,
            "og_description": product.description[:200],
            "og_image": product.thumbnail or "/static/assets/default-product.jpg",
            "og_url": f"https://yourdomain.com/product/{product.slug}",
            "twitter_card": "summary_large_image",
            "canonical_url": f"https://yourdomain.com/product/{product.slug}"
        }
    
    @staticmethod
    def generate_structured_data(product: Product, avg_rating: float, review_count: int) -> Dict[str, Any]:
        """JSON-LD 구조화 데이터 생성"""
        return {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.name,
            "description": product.description,
            "image": product.thumbnail or "/static/assets/default-product.jpg",
            "url": f"https://yourdomain.com/product/{product.slug}",
            "brand": {
                "@type": "Brand",
                "name": "운세 상점"
            },
            "offers": {
                "@type": "Offer",
                "price": product.price,
                "priceCurrency": "KRW",
                "availability": "https://schema.org/InStock" if product.is_active else "https://schema.org/OutOfStock",
                "url": f"https://yourdomain.com/shop/{product.slug}/buy"
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": avg_rating,
                "reviewCount": review_count,
                "bestRating": 5,
                "worstRating": 1
            } if review_count > 0 else None
        } 