from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.tasks import TaskRepository
from app.repository.users import UserRepository
from app.schemas.task import TaskCreateIn, TaskOut

router = APIRouter(prefix="/tasks", tags=["Задачи"])


@router.post("/personal", response_model=TaskOut)
async def create_personal_task(
    telegram_id: int = Query(gt=0),
    payload: TaskCreateIn = ...,
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=404, detail="User not found. Call /users/upsert first."
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
