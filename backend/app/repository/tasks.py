from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repository.users import UserRepository


class TaskRepository:
    @staticmethod
    async def create_personal(
        db: AsyncSession,
        *,
        title: str,
        description: str | None,
        due_at,
        owner_user_id: int,
        created_by: int,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            due_at=due_at,
            status="todo",
            owner_user_id=owner_user_id,
            created_by=created_by,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def create_from_bot(
        db: AsyncSession,
        *,
        telegram_id: int,
        title: str,
        description: str | None,
        remind_at: str,  # уже "HH:MM" после валидатора в схеме
        username: str | None,
        first_name: str | None,
    ) -> Task:
        # 1) user upsert by telegram_id
        user = await UserRepository.upsert(
            db,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )

        # 2) "HH:MM" -> datetime (today)
        hh, mm = map(int, remind_at.split(":"))
        now = datetime.now()

        due_at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if due_at <= now:
            due_at = due_at + timedelta(days=1)

        # 3) create task
        task = Task(
            title=title,
            description=description,
            due_at=due_at,
            status="todo",
            owner_user_id=user.id,
            created_by=user.id,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_by_owner(db: AsyncSession, owner_user_id: int) -> list[Task]:
        res = await db.execute(
            select(Task)
            .where(Task.owner_user_id == owner_user_id)
            .order_by(Task.id.desc())
        )
        return list(res.scalars().all())

    @staticmethod
    async def count_by_owner(db: AsyncSession, owner_user_id: int) -> int:
        res = await db.execute(
            select(func.count(Task.id)).where(Task.owner_user_id == owner_user_id)
        )
        return int(res.scalar_one())
