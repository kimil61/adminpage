from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/website_db")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=os.getenv("DEBUG", "False").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_transaction():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_posts_with_relations(db, limit: int = 10):
    from app.models import Post
    return (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(Post.is_published == True, Post.is_deleted == False)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )


def get_paginated_posts(db, page: int = 1, per_page: int = 10):
    from app.models import Post
    offset = (page - 1) * per_page

    total_query = db.query(func.count(Post.id)).filter(
        Post.is_published == True, Post.is_deleted == False
    )
    total = total_query.scalar()

    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.category))
        .filter(Post.is_published == True, Post.is_deleted == False)
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    pages = (total + per_page - 1) // per_page

    return {
        "posts": posts,
        "total": total,
        "pages": pages,
        "current_page": page,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


def get_active_posts(db):
    from app.models import Post
    return db.query(Post).filter(Post.is_deleted == False)
