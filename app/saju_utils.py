# app/saju_utils.py
from datetime import datetime, timedelta
import sxtwl
import pytz
from typing import Optional, Tuple
import pytz

class SajuKeyManager:
    """사주 키 생성 및 관리 클래스"""
    
    TIMEZONE_MAP = {
        "Asia/Seoul": "KST", "UTC": "UTC", "America/New_York": "EST",
        "Europe/London": "GMT", "Asia/Tokyo": "JST", "Asia/Shanghai": "CST",
        "America/Los_Angeles": "PST", "Europe/Paris": "CET"
    }
    
    @classmethod
    def build_saju_key(cls, 
                      birth_date: str,  # YYYY-MM-DD
                      birth_hour: Optional[int],  # 0-23 or None
                      gender: str,  # male/female
                      calendar: str = "SOL",  # SOL/LUN
                      timezone: str = "Asia/Seoul") -> str:
        """
        사주 키 생성
        
        Returns:
            예: S_19840601_20_KST_M
        """
        # 달력 코드
        cal_code = "S" if calendar == "SOL" else "L"
        
        # 날짜 코드 (하이픈 제거)
        date_code = birth_date.replace("-", "")
        
        # 시간 코드
        hour_code = f"{birth_hour:02d}" if birth_hour is not None else "UH"
        
        # 시간대 코드
        tz_code = cls.TIMEZONE_MAP.get(timezone, timezone.replace("/", "-")[:6])
        
        # 성별 코드
        sex_code = {"male": "M", "female": "F"}.get(gender, "U")
        
        return f"{cal_code}_{date_code}_{hour_code}_{tz_code}_{sex_code}"
    
    @classmethod
    def parse_saju_key(cls, saju_key: str) -> dict:
        """사주 키 파싱"""
        try:
            parts = saju_key.split("_")
            if len(parts) != 5:
                raise ValueError("Invalid saju_key format")
            
            cal_code, date_code, hour_code, tz_code, sex_code = parts
            
            return {
                "calendar": "SOL" if cal_code == "S" else "LUN",
                "birth_date": f"{date_code[:4]}-{date_code[4:6]}-{date_code[6:8]}",
                "birth_hour": None if hour_code == "UH" else int(hour_code),
                "timezone": next((k for k, v in cls.TIMEZONE_MAP.items() if v == tz_code), tz_code),
                "gender": {"M": "male", "F": "female"}.get(sex_code, "unknown")
            }
        except Exception as e:
            raise ValueError(f"Failed to parse saju_key: {e}")
    
    @classmethod
    def convert_lunar_to_solar(cls, lunar_date: str) -> str:
        """음력을 양력으로 변환"""
        try:
            year, month, day = map(int, lunar_date.split("-"))
            
            # sxtwl을 사용한 음력→양력 변환
            lunar = sxtwl.fromLunar(year, month, day, False)  # 평달 기준
            solar_date = f"{lunar.getSolar().year:04d}-{lunar.getSolar().month:02d}-{lunar.getSolar().day:02d}"
            
            return solar_date
        except Exception as e:
            print(f"음력 변환 실패: {e}")
            return lunar_date  # 실패 시 원본 반환
    
    @classmethod
    def normalize_birth_time(cls, 
                           birth_date: str, 
                           birth_hour: Optional[int],
                           timezone: str) -> datetime:
        """
        출생 시간을 표준화하여 사주 계산용 datetime 반환
        
        Args:
            birth_date: YYYY-MM-DD 형식의 날짜
            birth_hour: 시간 (0-23) 또는 None (시간 미상)
            timezone: IANA 시간대 문자열
            
        Returns:
            서울 시간대로 변환된 datetime 객체
        """
        try:
            # 시간 미상일 경우 기본값 설정 (정오 12시)
            hour = birth_hour if birth_hour is not None else 12
            
            # 현지 시간으로 datetime 생성
            year, month, day = map(int, birth_date.split("-"))
            local_dt = datetime(year, month, day, hour, 0, 0)
            
            # 지정된 시간대로 localize
            local_tz = pytz.timezone(timezone)
            localized_dt = local_tz.localize(local_dt)
            
            # 서울 시간대로 변환 (사주 계산 표준)
            seoul_tz = pytz.timezone('Asia/Seoul')
            seoul_dt = localized_dt.astimezone(seoul_tz)
            
            return seoul_dt.replace(tzinfo=None)  # naive datetime으로 반환
            
        except Exception as e:
            print(f"시간 정규화 실패: {e}")
            # 폴백: 입력된 시간을 그대로 사용
            year, month, day = map(int, birth_date.split("-"))
            return datetime(year, month, day, hour or 12, 0, 0)
    
    @classmethod
    def get_birth_info_for_calculation(cls, saju_key: str) -> Tuple[datetime, str, str]:
        """
        사주 키로부터 사주 계산에 필요한 정보 추출
        
        Returns:
            (계산용_datetime, 원본_날짜, 성별)
        """
        parsed = cls.parse_saju_key(saju_key)
        
        # 음력인 경우 양력으로 변환
        if parsed["calendar"] == "LUN":
            solar_date = cls.convert_lunar_to_solar(parsed["birth_date"])
        else:
            solar_date = parsed["birth_date"]
        
        # 시간 정규화
        calc_datetime = cls.normalize_birth_time(
            solar_date, 
            parsed["birth_hour"], 
            parsed["timezone"]
        )
        
        return calc_datetime, parsed["birth_date"], parsed["gender"]

# 사용 예시
if __name__ == "__main__":
    # 키 생성 테스트
    key1 = SajuKeyManager.build_saju_key("1984-06-01", 20, "male", "SOL", "Asia/Seoul")
    print(f"생성된 키: {key1}")  # S_19840601_20_KST_M
    
    # 키 파싱 테스트
    parsed = SajuKeyManager.parse_saju_key(key1)
    print(f"파싱 결과: {parsed}")
    
    # 계산용 정보 추출
    calc_dt, orig_date, gender = SajuKeyManager.get_birth_info_for_calculation(key1)
    print(f"계산용 시간: {calc_dt}, 원본 날짜: {orig_date}, 성별: {gender}")