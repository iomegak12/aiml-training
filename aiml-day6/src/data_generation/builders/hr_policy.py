"""Builds an HR policy Document from a catalog entry."""

from __future__ import annotations

import re

from data_generation.catalog import COMPANY
from data_generation.models import Bullets, DocMeta, Document, Notice, Paragraph, Section, Table

NON_COMPLIANCE = ("Violation of this policy may result in disciplinary action, up to and including termination of "
                  "employment, in line with the Code of Conduct and Ethics (HR-POL-004). Where a violation also breaches "
                  "the law, Aranya may report it to the appropriate authorities.")


def doc_id_for(policy: dict) -> str:
    return f"{policy['policy_id']}-V{policy['version']}"


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title.replace("&", "and")).strip("_")


def _control_table(policy: dict) -> Table:
    rows = [
        ["Policy ID", policy["policy_id"]],
        ["Document title", policy["title"]],
        ["Version", policy["version"]],
        ["Status", "SUPERSEDED - for reference only" if policy.get("status") == "superseded" else "Current - in force"],
        ["Effective date", policy["effective_date"]],
        ["Policy owner", policy["owner"]],
        ["Approved by", policy["approver"]],
        ["Review cycle", policy["review_cycle"]],
    ]
    if policy.get("supersedes"):
        rows.append(["Supersedes", policy["supersedes"]])
    if policy.get("superseded_by"):
        rows.append(["Superseded by", policy["superseded_by"]])
    rows.append(["Applies to", f"{COMPANY['name']} (CIN {COMPANY['cin']})"])
    return Table(rows=rows, col_widths=[0.28, 0.72], caption="Document control")


def build(policy: dict) -> Document:
    status = policy.get("status", "current")
    preamble = []
    if status == "superseded":
        preamble.append(Notice(
            f"SUPERSEDED: Version {policy['version']} of the {policy['title']} has been replaced by "
            f"{policy['superseded_by']}. It is retained for audit and reference only and must not be used for current "
            "decisions.", kind="superseded"))
    preamble.append(_control_table(policy))

    sections: list[Section] = []

    def add(sid: str, title: str, blocks: list, facts: dict | None = None) -> None:
        sections.append(Section(id=sid, title=f"{len(sections) + 1}. {title}", blocks=blocks, facts=facts or {}))

    add("purpose", "Purpose", [Paragraph(policy["purpose"], enrich=True)], {"policy": policy["title"]})
    add("scope", "Scope", [Paragraph(policy["scope"], enrich=True)], {"company": COMPANY["name"]})
    add("definitions", "Definitions",
        [Table(header=["Term", "Meaning"], rows=[list(d) for d in policy["definitions"]], col_widths=[0.28, 0.72])])
    for i, (title, intro, blocks) in enumerate(policy["body"], start=1):
        lead = [Paragraph(intro, enrich=True)] if intro else []
        add(f"body_{i}", title, lead + list(blocks), {"section": title})
    add("procedure", "Procedure", [Bullets(policy["procedure"], ordered=True)])
    add("exceptions", "Exceptions and Approvals", [Paragraph(policy["exceptions"])])
    add("non_compliance", "Non-Compliance", [Paragraph(NON_COMPLIANCE)])
    faq_blocks = []
    for q, a in policy["faqs"]:
        faq_blocks += [Paragraph(f"**Q: {q}**"), Paragraph(f"A: {a}")]
    add("faqs", "Frequently Asked Questions", faq_blocks)
    add("related", "Related Policies and Contacts", [
        Bullets(policy["related"]),
        Paragraph(f"For questions about this policy, contact the HR helpdesk at {COMPANY['hr_email']} or on extension "
                  f"{COMPANY['hr_extension']}, or raise a ticket in {COMPANY['hrms']}."),
    ])
    add("revisions", "Revision History",
        [Table(header=["Version", "Effective date", "Summary of changes"], rows=[list(r) for r in policy["revisions"]],
               col_widths=[0.13, 0.22, 0.65])])
    add("acknowledgement", "Acknowledgement", [Paragraph(
        f"Employees are required to read this policy and acknowledge it in {COMPANY['hrms']}. Acknowledgement confirms that "
        "the employee has understood the policy and agrees to comply with it. Aranya reserves the right to amend this "
        "policy at any time; changes are communicated by email and published on the intranet.")])

    doc_id = doc_id_for(policy)
    meta = DocMeta(
        doc_id=doc_id,
        title=policy["title"],
        subtitle=f"Version {policy['version']} | Effective {policy['effective_date']}",
        category="hr_policy",
        subcategory="hr",
        publisher=COMPANY["name"],
        version=policy["version"],
        effective_date=policy["effective_date"],
        filename=f"{policy['policy_id']}_{_slug(policy['title'])}_v{policy['version']}.pdf",
        relative_dir="hr_policies",
        page_range=(3, 4),
        status=status,
        supersedes=policy.get("supersedes"),
        superseded_by=policy.get("superseded_by"),
        keywords=["HR policy", "India", policy["policy_id"], policy["title"], f"v{policy['version']}", status],
    )
    return Document(meta=meta, sections=sections, facts=policy, preamble=preamble)
