# Problem 4: With and without the prompt cache

We ran the vendor desk agent on all 12 practice documents twice with `gpt-6-luna` through Portkey: once with the prompt cache **off**, then once with it **on**.
`scripts/cache_test.py` ran both setups, and every model call (48 in total) is saved in `output/cache_test.json`. Each entry has the setup, the document, every token count the API reported, the prompt cache diagnostics and the dollar cost from `data/prices.json`.

## How each setup was configured (`agent.py`)

| Setup | Settings | What it means |
|---|---|---|
| **no_cache** | `cache=False`, `openai_prompt_cache_options={"mode": "explicit"}`, `openai_cache_instructions=False` | No cache breakpoints, and OpenAI's *implicit* caching is switched off too |
| **cache** | `cache=True`, `openai_prompt_cache_options={"mode": "implicit", "ttl": "30m"}`, `openai_cache_instructions=True` | A breakpoint right after the handbook instructions, kept for 30 minutes |

The no-cache setup ran first, so the cache setup started cold and had to pay for its own cache write.

## Proof that each setup did what we told it to

| Setup | Calls | Input tokens | Cache read tokens | Cache write tokens | Output tokens |
|---|---|---|---|---|---|
| no_cache | 24 | 257,963 | **0** | **0** | 1,914 |
| cache | 24 | 257,963 | **242,329** (94%) | 12,610 | 1,974 |

- **no_cache:** 0 of 24 calls reported any cache read or cache write tokens. The script checks every call and flags any no-cache call with cache tokens; it flagged none.
- **cache:** the first call (p01, call 1) wrote 10,544 tokens to the cache and read 0, which is the cold start. Each of the other 23 calls read 10,526 to 10,545 tokens from the cache. On each call, only the new tail (the vendor document and the conversation so far, 19 to 193 tokens) was written fresh.
- Both setups sent exactly the same 257,963 input tokens. Only the billing of those tokens changed.

## Cost

| Setup | Total (12 docs) | Per document | Per call |
|---|---|---|---|
| no_cache | **$0.026753** | $0.0022294 | $0.0011147 |
| cache | **$0.005289** | $0.0004407 | $0.0002204 |
| **Saved** | $0.021464 | **80.2%** | |

How the cache setup's $0.005289 breaks down:
- Cached input: $0.002423
- Cache write: $0.001576, of which $0.001318 is the single cold write
- Output: $0.000987
- Uncached input: $0.000302

After the cold start, the warm cost per document is ($0.005289 − $0.001535 for p01) / 11 = **$0.0003413**. That saves **84.7%** compared with no cache.

## Real numbers vs. the Problem 2 estimates

| | Problem 2 estimate | Real run | Why they differ |
|---|---|---|---|
| Fixed prefix tokens | 10,058 (handbook only, tiktoken) | 10,544 cached prefix; 10,671 input on call 1 | The prompt adds about 256 tokens of instructions on top of the handbook (10,314 by tiktoken). Tool definitions, the output schema and the request wrapper add about 360 more. |
| Model calls per document | 1 | **2** | Call 1 asks for `read_vendor_doc`. Call 2 reads the document and answers. The full prompt goes out both times. |
| Input tokens per document | 10,058 | **21,497** | 2 calls of about 10,700 each |
| One uncached call | $0.0010058 | $0.0011147 | About 11% more: the extra prompt and schema tokens plus output |
| One cold cache write | $0.0012572 | $0.0013180 (10,544 × $0.125/1M) | A bigger prefix than estimated |
| One warm cached call | $0.0001006 | about $0.000171 | The cache reads ($0.000105) match the estimate. Output tokens and the freshly written tail add the rest. |
| Saved by caching | 89.9% | 80.2% for this 12-doc test; 84.7% once warm | Output tokens and the new tail can't be cached, and one cold write over 12 docs is a big share |

The estimates got the token count and the price of a cache read right. They undercounted the bill because they assumed one call per document and looked only at the handbook.

