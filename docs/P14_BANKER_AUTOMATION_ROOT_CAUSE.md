# P14 Banker Automation Root Cause

Date: 2026-06-04

## Finding

The banker/judge mechanics were not deleted. They are present in `ops/ai_judge_daily_pool.py` and in the run prompt/data artifacts:

- per-seat prompt/context generation
- leaderboard and account summary
- virtual GP loan decision
- bet ledger schema
- source card collection
- previous report context

The automation gap came from two separate breaks:

1. `ops/run_daily_pool_pipeline.py` always synced `manual_stub` odds, then generated prompts from `data/pool/odds_snapshots/2026-06-03_T-1h.json`.
2. GitHub Actions always ran with `--skip-browser`, and `ops/ai_judge_daily_pool.py` has no configured browser collector. It only generates prompt packets and waits for raw web model output files.

Because the run-6 prompts were generated from `manual_stub`, the prompt told models:

`valid_odds_rows = 0`, do not invent odds, use empty `bet_ledger`.

The models therefore returned empty or unusable betting receipts. Later, the real provider snapshot existed with 989 valid odds rows, but the system did not automatically re-ask the web models with the corrected odds context.

## Current State

Run `run-6` now has regenerated prompts using:

`data/pool/odds_snapshots/2026-06-03_T-1h_the_odds_api.json`

The prompt manifest records `odds_provider: the_odds_api`, and the prompt odds summary shows `valid_odds_rows: 989`.

The pipeline status is intentionally blocked:

`real_odds_present_but_no_accepted_bets`

This is correct. The pipeline must not mark the run as complete until the 12 web models are recollected from the real-odds prompt packets.

## Fixes Applied

- Added provider-aware prompt odds selection in `ops/ai_judge_daily_pool.py`.
- Added Banker Judge instructions covering ranking, chips, yesterday performance, virtual loans, risk rules, and source_cards.
- Removed the confusing `Grand Judge` anti-pollution wording from the model prompt.
- Added `--odds-provider` and `--reuse-existing-odds` to `ops/run_daily_pool_pipeline.py`.
- Added `post_run_guardrails`, which blocks a run when real odds exist but accepted bets are still zero.
- Updated GitHub Actions to use `the_odds_api` and `secrets.THE_ODDS_API_KEY`.

## Required Next Step

Recollect the 12 active model outputs from:

`data/pool/prompts/run-6/*.md`

Save real raw replies into:

`data/pool/model_outputs/raw/run-6/`

Then rerun:

```bash
python3 ops/run_daily_pool_pipeline.py \
  --date 2026-06-03 \
  --round run-6 \
  --odds-provider the_odds_api \
  --reuse-existing-odds
```

Only after `accepted_bets > 0` should the run be deployed as a completed prediction pool round.
