# Lightning chunk budget — primary-source research

Ticket: `issues/01-lightning-chunk-budget.md`
Date: 2026-08-20
Scope: one Lightning call on the running gb10 `llama-server`. No blogs.

## Answer

**Recommended default: 80,000 characters of document body per call** (about **14,000–16,000 tokens** of English CTE prose), with a reserved **8,000 tokens** for system prompt + chat template + JSON (and reasoning) completion.

If Burling can budget in tokens (it can: the server’s `POST /tokenize` is live), prefer:

- `chunk_tokens`: **16,000**
- `threshold_tokens`: **20,000**
- `reserve_tokens`: **8,192** (system + template + `n_predict`)

**Hard ceiling for one call (this box):** prompt tokens + generated tokens **≤ 520,000**. The live slot `n_ctx` is **524,288**. Do not treat 12,000 characters as a context limit.

**Do not fill the 512K window by default.** NVIDIA’s own llama.cpp recipe only publishes a validated example at **`-c 40960` (~40K)** and says raise it as VRAM allows. This server already allocated 512K; that is a *fit* number, not a *quality-validated* number for JSON tagging.

Current Burling habit vs this box:

| Budget | Where | Approx tokens (English CTE) | Fraction of live `n_ctx` 524,288 |
| --- | --- | --- | --- |
| 12,000 chars silent truncate | `DOC_CAP` in `tag_rich.py` | ~2,200 | ~0.4% |
| 12,000 / 10,000 chars | `chunking.threshold_chars` / `chunk_chars` | ~2,200 / ~1,800 | ~0.4% |
| **80,000 chars (this recommendation)** | proposed default body | **~14,300** | **~2.7%** |
| NVIDIA llama.cpp example 40,960 | model card recipe | 40,960 total window | 7.8% |
| Live server `-c` | gb10 cmdline | 524,288 | 100% |
| GGUF / NVIDIA train | `n_ctx_train` | 1,048,576 | (not allocated here) |

`tag_rich.py` still silently slices `extracted["text"][:DOC_CAP]` and appends `…[truncated for context budget]` while pass1 already splits at 12,000 / 10,000. Those two 12k numbers are the same habit, not a server constraint.

## Why this answer

### 1. The binding limit is this process’s `n_ctx`, not the 1M train length

Observed on `gb10` (`Host gb10` → `100.85.15.59`, user `lenovo`) against `http://127.0.0.1:8080`:

| Field | Value |
| --- | --- |
| Health | `{"status":"ok"}` |
| Model path (served) | `/home/lenovo/llama.cpp/models/nemotron35-lightning-30b.gguf` |
| Real file (symlink) | `/home/lenovo/llama.cpp/models/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q8_0.gguf` (33G) |
| `n_ctx` (runtime) | **524288** (512K) |
| `n_ctx_train` | **1048576** (1M) |
| `n_params` | **32913266240** (~32.9B) |
| `n_embd` | 2688 |
| `n_vocab` | 131072 |
| `ftype` | **Q8_0** |
| `size` (weights, from `/v1/models`) | 34996745984 |
| `/props` `total_slots` | **4** |
| Per-slot `n_ctx` | 524288 on every slot |
| Build | `b10380-0b1bad14f` |

Process command (abbreviated):

```
/home/lenovo/llama.cpp/build-cuda/bin/llama-server \
  -m /home/lenovo/llama.cpp/models/nemotron35-lightning-30b.gguf \
  --host 0.0.0.0 --port 8080 --gpu-layers all \
  -c 524288 --jinja --no-mmap -fa on \
  --reasoning on --reasoning-format deepseek \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -b 2048 -ub 2048
```

No `--parallel` on the command line. Official `llama-server --help` on this binary: `-np, --parallel N` default **`-1` = auto**, and `-kvu, --kv-unified` is **enabled if the number of slots is auto**. `/props` reports 4 slots. So **524,288 tokens is a shared KV pool**, not four independent 512K windows. One idle-box call can use the full 512K. Concurrent Burling calls share it.

Slot snapshots showed `n_predict` / `max_tokens` **4096**. Reasoning is on. Thinking tokens count against that generation budget and against `n_ctx`. Reserve must cover them.

GGUF key `nemotron_h_moe.context_length` is present (llama-gguf listed it; the running loader published the value as `n_ctx_train` 1048576). That matches NVIDIA’s “up to 1M tokens” train/support claim. This process did **not** load the train length; it loaded **half** (`-c 524288`).

Official llama.cpp server docs: `-c, --ctx-size N` is “size of the prompt context (default: 0, 0 = loaded from model)”. Overflow is defined: `truncated` is true when `tokens_evaluated` + tokens predicted **exceed `n_ctx`**. A safe call is therefore **prompt + completion < 524,288**, with slack for the other three slots if anything else is in flight.

### 2. 12,000 characters is ~2k tokens on this tokenizer

Live `POST /tokenize` on the same server (no specials added):

| Text | Chars | Tokens | Chars/token |
| --- | --- | --- | --- |
| `tag_rich.py` SYSTEM prompt | 1,644 | **408** | 4.0 |
| Typical user header (path + pass1 + priors) | 182 | **57** | 3.2 |
| English CTE-like prose (~12k) | 12,150 | **2,161** | **5.6** |
| Worst-case dense ASCII (`"A"*12000`) | 12,000 | **6,000** | 2.0 |

Overhead before any document body: **~500 tokens** (408 + 57 + a small chat-template tax). JSON + thinking: up to the slot’s **4,096** `n_predict`. An **8,192-token reserve** is about 20× the system prompt and covers generation.

