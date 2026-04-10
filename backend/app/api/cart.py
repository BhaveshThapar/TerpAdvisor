"""Planning cart API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import CartItem
from app.api.user import _current_user
from app.schemas.schemas import CartAddRequest, CartItemResponse

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("/", response_model=list[CartItemResponse])
async def get_cart(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(CartItem).where(CartItem.user_id == user.id).order_by(CartItem.added_at)
    )
    rows = result.scalars().all()
    return [CartItemResponse(course_id=r.course_id, added_at=str(r.added_at)) for r in rows]


@router.post("/", response_model=CartItemResponse)
async def add_to_cart(body: CartAddRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    course_id = body.course_id.strip().upper()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    existing = await db.execute(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.course_id == course_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Course already in cart")
    item = CartItem(user_id=user.id, course_id=course_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return CartItemResponse(course_id=item.course_id, added_at=str(item.added_at))


@router.delete("/clear")
async def clear_cart(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    await db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    await db.commit()
    return {"message": "Cart cleared"}


@router.delete("/{course_id}")
async def remove_from_cart(course_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    await db.execute(
        delete(CartItem).where(
            CartItem.user_id == user.id,
            CartItem.course_id == course_id.upper(),
        )
    )
    await db.commit()
    return {"message": f"Removed {course_id} from cart"}
