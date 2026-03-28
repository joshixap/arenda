from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session
from shared.models import Subscription, SubscriptionChannel, User
from user_service.auth import get_current_user
from user_service.schemas import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == current_user.id).order_by(Subscription.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        channel = SubscriptionChannel(body.channel)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid channel")

    sub = Subscription(
        user_id=current_user.id,
        name=body.name,
        channel=channel,
        filter_city=body.filter_city,
        filter_rooms_min=body.filter_rooms_min,
        filter_rooms_max=body.filter_rooms_max,
        filter_price_min=body.filter_price_min,
        filter_price_max=body.filter_price_max,
        filter_area_min=body.filter_area_min,
        filter_area_max=body.filter_area_max,
        filter_sources=body.filter_sources,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


@router.patch("/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription(
    sub_id: uuid.UUID,
    body: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    await session.commit()
    await session.refresh(sub)
    return sub


@router.delete("/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == current_user.id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    await session.delete(sub)
    await session.commit()
