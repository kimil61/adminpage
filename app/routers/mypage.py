from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.services.mypage_service import MypageService
from app.dependencies import get_db, get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mypage", tags=["mypage"])

# SSR: 마이페이지 대시보드
@router.get("", response_class=HTMLResponse)
def mypage_dashboard(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dashboard_data = MypageService.get_dashboard(user.id, db)
    return request.app.state.templates.TemplateResponse("mypage/dashboard.html", {"request": request, "user": user, **dashboard_data})

# SSR: 주문/결제 내역
@router.get("/orders", response_class=HTMLResponse)
def mypage_orders(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    orders = MypageService.get_orders(user.id, db)
    return request.app.state.templates.TemplateResponse("mypage/orders.html", {"request": request, "user": user, "orders": orders})

# SSR: 포인트/충전 내역
@router.get("/points", response_class=HTMLResponse)
def mypage_points(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    points = MypageService.get_points(user.id, db)
    return request.app.state.templates.TemplateResponse("mypage/points.html", {"request": request, "user": user, "points": points})

# SSR: 내가 쓴 리뷰
@router.get("/reviews", response_class=HTMLResponse)
def mypage_reviews(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    reviews = MypageService.get_reviews(user.id, db)
    return request.app.state.templates.TemplateResponse("mypage/reviews.html", {"request": request, "user": user, "reviews": reviews})

# SSR: 계정/알림 설정
@router.get("/settings", response_class=HTMLResponse)
def mypage_settings(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return request.app.state.templates.TemplateResponse("mypage/settings.html", {"request": request, "user": user})

# SSR: 구매 내역
@router.get("/purchases", response_class=HTMLResponse)
def mypage_purchases(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    purchases = MypageService.get_purchases(user.id, db)
    return request.app.state.templates.TemplateResponse("mypage/purchases.html", {"request": request, "user": user, "purchases": purchases})

# (추후) API 라우트도 추가 가능 

@router.get("/dashboard", response_class=HTMLResponse)
def mypage_dashboard_alias(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    return mypage_dashboard(request, db, user) 