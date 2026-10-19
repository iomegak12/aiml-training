"""Metadata filters: known values per store and deterministic filter inference.

Near-duplicate manuals (Lumina 55 vs Lumina 55 Pro) are the classic failure of pure
semantic search. Pinning the model with a metadata filter fixes it. ``infer_filter``
spots a known model name, model number or document ID in the question (longest match
wins, so "Lumina 55 Pro" beats "Lumina 55") and returns the matching filter.
"""

from __future__ import annotations

import re

from agentic_rag.config import AgentSettings
from agentic_rag.retrieval.models import MetadataFilter
from agentic_rag.retrieval.stores import StoreKey, load_all_chunks

_FIELDS = ("doc_id", "brand", "model", "model_number", "family", "status")
_known: dict[str, dict[str, list[str]]] = {}


def known_values(settings: AgentSettings, key: StoreKey) -> dict[str, list[str]]:
    """Distinct ``doc_id``, ``brand``, ``model``, ``model_number``, ``family`` and ``status`` values in store ``key``."""
    cache_key = str(settings.store(key).persist_dir)
    if cache_key not in _known:
        values: dict[str, set[str]] = {f: set() for f in _FIELDS}
        for chunk in load_all_chunks(settings, key):
            for field in _FIELDS:
                value = chunk.doc_id if field == "doc_id" else chunk.metadata.get(field)
                if value:
                    values[field].add(str(value))
        _known[cache_key] = {f: sorted(v) for f, v in values.items()}
    return _known[cache_key]


def _mentions(text: str, value: str) -> bool:
    """True when ``value`` occurs in ``text`` as a whole phrase (case-insensitive)."""
    return re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", text, re.IGNORECASE) is not None


_VERSION = re.compile(r"\b(?:v|version\s*)(\d+\.\d+)\b", re.IGNORECASE)
_OLD_WORDS = re.compile(r"\b(previous|earlier|older|old|superseded|used to|before the (?:new|current))\b",
                        re.IGNORECASE)
_TITLE_STOPWORDS = {"policy", "and", "the", "of", "for", "user", "manual"}


def asks_for_old_version(question: str) -> bool:
    """True when the question explicitly asks about a past or a specific version ("v3.0", "previous policy")."""
    return bool(_VERSION.search(question) or _OLD_WORDS.search(question))


def versioned_document(settings: AgentSettings, key: StoreKey, question: str) -> str | None:
    """Document ID for an explicit "<title> v<N.N>" mention, e.g. "Travel Policy v3.0" -> ``HR-POL-002-V3.0``."""
    match = _VERSION.search(question)
    if not match:
        return None
    words = set(re.findall(r"[a-z]+", question.lower())) - _TITLE_STOPWORDS
    candidates = {c.doc_id for c in load_all_chunks(settings, key)
                  if str(c.metadata.get("version")) == match.group(1)
                  and words & (set(re.findall(r"[a-z]+", c.title.lower())) - _TITLE_STOPWORDS)}
    return candidates.pop() if len(candidates) == 1 else None


def infer_filter(settings: AgentSettings, key: StoreKey, question: str) -> MetadataFilter:
    """Infer a metadata filter from explicit mentions in ``question``.

    Order of preference: document ID, "<title> v<N.N>" (a specific policy version), model number,
    model name (longest first). Brand is added alongside a model so the filter stays unambiguous.
    Comparisons ("which Aria 12 models ...", two models of one family) filter on the ``family``.
    """
    values = known_values(settings, key)
    for doc_id in sorted(values["doc_id"], key=len, reverse=True):
        if _mentions(question, doc_id):
            return MetadataFilter(doc_id=doc_id)
    versioned = versioned_document(settings, key, question)
    if versioned:
        return MetadataFilter(doc_id=versioned)
    for number in sorted(values["model_number"], key=len, reverse=True):
        if _mentions(question, number):
            return MetadataFilter(model_number=number)
    models = mentioned_models(settings, key, question)
    if not models:
        return MetadataFilter()
    family = model_families(settings, key)
    families = {family.get(m) for m in models}
    if len(models) > 1 or _COMPARISON.search(question):
        # A comparison ("which Aria 12 models ...", "Z9 vs Z9 Ultra") needs every model of the family.
        if len(families) == 1 and None not in families:
            return MetadataFilter(family=families.pop())
        return MetadataFilter()
    brand = next((b for b in values["brand"] if _mentions(question, b)), None)
    return MetadataFilter(model=models[0], brand=brand)


_COMPARISON = re.compile(r"\b(models|variants|compare[sd]?|comparison|versus|vs\.?|difference|differences|among|"
                         r"which one|all (?:of )?the)\b", re.IGNORECASE)


def mentioned_models(settings: AgentSettings, key: StoreKey, question: str) -> list[str]:
    """Distinct models named in ``question``, longest first, without overlaps ("Z9 Plus" hides "Z9")."""
    found: list[str] = []
    remaining = question
    for model in sorted(known_values(settings, key)["model"], key=len, reverse=True):
        if _mentions(remaining, model):
            found.append(model)
            remaining = re.sub(rf"(?<![\w-]){re.escape(model)}(?![\w-])", " ", remaining, flags=re.IGNORECASE)
    return found


_families: dict[str, dict[str, str]] = {}


def model_families(settings: AgentSettings, key: StoreKey) -> dict[str, str]:
    """``model -> family`` map, e.g. ``"Aria 12 Pro" -> "Nexora Aria 12"``."""
    cache_key = str(settings.store(key).persist_dir)
    if cache_key not in _families:
        _families[cache_key] = {str(c.metadata["model"]): str(c.metadata["family"]) for c in load_all_chunks(settings, key)
                                if c.metadata.get("model") and c.metadata.get("family")}
    return _families[cache_key]


def current_successor(settings: AgentSettings, key: StoreKey, doc_id: str) -> str | None:
    """Current version of a superseded document (``HR-POL-001-V2.0`` -> ``HR-POL-001-V3.0``), else ``None``."""
    chunks = load_all_chunks(settings, key)
    if not any(c.doc_id == doc_id and c.metadata.get("status") == "superseded" for c in chunks):
        return None
    prefix = doc_id.rsplit("-V", 1)[0]
    return next((c.doc_id for c in chunks if c.doc_id.startswith(prefix + "-V")
                 and c.metadata.get("status") == "current"), None)


def normalise_filter(settings: AgentSettings, key: StoreKey, flt: MetadataFilter | None) -> MetadataFilter:
    """Snap user- or LLM-supplied filter values to the exact stored spelling; drop unknown values.

    Chroma filters are exact and case-sensitive, so "lumina 55 pro" must become
    "Lumina 55 Pro". A value that matches nothing is dropped rather than returning zero hits.
    """
    if flt is None or flt.is_empty():
        return MetadataFilter()
    values = known_values(settings, key)
    cleaned: dict[str, str] = {}
    for field, value in flt.constraints().items():
        if field not in values:
            cleaned[field] = value
            continue
        match = next((v for v in values[field] if v.casefold() == str(value).casefold()), None)
        if match:
            cleaned[field] = match
    return MetadataFilter(**cleaned)


def current_only(settings: AgentSettings, key: StoreKey, flt: MetadataFilter | None) -> MetadataFilter:
    """Add ``status="current"`` to ``flt`` when store ``key`` contains superseded documents.

    HR policies keep old versions for audit; without this constraint a superseded
    entitlement table can outrank the current one (the "version trap").
    """
    flt = flt or MetadataFilter()
    if flt.status is None and flt.doc_id is None and "superseded" in known_values(settings, key)["status"]:
        return flt.model_copy(update={"status": "current"})
    return flt
