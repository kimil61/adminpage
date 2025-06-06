#!/bin/bash

# FastAPI + Jinja2 웹사이트 프로젝트 생성 스크립트
echo "🚀 FastAPI + Jinja2 웹사이트 프로젝트 생성을 시작합니다..."

# 1. 기본 폴더 구조 생성
echo "📁 폴더 구조 생성 중..."
mkdir -p app/routers
mkdir -p templates/auth
mkdir -p templates/blog
mkdir -p templates/admin
mkdir -p templates/errors
mkdir -p static/css
mkdir -p static/js
mkdir -p static/uploads

# 2. requirements.txt 생성
echo "📦 requirements.txt 생성 중..."
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
jinja2==3.1.2
python-multipart==0.0.6
sqlalchemy==2.0.23
pymysql==1.1.0
python-dotenv==1.0.0
wtforms==3.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
aiofiles==23.2.1
pillow==10.1.0
itsdangerous==2.1.2
starlette==0.27.0
EOF

# 3. .env.example 생성
echo "⚙️ 환경설정 파일 생성 중..."
cat > .env.example << 'EOF'
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/website_db
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=True
UPLOAD_DIR=static/uploads
MAX_UPLOAD_SIZE=5242880
EOF

# 4. .env 파일 생성 (개발용)
cp .env.example .env

# 5. app/__init__.py 생성
touch app/__init__.py
touch app/routers/__init__.py

# 6. app/database.py 생성
echo "🗄️ 데이터베이스 설정 파일 생성 중..."
cat > app/database.py << 'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/website_db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=os.getenv("DEBUG", "False").lower() == "true"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF

# 7. app/models.py 생성
echo "📋 데이터베이스 모델 생성 중..."
cat > app/models.py << 'EOF'
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="author")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="category")

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, index=True)
    content = Column(Text)
    excerpt = Column(String(500))
    featured_image = Column(String(500))
    
    author_id = Column(Integer, ForeignKey("users.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    
    is_published = Column(Boolean, default=False)
    views = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    
    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")

class Media(Base):
    __tablename__ = "media"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255))
    file_type = Column(String(50))
    file_size = Column(Integer)
    file_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")
EOF

# 8. app/forms.py 생성
echo "📝 폼 클래스 생성 중..."
cat > app/forms.py << 'EOF'
from wtforms import Form, StringField, TextAreaField, PasswordField, BooleanField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class LoginForm(Form):
    username = StringField('사용자명', validators=[
        DataRequired(message="사용자명을 입력해주세요.")
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message="비밀번호를 입력해주세요.")
    ])
    remember_me = BooleanField('로그인 상태 유지')

class RegisterForm(Form):
    username = StringField('사용자명', validators=[
        DataRequired(message="사용자명을 입력해주세요."),
        Length(min=3, max=50, message="사용자명은 3-50자여야 합니다.")
    ])
    email = StringField('이메일', validators=[
        DataRequired(message="이메일을 입력해주세요."),
        Email(message="올바른 이메일 형식이 아닙니다.")
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message="비밀번호를 입력해주세요."),
        Length(min=6, message="비밀번호는 최소 6자 이상이어야 합니다.")
    ])
    password_confirm = PasswordField('비밀번호 확인', validators=[
        DataRequired(message="비밀번호 확인을 입력해주세요."),
        EqualTo('password', message="비밀번호가 일치하지 않습니다.")
    ])

class PostForm(Form):
    title = StringField('제목', validators=[
        DataRequired(message="제목을 입력해주세요."),
        Length(max=200, message="제목은 200자 이하여야 합니다.")
    ])
    content = TextAreaField('내용', validators=[
        DataRequired(message="내용을 입력해주세요.")
    ])
    excerpt = TextAreaField('요약', validators=[
        Length(max=500, message="요약은 500자 이하여야 합니다.")
    ])
    category_id = SelectField('카테고리', coerce=int, validators=[Optional()])
    featured_image = FileField('대표 이미지')
    is_published = BooleanField('발행')

class CategoryForm(Form):
    name = StringField('카테고리명', validators=[
        DataRequired(message="카테고리명을 입력해주세요."),
        Length(max=100, message="카테고리명은 100자 이하여야 합니다.")
    ])
    slug = StringField('슬러그', validators=[
        DataRequired(message="슬러그를 입력해주세요."),
        Length(max=100, message="슬러그는 100자 이하여야 합니다.")
    ])
    description = TextAreaField('설명')
EOF

# 9. app/utils.py 생성
echo "🔧 유틸리티 함수 생성 중..."
cat > app/utils.py << 'EOF'
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
import os
import uuid
import re
from PIL import Image
import aiofiles

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")
    
    return user

def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user

def flash_message(request: Request, message: str, category: str = "info"):
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request):
    messages = request.session.pop("flash_messages", [])
    return [(msg["category"], msg["message"]) for msg in messages]

def create_slug(text: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9가-힣\s]', '', text)
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug.lower()

async def save_uploaded_file(file: UploadFile, folder: str = "uploads") -> str:
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise ValueError("허용되지 않는 파일 형식입니다.")
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    upload_dir = f"static/uploads/{folder}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, unique_filename)
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    if file_extension in {'.jpg', '.jpeg', '.png', '.webp'}:
        resize_image(file_path, max_width=800)
    
    return f"/static/uploads/{folder}/{unique_filename}"

def resize_image(image_path: str, max_width: int = 800):
    try:
        with Image.open(image_path) as img:
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                img.save(image_path, optimize=True, quality=85)
    except Exception:
        pass
EOF

# 10. 라우터 파일들 생성
echo "🛣️ 라우터 파일들 생성 중..."

