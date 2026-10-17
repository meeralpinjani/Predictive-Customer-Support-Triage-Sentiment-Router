"""Pairwise text similarity: MiniLM sentence embeddings when the AI models are loaded,
TF-IDF otherwise. Used to find duplicate tickets (incidents) and unanswered topics."""
from app.config import settings


def similarity_matrix(texts: list[str]) -> tuple[list[list[float]], str]:
    """Returns (n x n cosine similarities, method)."""
    if not texts:
        return [], "none"
    if settings.nlp_mode == "hf":
        try:
            from app.nlp import hf
            if hf.ready():
                from sentence_transformers import util
                vecs = hf.embedder().encode([t[:512] for t in texts], convert_to_tensor=True, normalize_embeddings=True)
                return util.cos_sim(vecs, vecs).tolist(), "minilm"
        except Exception:
            pass
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    m = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True).fit_transform(texts)
    return cosine_similarity(m).tolist(), "tfidf"


# Same-issue thresholds differ: embeddings score paraphrases higher than word overlap does.
DUPLICATE_THRESHOLD = {"minilm": 0.70, "tfidf": 0.45}
TOPIC_THRESHOLD = {"minilm": 0.55, "tfidf": 0.30}


def cluster(texts: list[str], threshold: dict[str, float], min_size: int = 2) -> tuple[list[list[int]], str]:
    """Greedy single-pass clustering: each group is a seed plus everything similar enough to it."""
    sims, method = similarity_matrix(texts)
    th = threshold.get(method, 0.5)
    used: set[int] = set()
    groups = []
    for i in range(len(texts)):
        if i in used:
            continue
        members = [j for j in range(len(texts)) if j not in used and (j == i or sims[i][j] >= th)]
        if len(members) >= min_size:
            groups.append(members)
            used.update(members)
    return groups, method
