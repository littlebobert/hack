from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .schemas import ExtractionResponse, RenderRequest, RenderResponse
from .services.anthropic_extractor import extract_form_from_image
from .services.renderer import render_filled_form

def configure_cors(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = FastAPI(title="Form Builder Backend", version="0.1.0")
configure_cors(app, get_settings())


@app.on_event("startup")
async def startup_event() -> None:
    storage_path = Path("storage/uploads")
    storage_path.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: Annotated[UploadFile, File(...)],
    settings: Settings = Depends(get_settings),
) -> ExtractionResponse:
    if not file.content_type or "image" not in file.content_type:
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    unique_id = uuid.uuid4().hex
    storage_dir = Path("storage/uploads")
    storage_dir.mkdir(parents=True, exist_ok=True)

    destination = storage_dir / f"{unique_id}_{file.filename}"
    contents = await file.read()
    destination.write_bytes(contents)

    try:
        image_b64 = base64.b64encode(contents).decode("utf-8")
        document = await extract_form_from_image(
            image_b64=image_b64,
            file_name=file.filename or "uploaded_form",
            settings=settings,
            storage_path=str(destination),
        )
        return ExtractionResponse(document=document)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.exception_handler(Exception)
async def fallback_exception_handler(_, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.post("/render", response_model=RenderResponse)
async def render_form(request: RenderRequest) -> RenderResponse:
    try:
        image_b64 = render_filled_form(request.document, request.values)
        return RenderResponse(image_base64=image_b64)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

