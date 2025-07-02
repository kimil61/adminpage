# app/models.py - 운세 커머스 플랫폼 완전 설계

from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime, Date, Text, ForeignKey, UniqueConstraint, JSON, Numeric, Index
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime, timedelta
from decimal import Decimal

################################################################################
# 🏗️ 기존 모델 수정 (A. 기존 모델 수정)
################################################################################

class User(Base):
    """기존 User 모델 - 유지"""
    __tablename__ = "blog_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    points = Column(Integer, default=0)  # 일반 포인트 (유지)
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계 설정
    posts = relationship("Post", back_populates="author")
    fortune_points = relationship("UserFortunePoint", back_populates="user")
    fortune_transactions = relationship("FortuneTransaction", back_populates="user")
    orders = relationship("Order", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    purchases = relationship("UserPurchase", back_populates="user")
    reviews = relationship("UserReview", back_populates="user")
    referral_rewards = relationship(
        "ReferralReward",
        back_populates="user",
        foreign_keys="ReferralReward.referrer_user_id"
    )
    attendance_records = relationship("DailyAttendance", back_populates="user")

class UserFortunePoint(Base):
    """행운 포인트 관리 - 기존 유지"""
    __tablename__ = "user_fortune_points"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    points = Column(Integer, default=0)  # 현재 보유 행운 포인트
    total_earned = Column(Integer, default=0)  # 총 획득 포인트
    total_spent = Column(Integer, default=0)   # 총 사용 포인트
    last_updated = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="fortune_points")

class FortuneTransaction(Base):
    """행운 거래 내역 - 기존 유지 + 확장"""
    __tablename__ = "fortune_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    transaction_type = Column(Enum("earn", "spend", "refund", "expire", name="transaction_type"), nullable=False)
    amount = Column(Integer, nullable=False)  # 포인트 양 (양수/음수)
    balance_after = Column(Integer, nullable=False)  # 거래 후 잔액
    source = Column(String(100))  # 거래 소스 (예: 'purchase', 'daily_bonus', 'referral')
    reference_id = Column(String(100))  # 참조 ID (주문번호, 상품코드 등)
    description = Column(String(255))  # 거래 설명
    expires_at = Column(DateTime, nullable=True)  # 포인트 만료일 (적립된 경우)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="fortune_transactions")

class Product(Base):
    """상품 테이블 - 확장"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 상품명
    description = Column(Text)  # 설명
    price = Column(Integer, nullable=False)  # 원화 가격
    code = Column(String(50), unique=True, nullable=False)  # 상품 코드
    
    # 🆕 새로 추가된 필드들
    category = Column(String(50), default="saju")  # 카테고리 (saju, tarot, etc)
    pricing_type = Column(Enum("one_time", "subscription", name="pricing_type"), default="one_time")
    slug = Column(String(100), unique=True, nullable=False)  # SEO URL
    fortune_cost = Column(Integer, default=0)  # 행운 포인트 비용 (0이면 현금 결제만)
    thumbnail = Column(String(255), nullable=True)  # 썸네일 이미지
    features = Column(JSON, nullable=True)  # 상품 특징 리스트
    tags = Column(JSON, nullable=True)  # 태그들
    difficulty_level = Column(Integer, default=1)  # 난이도 (1-5)
    estimated_time = Column(Integer, default=5)  # 예상 소요시간(분)
    
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # 추천 상품 여부
    sort_order = Column(Integer, default=0)  # 정렬 순서
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    orders = relationship("Order", back_populates="product")
    saju_products = relationship("SajuProduct", back_populates="base_product")
    reviews = relationship("UserReview", back_populates="product")

class Order(Base):
    """주문 테이블 - 확장"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    amount = Column(Integer, nullable=False)  # 결제 금액
    kakao_tid = Column(String(100), unique=True, nullable=False)
    saju_key = Column(String(100), nullable=False)
    pdf_send_email = Column(String(100), nullable=True)
    pdf_send_phone = Column(String(50), nullable=True)
    
    # 기존 필드들
    status = Column(Enum("pending", "paid", "cancelled", "refunded", name="order_status"), default="pending")
    report_status = Column(Enum("pending", "generating", "completed", "failed", name="report_status"), default="pending")
    celery_task_id = Column(String(200), nullable=True)
    report_completed_at = Column(DateTime, nullable=True)
    analysis_cache_id = Column(Integer, ForeignKey("saju_analysis_cache.id"), nullable=True)
    report_html = Column(String(255), nullable=True)
    report_pdf = Column(String(255), nullable=True)
    
    # 🆕 구독 관련 필드들
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    payment_method = Column(String(50), default="kakao")  # 결제 수단
    is_subscription_payment = Column(Boolean, default=False)  # 구독 결제 여부
    billing_cycle = Column(Integer, nullable=True)  # 빌링 사이클 (구독인 경우)
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    subscription = relationship("Subscription", back_populates="orders")
    analysis_cache = relationship("SajuAnalysisCache", back_populates="orders")

