---
name: rag-answering
description: Shared rules for answering from retrieved documents - one focused search before answering, evidence with exact citations and quotes, honest "I don't know", confidence scoring and gap reporting in the AgentReport. Use whenever an answer is built from vector-store search results.
---

# Answering from retrieved evidence

## Search discipline
- Search before answering; never answer from memory.
- Start with one well-chosen search (see your domain skill for which tool). Search again only if the result is
  missing something specific - change the query or the tool, do not repeat the same call.
- Two or three searches are usually enough. Stop when the evidence answers the goal.

## Evidence
- Every fact in `findings` must be backed by an `evidence` item: `kind="doc"`, `ref` = document ID
  (e.g. `HR-POL-001-V3.0`), `page`, and a short verbatim `quote` (one or two sentences) that contains the fact.
- Use the tool result's `sources` (`doc_id`, `page`, `quote`) - do not paraphrase into the quote.
- Keep numbers, units and names exactly as written in the source.

## When the evidence is not enough
- If the documents do not contain the answer, say so plainly in `findings` ("The Leave Policy does not cover ...")
  and add the missing piece to `gaps`. An honest "not found" is a correct result; a guess is a failure.
- If sources conflict (e.g. superseded vs current version), report both and say which one applies.

## Confidence
- `0.9-1.0`: answer stated explicitly in a current source. `0.6-0.8`: answer needs light inference or one part is
  missing. `< 0.5`: weak or indirect evidence - explain in `gaps`.
