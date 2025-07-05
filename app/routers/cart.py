from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from app.services.cart_service import CartService
from app.dependencies import get_db, get_current_user
from sqlalchemy.orm import Session
from app.template import templates
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/cart", tags=["cart"])

# Pydantic 모델
class CartItemRequest(BaseModel):
    product_id: int
    quantity: int = 1
    csrf_token: str
    idempotency_key: str

class CartUpdateRequest(BaseModel):
    product_id: int
    quantity: int
    csrf_token: str
    idempotency_key: str

# SSR: 장바구니 페이지
@router.get("", response_class=HTMLResponse)
def cart_page(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart = dict(CartService.get_cart(user.id, db))
    return templates.TemplateResponse(
        "cart/cart.html",
        {"request": request, "user": user, "cart": cart, "cart_items": cart.get("items", [])}
    )

# API: 장바구니 조회
@router.get("/api/v1/items")
def get_cart_items(db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart_data = CartService.get_cart(user.id, db)
    return {"success": True, "data": cart_data}

# API: 장바구니에 상품 추가
@router.post("/api/v1/add")
def add_to_cart(request: CartItemRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = CartService.add_to_cart(user.id, request.product_id, request.quantity, db)
    return JSONResponse(content=result)

# API: 장바구니에서 상품 제거
@router.delete("/api/v1/remove/{product_id}")
def remove_from_cart(product_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = CartService.remove_from_cart(user.id, product_id, db)
    return JSONResponse(content=result)

# API: 장바구니 상품 수량 변경
@router.put("/api/v1/update")
def update_cart_quantity(request: CartUpdateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = CartService.update_quantity(user.id, request.product_id, request.quantity, db)
    return JSONResponse(content=result)

# API: 장바구니 비우기
@router.delete("/api/v1/clear")
def clear_cart(db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = CartService.clear_cart(user.id, db)
    return JSONResponse(content=result) 