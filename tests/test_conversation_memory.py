"""
tests/test_conversation_memory.py
───────────────────────────────────
Unit tests for RAG Chat/Conversation Memory persistence and logic.
"""
import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from app.database.session import Base
from app.database.models import ChatMessage
from app.retrieval.generator import (
    get_session_history,
    save_chat_message,
    format_history_for_prompt,
    condense_query,
)

# Setup in-memory SQLite database for testing database schemas
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop tables
        Base.metadata.drop_all(bind=engine)


def test_save_and_retrieve_chat_history(db_session):
    session_id = "test_user_session_123"
    
    # Save a user message and assistant response
    save_chat_message(db_session, session_id, "user", "What is Article 21?")
    save_chat_message(db_session, session_id, "assistant", json.dumps({"answer": "Article 21 protects life and liberty.", "answered": True, "citations": []}))

    # Retrieve history
    history = get_session_history(db_session, session_id, limit=10)
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "What is Article 21?"
    assert history[1].role == "assistant"
    
    # Verify chronological ordering (oldest first)
    assert history[0].created_at <= history[1].created_at


def test_format_history_for_prompt(db_session):
    session_id = "test_session_456"
    save_chat_message(db_session, session_id, "user", "Hello")
    save_chat_message(db_session, session_id, "assistant", json.dumps({"answer": "Hi there!", "answered": True}))
    
    history_msgs = get_session_history(db_session, session_id)
    history_str = format_history_for_prompt(history_msgs)
    
    expected = "User: Hello\nAssistant: Hi there!"
    assert history_str == expected


def test_format_history_empty():
    history_str = format_history_for_prompt([])
    assert history_str == "No previous conversation history."


def test_condense_query_empty_history():
    # When history is empty, it should return the query immediately without calling LLM
    query = "What is the status of Gaganyaan?"
    result = condense_query(query, "No previous conversation history.")
    assert result == query

    result_empty = condense_query(query, "   ")
    assert result_empty == query
