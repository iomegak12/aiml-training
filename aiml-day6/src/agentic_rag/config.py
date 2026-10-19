"""Settings for the multi-agent RAG system, loaded from the project ``.env`` file.

``AgentSettings`` gathers everything the building blocks, specialist agents and the
Coordinator graph need: model names and reasoning efforts, API keys, judge thresholds,
retrieval knobs, Serper settings, graph budgets and state paths. Vector-store settings
are reused from :class:`data_ingestion.config.IngestionSettings`, so the agents always
read the same Chroma databases that the ingestion pipeline wrote.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from data_ingestion.config import DEFAULT_PROJECT_ROOT, IngestionSettings, StoreConfig

EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


def _str(name: str, default: str) -> str:
    """Return the stripped value of ``name`` or ``default`` when unset or empty."""
    return os.getenv(name, "").strip() or default


def _int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    """Return ``name`` as an integer within ``[minimum, maximum]``."""
    raw = os.getenv(name, "").strip()
    value = int(raw) if raw else default
    if value < minimum or (maximum is not None and value > maximum):
        upper = f" and <= {maximum}" if maximum is not None else ""
        raise ValueError(f"{name} must be >= {minimum}{upper}, got {value}")
    return value


def _effort(name: str, default: str) -> str:
    """Return a reasoning effort (``none`` ... ``xhigh``) from ``name``."""
    value = _str(name, default).lower()
    if value not in EFFORTS:
        raise ValueError(f"{name} must be one of {', '.join(EFFORTS)}, got {value!r}")
    return value


@dataclass(frozen=True)
class AgentSettings:
    """All settings for the multi-agent RAG system.

    Attributes:
        project_root: Repository root; relative paths resolve against it.
        ingestion: Vector-store settings shared with the ingestion pipeline.
        openai_api_key: Key used by the Coordinator, specialists and RAG steps.
        model: Main reasoning model (``OPENAI_MODEL``) used by the Coordinator.
        coordinator_effort: Reasoning effort for planning, reflection and synthesis.
        specialist_model: Model behind every specialist Deep Agent.
        specialist_effort: Reasoning effort for the specialists.
        fast_model: Model for small RAG steps (rewrite, grade, rerank, memory extraction).
        fast_effort: Reasoning effort for the fast model.
        judge_model: Judge model (``JUDGE_OPENAI_MODEL``).
        judge_api_key: Judge key (``JUDGE_OPENAI_API_KEY``, falls back to ``OPENAI_API_KEY``).
        judge_effort: Reasoning effort for the judge.
        judge_pass_score: Overall score (0-100) an answer needs to pass the judge.
        judge_max_retries: Extra attempts after a failed judgement before giving up.
        max_replans: Times the Coordinator may replan after reflection within one attempt.
        max_agent_calls: Upper bound on specialist runs per question (all attempts).
        rag_top_k: Passages handed to answer generation.
        rag_candidate_k: Candidates fetched per retriever before fusion and reranking.
        rrf_k: Reciprocal Rank Fusion constant.
        serper_api_key: Key for the Serper web-search API (``None`` disables research).
        serper_results: Results requested per web search.
        state_dir: Folder for the SQLite checkpointer and long-term store.
        mcp_config_path: JSON file describing the MCP servers the agents use.
        crm_mcp_url: URL of the CRM & Support MCP server.
        skills_dir: Source of truth for the agent skills (``src/skills``).
        golden_qa_path: Golden Q&A set used by the batch evaluation.
        eval_dir: Output folder for evaluation reports.
        eval_sample_size: Default number of golden questions per evaluation run.
    """

    project_root: Path
    ingestion: IngestionSettings
    openai_api_key: str | None
    model: str
    coordinator_effort: str
    specialist_model: str
    specialist_effort: str
    fast_model: str
    fast_effort: str
    judge_model: str
    judge_api_key: str | None
    judge_effort: str
    judge_pass_score: int
    judge_max_retries: int
    max_replans: int
    max_agent_calls: int
    rag_top_k: int
    rag_candidate_k: int
    rrf_k: int
    serper_api_key: str | None
    serper_results: int
    state_dir: Path
    mcp_config_path: Path
    crm_mcp_url: str
    skills_dir: Path
    golden_qa_path: Path
    eval_dir: Path
    eval_sample_size: int

    @classmethod
    def load(cls, project_root: Path | None = None) -> AgentSettings:
        """Load settings from ``<project_root>/.env`` (environment variables take precedence)."""
        ingestion = IngestionSettings.load(project_root or DEFAULT_PROJECT_ROOT)
        root = ingestion.project_root
        model = _str("OPENAI_MODEL", "gpt-5.1")
        fast_model = _str("OPENAI_FAST_MODEL", model)
        openai_key = os.getenv("OPENAI_API_KEY") or None
        return cls(
            project_root=root,
            ingestion=ingestion,
            openai_api_key=openai_key,
            model=model,
            coordinator_effort=_effort("COORDINATOR_REASONING_EFFORT", "high"),
            specialist_model=_str("SPECIALIST_MODEL", fast_model),
            specialist_effort=_effort("SPECIALIST_REASONING_EFFORT", "low"),
            fast_model=fast_model,
            fast_effort=_effort("OPENAI_FAST_REASONING_EFFORT", "low"),
            judge_model=_str("JUDGE_OPENAI_MODEL", model),
            judge_api_key=os.getenv("JUDGE_OPENAI_API_KEY") or openai_key,
            judge_effort=_effort("JUDGE_REASONING_EFFORT", "low"),
            judge_pass_score=_int("JUDGE_PASS_SCORE", 80, minimum=0, maximum=100),
            judge_max_retries=_int("JUDGE_MAX_RETRIES", 3, minimum=0, maximum=10),
            max_replans=_int("MAX_REPLANS", 2, minimum=0, maximum=10),
            max_agent_calls=_int("MAX_AGENT_CALLS", 8, minimum=1),
            rag_top_k=_int("RAG_TOP_K", 6, minimum=1),
            rag_candidate_k=_int("RAG_CANDIDATE_K", 20, minimum=1),
            rrf_k=_int("RRF_K", 60, minimum=1),
            serper_api_key=os.getenv("SERPER_API_KEY") or None,
            serper_results=_int("SERPER_RESULTS", 5, minimum=1, maximum=20),
            state_dir=(root / _str("AGENT_STATE_DIR", "data/agent_state")).resolve(),
            mcp_config_path=(root / _str("MCP_CONFIG_PATH", "config/mcp_servers.json")).resolve(),
            crm_mcp_url=_str("CRM_MCP_URL", f"http://localhost:{_str('MCP_PORT', '8765')}/mcp"),
            skills_dir=root / "src" / "skills",
            golden_qa_path=root / "data" / "golden_qa" / "golden_qa.jsonl",
            eval_dir=root / "data" / "eval",
            eval_sample_size=_int("EVAL_SAMPLE_SIZE", 20, minimum=1),
        )

    def store(self, key: str) -> StoreConfig:
        """Return the vector-store definition for ``key`` (``hr`` or ``products``)."""
        try:
            return self.ingestion.stores[key]
        except KeyError:
            raise ValueError(f"Unknown store {key!r}; expected one of {', '.join(self.ingestion.stores)}") from None

    def require_openai(self) -> str:
        """Return the OpenAI key or raise a clear error when it is missing."""
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set; add it to .env to run the agents.")
        return self.openai_api_key
