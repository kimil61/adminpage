#!/usr/bin/env python3
"""
운세 커머스 플랫폼 데이터베이스 초기화 및 샘플 데이터 생성
기존 setup_db.py를 새로운 모델에 맞게 완전 리뉴얼
"""

from app.database import engine, SessionLocal
from app.models import *
from app.utils import hash_password
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_database():
    """데이터베이스 테이블 생성 및 초기 데이터 설정"""
    
    print("🚀 Fortune Commerce 데이터베이스 초기화 시작...")
    print("=" * 60)
    
    # 1. 테이블 생성
    print("🗄️ 데이터베이스 테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    print("✅ 모든 테이블 생성 완료")
    
    db = SessionLocal()
    
    try:
        # 2. 기본 사용자 생성
        create_users(db)
        
        # 3. 카테고리 생성
        create_categories(db)
        
        # 4. 구독 플랜 및 샘플 구독자 생성
        create_subscriptions(db)
        
        # 5. 상품 및 사주 상품 생성
        create_products(db)
        
        # 6. 행운 충전 패키지 생성
        create_fortune_packages(db)
        
        # 7. 서비스별 행운 비용 설정
        create_service_costs(db)
        
        # 8. 행운 포인트 초기 설정
        setup_initial_fortune_points(db)
        
        # 9. 추천 코드 생성
        create_referral_codes(db)
        
        # 10. 샘플 포스트 생성
        create_sample_posts(db)
        
        # 11. 샘플 리뷰 생성
        create_sample_reviews(db)
        
        db.commit()
        print_success_summary()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_users(db):
    """기본 사용자 계정 생성"""
    print("\n👥 사용자 계정 생성 중...")
    
    users_data = [
        {
            "username": "admin",
            "email": "admin@fortune.com",
            "password": "admin123",
            "is_admin": True,
            "points": 1000
        },
        {
            "username": "user1",
            "email": "user1@test.com", 
            "password": "user123",
            "is_admin": False,
            "points": 500
        },
        {
            "username": "user2",
            "email": "user2@test.com",
            "password": "user123", 
            "is_admin": False,
            "points": 300
        },
        {
            "username": "premium_user",
            "email": "premium@test.com",
            "password": "user123",
            "is_admin": False,
            "points": 800
        }
    ]
    
    for user_data in users_data:
        existing_user = db.query(User).filter(User.username == user_data["username"]).first()
        if not existing_user:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                password=hash_password(user_data["password"]),
                is_admin=user_data["is_admin"],
                points=user_data["points"]
            )
            db.add(user)
            print(f"   ✅ {user_data['username']} 계정 생성됨")

def create_categories(db):
    """블로그 카테고리 생성"""
    print("\n📂 카테고리 생성 중...")
    
    categories_data = [
        {"name": "사주운세", "slug": "saju", "description": "사주팔자 관련 포스트"},
        {"name": "타로", "slug": "tarot", "description": "타로 카드 관련 포스트"},
        {"name": "풍수", "slug": "fengshui", "description": "풍수지리 관련 포스트"},
        {"name": "공지사항", "slug": "notice", "description": "서비스 공지사항"},
    ]
    
    for cat_data in categories_data:
        existing_cat = db.query(Category).filter(Category.slug == cat_data["slug"]).first()
        if not existing_cat:
            category = Category(**cat_data)
            db.add(category)
            print(f"   ✅ {cat_data['name']} 카테고리 생성됨")

def create_subscriptions(db):
    """구독 플랜 및 샘플 구독자 생성"""
    print("\n💎 구독 서비스 설정 중...")
    
    # 프리미엄 사용자를 구독자로 설정
    premium_user = db.query(User).filter(User.username == "premium_user").first()
    if premium_user:
        existing_sub = db.query(Subscription).filter(Subscription.user_id == premium_user.id).first()
        if not existing_sub:
            subscription = Subscription(
                user_id=premium_user.id,
                plan_type="premium",
                status="active",
                monthly_fortune_points=300,
                discount_rate=Decimal("15.00"),
                priority_support=True,
                exclusive_content=True,
                monthly_price=9900,
                next_billing_date=date.today() + timedelta(days=30),
                last_billing_date=date.today(),
                auto_renewal=True
            )
            db.add(subscription)
            print("   ✅ 프리미엄 구독 샘플 생성됨")

