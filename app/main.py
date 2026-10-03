import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, materials, users
from app.core.config import settings
from app.db import models  # noqa: F401  (registers tables on Base)
from app.db.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AI Learning Material Analyzer",
    description="Upload PDF learning material, then get an AI summary and quiz. OCR is used for scanned PDFs.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Users", "description": "Create accounts"},
        {"name": "Authentication", "description": "Log in and get a JWT"},
        {"name": "Materials", "description": "Upload PDFs, summaries and quizzes (login required)"},
    ],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(materials.router)
