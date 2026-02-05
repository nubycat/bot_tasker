from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.tasks import TaskRepository
from app.repository.users import UserRepository
from app.schemas.task import TaskCreateIn, TaskOut, TaskCreateFromBotIn

router = APIRouter(prefix="/tasks", tags=["Задачи"])


@router.post("/personal", response_model=TaskOut)
async def create_personal_task(
    payload: TaskCreateIn,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    return await TaskRepository.create_personal(
        db,
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        owner_user_id=user.id,
        created_by=user.id,
    )


@router.get("/personal", response_model=list[TaskOut])
async def list_personal_tasks(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return []

    return await TaskRepository.list_by_owner(db, user.id)


@router.get("/personal/count")
async def count_personal_tasks(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return {"count": 0}

    count = await TaskRepository.count_by_owner(db, user.id)
    return {"count": count}


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task_from_bot(
    payload: TaskCreateFromBotIn,
    db: AsyncSession = Depends(get_db),
):
    return await TaskRepository.create_from_bot(
        db,
        telegram_id=payload.telegram_id,
        title=payload.title,
        description=payload.description,
        remind_at=payload.remind_at,
        username=payload.username,
        first_name=payload.first_name,
    )


@router.get("/personal/today", response_model=list[TaskOut])
async def list_personal_today(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает задачи на сегодня для пользователя по telegram_id."""
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return []

    now = datetime.now()
    day_start = datetime.combine(now.date(), time.min)
    day_end = day_start + timedelta(days=1)

    return await TaskRepository.list_today_by_owner(db, user.id, day_start, day_end)
