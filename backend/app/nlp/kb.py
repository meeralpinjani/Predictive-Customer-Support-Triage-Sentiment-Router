"""Knowledge-base retrieval.

Each article is indexed as its title plus every example question separately; a ticket's
confidence for an article is its best similarity to any of those texts. Comparing against
single questions (instead of one concatenated blob) keeps paraphrases from being diluted.
"""
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


def _questions(a: dict[str, Any]) -> list[str]:
    qs = a.get("questions", [])
    if isinstance(qs, str):
        try:
            qs = json.loads(qs)
        except ValueError:
            qs = [qs]
    return [a["title"], *qs]


class _IndexedKb:
    kind = "base"

    def __init__(self, articles: list[dict[str, Any]]) -> None:
        self.articles = articles
        self.texts: list[str] = []
        self.owner: list[int] = []
        for i, a in enumerate(articles):
            for q in _questions(a):
                self.texts.append(q)
                self.owner.append(i)

    def _similarities(self, text: str) -> list[float]:
        raise NotImplementedError

    def rank(self, text: str, k: int = 3) -> list[KbMatch]:
        """Best k articles (one score per article: its closest question)."""
        if not self.texts:
            return []
        best: dict[int, float] = {}
        for owner, sim in zip(self.owner, self._similarities(text)):
            best[owner] = max(best.get(owner, -1.0), sim)
        out = []
        for i in sorted(best, key=best.get, reverse=True)[:k]:
            a = self.articles[i]
            out.append(KbMatch(article_id=a["id"], title=a["title"], answer=a["answer"],
                               source=a.get("source", "Help Center"), confidence=round(max(best[i], 0.0), 3)))
        return out

    def match(self, text: str) -> KbMatch | None:
        if not self.texts:
            return None
        sims = self._similarities(text)
        best_i, best = 0, -1.0
        for owner, s in zip(self.owner, sims):
            if s > best:
                best_i, best = owner, s
        a = self.articles[best_i]
        return KbMatch(
            article_id=a["id"],
            title=a["title"],
            answer=a["answer"],
            source=a.get("source", "Help Center"),
            confidence=round(max(best, 0.0), 3),
        )


class TfidfKb(_IndexedKb):
    kind = "tfidf"

    def __init__(self, articles: list[dict[str, Any]]) -> None:
        super().__init__(articles)
        from sklearn.feature_extraction.text import TfidfVectorizer
        if self.texts:
            self.vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
            self.matrix = self.vec.fit_transform(self.texts)

    def _similarities(self, text: str) -> list[float]:
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(self.vec.transform([text]), self.matrix)[0].tolist()


class MiniLmKb(_IndexedKb):
    kind = "minilm"

    def __init__(self, articles: list[dict[str, Any]]) -> None:
        super().__init__(articles)
        from app.nlp.hf import embedder
        self.model = embedder()
        self.vecs = self.model.encode(self.texts, convert_to_tensor=True, normalize_embeddings=True)

    def _similarities(self, text: str) -> list[float]:
        from sentence_transformers import util
        q = self.model.encode(text[:512], convert_to_tensor=True, normalize_embeddings=True)
        return util.cos_sim(q, self.vecs)[0].tolist()


_kb_instance: Any = None


def get_kb(articles: list[dict[str, Any]] | None = None, mode: str = "rules") -> Any:
    """Build (when articles are given) or return the active KB index."""
    global _kb_instance
    if articles is not None:
        if mode == "hf":
            try:
                _kb_instance = MiniLmKb(articles)
            except Exception as exc:
                log.warning("MiniLM KB unavailable, using TF-IDF: %s", exc)
                _kb_instance = TfidfKb(articles)
        else:
            _kb_instance = TfidfKb(articles)
    return _kb_instance


def reset_kb() -> None:
    global _kb_instance
    _kb_instance = None
