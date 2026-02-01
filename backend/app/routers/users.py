from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.users import UserRepository
from app.schemas.user import UserUpsertIn, UserOut

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.post("/upsert", response_model=UserOut)
async def upsert_user(payload: UserUpsertIn, db: AsyncSession = Depends(get_db)):
    return await UserRepository.upsert(
        db, payload.telegram_id, payload.username, payload.first_name
    )