def create_products(db):
    """상품 및 사주 상품 생성"""
    print("\n🛒 상품 생성 중...")
    
    # 기본 상품들
    products_data = [
        {
            "name": "무료 기본 운세",
            "description": "간단한 사주 기본 분석 서비스",
            "price": 0,
            "code": "free_basic",
            "category": "saju",
            "pricing_type": "one_time",
            "slug": "free-basic-fortune",
            "fortune_cost": 0,
            "features": ["기본 사주팔자", "성격 분석", "2025년 운세"],
            "tags": ["무료", "기본", "입문"],
            "difficulty_level": 1,
            "estimated_time": 3,
            "is_featured": True
        },
        {
            "name": "행운 포인트 기본 분석", 
            "description": "행운 포인트로만 이용 가능한 상세 분석",
            "price": 0,
            "code": "point_basic",
            "category": "saju",
            "pricing_type": "one_time", 
            "slug": "point-basic-analysis",
            "fortune_cost": 50,
            "features": ["상세 사주팔자", "성격 분석", "연간 운세", "행운 키워드"],
            "tags": ["포인트", "상세", "추천"],
            "difficulty_level": 2,
            "estimated_time": 5,
            "is_featured": True
        },
        {
            "name": "프리미엄 사주 리포트",
            "description": "AI 심층 분석 + PDF 리포트 제공",
            "price": 1900,
            "code": "premium_saju",
            "category": "saju", 
            "pricing_type": "one_time",
            "slug": "premium-saju-report",
            "fortune_cost": 0,
            "features": ["전문가급 심층 분석", "PDF 리포트", "월별 운세", "궁합 분석"],
            "tags": ["프리미엄", "PDF", "심층분석"],
            "difficulty_level": 5,
            "estimated_time": 10,
            "is_featured": True
        },
        {
            "name": "연애운 특화 분석",
            "description": "연애와 결혼운에 특화된 맞춤 분석",
            "price": 1500,
            "code": "love_fortune",
            "category": "saju",
            "pricing_type": "one_time",
            "slug": "love-fortune-analysis", 
            "fortune_cost": 80,
            "features": ["연애운 집중 분석", "이상형 분석", "궁합 가이드"],
            "tags": ["연애", "결혼", "궁합"],
            "difficulty_level": 3,
            "estimated_time": 7
        },
        {
            "name": "직업운 Career 분석",
            "description": "직업과 사업운에 특화된 전문 분석",
            "price": 1800,
            "code": "career_fortune",
            "category": "saju",
            "pricing_type": "one_time",
            "slug": "career-fortune-analysis",
            "fortune_cost": 100, 
            "features": ["직업운 분석", "사업운 분석", "재물운 분석", "성공 전략"],
            "tags": ["직업", "사업", "재물운"],
            "difficulty_level": 4,
            "estimated_time": 8
        }
    ]
    
    for product_data in products_data:
        existing_product = db.query(Product).filter(Product.code == product_data["code"]).first()
        if not existing_product:
            product = Product(**product_data)
            db.add(product)
            db.flush()  # ID를 얻기 위해
            
            # 사주 전용 상품 설정 추가
            saju_product_data = {
                "base_product_id": product.id,
                "analysis_type": get_analysis_type(product_data["code"]),
                "ai_model": "gpt-4o",
                "prompt_version": "v3",
                "includes_yearly_fortune": True,
                "includes_monthly_fortune": product_data["difficulty_level"] >= 3,
                "includes_compatibility": "love" in product_data["code"],
                "includes_lucky_items": True,
                "output_format": {"html": True, "pdf": product_data["price"] > 0},
                "max_pages": product_data["difficulty_level"] * 2,
                "template_style": "modern",
                "min_subscription_level": "premium" if product_data["difficulty_level"] >= 4 else None,
                "fortune_point_cost": product_data["fortune_cost"]
            }
            
            saju_product = SajuProduct(**saju_product_data)
            db.add(saju_product)
            
            print(f"   ✅ {product_data['name']} 상품 생성됨")

