"""Deterministic golden question/answer set for RAG evaluation.

Answers come from the catalog (never from the LLM), and every answer carries
evidence strings that must appear verbatim on the cited PDF pages. Question
types:

- ``factual`` / ``table_lookup``  single fact from prose or a table
- ``near_duplicate``              value differs between sibling models
- ``version_conflict``            current vs superseded policy values
- ``comparison``                  needs several documents
- ``procedural``                  troubleshooting or process steps
- ``unanswerable``                not in the corpus; the system should say so
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from data_generation.builders import phone_manual, tv_manual
from data_generation.builders.hr_policy import doc_id_for
from data_generation.catalog import PHONES, POLICIES, TVS
from data_generation.qa.pdf_text import pages_containing

TV_QUESTIONS = [
    ("Native refresh rate", "What is the native refresh rate of the {name}?"),
    ("HDMI 2.1 ports", "How many HDMI 2.1 ports does the {name} have?"),
    ("Audio output", "What is the audio output of the {name}?"),
    ("VESA wall-mount pattern", "What VESA wall-mount pattern does the {name} use?"),
    ("Warranty", "What warranty comes with the {name}?"),
    ("Maximum retail price (MRP)", "What is the MRP of the {name} in India?"),
]
TV_ROTATING = [
    ("Weight without stand", "How much does the {name} weigh without its stand?"),
    ("Power consumption (typical)", "What is the typical power consumption of the {name}?"),
    ("HDR formats", "Which HDR formats does the {name} support?"),
    ("Wall-mount screws", "Which screws are needed to wall-mount the {name}?"),
]
PHONE_QUESTIONS = [
    ("Battery capacity", "What is the battery capacity of the {name}?"),
    ("Wired charging", "What is the maximum wired charging speed of the {name}?"),
    ("Wireless charging", "Does the {name} support wireless charging?"),
    ("Water and dust resistance", "What is the IP rating of the {name}?"),
    ("Software support", "How many years of software support does the {name} get?"),
    ("SAR (head)", "What is the head SAR value of the {name}?"),
]
PHONE_ROTATING = [
    ("Rear cameras", "What rear cameras does the {name} have?"),
    ("Charger in the box", "What charger is included in the box with the {name}?"),
    ("Memory card", "Does the {name} support a memory card?"),
    ("Maximum retail price (MRP)", "What is the MRP of the {name}?"),
    ("SIM", "What SIM configuration does the {name} support?"),
]

UNANSWERABLE = [
    ("What is the native refresh rate of the Voltara Lumina 75 Pro?", "product_manual"),
    ("What is the battery capacity of the Nexora Aria 13?", "product_manual"),
    ("What is the price of the Lumenix OLED O77?", "product_manual"),
    ("What is the screen size of the Zentrix Z9 Ultra Max?", "product_manual"),
    ("Does the Voltara Lumina 55 Pro support satellite TV reception without a set-top box via DVB-S2?", "product_manual"),
    ("What is the employee referral bonus amount at Aranya Technologies?", "hr_policy"),
    ("What is the canteen meal subsidy per day at Aranya?", "hr_policy"),
    ("How many days of pet adoption leave does Aranya provide?", "hr_policy"),
]
NOT_IN_CORPUS = "Not available in the corpus. The system should say it does not know rather than guess."


def _name(p: dict) -> str:
    return f"{p['brand']} {p['model']}"


def _value(rows: list[list[str]], label: str) -> str:
    return next(v for k, v in rows if k == label)


def _qa(question, answer, category, qtype, difficulty, sources):
    return {"question": question, "answer": answer, "category": category, "question_type": qtype,
            "difficulty": difficulty, "sources": sources}


def _src(doc_id: str, evidence: list[str]) -> dict:
    return {"doc_id": doc_id, "evidence": evidence}


def _spec_questions(products: list[dict], spec_rows, base: list, rotating: list) -> list[dict]:
    items = []
    rows_by_id = {p["doc_id"]: spec_rows(p) for p in products}
    for i, p in enumerate(products):
        rows = rows_by_id[p["doc_id"]]
        family_rows = [rows_by_id[q["doc_id"]] for q in products if q["family"] == p["family"] and q is not p]
        for label, template in base + [rotating[i % len(rotating)]]:
            value = _value(rows, label)
            differs = any(_value(r, label) != value for r in family_rows)
            qtype, difficulty = ("near_duplicate", "medium") if differs else ("table_lookup", "easy")
            items.append(_qa(template.format(name=_name(p)), value, "product_manual", qtype, difficulty,
                             [_src(p["doc_id"], [label, value])]))
    return items


def _tv_extras() -> list[dict]:
    items = []
    for tv in TVS:
        code, meaning, action = tv["error_codes"][-1]
        items.append(_qa(f"What does error code {code} mean on the {_name(tv)}, and what should I do?",
                         f"{meaning} {action}", "product_manual", "procedural", "medium",
                         [_src(tv["doc_id"], [code, meaning])]))
        if not tv["vrr"]:
            items.append(_qa(f"My console shows a blank screen at 120 Hz on the {_name(tv)}. What should I do?",
                             f"The {_name(tv)} supports up to {tv['refresh_hz']} Hz only; set the console video output "
                             "to 4K at 60 Hz.", "product_manual", "near_duplicate", "hard",
                             [_src(tv["doc_id"], ["Console shows a blank screen at 120 Hz", "Set the console video output to 4K at 60 Hz."])]))
    return items


def _comparisons() -> list[dict]:
    items = []

    def compare(question, products, rows_fn, label, pick, fmt):
        winner = pick(products)
        rows = {p["doc_id"]: rows_fn(p) for p in products}
        answer = fmt(winner) + " Values: " + "; ".join(f"{_name(p)}: {_value(rows[p['doc_id']], label)}" for p in products) + "."
        items.append(_qa(question, answer, "product_manual", "comparison", "hard",
                         [_src(p["doc_id"], [label, _value(rows[p["doc_id"]], label)]) for p in products]))

    aria = [p for p in PHONES if p["family"] == "Nexora Aria 12"]
    z9 = [p for p in PHONES if p["family"] == "Zentrix Z9"]
    lumina = [t for t in TVS if t["family"] == "Voltara Lumina"]
    lumenix_55 = [t for t in TVS if t["brand"] == "Lumenix" and t["screen_size_in"] == 55]

    compare("Which Nexora Aria 12 model has the largest battery?", aria, phone_manual.spec_rows, "Battery capacity",
            lambda ps: max(ps, key=lambda p: p["battery_mah"]), lambda w: f"The {_name(w)} ({w['battery_mah']} mAh).")
    compare("Which Zentrix Z9 series phone charges fastest with a cable?", z9, phone_manual.spec_rows, "Wired charging",
            lambda ps: max(ps, key=lambda p: p["wired_w"]), lambda w: f"The {_name(w)} ({w['wired_w']} W).")
    compare("Which Nexora Aria 12 models are rated IP68?", aria, phone_manual.spec_rows, "Water and dust resistance",
            lambda ps: [p for p in ps if p["ip_rating"] == "IP68"],
            lambda ws: "Only the " + ", ".join(_name(w) for w in ws) + ".")
    compare("Which Zentrix phones support wireless charging?", [p for p in PHONES if p["brand"] == "Zentrix"],
            phone_manual.spec_rows, "Wireless charging", lambda ps: [p for p in ps if p["wireless_w"]],
            lambda ws: "Only the " + ", ".join(_name(w) for w in ws) + ".")
    compare("Which Voltara Lumina TVs support a 120 Hz refresh rate?", lumina, tv_manual.spec_rows, "Native refresh rate",
            lambda ts: [t for t in ts if t["refresh_hz"] >= 120],
            lambda ws: "The " + " and ".join(_name(w) for w in ws) + ".")
    compare("Among the Lumenix 55-inch TVs, which one has the most HDMI 2.1 ports?", lumenix_55, tv_manual.spec_rows,
            "HDMI 2.1 ports", lambda ts: max(ts, key=lambda t: t["hdmi21_ports"]),
            lambda w: f"The {_name(w)} ({w['hdmi21_ports']} HDMI 2.1 ports).")
    compare("What is the difference in warranty between the Voltara Lumina 55 and Lumina 55 Pro?",
            [t for t in lumina if t["screen_size_in"] == 55], tv_manual.spec_rows, "Warranty",
            lambda ts: max(ts, key=lambda t: t["warranty_years"]),
            lambda w: f"The {_name(w)} has the longer warranty.")
    compare("Which Zentrix phone is the lightest?", [p for p in PHONES if p["brand"] == "Zentrix"], phone_manual.spec_rows,
            "Weight", lambda ps: min(ps, key=lambda p: p["weight_g"]), lambda w: f"The {_name(w)} ({w['weight_g']} g).")
    return items


def _hr_questions() -> list[dict]:
    items = []
    for policy in POLICIES:
        doc_id = doc_id_for(policy)
        for q in policy["qa"]:
            items.append(_qa(q["question"], q["answer"], "hr_policy", q["type"], q["difficulty"],
                             [_src(doc_id, q["evidence"])]))
    return items


def build_questions() -> list[dict]:
    items = (_spec_questions(TVS, tv_manual.spec_rows, TV_QUESTIONS, TV_ROTATING)
             + _tv_extras()
             + _spec_questions(PHONES, phone_manual.spec_rows, PHONE_QUESTIONS, PHONE_ROTATING)
             + _comparisons()
             + _hr_questions()
             + [_qa(q, NOT_IN_CORPUS, cat, "unanswerable", "medium", []) for q, cat in UNANSWERABLE])
    for i, item in enumerate(items, start=1):
        item["id"] = f"Q{i:04d}"
    return items


def generate(pdf_paths: dict[str, Path], corpus_dir: Path, out_dir: Path) -> list[dict]:
    """Build the Q&A set, locate evidence pages in the rendered PDFs and write JSONL + CSV.

    Questions whose source documents were not generated (e.g. ``--only hr``) are skipped.
    """
    items = []
    for item in build_questions():
        if any(s["doc_id"] not in pdf_paths for s in item["sources"]):
            continue
        for source in item["sources"]:
            path = pdf_paths[source["doc_id"]]
            source["file"] = path.relative_to(corpus_dir).as_posix()
            source["pages"] = pages_containing(path, source["evidence"])
        items.append(item)

    out_dir.mkdir(parents=True, exist_ok=True)
    ordered = [{"id": it["id"], **{k: v for k, v in it.items() if k != "id"}} for it in items]
    with (out_dir / "golden_qa.jsonl").open("w", encoding="utf-8") as fh:
        for item in ordered:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (out_dir / "golden_qa.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "question", "answer", "category", "question_type", "difficulty",
                         "source_docs", "source_files", "source_pages", "evidence"])
        for it in ordered:
            s = it["sources"]
            writer.writerow([it["id"], it["question"], it["answer"], it["category"], it["question_type"],
                             it["difficulty"], "; ".join(x["doc_id"] for x in s), "; ".join(x["file"] for x in s),
                             "; ".join(f"{x['doc_id']}:{','.join(map(str, x['pages']))}" for x in s),
                             " || ".join(" | ".join(x["evidence"]) for x in s)])
    return ordered
