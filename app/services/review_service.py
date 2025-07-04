"""
리뷰 서비스 - 상품 리뷰 관리
- 리뷰 작성 및 수정
- 평점 시스템
- 구매 인증
- 리뷰 신고 및 관리
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from fastapi import Depends
from app.models import (
    User, Product, UserReview, UserPurchase, Order
)
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

class ReviewService:
    """리뷰 서비스 클래스"""
    
    @staticmethod
    def get_product_reviews(
        product_id: int,
        db: Session,
        page: int = 1,
        per_page: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        rating_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        상품 리뷰 목록 조회
        
        Args:
            product_id: 상품 ID
            db: 데이터베이스 세션
            page: 페이지 번호
            per_page: 페이지당 항목 수
            sort_by: 정렬 기준
            sort_order: 정렬 순서
            rating_filter: 평점 필터
            
        Returns:
            Dict containing reviews and statistics
        """
        try:
            offset = (page - 1) * per_page
            
            # 기본 쿼리
            query = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product_id,
                    UserReview.is_visible == True
                )
            )
            
            # 평점 필터
            if rating_filter:
                query = query.filter(UserReview.rating == rating_filter)
            
            # 정렬
            if sort_by == "rating":
                order_func = desc(UserReview.rating) if sort_order == "desc" else asc(UserReview.rating)
            elif sort_by == "helpful":
                order_func = desc(UserReview.helpful_count) if sort_order == "desc" else asc(UserReview.helpful_count)
            else:
                order_func = desc(UserReview.created_at) if sort_order == "desc" else asc(UserReview.created_at)
            
            query = query.order_by(order_func)
            
            # 리뷰 조회
            reviews = query.offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total_query = db.query(UserReview).filter(
                and_(
                    UserReview.product_id == product_id,
                    UserReview.is_visible == True
                )
            )
            if rating_filter:
                total_query = total_query.filter(UserReview.rating == rating_filter)
            
            total = total_query.count()
            
            # 평점 통계 조회
            stats_query = db.query(
                func.avg(UserReview.rating).label('avg_rating'),
                func.count(UserReview.id).label('total_reviews'),
                func.sum(UserReview.helpful_count).label('total_helpful')
            ).filter(
                and_(
                    UserReview.product_id == product_id,
                    UserReview.is_visible == True
                )
            )
            
            stats = stats_query.first()
            
            # 평점별 개수 조회
            rating_counts = db.query(
                UserReview.rating,
                func.count(UserReview.id).label('count')
            ).filter(
                and_(
                    UserReview.product_id == product_id,
                    UserReview.is_visible == True
                )
            ).group_by(UserReview.rating).all()
            
            rating_distribution = {i: 0 for i in range(1, 6)}
            for rating, count in rating_counts:
                rating_distribution[rating] = count
            
            return {
                "reviews": reviews,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                },
                "statistics": {
                    "average_rating": round(float(stats.avg_rating or 0), 1),
                    "total_reviews": stats.total_reviews or 0,
                    "total_helpful": stats.total_helpful or 0,
                    "rating_distribution": rating_distribution
                }
            }
            
        except Exception as e:
            logger.error(f"상품 리뷰 조회 실패: product_id={product_id}, error={e}")
            return {
                "reviews": [],
                "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0},
                "statistics": {"average_rating": 0, "total_reviews": 0, "total_helpful": 0, "rating_distribution": {}}
            }
    
    @staticmethod
    def can_write_review(user_id: int, product_id: int, db: Session) -> Tuple[bool, str]:
        """
        리뷰 작성 가능 여부 확인
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (작성 가능 여부, 메시지)
        """
        try:
            # 이미 작성한 리뷰 확인
            existing_review = db.query(UserReview).filter(
                and_(
                    UserReview.user_id == user_id,
                    UserReview.product_id == product_id
                )
            ).first()
            
            if existing_review:
                return False, "이미 리뷰를 작성했습니다."
            
            # 구매 내역 확인
            purchase = db.query(UserPurchase).filter(
                and_(
                    UserPurchase.user_id == user_id,
                    UserPurchase.product_id == product_id
                )
            ).first()
            
            if not purchase:
                return False, "구매 내역이 없어 리뷰를 작성할 수 없습니다."
            
            return True, "리뷰 작성이 가능합니다."
            
        except Exception as e:
            logger.error(f"리뷰 작성 가능 여부 확인 실패: user_id={user_id}, product_id={product_id}, error={e}")
            return False, "리뷰 작성 가능 여부를 확인할 수 없습니다."
    
    @staticmethod
    def create_review(
        user_id: int,
        product_id: int,
        rating: int,
        content: str,
        title: Optional[str] = None,
        accuracy_rating: Optional[int] = None,
        satisfaction_rating: Optional[int] = None,
        recommendation_rating: Optional[int] = None,
        db: Session = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        리뷰 작성
        
        Args:
            user_id: 사용자 ID
            product_id: 상품 ID
            rating: 평점 (1-5)
            content: 리뷰 내용
            title: 리뷰 제목 (선택)
            accuracy_rating: 정확도 평점 (1-5)
            satisfaction_rating: 만족도 평점 (1-5)
            recommendation_rating: 추천도 평점 (1-5)
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 입력 검증
            if not (1 <= rating <= 5):
                return False, "평점은 1-5 사이의 값이어야 합니다.", {}
            
            if not content or len(content.strip()) < 10:
                return False, "리뷰 내용은 최소 10자 이상이어야 합니다.", {}
            
            # 추가 평점 검증
            for additional_rating in [accuracy_rating, satisfaction_rating, recommendation_rating]:
                if additional_rating is not None and not (1 <= additional_rating <= 5):
                    return False, "추가 평점은 1-5 사이의 값이어야 합니다.", {}
            
            # 리뷰 작성 가능 여부 확인
            can_write, message = ReviewService.can_write_review(user_id, product_id, db)
            if not can_write:
                return False, message, {}
            
            # 구매 내역 조회 (인증된 리뷰용)
            purchase = db.query(UserPurchase).filter(
                and_(
                    UserPurchase.user_id == user_id,
                    UserPurchase.product_id == product_id
                )
            ).first()
            
            # 리뷰 생성
            review = UserReview(
                user_id=user_id,
                product_id=product_id,
                order_id=purchase.order_id if purchase else None,
                rating=rating,
                title=title,
                content=content.strip(),
                accuracy_rating=accuracy_rating,
                satisfaction_rating=satisfaction_rating,
                recommendation_rating=recommendation_rating,
                is_verified=True if purchase else False,
                is_visible=True
            )
            
            db.add(review)
            db.commit()
            db.refresh(review)
            
            logger.info(f"리뷰 작성 성공: user_id={user_id}, product_id={product_id}, review_id={review.id}")
            
            return True, "리뷰가 성공적으로 작성되었습니다.", {
                "review_id": review.id,
                "is_verified": review.is_verified
            }
            
        except Exception as e:
            logger.error(f"리뷰 작성 실패: user_id={user_id}, product_id={product_id}, error={e}")
            db.rollback()
            return False, "리뷰 작성 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def update_review(
        user_id: int,
        review_id: int,
        rating: Optional[int] = None,
        content: Optional[str] = None,
        title: Optional[str] = None,
        accuracy_rating: Optional[int] = None,
        satisfaction_rating: Optional[int] = None,
        recommendation_rating: Optional[int] = None,
        db: Session = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        리뷰 수정
        
        Args:
            user_id: 사용자 ID
            review_id: 리뷰 ID
            rating: 평점 (1-5)
            content: 리뷰 내용
            title: 리뷰 제목
            accuracy_rating: 정확도 평점 (1-5)
            satisfaction_rating: 만족도 평점 (1-5)
            recommendation_rating: 추천도 평점 (1-5)
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 리뷰 조회
            review = db.query(UserReview).filter(
                and_(
                    UserReview.id == review_id,
                    UserReview.user_id == user_id
                )
            ).first()
            
            if not review:
                return False, "수정할 리뷰를 찾을 수 없습니다.", {}
            
            # 입력 검증
            if rating is not None and not (1 <= rating <= 5):
                return False, "평점은 1-5 사이의 값이어야 합니다.", {}
            
            if content is not None and len(content.strip()) < 10:
                return False, "리뷰 내용은 최소 10자 이상이어야 합니다.", {}
            
            # 추가 평점 검증
            for additional_rating in [accuracy_rating, satisfaction_rating, recommendation_rating]:
                if additional_rating is not None and not (1 <= additional_rating <= 5):
                    return False, "추가 평점은 1-5 사이의 값이어야 합니다.", {}
            
            # 리뷰 업데이트
            if rating is not None:
                review.rating = rating
            if content is not None:
                review.content = content.strip()
            if title is not None:
                review.title = title
            if accuracy_rating is not None:
                review.accuracy_rating = accuracy_rating
            if satisfaction_rating is not None:
                review.satisfaction_rating = satisfaction_rating
            if recommendation_rating is not None:
                review.recommendation_rating = recommendation_rating
            
            review.updated_at = datetime.now()
            
            db.commit()
            
            logger.info(f"리뷰 수정 성공: user_id={user_id}, review_id={review_id}")
            
            return True, "리뷰가 성공적으로 수정되었습니다.", {
                "review_id": review.id
            }
            
        except Exception as e:
            logger.error(f"리뷰 수정 실패: user_id={user_id}, review_id={review_id}, error={e}")
            db.rollback()
            return False, "리뷰 수정 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def delete_review(user_id: int, review_id: int, db: Session) -> Tuple[bool, str]:
        """
        리뷰 삭제 (소프트 삭제)
        
        Args:
            user_id: 사용자 ID
            review_id: 리뷰 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
        """
        try:
            # 리뷰 조회
            review = db.query(UserReview).filter(
                and_(
                    UserReview.id == review_id,
                    UserReview.user_id == user_id
                )
            ).first()
            
            if not review:
                return False, "삭제할 리뷰를 찾을 수 없습니다."
            
            # 소프트 삭제 (비활성화)
            review.is_visible = False
            db.commit()
            
            logger.info(f"리뷰 삭제 성공: user_id={user_id}, review_id={review_id}")
            
            return True, "리뷰가 성공적으로 삭제되었습니다."
            
        except Exception as e:
            logger.error(f"리뷰 삭제 실패: user_id={user_id}, review_id={review_id}, error={e}")
            db.rollback()
            return False, "리뷰 삭제 중 오류가 발생했습니다."
    
    @staticmethod
    def mark_helpful(review_id: int, user_id: int, db: Session) -> Tuple[bool, str]:
        """
        리뷰 도움됨 표시
        
        Args:
            review_id: 리뷰 ID
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
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
                return False, "리뷰를 찾을 수 없습니다."
            
            # 자신의 리뷰는 도움됨 표시 불가
            if review.user_id == user_id:
                return False, "자신의 리뷰에는 도움됨을 표시할 수 없습니다."
            
            # 도움됨 카운트 증가
            review.helpful_count += 1
            db.commit()
            
            logger.info(f"리뷰 도움됨 표시 성공: review_id={review_id}, user_id={user_id}")
            
            return True, "도움됨으로 표시되었습니다."
            
        except Exception as e:
            logger.error(f"리뷰 도움됨 표시 실패: review_id={review_id}, user_id={user_id}, error={e}")
            db.rollback()
            return False, "도움됨 표시 중 오류가 발생했습니다."
    
    @staticmethod
    def report_review(
        review_id: int,
        user_id: int,
        reason: str,
        description: Optional[str] = None,
        db: Session = None
    ) -> Tuple[bool, str]:
        """
        리뷰 신고
        
        Args:
            review_id: 리뷰 ID
            user_id: 신고자 ID
            reason: 신고 사유
            description: 상세 설명 (선택)
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
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
                return False, "신고할 리뷰를 찾을 수 없습니다."
            
            # 자신의 리뷰는 신고 불가
            if review.user_id == user_id:
                return False, "자신의 리뷰는 신고할 수 없습니다."
            
            # 신고 카운트 증가
            review.report_count += 1
            
            # 신고 사유 저장 (임시 - 나중에 별도 테이블로 확장)
            # TODO: ReviewReport 테이블 생성
            
            db.commit()
            
            logger.info(f"리뷰 신고 성공: review_id={review_id}, user_id={user_id}, reason={reason}")
            
            return True, "리뷰가 신고되었습니다. 검토 후 조치하겠습니다."
            
        except Exception as e:
            logger.error(f"리뷰 신고 실패: review_id={review_id}, user_id={user_id}, error={e}")
            db.rollback()
            return False, "리뷰 신고 중 오류가 발생했습니다."
    
    @staticmethod
    def get_user_reviews(
        user_id: int,
        db: Session,
        page: int = 1,
        per_page: int = 10
    ) -> Dict[str, Any]:
        """
        사용자 리뷰 목록 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            page: 페이지 번호
            per_page: 페이지당 항목 수
            
        Returns:
            Dict containing user reviews and pagination
        """
        try:
            offset = (page - 1) * per_page
            
            # 리뷰 조회
            reviews = db.query(UserReview).filter(
                and_(
                    UserReview.user_id == user_id,
                    UserReview.is_visible == True
                )
            ).order_by(desc(UserReview.created_at)).offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total = db.query(UserReview).filter(
                and_(
                    UserReview.user_id == user_id,
                    UserReview.is_visible == True
                )
            ).count()
            
            return {
                "reviews": reviews,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"사용자 리뷰 조회 실패: user_id={user_id}, error={e}")
            return {
                "reviews": [],
                "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0}
            } 