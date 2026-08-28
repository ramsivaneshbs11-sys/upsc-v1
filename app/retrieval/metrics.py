"""
app/retrieval/metrics.py
─────────────────────────
Lightweight per-request metrics recorder for the UPSC RAG pipeline.

Records stage-level latency and token usage to a CSV file and (optionally)
to the Python logging system when ENABLE_DETAILED_LOGGING is True.

CSV Schema (metrics/current_affairs_metrics.csv):
    timestamp       ISO-8601 UTC timestamp
    query           First 80 chars of the user query
    mode            Prompt mode (prelims / mains / current_affairs)
    stage           Pipeline stage (search / scrape / rerank / gen / total)
    latency_ms      Wall-clock time for the stage in milliseconds
    input_tokens    Estimated input token count (0 if not applicable)
    output_tokens   Estimated output token count (0 if not applicable)
    provider        LLM provider used (groq / gemini / n/a)
    routing         Retrieval routing decision (high / medium / low / n/a)

Public API:
    record(query, mode, stage, latency_ms, **extra) -> None
        Append one row to the CSV.

    timer(stage) -> ContextManager
        Context manager that measures wall-clock time and calls record().
"""

from __future__ import annotations

import csv
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Generator

from app.core.config import ENABLE_DETAILED_LOGGING, METRICS_DIR

logger = logging.getLogger(__name__)

# ── CSV file path ──────────────────────────────────────────────────────────────
_METRICS_FILE: Path = METRICS_DIR / "current_affairs_metrics.csv"

_CSV_FIELDNAMES = [
    "timestamp",
    "query",
    "mode",
    "stage",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "provider",
    "routing",
]

_write_lock = Lock()


def _ensure_csv_header() -> None:
    """Write the CSV header row if the file does not yet exist."""
    if not _METRICS_FILE.exists():
        try:
            with _METRICS_FILE.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES)
                writer.writeheader()
        except OSError as exc:
            logger.warning(f"[Metrics] Could not create metrics file: {exc}")


_ensure_csv_header()


def record(
    query:         str = "",
    mode:          str = "n/a",
    stage:         str = "n/a",
    latency_ms:    float = 0.0,
    input_tokens:  int = 0,
    output_tokens: int = 0,
    provider:      str = "n/a",
    routing:       str = "n/a",
) -> None:
    """
    Append one metrics row to the CSV file.

    Args:
        query:         User query (truncated to 80 chars for readability).
        mode:          Prompt mode ("prelims" / "mains" / "current_affairs" / "n/a").
        stage:         Pipeline stage ("search" / "scrape" / "rerank" / "gen" / "total").
        latency_ms:    Wall-clock latency for the stage in milliseconds.
        input_tokens:  Estimated input tokens consumed (0 if unknown).
        output_tokens: Estimated output tokens generated (0 if unknown).
        provider:      LLM provider ("groq" / "gemini" / "n/a").
        routing:       Retrieval routing used ("high" / "medium" / "low" / "n/a").
    """
    row = {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "query":         query[:80].replace("\n", " "),
        "mode":          mode,
        "stage":         stage,
        "latency_ms":    round(latency_ms, 2),
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "provider":      provider,
        "routing":       routing,
    }

    # Write to CSV
    try:
        with _write_lock:
            with _METRICS_FILE.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES)
                writer.writerow(row)
    except OSError as exc:
        logger.warning(f"[Metrics] Failed to write CSV row: {exc}")

    # Optionally mirror to the logging system
    if ENABLE_DETAILED_LOGGING:
        logger.info(
            f"[Metrics] stage={stage} | mode={mode} | "
            f"latency={latency_ms:.1f}ms | "
            f"in_tokens={input_tokens} | out_tokens={output_tokens} | "
            f"provider={provider} | routing={routing} | "
            f"query={query[:60]!r}"
        )


@contextmanager
def timer(
    stage:   str,
    query:   str = "",
    mode:    str = "n/a",
    routing: str = "n/a",
    provider: str = "n/a",
) -> Generator[dict, None, None]:
    """
    Context manager that measures wall-clock time for a pipeline stage and
    automatically calls record() on exit.

    Usage:
        with timer("search", query=q, mode="prelims") as ctx:
            results = run_search(q)
            ctx["input_tokens"] = estimate_tokens(results)

    The ctx dict can be mutated inside the block to pass token counts and
    provider info to the recorder.
    """
    ctx: dict = {
        "input_tokens":  0,
        "output_tokens": 0,
        "provider":      provider,
        "routing":       routing,
    }
    start = time.perf_counter()
    try:
        yield ctx
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        record(
            query=query,
            mode=mode,
            stage=stage,
            latency_ms=elapsed_ms,
            input_tokens=ctx.get("input_tokens", 0),
            output_tokens=ctx.get("output_tokens", 0),
            provider=ctx.get("provider", provider),
            routing=ctx.get("routing", routing),
        )
