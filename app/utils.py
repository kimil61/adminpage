from passlib.context import CryptContext
from fastapi import HTTPException, Depends, Request, UploadFile
from werkzeug.utils import secure_filename
import magic
import secrets
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


def generate_csrf_token(request: Request) -> str:
    """세션에 CSRF 토큰을 생성하고 반환"""
    token = secrets.token_hex(16)
    request.session['csrf_token'] = token
    return token


def verify_csrf_token(request: Request, token: str):
    session_token = request.session.get('csrf_token')
    if not session_token or session_token != token:
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

async def save_uploaded_file(file: UploadFile, folder: str = "uploads") -> str:
    """파일 업로드시 확장자와 MIME 타입, 크기를 검증한다."""
    allowed_mime_types = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf', 'application/msword'
    }
    max_file_size = 5 * 1024 * 1024  # 5MB

    content = await file.read()
    if len(content) > max_file_size:
        raise ValueError("파일 크기가 제한을 초과합니다.")

    mime_type = magic.from_buffer(content, mime=True)
    if mime_type not in allowed_mime_types:
        raise ValueError("허용되지 않는 파일 형식입니다.")

    file_extension = os.path.splitext(secure_filename(file.filename))[1].lower()
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    upload_dir = f"static/uploads/{folder}"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, unique_filename)
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

    if mime_type.startswith('image/'):
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
