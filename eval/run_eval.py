#!/usr/bin/env python3
"""Run gold-set evaluation against the live pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(REPO / ".env")

GOLD_PATH = REPO / "data" / "gold_questions.json"
RESULTS_PATH = REPO / "eval" / "results.md"

FAST_IDS = {
    "q001",
    "q003",
    "q005",
    "q006",
    "q010",
    "u001",
    "s001",
    "img001",
}

ABSTAIN = "not found in the provided documents"


def load_gold(fast: bool) -> list[dict]:
    if not GOLD_PATH.exists():
        print(f"Missing {GOLD_PATH}. Run: python scripts/make_test_pack.py", file=sys.stderr)
        sys.exit(1)
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    if fast:
        gold = [q for q in gold if q["id"] in FAST_IDS]
    return gold


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def extract_numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d+(?:\.\d+)?", text)]


def answer_matches(q: dict, answer: str, abstained: bool) -> bool:
    if q["type"] == "unanswerable":
        return abstained or ABSTAIN in answer.lower()
    expected = q.get("expected_answer") or ""
    if q.get("expected_numeric") is not None:
        exp = float(q["expected_numeric"])
        nums = extract_numbers(answer)
        if any(abs(n - exp) < 0.25 for n in nums):
            return True
    ans_n = normalize(answer)
    exp_n = normalize(expected)
    if not exp_n:
        return False
    return exp_n in ans_n or ans_n in exp_n or any(
        part in ans_n for part in exp_n.split(";") if len(part) > 8
    )


def citation_matches(q: dict, claims: list) -> bool:
    if q["type"] == "unanswerable":
        return True
    expected_docs = set(q.get("expected_docs") or [])
    expected_pages = set(q.get("expected_pages") or [])
    if not expected_docs:
        return True
    for claim in claims:
        for cit in claim.citations:
            name = getattr(cit, "doc_name", None) or getattr(cit, "doc_id", "")
            page = getattr(cit, "page", 0)
            if name in expected_docs and page in expected_pages:
                return True
    return False


def retrieval_recall_at_8(q: dict, doc_index) -> bool:
    from retrieval.hybrid import hybrid_search
    from retrieval.rerank import rerank_hits

    expected_docs = set(q.get("expected_docs") or [])
    expected_pages = set(q.get("expected_pages") or [])
    if q["type"] == "unanswerable":
        return True
    if not expected_docs:
        return False
    hits = hybrid_search(
        doc_index, q["question"], top_k=20, doc_ids=list(expected_docs)
    )
    top = rerank_hits(q["question"], hits, top_k=8)
    return any(
        h.element.doc_name in expected_docs and h.element.page in expected_pages
        for h in top
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run gold-set evaluation")
    parser.add_argument("--fast", action="store_true", help="Small subset to save quota")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip LLM /ask scoring")
    args = parser.parse_args()

    os.environ.setdefault("VERIFIER_SKIP_LLM", "1")

    gold = load_gold(args.fast)
    from app.config import get_settings
    from indexing.store import load_document_index

    settings = get_settings()
    index_dir = settings.resolve_path(settings.index_dir)
    if not index_dir.exists() or not list(index_dir.glob("*/elements.json")):
        print("Index missing. Run: python scripts/ingest_all.py", file=sys.stderr)
        sys.exit(1)

    doc_index = load_document_index(index_dir)
    has_key = bool(settings.gemini_api_key.strip())
    llm_eval = has_key and not args.retrieval_only

    ret_hits = 0
    ans_hits = 0
    cit_hits = 0
    abst_hits = 0
    llm_total = 0
    latencies: list[float] = []
    gemini_calls = 0
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"ans": 0, "n": 0, "cit": 0})

    from agent.gemini_client import get_gemini_client
    from agent.query_pipeline import ask

    client = get_gemini_client() if llm_eval else None
    unanswerable = [q for q in gold if q["type"] == "unanswerable"]

    for q in gold:
        if retrieval_recall_at_8(q, doc_index):
            ret_hits += 1

        if not llm_eval:
            continue

        llm_total += 1
        t0 = time.perf_counter()
        if client:
            client.reset_call_count()
        try:
            resp = ask(q["question"])
        except Exception as exc:
            print(f"  {q['id']} failed: {exc}")
            llm_total -= 1
            continue
        latencies.append(time.perf_counter() - t0)
        if client:
            gemini_calls += client.call_count

        qtype = q["type"]
        by_type[qtype]["n"] += 1
        if answer_matches(q, resp.answer, resp.abstained):
            ans_hits += 1
            by_type[qtype]["ans"] += 1
        if citation_matches(q, resp.claims):
            cit_hits += 1
            by_type[qtype]["cit"] += 1
        if qtype == "unanswerable" and (
            resp.abstained or ABSTAIN in resp.answer.lower()
        ):
            abst_hits += 1

    ret_total = len(gold)
    recall = ret_hits / ret_total if ret_total else 0.0
    ans_acc = ans_hits / llm_total if llm_total else 0.0
    cit_acc = cit_hits / llm_total if llm_total else 0.0
    abst_acc = abst_hits / len(unanswerable) if unanswerable and llm_eval else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    lines = [
        "# Eval results",
        "",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Questions: {len(gold)} ({'fast subset' if args.fast else 'full'})",
        f"- LLM eval: {'yes' if llm_eval else 'no (set GEMINI_API_KEY or drop --retrieval-only)'}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Retrieval recall@8 | {recall:.3f} ({ret_hits}/{ret_total}) |",
    ]
    if llm_eval:
        lines.extend(
            [
                f"| Answer accuracy | {ans_acc:.3f} ({ans_hits}/{llm_total}) |",
                f"| Citation accuracy | {cit_acc:.3f} ({cit_hits}/{llm_total}) |",
                f"| Abstention accuracy (unanswerable) | {abst_acc:.3f} ({abst_hits}/{len(unanswerable)}) |",
                f"| Avg latency (s) | {avg_lat:.2f} |",
                f"| Total Gemini calls | {gemini_calls} |",
                "",
                "## By question type",
                "",
                "| Type | Answer acc | Citation acc | N |",
                "| --- | --- | --- | --- |",
            ]
        )
        for t, stats in sorted(by_type.items()):
            n = stats["n"]
            if n:
                lines.append(
                    f"| {t} | {stats['ans']/n:.2f} | {stats['cit']/n:.2f} | {n} |"
                )

    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== Eval summary ===")
    print(f"retrieval recall@8: {recall:.3f}")
    if llm_eval:
        print(f"answer accuracy:    {ans_acc:.3f}")
        print(f"citation accuracy:  {cit_acc:.3f}")
        print(f"abstention acc:     {abst_acc:.3f}")
        print(f"avg latency:        {avg_lat:.2f}s")
        print(f"gemini calls:       {gemini_calls}")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
