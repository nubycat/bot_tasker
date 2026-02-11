from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=4, max_length=64)
    nickname: str = Field(min_length=4, max_length=32)


class TeamOut(BaseModel):
    id: int
    name: str
    join_code: str

    class Config:
        from_attributes = True


class TeamJoin(BaseModel):
    nickname: str = Field(min_length=4, max_length=32)


class TeamMemberOut(BaseModel):
    team_id: int
    user_id: int
    nickname: str

    class Config:
        from_attributes = True
