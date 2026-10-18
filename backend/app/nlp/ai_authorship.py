"""AI-writing detector for the integrity review aid (admins only).

Wraps the local `rasbt/ai-text-detector-modernbert` model (see docs/integrity/MODEL_VERIFICATION.md).
- Loaded once, lazily, behind a lock, from AI_INTEGRITY_MODEL_PATH (configuration only).
- The AI class index is read from the model's own config and cross-checked; if it can't be
  verified the detector reports model_unavailable / label_mapping_unverified instead of guessing.
- Long text is split into overlapping token windows; the mean and max window scores are both
  reported and the mean is used for decisions.
- One inference at a time, in a single worker thread, with a hard deadline for the caller.
- Never calls an external API. The score is a "detector score", not a probability.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.nlp.rules import detect_language

log = logging.getLogger("triage.integrity.detector")

MODEL_NAME = "rasbt/ai-text-detector-modernbert"
STATUSES = ("not_assessed", "insufficient_text", "unsupported_language", "model_unavailable", "assessed")
LIMITATIONS = [
    "Trained on English text that differs from support tickets; out of domain here.",
    "Formal, templated, translated or non-native English can score high without any AI use.",
    "Short or partly AI-assisted text is hard to classify.",
    "A detector score is not a probability and is never evidence on its own.",
]


@dataclass
class AuthorshipResult:
    status: str
    score: float | None = None          # mean of window scores (used for decisions)
    score_max: float | None = None
    model_name: str = MODEL_NAME
    model_version: str | None = None
    chunk_count: int = 0
    word_count: int = 0
    reason: str | None = None
    limitations: list[str] = field(default_factory=lambda: list(LIMITATIONS))


# ---------------------------------------------------------------- text checks
def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def language_supported(text: str) -> bool:
    """English only: Hindi / Hinglish (existing detector) and mostly non-Latin text are unsupported."""
    if detect_language(text) != "en":
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if c.isascii())
    return latin / len(letters) >= 0.8


def chunk_windows(ids: list[int], size: int, overlap: int, max_chunks: int) -> tuple[list[list[int]], bool]:
    """Overlapping windows over token ids. Returns (windows, truncated)."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and larger than the overlap")
    if not ids:
        return [], False
    step = size - overlap
    windows, start = [], 0
    while start < len(ids):
        windows.append(ids[start:start + size])
        if start + size >= len(ids):
            break
        start += step
    truncated = len(windows) > max_chunks
    return windows[:max_chunks], truncated


# ---------------------------------------------------------------- backends
class UnavailableBackend:
    """Used when the model can't be loaded or verified: every call reports model_unavailable."""
    version = None

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def score_windows(self, text: str) -> tuple[list[float], bool]:
        raise RuntimeError(self.reason)


def verify_label_mapping(model_dir: Path) -> int:
    """Index of the AI class from config.json id2label, cross-checked with detector-config.json.
    Raises ValueError("label_mapping_unverified") when missing, ambiguous or inconsistent."""
    try:
        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("label_mapping_unverified") from exc
    id2label = cfg.get("id2label") or {}
    ai = [int(i) for i, name in id2label.items() if str(name).strip().upper() == "AI"]
    if len(ai) != 1 or len(id2label) != 2:
        raise ValueError("label_mapping_unverified")
    det = model_dir / "detector-config.json"
    if det.exists():
        try:
            mapping = json.loads(det.read_text(encoding="utf-8")).get("label_mapping", {})
        except ValueError as exc:
            raise ValueError("label_mapping_unverified") from exc
        if "ai" in mapping and int(mapping["ai"]) != ai[0]:
            raise ValueError("label_mapping_unverified")
    return ai[0]


class ModernBertBackend:
    def __init__(self, model_dir: Path) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.ai_index = verify_label_mapping(model_dir)
        meta = {}
        if (model_dir / "detector-config.json").exists():
            meta = json.loads((model_dir / "detector-config.json").read_text(encoding="utf-8"))
        self.temperature = float(meta.get("temperature", 1.0)) or 1.0
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()
        if str(self.model.config.id2label.get(self.ai_index, "")).upper() != "AI":   # loaded config must agree too
            raise ValueError("label_mapping_unverified")
        # Special tokens the tokenizer adds around a text (e.g. [CLS] ... [SEP]), learned from a probe,
        # so each window is framed exactly like a normal tokenizer call.
        full = self.tokenizer("probe text")["input_ids"]
        plain = self.tokenizer("probe text", add_special_tokens=False)["input_ids"]
        start = next((i for i in range(len(full) - len(plain) + 1) if full[i:i + len(plain)] == plain), None)
        if start is None:
            raise ValueError("tokenizer_special_tokens_unverified")
        self.prefix, self.suffix = full[:start], full[start + len(plain):]
        max_len = int(getattr(self.model.config, "max_position_embeddings", 512))
        if settings.ai_integrity_chunk_size + len(self.prefix) + len(self.suffix) > max_len:
            raise ValueError("chunk_size_exceeds_model_max_length")
        self.torch = torch
        self.version = (meta.get("best_checkpoint") or "") + "@" + _revision(model_dir)

    def score_windows(self, text: str) -> tuple[list[float], bool]:
        tok = self.tokenizer
        ids = tok(text, add_special_tokens=False)["input_ids"]
        windows, truncated = chunk_windows(ids, settings.ai_integrity_chunk_size,
                                           settings.ai_integrity_chunk_overlap, settings.ai_integrity_max_chunks)
        scores = []
        with self.torch.inference_mode():
            for w in windows:
                ids_t = self.torch.tensor([self.prefix + w + self.suffix])
                logits = self.model(input_ids=ids_t, attention_mask=self.torch.ones_like(ids_t)).logits
                probs = (logits / self.temperature).float().softmax(dim=-1)[0]
                scores.append(float(probs[self.ai_index]))
        return scores, truncated


