from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.team_member import TeamMember


ALPHABET = string.ascii_letters + string.digits  # A-Z a-z 0-9


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _new_join_code(self, length: int = 16) -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(length))

    async def create_team_with_creator(
        self, *, name: str, user_id: int, nickname: str
    ) -> Team:
        if not user_id:
            # это лучше ловить раньше, чем получать 500 из БД
            raise ValueError("user_id is required")

        # правильный подход: НЕ делаем SELECT на уникальность,
        # а полагаемся на UNIQUE-индекс в БД и ретраим только при коллизии.
        last_err: Exception | None = None

        for _ in range(5):  # 5 попыток более чем достаточно
            join_code = self._new_join_code(16)

            team = Team(
                name=name,
                join_code=join_code,
                created_by=user_id,  # <-- ВОТ ЭТО КЛЮЧЕВО
            )
            self.session.add(team)

            try:
                await self.session.flush()  # получаем team.id, может упасть из-за UNIQUE
                member = TeamMember(team_id=team.id, user_id=user_id, nickname=nickname)
                self.session.add(member)

                await self.session.commit()
                await self.session.refresh(team)
                return team

            except IntegrityError as e:
                await self.session.rollback()
                last_err = e
                # если это коллизия join_code (UNIQUE) — пробуем ещё раз
                # если это другая ошибка — пробрасываем дальше
                msg = str(getattr(e, "orig", e))
                if "join_code" in msg or "unique" in msg.lower():
                    continue
                raise

        raise RuntimeError("Failed to generate unique join_code") from last_err

    async def get_team(self, team_id: int) -> Team | None:
        res = await self.session.execute(select(Team).where(Team.id == team_id))
        return res.scalar_one_or_none()

    async def get_member(self, *, team_id: int, user_id: int) -> TeamMember | None:
        res = await self.session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    async def join_team(
        self, *, team_id: int, user_id: int, nickname: str
    ) -> TeamMember:
        existing = await self.get_member(team_id=team_id, user_id=user_id)
        if existing:
            return existing

        member = TeamMember(team_id=team_id, user_id=user_id, nickname=nickname)
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def get_team_by_code(self, join_code: str) -> Team | None:
        res = await self.session.execute(
            select(Team).where(Team.join_code == join_code)
        )
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_join_code(db: AsyncSession, join_code: str) -> Team | None:
        res = await db.execute(select(Team).where(Team.join_code == join_code))
        return res.scalar_one_or_none()

    @staticmethod
    async def ensure_member(db, *, team_id: int, user_id: int, nickname: str) -> None:
        res = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        if res.scalar_one_or_none():
            return

        db.add(TeamMember(team_id=team_id, user_id=user_id, nickname=nickname))
        await db.commit()
