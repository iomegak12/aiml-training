---
name: hr-policies
description: Answer questions about Aranya Technologies HR policies (leave, travel and expenses, medical insurance, code of conduct, POSH, hybrid work/WFH, IT security, data privacy, attendance and overtime, appraisals, whistleblowing, anti-bribery, notice period and F&F) from the HR policy vector store, using the current policy version and citing policy ID, version and page. Use for any employee-policy, entitlement, allowance or HR-process question.
---

# HR policies

Knowledge source: the **`hr` vector store** (15 PDFs, collection `hr_policies`). Never answer HR questions from
general knowledge - entitlements are company-specific.

## Which search to use
| Situation | Tool (agent) | Why |
|---|---|---|
| Default for most questions | `advanced_search` | rewrites the question, current versions only, LLM rerank |
| Question names a policy ID or exact term (`HR-POL-004`, "per diem", "Tier X") | `hybrid_search` | BM25 keyword match plus vectors, fastest |
| Two or more questions in one ("casual leave **and** meal allowance") | `multi_query_search` | searches each part separately, then fuses |
| Unsure the policy covers it, or first search looked weak | `corrective_search` | grades evidence, broadens, says "I don't know" |

Coding assistants (Claude Code, Codex, Copilot) can run the same retrieval from the shell:
`uv run python <this skill folder>/scripts/search.py "question" --pipeline advanced`.

## Version rules (the "version trap")
- Two policies have older versions kept for audit: **Leave Policy** (v2.0 superseded by v3.0, 1 April 2025) and
  **Travel and Expense Claims** (v3.0 superseded by v4.0, 1 January 2026).
- Answer from the **current** version. Mention the superseded value only if the user asks about the past or
  the values changed in a way the user may have heard about ("it used to be 7 days; since v3.0 it is 8").
- Search with `include_superseded=true` only when the user explicitly asks about an old version.

## Policy catalogue
| ID | Policy | Current version |
|---|---|---|
| HR-POL-001 | Leave Policy | v3.0 (v2.0 superseded) |
| HR-POL-002 | Travel and Expense Claims | v4.0 (v3.0 superseded) |
| HR-POL-003 | Medical Reimbursement and Group Health Insurance | v2.1 |
| HR-POL-004 | Code of Conduct and Ethics | v5.0 |
| HR-POL-005 | Prevention of Sexual Harassment (POSH) | v3.0 |
| HR-POL-006 | Hybrid Work and Work From Home | v2.0 |
| HR-POL-007 | IT Acceptable Use and Information Security | v4.2 |
| HR-POL-008 | Data Privacy and Confidentiality | v1.1 |
| HR-POL-009 | Attendance, Working Hours and Overtime | v2.3 |
| HR-POL-010 | Performance Management and Appraisal | v3.0 |
| HR-POL-011 | Whistleblower and Grievance Redressal | v2.0 |
| HR-POL-012 | Anti-Bribery and Anti-Corruption | v2.1 |
| HR-POL-013 | Separation, Notice Period and Full and Final Settlement | v2.2 |

## Answer style
- Lead with the number or rule, then conditions and exceptions (eligibility, caps, approvals).
- Cite as `HR-POL-001-V3.0 p.2`. Follow the `rag-answering` skill for evidence and confidence.
- Sensitive topics (POSH, whistleblowing, grievances): state the process and the confidential channel; do not
  speculate about individual cases.