def _revision(model_dir: Path) -> str:
    """The pinned Hub revision written by scripts/download_integrity_model.py, if present."""
    try:
        return (model_dir / "REVISION").read_text(encoding="utf-8").strip()[:40]
    except OSError:
        return "local"


# ---------------------------------------------------------------- detector
class AuthorshipDetector:
    """Lazy, thread-safe singleton around one backend."""

    def __init__(self, backend=None) -> None:
        self._backend = backend
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-detector")

    def backend(self):
        if self._backend is None:
            with self._load_lock:
                if self._backend is None:
                    self._backend = load_backend()
        return self._backend

    def _run(self, text: str):
        with self._infer_lock:
            return self.backend().score_windows(text)

    def assess(self, text: str, timeout: float | None = None) -> AuthorshipResult:
        text = normalise(text)
        words = word_count(text)
        if not text or words < settings.ai_integrity_min_words:
            return AuthorshipResult("insufficient_text", word_count=words,
                                    reason=f"fewer than {settings.ai_integrity_min_words} words")
        if not language_supported(text):
            return AuthorshipResult("unsupported_language", word_count=words, reason="detector supports English only")
        backend = self.backend()
        if isinstance(backend, UnavailableBackend):
            return AuthorshipResult("model_unavailable", word_count=words, reason=backend.reason)
        future = self._pool.submit(self._run, text)
        try:
            scores, truncated = future.result(timeout=timeout or settings.ai_integrity_timeout_seconds)
        except FutureTimeout:
            # A CPU-bound call can't be killed in-process: stop waiting and discard the late result.
            return AuthorshipResult("model_unavailable", word_count=words, reason="timeout",
                                    model_version=getattr(backend, "version", None))
        except Exception as exc:  # the detector must never break the caller
            log.warning("Detector error: %s", type(exc).__name__)
            return AuthorshipResult("model_unavailable", word_count=words, reason="detector_error",
                                    model_version=getattr(backend, "version", None))
        if not scores:
            return AuthorshipResult("insufficient_text", word_count=words, reason="no tokens")
        result = AuthorshipResult(
            "assessed", score=round(sum(scores) / len(scores), 4), score_max=round(max(scores), 4),
            model_version=getattr(backend, "version", None), chunk_count=len(scores), word_count=words,
        )
        if truncated:
            result.limitations.append(f"Only the first {settings.ai_integrity_max_chunks} windows were scored.")
        return result


def load_backend():
    path = settings.ai_integrity_model_path.strip()
    if not path:
        return UnavailableBackend("model_path_not_configured")
    model_dir = Path(path)
    if not model_dir.is_dir() or not (model_dir / "config.json").exists():
        return UnavailableBackend("model_path_invalid")
    try:
        return ModernBertBackend(model_dir)
    except ValueError as exc:
        return UnavailableBackend(str(exc) if str(exc) else "model_load_failed")
    except Exception as exc:  # missing packages, corrupt weights...
        log.warning("Integrity detector unavailable: %s", type(exc).__name__)
        return UnavailableBackend("model_load_failed")


_detector: AuthorshipDetector | None = None
_detector_lock = threading.Lock()


def get_detector() -> AuthorshipDetector:
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = AuthorshipDetector()
    return _detector


def set_detector(detector: AuthorshipDetector | None) -> None:
    """Swap the detector (tests, or after the model path changes)."""
    global _detector
    with _detector_lock:
        _detector = detector


def startup_check() -> str:
    """Validate the configured model directory at start-up without loading the weights."""
    path = settings.ai_integrity_model_path.strip()
    if not path:
        return "model_path_not_configured"
    model_dir = Path(path)
    if not model_dir.is_dir() or not (model_dir / "config.json").exists():
        log.warning("AI_INTEGRITY_MODEL_PATH is not a model directory; the detector will report model_unavailable")
        return "model_path_invalid"
    try:
        verify_label_mapping(model_dir)
    except ValueError:
        log.warning("Integrity detector label mapping could not be verified; it will report model_unavailable")
        return "label_mapping_unverified"
    return "ok"
