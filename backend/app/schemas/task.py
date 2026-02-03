from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.core.time_utils import normalize_time_hhmm


class TaskCreateFromBotIn(BaseModel):
    telegram_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    remind_at: str

    @field_validator("remind_at")
    @classmethod
    def validate_remind_at(cls, v: str) -> str:
        # превращает "18" -> "18:00", "8:3" -> "08:03"
        return normalize_time_hhmm(v)


class TaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1500)
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


#
class TaskCreateFromBotIn(BaseModel):
    """
    Input-схема для создания задачи из Telegram-бота.

    Отличается от TaskCreateIn: бот присылает только время (remind_at),
    а не полный datetime (due_at).
    """

    telegram_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1500)
    remind_at: str = Field(min_length=1, max_length=5)
    username: str | None = Field(default=None, max_length=64)
    first_name: str | None = Field(default=None, max_length=64)