# app/routers/auth.py
cat > app/routers/auth.py << 'EOF'
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.forms import LoginForm, RegisterForm
from app.utils import hash_password, verify_password, flash_message

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    form = LoginForm()
    return templates.TemplateResponse("auth/login.html", {
        "request": request, 
        "form": form
    })

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: bool = Form(False),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    
    if user and verify_password(password, user.password):
        request.session['user_id'] = user.id
        request.session['username'] = user.username
        request.session['is_admin'] = user.is_admin
        
        flash_message(request, "로그인되었습니다.", "success")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    else:
        flash_message(request, "사용자명 또는 비밀번호가 잘못되었습니다.", "error")
        form = LoginForm(request)
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "form": form
        })

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    form = RegisterForm()
    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "form": form
    })

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        flash_message(request, "이미 존재하는 사용자명 또는 이메일입니다.", "error")
    else:
        hashed_password = hash_password(password)
        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )
        db.add(new_user)
        db.commit()
        
        flash_message(request, "회원가입이 완료되었습니다. 로그인해주세요.", "success")
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    form = RegisterForm(request)
    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "form": form
    })

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    flash_message(request, "로그아웃되었습니다.", "info")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
EOF

# app/routers/blog.py
cat > app/routers/blog.py << 'EOF'
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, Category

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/blog", response_class=HTMLResponse)
async def blog_list(
    request: Request, 
    page: int = 1,
    db: Session = Depends(get_db)
):
    per_page = 6
    offset = (page - 1) * per_page
    
    posts = db.query(Post).filter(
        Post.is_published == True
    ).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    total = db.query(Post).filter(Post.is_published == True).count()
    pages = (total + per_page - 1) // per_page
    
    categories = db.query(Category).all()
    
    return templates.TemplateResponse("blog/list.html", {
        "request": request,
        "posts": posts,
        "categories": categories,
        "page": page,
        "pages": pages,
        "total": total
    })

@router.get("/blog/{post_id}", response_class=HTMLResponse)
async def blog_detail(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.is_published == True
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="포스트를 찾을 수 없습니다.")
    
    post.views += 1
    db.commit()
    
    related_posts = db.query(Post).filter(
        Post.category_id == post.category_id,
        Post.id != post.id,
        Post.is_published == True
    ).limit(3).all()
    
    return templates.TemplateResponse("blog/detail.html", {
        "request": request,
        "post": post,
        "related_posts": related_posts
    })

@router.get("/category/{category_slug}", response_class=HTMLResponse)
async def blog_category(
    request: Request,
    category_slug: str,
    page: int = 1,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.slug == category_slug).first()
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    
    per_page = 6
    offset = (page - 1) * per_page
    
    posts = db.query(Post).filter(
        Post.category_id == category.id,
        Post.is_published == True
    ).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    
    return templates.TemplateResponse("blog/category.html", {
        "request": request,
        "posts": posts,
        "category": category,
        "page": page
    })
EOF

# app/routers/admin.py
cat > app/routers/admin.py << 'EOF'
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Post, Category, Media
from app.forms import PostForm, CategoryForm
from app.utils import require_admin, save_uploaded_file, create_slug, flash_message
import os
from datetime import datetime

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_posts = db.query(Post).count()
    published_posts = db.query(Post).filter(Post.is_published == True).count()
    total_users = db.query(User).count()
    total_categories = db.query(Category).count()
    
    recent_posts = db.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_posts": total_posts,
        "published_posts": published_posts,
        "total_users": total_users,
        "total_categories": total_categories,
        "recent_posts": recent_posts
    })

