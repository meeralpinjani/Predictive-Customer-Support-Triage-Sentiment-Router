"""Text extraction from customer PDF / DOCX attachments for the integrity review aid.

Safety rules:
- Works on bytes in memory: nothing is written to disk, so there are no temporary files to leak.
- Type is checked by extension, declared MIME type and magic bytes together.
- Limits from configuration: file size, pages, extracted characters, time.
- Encrypted PDFs are refused; DOCX is read with the standard library, bounded against zip bombs,
  and documents with a DOCTYPE (entity tricks) are refused. Macros and embedded objects are never opened.
- Image-only documents return needs_ocr (no OCR is done).
- Extracted text is data only: it is never placed into prompts, templates or instructions.
"""
from __future__ import annotations

import io
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from xml.etree import ElementTree

from app.config import settings

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
STATUSES = ("extracted", "unsupported_type", "too_large", "too_many_pages", "encrypted", "malformed",
            "needs_ocr", "timeout")

# DOCX bounds (zip-bomb guard)
DOCX_MAX_ENTRIES = 500
DOCX_MAX_UNCOMPRESSED = 50 * 1024 * 1024
DOCX_MAX_RATIO = 100
MIN_CHARS_PER_PAGE = 20      # below this a PDF is treated as scanned / image-only

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc-extract")
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Extraction:
    status: str
    kind: str | None = None          # pdf | docx
    text: str = ""
    pages: int | None = None
    truncated: bool = False
    detail: str | None = None
    notes: list[str] = field(default_factory=list)


def is_docx_bytes(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


def detect_kind(filename: str, content_type: str, data: bytes) -> str | None:
    """pdf / docx only when extension, declared type and bytes all agree."""
    name = (filename or "").lower()
    if name.endswith(".pdf") and content_type == PDF_MIME and data.startswith(b"%PDF-"):
        return "pdf"
    if name.endswith(".docx") and content_type == DOCX_MIME and is_docx_bytes(data):
        return "docx"
    return None


def _clip(text: str) -> tuple[str, bool]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    limit = settings.ai_integrity_max_document_chars
    return (text[:limit], True) if len(text) > limit else (text, False)


def _pdf(data: bytes) -> Extraction:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return Extraction("encrypted", "pdf", detail="password-protected PDF")
        pages = len(reader.pages)
    except PdfReadError as exc:
        return Extraction("malformed", "pdf", detail=type(exc).__name__)
    except Exception as exc:  # pypdf raises several error types for broken files
        return Extraction("malformed", "pdf", detail=type(exc).__name__)
    if pages > settings.ai_integrity_max_document_pages:
        return Extraction("too_many_pages", "pdf", pages=pages)
    parts = []
    try:
        for page in reader.pages:
            parts.append(page.extract_text() or "")
    except Exception as exc:
        return Extraction("malformed", "pdf", pages=pages, detail=type(exc).__name__)
    text, truncated = _clip("\n".join(parts))
    if len(text) < MIN_CHARS_PER_PAGE * max(pages, 1):
        return Extraction("needs_ocr", "pdf", text=text, pages=pages,
                          detail="little or no extractable text (scanned or image-only); could not be fully analysed")
    return Extraction("extracted", "pdf", text=text, pages=pages, truncated=truncated)


def _docx(data: bytes) -> Extraction:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > DOCX_MAX_ENTRIES:
                return Extraction("malformed", "docx", detail="too many entries")
            total = sum(i.file_size for i in infos)
            packed = max(sum(i.compress_size for i in infos), 1)
            if total > DOCX_MAX_UNCOMPRESSED or total / packed > DOCX_MAX_RATIO:
                return Extraction("too_large", "docx", detail="uncompressed size or compression ratio over the limit")
            info = z.getinfo("word/document.xml")
            if info.file_size > DOCX_MAX_UNCOMPRESSED:
                return Extraction("too_large", "docx", detail="document part too large")
            with z.open(info) as f:
                xml = f.read(DOCX_MAX_UNCOMPRESSED + 1)
    except (zipfile.BadZipFile, KeyError, RuntimeError) as exc:   # RuntimeError: encrypted zip entries
        return Extraction("malformed", "docx", detail=type(exc).__name__)
    if b"<!DOCTYPE" in xml[:4096].upper() or b"<!ENTITY" in xml.upper():
        return Extraction("malformed", "docx", detail="document type declarations are not allowed")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        return Extraction("malformed", "docx", detail=type(exc).__name__)
    paragraphs = []
    for p in root.iter(f"{W_NS}p"):
        runs = [t.text or "" for t in p.iter(f"{W_NS}t")]
        if runs:
            paragraphs.append("".join(runs))
    text, truncated = _clip("\n".join(paragraphs))
    if len(text) < MIN_CHARS_PER_PAGE:
        return Extraction("needs_ocr", "docx", text=text, detail="little or no text; could not be fully analysed")
    return Extraction("extracted", "docx", text=text, truncated=truncated)


def extract(filename: str, content_type: str, data: bytes, timeout: float | None = None) -> Extraction:
    if len(data) > settings.ai_integrity_max_file_size_mb * 1024 * 1024:
        return Extraction("too_large", detail=f"over {settings.ai_integrity_max_file_size_mb} MB")
    kind = detect_kind(filename, content_type, data)
    if kind is None:
        return Extraction("unsupported_type", detail="only PDF and DOCX are analysed")
    future = _pool.submit(_pdf if kind == "pdf" else _docx, data)
    try:
        return future.result(timeout=timeout or settings.ai_integrity_extraction_timeout_seconds)
    except FutureTimeout:
        return Extraction("timeout", kind, detail="extraction took too long; could not be fully analysed")
    except Exception as exc:  # never let a bad document break the assessment
        return Extraction("malformed", kind, detail=type(exc).__name__)
