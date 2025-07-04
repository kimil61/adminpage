"""
추천인 서비스 - 추천인 코드 및 보상 관리
- 추천인 코드 생성 및 관리
- 추천인 보상 시스템
- 추천인 통계 및 분석
- 추천인 마케팅 도구
"""

import logging
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.models import (
    User, UserReferral, UserReferralReward, UserFortunePoint
)
from app.exceptions import BadRequestError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

class ReferralService:
    """추천인 서비스 클래스"""
    
    @staticmethod
    def generate_referral_code(user_id: int, db: Session) -> str:
        """
        추천인 코드 생성
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            str: 생성된 추천인 코드
        """
        try:
            # 기존 코드 확인
            existing_referral = db.query(UserReferral).filter(
                UserReferral.user_id == user_id
            ).first()
            
            if existing_referral:
                return existing_referral.referral_code
            
            # 새로운 코드 생성 (8자리, 영문+숫자)
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                
                # 중복 확인
                if not db.query(UserReferral).filter(
                    UserReferral.referral_code == code
                ).first():
                    break
            
            # 추천인 레코드 생성
            referral = UserReferral(
                user_id=user_id,
                referral_code=code,
                is_active=True
            )
            
            db.add(referral)
            db.commit()
            
            logger.info(f"추천인 코드 생성 성공: user_id={user_id}, code={code}")
            
            return code
            
        except Exception as e:
            logger.error(f"추천인 코드 생성 실패: user_id={user_id}, error={e}")
            db.rollback()
            raise BadRequestError("추천인 코드 생성 중 오류가 발생했습니다.")
    
    @staticmethod
    def get_referral_by_code(code: str, db: Session) -> Optional[UserReferral]:
        """
        추천인 코드로 추천인 정보 조회
        
        Args:
            code: 추천인 코드
            db: 데이터베이스 세션
            
        Returns:
            UserReferral or None: 추천인 정보
        """
        try:
            return db.query(UserReferral).filter(
                and_(
                    UserReferral.referral_code == code,
                    UserReferral.is_active == True
                )
            ).first()
            
        except Exception as e:
            logger.error(f"추천인 코드 조회 실패: code={code}, error={e}")
            return None
    
    @staticmethod
    def get_user_referral_info(user_id: int, db: Session) -> Dict[str, Any]:
        """
        사용자 추천인 정보 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing referral information
        """
        try:
            # 추천인 정보 조회
            referral = db.query(UserReferral).filter(
                UserReferral.user_id == user_id
            ).first()
            
            if not referral:
                return {
                    "has_referral": False,
                    "referral_code": None,
                    "total_referrals": 0,
                    "total_rewards": 0,
                    "recent_referrals": []
                }
            
            # 추천받은 사용자 수 조회
            total_referrals = db.query(User).filter(
                User.referred_by == user_id
            ).count()
            
            # 총 보상 포인트 조회
            total_rewards = db.query(func.sum(UserReferralReward.points)).filter(
                UserReferralReward.referrer_id == user_id
            ).scalar() or 0
            
            # 최근 추천받은 사용자 조회
            recent_referrals = db.query(User).filter(
                User.referred_by == user_id
            ).order_by(desc(User.created_at)).limit(5).all()
            
            return {
                "has_referral": True,
                "referral_code": referral.referral_code,
                "total_referrals": total_referrals,
                "total_rewards": total_rewards,
                "recent_referrals": recent_referrals,
                "is_active": referral.is_active
            }
            
        except Exception as e:
            logger.error(f"사용자 추천인 정보 조회 실패: user_id={user_id}, error={e}")
            return {
                "has_referral": False,
                "referral_code": None,
                "total_referrals": 0,
                "total_rewards": 0,
                "recent_referrals": []
            }
    
    @staticmethod
    def process_referral_signup(
        referral_code: str,
        new_user_id: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        추천인 가입 처리
        
        Args:
            referral_code: 추천인 코드
            new_user_id: 새로 가입한 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 추천인 코드 유효성 확인
            referral = ReferralService.get_referral_by_code(referral_code, db)
            if not referral:
                return False, "유효하지 않은 추천인 코드입니다.", {}
            
            # 자기 자신을 추천할 수 없음
            if referral.user_id == new_user_id:
                return False, "자기 자신을 추천할 수 없습니다.", {}
            
            # 이미 추천받은 사용자인지 확인
            new_user = db.query(User).filter(User.id == new_user_id).first()
            if not new_user:
                return False, "사용자를 찾을 수 없습니다.", {}
            
            if new_user.referred_by:
                return False, "이미 추천인을 통해 가입한 사용자입니다.", {}
            
            # 추천인 정보 업데이트
            new_user.referred_by = referral.user_id
            new_user.referral_signup_date = datetime.now()
            
            # 추천인 보상 지급
            reward_points = 1000  # 기본 보상 포인트
            reward = UserReferralReward(
                referrer_id=referral.user_id,
                referred_user_id=new_user_id,
                points=reward_points,
                reward_type="signup",
                description="추천인 가입 보상"
            )
            
            # 추천인 포인트 증가
            referrer_points = db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == referral.user_id
            ).first()
            
            if referrer_points:
                referrer_points.points += reward_points
            else:
                referrer_points = UserFortunePoint(
                    user_id=referral.user_id,
                    points=reward_points
                )
                db.add(referrer_points)
            
            db.add(reward)
            db.commit()
            
            logger.info(f"추천인 가입 처리 성공: referrer_id={referral.user_id}, new_user_id={new_user_id}, points={reward_points}")
            
            return True, "추천인 가입이 완료되었습니다.", {
                "referrer_id": referral.user_id,
                "reward_points": reward_points
            }
            
        except Exception as e:
            logger.error(f"추천인 가입 처리 실패: referral_code={referral_code}, new_user_id={new_user_id}, error={e}")
            db.rollback()
            return False, "추천인 가입 처리 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def process_referral_purchase(
        referred_user_id: int,
        purchase_amount: int,
        db: Session
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        추천받은 사용자의 구매 시 보상 처리
        
        Args:
            referred_user_id: 추천받은 사용자 ID
            purchase_amount: 구매 금액
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str, Dict]: (성공 여부, 메시지, 결과 데이터)
        """
        try:
            # 추천받은 사용자 정보 조회
            referred_user = db.query(User).filter(User.id == referred_user_id).first()
            if not referred_user or not referred_user.referred_by:
                return False, "추천인 정보를 찾을 수 없습니다.", {}
            
            # 이미 이번 구매에 대한 보상을 받았는지 확인
            existing_reward = db.query(UserReferralReward).filter(
                and_(
                    UserReferralReward.referrer_id == referred_user.referred_by,
                    UserReferralReward.referred_user_id == referred_user_id,
                    UserReferralReward.reward_type == "purchase",
                    UserReferralReward.created_at >= datetime.now() - timedelta(days=30)
                )
            ).first()
            
            if existing_reward:
                return False, "이미 이번 구매에 대한 보상을 받았습니다.", {}
            
            # 보상 포인트 계산 (구매 금액의 5%, 최대 5000포인트)
            reward_points = min(int(purchase_amount * 0.05), 5000)
            
            # 추천인 보상 지급
            reward = UserReferralReward(
                referrer_id=referred_user.referred_by,
                referred_user_id=referred_user_id,
                points=reward_points,
                reward_type="purchase",
                description=f"추천인 구매 보상 (구매금액: {purchase_amount:,}원)"
            )
            
            # 추천인 포인트 증가
            referrer_points = db.query(UserFortunePoint).filter(
                UserFortunePoint.user_id == referred_user.referred_by
            ).first()
            
            if referrer_points:
                referrer_points.points += reward_points
            else:
                referrer_points = UserFortunePoint(
                    user_id=referred_user.referred_by,
                    points=reward_points
                )
                db.add(referrer_points)
            
            db.add(reward)
            db.commit()
            
            logger.info(f"추천인 구매 보상 처리 성공: referrer_id={referred_user.referred_by}, referred_user_id={referred_user_id}, points={reward_points}")
            
            return True, "추천인 구매 보상이 지급되었습니다.", {
                "referrer_id": referred_user.referred_by,
                "reward_points": reward_points,
                "purchase_amount": purchase_amount
            }
            
        except Exception as e:
            logger.error(f"추천인 구매 보상 처리 실패: referred_user_id={referred_user_id}, error={e}")
            db.rollback()
            return False, "추천인 구매 보상 처리 중 오류가 발생했습니다.", {}
    
    @staticmethod
    def get_referral_rewards(
        user_id: int,
        db: Session,
        page: int = 1,
        per_page: int = 10
    ) -> Dict[str, Any]:
        """
        추천인 보상 내역 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            page: 페이지 번호
            per_page: 페이지당 항목 수
            
        Returns:
            Dict containing referral rewards and pagination
        """
        try:
            offset = (page - 1) * per_page
            
            # 보상 내역 조회
            rewards = db.query(UserReferralReward).filter(
                UserReferralReward.referrer_id == user_id
            ).order_by(desc(UserReferralReward.created_at)).offset(offset).limit(per_page).all()
            
            # 전체 개수 조회
            total = db.query(UserReferralReward).filter(
                UserReferralReward.referrer_id == user_id
            ).count()
            
            return {
                "rewards": rewards,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            logger.error(f"추천인 보상 내역 조회 실패: user_id={user_id}, error={e}")
            return {
                "rewards": [],
                "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0}
            }
    
    @staticmethod
    def get_referral_statistics(user_id: int, db: Session) -> Dict[str, Any]:
        """
        추천인 통계 조회
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict containing referral statistics
        """
        try:
            # 총 추천받은 사용자 수
            total_referrals = db.query(User).filter(
                User.referred_by == user_id
            ).count()
            
            # 이번 달 추천받은 사용자 수
            this_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            this_month_referrals = db.query(User).filter(
                and_(
                    User.referred_by == user_id,
                    User.referral_signup_date >= this_month
                )
            ).count()
            
            # 총 보상 포인트
            total_rewards = db.query(func.sum(UserReferralReward.points)).filter(
                UserReferralReward.referrer_id == user_id
            ).scalar() or 0
            
            # 이번 달 보상 포인트
            this_month_rewards = db.query(func.sum(UserReferralReward.points)).filter(
                and_(
                    UserReferralReward.referrer_id == user_id,
                    UserReferralReward.created_at >= this_month
                )
            ).scalar() or 0
            
            # 보상 타입별 통계
            signup_rewards = db.query(func.sum(UserReferralReward.points)).filter(
                and_(
                    UserReferralReward.referrer_id == user_id,
                    UserReferralReward.reward_type == "signup"
                )
            ).scalar() or 0
            
            purchase_rewards = db.query(func.sum(UserReferralReward.points)).filter(
                and_(
                    UserReferralReward.referrer_id == user_id,
                    UserReferralReward.reward_type == "purchase"
                )
            ).scalar() or 0
            
            return {
                "total_referrals": total_referrals,
                "this_month_referrals": this_month_referrals,
                "total_rewards": total_rewards,
                "this_month_rewards": this_month_rewards,
                "signup_rewards": signup_rewards,
                "purchase_rewards": purchase_rewards
            }
            
        except Exception as e:
            logger.error(f"추천인 통계 조회 실패: user_id={user_id}, error={e}")
            return {
                "total_referrals": 0,
                "this_month_referrals": 0,
                "total_rewards": 0,
                "this_month_rewards": 0,
                "signup_rewards": 0,
                "purchase_rewards": 0
            }
    
    @staticmethod
    def deactivate_referral_code(user_id: int, db: Session) -> Tuple[bool, str]:
        """
        추천인 코드 비활성화
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
        """
        try:
            referral = db.query(UserReferral).filter(
                UserReferral.user_id == user_id
            ).first()
            
            if not referral:
                return False, "추천인 코드를 찾을 수 없습니다."
            
            referral.is_active = False
            db.commit()
            
            logger.info(f"추천인 코드 비활성화 성공: user_id={user_id}")
            
            return True, "추천인 코드가 비활성화되었습니다."
            
        except Exception as e:
            logger.error(f"추천인 코드 비활성화 실패: user_id={user_id}, error={e}")
            db.rollback()
            return False, "추천인 코드 비활성화 중 오류가 발생했습니다."
    
    @staticmethod
    def reactivate_referral_code(user_id: int, db: Session) -> Tuple[bool, str]:
        """
        추천인 코드 재활성화
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Tuple[bool, str]: (성공 여부, 메시지)
        """
        try:
            referral = db.query(UserReferral).filter(
                UserReferral.user_id == user_id
            ).first()
            
            if not referral:
                return False, "추천인 코드를 찾을 수 없습니다."
            
            referral.is_active = True
            db.commit()
            
            logger.info(f"추천인 코드 재활성화 성공: user_id={user_id}")
            
            return True, "추천인 코드가 재활성화되었습니다."
            
        except Exception as e:
            logger.error(f"추천인 코드 재활성화 실패: user_id={user_id}, error={e}")
            db.rollback()
            return False, "추천인 코드 재활성화 중 오류가 발생했습니다." 