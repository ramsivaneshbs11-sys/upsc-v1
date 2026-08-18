"""
app/retrieval/generator.py
───────────────────────────
Anti-Hallucination LLM Answer Generator.

Implements 3 layers of hallucination prevention:

  Layer 1 — Score Gate:
      If the best rerank_score is below RERANK_SCORE_THRESHOLD, the LLM is
      NOT called. Returns a fixed "insufficient information" response instead
      of risking a hallucinated answer.

  Layer 2 — Strict Context-Only System Prompt:
      The Gemini Flash prompt explicitly forbids using any outside knowledge.
      Every claim must be grounded in the supplied context passages.
      If the answer is not in the context, the model must say so.

  Layer 3 — Citation Enforcement:
      The model must tag every fact with [chunk_id] inline. The response
      includes a "citations" list so the caller can trace every claim back
      to the original source document and page.

Public API:
    generate_grounded_answer(query, chunks, source) -> dict
"""

import json
import logging
import re
import requests
import google.generativeai as genai

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

# ── Configurable thresholds ────────────────────────────────────────────────────
# Minimum rerank_score for the best chunk to trigger LLM generation.
# cross-encoder/ms-marco-MiniLM-L-6-v2 typically returns scores in [-10, +10].
# A score < 0.0 means the cross-encoder found the chunk largely irrelevant.
RERANK_SCORE_THRESHOLD: float = 0.0

# ── Gemini client singleton ────────────────────────────────────────────────────
_gemini_model = None

def _get_gemini_model():
    global _gemini_model
    if _gemini_model is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        # Parse the first key if there is a comma-separated list of keys in .env
        actual_key = GEMINI_API_KEY.split(',')[0].strip() if ',' in GEMINI_API_KEY else GEMINI_API_KEY
        genai.configure(api_key=actual_key)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info(f"Gemini generator model loaded: {GEMINI_MODEL}")
    return _gemini_model


# ── Anti-Hallucination System Prompt ──────────────────────────────────────────
_ANTI_HALLUCINATION_PROMPT = """
You are a strict UPSC study assistant. Your ONLY job is to answer the question
using the CONTEXT PASSAGES provided below.

━━━━━━━━━━━ STRICT RULES — READ CAREFULLY ━━━━━━━━━━━

1. CONTEXT ONLY:
   Answer EXCLUSIVELY from the context passages below.
   Do NOT use any outside knowledge, training data, or general facts.

2. CITE EVERY CLAIM:
   After every sentence that states a fact, add the chunk ID in brackets.
   Example: "Cultural ecology studies human adaptation. [chk_0012]"

3. UNKNOWN = ADMIT IT:
   If the answer is NOT found in the context passages, you MUST respond with:
   "I don't have enough information in my knowledge base to answer this question."
   Do NOT guess, infer, or speculate.

4. NO PADDING:
   Do not add introductions, summaries, disclaimers, or filler text.
   Answer directly and concisely.

5. PARTIAL ANSWERS:
   If only part of the question is answered by the context, answer that part
   and clearly state: "The remaining part of the question is not covered in
   the available documents."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTEXT PASSAGES:
{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION: {query}

Respond with ONLY a JSON object in this exact format (no markdown fences):
{{
  "answer": "<your grounded answer with inline [chunk_id] citations>",
  "answered": true,
  "citations": ["chk_001", "chk_002"]
}}

If you cannot answer from context:
{{
  "answer": "I don't have enough information in my knowledge base to answer this question.",
  "answered": false,
  "citations": []
}}
""".strip()


