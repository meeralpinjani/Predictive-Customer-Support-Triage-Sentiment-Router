import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from app.config import settings
from app.nlp.rules import Analysis, analyse_rules

log = logging.getLogger("triage.nlp")
_pool = ThreadPoolExecutor(max_workers=2)


def analyse(text: str) -> Analysis:
    base = analyse_rules(text)
    if settings.nlp_mode != "hf":
        return base
    try:
        from app.nlp import hf
        fr = _pool.submit(hf.frustration_hf, text, base.frustration).result(timeout=settings.hf_timeout_sec)
        return replace(base, frustration=fr, mode="hf", confidence=0.8)
    except Exception as exc:  # model missing, timeout, runtime error
        log.warning("HF analysis failed, using rules: %s", exc)
        return base
