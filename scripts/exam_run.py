"""Problem 8: run the final defended agent (all three layers) on the 10 exam documents.

    python scripts/exam_run.py

Writes output/exam_results.json straight from the agent's output, one entry per file.
Nothing in it is edited by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
from tools import TRAP_LOG, ensure_log  # noqa: E402

DOCS = sorted((ROOT / "data" / "exam_docs").iterdir())
OUT = ROOT / "output" / "exam_results.json"


def main() -> None:
    ensure_log(TRAP_LOG)
    entries = []
    for path in DOCS:
        before = len(json.loads(TRAP_LOG.read_text(encoding="utf-8")))
        answer, result = agent.run(f"data/exam_docs/{path.name}", defenses=agent.ALL)
        traps = json.loads(TRAP_LOG.read_text(encoding="utf-8"))[before:]
        a, u = answer.model_dump(), result.usage
        entries.append({
            "file": path.name,
            "vendor": a["vendor"],
            "sku": a["sku"],
            "unit_price": a["unit_price"],
            "lead_time_days": a["lead_time_days"],
            "min_order": a["min_order"],
            "decision": a["decision"],
            "reason": a["reason"],
            "trap_tool_called": bool(traps),
            "input_tokens": u.input_tokens,
            "cached_tokens": u.cache_read_tokens,
            "output_tokens": u.output_tokens,
            "cost_usd": agent.cost_usd(u)["total"],
        })
        e = entries[-1]
        print(f"{e['file']:18} {e['vendor']!s:26} {e['sku']!s:10} {e['unit_price']!s:7} "
              f"{e['lead_time_days']!s:4} {e['min_order']!s:5} {e['decision']:17} trap={e['trap_tool_called']} "
              f"${e['cost_usd']:.6f}")
    OUT.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(entries)} entries, total ${sum(e['cost_usd'] for e in entries):.6f}, "
          f"trap calls {sum(e['trap_tool_called'] for e in entries)}")


if __name__ == "__main__":
    main()
