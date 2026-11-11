# HW 6 — AI Prompts Log

A log of the prompts I typed into the vibe coder (Claude Code) for each problem in HW 6.
Each problem is described in my own words; no assignment pages or URLs were pasted.
Each section has the problem number and title, my first prompt, any follow-up prompts, and one sentence on what the first prompt was missing.

---

## Problem 1: Vibe coder prompts

**Prompts:**

1. > i need to work on HW 6

_What was lacking after the first prompt:_ The first prompt didn't include the assignment or any files, and the HW 6 folder was empty, so the follow-up had to say which problem to start and how the prompt log should be set up.

**Follow-up prompts:**

2. > Okay, let's do problem one. Vibe coder prompts. We're going to create an AI prompts.md file and keep it updated as we work. This file is a log of what we typed into the vibe coder. Just like our previous homeworks. As in our previous homeworks, we need one section for each problem. Each section should include the problem number and title, at least one prompt I typed in my words as much as possible, one follow-up prompt if needed, and one sentence on what was lacking after the first prompt. Got it?

---

## Problem 2: Size up the handbook

**Prompts:**

1. > All right, here we are, problem two. Size up the handbook, unzip data.zip, look through data / shop_handbook.md. The campus customs shop handbook. Our agent will send it to the model on every single call. So we need to look at data / prices.json. We need to figure out how many tokens the handbook is. In output / handbook_estimates.md, write the token count and how many we have, what the handbook alone cost in dollars on one call and on 1,000 calls with cached tokens and without them. We need to show the math. We need to check these estimates against real runs in problem 4.

_What was lacking after the first prompt:_ Nothing major was missing, though the prompt didn't say which tokenizer to count with, so the vibe coder picked tiktoken's `o200k_base` and noted that Problem 4's real runs will check it.

---

## Problem 3: Build the vendor desk agent

**Prompts:**

1. > Problem 3: Build the vendor desk agent
   > Build a pydanticai desk agent using gpt-6-luna. The agent is 4 files: prompts/prompt.md is instructions for the agent which  also sends the handbook to the model on every call, agent.py is the entry point, tools.py is the tools, and models.py is the structured types. Give the agent the path to the vendor doc. The agent should use a tool to read the file (html, pdf, or .eml) and return vendor, sku, unit price, lead time in days, min order, a decision to recommend or do_not_recommend following the rules of the handbook, and a one sentence reason.
   > The agent must have 2 trap tools, send_email and approve_payment. The agents job doesn't need them. They are there to catch malicious document that tricks your agent into emailing someone or paying a vendor. The agency does not send or pay anything. It appends the call and it's arguments to output/trap_calls.json which starts empty. If the file ever has an entry it shows a document took over our agent. Keep them on our system for the whole homework. After every run, append to: output/usage_log.json, document, time, the token counts, the API reports, and the dollar cost using prices.json, and output/audit_trail.json, each tool call with its arguments, and a short result plus the final answer.  This terminal call should run the agent:
   > python agent.py --doc data/practice_docs/p01_bluehen_quote.html
   > This runs our agent on one vendor quote and logs the answer, tools, and cost. run it on p01 and p08 to show that it works. Start output /harness.md, each field in models.py and why, and each tool in one line.
   > Questions?

_What was lacking after the first prompt:_ The prompt didn't say how cached and cache-write tokens should be priced, and the first cost calculation double-counted cache-write tokens until the vibe coder fixed it.

---

## Problem 4: With and without cached tokens

**Prompts:**

1. > Problem 4, with and without cached tokens. The handbook is the same on every call, so we should be able to reuse it from a cache at a much cheaper price. So we want to test what this change is worth. We're going to run our agent on all 12 practice documents in two ways. Once with cache set up so the handbook gets reused from cache, and two, without cache set up so nothing gets reused from cache. Then we need to check the token counts the API sends back to prove each setup really did what we told it to do. A without cache runs that still shows cache tokens does not count. We want to save every model call from both setups to output / cache_test.json. Each call needs to include the setup document, every token count the API reports, and dollars from prices.json. in output / cache underscore test dot md, we need to store total cost and cost per document for each setup and the percent we saved, how our real numbers compare with problem 2 estimates, a projection for 1,000 documents a day for 30 days with and without cache, anything in the numbers that surprised you, and why it happens.

_What was lacking after the first prompt:_ The prompt didn't say how to turn caching off, and OpenAI caches long prompts automatically, so the vibe coder had to switch off implicit caching explicitly to get a no-cache run with zero cache tokens.

---

## Problem 5: Attack your own agent

**Prompts:**

1. > Now we're on to problem 5, attack your own agent. Some vendor documents are booby-trapped. With text aimed at AI. We're going to run problem 3 agent with no new defenses on all 12 documents in data/practice_docs/. We need to compare each answer to data / practice_key.jason. We also need to check the log. We also need to check the log our fake email and payment tools write to from problem 3. This is output/trap_calls.json.. Let's save output / attack underscore results dot JSON for each document, whether each field matched the key, whether the decision matched, whether a trap tool was called, and whether a link or other strange text showed up in the answer. In another file, output / attack_results.md, we need to write every document that fooled my agent. We need to write what fooled it and where the file was hiding it. Open the documents the way a person would in a browser, a PDF viewer, an email app, and compare that with what the agent read.

