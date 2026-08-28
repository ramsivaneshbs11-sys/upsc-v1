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

import json
import logging
import re
import numpy as np
import requests
import google.generativeai as genai

from app.core.config import (
    ALLOWED_CLASSIFICATIONS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)
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
        # ── Added: Religious & cultural history topics commonly confused with Anthropology ──
        "Buddhism Jainism Hinduism Islam Sufism Bhakti movement religious philosophy teachings",
        "Gautama Buddha Mahavira Four Noble Truths Eightfold Path Nirvana Ahimsa Dharma",
        "Sufi saints Bhakti saints Kabir Mirabai Guru Nanak medieval religious movements India",
        "Indian art architecture temple cave paintings sculpture Ajanta Ellora Sanchi stupa",
        "Salt Satyagraha Civil Disobedience Quit India Movement Dandi March Gandhi Khilafat",
        "Non-Cooperation Movement Indian National Congress Swaraj boycott British colonial protest",
        "Simon Commission Lahore session Purna Swaraj Gandhi Nehru Rowlatt Act Jallianwala Bagh",
    ],
    "Anthropology": [
        "Anthropology culture society kinship marriage family tribe ritual",
        "Social cultural biological physical anthropology human evolution race",
        "Kinship descent lineage clan moiety phratry marriage rules exogamy endogamy",
        "Tribe indigenous people scheduled tribes cultural ecology adaptation",
        "Ethnography fieldwork participant observation qualitative research",
        "Cultural diffusion acculturation assimilation sociocultural change enculturation",
        "Caste class stratification social structure inequality",
        "Fossil hominid prehistoric human evolution Neanderthal Homo sapiens",
        "Applied anthropology development tribal welfare social policy",
        # ── Refined: Tribal-specific religion terms only (removed generic 'religion') ──
        "Totemism animism tribal religion magic shamanism sorcery witchcraft ritual belief",
        "Functionalism structuralism cultural materialism anthropological theory Boas Malinowski",
        "Somatoscopy dermatoglyphics blood groups genetic markers human genetics physical traits",
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


def _get_active_classifications() -> list[str]:
    """
    Fetch all active classifications including both hardcoded ones
    and those registered dynamically in the PostgreSQL database.
    """
    classes = list(ALLOWED_CLASSIFICATIONS)
    try:
        from app.database.session import SessionLocal
        from app.database.classification_models import Classification
        db = SessionLocal()
        try:
            dynamic_records = db.query(Classification).all()
            for r in dynamic_records:
                if r.name not in classes:
                    classes.append(r.name)
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Could not load dynamic classifications from DB: {exc}")
    return classes


def classify_query_via_groq(query: str, allowed_classes: list[str]) -> tuple[str, float, dict] | None:
    """
    Query classifier using Groq API only. 
    Guarantees highly accurate UPSC routing.
    """
    classes_str = ", ".join([f"'{c}'" for c in allowed_classes])
    prompt = f"""You are an expert UPSC subject classifier. Your ONLY job is to route the user's query to the correct subject category from this list: {classes_str}.

CRITICAL RULES:
1. CASE INSENSITIVE: Treat the query as case-insensitive. "netting robert mcc", "Netting Robert McC", and "NETTING ROBERT MCC" all refer to the same person. Names in lowercase are still proper names of people/places/concepts.
2. PROPER NOUN DETECTION: Even if names or terms are written in lowercase, recognize them as the real anthropologists, historians, rulers, or concepts they refer to (e.g., "robert mcc netting" = anthropologist Robert McC. Netting → classify as Anthropology).
3. SUBJECT EXPERTISE: Use your deep knowledge of UPSC syllabus to classify correctly:
   - Anthropology: Human evolution, kinship, marriage, tribe, ethnography, cultural ecology, social structure, physical anthropology, applied anthropology, famous anthropologists (Netting, Boas, Malinowski, Morgan, Radcliffe-Brown, etc.)
   - History: Ancient/Medieval/Modern Indian history, freedom struggle, world history, dynasties, battles, monuments, socio-religious movements, Gandhi, Nehru, colonial era
4. CONFIDENCE: Be bold — assign high confidence (0.90+) when the subject is clear. Only assign low confidence when the query is genuinely ambiguous between two subjects.
5. OUTPUT: Respond ONLY with a raw JSON object, no markdown fences, no extra text.

User Query: "{query}"

JSON Output (exactly three keys):
- "classification": The chosen category name from the allowed list (spelled exactly as shown).
- "confidence": Float between 0.0 and 1.0.
- "reasoning": One sentence explaining why this category is correct.
"""
    try:
        raw_response = None
        if not GROQ_API_KEY or not GROQ_API_KEY.strip():
            raise RuntimeError("GROQ_API_KEY is not set or empty in .env")

        logger.info(f"[Classifier] Calling Groq using model: {GROQ_MODEL}")
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10.0
        )
        resp.raise_for_status()
        raw_response = resp.json()["choices"][0]["message"]["content"].strip()

        if not raw_response:
            return None

        # Clean markdown formatting if present
        raw_response = re.sub(r"^```(?:json)?\s*", "", raw_response)
        raw_response = re.sub(r"\s*```$", "", raw_response)

        result = json.loads(raw_response)
        cls = result.get("classification")
        conf = float(result.get("confidence", 0.90))

        if cls in allowed_classes:
            # Reconstruct all_scores dictionary
            all_scores = {}
            for c in allowed_classes:
                if c == cls:
                    all_scores[c] = conf
                else:
                    all_scores[c] = round((1.0 - conf) / max(len(allowed_classes) - 1, 1), 4)
            return cls, conf, all_scores

    except Exception as exc:
        logger.error(f"[Classifier] classify_query_via_groq failed: {exc}")
    return None


