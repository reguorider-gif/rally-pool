# Product Overview: AI Judge Prediction Pool

## What It Is

AI Judge Prediction Pool is an operations dashboard for running a 12-seat AI
forecasting council around football match prediction, odds readiness, model
output recovery, receipt validation, and settlement reporting.

The system is designed to answer one operational question:

> Did every active model seat provide a recoverable, auditable output, and can
> that output safely enter the prediction pool workflow?

## Who It Is For

- Operators who need to run repeatable AI forecasting rounds.
- Researchers comparing multi-model behavior under the same prompt context.
- Product teams that need provenance for model answers, not just final summaries.
- Maintainers who need a dashboard that explains blocked, partial, and complete
  states without guessing.

## Current Production URL

https://pool-app-one.vercel.app

## Current GitHub Repository

https://github.com/reguorider/rally-pool

## Key Capabilities

### 1. Multi-Model Seat Management

The current active seat contract contains 12 models:

- Gemini
- ChatGPT
- Yuanbao
- Wenxin
- DeepSeek
- MiMo
- Kimi
- Qwen
- xAI
- MiniMax
- Doubao
- Meta AI

Claude and Zhipu are intentionally removed from active run-6 operations because
they do not return usable results for this workflow.

### 2. Raw Output Recovery

Each model answer is saved as a raw text artifact before downstream processing.
This makes the pipeline auditable and prevents hidden rewriting of model output.

Run-6 currently has:

- 12/12 raw outputs recovered
- 12/12 valid receipts at the model status level
- 0 models in rerun queue
- 0 quota/auth/timeout blockers

### 3. Classification And Validation

The classifier separates operational states:

- valid receipt
- placeholder output
- context pollution
- quota block
- auth block
- timeout
- parse error
- risk refusal

The validator then attempts structured receipt extraction and checks accepted
bets against match data and odds snapshots.

### 4. Provider Readiness

The app supports real odds-provider readiness checks through `THE_ODDS_API_KEY`,
while keeping secrets out of tracked files. Provider state is reported as
configured, blocked, or warning-ready, with secrets fully redacted.

### 5. Pipeline Reporting

The daily pipeline turns one run into persisted artifacts:

- run manifest
- prompt packets
- raw output dropbox state
- model runs
- model outputs
- rerun queue
- bet receipts
- settlements
- daily report
- pipeline status report

### 6. Production Dashboard

The frontend exposes five operational views:

- dashboard overview
- model performance
- match detail
- run archives
- system health

## Run-6 Production Snapshot

| Area | Current Status |
| --- | --- |
| Active seats | 12 |
| Raw outputs | 12/12 |
| Valid model receipts | 12/12 |
| Rerun queue | 0 |
| Pipeline | pass |
| Production deploy | Vercel alias live |
| GitHub publication | repository push target |

## Product Image

The generated product image is stored at:

```text
assets/ai-judge-product-hero.png
```

It presents the core product story: a 12-seat AI council, recovered raw outputs,
real odds provider support, validated receipts, and collect-to-deploy pipeline
operations.

## Operational Principle

The project does not treat model answers as trusted just because they exist. It
stores raw output first, classifies the operational state, validates structure,
checks market coverage, and only then lets results influence reports or
settlement.
