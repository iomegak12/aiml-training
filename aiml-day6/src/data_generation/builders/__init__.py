"""Turn catalog facts into Documents with deterministic template prose."""

from __future__ import annotations

from data_generation.builders import hr_policy, phone_manual, tv_manual
from data_generation.catalog import PHONES, POLICIES, TVS
from data_generation.models import Document

ONLY_CHOICES = ("all", "products", "hr")


def build_all(only: str = "all") -> list[Document]:
    if only not in ONLY_CHOICES:
        raise ValueError(f"only must be one of {ONLY_CHOICES}, got {only!r}")
    docs: list[Document] = []
    if only in ("all", "products"):
        docs += [tv_manual.build(tv) for tv in TVS]
        docs += [phone_manual.build(p) for p in PHONES]
    if only in ("all", "hr"):
        docs += [hr_policy.build(p) for p in POLICIES]
    return docs