@router.get("/posts", response_class=HTMLResponse)
async def admin_posts(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    per_page = 10
    offset = (page - 1) * per_page
    
    posts = db.query(Post).order_by(Post.created_at.desc()).offset(offset).limit(per_page).all()
    total = db.query(Post).count()
    pages = (total + per_page - 1) // per_page
    
    return templates.TemplateResponse("admin/posts.html", {
        "request": request,
        "posts": posts,
        "page": page,
        "pages": pages
    })

@router.get("/posts/create", response_class=HTMLResponse)
async def admin_create_post(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    form = PostForm()
    categories = db.query(Category).all()
    form.category_id.choices = [(0, '카테고리 선택')] + [(c.id, c.name) for c in categories]
    
    return templates.TemplateResponse("admin/post_form.html", {
        "request": request,
        "form": form,
        "action": "create"
    })

@router.post("/posts/create")
async def admin_create_post_submit(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    excerpt: str = Form(""),
    category_id: int = Form(0),
    is_published: bool = Form(False),
    featured_image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    slug = create_slug(title)
    
    existing_post = db.query(Post).filter(Post.slug == slug).first()
    if existing_post:
        slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    featured_image_url = None
    if featured_image and featured_image.filename:
        featured_image_url = await save_uploaded_file(featured_image, "posts")
    
    new_post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt,
        author_id=current_user.id,
        category_id=category_id if category_id > 0 else None,
        is_published=is_published,
        featured_image=featured_image_url,
        published_at=datetime.utcnow() if is_published else None
    )
    
    db.add(new_post)
    db.commit()
    
    flash_message(request, "포스트가 생성되었습니다.", "success")
    return RedirectResponse(url="/admin/posts", status_code=302)

@router.get("/categories", response_class=HTMLResponse)
async def admin_categories(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    categories = db.query(Category).all()
    form = CategoryForm()
    
    return templates.TemplateResponse("admin/categories.html", {
        "request": request,
        "categories": categories,
        "form": form
    })

@router.post("/categories")
async def admin_create_category(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing_category = db.query(Category).filter(
        (Category.name == name) | (Category.slug == slug)
    ).first()
    
    if existing_category:
        flash_message(request, "이미 존재하는 카테고리명 또는 슬러그입니다.", "error")
    else:
        new_category = Category(name=name, slug=slug, description=description)
        db.add(new_category)
        db.commit()
        flash_message(request, "카테고리가 생성되었습니다.", "success")
    
    return RedirectResponse(url="/admin/categories", status_code=302)
EOF

# 11. 메인 app/main.py 생성
echo "🎯 메인 애플리케이션 파일 생성 중..."
cat > app/main.py << 'EOF'
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models import Base, Post, Category
from app.routers import auth, blog, admin
from app.utils import get_flashed_messages
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="My Website", version="1.0.0")

app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "your-super-secret-key-change-this")
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

templates.env.globals.update({
    "get_flashed_messages": get_flashed_messages,
})

app.include_router(auth.router)
app.include_router(blog.router)
app.include_router(admin.router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    recent_posts = db.query(Post).filter(
        Post.is_published == True
    ).order_by(Post.created_at.desc()).limit(6).all()
    
    categories = db.query(Category).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_posts": recent_posts,
        "categories": categories
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
EOF

# 12. 관리자 계정 생성 스크립트
echo "👑 관리자 계정 생성 스크립트 생성 중..."
cat > create_admin.py << 'EOF'
from app.database import SessionLocal, engine
from app.models import Base, User
from app.utils import hash_password

def create_admin():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("❌ 관리자 계정이 이미 존재합니다.")
            return
        
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password=hash_password("admin123"),
            is_admin=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("✅ 관리자 계정이 생성되었습니다!")
        print("🔐 사용자명: admin")
        print("🔐 비밀번호: admin123")
        print("⚠️  로그인 후 반드시 비밀번호를 변경하세요!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
EOF

# 13. 기본 템플릿 파일들 생성
echo "🎨 템플릿 파일들 생성 중..."

# templates/base.html
cat > templates/base.html << 'EOF'
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}My Website{% endblock %}</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="/static/css/style.css" rel="stylesheet">
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">My Website</a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/">홈</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/blog">블로그</a>
                    </li>
                </ul>
                
                <ul class="navbar-nav">
                    {% if request.session.get('user_id') %}
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">
                                {{ request.session.get('username') }}
                            </a>
                            <ul class="dropdown-menu">
                                {% if request.session.get('is_admin') %}
                                <li><a class="dropdown-item" href="/admin/">관리자</a></li>
                                {% endif %}
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="/logout">로그아웃</a></li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="/login">로그인</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/register">회원가입</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>
    
    <main class="container mt-4">
        {% with messages = get_flashed_messages(request) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </main>
    
    <footer class="bg-dark text-light mt-5 py-4">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    <p>&copy; 2024 My Website. All rights reserved.</p>
                </div>
                <div class="col-md-6 text-end">
                    <p>Made with FastAPI + Jinja2</p>
                </div>
            </div>
        </div>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    {% block extra_scripts %}{% endblock %}
</body>
</html>
EOF

# templates/index.html
cat > templates/index.html << 'EOF'
{% extends "base.html" %}

{% block title %}홈 - My Website{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="jumbotron bg-primary text-white p-5 rounded mb-4">
            <h1 class="display-4">환영합니다!</h1>
            <p class="lead">FastAPI + Jinja2로 만든 웹사이트입니다.</p>
            <a class="btn btn-light btn-lg" href="/blog">블로그 보기</a>
        </div>
        
        <h2>최신 포스트</h2>
        <div class="row">
            {% for post in recent_posts %}
            <div class="col-md-6 mb-4">
                <div class="card h-100">
                    {% if post.featured_image %}
                    <img src="{{ post.featured_image }}" class="card-img-top" alt="{{ post.title }}" style="height: 200px; object-fit: cover;">
                    {% endif %}
                    <div class="card-body d-flex flex-column">
                        <h5 class="card-title">{{ post.title }}</h5>
                        <p class="card-text flex-grow-1">{{ post.excerpt or post.content[:100] }}...</p>
                        <a href="/blog/{{ post.id }}" class="btn btn-primary mt-auto">더 읽기</a>
                    </div>
                    <div class="card-footer text-muted">
                        {{ post.created_at.strftime('%Y-%m-%d') }} | {{ post.author.username }}
                    </div>
                </div>
            </div>
            {% endfor %}
            
            {% if not recent_posts %}
            <div class="col-12 text-center py-5">
                <h3 class="text-muted">아직 포스트가 없습니다</h3>
                <p class="text-muted">관리자 페이지에서 첫 번째 포스트를 작성해보세요!</p>
                {% if request.session.get('is_admin') %}
                <a href="/admin/posts/create" class="btn btn-primary">첫 포스트 작성하기</a>
                {% endif %}
            </div>
            {% endif %}
        </div>
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5>카테고리</h5>
            </div>
            <div class="list-group list-group-flush">
                {% for category in categories %}
                <a href="/category/{{ category.slug }}" 
                   class="list-group-item list-group-item-action">
                    {{ category.name }}
                </a>
                {% endfor %}
                
                {% if not categories %}
                <div class="list-group-item text-muted text-center">
                    카테고리가 없습니다
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# templates/auth/login.html
cat > templates/auth/login.html << 'EOF'
{% extends "base.html" %}

{% block title %}로그인 - My Website{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4>로그인</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">사용자명</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="password" class="form-label">비밀번호</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    
                    <div class="mb-3 form-check">
                        <input type="checkbox" class="form-check-input" id="remember_me" name="remember_me">
                        <label class="form-check-label" for="remember_me">로그인 상태 유지</label>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100">로그인</button>
                </form>
                
                <div class="text-center mt-3">
                    <p>계정이 없으신가요? <a href="/register">회원가입</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# templates/auth/register.html
cat > templates/auth/register.html << 'EOF'
{% extends "base.html" %}

{% block title %}회원가입 - My Website{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4>회원가입</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">사용자명</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="email" class="form-label">이메일</label>
                        <input type="email" class="form-control" id="email" name="email" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="password" class="form-label">비밀번호</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="password_confirm" class="form-label">비밀번호 확인</label>
                        <input type="password" class="form-control" id="password_confirm" name="password_confirm" required>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100">회원가입</button>
                </form>
                
                <div class="text-center mt-3">
                    <p>이미 계정이 있으신가요? <a href="/login">로그인</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# templates/blog/list.html
cat > templates/blog/list.html << 'EOF'
{% extends "base.html" %}

{% block title %}블로그 - My Website{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <h1 class="mb-4">블로그</h1>
        
        {% if posts %}
            <div class="row">
                {% for post in posts %}
                <div class="col-md-6 mb-4">
                    <div class="card h-100">
                        {% if post.featured_image %}
                        <img src="{{ post.featured_image }}" class="card-img-top" alt="{{ post.title }}" style="height: 200px; object-fit: cover;">
                        {% endif %}
                        <div class="card-body d-flex flex-column">
                            <h5 class="card-title">{{ post.title }}</h5>
                            <p class="card-text flex-grow-1">{{ post.excerpt or post.content[:150] }}...</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <a href="/blog/{{ post.id }}" class="btn btn-primary">더 읽기</a>
                                <small class="text-muted">조회 {{ post.views }}회</small>
                            </div>
                        </div>
                        <div class="card-footer text-muted">
                            <div class="d-flex justify-content-between">
                                <span>{{ post.created_at.strftime('%Y-%m-%d') }}</span>
                                <span>{{ post.author.username }}</span>
                            </div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            {% if pages > 1 %}
            <nav>
                <ul class="pagination justify-content-center">
                    {% if page > 1 %}
                        <li class="page-item">
                            <a class="page-link" href="?page={{ page - 1 }}">이전</a>
                        </li>
                    {% endif %}
                    
                    {% for p in range(1, pages + 1) %}
                        <li class="page-item {{ 'active' if p == page else '' }}">
                            <a class="page-link" href="?page={{ p }}">{{ p }}</a>
                        </li>
                    {% endfor %}
                    
                    {% if page < pages %}
                        <li class="page-item">
                            <a class="page-link" href="?page={{ page + 1 }}">다음</a>
                        </li>
                    {% endif %}
                </ul>
            </nav>
            {% endif %}
        {% else %}
            <div class="text-center py-5">
                <h3 class="text-muted">아직 포스트가 없습니다</h3>
                <p class="text-muted">첫 번째 포스트를 기다리고 있어요!</p>
            </div>
        {% endif %}
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5>카테고리</h5>
            </div>
            <div class="list-group list-group-flush">
                {% for category in categories %}
                <a href="/category/{{ category.slug }}" 
                   class="list-group-item list-group-item-action">
                    {{ category.name }}
                </a>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# templates/blog/detail.html
cat > templates/blog/detail.html << 'EOF'
{% extends "base.html" %}

{% block title %}{{ post.title }} - My Website{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <article>
            <header class="mb-4">
                <h1>{{ post.title }}</h1>
                <div class="text-muted mb-3">
                    <i class="fas fa-calendar"></i> {{ post.created_at.strftime('%Y년 %m월 %d일') }}
                    <i class="fas fa-user ms-3"></i> {{ post.author.username }}
                    <i class="fas fa-eye ms-3"></i> {{ post.views }}회
                    {% if post.category %}
                    <i class="fas fa-tag ms-3"></i> {{ post.category.name }}
                    {% endif %}
                </div>
                {% if post.featured_image %}
                <img src="{{ post.featured_image }}" class="img-fluid rounded mb-4" alt="{{ post.title }}">
                {% endif %}
            </header>
            
            <div class="content">
                {{ post.content | safe }}
            </div>
        </article>
        
        {% if related_posts %}
        <div class="mt-5">
            <h3>관련 포스트</h3>
            <div class="row">
                {% for related in related_posts %}
                <div class="col-md-4 mb-3">
                    <div class="card">
                        {% if related.featured_image %}
                        <img src="{{ related.featured_image }}" class="card-img-top" alt="{{ related.title }}" style="height: 150px; object-fit: cover;">
                        {% endif %}
                        <div class="card-body">
                            <h6 class="card-title">{{ related.title }}</h6>
                            <a href="/blog/{{ related.id }}" class="btn btn-sm btn-outline-primary">읽기</a>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5>카테고리</h5>
            </div>
            <div class="list-group list-group-flush">
                <a href="/blog" class="list-group-item list-group-item-action">전체 보기</a>
                {% if post.category %}
                <a href="/category/{{ post.category.slug }}" 
                   class="list-group-item list-group-item-action active">
                    {{ post.category.name }}
                </a>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# 관리자 템플릿들
echo "👑 관리자 템플릿들 생성 중..."

# templates/admin/base.html
cat > templates/admin/base.html << 'EOF'
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}관리자{% endblock %} - My Website</title>
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    
    <style>
        .sidebar {
            min-height: 100vh;
            background: linear-gradient(180deg, #343a40 0%, #495057 100%);
        }
        .sidebar .nav-link {
            color: #fff;
            padding: 12px 20px;
            margin: 2px 8px;
            border-radius: 8px;
        }
        .sidebar .nav-link:hover {
            background-color: rgba(255,255,255,0.1);
        }
        .sidebar .nav-link.active {
            background-color: #007bff;
        }
    </style>
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <nav class="col-md-3 col-lg-2 sidebar">
                <div class="position-sticky pt-4">
                    <div class="text-center mb-4">
                        <h5 class="text-light">관리자 패널</h5>
                        <small class="text-light">{{ request.session.get('username') }}</small>
                    </div>
                    
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link" href="/admin/">
                                <i class="fas fa-tachometer-alt me-2"></i>대시보드
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/admin/posts">
                                <i class="fas fa-edit me-2"></i>포스트 관리
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/admin/posts/create">
                                <i class="fas fa-plus me-2"></i>새 포스트
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="/admin/categories">
                                <i class="fas fa-tags me-2"></i>카테고리
                            </a>
                        </li>
                        <li class="nav-item mt-3">
                            <a class="nav-link" href="/" target="_blank">
                                <i class="fas fa-external-link-alt me-2"></i>사이트 보기
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link text-warning" href="/logout">
                                <i class="fas fa-sign-out-alt me-2"></i>로그아웃
                            </a>
                        </li>
                    </ul>
                </div>
            </nav>
            
            <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
                <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                    <h1 class="h2">{% block page_title %}대시보드{% endblock %}</h1>
                </div>
                
                {% with messages = get_flashed_messages(request) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                {% block content %}{% endblock %}
            </main>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    {% block extra_scripts %}{% endblock %}
</body>
</html>
EOF

# templates/admin/dashboard.html
cat > templates/admin/dashboard.html << 'EOF'
{% extends "admin/base.html" %}

{% block page_title %}대시보드{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-primary">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">총 포스트</div>
                        <div class="h5 mb-0 font-weight-bold">{{ total_posts }}</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-edit fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-success">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">발행된 포스트</div>
                        <div class="h5 mb-0 font-weight-bold">{{ published_posts }}</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-check fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-info">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="text-xs font-weight-bold text-info text-uppercase mb-1">총 사용자</div>
                        <div class="h5 mb-0 font-weight-bold">{{ total_users }}</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-users fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-xl-3 col-md-6 mb-4">
        <div class="card border-warning">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">카테고리</div>
                        <div class="h5 mb-0 font-weight-bold">{{ total_categories }}</div>
                    </div>
                    <div class="col-auto">
                        <i class="fas fa-tags fa-2x text-gray-300"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header d-flex justify-content-between">
                <h6 class="m-0 font-weight-bold text-primary">최근 포스트</h6>
                <a href="/admin/posts" class="btn btn-sm btn-outline-primary">전체 보기</a>
            </div>
            <div class="card-body">
                {% if recent_posts %}
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>제목</th>
                                    <th>상태</th>
                                    <th>작성일</th>
                                    <th>조회수</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for post in recent_posts %}
                                <tr>
                                    <td>{{ post.title[:50] }}{% if post.title|length > 50 %}...{% endif %}</td>
                                    <td>
                                        {% if post.is_published %}
                                            <span class="badge bg-success">발행됨</span>
                                        {% else %}
                                            <span class="badge bg-secondary">초안</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ post.created_at.strftime('%m/%d') }}</td>
                                    <td>{{ post.views }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <div class="text-center py-5">
                        <h5 class="text-muted">포스트가 없습니다</h5>
                        <p class="text-muted">첫 번째 포스트를 작성해보세요!</p>
                        <a href="/admin/posts/create" class="btn btn-primary">새 포스트 작성</a>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h6 class="m-0 font-weight-bold text-primary">빠른 작업</h6>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="/admin/posts/create" class="btn btn-primary">새 포스트 작성</a>
                    <a href="/admin/categories" class="btn btn-outline-secondary">카테고리 관리</a>
                    <a href="/" target="_blank" class="btn btn-outline-success">사이트 미리보기</a>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

# templates/admin/posts.html
cat > templates/admin/posts.html << 'EOF'
{% extends "admin/base.html" %}

{% block page_title %}포스트 관리{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <p class="text-muted mb-0">총 {{ posts|length }}개의 포스트</p>
    </div>
    <a href="/admin/posts/create" class="btn btn-primary">새 포스트 작성</a>
</div>

<div class="card">
    <div class="card-body">
        {% if posts %}
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>제목</th>
                            <th>작성자</th>
                            <th>카테고리</th>
                            <th>상태</th>
                            <th>작성일</th>
                            <th>조회수</th>
                            <th>작업</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for post in posts %}
                        <tr>
                            <td>{{ post.title }}</td>
                            <td>{{ post.author.username }}</td>
                            <td>
                                {% if post.category %}
                                    {{ post.category.name }}
                                {% else %}
                                    <span class="text-muted">-</span>
                                {% endif %}
                            </td>
                            <td>
                                {% if post.is_published %}
                                    <span class="badge bg-success">발행됨</span>
                                {% else %}
                                    <span class="badge bg-secondary">초안</span>
                                {% endif %}
                            </td>
                            <td>{{ post.created_at.strftime('%Y-%m-%d') }}</td>
                            <td>{{ post.views }}</td>
                            <td>
                                <div class="btn-group btn-group-sm">
                                    <a href="/admin/posts/{{ post.id }}/edit" class="btn btn-outline-primary btn-sm">수정</a>
                                    {% if post.is_published %}
                                        <a href="/blog/{{ post.id }}" target="_blank" class="btn btn-outline-success btn-sm">보기</a>
                                    {% endif %}
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <div class="text-center py-5">
                <h4 class="text-muted">포스트가 없습니다</h4>
                <p class="text-muted">첫 번째 포스트를 작성해보세요!</p>
                <a href="/admin/posts/create" class="btn btn-primary">새 포스트 작성</a>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
EOF

# templates/admin/post_form.html
cat > templates/admin/post_form.html << 'EOF'
{% extends "admin/base.html" %}

{% block page_title %}
{% if action == "create" %}
새 포스트 작성
{% else %}
포스트 수정
{% endif %}
{% endblock %}

{% block extra_head %}
<script src="https://cdn.tiny.cloud/1/no-api-key/tinymce/6/tinymce.min.js"></script>
{% endblock %}

{% block content %}
<form method="POST" enctype="multipart/form-data">
    <div class="row">
        <div class="col-lg-8">
            <div class="card">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">포스트 내용</h6>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label for="title" class="form-label">제목 *</label>
                        <input type="text" class="form-control" id="title" name="title" 
                               value="{{ form.title.data or '' }}" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="content" class="form-label">내용 *</label>
                        <textarea class="form-control" id="content" name="content" rows="15">{{ form.content.data or '' }}</textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="excerpt" class="form-label">요약</label>
                        <textarea class="form-control" id="excerpt" name="excerpt" rows="3">{{ form.excerpt.data or '' }}</textarea>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-lg-4">
            <div class="card">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">발행 설정</h6>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="is_published" name="is_published" 
                                   {% if form.is_published.data %}checked{% endif %}>
                            <label class="form-check-label" for="is_published">바로 발행</label>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="category_id" class="form-label">카테고리</label>
                        <select class="form-select" id="category_id" name="category_id">
                            {% for value, label in form.category_id.choices %}
                            <option value="{{ value }}" {% if form.category_id.data == value %}selected{% endif %}>
                                {{ label }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="featured_image" class="form-label">대표 이미지</label>
                        <input type="file" class="form-control" id="featured_image" name="featured_image" accept="image/*">
                    </div>
                    
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary">
                            {% if action == "create" %}
                            포스트 생성
                            {% else %}
                            포스트 수정
                            {% endif %}
                        </button>
                        <a href="/admin/posts" class="btn btn-secondary">취소</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</form>
{% endblock %}

{% block extra_scripts %}
<script>
tinymce.init({
    selector: '#content',
    height: 400,
    menubar: false,
    plugins: [
        'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
        'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
        'insertdatetime', 'media', 'table', 'help', 'wordcount'
    ],
    toolbar: 'undo redo | blocks | bold italic backcolor | ' +
             'alignleft aligncenter alignright alignjustify | ' +
             'bullist numlist outdent indent | removeformat | help',
    content_style: 'body { font-family:Helvetica,Arial,sans-serif; font-size:14px }',
    language: 'ko'
});
</script>
{% endblock %}
EOF

# templates/admin/categories.html
cat > templates/admin/categories.html << 'EOF'
{% extends "admin/base.html" %}

{% block page_title %}카테고리 관리{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header">
                <h6 class="m-0 font-weight-bold text-primary">카테고리 목록</h6>
            </div>
            <div class="card-body">
                {% if categories %}
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>이름</th>
                                    <th>슬러그</th>
                                    <th>설명</th>
                                    <th>포스트 수</th>
                                    <th>생성일</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for category in categories %}
                                <tr>
                                    <td>{{ category.name }}</td>
                                    <td><code>{{ category.slug }}</code></td>
                                    <td>{{ category.description or '-' }}</td>
                                    <td>{{ category.posts|length }}</td>
                                    <td>{{ category.created_at.strftime('%Y-%m-%d') }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <div class="text-center py-5">
                        <h4 class="text-muted">카테고리가 없습니다</h4>
                        <p class="text-muted">첫 번째 카테고리를 만들어보세요!</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h6 class="m-0 font-weight-bold text-primary">새 카테고리 추가</h6>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="name" class="form-label">카테고리명 *</label>
                        <input type="text" class="form-control" id="name" name="name" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="slug" class="form-label">슬러그 *</label>
                        <input type="text" class="form-control" id="slug" name="slug" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="description" class="form-label">설명</label>
                        <textarea class="form-control" id="description" name="description" rows="3"></textarea>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100">카테고리 추가</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
document.getElementById('name').addEventListener('input', function() {
    const name = this.value;
    const slug = name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').trim('-');
    document.getElementById('slug').value = slug;
});
</script>
{% endblock %}
EOF

# 에러 페이지들
echo "❌ 에러 페이지들 생성 중..."

# templates/errors/404.html
cat > templates/errors/404.html << 'EOF'
{% extends "base.html" %}

{% block title %}페이지를 찾을 수 없습니다 - My Website{% endblock %}

{% block content %}
<div class="text-center py-5">
    <h1 class="display-1">404</h1>
    <h2>페이지를 찾을 수 없습니다</h2>
    <p class="text-muted">요청하신 페이지가 존재하지 않거나 이동되었습니다.</p>
    <a href="/" class="btn btn-primary">홈으로 돌아가기</a>
</div>
{% endblock %}
EOF

# templates/errors/500.html
cat > templates/errors/500.html << 'EOF'
{% extends "base.html" %}

{% block title %}서버 오류 - My Website{% endblock %}

{% block content %}
<div class="text-center py-5">
    <h1 class="display-1">500</h1>
    <h2>서버 오류가 발생했습니다</h2>
    <p class="text-muted">잠시 후 다시 시도해주세요.</p>
    <a href="/" class="btn btn-primary">홈으로 돌아가기</a>
</div>
{% endblock %}
EOF

# 14. CSS 파일들 생성
echo "🎨 CSS 파일들 생성 중..."

# static/css/style.css
cat > static/css/style.css << 'EOF'
/* 기본 스타일 */
body {
    background-color: #f8f9fa;
}

.card {
    transition: transform 0.2s ease-in-out;
    border: none;
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
}

.jumbotron {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.navbar-brand {
    font-weight: bold;
    font-size: 1.5rem;
}

/* 블로그 관련 스타일 */
.blog-meta {
    font-size: 0.875rem;
    color: #6c757d;
}

.content {
    line-height: 1.8;
}

.content img {
    max-width: 100%;
    height: auto;
    border-radius: 0.375rem;
    margin: 1rem 0;
}

.content h1, .content h2, .content h3 {
    margin-top: 2rem;
    margin-bottom: 1rem;
}

.content p {
    margin-bottom: 1rem;
}

.content blockquote {
    border-left: 4px solid #007bff;
    padding-left: 1rem;
    margin: 1.5rem 0;
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 0.25rem;
}

/* 관리자 스타일 */
.admin-sidebar {
    background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
}

.text-xs {
    font-size: 0.75rem;
}

.font-weight-bold {
    font-weight: 700;
}

/* 반응형 */
@media (max-width: 768px) {
    .jumbotron {
        padding: 2rem 1rem;
    }
    
    .jumbotron h1 {
        font-size: 2rem;
    }
    
    .card-body {
        padding: 1rem;
    }
}

/* 로딩 애니메이션 */
.spinner-border-sm {
    width: 1rem;
    height: 1rem;
}

/* 플래시 메시지 애니메이션 */
.alert {
    animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* 이미지 최적화 */
.card-img-top {
    transition: transform 0.2s ease-in-out;
}

.card:hover .card-img-top {
    transform: scale(1.05);
}

/* 버튼 스타일 */
.btn {
    border-radius: 0.5rem;
    font-weight: 500;
    transition: all 0.2s ease-in-out;
}

.btn:hover {
    transform: translateY(-1px);
}

/* 폼 스타일 */
.form-control:focus {
    border-color: #86b7fe;
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
}

/* 네비게이션 */
.navbar {
    box-shadow: 0 2px 4px rgba(0,0,0,.1);
}

.navbar-nav .nav-link {
    transition: color 0.2s ease-in-out;
}

/* 푸터 */
footer {
    margin-top: auto;
}

/* 유틸리티 클래스 */
.text-gray-800 {
    color: #5a5c69;
}

.text-gray-300 {
    color: #dddfeb;
}

.border-left-primary {
    border-left: 0.25rem solid #4e73df !important;
}

.border-left-success {
    border-left: 0.25rem solid #1cc88a !important;
}

.border-left-info {
    border-left: 0.25rem solid #36b9cc !important;
}

.border-left-warning {
    border-left: 0.25rem solid #f6c23e !important;
}
EOF

# 15. JavaScript 파일 생성
echo "⚡ JavaScript 파일들 생성 중..."

# static/js/main.js
cat > static/js/main.js << 'EOF'
// 메인 JavaScript 파일

document.addEventListener('DOMContentLoaded', function() {
    // 플래시 메시지 자동 닫기
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.classList.remove('show');
            setTimeout(function() {
                alert.remove();
            }, 150);
        }, 5000);
    });
    
    // 이미지 로딩 에러 처리
    const images = document.querySelectorAll('img');
    images.forEach(function(img) {
        img.addEventListener('error', function() {
            this.src = '/static/images/placeholder.jpg';
            this.alt = '이미지를 불러올 수 없습니다';
        });
    });
    
    // 폼 제출 시 로딩 표시
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>처리 중...';
                
                setTimeout(function() {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 5000);
            }
        });
    });
    
    // 뒤로가기 버튼
    const backBtns = document.querySelectorAll('.btn-back');
    backBtns.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            history.back();
        });
    });
    
    // 확인 대화상자
    const confirmBtns = document.querySelectorAll('[data-confirm]');
    confirmBtns.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
    
    // 툴팁 초기화 (Bootstrap 5)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    console.log('🚀 FastAPI + Jinja2 웹사이트가 로드되었습니다!');
});

// 이미지 미리보기 함수
function previewImage(input, previewId) {
    const file = input.files[0];
    const preview = document.getElementById(previewId);
    
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        preview.style.display = 'none';
    }
}

