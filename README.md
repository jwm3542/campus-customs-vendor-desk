# HW 6: Campus Customs Vendor Desk Agent

A PydanticAI agent on `gpt-6-luna` (through Portkey) that reads one vendor quote, invoice, catalog page or email (`.html`, `.pdf` or `.eml`), pulls out the vendor, SKU, unit price, lead time and minimum order, and recommends whether to buy under the rules in `data/shop_handbook.md`. It has defenses against prompt injection hidden in vendor documents. The `send_email` and `approve_payment` tools are traps: they never send or pay anything, they only write to `output/trap_calls.json`.

Campus Customs, its vendors and its documents are made up for class.

## Quick start: how to run the agent

```bash
git clone https://github.com/jwm3542/campus-customs-vendor-desk.git
cd campus-customs-vendor-desk
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # macOS/Linux: cp .env.example .env, then put your Portkey key in .env
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

It prints the agent's answer (vendor, SKU, unit price, lead time, minimum order, decision, reason) plus the run's tokens and cost. Point `--doc` at any file in `data/practice_docs/`, `data/exam_docs/` or `data/my_attacks/`. All three defense layers are on by default; `--defenses none` runs the undefended agent. Needs Python 3.11 or newer.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Put your Portkey key in `.env` as `PORTKEY_API_KEY=...`. Leave `OPENAI_MODEL=gpt-6-luna`; the agent refuses any other model. Never commit `.env`.

## Run the agent

```bash
python agent.py --doc data/practice_docs/p01_bluehen_quote.html            # all defenses on
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses none   # undefended Problem 3 agent
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses code,prompt  # any mix of code, design, prompt
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --no-cache  # prompt cache off
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --fresh     # skip Portkey's saved-answer cache
```

Portkey keeps its own response cache: an exact repeat of a request can be answered from a stored copy, with the original token counts, instead of by the model. `--fresh` forces a real model call, and both logs record Portkey's cache status for every call (`gateway_cache`: `MISS`/`REFRESH` means the model answered, `HIT` means a replay).

The agent prints its answer and the run's token count and cost. Every script below makes real model calls, at fractions of a cent per document. Each run is added to `output/usage_log.json` (tokens and dollars) and `output/audit_trail.json` (tool calls and the answer).

## Files

- `agent.py`: the entry point. It builds the agent, applies the defense layers and writes the logs.
- `tools.py`: the document reader, the two trap tools and the log helpers.
- `models.py`: the structured output types.
- `scripts/`: one script per problem, listed in the table below.
- `defenses.py`: the code layer (keep only the visible text) and the design layer (handbook rules applied in Python, plus the grounding check).
- `prompts/prompt.md`: the agent's instructions, the security rules, and the design layer's facts-only extractor prompt. The handbook is attached at run time.
- `output/harness.md`: explains every field, tool and defense layer.
- `output/hw6_report.html`: the results page. It's a single file that opens by double-click.

## Reproduce each problem

| Problem | Command | Output |
|---|---|---|
| 2 Handbook size | `python scripts/estimate_handbook.py` | `output/handbook_estimate.md` |
| 4 Cache test | `python scripts/cache_test.py` | `output/cache_test.json`, `cache_test.md` |
| 5 Attack | `python scripts/attack_test.py` | `output/attack_results.json`, `attack_results.md` |
| 6 Defend | `python scripts/defense_test.py` | `output/defense_results.json`, `defense_results.md` |
| 7 Red team | `python scripts/make_attacks.py` then `python scripts/red_team_test.py` | `data/my_attacks/`, `output/red_team.md` |
| 8 Exam | `python scripts/exam_run.py` | `output/exam_results.json` |
| 9 Report | `python scripts/build_report.py` | `output/hw6_report.html` |
