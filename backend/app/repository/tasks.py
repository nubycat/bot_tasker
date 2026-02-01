from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


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
    async def list_by_owner(db: AsyncSession, owner_user_id: int) -> list[Task]:
        res = await db.execute(
            select(Task)
            .where(Task.owner_user_id == owner_user_id)
            .order_by(Task.id.desc())
        )
        return list(res.scalars().all())
