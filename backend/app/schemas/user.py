from pydantic import BaseModel, Field


class UserUpsertIn(BaseModel):
    telegram_id: int = Field(gt=0)
    username: str | None = None
    first_name: str | None = None


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None

    class Config:
        from_attributes = True
