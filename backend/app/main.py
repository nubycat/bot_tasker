from fastapi import FastAPI

from app.routers.users import router as users_router
from app.routers.tasks import router as tasks_router
from app.routers.teams import router as teams_router
from app.routers.teams import router as teams_router


app = FastAPI(title="Tasker Backend")

app.include_router(users_router)
app.include_router(tasks_router)
app.include_router(teams_router)
app.include_router(teams_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
