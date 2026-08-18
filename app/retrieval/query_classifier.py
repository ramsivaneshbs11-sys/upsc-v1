"""
app/retrieval/query_classifier.py
───────────────────────────────────
Zero-cost embedding-based query classifier.

Uses the BAAI/bge-base-en-v1.5 model (already loaded for ingestion) to
classify a user query into one of the ALLOWED_CLASSIFICATIONS by computing
cosine similarity between the query embedding and predefined subject
description embeddings.

NO API KEY REQUIRED — runs fully locally using the same model already in memory.

Output schema:
    {
        "classification": "Anthropology",   # top predicted class
        "confidence": 0.92,                 # cosine similarity to top class
        "all_scores": {                     # scores for all classes
            "Anthropology": 0.92,
            "History": 0.08
        }
    }
"""

import logging
import numpy as np

from app.core.config import ALLOWED_CLASSIFICATIONS
from app.services.embedding_service import _get_model as get_embedding_model

logger = logging.getLogger(__name__)


# ── Subject description anchors ────────────────────────────────────────────────
# Each classification is described with rich, representative sentences.
# The classifier embeds both the query and these anchors, then picks the
# closest one by cosine similarity.

_SUBJECT_ANCHORS: dict[str, list[str]] = {
    "History": [
        "Ancient medieval modern Indian history civilizations empires kingdoms rulers dynasties",
        "Mughal empire British colonial rule independence freedom struggle nationalism",
        "Battle of Panipat Maratha Sultanate Maurya Gupta Vijayanagara empire",
        "Vedic period Indus Valley civilization bronze age iron age ancient India",
        "World war French revolution Renaissance reformation European history",
        "UPSC history prelims mains polity governance ancient medieval modern",
        "Archaeological findings historical monuments heritage sites inscriptions",
        "Socio-religious reform movements nationalism India freedom fighters",
    ],
    "Anthropology": [
        "Anthropology culture society kinship marriage family tribe ritual",
        "Social cultural biological physical anthropology human evolution race",
        "Kinship descent lineage clan moiety phratry marriage rules exogamy endogamy",
        "Tribe indigenous people scheduled tribes cultural ecology adaptation",
        "Ethnography fieldwork participant observation qualitative research",
        "Cultural diffusion acculturation assimilation syncretism social change",
        "Caste class stratification social structure inequality",
        "Fossil hominid prehistoric human evolution Neanderthal Homo sapiens",
        "Applied anthropology development tribal welfare social policy",
        "Totemism animism religion magic ritual belief systems",
    ],
}


# ── Precomputed anchor embeddings (cached at module load time) ─────────────────
_anchor_embeddings: dict[str, np.ndarray] | None = None


def _get_anchor_embeddings() -> dict[str, np.ndarray]:
    """
    Lazily compute and cache the mean anchor embeddings for each subject.
    Called once on first query — subsequent calls reuse cached values.
    """
    global _anchor_embeddings
    if _anchor_embeddings is None:
        model = get_embedding_model()
        _anchor_embeddings = {}
        for subject, anchors in _SUBJECT_ANCHORS.items():
            vecs = model.encode(
                anchors,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            # Mean-pool anchor embeddings → single representative vector per class
            mean_vec = np.mean(vecs, axis=0)
            # Re-normalize after mean-pooling
            mean_vec = mean_vec / (np.linalg.norm(mean_vec) + 1e-9)
            _anchor_embeddings[subject] = mean_vec
            logger.info(f"QueryClassifier: anchor embedding cached for '{subject}'")
    return _anchor_embeddings


def classify_query(query: str) -> dict:
    """
    Classify a user query using cosine similarity to subject anchor embeddings.

    No API key needed — uses the locally loaded BAAI/bge-base-en-v1.5 model.

    Args:
        query: The user's search query string.

    Returns:
        dict with keys:
            classification (str)   — predicted subject class
            confidence (float)     — cosine similarity to top class (0.0–1.0)
            all_scores (dict)      — cosine similarity for every class
    """
    try:
        model           = get_embedding_model()
        anchor_embeddings = _get_anchor_embeddings()

        # Embed the query
        query_vec = model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]  # shape: (768,)

        # Compute cosine similarity to each subject anchor
        raw_scores: dict[str, float] = {}
        for subject in ALLOWED_CLASSIFICATIONS:
            if subject in anchor_embeddings:
                sim = float(np.dot(query_vec, anchor_embeddings[subject]))
                raw_scores[subject] = sim

        if not raw_scores:
            raise ValueError("No anchor embeddings available.")

        # Convert raw cosine similarities to a probability-like distribution
        # using softmax so scores sum to ~1.0
        subjects = list(raw_scores.keys())
        sims     = np.array([raw_scores[s] for s in subjects])

        # Softmax with temperature=5 (sharpens the distribution)
        temp     = 5.0
        exp_sims = np.exp(temp * (sims - sims.max()))
        probs    = exp_sims / exp_sims.sum()

        all_scores     = {s: round(float(p), 4) for s, p in zip(subjects, probs)}
        top_subject    = max(all_scores, key=all_scores.get)
        top_confidence = all_scores[top_subject]

        logger.info(
            f"QueryClassifier: '{query[:60]}' → class='{top_subject}', "
            f"confidence={top_confidence:.3f}, all={all_scores}"
        )

        return {
            "classification": top_subject,
            "confidence":     top_confidence,
            "all_scores":     all_scores,
        }

    except Exception as exc:
        logger.exception(
            f"QueryClassifier failed — returning uniform distribution. Error: {exc}"
        )
        uniform = round(1.0 / max(len(ALLOWED_CLASSIFICATIONS), 1), 4)
        return {
            "classification": ALLOWED_CLASSIFICATIONS[0],
            "confidence":     uniform,
            "all_scores":     {c: uniform for c in ALLOWED_CLASSIFICATIONS},
        }
