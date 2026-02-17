from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.core.time_utils import normalize_time_hhmm


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


class TaskCreateFromBotIn(BaseModel):
    """
    Схема входных данных для создания задачи из Telegram-бота.

    Почему отдельная схема:
    - TaskCreateIn использует due_at (полный datetime)
    - бот присылает только время remind_at строкой: "18" или "18:30 или 1830"
      (нормализуется через normalize_time_hhmm)

    Дополнительно бот присылает telegram_id и данные профиля.
    """

    telegram_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1500)
    remind_at: str = Field(min_length=1, max_length=5)  # "18" or "18:30"
    username: str | None = Field(default=None, max_length=64)
    first_name: str | None = Field(default=None, max_length=64)

    @field_validator("remind_at")
    @classmethod
    def validate_remind_at(cls, v: str) -> str:
        # "18" -> "18:00", "8:3" -> "08:03", "1830" -> "18:30"
        return normalize_time_hhmm(v)


class TodayTasksOut(BaseModel):
    """
    TodayTasksOut — схема ответа для эндпоинта "задачи на сегодня".

    Поля:
    - open: список невыполненных задач (TaskOut)
    - done: список выполненных задач (TaskOut)

    Если задач нет — возвращаются пустые списки [].
    """

    open: list[TaskOut]
    done: list[TaskOut]