// AJAX 요청 헬퍼
function sendAjaxRequest(url, method = 'GET', data = null) {
    return fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: data ? JSON.stringify(data) : null
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .catch(error => {
        console.error('Ajax request failed:', error);
        throw error;
    });
}

// 성공 메시지 표시
function showSuccessMessage(message) {
    showMessage(message, 'success');
}

// 에러 메시지 표시
function showErrorMessage(message) {
    showMessage(message, 'danger');
}

// 메시지 표시 함수
function showMessage(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
    }
}
EOF

# 16. 실행 스크립트들 생성
echo "🏃 실행 스크립트들 생성 중..."

# run.py (간단한 실행용)
cat > run.py << 'EOF'
#!/usr/bin/env python3
"""
FastAPI + Jinja2 웹사이트 실행 스크립트
"""

import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    
    # 개발/운영 모드 설정
    debug_mode = os.getenv("DEBUG", "True").lower() == "true"
    
    print("🚀 FastAPI + Jinja2 웹사이트 시작!")
    print(f"📍 모드: {'개발' if debug_mode else '운영'}")
    print("🌐 주소: http://localhost:8000")
    print("👑 관리자: http://localhost:8000/admin")
    print("📚 API 문서: http://localhost:8000/docs")
    print("\n종료하려면 Ctrl+C를 누르세요.\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=debug_mode,
        log_level="info" if debug_mode else "warning"
    )
