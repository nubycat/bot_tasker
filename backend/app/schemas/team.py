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


class TeamJoinByCode(BaseModel):
    join_code: str = Field(min_length=16, max_length=16, pattern=r"^[A-Za-z0-9]{16}$")
    nickname: str = Field(min_length=2, max_length=32)


class TeamJoinIn(BaseModel):
    join_code: str = Field(min_length=3, max_length=64)


class TeamJoinOut(BaseModel):
    team_id: int
    name: str
