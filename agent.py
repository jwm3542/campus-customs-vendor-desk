"""Campus Customs vendor desk agent: entry point.

    python agent.py --doc data/practice_docs/p01_bluehen_quote.html
    python agent.py --doc ... --defenses none          # Problem 3 agent, no defenses
    python agent.py --doc ... --defenses code,prompt   # any mix of code, design, prompt
    python agent.py --doc ... --fresh                  # skip Portkey's saved-answer cache

Reads one vendor document, returns a VendorDecision, and logs the run to
output/usage_log.json and output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import httpx2 as httpx  # the HTTP library the openai SDK is built on
from dotenv import load_dotenv
from openai import AsyncOpenAI

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, Tool  # noqa: E402
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

from defenses import decide, ground, read_visible  # noqa: E402
from models import ExtractedFacts, VendorDecision  # noqa: E402
from tools import (AGENT_TOOLS, AUDIT_LOG, MAX_DOC_CHARS, ROOT, TRAP_LOG,  # noqa: E402
                   TRAP_TOOLS, USAGE_LOG, append_json, ensure_log, now_iso,
                   read_vendor_doc, read_vendor_doc_visible, resolve_doc)

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")  # course-folder .env holds PORTKEY_API_KEY

# HW 6 rule: gpt-6-luna for every call, nothing else. Set once here via OPENAI_MODEL.
ALLOWED_MODEL = "gpt-6-luna"
MODEL_NAME = os.getenv("OPENAI_MODEL", ALLOWED_MODEL)
if MODEL_NAME != ALLOWED_MODEL:
    raise SystemExit(f"OPENAI_MODEL must be {ALLOWED_MODEL!r} for HW 6 (got {MODEL_NAME!r}).")

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
PROMPT_PATH = ROOT / "prompts" / "prompt.md"
HANDBOOK_PATH = ROOT / "data" / "shop_handbook.md"
PRICES_PATH = ROOT / "data" / "prices.json"
LIMITS = UsageLimits(request_limit=6, tool_calls_limit=6, total_tokens_limit=60_000)
SHORT = 300  # chars kept for each tool result in the audit trail

# Portkey also has its own response cache (separate from OpenAI's prompt cache): an exact
# repeat of a request can be answered from Portkey's store, replaying the original answer and
# token counts. We log Portkey's cache status for every model call, and --fresh forces a new call.
_GATEWAY_CACHE: list[str] = []


async def _note_gateway_cache(response: httpx.Response) -> None:
    _GATEWAY_CACHE.append(response.headers.get("x-portkey-cache-status", "n/a"))

# Problem 6 defense layers. Default is all three; empty = the Problem 3 agent.
LAYERS = ("code", "design", "prompt")
ALL = frozenset(LAYERS)
RULES_RE = re.compile(r"<!-- SECURITY RULES START.*?<!-- SECURITY RULES END -->\n*", re.S)
EXTRACT_RE = re.compile(r"\n<!-- EXTRACT PROMPT START[^\n]*-->\n(.*?)<!-- EXTRACT PROMPT END -->\n", re.S)


def prompt_sections() -> tuple[str, str]:
    """prompts/prompt.md holds both prompts: the agent prompt, then the design layer's
    facts-only extractor prompt between the EXTRACT PROMPT markers."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    m = EXTRACT_RE.search(text)
    return text[:m.start()].rstrip("\n") + "\n", m.group(1)


def security_rules() -> str:
    """The PROMPT defense layer: the rules section kept in prompts/prompt.md."""
    m = RULES_RE.search(prompt_sections()[0])
    return m.group(0).strip() if m else ""


def build_instructions(defenses=ALL) -> str:
    """Agent instructions with the full handbook appended (sent on every call)."""
    handbook = HANDBOOK_PATH.read_text(encoding="utf-8")
    if "design" in defenses:
        text = prompt_sections()[1]
        text = text.replace("{security_rules}", security_rules() if "prompt" in defenses else "")
    else:
        text = prompt_sections()[0]
        if "prompt" not in defenses:
            text = RULES_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).replace("{handbook}", handbook)


