"""Problem 4: run all 12 practice docs with the prompt cache off, then on.

    python scripts/cache_test.py

Saves every model call to output/cache_test.json and prints a summary.
The no-cache setup runs first so the cached setup starts cold and shows its own cache write.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic_ai.messages import ModelResponse  # noqa: E402

import agent  # noqa: E402
from tools import now_iso  # noqa: E402

DOCS = sorted((ROOT / "data" / "practice_docs").iterdir())
KEY = {k["file"]: k for k in json.loads((ROOT / "data" / "practice_key.json").read_text())}
OUT = ROOT / "output" / "cache_test.json"
SETUPS = [("no_cache", False), ("cache", True)]
FIELDS = ("vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision")


def call_records(setup: str, doc: str, result) -> list[dict]:
    rows = []
    responses = [m for m in result.all_messages() if isinstance(m, ModelResponse)]
    for i, resp in enumerate(responses, 1):
        u = resp.usage
        usage = {f.name: getattr(u, f.name) for f in dataclasses.fields(u)
                 if f.name not in ("details", "cost")}
        diag = (resp.provider_details or {}).get("prompt_cache_diagnostics")
        rows.append({
            "setup": setup,
            "document": doc,
            "call": i,
            "model": resp.model_name,
            "time": resp.timestamp.isoformat(timespec="seconds"),
            "usage": usage,
            "usage_details": dict(u.details),
            "prompt_cache_diagnostics": diag,
            "cost_usd": agent.cost_usd(u),
        })
    return rows


def main() -> None:
    calls, answers = [], []
    for setup, cache in SETUPS:
        for path in DOCS:
            doc = f"data/practice_docs/{path.name}"
            answer, result = agent.run(doc, cache=cache, defenses=frozenset())  # Problem 3 agent
            rows = call_records(setup, doc, result)
            calls.extend(rows)
            got = answer.model_dump()
            want = KEY[path.name]
            correct = all(got[f] == want[f] for f in FIELDS)
            answers.append({"setup": setup, "document": doc, "correct": correct, "answer": got})
            print(f"{setup:8} {path.name:30} calls={len(rows)} "
                  f"in={sum(r['usage']['input_tokens'] for r in rows):6} "
                  f"read={sum(r['usage']['cache_read_tokens'] for r in rows):6} "
                  f"write={sum(r['usage']['cache_write_tokens'] for r in rows):6} "
                  f"${sum(r['cost_usd']['total'] for r in rows):.6f} "
                  f"{'OK' if correct else 'MISMATCH'}")

    OUT.write_text(json.dumps({"generated": now_iso(), "model": agent.MODEL_NAME,
                               "calls": calls, "answers": answers}, indent=2) + "\n", encoding="utf-8")

    # Proof check: a no-cache call that shows any cache tokens does not count.
    leaks = [c for c in calls if c["setup"] == "no_cache"
             and (c["usage"]["cache_read_tokens"] or c["usage"]["cache_write_tokens"])]
    print(f"\nno_cache calls with cache tokens: {len(leaks)}")
    for setup, _ in SETUPS:
        rows = [c for c in calls if c["setup"] == setup]
        total = sum(c["cost_usd"]["total"] for c in rows)
        print(f"{setup}: {len(rows)} calls, ${total:.6f} total, ${total/len(DOCS):.6f}/doc")


if __name__ == "__main__":
    main()