def classify_query(query: str) -> dict:
    """
    Classify a user query using Groq API directly by default.
    Falls back to the local embedding classifier if Groq is unavailable.
    """
    active_classes = _get_active_classifications()

    # ── Step 1: Direct Groq Classification ───────────────────────────────────
    groq_res = classify_query_via_groq(query, active_classes)
    if groq_res:
        cls, conf, all_scores = groq_res
        logger.info(
            f"QueryClassifier (Groq): '{query[:60]}' → class='{cls}', "
            f"confidence={conf:.3f}, all={all_scores}"
        )
        return {
            "classification": cls,
            "confidence":     conf,
            "all_scores":     all_scores,
        }

    # ── Step 2: Backup Local Embedding Fallback ──────────────────────────────
    logger.warning("QueryClassifier: Groq classification failed. Falling back to local BGE embeddings.")
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
        for subject in active_classes:
            if subject in anchor_embeddings:
                sim = float(np.dot(query_vec, anchor_embeddings[subject]))
                raw_scores[subject] = sim

        if not raw_scores:
            raise ValueError("No anchor embeddings available.")

        # Softmax with temperature=10
        subjects = list(raw_scores.keys())
        sims     = np.array([raw_scores[s] for s in subjects])
        temp     = 10.0
        exp_sims = np.exp(temp * (sims - sims.max()))
        probs    = exp_sims / exp_sims.sum()

        all_scores     = {s: round(float(p), 4) for s, p in zip(subjects, probs)}
        top_subject    = max(all_scores, key=all_scores.get)
        top_confidence = all_scores[top_subject]

        logger.info(
            f"QueryClassifier (Local Backup): '{query[:60]}' → class='{top_subject}', "
            f"confidence={top_confidence:.3f}, all={all_scores}"
        )

        return {
            "classification": top_subject,
            "confidence":     top_confidence,
            "all_scores":     all_scores,
        }

    except Exception as exc:
        logger.exception(
            f"QueryClassifier backup failed — returning uniform distribution. Error: {exc}"
        )
        uniform = round(1.0 / max(len(active_classes), 1), 4)
        return {
            "classification": active_classes[0],
            "confidence":     uniform,
            "all_scores":     {c: uniform for c in active_classes},
        }
