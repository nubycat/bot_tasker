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
            team_id=user.active_team_id,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_by_owner(db: AsyncSession, owner_user_id: int) -> list[Task]:
        res = await db.execute(
            select(Task)
            .where(
                Task.owner_user_id == owner_user_id,
                Task.team_id.is_(None),
            )
            .order_by(Task.id.desc())
        )
        return list(res.scalars().all())

    @staticmethod
    async def count_by_owner(db: AsyncSession, owner_user_id: int) -> int:
        res = await db.execute(
            select(func.count(Task.id)).where(Task.owner_user_id == owner_user_id)
        )
        return int(res.scalar_one())

    @staticmethod
    async def list_today_by_owner(
        db: AsyncSession,
        owner_user_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Task]:
        """Return owner's tasks due within [day_start, day_end), ordered by due_at."""
        res = await db.execute(
            select(Task)
            .where(
                Task.owner_user_id == owner_user_id,
                Task.due_at.is_not(None),
                Task.due_at >= day_start,
                Task.due_at < day_end,
            )
            .order_by(Task.due_at.asc())
        )
        return list(res.scalars().all())

    @staticmethod
    async def get_personal_by_id(
        db: AsyncSession,
        *,
        task_id: int,
        owner_user_id: int,
    ) -> Task | None:
        """
        Получить **личную** задачу по её ID, но **только если она принадлежит** указанному владельцу.

        Метод делает выборку из таблицы задач с двумя условиями:
        - `Task.id == task_id`
        - `Task.owner_user_id == owner_user_id`

        Это защищает от доступа к чужим задачам: если задача существует, но владелец другой —
        вернётся `None`, как будто задачи нет.

        Args:
            db: Асинхронная сессия SQLAlchemy (`AsyncSession`).
            task_id: Идентификатор задачи.
            owner_user_id: Идентификатор пользователя-владельца задачи.

        Returns:
            `Task`, если задача найдена и принадлежит пользователю, иначе `None`.

        Notes:
            - Возвращает один объект или `None` (по фильтру `Task.id`).
        """
        res = await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.owner_user_id == owner_user_id,
                Task.team_id.is_(None),
            )
        )
        return res.scalar_one_or_none()

    # TODO: open/done
    @staticmethod
    async def list_today_open_by_owner(db, owner_user_id: int, day_start, day_end):
        """
        Возвращает выполненные задачи ("done") владельца за сегодня.
        Фильтр по due_at: [day_start, day_end), сортировка по due_at ASC.
        """
        stmt = (
            select(Task)
            .where(
                Task.owner_user_id == owner_user_id,
                Task.due_at >= day_start,
                Task.due_at < day_end,
                Task.status == "todo",
                Task.team_id.is_(None),
            )
            .order_by(Task.due_at.asc())
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def list_today_done_by_owner(db, owner_user_id: int, day_start, day_end):
        """
        Возвращает выполненные задачи ("done") владельца за сегодня.
        Фильтр по due_at: [day_start, day_end), сортировка по due_at ASC.
        """
        stmt = (
            select(Task)
            .where(
                Task.owner_user_id == owner_user_id,
                Task.due_at >= day_start,
                Task.due_at < day_end,
                Task.status == "done",
                Task.team_id.is_(None),
            )
            .order_by(Task.due_at.asc())
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def mark_done_personal(
        db, *, task_id: int, owner_user_id: int
    ) -> Task | None:
        task = await TaskRepository.get_personal_by_id(
            db,
            task_id=task_id,
            owner_user_id=owner_user_id,
        )
        if task is None:
            return None

        task.status = "done"
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def snooze_to_tomorrow_personal(
        db,
        *,
        task_id: int,
        owner_user_id: int,
    ):
        task = await TaskRepository.get_personal_by_id(
            db,
            task_id=task_id,
            owner_user_id=owner_user_id,
        )
        if task is None:
            return None

        task.due_at = task.due_at + timedelta(days=1)

        await db.commit()
        await db.refresh(task)
        return task
