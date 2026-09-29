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
| 9 | Repo name `fraudstream-ai` (github.com/Haripranay22/fraudstream-ai) | Short, searchable, signals streaming + AI explainer |
| 10 | `apache/kafka:4.0.0` image, single node as broker + controller | Official image; Kafka 4 is KRaft-only; one node is enough locally |
| 11 | Two listeners: `kafka:29092` (containers), `localhost:9092` (host) | A broker advertises the address clients must use; containers and host reach it differently |
| 12 | Topic auto-create OFF | Topics are made on purpose (1.05); a typo in a topic name fails loudly instead of creating a new topic |
| 13 | Kafka UI = `kafbat/kafka-ui` | Maintained fork; `provectuslabs/kafka-ui` is abandoned |
| 14 | Python client = `confluent-kafka` (not `kafka-python`) | Built on librdkafka: full idempotent producer, faster, used in production. Course may show kafka-python; the API ideas are the same |
| 15 | GNU make on Windows via winget (`ezwinports.make`) | Same `make up/down/logs` works later on Linux/AWS |
| 16 | Coaching mode: I build and run all pipelines/DAGs; Claude hints, reviews, writes tests | The goal is to learn Kafka/Spark/Airflow/dbt by hitting and fixing real problems, not to collect generated code |

## Setup gotchas
- Docker Hub pulls failed with `EOF` when both images downloaded in parallel. Fix: `docker pull apache/kafka:4.0.0` on its own, then `make up`.
- Git Bash rewrites `/opt/...` paths in `docker exec`. Use PowerShell, or prefix `MSYS_NO_PATHCONV=1`.
- Kafka logs a few `ERROR ... DUPLICATE_BROKER_REGISTRATION / timed out` lines at startup — harmless race in combined mode; it registers seconds later.

## Kafka topics
transactions.raw · fraud.labels · transactions.scored · alerts

## Metrics to report
Precision, recall, F1, dollar-weighted recall, FPR, p50/p95 alert latency — per fraud pattern, rules vs XGBoost

## Watch log
<!-- 3 lines per WATCH task: ### <task #> — <lecture>, then key idea / how it applies here / open question -->

## Break log
<!-- 1.15 etc.: what I broke, what happened, what I learned -->

## Next
See ROADMAP.md → 1.01/1.02 WATCH (1.03 done), then 1.04
