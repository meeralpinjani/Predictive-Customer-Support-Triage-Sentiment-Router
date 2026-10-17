import json
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("triage.kb")


@dataclass
class KbMatch:
    article_id: str
    title: str
    answer: str
    source: str
    confidence: float


class TfidfKb:
    def __init__(self, articles: list[dict[str, Any]]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.articles = articles
        docs: list[str] = []
        for a in articles:
            qs = a.get("questions", [])
            if isinstance(qs, str):
                try:
                    qs = json.loads(qs)
                except Exception:
                    qs = [qs]
            docs.append(a["title"] + ". " + " ".join(qs))
        if docs:
            self.vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            self.matrix = self.vec.fit_transform(docs)
        else:
            self.vec = None
            self.matrix = None

    def match(self, text: str) -> KbMatch | None:
        from sklearn.metrics.pairwise import cosine_similarity
        if not self.articles or self.matrix is None or self.vec is None:
            return None
        sims = cosine_similarity(self.vec.transform([text]), self.matrix)[0]
        i = int(sims.argmax())
        a = self.articles[i]
        return KbMatch(
            article_id=a["id"],
            title=a["title"],
            answer=a["answer"],
            source=a.get("source", "Help Center"),
            confidence=round(float(sims[i]), 3),
        )


class MiniLmKb:
    def __init__(self, articles: list[dict[str, Any]]) -> None:
        from sentence_transformers import SentenceTransformer
        self.articles = articles
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        docs: list[str] = []
        for a in articles:
            qs = a.get("questions", [])
            if isinstance(qs, str):
                try:
                    qs = json.loads(qs)
                except Exception:
                    qs = [qs]
            docs.append(a["title"] + ". " + " ".join(qs))
        self.vecs = self.model.encode(docs, convert_to_tensor=True, normalize_embeddings=True)

    def match(self, text: str) -> KbMatch | None:
        from sentence_transformers import util
        if not self.articles:
            return None
        q = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        sims = util.cos_sim(q, self.vecs)[0]
        i = int(sims.argmax())
        a = self.articles[i]
        return KbMatch(
            article_id=a["id"],
            title=a["title"],
            answer=a["answer"],
            source=a.get("source", "Help Center"),
            confidence=round(float(sims[i]), 3),
        )


_kb_instance: Any = None


def get_kb(articles: list[dict[str, Any]] | None = None, mode: str = "rules") -> Any:
    global _kb_instance
    if articles is not None:
        if mode == "hf":
            try:
                _kb_instance = MiniLmKb(articles)
            except Exception as exc:
                log.warning("MiniLM model failed to initialize, falling back to TF-IDF: %s", exc)
                _kb_instance = TfidfKb(articles)
        else:
            _kb_instance = TfidfKb(articles)
    return _kb_instance