def _build_context_block(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a numbered context block for the prompt.
    Each chunk is labelled with its chunk_id so the LLM can cite it.
    """
    lines = []
    for i, chunk in enumerate(chunks, 1):
        chunk_id = chunk.get("chunk_id", f"chunk_{i}")
        text     = chunk.get("text", "").strip()
        source   = chunk.get("source", "qdrant")
        meta     = chunk.get("metadata", {})
        page     = meta.get("page_num", meta.get("page", "?"))

        lines.append(
            f"[{chunk_id}] (source={source}, page={page})\n{text}"
        )
    return "\n\n---\n\n".join(lines)


def format_citations(citations: list[str], chunks: list[dict]) -> list[dict]:
    """
    Convert a list of raw chunk_ids into human-readable citation objects.
    Queries the PostgreSQL documents table to map UUID file names back to
    original uploaded filenames.

    Each citation object contains:
        chunk_id   (str)  — original chunk reference ID
        document   (str)  — original PDF filename (e.g. "Brain Tree VOL-1.pdf")
        pages      (any)  — page number(s) where the fact was found
        preview    (str)  — first 150 characters of the source passage

    Args:
        citations: List of chunk_id strings returned by the LLM.
        chunks:    The reranked chunks that were sent to the LLM.

    Returns:
        List of human-readable citation dicts.
    """
    chunk_map = {c.get("chunk_id", ""): c for c in chunks}
    
    # Pre-fetch original filenames from the PostgreSQL database
    file_ids = {c.get("file_id") for c in chunks if c.get("file_id")}
    file_id_to_name = {}
    if file_ids:
        try:
            from sqlalchemy import text
            from app.database.session import SessionLocal
            with SessionLocal() as db:
                query_str = text("SELECT id, original_filename FROM documents WHERE id IN :ids")
                rows = db.execute(query_str, {"ids": tuple(file_ids)}).fetchall()
                file_id_to_name = {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.error(f"[Generator] Failed to fetch original filenames from DB: {e}")

    result = []
    for cid in citations:
        chunk = chunk_map.get(cid, {})
        meta  = chunk.get("metadata", {})
        file_id = chunk.get("file_id")

        # Resolve document name from DB lookup, falling back to metadata filenames
        doc_name = None
        if file_id and file_id in file_id_to_name:
            doc_name = file_id_to_name[file_id]

        if not doc_name:
            doc_name = (
                meta.get("file_name")
                or meta.get("source_file")
                or meta.get("filename")
                or "Unknown Document"
            )

        # Page numbers can be a list (page_numbers) or a single int (page_num/page)
        pages = (
            meta.get("page_numbers")
            or meta.get("page_num")
            or meta.get("page")
            or "?"
        )
        preview_text = chunk.get("text", "")
        preview = (preview_text[:150] + "...") if len(preview_text) > 150 else preview_text

        result.append({
            "chunk_id": cid,
            "document": doc_name,
            "pages":    pages,
            "preview":  preview,
        })
    return result


def generate_grounded_answer(
    query:  str,
    chunks: list[dict],
    source: str = "qdrant",
) -> dict:
    """
    Generate a hallucination-resistant answer from retrieved chunks.

    Layer 1 — Score Gate: If best rerank_score < RERANK_SCORE_THRESHOLD,
               skip LLM and return "insufficient information".
    Layer 2 — Strict prompt: LLM must use context ONLY and cite every claim.
    Layer 3 — Citation enforcement: response includes cited chunk IDs.

    Args:
        query:  The user's original query.
        chunks: Reranked top-K chunks from the retrieval layer.
        source: "qdrant" or "duckduckgo" — included in metadata.

    Returns:
        dict with keys:
            answer      (str)        — grounded answer or "insufficient info"
            answered    (bool)       — False if LLM could not answer from context
            citations   (list[str])  — chunk_ids cited in the answer
            gated       (bool)       — True if score gate blocked LLM call
            gate_reason (str | None) — reason for gating, if applicable
    """
    # ── Layer 1: Score Gate ────────────────────────────────────────────────────
    if not chunks:
        logger.warning(f"[Generator] No chunks for query: '{query[:60]}' — gated.")
        return {
            "answer":         "I don't have enough information in my knowledge base to answer this question.",
            "answered":       False,
            "citations":      [],
            "rich_citations": [],
            "gated":          True,
            "gate_reason":    "No chunks retrieved from the knowledge base.",
        }

    best_rerank_score = max(c.get("rerank_score", 0.0) for c in chunks)
    if best_rerank_score < RERANK_SCORE_THRESHOLD:
        logger.warning(
            f"[Generator] Score gate triggered — best rerank_score={best_rerank_score:.3f} "
            f"< threshold={RERANK_SCORE_THRESHOLD} for query: '{query[:60]}'"
        )
        return {
            "answer":         "I don't have enough information in my knowledge base to answer this question.",
            "answered":       False,
            "citations":      [],
            "rich_citations": [],
            "gated":          True,
            "gate_reason": (
                f"Retrieval confidence too low (best rerank score: {best_rerank_score:.3f}). "
                "The question may be outside the scope of the available documents."
            ),
        }

    # ── Layer 2 + 3: Strict Prompt with Citation Enforcement ──────────────────
    context_block = _build_context_block(chunks)
    prompt = _ANTI_HALLUCINATION_PROMPT.format(
        context=context_block,
        query=query,
    )

    try:
        # -- Conditional Invocation: Groq or Gemini --
        if GROQ_API_KEY and GROQ_API_KEY.strip():
            logger.info(f"[Generator] Calling Groq API using model: {GROQ_MODEL}")
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
                timeout=15.0
            )
            resp.raise_for_status()
            response_json = resp.json()
            raw = response_json["choices"][0]["message"]["content"].strip()
        else:
            logger.info(f"[Generator] Calling Gemini API using model: {GEMINI_MODEL}")
            api_keys = [k.strip() for k in re.split(r"[,;]", GEMINI_API_KEY) if k.strip()]
            if not api_keys:
                raise RuntimeError("GEMINI_API_KEY is not set or empty in .env")

            raw = None
            last_exception = None
            for idx, key in enumerate(api_keys):
                masked = f"{key[:8]}..." if len(key) > 8 else "***"
                try:
                    logger.info(f"[Generator] Trying Gemini API Key {idx} ({masked}) ...")
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(GEMINI_MODEL)
                    response = model.generate_content(prompt)
                    raw = response.text.strip()
                    break
                except Exception as exc:
                    logger.warning(f"[Generator] Gemini API Key {idx} failed: {exc}. Trying next key...")
                    last_exception = exc

            if raw is None:
                raise last_exception or RuntimeError("All Gemini API keys failed.")

        # Strip markdown fences if model added them
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)

        answer    = result.get("answer", "").strip()
        answered  = bool(result.get("answered", False))
        citations = result.get("citations", [])

        logger.info(
            f"[Generator] answered={answered}, citations={citations}, "
            f"query='{query[:60]}'"
        )

        rich_citations = format_citations(citations, chunks)

        return {
            "answer":          answer,
            "answered":        answered,
            "citations":       citations,
            "rich_citations":  rich_citations,
            "gated":           False,
            "gate_reason":     None,
        }

    except Exception as exc:
        logger.error(f"[Generator] LLM generation failed: {exc}")
        return {
            "answer":         "I don't have enough information in my knowledge base to answer this question.",
            "answered":       False,
            "citations":      [],
            "rich_citations": [],
            "gated":          True,
            "gate_reason":    f"LLM generation error: {exc}",
        }
