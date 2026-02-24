from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamMember(Base):
    __tablename__ = "team_members"

    __table_args__ = (
        # один пользователь не может вступить дважды в одну команду
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        # ник уникален внутри команды (по твоей логике "Done | Alex")
        UniqueConstraint("team_id", "nickname", name="uq_team_members_team_nickname"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    nickname: Mapped[str] = mapped_column(String(64))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
