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
    
    @staticmethod
    def build_saju_key(
        birth_date: str,
        birth_hour: int | None,
        gender: str,
        calendar: str = "SOL",
        timezone: str = "Asia/Seoul",
    ) -> str:
        """
        Return global-unique saju_key
        Format: {CAL}_{YYYYMMDD}_{HH|UH}_{TZ}_{SEX}
        """
        hour_part = f"{int(birth_hour):02d}" if birth_hour is not None else "UH"
        tz_part   = timezone.replace("/", "-")
        sex_part  = {"male": "M", "female": "F"}.get(gender.lower(), "U")
        return f"{calendar}_{birth_date.replace('-', '')}_{hour_part}_{tz_part}_{sex_part}"
    
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
    
    @staticmethod
    def convert_lunar_to_solar(date_str: str) -> str | None:
        """음력 YYYY-MM-DD → 양력 YYYY-MM-DD (sxtwl 이용)"""
        try:
            y, m, d = map(int, date_str.split("-"))
            day = sxtwl.fromLunar(y, m, d, False)  # 윤달 아님 가정
            return (
                f"{day.getSolarYear():04d}-"
                f"{day.getSolarMonth():02d}-"
                f"{day.getSolarDay():02d}"
            )
        except Exception as e:
            print(f"음력 변환 실패: {e}")
            return None
    
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
    
    @staticmethod
    def get_birth_info_for_calculation(saju_key: str):
        """
        Parse saju_key → (datetime[KST], original_date_str, gender)
        """
        try:
            cal, ymd, hour_part, tz_part, sex = saju_key.split("_", 4)
            gender = "male" if sex == "M" else "female" if sex == "F" else "unknown"
            hour = 12 if hour_part == "UH" else int(hour_part)

            year, month, day = int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])
            orig_date = f"{year:04d}-{month:02d}-{day:02d}"

            # 음력 → 양력
            if cal == "LUN":
                solar = SajuKeyManager.convert_lunar_to_solar(orig_date)
                if solar:
                    year, month, day = map(int, solar.split("-"))

            local_tz = pytz.timezone(tz_part.replace("-", "/"))
            dt_local = local_tz.localize(datetime(year, month, day, hour, 0, 0))
            dt_kst   = dt_local.astimezone(pytz.timezone("Asia/Seoul"))

            return dt_kst, orig_date, gender
        except Exception as e:
            print(f"SajuKeyManager.parse 오류: {e}")
            fallback = pytz.timezone("Asia/Seoul").localize(datetime(1984, 1, 1, 12))
            return fallback, "1984-01-01", "unknown"

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