EOF

# setup_db.py (데이터베이스 초기화)
cat > setup_db.py << 'EOF'
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
EOF

# 17. README.md 생성
echo "📖 README.md 생성 중..."
cat > README.md << 'EOF'
# 🚀 FastAPI + Jinja2 웹사이트 템플릿

완전한 기능을 갖춘 웹사이트를 빠르게 구축할 수 있는 템플릿입니다.

## ✨ 주요 기능

- **FastAPI** 백엔드로 빠른 성능
- **Jinja2** 템플릿으로 서버사이드 렌더링 (SEO 최적화)
- **Bootstrap 5** 반응형 디자인
- **관리자 페이지**로 쉬운 콘텐츠 관리
- **WYSIWYG 에디터** (TinyMCE)
- **파일 업로드** 및 이미지 최적화
- **사용자 인증** (세션 기반)
- **블로그 시스템**
- **카테고리 관리**

## 🛠️ 빠른 시작

### 1. 스크립트 실행

```bash
# 스크립트에 실행 권한 부여
chmod +x setup_website.sh

# 전체 프로젝트 구조 생성
./setup_website.sh
```

### 2. 가상환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 데이터베이스 설정

```bash
# MySQL 설치 후 데이터베이스 생성
mysql -u root -p
CREATE DATABASE website_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# .env 파일 수정 (MySQL 비밀번호 등)
cp .env.example .env
# DATABASE_URL을 본인의 MySQL 설정에 맞게 수정
```

