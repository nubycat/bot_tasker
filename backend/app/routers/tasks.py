from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.tasks import TaskRepository
from app.repository.users import UserRepository
from app.schemas.task import TaskCreateIn, TaskOut, TaskCreateFromBotIn, TodayTasksOut

router = APIRouter(prefix="/tasks", tags=["Задачи"])
TZ = ZoneInfo(os.getenv("APP_TZ", "UTC"))


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


@router.get("/personal/today", response_model=TodayTasksOut)
async def list_personal_today(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает задачи на сегодня для пользователя по telegram_id (open/done)."""
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return {"open": [], "done": []}

    now_local = datetime.now(TZ).replace(tzinfo=None)
    day_start = datetime.combine(now_local.date(), time.min)
    day_end = day_start + timedelta(days=1)

    open_tasks = await TaskRepository.list_today_open_by_owner(
        db, user.id, day_start, day_end
    )
    done_tasks = await TaskRepository.list_today_done_by_owner(
        db, user.id, day_start, day_end
    )

    return {"open": open_tasks, "done": done_tasks}


@router.get("/team/today", response_model=TodayTasksOut)
async def list_team_today(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает задачи на сегодня для команды по telegram_id (open/done)."""
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return {"open": [], "done": []}

    if user.active_team_id is None:
        raise HTTPException(status_code=400, detail="No active team")

    now_local = datetime.now(TZ).replace(tzinfo=None)
    day_start = datetime.combine(now_local.date(), time.min)
    day_end = day_start + timedelta(days=1)

    open_tasks = await TaskRepository.list_today_open_by_team(
        db, user.active_team_id, day_start, day_end
    )
    done_tasks = await TaskRepository.list_today_done_by_team(
        db, user.active_team_id, day_start, day_end
    )
    return {"open": open_tasks, "done": done_tasks}


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


# ПОТОМ УДАЛИТЬ, НАВЕРНО

# @router.get("/personal/today", response_model=list[TaskOut])
# async def list_personal_today(
#     telegram_id: int = Query(gt=0),
#     db: AsyncSession = Depends(get_db),
# ):
#     """Возвращает задачи на сегодня для пользователя по telegram_id."""
#     user = await UserRepository.get_by_telegram_id(db, telegram_id)
#     if user is None:
#         return []

#     now_msk = datetime.now(TZ).replace(tzinfo=None)
#     day_start = datetime.combine(now_msk.date(), time.min)
#     day_end = day_start + timedelta(days=1)

#     return await TaskRepository.list_today_by_owner(db, user.id, day_start, day_end)


@router.get("/personal/{task_id}", response_model=TaskOut)
async def get_personal_task(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    task = await TaskRepository.get_personal_by_id(
        db,
        task_id=task_id,
        owner_user_id=user.id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.get("/team/{task_id}", response_model=TaskOut)
async def get_team_task(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.active_team_id is None:
        raise HTTPException(status_code=400, detail="No active team")

    task = await TaskRepository.get_team_by_id(
        db,
        task_id=task_id,
        team_id=user.active_team_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.patch("/personal/{task_id}/done", response_model=TaskOut)
async def mark_personal_done(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Помечает личную задачу выполненной (status='done')."""
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    task = await TaskRepository.mark_done_personal(
        db, task_id=task_id, owner_user_id=user.id
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.patch("/personal/{task_id}/tomorrow", response_model=TaskOut)
async def move_personal_task_to_tomorrow(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """Переносит личную задачу на завтра (due_at + 1 day)."""
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    task = await TaskRepository.snooze_to_tomorrow_personal(
        db,
        task_id=task_id,
        owner_user_id=user.id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.patch("/team/{task_id}/done", response_model=TaskOut)
async def mark_team_done(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.active_team_id is None:
        raise HTTPException(status_code=400, detail="No active team")

    task = await TaskRepository.mark_done_team(
        db,
        task_id=task_id,
        team_id=user.active_team_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


@router.patch("/team/{task_id}/tomorrow", response_model=TaskOut)
async def move_team_task_to_tomorrow(
    task_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.active_team_id is None:
        raise HTTPException(status_code=400, detail="No active team")

    task = await TaskRepository.snooze_to_tomorrow_team(
        db,
        task_id=task_id,
        team_id=user.active_team_id,
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return task


# handler, который возвращает TodayTasksOut и внутри выбирается personal/team:


@router.get("/today", response_model=TodayTasksOut)
async def list_today(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Контекстный today:
    - если active_team_id есть -> today по команде
    - иначе -> today личные
    """
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        return {"open": [], "done": []}

    now_local = datetime.now(TZ).replace(tzinfo=None)
    day_start = datetime.combine(now_local.date(), time.min)
    day_end = day_start + timedelta(days=1)

    if user.active_team_id:
        open_tasks = await TaskRepository.list_today_open_by_team(
            db, user.active_team_id, day_start, day_end
        )
        done_tasks = await TaskRepository.list_today_done_by_team(
            db, user.active_team_id, day_start, day_end
        )
    else:
        open_tasks = await TaskRepository.list_today_open_by_owner(
            db, user.id, day_start, day_end
        )
        done_tasks = await TaskRepository.list_today_done_by_owner(
            db, user.id, day_start, day_end
        )

    return {"open": open_tasks, "done": done_tasks}
