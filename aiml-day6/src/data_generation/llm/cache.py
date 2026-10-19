"""JSON file cache for LLM outputs, one file per document section.

The cache key hashes what defines the content (model, instructions and
prompt), so editing a template or switching models invalidates exactly the
affected sections. Reasoning effort is deliberately *not* part of the key: it
is a speed/quality knob, so changing it reuses existing prose. Use
``--refresh`` to regenerate at a different effort.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def cache_key(model: str, instructions: str, prompt: str) -> str:
    payload = "\x1f".join([model, instructions, prompt]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


class LLMCache:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, doc_id: str, section_id: str) -> Path:
        return self.root / doc_id / f"{section_id}.json"

    def get(self, doc_id: str, section_id: str, key: str) -> str | None:
        path = self._path(doc_id, section_id)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return record.get("output") if record.get("key") == key else None

    def put(self, doc_id: str, section_id: str, key: str, model: str, effort: str, prompt: str, output: str) -> None:
        path = self._path(doc_id, section_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "doc_id": doc_id,
            "section_id": section_id,
            "model": model,
            "reasoning_effort": effort,
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "prompt": prompt,
            "output": output,
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