### 4. 초기 데이터 설정

```bash
# 데이터베이스 테이블 생성 및 관리자 계정 생성
python setup_db.py
```

### 5. 서버 실행

```bash
# 개발 서버 시작
python run.py

# 또는
uvicorn app.main:app --reload
```

### 6. 접속 확인

- 🏠 **홈페이지**: http://localhost:8000
- 👑 **관리자**: http://localhost:8000/admin
- 📚 **API 문서**: http://localhost:8000/docs

**기본 관리자 계정**: `admin` / `admin123`

## 📁 프로젝트 구조

```
my-website/
├── app/                 # FastAPI 애플리케이션
│   ├── routers/        # 라우터 (페이지별)
│   ├── models.py       # 데이터베이스 모델
│   ├── forms.py        # WTForms 폼 클래스
│   ├── utils.py        # 유틸리티 함수
│   ├── database.py     # DB 연결 설정
│   └── main.py         # 메인 애플리케이션
├── templates/          # Jinja2 템플릿
│   ├── base.html       # 기본 레이아웃
│   ├── auth/           # 인증 페이지
│   ├── blog/           # 블로그 페이지
│   ├── admin/          # 관리자 페이지
│   └── errors/         # 에러 페이지
├── static/             # 정적 파일
│   ├── css/            # CSS 파일
│   ├── js/             # JavaScript 파일
│   └── uploads/        # 업로드 파일
├── requirements.txt    # Python 패키지 목록
├── .env               # 환경 변수
├── create_admin.py    # 관리자 계정 생성
├── setup_db.py        # DB 초기화 및 샘플 데이터
├── run.py             # 서버 실행 스크립트
└── README.md          # 이 파일
```