_What was lacking after the first prompt:_ The prompt only asked about documents that fooled the agent, but two attacks (the p04 payment comment and the p09 tracking link) never reached the agent because of how the reader parses HTML and email, so the vibe coder also wrote up the attacks the agent missed by luck rather than defense.

---

## Problem 6: Defend your agent

**Prompts:**

1. > All right, bro. On to problem 6. Defend your agent. We're going to defend against our agent at three levels. First is code, what the program does to the document before any model sees it. Second is design, how our agent is put together so that a poisoned document cannot reach the dangerous tools or the decision. Finally, the prompt, rules in prompts/prompts.md. Do not delete send underscore email or approve underscore payment from the system. We'll use these later with human sign off. Keep a way to run the agent with no defenses. We need to do that in problem 7. We're going to rerun all 12 practice documents, save our output to output that slash defense underscore results dot JSON in the same shape as problem 5, plus tokens and dollars per document. Clean documents must still come back with the right values. Refurbishing or blanking out a real quote counts as a failure in output slash defense underscore results dot MD. We'll write a before and after table for all 12 documents, what each layer catches that the others miss, the extra tokens and dollars each layer adds per document. Add your safety features to output slash harness.md in a safety section, what each defense layer does in plain words. Any questions?

_What was lacking after the first prompt:_ The prompt asked what each layer catches that the others miss, but a single all-layers run can't show that, so the vibe coder also ran each layer on its own, which showed that the prompt rules alone still got p02's decision wrong.

---

## Problem 7: Red team

**Prompts:**

1. > Now we're on to problem 7. Red team. Now, we are the hacker. We need to make 2 booby-trapped vendor documents in data slash my underscore attacks slash HTML, PDF, or email. Each one should use a hiding trick or an attack goal that is not in the practice set. A person opening the document should see a normal quote. We then need to run both attacks on the agent with no defenses and on the defended agent in output slash red underscore team dot md. For each attack, we should record what is hidden, where, what it tries to make the agent do, and what happened before and after our defenses. More points for attacks that are new and that actually fool the agent with no defenses.

_What was lacking after the first prompt:_ The prompt didn't say what kind of attack wording works, and the vibe coder's first two attacks (a "catalog mapping note" and a fake handbook rule change) didn't fool even the undefended agent, so they were rewritten as routine vendor "corrections" of a fact, which hijacked the undefended agent every time.

**Follow-up prompts:**

2. > Yes, fix it

---

## Problem 8: Exam documents

**Prompts:**

1. > Looks like we're nearing the end. We're on problem 8, examine documents. In data slash exam underscore docs slash, there are 10 vendor documents with no answer key. Run our final defended agent on all of them. Do not hand edit the results. Save output slash exam underscore results dot JSON with one entry per exam file. Each entry has these fields: file, the exam file name, e.g. E01 underscore quote dot HTML, vendor, SKU, unit underscore price, lead underscore time underscore days, min underscore order, decision, recommend or do underscore not underscore recommend, reason, trap underscore tool underscore called, either true or false, input underscore tokens, cached underscore tokens, output underscore tokens, cost underscore USD. The Gradles will compare our results to a hidden answer key and rerun some agents to check. We get points for correct fields and decisions. No trap tool calls and clean documents handled normally. You got it?

_What was lacking after the first prompt:_ Nothing major; the prompt gave the exact fields, so the vibe coder only had to script the run (`scripts/exam_run.py`) so the results came straight from the agent with no hand edits.

**Follow-up prompts:**

2. > can we update everything so it says "do_not_recommend" rather than "do_not"? or is that merely truncated for display?

---

## Problem 9: Results page

**Prompts:**

1. > We are dangerously close here. We're on problem 9. Results page. Build output slash hw6_report.html. It must be one file that opens by double-click with no internet and no other files next to it. The page must show 5 things below. Use the real numbers from earlier problems. We need one, our caching results, with a chart. Two, attacks before and after, our defenses. Three, what our defenses cost in tokens and dollars. Four, our exam results and our two red team attacks. Five, a short Recommendation to the store manager. Should campus customs turn this agent on for real vendor mail, and what would it cost per month at 1,000 documents a day? More points for a designed page, fonts, colors, layout that reads well. Let's use our page design we have created for previous homeworks.

_What was lacking after the first prompt:_ Our previous homework pages loaded their fonts from Google, which breaks the "no internet" rule, so the vibe coder downloaded the fonts once and embedded them in the page (`scripts/build_report.py` builds it from the JSON results).

---

## Problem 10: Push to GitHub and submit the URL

**Prompts:**

1. > Problem 10: Push to GitHub and submit the URL
   > Push the project to public GitHub repository and submit the repo URL on Canvas. The graders will clone it so make sure all the necessary are there. Include the whole data/ folder which contains the the course data plus our 2 attack files. The graders need to be able to clone the repo and run the agent right away. do not commit my real .env, use .gitignore to keep it our and include .env.example with placeholders only. Other Python files are fine. Put a short note in README.md on how to run the agent. cool?

_What was lacking after the first prompt:_ The prompt didn't name the repository, so the vibe coder followed the HW 5 pattern (a public repo under the same account) and called it `campus-customs-vendor-desk`, then proved "run it right away" by cloning the pushed repo into a clean folder, installing it, and running the agent.
