# P14 Runtime Summary and Archive Restore

## What Broke

1. The AI Judge desktop client routed `worldcupPage` actions to `/worldcup-pool`,
   but the local runtime did not contain `worldcup_pool.html`, so Flask returned
   `404 Not Found`.
2. The pool-app five-page UI hid `legacy-content` and only rendered minimal
   Run-5/Run-6 blocks in the new archive view. Historical data was still present
   in `data/pool/app_static/frontend_archives.json`, but UCL final settlement,
   historical match results, and Run-5 model strategy summaries were no longer
   visible.
3. The dashboard mixed run-5 and run-6 state. It also treated provider
   `overall=ready` as unconfirmed and displayed a hard-coded odds row count.

## Current Verified State

- Active seats: 12, with Claude and Zhipu excluded from current runs.
- Provider smoke: `PASS_REAL_PROVIDER_HAS_VALID_ODDS`.
- Valid odds rows: 989.
- Run-6 raw outputs: 12/12 found.
- Run-6 model runs: 12 valid receipts, 0 rerun.
- Run-6 betting receipts: 0 accepted bets, 3 zero-stake receipts.
- Historical archive counts:
  - `round_results`: 6
  - `ucl_bets`: 13
  - `run4_model_archive`: 13
  - `run5_model_archive`: 13

## Fixes

- Added `GET /api/pool/runtime-summary` so the frontend can read the current
  automation state, provider status, model output status, betting gap, current
  ranking, and restored historical archive data from one endpoint.
- Updated the dashboard to show run-6 awareness:
  - pipeline status
  - real provider status
  - model raw output recovery
  - betting receipt gap
  - current ranking context
- Restored archive visibility in the new Run archive view:
  - UCL final settlement
  - historical result ledger
  - Run-5 model strategy summaries
- Fixed provider readiness display for `overall=ready` and replaced the old
  hard-coded `957` odds row value with live provider smoke data.
- Added local desktop runtime bridge page:
  - `/Users/audimacmini/Library/Application Support/AI Judge/runtime/product/worldcup_pool.html`
  - `/Users/audimacmini/Documents/ai-judge-skill/product/worldcup_pool.html`

## Remaining Operational Gap

Run-6 has real model outputs and real odds, but its current receipts still
contain 0 accepted bets. The next operational step is to regenerate or manually
review bet receipts using the real provider snapshot, then rerun settlement.

Recommended action:

```bash
python3 ops/ai_judge_daily_pool.py ingest --round run-6
python3 ops/ai_judge_daily_pool.py classify --round run-6
python3 ops/ai_judge_daily_pool.py validate --round run-6
python3 ops/ai_judge_daily_pool.py settle --round run-6
```

Do not fabricate ROI or GP returns before accepted bets exist.

## Verification

- `python3 -c ast parse` for `app.py` and `pool_data.py`: passed.
- HTML script syntax parse with Node: passed.
- `python3 ops/check_pool_data_health.py`: passed.
- Local desktop `http://127.0.0.1:8501/worldcup-pool`: 200 OK.
- Local FastAPI `GET /api/pool/runtime-summary`: 200 OK, returning run-6 / 12
  seats / 989 odds rows / 12 model outputs / archive counts restored.