def get_analysis_type(code):
    """상품 코드에 따른 분석 타입 반환"""
    if "free" in code or "basic" in code:
        return "basic"
    elif "love" in code:
        return "love"  
    elif "career" in code:
        return "career"
    else:
        return "detailed"

def create_fortune_packages(db):
    """행운 충전 패키지 생성"""
    print("\n⭐ 행운 충전 패키지 생성 중...")
    
    packages_data = [
        {
            "name": "행운 스타터",
            "description": "처음 시작하는 분들을 위한 기본 패키지",
            "fortune_points": 100,
            "bonus_points": 20,
            "price": 1000,
            "expires_days": 90,
            "is_featured": True,
            "sort_order": 1
        },
        {
            "name": "행운 베이직",
            "description": "가장 인기 있는 기본 패키지",
            "fortune_points": 300, 
            "bonus_points": 80,
            "price": 2900,
            "expires_days": 180,
            "is_featured": True,
            "sort_order": 2,
            "discount_rate": Decimal("5.00")
        },
        {
            "name": "행운 프리미엄",
            "description": "풍부한 혜택의 프리미엄 패키지",
            "fortune_points": 600,
            "bonus_points": 200,
            "price": 5500,
            "expires_days": 365,
            "is_featured": True,
            "sort_order": 3,
            "discount_rate": Decimal("10.00")
        },
        {
            "name": "행운 VIP",
            "description": "최고급 VIP 전용 패키지",
            "fortune_points": 1200,
            "bonus_points": 500,
            "price": 9900,
            "expires_days": 365,
            "sort_order": 4,
            "discount_rate": Decimal("15.00"),
            "min_subscription_level": "premium"
        }
    ]
    
    for package_data in packages_data:
        existing_package = db.query(FortunePackage).filter(FortunePackage.name == package_data["name"]).first()
        if not existing_package:
            package = FortunePackage(**package_data)
            db.add(package)
            print(f"   ✅ {package_data['name']} 패키지 생성됨")

def create_service_costs(db):
    """서비스별 행운 비용 설정"""
    print("\n💰 서비스별 행운 비용 설정 중...")
    
    service_costs_data = [
        {
            "service_name": "free_basic",
            "fortune_cost": 0,
            "description": "무료 기본 사주 분석",
            "max_daily_uses": 3
        },
        {
            "service_name": "point_basic", 
            "fortune_cost": 50,
            "description": "포인트 기본 사주 분석",
            "max_daily_uses": 10
        },
        {
            "service_name": "love_match",
            "fortune_cost": 80,
            "description": "연애운 궁합 분석",
            "max_daily_uses": 5
        },
        {
            "service_name": "career_analysis",
            "fortune_cost": 100,
            "description": "직업운 분석",
            "max_daily_uses": 3
        },
        {
            "service_name": "yearly_fortune",
            "fortune_cost": 120,
            "description": "연간 종합 운세",
            "max_daily_uses": 2
        },
        {
            "service_name": "naming_service",
            "fortune_cost": 150,
            "description": "작명 서비스",
            "max_daily_uses": 1
        }
    ]
    
    for cost_data in service_costs_data:
        existing_cost = db.query(ServiceFortuneCost).filter(ServiceFortuneCost.service_name == cost_data["service_name"]).first()
        if not existing_cost:
            service_cost = ServiceFortuneCost(**cost_data)
            db.add(service_cost)
            print(f"   ✅ {cost_data['service_name']} 비용 설정됨")

