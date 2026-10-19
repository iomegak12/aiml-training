"""Validate the agent skills in ``src/skills`` and mirror them for coding assistants.

``src/skills`` is the single source of truth. The same folders are copied to:

- ``.claude/skills/``  - discovered by Claude Code (and by GitHub Copilot)
- ``.agents/skills/``  - discovered by OpenAI Codex (and by GitHub Copilot)

Copies (not symlinks) are used because symlinks need extra privileges on Windows.
Each mirror keeps a ``.skills-sync.json`` manifest listing the skills it manages, so a
skill removed from ``src/skills`` is removed from the mirror while skills you added to
the mirror by hand are left alone. ``check`` reports drift (a mirror edited directly or
not re-synced) and frontmatter problems, and is meant for CI or a pre-commit hook.
"""

from __future__ import annotations

import filecmp
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

MIRRORS = (".claude/skills", ".agents/skills")
MANIFEST = ".skills-sync.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


@dataclass
class SkillInfo:
    """A skill folder and its parsed frontmatter."""

    name: str
    path: Path
    description: str
    problems: list[str] = field(default_factory=list)


def parse_frontmatter(skill_md: Path) -> dict:
    """Return the YAML frontmatter of a ``SKILL.md`` (empty dict when missing or invalid)."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def skill_body(skill_md: Path) -> str:
    """The instructions of a ``SKILL.md`` without its frontmatter."""
    text = skill_md.read_text(encoding="utf-8")
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL).strip()


def load_skills(source: Path) -> list[SkillInfo]:
    """Read and validate every skill folder in ``source`` against the Agent Skills spec."""
    skills = []
    for folder in sorted(p for p in source.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        skill_md = folder / "SKILL.md"
        if not skill_md.is_file():
            skills.append(SkillInfo(folder.name, folder, "", ["missing SKILL.md"]))
            continue
        meta = parse_frontmatter(skill_md)
        name, description = str(meta.get("name", "")), str(meta.get("description", ""))
        problems = []
        if not meta:
            problems.append("missing or invalid YAML frontmatter")
        if name != folder.name:
            problems.append(f"name {name!r} must match folder name {folder.name!r}")
        if not NAME_RE.match(name) or len(name) > 64:
            problems.append("name must be lowercase letters, digits and single hyphens (max 64)")
        if not description:
            problems.append("description is required")
        elif len(description) > 1024:
            problems.append(f"description is {len(description)} characters (max 1024)")
        skills.append(SkillInfo(name or folder.name, folder, description, problems))
    return skills


def _tree_hash(folder: Path) -> str:
    """Content hash of every file under ``folder`` (paths and bytes), ignoring caches."""
    digest = hashlib.sha256()
    for file in sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                       and p.suffix != ".pyc"):
        digest.update(file.relative_to(folder).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def sync(project_root: Path, mirrors: tuple[str, ...] = MIRRORS) -> list[str]:
    """Copy every valid skill from ``src/skills`` into each mirror; returns a log of changes."""
    source = project_root / "src" / "skills"
    skills = load_skills(source)
    invalid = [f"{s.name}: {p}" for s in skills for p in s.problems]
    if invalid:
        raise ValueError("Fix the skills before syncing:\n  " + "\n  ".join(invalid))
    log = []
    for mirror in mirrors:
        target = project_root / mirror
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target / MANIFEST
        previous = set(json.loads(manifest_path.read_text(encoding="utf-8")).get("skills", [])) \
            if manifest_path.exists() else set()
        names = {s.name for s in skills}
        for stale in sorted(previous - names):
            shutil.rmtree(target / stale, ignore_errors=True)
            log.append(f"{mirror}/{stale}: removed (no longer in src/skills)")
        for skill in skills:
            dest = target / skill.name
            if dest.exists() and _tree_hash(dest) == _tree_hash(skill.path):
                continue
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(skill.path, dest, ignore=IGNORE)
            log.append(f"{mirror}/{skill.name}: updated")
        manifest_path.write_text(json.dumps({"source": "src/skills", "skills": sorted(names)}, indent=2) + "\n",
                                 encoding="utf-8")
    return log


def check(project_root: Path, mirrors: tuple[str, ...] = MIRRORS) -> list[str]:
    """Return every problem found: invalid frontmatter, missing or drifted mirror copies (empty = all good)."""
    source = project_root / "src" / "skills"
    problems = [f"src/skills/{s.name}: {p}" for s in load_skills(source) for p in s.problems]
    for mirror in mirrors:
        for skill in load_skills(source):
            dest = project_root / mirror / skill.name
            if not dest.exists():
                problems.append(f"{mirror}/{skill.name}: missing (run `make sync-skills`)")
            elif _tree_hash(dest) != _tree_hash(skill.path):
                diff = filecmp.dircmp(skill.path, dest)
                changed = diff.diff_files + diff.left_only + diff.right_only
                problems.append(f"{mirror}/{skill.name}: differs from src/skills {changed or '(nested files)'}")
    return problems