################################################################################
# 🆕 신규 모델 추가 (B. 신규 모델 추가)
################################################################################

class Subscription(Base):
    """1. 정기구독 관리"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    plan_type = Column(String(50), nullable=False)  # 'basic', 'premium', 'vip'
    
    # 구독 상태
    status = Column(Enum("active", "paused", "cancelled", "expired", name="subscription_status"), default="active")
    
    # 구독 혜택
    monthly_fortune_points = Column(Integer, default=0)  # 월 지급 행운 포인트
    discount_rate = Column(Numeric(5, 2), default=0.00)  # 할인율 (0.00-100.00)
    priority_support = Column(Boolean, default=False)  # 우선 지원
    exclusive_content = Column(Boolean, default=False)  # 독점 콘텐츠 접근
    
    # 결제 정보
    monthly_price = Column(Integer, nullable=False)  # 월 요금
    next_billing_date = Column(Date, nullable=False)  # 다음 결제일
    last_billing_date = Column(Date, nullable=True)  # 마지막 결제일
    auto_renewal = Column(Boolean, default=True)  # 자동 갱신
    
    # 구독 기간
    started_at = Column(DateTime, default=datetime.now)
    ends_at = Column(DateTime, nullable=True)  # 구독 종료일 (해지시)
    cancelled_at = Column(DateTime, nullable=True)  # 해지 신청일
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="subscriptions")
    orders = relationship("Order", back_populates="subscription")
    
    # 인덱스
    __table_args__ = (
        Index('idx_subscription_user_status', 'user_id', 'status'),
        Index('idx_subscription_billing', 'next_billing_date', 'status'),
    )

class SajuProduct(Base):
    """2. 운세 상품 전용"""
    __tablename__ = "saju_products"
    
    id = Column(Integer, primary_key=True, index=True)
    base_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # 사주 전용 설정
    analysis_type = Column(String(50), nullable=False)  # 'basic', 'detailed', 'love', 'career', 'health'
    ai_model = Column(String(50), default="gpt-4o")  # 사용할 AI 모델
    prompt_version = Column(String(20), default="v3")  # 프롬프트 버전
    
    # 분석 범위
    includes_yearly_fortune = Column(Boolean, default=True)  # 연간 운세 포함
    includes_monthly_fortune = Column(Boolean, default=False)  # 월간 운세 포함
    includes_compatibility = Column(Boolean, default=False)  # 궁합 분석 포함
    includes_lucky_items = Column(Boolean, default=True)  # 행운 아이템 포함
    
    # 출력 설정
    output_format = Column(JSON, default={"html": True, "pdf": True})  # 출력 형식
    max_pages = Column(Integer, default=10)  # 최대 페이지 수
    template_style = Column(String(50), default="modern")  # 템플릿 스타일
    
    # 접근 권한
    min_subscription_level = Column(String(20), nullable=True)  # 최소 구독 등급 요구사항
    fortune_point_cost = Column(Integer, default=0)  # 행운 포인트 비용
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    base_product = relationship("Product", back_populates="saju_products")

class UserPurchase(Base):
    """3. 운세 구매 기록"""
    __tablename__ = "user_purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # 구매 정보
    purchase_type = Column(String(20), default="cash")  # 'cash', 'fortune_points', 'subscription'
    original_price = Column(Integer, nullable=False)  # 원래 가격
    paid_amount = Column(Integer, nullable=False)  # 실제 지불 금액
    fortune_points_used = Column(Integer, default=0)  # 사용한 행운 포인트
    discount_amount = Column(Integer, default=0)  # 할인 금액
    
    # 사용 이력
    access_count = Column(Integer, default=0)  # 접근 횟수
    last_accessed_at = Column(DateTime, nullable=True)  # 마지막 접근 시간
    expires_at = Column(DateTime, nullable=True)  # 만료일 (있는 경우)
    
    # 추가 정보
    saju_key = Column(String(100), nullable=True)  # 관련 사주 키
    info_metadata = Column(JSON, nullable=True)  # 추가 메타데이터
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="purchases")
    product = relationship("Product")
    order = relationship("Order")
    
    # 인덱스
    __table_args__ = (
        Index('idx_purchase_user_product', 'user_id', 'product_id'),
        Index('idx_purchase_saju_key', 'saju_key'),
    )

class ReferralReward(Base):
    """4. 추천 리워드"""
    __tablename__ = "referral_rewards"
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)  # 추천한 사람
    referred_user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=True)   # 추천받은 사람
    
    # 추천 정보
    referral_code = Column(String(20), unique=True, nullable=False)  # 추천 코드
    referral_type = Column(String(20), default="signup")  # 'signup', 'purchase', 'subscription'
    
    # 보상 정보
    reward_type = Column(String(20), nullable=False)  # 'fortune_points', 'discount', 'cash'
    reward_amount = Column(Integer, nullable=False)  # 보상 양
    reward_description = Column(String(255))  # 보상 설명
    
    # 상태 관리
    status = Column(Enum("pending", "completed", "cancelled", name="referral_status"), default="pending")
    awarded_at = Column(DateTime, nullable=True)  # 보상 지급일
    expires_at = Column(DateTime, nullable=True)  # 보상 만료일
    
    # 추적 정보
    ip_address = Column(String(45), nullable=True)  # 가입시 IP
    user_agent = Column(String(255), nullable=True)  # 가입시 User Agent
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="referral_rewards", foreign_keys=[referrer_user_id])
    referred_user = relationship("User", foreign_keys=[referred_user_id])

class ServiceFortuneCost(Base):
    """5. 서비스별 행운 비용"""
    __tablename__ = "service_fortune_costs"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(50), unique=True, nullable=False)  # 'basic_saju', 'love_match', etc
    fortune_cost = Column(Integer, nullable=False)  # 행운 포인트 비용
    description = Column(String(255))  # 서비스 설명
    
    # 추가 설정
    is_active = Column(Boolean, default=True)
    min_user_level = Column(Integer, default=0)  # 최소 사용자 레벨
    max_daily_uses = Column(Integer, nullable=True)  # 일일 최대 사용 횟수 (None이면 무제한)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class FortunePackage(Base):
    """6. 행운 충전 패키지"""
    __tablename__ = "fortune_packages"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 패키지명 (예: "행운 스타터", "행운 프리미엄")
    description = Column(Text)  # 패키지 설명
    
    # 패키지 구성
    fortune_points = Column(Integer, nullable=False)  # 기본 포인트
    bonus_points = Column(Integer, default=0)  # 보너스 포인트
    price = Column(Integer, nullable=False)  # 가격 (원)
    
    # 유효성
    expires_days = Column(Integer, default=365)  # 포인트 유효기간 (일)
    
    # 판매 설정
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)  # 추천 패키지
    discount_rate = Column(Numeric(5, 2), default=0.00)  # 할인율
    sort_order = Column(Integer, default=0)  # 정렬 순서
    
    # 제한 설정
    max_purchase_per_user = Column(Integer, nullable=True)  # 사용자당 최대 구매 수
    min_subscription_level = Column(String(20), nullable=True)  # 최소 구독 등급
    
    created_at = Column(DateTime, default=datetime.now)

class UserReview(Base):
    """7. 리뷰 시스템"""
    __tablename__ = "user_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # 리뷰 내용
    rating = Column(Integer, nullable=False)  # 평점 (1-5)
    title = Column(String(200), nullable=True)  # 리뷰 제목
    content = Column(Text, nullable=False)  # 리뷰 내용
    
    # 추가 평가 항목
    accuracy_rating = Column(Integer, nullable=True)  # 정확도 평점 (1-5)
    satisfaction_rating = Column(Integer, nullable=True)  # 만족도 평점 (1-5)
    recommendation_rating = Column(Integer, nullable=True)  # 추천도 평점 (1-5)
    
    # 상태 관리
    is_verified = Column(Boolean, default=False)  # 인증된 리뷰 (실제 구매자)
    is_featured = Column(Boolean, default=False)  # 추천 리뷰
    is_visible = Column(Boolean, default=True)  # 노출 여부
    
    # 유용성
    helpful_count = Column(Integer, default=0)  # 도움 되었다 수
    report_count = Column(Integer, default=0)  # 신고 수
    
    # 리뷰어 정보 (익명화)
    reviewer_age_group = Column(String(10), nullable=True)  # '20대', '30대' 등
    reviewer_gender = Column(String(10), nullable=True)  # '남성', '여성'
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")
    order = relationship("Order")
    
    # 인덱스
    __table_args__ = (
        Index('idx_review_product_rating', 'product_id', 'rating'),
        Index('idx_review_user_product', 'user_id', 'product_id'),
        UniqueConstraint('user_id', 'product_id', 'order_id', name='unique_user_product_order_review'),
    )

class DailyAttendance(Base):
    """8. 출석 체크"""
    __tablename__ = "daily_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("blog_users.id"), nullable=False)
    attendance_date = Column(Date, nullable=False)  # 출석 날짜
    
    # 출석 보상
    reward_points = Column(Integer, default=10)  # 지급된 포인트
    bonus_multiplier = Column(Numeric(3, 2), default=1.00)  # 보너스 배수 (연속 출석시)
    consecutive_days = Column(Integer, default=1)  # 연속 출석 일수
    
    # 특별 이벤트
    is_special_day = Column(Boolean, default=False)  # 특별한 날 (이벤트 등)
    special_reward = Column(Integer, default=0)  # 특별 보상
    event_name = Column(String(100), nullable=True)  # 이벤트명
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 관계
    user = relationship("User", back_populates="attendance_records")
    
    # 인덱스
    __table_args__ = (
        Index('idx_attendance_user_date', 'user_id', 'attendance_date'),
        UniqueConstraint('user_id', 'attendance_date', name='unique_user_daily_attendance'),
    )

################################################################################
# 🔄 기존 사주 관련 모델들 (유지)
################################################################################

class SajuUser(Base):
    """사주 사용자 테이블 - 기존 유지"""
    __tablename__ = "saju_users"
    __table_args__ = (
        UniqueConstraint("user_id", "saju_key", name="uniq_user_saju"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    birthdate = Column(String(20))
    birthhour = Column(Integer)
    gender = Column(String(10))
    calendar = Column(Enum("SOL", "LUN", name="calendar_enum"), default="SOL")
    timezone = Column(String(50), default="Asia/Seoul")
    birth_date_original = Column(Date)
    birth_date_converted = Column(Date)
    session_token = Column(String(255), unique=True)
    first_visit = Column(DateTime, default=datetime.now)
    last_visit = Column(DateTime, default=datetime.now)
    visit_count = Column(Integer, default=1)
    saju_key = Column(String(120), nullable=True)
    calculated_pillars = Column(JSON, nullable=True)
    elem_dict_kr = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey("blog_users.id"))
    
    user = relationship("User")

class SajuAnalysisCache(Base):
    """사주 분석 캐시 테이블 - 기존 유지"""
    __tablename__ = "saju_analysis_cache"

    id = Column(Integer, primary_key=True)
    saju_key = Column(String(100), unique=True, index=True)
    analysis_preview = Column(Text, nullable=True)
    analysis_full = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    orders = relationship("Order", back_populates="analysis_cache")

# 기타 기존 모델들 (Category, Post 등)도 유지...
class Category(Base):
    __tablename__ = "blog_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    posts = relationship("Post", back_populates="category")

class Post(Base):
    __tablename__ = "blog_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, index=True)
    content = Column(Text)
    excerpt = Column(String(500))
    featured_image = Column(String(500))
    author_id = Column(Integer, ForeignKey("blog_users.id"))
    category_id = Column(Integer, ForeignKey("blog_categories.id"))
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")

################################################################################
# 🔧 유틸리티 함수들
################################################################################

def get_user_subscription_level(user_id: int, db) -> str:
    """사용자의 현재 구독 등급 반환"""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active"
    ).first()
    
    return subscription.plan_type if subscription else "free"

def get_user_fortune_balance(user_id: int, db) -> int:
    """사용자의 현재 행운 포인트 잔액 반환"""
    fortune_point = db.query(UserFortunePoint).filter(
        UserFortunePoint.user_id == user_id
    ).first()
    
    return fortune_point.points if fortune_point else 0

def create_referral_code(user_id: int) -> str:
    """추천 코드 생성"""
    import random
    import string
    
    base = f"REF{user_id:04d}"
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{base}{suffix}"