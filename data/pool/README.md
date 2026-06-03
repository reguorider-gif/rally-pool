# AI Judge Pool Data Directory

This directory stores structured data for the AI Judge prediction pool.

## Directory Layout

| Directory | Purpose |
|---|---|
| `matches/` | Match schedule and basic info |
| `match_results/` | Final match results with source provenance |
| `odds_snapshots/` | Pre-match odds snapshots at key time points |
| `model_runs/` | Per-round per-model run status records |
| `model_outputs/` | Raw and parsed model outputs |
| `bet_receipts/` | Standardized bet receipts (schema-validated) |
| `settlements/` | Post-match settlement calculations |
| `model_health/` | Model availability, pollution rates, success rates |
| `daily_reports/` | Daily automated reports (JSON + MD) |
| `rerun_queue/` | Queues for failed model reruns |
| `pipeline_runs/` | Daily pipeline execution status records |
| `samples/` | Sample data files for schema development |

## Rules

- Historical seed data from `server.py` will be migrated here in P9.2.
- P9.1 only establishes directory structure and schema contracts; no data migration.
- When data is missing, it MUST be explicitly marked as `missing` or `manual_review`.
- Never fabricate match results, odds, or ROI figures.