## Projection: 1,000 documents a day for 30 days (30,000 documents)

Method (the same one the results page uses): warm cost per document (docs 2 to 12) × 30,000, plus one cold start a day, where a cold start is what the first document costs above a warm one.

| Setup | Math | 30-day cost |
|---|---|---|
| No cache | $0.0022286 × 30,000 + 30 × $0.0000104 | **$66.86** |
| Cache, warm documents | $0.0003413 × 30,000 | $10.24 |
| Cache, one cold start a day | 30 × $0.0011935 (mostly the cache write) | $0.04 |
| **Cache total** | | **$10.27** |
| **Savings** | | **$56.59 a month (84.6%)** |

This assumes the cache stays warm through the working day. At 1,000 documents a day, about one every 30 seconds over 8 hours, a request arrives well inside the 30-minute cache lifetime. If documents came in bursts with long gaps, each gap would cost another cold write of about $0.0013. That would still be small.

## What surprised us, and why

1. **The handbook goes out twice per document, not once.** The agent has to call a tool to read the file, so every run takes two model calls, and each call re-sends the whole prompt. This doubled the per-document bill compared with the Problem 2 estimate. Caching makes the second send cheap, but it still costs money.
2. **"Cache off" is not the default.** OpenAI caches long prompts automatically. Our Problem 3 runs already showed about 10,500 cached tokens without us asking. Leaving out our own cache settings would still have cached, and the test would not have counted. We had to set the cache mode to `explicit` with no breakpoints, which turns implicit caching off. The zero cache tokens in the no-cache rows confirm it worked.
3. **We saved 80%, not 90%.** The cache only discounts the repeated prefix. Output tokens ($0.50/1M) are the same in both setups and come to about 19% of the cached bill. In the cache setup, the small new tail of each call is billed as a cache write at $0.125/1M instead of $0.10/1M. That is because `cache=True` also caches the growing conversation, so the uncached sliver costs 25% more than it would without caching.
4. **The cold start is a big share of a small test.** One cache write ($0.00132) cost more than 3 warm documents. Over 12 documents it pulled the average down from 84.7% to 80.2% saved. Over 30,000 documents it disappears.
5. **The cache reads slightly less than it wrote.** Later documents read 10,526 tokens back from the 10,544-token cache. Cache hits are matched on the prefix in fixed-size chunks, so a few tokens near the breakpoint fall outside the reused block. It makes no practical difference.
6. **The API reports the model as `gpt-6-luna-global`.** We request `gpt-6-luna` everywhere, and that's the only model name in our code. Portkey routes our calls to an Azure OpenAI deployment of `gpt-6-luna` (its response headers name the provider `azure-openai`), and `-global` is that deployment's tag.
7. **Caching did not change the answers.** Three documents (p02, p07 and p12) fooled the agent in both setups, and a fourth, p03, fooled it in the cache run only. Each of these documents contains text that steers the agent, for example a "corrected" 7-day lead time in p07 and a "vendor of record" swap in p03. The model also isn't fully deterministic, which is why p03 flipped between runs. That's the prompt-injection problem for the later problems, not a caching effect. `trap_calls.json` stayed empty: no document got the agent to email anyone or approve a payment.
8. **Portkey has a second, separate cache.** Found later, in our final review: besides OpenAI's prompt cache (what this problem measures), the Portkey gateway keeps a **response cache** for our key. If the exact same request is sent again, Portkey can replay the stored answer, with its original token counts, instead of asking the model; its `x-portkey-cache-status` header says `HIT`. It didn't touch this test, because every one of these 48 calls was a request we had never sent before. But it explains why some later reruns (Problem 5, the Problem 6 rerun, the first Problem 7 trials) repeated earlier answers word for word. `agent.py` now logs Portkey's cache status for every call (`gateway_cache` in `usage_log.json` and `audit_trail.json`), and `--fresh` forces a real model call. For the shop, it means an exact duplicate document would cost nothing at the model, so the projection above is an upper bound.
