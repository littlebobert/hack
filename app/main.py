"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import questionnaires, system


def create_app() -> FastAPI:
    """Instantiate and configure FastAPI server."""
    app = FastAPI(
        title="Questionnaire Parser API",
        version="0.1.0",
        description="Upload questionnaire photos and receive structured JSON answers parsed via OpenAI OCR.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system.router)
    app.include_router(questionnaires.router, prefix="/api/v1")
    return app


app = create_app()
