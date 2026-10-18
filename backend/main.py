import asyncio
from contextlib import asynccontextmanager

from agents.main_agent import ping_agent_service
from database import models as user_models
from database.connection import Base as UserBase
from database.connection import engine as db_engine
from datapool import models as datapool_models
from datapool.connection import Base as DataPoolBase
from datapool.connection import engine as dp_engine
from fastapi import FastAPI
from routers.agent import router as agent_router
from routers.auth import router as auth_router
from routers.datapool import router as datapool_router
from routers.skills import router as skills_router
from routers.urls import router as urls_router
from routers.users import router as users_router
from routers.webhooks import router as webhooks_router
from services.quest_expiry import quest_expiry_loop
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app: FastAPI):
    UserBase.metadata.create_all(bind=db_engine)
    DataPoolBase.metadata.create_all(bind=dp_engine)

    agent_status = ping_agent_service()
    app.state.agent_status = agent_status
    #this is to check quest expiry repeatditly
    expiry_task = asyncio.create_task(quest_expiry_loop())

    try:
        yield
    finally:
        # Stop the background task before shutdown.
        expiry_task.cancel()

        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

        db_engine.dispose()
        dp_engine.dispose()


app = FastAPI(
    title="AI Skill Sense Backend",
    lifespan=lifespan,
)
app.include_router(urls_router)
app.include_router(users_router)
app.include_router(skills_router)
app.include_router(datapool_router)
app.include_router(agent_router)
app.include_router(auth_router)
app.include_router(webhooks_router)


@app.get("/")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health_check():
    with db_engine.connect() as connection:
        db_result = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()

    with dp_engine.connect() as connection:
        dp_result = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()

    return {
        "status": "connected",
        "database": db_result,
        "datapool": dp_result,
    }
