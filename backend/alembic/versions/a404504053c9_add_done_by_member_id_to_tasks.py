"""add done_by_member_id to tasks

Revision ID: a404504053c9
Revises: 6dcccaab6bc7
Create Date: 2026-02-21 16:40:17.467562

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a404504053c9"
down_revision: Union[str, None] = "6dcccaab6bc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("done_by_member_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_tasks_done_by_member_id"),
        "tasks",
        ["done_by_member_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_tasks_done_by_member_id_team_members"),
        "tasks",
        "team_members",
        ["done_by_member_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_tasks_done_by_member_id_team_members"), "tasks", type_="foreignkey"
    )
    op.drop_index(op.f("ix_tasks_done_by_member_id"), table_name="tasks")
    op.drop_column("tasks", "done_by_member_id")
