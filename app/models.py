from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "blog_users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="author")

class Category(Base):
    __tablename__ = "blog_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    views = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    
    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")

class Media(Base):
    __tablename__ = "blog_media"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255))
    file_type = Column(String(50))
    file_size = Column(Integer)
    file_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("blog_users.id"))
    user = relationship("User")


class InPost(Base):
    """지식in에서 수집된 포스트"""

    __tablename__ = "in_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    gen_content1 = Column(Text)
    gen_content2 = Column(Text)
    gen_content3 = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FilteredContent(Base):
    """필터링된 원본/치환 콘텐츠 기록"""

    __tablename__ = "filtered_contents"

    id = Column(Integer, primary_key=True, index=True)
    in_posts_id = Column(Integer, index=True, nullable=True)
    filter_result = Column(Text, nullable=True)
    confidence_score = Column(Integer, nullable=True)  # MySQL float → use Float if high precision needed
    reasoning = Column(Text, nullable=True)
    suitable_for_blog = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# app/models.py에 추가할 사주 관련 모델들

class SajuUser(Base):
    """사주 사용자 테이블"""
    __tablename__ = "saju_users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    birthdate = Column(String(20))  # YYYY-MM-DD 형식
    birthhour = Column(Integer)
    gender = Column(String(10))
    session_token = Column(String(255), unique=True)
    first_visit = Column(DateTime, default=datetime.utcnow)
    last_visit = Column(DateTime, default=datetime.utcnow)
    visit_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class SajuFortune(Base):
    """사주 운세 결과 테이블"""
    __tablename__ = "saju_fortunes"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), index=True)
    menu = Column(String(50))  # 'basic', 'saju', 'love', etc.
    date = Column(String(20))  # YYYY-MM-DD 형식
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class SajuInterpretation(Base):
    """사주 해석 데이터 테이블"""
    __tablename__ = "saju_interpretations"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Integer)
    ilju = Column(String(10))  # 일주 (예: 甲子)
    cn = Column(Text)  # 중국어 해석
    kr = Column(Text)  # 한국어 해석
    en = Column(Text)  # 영어 해석
    created_at = Column(DateTime, default=datetime.utcnow)

class MatchReport(Base):
    """궁합 리포트 캐시 테이블"""
    __tablename__ = "match_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True)  # 해시키
    report = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    

# 사주 위키 콘텐츠 테이블
class SajuWikiContent(Base):
    """사주 위키 콘텐츠 테이블"""

    __tablename__ = "saju_wiki_contents"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(Text)
    line_number = Column(Integer)
    content = Column(Text)
    kr_literal = Column(Text)
    kr_explained = Column(Text)