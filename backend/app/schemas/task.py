from datetime import datetime
from pydantic import BaseModel, Field


class TaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    due_at: datetime | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str | None
    due_at: datetime | None
    status: str
    owner_user_id: int
    created_by: int

    class Config:
        from_attributes = True
