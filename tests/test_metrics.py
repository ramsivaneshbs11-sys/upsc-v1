"""
tests/test_metrics.py
──────────────────────
Unit tests for app/retrieval/metrics.py

Covers:
  - record() creates the CSV file on first call
  - record() appends a correctly formatted row with all expected columns
  - Multiple calls append multiple rows
  - timer() context manager measures non-zero latency and records a row
  - timer() records token counts set inside the context block
  - CSV file has a valid header row
"""

import csv
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch


# ── Redirect metrics output to a temp dir for tests ───────────────────────────
import tempfile
_tmp_metrics_dir = Path(tempfile.mkdtemp())

# Must be set BEFORE importing metrics to override the module-level path
with patch.dict(os.environ, {"ENABLE_DETAILED_LOGGING": "false"}):
    import app.core.config as _cfg
    _cfg.METRICS_DIR = _tmp_metrics_dir
    _cfg.METRICS_DIR.mkdir(parents=True, exist_ok=True)

    import app.retrieval.metrics as metrics_mod
    # Override the file path used by the module
    metrics_mod._METRICS_FILE = _tmp_metrics_dir / "test_metrics.csv"
    # Re-run header creation on the test path
    metrics_mod._ensure_csv_header()

from app.retrieval.metrics import record, timer, _CSV_FIELDNAMES


@pytest.fixture(autouse=True)
def clean_csv():
    """Remove the test CSV before each test for isolation."""
    csv_path = metrics_mod._METRICS_FILE
    if csv_path.exists():
        csv_path.unlink()
    metrics_mod._ensure_csv_header()
    yield
    # Cleanup after test
    if csv_path.exists():
        csv_path.unlink()


def _read_csv() -> list[dict]:
    csv_path = metrics_mod._METRICS_FILE
    with csv_path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_csv_file_created_on_header():
    assert metrics_mod._METRICS_FILE.exists()


def test_csv_has_valid_header():
    with metrics_mod._METRICS_FILE.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == _CSV_FIELDNAMES


def test_record_appends_one_row():
    record(query="What is Article 21?", mode="prelims", stage="gen",
           latency_ms=123.4, input_tokens=500, output_tokens=150,
           provider="groq", routing="high")
    rows = _read_csv()
    assert len(rows) == 1
    row = rows[0]
    assert row["query"]         == "What is Article 21?"
    assert row["mode"]          == "prelims"
    assert row["stage"]         == "gen"
    assert float(row["latency_ms"]) == pytest.approx(123.4, abs=0.1)
    assert int(row["input_tokens"])  == 500
    assert int(row["output_tokens"]) == 150
    assert row["provider"]      == "groq"
    assert row["routing"]       == "high"


def test_record_appends_multiple_rows():
    record(stage="search")
    record(stage="scrape")
    record(stage="gen")
    rows = _read_csv()
    assert len(rows) == 3
    stages = [r["stage"] for r in rows]
    assert stages == ["search", "scrape", "gen"]


def test_record_truncates_long_query():
    long_query = "Q" * 200
    record(query=long_query, stage="gen")
    rows = _read_csv()
    assert len(rows[0]["query"]) <= 80


def test_timer_records_latency():
    with timer("search", query="test query", mode="mains"):
        time.sleep(0.05)  # 50 ms

    rows = _read_csv()
    assert len(rows) == 1
    latency = float(rows[0]["latency_ms"])
    assert latency >= 40.0   # at least 40 ms (generous lower bound)
    assert rows[0]["stage"] == "search"
    assert rows[0]["mode"]  == "mains"


def test_timer_records_token_counts_from_context():
    with timer("gen", query="token test", mode="prelims") as ctx:
        ctx["input_tokens"]  = 300
        ctx["output_tokens"] = 100
        ctx["provider"]      = "gemini"

    rows = _read_csv()
    assert int(rows[0]["input_tokens"])  == 300
    assert int(rows[0]["output_tokens"]) == 100
    assert rows[0]["provider"]           == "gemini"


def test_timer_records_even_on_exception():
    """Even if the block raises, the metrics row should still be written."""
    with pytest.raises(ValueError):
        with timer("scrape", query="exception test", mode="current_affairs"):
            raise ValueError("scrape failed")

    rows = _read_csv()
    assert len(rows) == 1
    assert rows[0]["stage"] == "scrape"