def setup_initial_fortune_points(db):
    """사용자별 행운 포인트 초기 설정"""
    print("\n🎲 행운 포인트 초기 설정 중...")
    
    users = db.query(User).all()
    
    for user in users:
        existing_fortune = db.query(UserFortunePoint).filter(UserFortunePoint.user_id == user.id).first()
        if not existing_fortune:
            # 사용자별 초기 포인트 설정
            initial_points = 200 if user.username == "admin" else 100
            if user.username == "premium_user":
                initial_points = 500  # 프리미엄 사용자는 더 많이
            
            fortune_point = UserFortunePoint(
                user_id=user.id,
                points=initial_points,
                total_earned=initial_points,
                total_spent=0
            )
            db.add(fortune_point)
            
            # 초기 적립 거래 기록
            transaction = FortuneTransaction(
                user_id=user.id,
                transaction_type="earn",
                amount=initial_points,
                balance_after=initial_points,
                source="initial_bonus",
                description="회원가입 축하 보너스",
                expires_at=datetime.now() + timedelta(days=365)
            )
            db.add(transaction)
            
            print(f"   ✅ {user.username}: {initial_points} 포인트 지급")

def create_referral_codes(db):
    """추천 코드 생성"""
    print("\n🔗 추천 코드 생성 중...")
    
    users = db.query(User).filter(User.is_admin == False).all()
    
    for user in users:
        existing_referral = db.query(ReferralReward).filter(ReferralReward.referrer_user_id == user.id).first()
        if not existing_referral:
            from app.models import create_referral_code
            
            referral = ReferralReward(
                referrer_user_id=user.id,
                referral_code=create_referral_code(user.id),
                referral_type="signup",
                reward_type="fortune_points",
                reward_amount=100,
                reward_description="친구 추천 보상",
                status="pending"
            )
            db.add(referral)
            print(f"   ✅ {user.username}: {referral.referral_code}")

def create_sample_posts(db):
    """샘플 포스트 생성"""
    print("\n📝 샘플 포스트 생성 중...")
    
    admin = db.query(User).filter(User.username == "admin").first()
    saju_category = db.query(Category).filter(Category.slug == "saju").first()
    notice_category = db.query(Category).filter(Category.slug == "notice").first()
    
    posts_data = [
        {
            "title": "🎉 Fortune Commerce 오픈 기념 이벤트",
            "slug": "grand-opening-event",
            "content": """
            <h2>🎉 Fortune Commerce 오픈을 축하합니다!</h2>
            <p>새로운 운세 서비스 플랫폼이 드디어 오픈했습니다. 
            행운 포인트 시스템과 구독 서비스로 더욱 편리하게 운세를 확인하세요!</p>
            
            <h3>🎁 오픈 기념 혜택</h3>
            <ul>
                <li>신규 가입시 행운 포인트 100개 증정</li>
                <li>첫 구매시 20% 할인</li>
                <li>프리미엄 구독 첫 달 50% 할인</li>
            </ul>
            """,
            "excerpt": "Fortune Commerce 오픈 기념 특별 혜택을 확인하세요!",
            "category_id": notice_category.id if notice_category else None,
            "author_id": admin.id,
            "is_published": True
        },
        {
            "title": "2025년 을사년 운세 미리보기",
            "slug": "2025-yearly-fortune-preview", 
            "content": """
            <h2>🐍 2025년 을사년 전체 운세 흐름</h2>
            <p>뱀의 해인 2025년은 변화와 성장의 한 해가 될 것으로 예상됩니다.</p>
            
            <h3>2025년 주요 특징</h3>
            <ul>
                <li><strong>목화 기운 강화:</strong> 성장과 발전의 에너지</li>
                <li><strong>변화의 시기:</strong> 새로운 기회와 도전</li>
                <li><strong>관계 중시:</strong> 인간관계의 중요성 부각</li>
            </ul>
            """,
            "excerpt": "2025년 을사년의 전체적인 운세 흐름을 미리 살펴보세요.",
            "category_id": saju_category.id if saju_category else None,
            "author_id": admin.id,
            "is_published": True
        }
    ]
    
    for post_data in posts_data:
        existing_post = db.query(Post).filter(Post.slug == post_data["slug"]).first()
        if not existing_post:
            post = Post(**post_data)
            db.add(post)
            print(f"   ✅ {post_data['title']} 포스트 생성됨")

