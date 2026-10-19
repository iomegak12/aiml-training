---
name: product-support
description: Troubleshoot and answer questions about Voltara and Lumenix TVs and Nexora and Zentrix phones from the product-manual vector store - specifications, setup, error codes (e.g. E-715), connectivity, charging, warranty and safety - always pinned to the exact model. Use for any product, device, error-code or troubleshooting question.
---

# Product support

Knowledge source: the **`products` vector store** (15 user manuals, collection `product_manuals`).

## Pin the exact model first
Manuals in a family are near-duplicates (Lumina 55 vs **Lumina 55 Pro**, Z9 vs Z9 Plus vs Z9 Ultra, Aria 12 vs
12 Lite vs 12 Pro). Specifications and error codes differ between them, so:
1. Find the model in the question, the conversation, or the customer's profile/ticket (`product_model`).
2. Pass it as the `model` (and `brand`) argument of the search tool. Model numbers (`VT-55L7Q`) also work.
3. If the model is unknown and the answer differs between models, say which models you checked or report the
   gap - never blend two manuals.

| Brand | Type | Models (model number) |
|---|---|---|
| Voltara | TV | Lumina 43 (VT-43L5U), Lumina 55 (VT-55L5U), Lumina 55 Pro (VT-55L7Q), Lumina 65 Pro (VT-65L7Q) |
| Lumenix | TV | QLED Q50 (LX-50Q6), QLED Q55 (LX-55Q6), QLED Q55X (LX-55Q8X), OLED O65 (LX-65O9) |
| Nexora | Phone | Aria 12 (NX-A12), Aria 12 Lite (NX-A12L), Aria 12 Pro (NX-A12P) |
| Zentrix | Phone | Z5 (ZX-Z5), Z9 (ZX-Z9), Z9 Plus (ZX-Z9P), Z9 Ultra (ZX-Z9U) |

## Which search to use
| Situation | Tool | Why |
|---|---|---|
| Error codes, model numbers, exact settings names | `hybrid_search` | BM25 matches `E-715` literally |
| Symptom descriptions ("screen flickers with my console") | `advanced_search` | rewrite + rerank |
| Several questions about one or more models | `multi_query_search` | one search per part |
| Feature may not exist on this model; weak first results | `corrective_search` | grades, broadens, "I don't know" |

Coding assistants can run `uv run python <this skill folder>/scripts/search.py "E-715" --model "Lumina 55 Pro"`.

## Troubleshooting answers
- Give numbered steps from the manual in order; include the meaning of the error code first.
- Quote limits exactly (charging wattage, refresh rate, HDMI port numbers).
- If the manual says to contact service, or steps do not fix the issue, say so - the Coordinator may then
  propose a support ticket through the Ticket Management agent.
- Cite as `TV-VOL-L55P p.7`. Follow the `rag-answering` skill.
