from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session
from shared.models import Favorite, User
from user_service.auth import get_current_user
from user_service.schemas import FavoriteResponse

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteResponse])
async def list_favorites(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Favorite).where(Favorite.user_id == current_user.id).order_by(Favorite.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{listing_id}", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in favorites")

    fav = Favorite(user_id=current_user.id, listing_id=listing_id)
    session.add(fav)
    await session.commit()
    await session.refresh(fav)
    return fav


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in favorites")
    await session.delete(fav)
    await session.commit()
