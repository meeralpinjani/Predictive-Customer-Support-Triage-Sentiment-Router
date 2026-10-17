"""Shared helpers for the offline evaluation scripts."""
import json
from functools import lru_cache
from pathlib import Path
import time

import pandas as pd

from app.config import settings
from app.nlp.analyzer import analyse
from app.nlp.kb import MiniLmKb, TfidfKb
from app.nlp.rules import Analysis

DATA = Path(__file__).resolve().parent.parent / "data"
MODES = ("rules", "hf")


def labelled(split: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(DATA / "tickets_labelled.csv")
    return df if split is None else df[df["split"] == split].reset_index(drop=True)


def kb_articles() -> list[dict]:
    return json.loads((DATA / "kb_articles.json").read_text(encoding="utf-8"))


def customers() -> list[dict]:
    return json.loads((DATA / "customers.json").read_text(encoding="utf-8"))


def set_mode(mode: str) -> bool:
    """Switch the analyser to `mode`. Returns False if HF models cannot be loaded."""
    settings.nlp_mode = mode
    if mode == "hf":
        from app.nlp import hf
        hf.warmup(background=False)
        return hf.ready()
    return True


@lru_cache(maxsize=2)
def kb_for(mode: str):
    return MiniLmKb(kb_articles()) if mode == "hf" else TfidfKb(kb_articles())


def analyse_all(texts: list[str], mode: str) -> tuple[list[Analysis], list[float]]:
    """Analyses plus per-ticket latency in ms (NLP + KB lookup, i.e. the request's model work)."""
    set_mode(mode)
    kb = kb_for(mode)
    out, ms = [], []
    for t in texts:
        start = time.perf_counter()
        a = analyse(t)
        kb.match(t)
        ms.append((time.perf_counter() - start) * 1000)
        out.append(a)
    return out, ms