# Cache setups (Problem 4). OpenAI caches long prefixes on its own by default, so
# "off" must also switch the implicit breakpoint off, not just skip our own breakpoints.
CACHE_ON = {"cache": True, "openai_prompt_cache_options": {"mode": "implicit", "ttl": "30m"},
            "openai_cache_instructions": True}
CACHE_OFF = {"cache": False, "openai_prompt_cache_options": {"mode": "explicit"},
             "openai_cache_instructions": False}


def build_agent(cache: bool = True, defenses=ALL, fresh: bool = False) -> Agent:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise SystemExit("PORTKEY_API_KEY is not set (expected in .env).")
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL, api_key=key,
        default_headers={"x-portkey-cache-force-refresh": "true"} if fresh else None,
        http_client=httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10),
                                      event_hooks={"response": [_note_gateway_cache]}),
    )
    model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    if "design" in defenses:
        # DESIGN layer: facts only and NO tools, so a document cannot reach
        # send_email, approve_payment, or the decision.
        output_type, tools = ExtractedFacts, []
    elif "code" in defenses:
        # CODE layer on the Problem 3 agent: same tools, but the reader returns visible text only.
        output_type, tools = VendorDecision, [Tool(read_vendor_doc_visible, name="read_vendor_doc")] + TRAP_TOOLS
    else:
        output_type, tools = VendorDecision, AGENT_TOOLS
    return Agent(
        model,
        output_type=output_type,
        instructions=build_instructions(defenses),
        tools=tools,
        model_settings={"max_tokens": 4_000, **(CACHE_ON if cache else CACHE_OFF)},
    )


def cost_usd(usage) -> dict:
    """Dollar cost from prices.json. Cached input is billed at the cached rate."""
    p = json.loads(PRICES_PATH.read_text())[MODEL_NAME]
    # input_tokens already includes cache reads and cache writes, so take both out.
    cached = usage.cache_read_tokens
    uncached = usage.input_tokens - cached - usage.cache_write_tokens
    parts = {
        "uncached_input": uncached * p["input_per_1m"] / 1e6,
        "cached_input": cached * p["cached_input_per_1m"] / 1e6,
        "cache_write": usage.cache_write_tokens * p["cache_write_per_1m"] / 1e6,
        "output": usage.output_tokens * p["output_per_1m"] / 1e6,
    }
    parts["total"] = sum(parts.values())
    return {k: round(v, 8) for k, v in parts.items()}


def tool_calls(messages) -> list[dict]:
    """Pair each tool call with a short version of its result."""
    results = {
        part.tool_call_id: str(part.content)
        for m in messages for part in getattr(m, "parts", [])
        if isinstance(part, ToolReturnPart)
    }
    calls = []
    for m in messages:
        if isinstance(m, ModelResponse):
            for part in m.parts:
                if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                    res = results.get(part.tool_call_id, "")
                    calls.append({"tool": part.tool_name, "args": part.args_as_dict(),
                                  "result": res[:SHORT] + ("..." if len(res) > SHORT else "")})
    return calls


def parse_defenses(value: str) -> frozenset:
    """'all', 'none', or a comma list such as 'code,prompt'."""
    value = value.strip().lower()
    if value == "all":
        return ALL
    if value in ("none", ""):
        return frozenset()
    chosen = frozenset(v.strip() for v in value.split(","))
    bad = chosen - ALL
    if bad:
        raise SystemExit(f"unknown defense layer(s): {sorted(bad)}; choose from {LAYERS}, all, none")
    return chosen


