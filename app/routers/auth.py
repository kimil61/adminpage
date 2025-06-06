from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
# from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.forms import LoginForm, RegisterForm
from app.utils import hash_password, verify_password, flash_message
from app.template import templates

router = APIRouter()
# templates = Jinja2Templates(directory="templates")

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    formdata = await request.form()
    form = LoginForm(formdata)

    username = formdata.get("username")
    password = formdata.get("password")

    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.password):
        flash_message(request, "아이디 또는 비밀번호가 틀렸습니다.", "error")
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "form": form
        })

    # 로그인 성공 처리
    request.session["user_id"] = user.id
    request.session["is_admin"] = user.is_admin
    return RedirectResponse(url="/admin", status_code=302)

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
    
    # 💥 여기 수정
    formdata = await request.form()
    form = RegisterForm(formdata)
    
    return templates.TemplateResponse("auth/register.html", {
        "request": request,
        "form": form
    })

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    flash_message(request, "로그아웃되었습니다.", "info")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
