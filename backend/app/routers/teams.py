from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository.teams import TeamRepository
from app.repository.users import UserRepository
from app.schemas.team import (
    TeamCreate,
    TeamOut,
    TeamJoin,
    TeamMemberOut,
    TeamJoinByCode,
    TeamJoinIn,
    TeamJoinOut,
)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamOut)
async def create_team(
    payload: TeamCreate,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):

    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if not user:
        # вариант 1 (строго): просим сначала /users/upsert
        raise HTTPException(
            status_code=400, detail="User not found. Call /users/upsert first."
        )

        # вариант 2 (мягко): auto-upsert (если хочешь так)
        # user = await UserRepository.upsert(db, telegram_id=telegram_id, username=None, first_name=payload.nickname)

    repo = TeamRepository(db)
    try:
        team = await repo.create_team_with_creator(
            name=payload.name,
            user_id=user.id,
            nickname=payload.nickname,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return team


@router.post("/{team_id}/join", response_model=TeamMemberOut)
async def join_team(
    team_id: int,
    payload: TeamJoin,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    repo = TeamRepository(db)

    team = await repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    member = await repo.join_team(
        team_id=team_id,
        user_id=user.id,
        nickname=payload.nickname,
    )
    return member


@router.get("/{team_id}/me", response_model=TeamMemberOut)
async def get_my_membership(
    team_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    repo = TeamRepository(db)
    member = await repo.get_member(team_id=team_id, user_id=user.id)
    if not member:
        raise HTTPException(status_code=404, detail="Not a team member")

    return member


@router.post("/join-by-code", response_model=TeamMemberOut)
async def join_team_by_code(
    payload: TeamJoinByCode,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    repo = TeamRepository(db)

    team = await repo.get_team_by_code(payload.join_code)
    if not team:
        raise HTTPException(status_code=404, detail="Invalid join_code")

    member = await repo.join_team(
        team_id=team.id,
        user_id=user.id,
        nickname=payload.nickname,
    )
    return member


@router.post("/{team_id}/activate")
async def activate_team(
    team_id: int,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    repo = TeamRepository(db)
    member = await repo.get_member(team_id=team_id, user_id=user.id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a team member")

    user.active_team_id = team_id
    await db.commit()
    await db.refresh(user)
    return {"active_team_id": user.active_team_id}


@router.post("/deactivate")
async def deactivate_team(
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Call /users/upsert first.",
        )

    user.active_team_id = None
    await db.commit()
    await db.refresh(user)
    return {"active_team_id": None}


@router.post("/join", response_model=TeamJoinOut)
async def join_team(
    payload: TeamJoinIn,
    telegram_id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    user = await UserRepository.get_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    team = await TeamRepository.get_by_join_code(db, payload.join_code)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    await TeamRepository.ensure_member(db, team_id=team.id, user_id=user.id)

    return {"team_id": team.id, "name": team.name}
