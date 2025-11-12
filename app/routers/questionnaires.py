"""Questionnaire OCR endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from ..dependencies import get_parser_service
from ..schemas import ParseResponse
from ..services.openai_parser import OpenAIQuestionnaireParser, ParserError

router = APIRouter(prefix="/questionnaires", tags=["questionnaires"])


@router.post(
    "/parse",
    response_model=ParseResponse,
    summary="Parse questionnaire image",
    status_code=status.HTTP_200_OK,
)
async def parse_questionnaire(
    file: UploadFile = File(...),
    include_debug: bool = Query(
        default=False,
        description="Return OCR debug blocks with line-level confidences.",
    ),
    parser: OpenAIQuestionnaireParser = Depends(get_parser_service),
) -> ParseResponse:
    """Accept image upload and return structured questionnaire JSON."""
    try:
        return await parser.parse_upload(file, include_debug=include_debug)
    except ParserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while parsing questionnaire.",
        ) from exc
