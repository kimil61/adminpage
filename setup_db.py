#!/usr/bin/env python3
"""
데이터베이스 초기화 및 샘플 데이터 생성
"""

from app.database import engine, SessionLocal
from app.models import Base, User, Category, Post
from app.utils import hash_password
from datetime import datetime

def setup_database():
    """데이터베이스 테이블 생성 및 초기 데이터 설정"""
    
    print("🗄️ 데이터베이스 테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 관리자 계정 생성
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@example.com",
                password=hash_password("admin123"),
                is_admin=True
            )
            db.add(admin)
            print("👑 관리자 계정 생성됨 (admin/admin123)")
        
        # 샘플 사용자 생성
        user = db.query(User).filter(User.username == "user").first()
        if not user:
            user = User(
                username="user",
                email="user@example.com",
                password=hash_password("user123"),
                is_admin=False
            )
            db.add(user)
            print("👤 일반 사용자 계정 생성됨 (user/user123)")
        
        # 기본 카테고리 생성
        categories_data = [
            {"name": "기술", "slug": "tech", "description": "기술 관련 포스트"},
            {"name": "일상", "slug": "daily", "description": "일상 이야기"},
            {"name": "여행", "slug": "travel", "description": "여행 후기"},
        ]
        
        for cat_data in categories_data:
            category = db.query(Category).filter(Category.slug == cat_data["slug"]).first()
            if not category:
                category = Category(**cat_data)
                db.add(category)
        
        db.commit()
        
        # 샘플 포스트 생성
        tech_category = db.query(Category).filter(Category.slug == "tech").first()
        daily_category = db.query(Category).filter(Category.slug == "daily").first()
        
        sample_posts = [
            {
                "title": "FastAPI + Jinja2로 웹사이트 만들기",
                "slug": "fastapi-jinja2-website",
                "content": """
                <h2>FastAPI와 Jinja2를 사용한 웹사이트 구축</h2>
                <p>이 포스트에서는 FastAPI와 Jinja2 템플릿 엔진을 사용하여 완전한 웹사이트를 구축하는 방법을 알아보겠습니다.</p>
                
                <h3>주요 특징</h3>
                <ul>
                    <li>빠른 성능의 FastAPI 백엔드</li>
                    <li>서버사이드 렌더링으로 SEO 최적화</li>
                    <li>Bootstrap 5를 활용한 반응형 디자인</li>
                    <li>관리자 페이지로 쉬운 콘텐츠 관리</li>
                </ul>
                
                <p>이 템플릿을 사용하면 개인 블로그부터 회사 홈페이지까지 다양한 웹사이트를 빠르게 구축할 수 있습니다.</p>
                """,
                "excerpt": "FastAPI와 Jinja2를 사용하여 완전한 웹사이트를 구축하는 방법을 알아봅시다.",
                "category_id": tech_category.id if tech_category else None,
                "author_id": admin.id,
                "is_published": True,
                "published_at": datetime.utcnow()
            },
            {
                "title": "웹사이트 개발 후기",
                "slug": "website-development-review",
                "content": """
                <h2>웹사이트 개발을 마치며</h2>
                <p>드디어 FastAPI + Jinja2 기반의 웹사이트 템플릿이 완성되었습니다!</p>
                
                <h3>개발 과정에서 배운 것들</h3>
                <p>이번 프로젝트를 통해 많은 것을 배울 수 있었습니다:</p>
                <ul>
                    <li>FastAPI의 강력함과 유연성</li>
                    <li>Jinja2 템플릿의 편리함</li>
                    <li>Bootstrap 5의 현대적인 디자인</li>
                </ul>
                
                <p>앞으로 이 템플릿을 기반으로 더 많은 기능을 추가해나갈 예정입니다.</p>
                """,
                "excerpt": "웹사이트 개발을 마치고 느낀 점들을 공유합니다.",
                "category_id": daily_category.id if daily_category else None,
                "author_id": admin.id,
                "is_published": True,
                "published_at": datetime.utcnow()
            }
        ]
        
        for post_data in sample_posts:
            existing_post = db.query(Post).filter(Post.slug == post_data["slug"]).first()
            if not existing_post:
                post = Post(**post_data)
                db.add(post)
        
        db.commit()
        print("📝 샘플 포스트 생성됨")
        
        print("\n✅ 데이터베이스 초기화 완료!")
        print("\n🎯 접속 정보:")
        print("   홈페이지: http://localhost:8000")
        print("   관리자: http://localhost:8000/admin")
        print("   로그인: admin / admin123")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    setup_database()
