"""The contract between specialists and the Coordinator: a structured ``AgentReport``.

Specialists never return free text. Each run ends with a report the Coordinator can
reason over: what was found, the evidence behind it, how confident the agent is, what
is still missing, and - for the Ticket Management agent - ticket writes it *proposes*
for human approval.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TicketTool = Literal["register_ticket", "resolve_ticket"]


class Evidence(BaseModel):
    """One piece of evidence behind a finding.

    ``kind`` decides what ``ref`` holds: a document ID (``doc``), a customer or ticket ID
    (``crm``), a URL (``web``) or a ticket ID created/changed by an approved action (``action``).
    """

    kind: Literal["doc", "crm", "web", "action"]
    ref: str = Field(description="doc_id (e.g. HR-POL-001-V3.0), CUST-/TKT- ID, or URL")
    page: int | None = Field(default=None, description="PDF page for documents")
    title: str | None = Field(default=None, description="Document, record or web page title")
    date: str | None = Field(default=None, description="Publication date for web results")
    quote: str = Field(description="Short verbatim excerpt (or record fields) that supports the finding")

    def cite(self) -> str:
        """Compact citation such as ``HR-POL-001-V3.0 p.2``, ``TKT-000119`` or a URL."""
        return f"{self.ref} p.{self.page}" if self.page else self.ref


class ProposedAction(BaseModel):
    """A ticket write proposed by the Ticket Management agent; executed only after human approval."""

    tool: TicketTool
    reason: str = Field(description="Why this action is needed")
    customer_id: str | None = Field(default=None, description="register_ticket: customer raising the ticket")
    title: str | None = Field(default=None, description="register_ticket: short specific title")
    description: str | None = Field(default=None, description="register_ticket: details and steps already tried")
    priority: Literal["low", "medium", "high", "critical"] | None = Field(default=None)
    product_model: str | None = Field(default=None, description="register_ticket: exact product model")
    ticket_id: str | None = Field(default=None, description="resolve_ticket: ticket to resolve")
    resolved_by: str | None = Field(default=None, description="resolve_ticket: who resolved it")
    resolution_remarks: str | None = Field(default=None, description="resolve_ticket: how it was resolved")

    def arguments(self) -> dict[str, str]:
        """Arguments for the MCP tool (only the fields that tool accepts, without empty values)."""
        fields = (("customer_id", "title", "description", "priority", "product_model") if self.tool == "register_ticket"
                  else ("ticket_id", "resolved_by", "resolution_remarks"))
        return {f: getattr(self, f) for f in fields if getattr(self, f)}

    def signature(self) -> str:
        """Stable key used to avoid asking for approval of the same action twice."""
        return f"{self.tool}:" + "|".join(f"{k}={v}" for k, v in sorted(self.arguments().items())
                                          if k in ("customer_id", "title", "ticket_id"))


class AgentReportDraft(BaseModel):
    """What a specialist returns (its structured response)."""

    findings: str = Field(description="Answer to the step goal in a few sentences, with the key facts")
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, description="0-1: how well the evidence supports the findings")
    gaps: list[str] = Field(default_factory=list, description="What could not be found or verified")
    proposed_actions: list[ProposedAction] = Field(default_factory=list,
                                                   description="Ticket writes needing human approval")


class AgentReport(AgentReportDraft):
    """A specialist's draft plus run metadata added by the system (not by the model)."""

    agent: str
    step_id: str
    goal: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str | None = None

    @property
    def duration_s(self) -> float:
        """Wall-clock seconds the specialist ran."""
        return round(self.finished_at - self.started_at, 1)
