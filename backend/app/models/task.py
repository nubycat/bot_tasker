from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="todo")

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # NEW: team scope
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True,
    )

    # NEW: who completed task (team member)
    done_by_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("team_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    done_by_member: Mapped["TeamMember | None"] = relationship(
        "TeamMember",
        lazy="selectin",
        foreign_keys=[done_by_member_id],
    )

    @property
    def done_by_nickname(self) -> str | None:
        return self.done_by_member.nickname if self.done_by_member else None
