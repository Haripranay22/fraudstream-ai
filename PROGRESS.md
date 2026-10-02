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
| 16 | ~~Coaching mode: I build and run all pipelines/DAGs; Claude hints, reviews, writes tests~~ (replaced by #17) | The goal is to learn Kafka/Spark/Airflow/dbt by hitting and fixing real problems, not to collect generated code |
| 17 | Architect mode: I spec + make design decisions, Claude writes code, I review/run/break it | Modern workflow is spec-driven; interview value is judgment + debugging, not typing boilerplate. BREAK/QUIZ stay hands-on |
| 18 | 3 partitions per topic, partition key `card_id` (Claude-recommended, 1.05) | Fraud rules need order per card, not global order; key gives that. 3 = 3 parallel Spark tasks + a real consumer-group/rebalance demo (1.14–1.16). Throughput alone would justify 1 |
| 19 | `transactions.raw` + `fraud.labels` retention 30 days, equal (Claude-recommended, 1.05) | Source of truth until Snowflake (Stage 3); replay raw into Spark in Stage 2. Equal retention so a label never outlives its transaction (training/eval join needs both) |
| 20 | `transactions.scored` + `alerts` retention 7 days (Claude-recommended, 1.05) | Derived data: rebuild by re-running Spark over raw |
| 21 | `cleanup.policy=delete` everywhere + `retention.bytes` 1 GB per partition (Claude-recommended, 1.05) | `compact` keeps only the latest message per key: on raw (key=card_id) it would erase card history. Byte cap protects laptop disk; whichever limit hits first wins |
| 22 | Every txn carries `event_time`; generator can send some late (1.08) | Arrival time lies: late/batched records look like bursts. Velocity rules must count by event time (Spark watermarks, Stage 2) |
| 23 | Spend baseline per customer per category, mean ± std (option B, 1.08) | One average flags every legit big purchase (a $2k TV for a $40 grocery shopper). Normal depends on what is bought |
| 24 | Spend profiles are generator-only ground truth, kept off the Customer record (1.08) | The detector must learn each customer's normal from the stream; reading the profile = leakage, inflated metrics |
| 25 | Cold start: fall back to the category norm until 5 txns in that category (option a, 1.08) | Standard industry answer; skipping misses fraud, flagging all firsts floods false positives. Threshold in config.yaml |
| 26 | 1–3 cards per customer; txns get `status` approved/declined; card testing in both shapes: per-card test-then-cash-out and per-merchant many-cards (1.08) | Realistic; declines are the key card-testing signal; shape 2 forces a per-merchant aggregation in Stage 2 |

## Setup gotchas
- Docker Hub pulls failed with `EOF` when both images downloaded in parallel. Fix: `docker pull apache/kafka:4.0.0` on its own, then `make up`.
- Git Bash rewrites `/opt/...` paths in `docker exec`. Use PowerShell, or prefix `MSYS_NO_PATHCONV=1`.
- `make topics` failed with `Bash/Service/0x80072747`: on Windows, plain `bash` is the WSL launcher (System32\bash.exe), not Git Bash. Fix: Makefile calls Git Bash by full path on Windows.
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
See ROADMAP.md → 1.03b QUIZ, then 1.05 SPEC
