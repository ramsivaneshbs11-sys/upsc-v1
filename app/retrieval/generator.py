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
      A mode-specific prompt is selected via prompts.get_prompt(mode).
      Three modes are supported: prelims, mains, current_affairs.
      All prompts forbid outside knowledge and enforce citation.

  Layer 3 — Citation Enforcement:
      The model must tag every fact with [chunk_id] inline. The response
      includes a "citations" list so the caller can trace every claim back
      to the original source document and page.

Public API:
    generate_grounded_answer(query, chunks, source, mode) -> dict
"""

import json
import logging
import re
import requests
import google.generativeai as genai

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL
from app.retrieval.prompts  import get_prompt
from app.retrieval.metrics  import timer as metrics_timer
from app.database.models import ChatMessage

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


# ── Prompt selection is now handled by app/retrieval/prompts.py ───────────────
# Use generate_grounded_answer(..., mode="prelims"|"mains"|"current_affairs")
# to choose the appropriate system prompt. The default is "prelims".
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


def _call_groq(prompt: str) -> str:
    """
    Call the Groq API with the given prompt.
    Raises an exception on any failure (incl. 429 rate limit).
    """
    if not GROQ_API_KEY or not GROQ_API_KEY.strip():
        raise RuntimeError("GROQ_API_KEY is not configured.")
    logger.info(f"[Generator] Calling Groq API using model: {GROQ_MODEL}")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_gemini(prompt: str) -> str:
    """
    Call the Gemini API with key rotation.
    Raises an exception if all keys fail.
    """
    api_keys = [k.strip() for k in re.split(r"[,;]", GEMINI_API_KEY) if k.strip()]
    if not api_keys:
        raise RuntimeError("GEMINI_API_KEY is not set or empty in .env")

    last_exception = None
    for idx, key in enumerate(api_keys):
        masked = f"{key[:8]}..." if len(key) > 8 else "***"
        try:
            logger.info(f"[Generator] Trying Gemini API Key {idx} ({masked}) ...")
            genai.configure(api_key=key)
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            logger.warning(f"[Generator] Gemini API Key {idx} failed: {exc}. Trying next key...")
            last_exception = exc

    raise last_exception or RuntimeError("All Gemini API keys failed.")


# ── Chat Memory helpers ────────────────────────────────────────────────────────

def get_session_history(db, session_id: str, limit: int = 10) -> list[ChatMessage]:
    """Retrieve last N messages from database for the session_id, in chronological order."""
    if not session_id or db is None:
        return []
    try:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(messages))
    except Exception as exc:
        logger.error(f"[Generator:DB] Failed to load chat history for session {session_id}: {exc}")
        return []


def save_chat_message(db, session_id: str, role: str, content: str):
    """Save a user or assistant message to the database."""
    if not session_id or db is None:
        return
    try:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(msg)
        db.commit()
    except Exception as exc:
        logger.error(f"[Generator:DB] Failed to save chat message: {exc}")
        db.rollback()


def format_history_for_prompt(messages: list[ChatMessage]) -> str:
    """Format a list of ChatMessage instances as user/assistant lines."""
    if not messages:
        return "No previous conversation history."
    lines = []
    for msg in messages:
        role = "User" if msg.role == "user" else "Assistant"
        content = msg.content
        try:
            # If the stored assistant response is a JSON string, extract just the answer
            parsed = json.loads(content)
            if "answer" in parsed:
                content = parsed["answer"]
        except Exception:
            pass
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def condense_query(query: str, history_str: str) -> str:
    """
    Given the user's new query and the conversation history,
    rewrite it into a standalone search query.
    """
    if not history_str.strip() or history_str == "No previous conversation history.":
        return query

    prompt = (
        "Given the following conversation history and a follow-up question, "
        "rewrite the follow-up question to be a standalone, self-contained search query. "
        "Do not answer the question; only return the rewritten question. "
        "Keep it concise and optimized for search engine retrieval.\n\n"
        "Conversation History:\n"
        f"{history_str}\n\n"
        f"Follow-up Question: {query}\n"
        "Standalone Question:"
    )
    try:
        logger.info(f"[Generator] Condensing query: '{query[:60]}'")
        rewritten = _call_gemini(prompt)
        rewritten_clean = rewritten.strip().strip('"').strip("'")
        logger.info(f"[Generator] Condensed query result: '{rewritten_clean[:80]}'")
        return rewritten_clean
    except Exception as exc:
        logger.warning(f"[Generator] Query condensation failed: {exc}. Using original query.")
        return query


def _call_gemini_grounded(query: str, system_instruction: str) -> dict:
    """
    Call the Gemini API with the native Google Search Grounding tool enabled.
    Uses key rotation across all keys in GEMINI_API_KEY.

    Returns a dict with:
        answer      (str)        — grounded markdown answer from Gemini
        answered    (bool)       — True if Gemini could answer from search results
        citations   (list[str])  — web source titles used (labelled src_001, etc.)
        rich_citations (list[dict]) — [{chunk_id, document, pages, preview, url}]
        search_queries (list[str]) — the Google Search queries Gemini executed

    Raises:
        RuntimeError if all API keys fail or SDK is not installed.
    """
    if not _GENAI_NEW_SDK:
        raise RuntimeError(
            "google-genai SDK >= 1.0.0 is required for Search Grounding. "
            "Run: pip install -U google-genai"
        )

    api_keys = _get_api_keys()
    if not api_keys:
        raise RuntimeError("GEMINI_API_KEY is not set or empty in .env")

    last_exception = None
    for idx, key in enumerate(api_keys):
        masked = f"{key[:8]}..." if len(key) > 8 else "***"
        try:
            logger.info(
                f"[Generator:Grounding] Trying Gemini API Key {idx} ({masked}) "
                f"for Search Grounding..."
            )
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=query,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                    temperature=0.0,
                ),
            )

            # ── Extract answer text ───────────────────────────────────────────
            answer_text = response.text.strip() if response.text else ""

            # ── Parse grounding metadata ──────────────────────────────────────
            search_queries: list[str] = []
            rich_citations: list[dict] = []
            citation_labels: list[str] = []

            if (
                response.candidates
                and response.candidates[0].grounding_metadata
            ):
                gm = response.candidates[0].grounding_metadata

                # Queries Gemini executed
                if gm.web_search_queries:
                    search_queries = list(gm.web_search_queries)

                # Grounding chunks = cited web sources
                if gm.grounding_chunks:
                    for src_idx, chunk in enumerate(gm.grounding_chunks):
                        if chunk.web:
                            label = f"src_{src_idx + 1:03d}"
                            citation_labels.append(label)
                            rich_citations.append({
                                "chunk_id": label,
                                "document": chunk.web.title or chunk.web.uri or "Web Source",
                                "pages":    None,
                                "preview":  "",
                                "url":      chunk.web.uri or "",
                            })

            answered = bool(answer_text)
            logger.info(
                f"[Generator:Grounding] Search Grounding succeeded. "
                f"Queries={search_queries}, sources={len(rich_citations)}"
            )
            return {
                "answer":         answer_text,
                "answered":       answered,
                "citations":      citation_labels,
                "rich_citations": rich_citations,
                "search_queries": search_queries,
            }

        except Exception as exc:
            logger.warning(
                f"[Generator:Grounding] Gemini API Key {idx} failed: {exc}. "
                f"Trying next key..."
            )
            last_exception = exc

    raise last_exception or RuntimeError("All Gemini API keys failed for Search Grounding.")


def generate_grounded_answer(
    query:  str,
    chunks: list[dict],
    source: str  = "qdrant",
    mode:   str  = "prelims",
    history_str: str = "",
) -> dict:
    """
    Generate a hallucination-resistant answer from retrieved chunks.

    Layer 1 — Score Gate: If best rerank_score < RERANK_SCORE_THRESHOLD,
               skip LLM and return "insufficient information".
    Layer 2 — Mode-specific prompt: Selected via get_prompt(mode).
               Modes: "prelims" | "mains" | "current_affairs".
    Layer 3 — Citation enforcement: response includes cited chunk IDs.

    Groq ↔ Gemini Fallback:
        Tries Groq first. If Groq raises any exception (incl. 429 rate limit),
        automatically falls back to Gemini key-rotation before giving up.

    Args:
        query:  The user's original query.
        chunks: Reranked top-K chunks from the retrieval layer.
        source: "qdrant" or "web" — included in metadata.
        mode:   Prompt mode — "prelims" (default), "mains", or "current_affairs".
        history_str: Human-formatted sliding-window conversation history.

    Returns:
        dict with keys:
            answer      (str)        — grounded answer or "insufficient info"
            answered    (bool)       — False if LLM could not answer from context
            citations   (list[str])  — chunk_ids cited in the answer
            gated       (bool)       — True if score gate blocked LLM call
            gate_reason (str | None) — reason for gating, if applicable
            mode        (str)        — prompt mode used
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
            "mode":           mode,
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
            "mode":           mode,
        }

    # ── Layer 2 + 3: Mode-specific Prompt with Citation Enforcement ─────────────
    context_block = _build_context_block(chunks)
    try:
        selected_prompt = get_prompt(mode)
    except ValueError:
        logger.warning(
            f"[Generator] Unknown mode '{mode}' — falling back to 'prelims'."
        )
        selected_prompt = get_prompt("prelims")
        mode = "prelims"
    prompt = selected_prompt.format(
        context=context_block,
        query=query,
        history=history_str if history_str.strip() else "No previous conversation history.",
    )

    try:
        # ── Groq-first → Gemini-fallback chain with metrics ───────────────────
        raw = None
        provider_used = "n/a"
        groq_available   = bool(GROQ_API_KEY and GROQ_API_KEY.strip())
        gemini_available = bool(GEMINI_API_KEY and GEMINI_API_KEY.strip())

        with metrics_timer("gen", query=query, mode=mode) as ctx:
            if groq_available:
                try:
                    raw = _call_groq(prompt)
                    provider_used = "groq"
                    logger.info("[Generator] Groq call succeeded.")
                except Exception as groq_exc:
                    logger.warning(
                        f"[Generator] Groq failed ({groq_exc}). "
                        f"Falling back to Gemini..."
                    )
                    if not gemini_available:
                        raise groq_exc

            if raw is None and gemini_available:
                logger.info("[Generator] Using Gemini API as fallback.")
                raw = _call_gemini(prompt)
                provider_used = "gemini"

            if raw is None:
                raise RuntimeError(
                    "No LLM API is configured (both GROQ_API_KEY and GEMINI_API_KEY are missing)."
                )

            # Estimate token usage (rough: 1 token ≈ 4 chars)
            ctx["input_tokens"]  = len(prompt) // 4
            ctx["output_tokens"] = len(raw) // 4
            ctx["provider"]      = provider_used

        # Strip markdown fences if model added them
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)

        answer    = result.get("answer", "").strip()
        answered  = bool(result.get("answered", False))
        citations = result.get("citations", [])

        logger.info(
            f"[Generator] answered={answered}, mode={mode}, provider={provider_used}, "
            f"citations={citations}, query='{query[:60]}'"
        )

        rich_citations = format_citations(citations, chunks)

        return {
            "answer":          answer,
            "answered":        answered,
            "citations":       citations,
            "rich_citations":  rich_citations,
            "gated":           False,
            "gate_reason":     None,
            "mode":            mode,
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
            "mode":           mode,
        }
