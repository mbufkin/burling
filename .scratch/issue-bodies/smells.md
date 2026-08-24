## Problem
Small correctness/quality items found in the two-axis code review of the working tree.

## Tasks
1. extract.py _safe_zip_target: set literal {".DS_Store", ".DS_Store"} repeats the same name — the second slot was probably meant for another junk file (e.g. .localized). Fix and add a fixture test.
2. extract.py extract_text: uses raise ValueError("zip unpacked; members are inventoried separately") as control flow. Return a status (enum or result object) instead so callers distinguish "error" from "handled, members queued".
3. run.py: --tags combined with --priors-only or --map silently skips the tags branch into legacy behavior. Error on contradictory flag combinations instead.
4. audit.py imports private helpers _region_index / _walk_regions from stitch_tags. Promote them to public names (region_index, walk_regions) in a shared module and update callers.
5. queue.build_queue calls ledger.existing_doc_id per file — O(n²) over the whole ledger on large intakes. Index rows by rel_path once per build.
