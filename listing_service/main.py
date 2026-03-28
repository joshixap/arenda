from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.database import create_tables, engine
from shared.models import Base
from listing_service.routers import listings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables(Base)
    yield
    await engine.dispose()


app = FastAPI(title="Listing Service", lifespan=lifespan)
app.include_router(listings.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
