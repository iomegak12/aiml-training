"""Settings loaded from the project ``.env`` file plus well-known project paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
REASONING_EFFORTS = ("none", "low", "medium", "high")


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    corpus_dir: Path
    qa_dir: Path
    cache_dir: Path
    openai_api_key: str | None
    openai_model: str
    reasoning_effort: str

    @property
    def llm_available(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def load(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or DEFAULT_PROJECT_ROOT).resolve()
        load_dotenv(root / ".env")
        data_dir = root / "data"
        effort = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower()
        return cls(
            project_root=root,
            data_dir=data_dir,
            corpus_dir=data_dir / "corpus",
            qa_dir=data_dir / "golden_qa",
            cache_dir=data_dir / "cache" / "llm",
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.1").strip(),
            reasoning_effort=effort if effort in REASONING_EFFORTS else "medium",
        )
