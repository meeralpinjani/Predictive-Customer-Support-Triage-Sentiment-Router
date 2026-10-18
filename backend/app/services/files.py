"""Attachment storage. Files are checked by their actual bytes (not the extension), stored in the
database under a random name, and only ever served through an authorised API endpoint."""
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Attachment
from app.nlp.document_extractor import DOCX_MIME, is_docx_bytes

# Magic bytes -> (content type, extension). SVG is deliberately not allowed (it can carry scripts).
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"%PDF-", "application/pdf", "pdf"),
]


def _sniff(data: bytes) -> tuple[str, str] | None:
    for sig, ctype, ext in SIGNATURES:
        if data.startswith(sig):
            return ctype, ext
    if is_docx_bytes(data):   # a ZIP that really is a Word document (not any ZIP)
        return DOCX_MIME, "docx"
    return None


def _clean_name(name: str | None) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip() or "file"
    return base[:120]


async def save_uploads(db: Session, files: list[UploadFile], ticket_id: int, uploader_id: int,
                       message_id: int | None = None) -> list[Attachment]:
    if len(files) > settings.max_files_per_message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"At most {settings.max_files_per_message} files at a time")
    limit = settings.max_upload_mb * 1024 * 1024
    staged: list[tuple[bytes, str, str, str]] = []
    for f in files:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413,
                                f"{_clean_name(f.filename)} is larger than {settings.max_upload_mb} MB")
        if not data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{_clean_name(f.filename)} is empty")
        kind = _sniff(data)
        if not kind:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                f"{_clean_name(f.filename)}: only PNG, JPG, PDF and DOCX files are allowed")
        staged.append((data, kind[0], kind[1], _clean_name(f.filename)))

    saved = []
    for data, ctype, ext, name in staged:
        att = Attachment(ticket_id=ticket_id, message_id=message_id, uploader_id=uploader_id, filename=name,
                         stored_name=f"{secrets.token_hex(16)}.{ext}", content_type=ctype, size=len(data),
                         content=data)
        db.add(att)
        saved.append(att)
    db.flush()
    return saved


def read_content(att: Attachment) -> bytes:
    if att.content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return att.content


def attachment_out(att: Attachment) -> dict:
    return {"id": att.id, "filename": att.filename, "content_type": att.content_type, "size": att.size,
            "url": f"/api/attachments/{att.id}", "is_image": att.content_type.startswith("image/")}
