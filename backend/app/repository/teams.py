import secrets
import string
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.team_member import TeamMember

ALPHABET = string.ascii_letters + string.digits  # A-Z a-z 0-9


def generate_join_code(length: int = 16) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_team_with_creator(
        self, *, name: str, user_id: int, nickname: str
    ) -> Team:
        last_err: Exception | None = None

        for _ in range(5):
            team = Team(name=name, join_code=generate_join_code(16))
            self.session.add(team)

            try:
                await self.session.flush()  # assign team.id

                self.session.add(
                    TeamMember(team_id=team.id, user_id=user_id, nickname=nickname)
                )

                await self.session.commit()
                await self.session.refresh(team)
                return team

            except IntegrityError as e:
                await self.session.rollback()
                last_err = e
                # В проде можно проверить, что это именно conflict по join_code constraint.
                # Здесь retry допустим: join_code уникален, коллизии крайне редкие.

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

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # гонка: другой запрос успел создать membership
            existing = await self.get_member(team_id=team_id, user_id=user_id)
            if existing:
                return existing
            raise

        await self.session.refresh(member)
        return member
