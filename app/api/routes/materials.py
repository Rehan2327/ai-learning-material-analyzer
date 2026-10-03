import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.db.models import Material, User
from app.schemas.material import MaterialOut, Quiz, QuizResponse, SummaryResponse
from app.services import ai_service, pdf_service, quiz_service
from app.services.ocr_service import OcrError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/materials", tags=["Materials"])


def get_owned_material(material_id: int, user: User, db: Session) -> Material:
    """Return the material only if it belongs to the user (404 otherwise)."""
    material = db.scalar(
        select(Material).where(Material.id == material_id, Material.owner_id == user.id)
    )
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    return material


def load_text(material: Material, db: Session) -> str:
    """Return the material's text, extracting (and OCR-ing if needed) only once."""
    if material.extracted_text:
        return material.extracted_text
    try:
        result = pdf_service.extract_text(material.file_path, settings.max_ocr_pages)
    except pdf_service.PdfProcessingError as exc:
        raise HTTPException(422, str(exc))
    except OcrError as exc:
        logger.error("OCR error: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    material.extracted_text = result.text
    material.used_ocr = result.used_ocr
    db.commit()
    return result.text


@router.post("/upload", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def upload_material(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Material:
    """Upload a PDF (max size set by MAX_UPLOAD_MB)."""
    original_name = os.path.basename(file.filename or "")
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only .pdf files are allowed")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            413,
            f"File is larger than {settings.max_upload_mb} MB",
        )
    if not content.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File is not a valid PDF")

    os.makedirs(settings.upload_dir, exist_ok=True)
    disk_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.pdf")
    with open(disk_path, "wb") as saved:
        saved.write(content)

    material = Material(owner_id=user.id, filename=original_name[:255], file_path=disk_path)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.post("/{material_id}/summary", response_model=SummaryResponse)
def summarize_material(
    material_id: int,
    regenerate: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """Extract text (OCR only if needed) and return an AI summary. Cached after the first call."""
    material = get_owned_material(material_id, user, db)
    if material.summary and not regenerate:
        return SummaryResponse(
            material_id=material.id, used_ocr=material.used_ocr, cached=True, summary=material.summary
        )
    text = load_text(material, db)
    try:
        material.summary = ai_service.summarize(text)
    except ai_service.AIServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    db.commit()
    return SummaryResponse(
        material_id=material.id, used_ocr=material.used_ocr, cached=False, summary=material.summary
    )


@router.post("/{material_id}/quiz", response_model=QuizResponse)
def quiz_material(
    material_id: int,
    regenerate: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizResponse:
    """Generate a multiple-choice quiz from the PDF. Cached after the first call."""
    material = get_owned_material(material_id, user, db)
    cached = bool(material.quiz_json) and not regenerate
    if cached:
        quiz = Quiz.model_validate_json(material.quiz_json)
    else:
        text = load_text(material, db)
        try:
            quiz = quiz_service.generate_quiz(text)
        except ai_service.AIServiceError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
        material.quiz_json = quiz.model_dump_json()
        db.commit()
    return QuizResponse(
        material_id=material.id, used_ocr=material.used_ocr, cached=cached, questions=quiz.questions
    )