So 12,000 characters is not “near the context wall.” It is a leftover small-model habit. Raising the body to 80,000 characters is still ~14k tokens of prose, or ~40k tokens in the 2-char/token worst case — which is the same order as NVIDIA’s published llama.cpp example window.

### 3. NVIDIA publishes 1M trained, 40K as the llama.cpp example, and a different 256K default on NIM

Three NVIDIA-owned pages, not one number:

1. **Model card** (`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`): Context Length **up to 1M tokens**. Pre-training “supports up to 1M context length.” Table row for **DGX Spark (GB10)** lists validated context **1M (default)** — that row is for the **NVFP4 / vLLM** recipes, not this Q8_0 `llama-server`. The **llama.cpp** subsection points at official GGUF `ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF` and a full recipe with **`-c 40960`**. Quote: “Validated context: the examples set `-c 40960` (~40K); raise it as VRAM allows.” Also: lower context if you want “more KV-cache headroom at high concurrency.”

2. **NVIDIA API model page** (`docs.api.nvidia.com` … `nvidia-nemotron-3-5-lightning-30b-a3b`): same **1M** input/output context; 30B total / 3B active; hybrid Mamba-2 + MoE + attention.

3. **NVIDIA NIM get-started** (different serving stack): “natively supports a context window of **262,144 tokens (256K)**” as the NIM default `--max-model-len`. Going larger “requires significantly more KV cache memory” and “extend[s] the model past its configured positional encoding range” — **NIM’s packaged default**, in tension with the HF card’s 1M. Do not treat 256K as this GGUF’s train length (`n_ctx_train` is 1M). Treat it as: **another NVIDIA surface is conservative at 256K and tells you to validate quality past that.**

The official ggml-org GGUF card exists but is a stub (“TODOs — add info”). It does **not** publish a context number. Depth reduced there.

### 4. What “safe” means here

Safe for Burling’s chunk-then-merge is the **smallest default that is grounded in this server and still leaves merge rare**, not the largest number that will physically fit.

- **Fits:** anything whose prompt + completion stays under 524,288 (shared). 80k chars does.
- **Published llama.cpp recipe:** 40,960 total. 16k-token body + 8k reserve = 24k, inside that recipe. Worst-case 80k chars (~40k tokens) + 8k reserve ≈ 48k — slightly above the example, still <10% of this process.
- **Quality at 512K on this Q8_0 + q8_0 KV stack:** no primary source measured it. NVIDIA validated 1M on GB10 for **vLLM/NVFP4**, and 40K as the **llama.cpp example**. NIM warns past 256K on **its** stack. Official llama.cpp help documents `--rope-scaling` / YaRN flags when context is changed relative to the model; this research did **not** inspect whether the running `-c 524288` vs `n_ctx_train` 1048576 is applying extra RoPE scale. Do not assume 512K is quality-equivalent to 40K.
- **Concurrency:** unified KV + 4 slots. A 400k-token body would starve other in-flight work. 16k–20k tokens will not.
- **JSON reliability:** long bodies plus `--reasoning on` plus 4096 `n_predict` can still starve the JSON if thinking is verbose. That is a generation-budget issue, not a reason to keep a 12k char truncate.

**Config translation (when the spec is written):** replace `DOC_CAP = 12_000` with the same chunker pass1 already has; set `threshold_chars: 80000`, `chunk_chars: 80000` (or token equivalents above); keep a small overlap. Files under ~80k chars become one call. Files over that chunk-then-merge. Nothing silent-truncates.

## Where it was found

- **gb10 live `llama-server`** — `GET http://127.0.0.1:8080/v1/models`, `/health`, `/props`, `/slots`, `POST /tokenize`; process cmdline; symlink + `llama-gguf … r` on `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q8_0.gguf` — runtime `n_ctx` 524288, train `n_ctx_train` 1048576, `ftype` Q8_0, 4 unified slots, measured token counts for the Burling system prompt and 12k-char samples.
- **llama.cpp official server docs + this binary’s `--help`** — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md and `/home/lenovo/llama.cpp/build-cuda/bin/llama-server --help` — `-c/--ctx-size` is the prompt-context / KV size (0 = load from model); overflow = `truncated`; `--parallel` default auto; `--kv-unified` default on when slots are auto; KV cache types include the q8_0 this host uses; RoPE/YaRN flags exist for context scaling.
- **NVIDIA model card (HF, NVIDIA org)** — https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 — trained/supported context **1M**; GB10 row 1M is the vLLM/NVFP4 recipe; llama.cpp subsection validates **`-c 40960`** and says raise as VRAM allows; KV-headroom note if concurrency is high.
- **NVIDIA API model page** — https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b — independent NVIDIA page, same 1M context and 30B/3B hybrid description.
- **NVIDIA NIM get-started (primary, different stack)** — https://docs.nvidia.com/nim/large-language-models/latest/get-started/advanced/get-started-nemotron-3.5-lightning.html — NIM default **256K**; more KV cache at longer windows; quality warning past 256K on that container. Not this GGUF’s train length.
- **ggml-org GGUF card** — https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF — official convert target named on the NVIDIA card; **no published context number** (stub / TODO). Not used for the numeric recommendation.
- **Burling code (local, for the 12k habit)** — `burling/tag_rich.py` `DOC_CAP = 12_000`; `burling/config.example.yaml` `chunking.threshold_chars: 12000` / `chunk_chars: 10000`; `burling/pass1.py` splits, `tag_rich.py` truncates.

Missing / reduced depth: no primary llama.cpp page that states “quality degrades at huge context” as a general rule (only overflow/`truncated`, KV-type flags, and RoPE-scaling flags). No published Q8_0 + 512K quality number for this exact host. ggml-org GGUF card has no `n_ctx`.
