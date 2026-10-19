"""Customer Support agent: identifies customers and summarises CRM profiles (read-only MCP tools)."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agentic_rag.agents.base import SpecialistSpec
from agentic_rag.mcp_client import CrmToolkit

SPEC = SpecialistSpec(
    name="customer_support",
    title="Customer Support agent (CRM profiles, read-only)",
    description="Find customers by ID, name, email or phone and report their profile: active status, credit "
                "limit, contact details, remarks such as products owned. Read-only.",
    skills=("customer-support",),
    system_prompt="""Identify the customer and report the profile facts the task needs, using the CRM tools.
Resolve identity carefully (see the customer-support skill); report ambiguity instead of guessing.
Evidence for CRM facts uses kind "crm" with the customer ID as ref and the relevant fields as quote.""",
    requires="crm",
)


def tools(crm: CrmToolkit) -> list[BaseTool]:
    """``get_customer_profile`` and ``search_customer_profiles`` from the CRM MCP server."""
    return list(crm.customer)