def create_sample_reviews(db):
    """샘플 리뷰 생성"""
    print("\n⭐ 샘플 리뷰 생성 중...")
    
    user1 = db.query(User).filter(User.username == "user1").first()
    user2 = db.query(User).filter(User.username == "user2").first()
    premium_product = db.query(Product).filter(Product.code == "premium_saju").first()
    basic_product = db.query(Product).filter(Product.code == "point_basic").first()
    
    reviews_data = [
        {
            "user_id": user1.id if user1 else None,
            "product_id": premium_product.id if premium_product else None,
            "rating": 5,
            "title": "정말 정확하고 상세해요!",
            "content": "다른 곳에서는 뻔한 이야기만 하는데, 여기는 정말 나만의 구체적인 조언을 줘서 놀랐어요. PDF 리포트도 깔끔하고 보관하기 좋네요.",
            "accuracy_rating": 5,
            "satisfaction_rating": 5,
            "recommendation_rating": 5,
            "is_verified": True,
            "is_featured": True,
            "reviewer_age_group": "30대",
            "reviewer_gender": "여성"
        },
        {
            "user_id": user2.id if user2 else None,
            "product_id": basic_product.id if basic_product else None,  
            "rating": 4,
            "title": "포인트로 이용할 수 있어서 좋아요",
            "content": "행운 포인트로 이용할 수 있어서 부담 없이 자주 확인할 수 있어요. 분석 내용도 생각보다 상세합니다.",
            "accuracy_rating": 4,
            "satisfaction_rating": 4,
            "recommendation_rating": 4,
            "is_verified": True,
            "reviewer_age_group": "20대",
            "reviewer_gender": "남성"
        }
    ]
    
    for review_data in reviews_data:
        if review_data["user_id"] and review_data["product_id"]:
            existing_review = db.query(UserReview).filter(
                UserReview.user_id == review_data["user_id"],
                UserReview.product_id == review_data["product_id"]
            ).first()
            
            if not existing_review:
                review = UserReview(**review_data)
                db.add(review)
                print(f"   ✅ {review_data['title']} 리뷰 생성됨")

def print_success_summary():
    """설정 완료 요약 출력"""
    print("\n" + "=" * 60)
    print("🎉 Fortune Commerce 데이터베이스 초기화 완료!")
    print("=" * 60)
    
    print("\n🎯 접속 정보:")
    print("   🏠 홈페이지: http://localhost:8000")
    print("   👑 관리자: http://localhost:8000/admin")
    print("   📚 API 문서: http://localhost:8000/docs")
    
    print("\n🔑 로그인 계정:")
    print("   👑 관리자: admin / admin123")
    print("   👤 일반 사용자: user1 / user123")
    print("   👤 일반 사용자: user2 / user123") 
    print("   💎 프리미엄 사용자: premium_user / user123")
    
    print("\n💰 초기 행운 포인트:")
    print("   👑 admin: 200 포인트")
    print("   👤 user1, user2: 100 포인트")
    print("   💎 premium_user: 500 포인트")
    
    print("\n🛒 생성된 상품:")
    print("   • 무료 기본 운세 (0원, 0포인트)")
    print("   • 행운 포인트 기본 분석 (0원, 50포인트)")
    print("   • 프리미엄 사주 리포트 (1,900원)")
    print("   • 연애운 특화 분석 (1,500원, 80포인트)")
    print("   • 직업운 Career 분석 (1,800원, 100포인트)")
    
    print("\n⭐ 행운 충전 패키지:")
    print("   • 행운 스타터: 100+20포인트 (1,000원)")
    print("   • 행운 베이직: 300+80포인트 (2,900원)")
    print("   • 행운 프리미엄: 600+200포인트 (5,500원)")
    print("   • 행운 VIP: 1200+500포인트 (9,900원)")
    
    print("\n💎 구독 서비스:")
    print("   • premium_user는 프리미엄 구독 활성화됨")
    print("   • 월 300포인트 지급, 15% 할인 혜택")
    
    print("\n📝 다음 단계:")
    print("   1. 서버 실행: python run.py")
    print("   2. 관리자 페이지에서 추가 설정")
    print("   3. 상품별 상세 설정 조정")
    print("   4. 결제 시스템 연동 확인")
    
    print("\n🚀 개발 시작 준비 완료!")

if __name__ == "__main__":
    setup_database()