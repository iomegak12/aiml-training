"""Short-term and long-term memory backed by SQLite files in ``AGENT_STATE_DIR``.

- **Short-term (thread) memory**: an ``AsyncSqliteSaver`` checkpointer. Every graph step of a
  ``thread_id`` is saved, so follow-up questions see the conversation and an interrupted run
  (clarification, approval) resumes exactly where it stopped - even after a restart.
- **Long-term (user) memory**: an ``AsyncSqliteStore``. The Coordinator saves durable facts
  about a user (name, products owned, customer ID, preferences) under
  ``("users", user_id, "facts")`` and recalls them on every new thread.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.base import BaseStore
from langgraph.store.sqlite.aio import AsyncSqliteStore

from agentic_rag.config import AgentSettings

CHECKPOINT_DB = "checkpoints.sqlite"
STORE_DB = "long_term_memory.sqlite"


def facts_namespace(user_id: str) -> tuple[str, ...]:
    """Store namespace that holds the long-term facts of ``user_id``."""
    return ("users", user_id, "facts")


@dataclass
class Memory:
    """The open checkpointer (short-term) and store (long-term)."""

    checkpointer: AsyncSqliteSaver
    store: AsyncSqliteStore


@asynccontextmanager
async def open_memory(settings: AgentSettings) -> AsyncIterator[Memory]:
    """Open both SQLite databases for the lifetime of the ``async with`` block."""
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    async with (
        AsyncSqliteSaver.from_conn_string(str(settings.state_dir / CHECKPOINT_DB)) as checkpointer,
        AsyncSqliteStore.from_conn_string(str(settings.state_dir / STORE_DB)) as store,
    ):
        await checkpointer.setup()
        await store.setup()
        yield Memory(checkpointer=checkpointer, store=store)


async def recall_facts(store: BaseStore, user_id: str, limit: int = 50) -> list[str]:
    """Return the saved facts about ``user_id``, oldest first."""
    items = await store.asearch(facts_namespace(user_id), limit=limit)
    items.sort(key=lambda item: item.created_at)
    return [str(item.value.get("fact", "")) for item in items if item.value.get("fact")]


async def remember_facts(store: BaseStore, user_id: str, facts: list[str], source_thread: str = "") -> int:
    """Save new ``facts`` about ``user_id`` (exact duplicates, ignoring case, are skipped); returns the count saved."""
    known = {f.casefold() for f in await recall_facts(store, user_id, limit=500)}
    saved = 0
    for fact in facts:
        fact = fact.strip()
        if not fact or fact.casefold() in known:
            continue
        await store.aput(facts_namespace(user_id), uuid.uuid4().hex,
                         {"fact": fact, "thread_id": source_thread, "saved_at": datetime.now(UTC).isoformat()})
        known.add(fact.casefold())
        saved += 1
    return saved


async def forget_user(store: BaseStore, user_id: str) -> int:
    """Delete every long-term fact about ``user_id``; returns the number deleted."""
    items = await store.asearch(facts_namespace(user_id), limit=1000)
    for item in items:
        await store.adelete(item.namespace, item.key)
    return len(items)