def _design_run(doc: str, cache: bool, defenses, fresh: bool):
    """DESIGN layer pipeline: code reads the file, the model only extracts facts,
    code checks the facts against the document text and applies the handbook rules."""
    pipeline = []
    p = resolve_doc(doc)
    if isinstance(p, str):
        raise SystemExit(p)
    if "code" in defenses:
        cleaned = read_visible(p)
        text = cleaned.text[:MAX_DOC_CHARS]
        pipeline.append({"step": "read_visible (code layer)", "removed": cleaned.removed, "flags": cleaned.flags})
    else:
        text = read_vendor_doc(doc)
        pipeline.append({"step": "read_vendor_doc (no code layer)"})
    prompt = f"Vendor document file: {Path(doc).name}\n<vendor_document>\n{text}\n</vendor_document>"
    result = build_agent(cache, defenses, fresh).run_sync(prompt, usage_limits=LIMITS)
    facts = result.output.model_dump()
    grounded, notes = ground(facts, text)
    decision, reason = decide(grounded)
    pipeline += [
        {"step": "model extracted facts", "facts": facts},
        {"step": "ground facts in document text", "blanked": notes},
        {"step": "decide in code from handbook tables", "decision": decision},
    ]
    return VendorDecision(**grounded, decision=decision, reason=reason), result, pipeline


def run(doc: str, cache: bool = True, defenses=ALL, fresh: bool = False):
    """Run the agent on one document. Returns (answer, full result).

    defenses: any of {"code", "design", "prompt"}; empty = the Problem 3 agent.
    fresh: bypass Portkey's response cache so the model really answers again."""
    defenses = frozenset(defenses)
    checked = resolve_doc(doc)
    if isinstance(checked, str):          # bad path: stop before paying for a model call
        raise SystemExit(checked)
    if checked.suffix.lower() not in (".html", ".htm", ".pdf", ".eml"):
        raise SystemExit(f"ERROR: unsupported file type {checked.suffix}. Use .html, .pdf, or .eml.")
    for log in (TRAP_LOG, USAGE_LOG, AUDIT_LOG):
        ensure_log(log)
    started = now_iso()
    pipeline = []
    _GATEWAY_CACHE.clear()
    if "design" in defenses:
        answer, result, pipeline = _design_run(doc, cache, defenses, fresh)
    else:
        result = build_agent(cache, defenses, fresh).run_sync(f"Vendor document path: {doc}", usage_limits=LIMITS)
        answer = result.output
        if "code" in defenses and not isinstance(resolve_doc(doc), str):
            cleaned = read_visible(resolve_doc(doc))
            pipeline.append({"step": "read_vendor_doc returned visible text only (code layer)",
                             "removed": cleaned.removed, "flags": cleaned.flags})
    usage = result.usage
    layers = sorted(defenses) or ["none"]

    append_json(USAGE_LOG, {
        "document": doc,
        "time": started,
        "model": MODEL_NAME,
        "cache": "on" if cache else "off",
        "defenses": layers,
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.details.get("reasoning_tokens", 0),
        "total_tokens": usage.total_tokens,
        "cost_usd": cost_usd(usage),
        # Portkey response-cache status per model call: MISS / REFRESH = the model really ran;
        # HIT = Portkey replayed a stored answer (and its original token counts).
        "gateway_cache": list(_GATEWAY_CACHE),
    })
    append_json(AUDIT_LOG, {
        "document": doc,
        "time": started,
        "defenses": layers,
        "tool_calls": tool_calls(result.all_messages()),
        "pipeline": pipeline,
        "gateway_cache": list(_GATEWAY_CACHE),
        "final_answer": answer.model_dump(),
    })
    return answer, result


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", required=True, help="Path to a vendor document (.html, .pdf, .eml)")
    parser.add_argument("--no-cache", action="store_true", help="Turn off prompt caching (Problem 4)")
    parser.add_argument("--fresh", action="store_true",
                        help="Bypass Portkey's response cache (force a new model call)")
    parser.add_argument("--defenses", default="all",
                        help="all (default), none (the Problem 3 agent), or a list like code,prompt")
    args = parser.parse_args()
    answer, _ = run(args.doc, cache=not args.no_cache, defenses=parse_defenses(args.defenses), fresh=args.fresh)
    print(json.dumps(answer.model_dump(), indent=2))
    last = json.loads(USAGE_LOG.read_text())[-1]
    print(f"\nTokens: {last['input_tokens']} in ({last['cached_input_tokens']} cached), "
          f"{last['output_tokens']} out | cost ${last['cost_usd']['total']:.6f}")


if __name__ == "__main__":
    main()
