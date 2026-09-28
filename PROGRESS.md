# Progress

## Current stage: 1 — generator + Kafka
Stage 0 (setup) ✅

## Decisions
| # | Decision | Why |
|---|----------|-----|
| 1 | Kafka in KRaft mode via Docker | No Zookeeper, simpler, $0 |
| 2 | Labels on separate topic `fraud.labels` | Prevent label leakage into scoring |
| 3 | JSON messages, schema defined in `streaming/schemas.py` | Simple first; Avro/Schema Registry optional later |
| 4 | Local PySpark, not Databricks | $0, same Structured Streaming API |
| 5 | Start Snowflake trial only at Stage 3 | 30-day trial clock |
| 6 | LLM answers only from SQL tool results | No hallucinated numbers |
| 7 | Git repo on `main`; `.env` gitignored, `.env.example` committed | No secrets in history; config keys documented |
| 8 | ROADMAP.md is the task list; PROGRESS.md logs decisions + learning | One source for "what's next", one for "what happened and why" |

## Kafka topics
transactions.raw · fraud.labels · transactions.scored · alerts

## Metrics to report
Precision, recall, F1, dollar-weighted recall, FPR, p50/p95 alert latency — per fraud pattern, rules vs XGBoost

## Watch log
<!-- 3 lines per WATCH task: ### <task #> — <lecture>, then key idea / how it applies here / open question -->

## Break log
<!-- 1.15 etc.: what I broke, what happened, what I learned -->

## Next
See ROADMAP.md → 1.01 WATCH
