from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    @staticmethod
    async def get_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
        res = await db.execute(select(User).where(User.telegram_id == telegram_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = await UserRepository.get_by_telegram_id(db, telegram_id)

        if user is None:
            user = User(
                telegram_id=telegram_id, username=username, first_name=first_name
            )
            db.add(user)
        else:
            user.username = username
            user.first_name = first_name

        await db.commit()
        await db.refresh(user)
        return user
