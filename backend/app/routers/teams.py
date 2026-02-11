from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.repository.teams import TeamRepository
from app.schemas.team import TeamCreate, TeamOut, TeamJoin, TeamMemberOut

# ВАЖНО:
# Здесь нет  способа "получить текущего пользователя".
# Поэтому  зависимость-заглушку, временно

router = APIRouter(prefix="/teams", tags=["teams"])


def get_current_user_id() -> int:
    """
    ЗАГЛУШКА.
    Заменить на реальную авторизацию/идентификацию пользователя (telegram_id -> user_id).
    """
    raise NotImplementedError("Wire current user dependency here")


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id),
):
    repo = TeamRepository(session)
    team = await repo.create_team_with_creator(
        name=payload.name,
        user_id=user_id,
        nickname=payload.nickname,
    )
    return team


@router.post("/{team_id}/join", response_model=TeamMemberOut)
async def join_team(
    team_id: int,
    payload: TeamJoin,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id),
):
    repo = TeamRepository(session)

    team = await repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    member = await repo.join_team(
        team_id=team_id, user_id=user_id, nickname=payload.nickname
    )
    return member


@router.get("/{team_id}/me", response_model=TeamMemberOut)
async def get_my_membership(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id),
):
    repo = TeamRepository(session)

    member = await repo.get_member(team_id=team_id, user_id=user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Not a team member")

    return member
