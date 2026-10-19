"""Small LLM steps used by the RAG pipelines (all on the fast model, structured output).

- ``rewrite_query``: rephrase into a standalone, keyword-rich search query and extract filters.
- ``decompose_question``: split a compound question into independent sub-questions.
- ``grade_chunks``: judge each retrieved chunk relevant or not (corrective RAG).
- ``llm_rerank``: score candidates 0-10 for the question and reorder (advanced RAG).
- ``check_groundedness``: verify every statement of an answer against the context.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_rag.config import AgentSettings
from agentic_rag.llm import fast_llm, structured
from agentic_rag.retrieval.models import RetrievedChunk

STORE_HINTS = {
    "hr": "HR policies of Aranya Technologies (leave, travel, expenses, WFH, conduct, POSH, ...). "
          "Policies have versions; older versions are SUPERSEDED.",
    "products": "User manuals for TVs (Voltara Lumina, Lumenix QLED/OLED) and phones (Nexora Aria, Zentrix Z). "
                "Many manuals are near-duplicates, so the exact model matters.",
}


class QueryRewrite(BaseModel):
    """A search-ready version of the user's question."""

    query: str = Field(description="Standalone, keyword-rich search query; keep codes and numbers verbatim")
    brand: str | None = Field(default=None, description="Brand named in the question, if any")
    model: str | None = Field(default=None, description="Exact product model named in the question, e.g. 'Lumina 55 Pro'")
    model_number: str | None = Field(default=None, description="Model number such as 'VT-55L7Q', if given")
    include_superseded: bool = Field(default=False, description="True only if the user asks about an old/previous version")


class SubQuestions(BaseModel):
    """Independent sub-questions of a compound question."""

    questions: list[str] = Field(description="Self-contained sub-questions, each answerable on its own")


class ChunkGrade(BaseModel):
    """Relevance verdict for one numbered chunk."""

    index: int
    relevant: bool
    reason: str = ""


class ChunkGrades(BaseModel):
    """Relevance verdicts for all chunks."""

    grades: list[ChunkGrade]


class ChunkScore(BaseModel):
    """Rerank score for one numbered chunk."""

    index: int
    score: int = Field(ge=0, le=10, description="0 = useless, 10 = directly answers the question")


class ChunkScores(BaseModel):
    """Rerank scores for all chunks."""

    scores: list[ChunkScore]


class Groundedness(BaseModel):
    """Statement-level support check of an answer against its context."""

    grounded: bool = Field(description="True when every factual statement is supported by the context")
    score: int = Field(ge=0, le=100, description="Share of statements supported, 0-100")
    unsupported_statements: list[str] = Field(default_factory=list)


def _numbered(chunks: list[RetrievedChunk], max_chars: int = 900) -> str:
    """Render chunks as ``[i] label\\ntext`` blocks for grading and reranking prompts."""
    return "\n\n".join(f"[{i}] {c.label()}\n{c.text[:max_chars]}" for i, c in enumerate(chunks))


def rewrite_query(settings: AgentSettings, question: str, store: str, history: str = "") -> QueryRewrite:
    """Rewrite ``question`` into a search query for ``store`` and extract product/version filters."""
    prompt = (
        f"Knowledge base: {STORE_HINTS.get(store, store)}\n"
        f"{'Conversation so far: ' + history if history else ''}\n"
        "Rewrite the user's question as one standalone search query for this knowledge base: resolve "
        "pronouns, expand abbreviations, add likely section terms, keep error codes, model names and numbers "
        "exactly. Extract brand/model filters only when explicitly named.\n\n"
        f"Question: {question}"
    )
    return structured(fast_llm(settings), QueryRewrite).invoke(prompt)


def decompose_question(settings: AgentSettings, question: str, max_questions: int = 4) -> list[str]:
    """Split ``question`` into at most ``max_questions`` self-contained sub-questions (1 if it is simple)."""
    prompt = (
        f"Split the question into at most {max_questions} self-contained sub-questions that can each be "
        "searched separately. Repeat the product model or policy name in every sub-question. If the question "
        f"is already simple, return it unchanged as the only item.\n\nQuestion: {question}"
    )
    result = structured(fast_llm(settings), SubQuestions).invoke(prompt)
    questions = [q.strip() for q in result.questions if q.strip()][:max_questions]
    return questions or [question]


def grade_chunks(settings: AgentSettings, question: str, chunks: list[RetrievedChunk]) -> list[ChunkGrade]:
    """Grade each chunk as relevant or not to ``question`` (one LLM call for all chunks)."""
    if not chunks:
        return []
    prompt = (
        "For each numbered passage decide whether it contains information that helps answer the question. "
        "A passage about a different product model or a superseded policy version is NOT relevant unless "
        f"the question asks for it.\n\nQuestion: {question}\n\nPassages:\n{_numbered(chunks)}"
    )
    grades = structured(fast_llm(settings), ChunkGrades).invoke(prompt).grades
    by_index = {g.index: g for g in grades if 0 <= g.index < len(chunks)}
    return [by_index.get(i, ChunkGrade(index=i, relevant=False, reason="not graded")) for i in range(len(chunks))]


def llm_rerank(settings: AgentSettings, question: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]:
    """Rerank ``chunks`` by LLM relevance score (ties keep retrieval order) and return the best ``top_n``."""
    if len(chunks) <= 1:
        return chunks[:top_n]
    prompt = (
        "Score every numbered passage 0-10 for how directly it answers the question (exact model and current "
        f"policy version matter).\n\nQuestion: {question}\n\nPassages:\n{_numbered(chunks, 700)}"
    )
    scores = {s.index: s.score for s in structured(fast_llm(settings), ChunkScores).invoke(prompt).scores}
    order = sorted(range(len(chunks)), key=lambda i: (-scores.get(i, 0), i))
    return [chunks[i].model_copy(update={"score": float(scores.get(i, 0)), "retriever": "rerank",
                                         "ranks": {**chunks[i].ranks, "rerank": pos}})
            for pos, i in enumerate(order[:top_n], start=1)]


def check_groundedness(settings: AgentSettings, answer: str, context: str) -> Groundedness:
    """Check every factual statement in ``answer`` against ``context`` (corrective RAG self-check)."""
    prompt = (
        "Check the ANSWER against the CONTEXT statement by statement. A statement is supported only if the "
        "context states it (numbers, limits and model names must match). 'I don't know' style answers are "
        f"grounded.\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
    )
    return structured(fast_llm(settings), Groundedness).invoke(prompt)
