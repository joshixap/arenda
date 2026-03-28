from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.database import create_tables, engine
from shared.models import Base
from user_service.routers import auth, favorites, subscriptions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(Base)
    yield
    await engine.dispose()


app = FastAPI(title="User Service", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(favorites.router)
app.include_router(subscriptions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
