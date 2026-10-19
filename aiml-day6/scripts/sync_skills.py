"""Validate the agent skills in src/skills and mirror them to .claude/skills and .agents/skills.

Usage:
    uv run scripts/sync_skills.py sync    # copy src/skills -> .claude/skills and .agents/skills
    uv run scripts/sync_skills.py check   # exit 1 on invalid frontmatter or drifted mirrors (CI / pre-commit)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentic_rag.skills_sync import MIRRORS, check, load_skills, sync  # noqa: E402


def main() -> int:
    """Run ``sync`` or ``check`` and return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["sync", "check"])
    args = parser.parse_args()
    skills = load_skills(ROOT / "src" / "skills")
    if args.command == "sync":
        try:
            log = sync(ROOT)
        except ValueError as exc:
            print(exc)
            return 1
        print("\n".join(log) or "Mirrors already up to date.")
        print(f"{len(skills)} skills mirrored to: {', '.join(MIRRORS)}")
        return 0
    problems = check(ROOT)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"OK   {len(skills)} skills valid and in sync with {', '.join(MIRRORS)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
