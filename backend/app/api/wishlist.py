"""Wishlist API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import CartItem, WishlistItem
from app.api.user import _current_user
from app.schemas.schemas import WishlistAddRequest, WishlistItemResponse

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


@router.get("/", response_model=list[WishlistItemResponse])
async def get_wishlist(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    result = await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == user.id).order_by(WishlistItem.added_at)
    )
    rows = result.scalars().all()
    return [WishlistItemResponse(course_id=r.course_id, added_at=str(r.added_at)) for r in rows]


@router.post("/", response_model=WishlistItemResponse)
async def add_to_wishlist(body: WishlistAddRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    course_id = body.course_id.strip().upper()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    existing = await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.course_id == course_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Course already in wishlist")
    item = WishlistItem(user_id=user.id, course_id=course_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return WishlistItemResponse(course_id=item.course_id, added_at=str(item.added_at))


@router.delete("/clear")
async def clear_wishlist(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    await db.execute(delete(WishlistItem).where(WishlistItem.user_id == user.id))
    await db.commit()
    return {"message": "Wishlist cleared"}


@router.delete("/{course_id}")
async def remove_from_wishlist(course_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    await db.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user.id,
            WishlistItem.course_id == course_id.upper(),
        )
    )
    await db.commit()
    return {"message": f"Removed {course_id} from wishlist"}


@router.post("/{course_id}/move-to-cart")
async def move_to_cart(course_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    normalized = course_id.strip().upper()
    existing_cart = await db.execute(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.course_id == normalized)
    )
    if not existing_cart.scalar_one_or_none():
        cart_item = CartItem(user_id=user.id, course_id=normalized)
        db.add(cart_item)
    await db.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user.id,
            WishlistItem.course_id == normalized,
        )
    )
    await db.commit()
    return {"message": "Moved to cart"}
