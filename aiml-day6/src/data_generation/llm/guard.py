"""Guard rails that keep LLM prose consistent with the catalog facts.

An LLM rewrite is accepted only if it introduces no number that is absent from
the section's facts and template text, and does not mention a sibling model
(which would poison near-duplicate retrieval). Rejected rewrites fall back to
the template text, so the golden Q&A answers always remain true.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_MARKDOWN = re.compile(r"(^\s*[-*#>]|\*\*|__|`)", re.MULTILINE)


def numbers(text: str) -> set[str]:
    """Numeric tokens with thousands separators removed (1,00,000 and 100,000 -> 100000)."""
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _mentions(name: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


def check(output: str, allowed_text: str, own_model: str = "", siblings: list[str] | None = None) -> tuple[bool, str]:
    if len(output.split()) < 15:
        return False, "output too short"
    if _MARKDOWN.search(output):
        return False, "contains markdown or list formatting"
    new_numbers = numbers(output) - numbers(allowed_text)
    if new_numbers:
        return False, f"introduces numbers not in facts: {sorted(new_numbers)}"
    siblings = siblings or []
    # Siblings whose name is contained in our own name (e.g. "Z9" inside "Z9 Plus") are only
    # checked after removing our own name from the text.
    without_own = re.sub(rf"(?<![\w-]){re.escape(own_model)}(?![\w-])", "", output) if own_model else output
    for sibling in siblings:
        text = without_own if own_model and sibling in own_model else output
        if _mentions(sibling, text):
            return False, f"mentions sibling model '{sibling}'"
    return True, "accepted"
