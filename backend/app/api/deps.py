from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.users import UserRepository
from app.models.user import User


async def get_current_user(
    telegram_id: int = Query(..., description="Telegram user id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        # бот делает /users/upsert на /start, так что это скорее “защита от кривых вызовов”
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )
    return user
