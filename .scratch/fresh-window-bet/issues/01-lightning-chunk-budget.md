# Lightning chunk budget

Type: research
Status: resolved
Blocked by:

## Question

What is a safe **chunk size** (characters or tokens) for one Lightning model call on the gb10 llama.cpp server we already run — so chunk-then-merge is grounded in the server’s context, not a 12k habit?

Need: `n_ctx` / train context from the running server or GGUF, NVIDIA / llama.cpp primary docs on context vs quality, and a recommended default that still leaves room for the system prompt and the JSON answer.

## Answer

Default body **80,000 characters** per call (~14–16k tokens of English), plus **8,192 tokens** reserved for system + JSON/thinking. Prefer token budgets if we call `/tokenize`: `chunk_tokens=16000`, `threshold_tokens=20000`.

Live gb10 `llama-server`: `n_ctx=524288`, train `n_ctx_train=1048576`. Hard ceiling prompt+completion ≤ ~520k. NVIDIA’s llama.cpp recipe only validates **40,960** — do not fill 512K by default. The current 12k `DOC_CAP` is ~2,200 tokens (~0.4% of the live window), a habit, not a limit.

Full trail: [research-lightning-context.md](../research-lightning-context.md).
