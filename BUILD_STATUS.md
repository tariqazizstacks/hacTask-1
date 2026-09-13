# HomeFix AI — Build Status

Last updated: after Stage 7.

## Included in this package

| Stage | File | Status |
|---|---|---|
| — | `HomeFix_AI_Roadmap.md` | complete — read this first |
| — | `COLAB_CELLS.md` | complete |
| — | `requirements.txt`, `.env.example`, `.gitignore` | complete |
| 1 | `src/config.py` | built, self-check passing |
| 1 | `src/__init__.py` | built |
| 2 | `generate_data.py` | built, validation passing |
| 2 | `data/services.csv` | 8 rows |
| 2 | `data/providers.csv` | 32 rows x 11 cols, no nulls |
| 2 | `data/requests.csv` | 15 seeded rows |
| 3 | `src/utils.py` | built, 46 tests passing |
| 3 | `src/database.py` | built, 49 tests passing |
| 3 | `test_stage3.py` | 95 passed, 0 failed |
| 4 | `src/safety.py` | built, 97 tests passing |
| 4 | `test_stage4.py` | 97 passed, 0 failed |
| 5 | `src/ai_assistant.py` | built, 146 tests passing |
| 5 | `test_stage5.py` | 146 passed, 0 failed (runs offline) |
| 6 | `src/classifier.py` | built, 118 tests passing |
| 6 | `test_stage6.py` | 118 passed, 0 failed |
| 7 | `src/provider_matching.py` | built, 101 tests passing |
| 7 | `test_stage7.py` | 101 passed, 0 failed |

## Not yet built

| Stage | File | Purpose |
|---|---|---|
| 8-10 | `app.py` | Gradio UI, 6 tabs |
| 11 | `src/rag.py` + `knowledge_base/*.txt` | policy retrieval |
| 12 | `src/analytics.py` | dashboard metrics |
| 12 | `README.md` | final submission document |

## Changes made in Stage 7

**Area is a scoring weight, not a filter.** The roadmap always specified area
as a 30-point weight, but the first implementation filtered on it. That
starved the results: only one AC technician in the demo data is based in
Islamabad, so a strict filter showed a single card where the demo script
calls for two or three. Scoring instead puts the local provider first and
offers nearby alternatives underneath.

**`find_providers()` returns a dict, not a bare DataFrame.** The roadmap
contract said DataFrame. The UI needs to know whether any providers exist in
the requested area so it can label the results honestly, and re-deriving that
in `app.py` would duplicate the logic. The DataFrame is at
`result["providers"]`.

## Changes made in Stage 6

**`data/services.csv` gained an `anchor_keywords` column.** Keyword matching
needs to know which words are device nouns and which are symptoms. "leaking"
and "water" are Plumber words, but in "my washing machine is leaking water"
the device decides the trade. Anchors score 10 per word, ordinary keywords
score 2. Anyone with an older `services.csv` must re-run `generate_data.py`.

**The Stage 5 gap is closed.** `classifier.resolve()` now reads
`needs_keyword_fallback` and fills the category from keywords, so the app is
fully usable with no API key at all — the only thing lost is the
conversational reply.

## Changes made in Stage 4

**`src/config.py`** gained `EMERGENCY_CONTACTS`. Verify those numbers before
your demo — a wrong emergency number in a safety message is worse than no
number. Rescue 1122 and Police 15 are nationally recognised; the gas and
power utility entries are deliberately left as descriptive labels for you to
fill in from your own bill.

## Changes made in Stage 3

Two amendments to earlier files. Both are already applied in this package —
if a team member has an older copy, they need to re-copy these files.

1. **`src/config.py`** gained `REQUEST_COLUMNS` and
   `PROVIDER_PUBLIC_COLUMNS`. The request schema was being defined in
   `generate_data.py` and would have been defined again in `database.py`.
   Two copies of a schema drift apart; one copy cannot.
   `generate_data.py` now reads it from config.

2. **`utils.generate_request_id()`** uses a 6-character suffix instead of 4.
   The test suite caught that 4 hex characters collide with ~85% probability
   across 500 IDs (birthday paradox on a 65,536-value space). 6 characters
   gives 16.7 million values. The 15 seeded request IDs in
   `generate_data.py` were widened to match. `save_request()` still re-draws
   on collision — entropy reduces the odds, the storage layer enforces the
   rule.

## Verified

* `python src/config.py` — paths resolve, 8 categories, 6 areas, weights sum to 100
* `python generate_data.py` — validation passes, three CSVs written
* `python -m src.utils` — helper self-check
* `python -m src.database` — health report: 32 providers, 8 services, 15 requests, ok
* `python test_stage7.py` — **101 passed, 0 failed**, including hand-checkable
  arithmetic for all four factors, a perfect provider scoring exactly 100, the
  worst possible scoring 0, category treated as a hard filter across all 8
  trades, deterministic ordering across runs, and the Hyderabad
  no-local-provider degradation case
* `python test_stage6.py` — **118 passed, 0 failed**, including all eight
  worked examples from requirement C verbatim, device-beats-symptom
  disambiguation, ambiguity detection, and a fuzz section proving the category
  is always either valid or null
* `python test_stage5.py` — **146 passed, 0 failed**, using a stub Groq client:
  malformed JSON recovery, rate-limit fallback to the second model, slot
  hardening against hallucinated categories and invented time slots,
  multi-turn merging, and zero API calls on a critical hazard
* `python test_stage4.py` — **97 passed, 0 failed**, including 22 false-positive
  cases that must NOT trigger the guard
* `python test_stage3.py` — **95 passed, 0 failed**, including:
  round-trip save and read-back, status updates, rejection of invalid phones,
  unknown providers, category/provider mismatches, past dates and invalid
  statuses, no partial writes after a failed save, and recovery from a
  deleted `requests.csv`

## Unverified — you must run this yourself

**Cell 6 in `COLAB_CELLS.md`** (the live Groq API call). `api.groq.com` was
not reachable from the environment these files were built in. Run it before
Stage 6. Every Groq code path is tested against a stub client rather than the
real endpoint, so run this before continuing:

```python
!python -m src.ai_assistant   # health check + two real extractions
```

If the health check fails, the problem is your key or the model ID in
`config.py`, not the code. Cell 7 lists the model IDs Groq currently serves.