## 🎯 사용 방법

### 관리자 페이지 사용법

1. **로그인**: `/admin` → `admin` / `admin123`
2. **카테고리 생성**: 관리자 → 카테고리 → 새 카테고리 추가
3. **포스트 작성**: 관리자 → 새 포스트 → 제목/내용 입력 → 발행
4. **파일 관리**: 포스트 작성 시 이미지 업로드 가능

### 커스터마이징

#### 디자인 변경
```css
/* static/css/style.css에서 수정 */
:root {
    --primary-color: #007bff;    /* 메인 색상 */
    --secondary-color: #6c757d;  /* 보조 색상 */
}
```

#### 사이트 이름 변경
```html
<!-- templates/base.html에서 수정 -->
<a class="navbar-brand" href="/">Your Website Name</a>
```

#### 로고 추가
```html
<!-- templates/base.html의 <head>에 추가 -->
<link rel="icon" href="/static/favicon.ico">
```

## 🔧 기술 스택

- **Backend**: FastAPI 0.104+
- **Frontend**: Jinja2 + Bootstrap 5
- **Database**: MySQL + SQLAlchemy
- **Authentication**: Session-based
- **File Upload**: Pillow (이미지 처리)
- **Forms**: WTForms
- **Editor**: TinyMCE

## 🚀 배포

