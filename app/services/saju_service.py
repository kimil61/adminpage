# app/services/saju_service.py
from datetime import datetime
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from app.models import SajuUser
from app.saju_utils import SajuKeyManager

class SajuService:
    """사주 계산 통합 서비스"""
    
    @staticmethod
    def get_or_calculate_saju(saju_key: str, db: Session) -> Tuple[dict, dict]:
        """
        사주 가져오기 또는 계산 (캐싱 포함)
        
        Args:
            saju_key: 사주 키
            db: 데이터베이스 세션
            
        Returns:
            tuple: (pillars, elem_dict_kr)
        """
        # 1. DB에서 이미 계산된 사주 찾기
        saju_user = db.query(SajuUser).filter_by(saju_key=saju_key).first()
        
        if saju_user and saju_user.calculated_pillars and saju_user.elem_dict_kr:
            # 이미 계산된 사주 반환
            return saju_user.calculated_pillars, saju_user.elem_dict_kr
        
        # 2. 없으면 새로 계산
        try:
            # SajuKeyManager를 통해 올바른 계산용 날짜 획득
            calc_datetime, orig_date, gender = SajuKeyManager.get_birth_info_for_calculation(saju_key)
            
            # 사주 계산 (기존 함수들 import)
            from app.routers.saju import calculate_four_pillars, analyze_four_pillars_to_string
            
            pillars = calculate_four_pillars(calc_datetime)
            elem_dict_kr, _ = analyze_four_pillars_to_string(
                pillars['year'][0], pillars['year'][1],
                pillars['month'][0], pillars['month'][1], 
                pillars['day'][0], pillars['day'][1],
                pillars['hour'][0], pillars['hour'][1],
            )
            
            # 3. DB에 저장 (업데이트 또는 새로 생성)
            if saju_user:
                saju_user.calculated_pillars = pillars
                saju_user.elem_dict_kr = elem_dict_kr
                saju_user.calculated_at = datetime.now()
            else:
                # saju_user가 없는 경우는 일단 패스 (기존 코드와의 호환성)
                pass
            
            db.commit()
            return pillars, elem_dict_kr
            
        except Exception as e:
            print(f"사주 계산 실패: {e}")
            # 기본값 반환
            return {
                "year": "甲子", "month": "甲子", 
                "day": "甲子", "hour": "甲子"
            }, {'목': 0, '화': 0, '토': 0, '금': 0, '수': 0}
    
    @staticmethod
    def invalidate_cache(saju_key: str, db: Session) -> None:
        """
        사주 캐시 무효화 (데이터 변경시)
        
        Args:
            saju_key: 사주 키
            db: 데이터베이스 세션
        """
        saju_user = db.query(SajuUser).filter_by(saju_key=saju_key).first()
        if saju_user:
            saju_user.calculated_pillars = None
            saju_user.elem_dict_kr = None
            saju_user.calculated_at = None
            db.commit()
    
    @staticmethod
    def has_cached_saju(saju_key: str, db: Session) -> bool:
        """
        사주가 캐시되어 있는지 확인
        
        Args:
            saju_key: 사주 키
            db: 데이터베이스 세션
            
        Returns:
            bool: 캐시 여부
        """
        saju_user = db.query(SajuUser).filter_by(saju_key=saju_key).first()
        return bool(
            saju_user and 
            saju_user.calculated_pillars and 
            saju_user.elem_dict_kr
        )