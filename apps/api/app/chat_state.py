from fastapi import HTTPException

from app.chat_contexts import (
    explain_chat_context,
    get_default_context,
    is_allowed_context,
)
from app.db import get_db


def ensure_chat_context_state_table() -> None:
    query = """
    CREATE TABLE IF NOT EXISTS chat_context_state (
        chat_key TEXT PRIMARY KEY,
        selected_context TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query)


def get_chat_context_state(chat_key: str) -> dict:
    info = explain_chat_context(chat_key)
    if not info["known"]:
        raise HTTPException(status_code=404, detail="Unknown chat_key")

    query = """
    SELECT
        chat_key,
        selected_context,
        updated_at
    FROM chat_context_state
    WHERE chat_key = %(chat_key)s
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"chat_key": chat_key})
            row = cur.fetchone()

    selected_context = row["selected_context"] if row else info["default_context"]
    updated_at = row["updated_at"] if row else None

    return {
        "chat_key": chat_key,
        "default_context": info["default_context"],
        "allowed_contexts": info["allowed_contexts"],
        "selected_context": selected_context,
        "updated_at": updated_at,
    }


def set_chat_context_state(chat_key: str, identity_key: str) -> dict:
    info = explain_chat_context(chat_key)
    if not info["known"]:
        raise HTTPException(status_code=404, detail="Unknown chat_key")

    if not is_allowed_context(chat_key, identity_key):
        raise HTTPException(status_code=400, detail="Context not allowed for this chat_key")

    query = """
    INSERT INTO chat_context_state (
        chat_key,
        selected_context
    )
    VALUES (
        %(chat_key)s,
        %(selected_context)s
    )
    ON CONFLICT (chat_key)
    DO UPDATE SET
        selected_context = EXCLUDED.selected_context,
        updated_at = NOW()
    RETURNING
        chat_key,
        selected_context,
        updated_at
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "chat_key": chat_key,
                    "selected_context": identity_key,
                },
            )
            row = cur.fetchone()

    return {
        "chat_key": row["chat_key"],
        "default_context": info["default_context"],
        "allowed_contexts": info["allowed_contexts"],
        "selected_context": row["selected_context"],
        "updated_at": row["updated_at"],
    }