### 운영 환경 설정

```bash
# .env 파일 수정
DEBUG=False
SECRET_KEY=your-production-secret-key
DATABASE_URL=mysql+pymysql://user:password@localhost/db
```

### Gunicorn으로 실행

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker 배포

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

## 🎨 확장 아이디어

### 추가 기능 구현
- **댓글 시스템**: 포스트에 댓글 기능 추가
- **검색 기능**: 전체 텍스트 검색
- **태그 시스템**: 포스트 태깅 및 필터링
- **갤러리**: 이미지 갤러리 페이지
- **이메일 발송**: 뉴스레터, 알림 기능
- **소셜 로그인**: Google, GitHub 연동
- **API 확장**: 모바일 앱 대비 REST API

### 성능 최적화
- **캐싱**: Redis 연동
- **CDN**: 정적 파일 CDN 사용
- **이미지 최적화**: WebP 변환, 썸네일 생성
- **데이터베이스**: 인덱스 최적화

## 🛠️ 트러블슈팅

### 자주 발생하는 문제

**MySQL 연결 오류**
```bash
pip install pymysql cryptography
```

**포트 충돌**
```bash
uvicorn app.main:app --port 8001
```

**권한 오류**
```bash
chmod 755 static/uploads
```

**패키지 설치 오류**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 📝 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능합니다.

## 🤝 기여하기

1. 이 저장소를 Fork
2. 새 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 Push (`git push origin feature/amazing-feature`)
5. Pull Request 생성

## 💬 지원

- **문서**: 이 README 파일
- **예제**: `setup_db.py`에서 샘플 데이터 확인
- **문제 신고**: GitHub Issues 사용

---

**🎉 즐거운 개발 되세요!**

이 템플릿으로 개인 블로그부터 회사 홈페이지까지 다양한 웹사이트를 만들어보세요!
EOF

# 18. .gitignore 생성
echo "📄 .gitignore 생성 중..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# Custom
static/uploads/*
!static/uploads/.gitkeep
.DS_Store
Thumbs.db
.vscode/
.idea/
*.swp
*.swo
*~

# Database
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
EOF

# 19. static/uploads/.gitkeep 생성
echo "📁 uploads 폴더 보존용 파일 생성 중..."
touch static/uploads/.gitkeep

# 20. 완료 메시지
echo ""
echo "🎉 ====================================="
echo "   FastAPI + Jinja2 웹사이트 템플릿"
echo "   파일 생성이 완료되었습니다!"
echo "===================================== 🎉"
echo ""
echo "📁 생성된 폴더 및 파일:"
echo "   ├── app/ (백엔드 코드)"
echo "   ├── templates/ (HTML 템플릿)"
echo "   ├── static/ (CSS, JS, 이미지)"
echo "   ├── requirements.txt"
echo "   ├── .env"
echo "   ├── create_admin.py"
echo "   ├── setup_db.py"
echo "   ├── run.py"
echo "   └── README.md"
echo ""
echo "🚀 다음 단계:"
echo "   1. pip install -r requirements.txt"
echo "   2. MySQL 데이터베이스 생성"
echo "   3. .env 파일에서 DB 설정 확인"
echo "   4. python setup_db.py"
echo "   5. python run.py"
echo ""
echo "🌐 접속 주소:"
echo "   홈페이지: http://localhost:8000"
echo "   관리자: http://localhost:8000/admin"
echo "   로그인: admin / admin123"
echo ""
echo "🎯 Happy coding! 🎯"