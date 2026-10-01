# Roadmap

Modes: SPEC (I decide + write the spec) · BUILD (Claude codes from my spec, I review + run) · BREAK · QUIZ · WATCH (optional, only what a decision needs)
Default flow per component: SPEC → BUILD → run → BREAK/QUIZ. See CLAUDE.md → Architect mode.
Course: "Apache Kafka for Data Engineering" (DataVidhya). WATCH is optional: watch a lecture when a SPEC decision needs it; log 3 lines in PROGRESS.md.

## Stage 0 — Setup ✅
- [x] 0.01 Problem framing, repo structure, CLAUDE.md, PROGRESS.md
- [x] 0.02 git init, .gitignore, .env.example, README stub

## Stage 1 — Generator + Kafka
- [ ] 1.01 WATCH — Sec 1 "Real-time Analytics Stack"; Sec 2 "Apache Kafka Masterclass", "Why Do We Need Kafka?"
- [ ] 1.02 WATCH — Sec 3 Docker (first 2 lectures, skip if familiar); Sec 4 "Kafka Installation Guide Docker"
- [x] 1.03 BUILD-CLAUDE — `docker-compose.yml` (Kafka KRaft + Kafka UI), `Makefile` (up/down/logs), `requirements.txt`. Done: `make up` works, Kafka UI shows the cluster at localhost:8080 (built by Claude before coaching mode)
- [x] 1.03b QUIZ — Own the infra: `make clean` → `make up` yourself; answer 5 design questions on docker-compose.yml (listeners, KRaft roles, CLUSTER_ID + volume, auto-create off, RF=1). Done: answered without notes
- [ ] 1.04 WATCH — Sec 5 "Kafka CLI Tools Basics", "Explore How Kafka Works (Internals)"
- [x] 1.05 SPEC → BUILD — I decide partitions, retention, cleanup policy per topic; Claude writes `scripts/create_topics.sh`; I run it + produce/consume a test message by hand. Done: topics visible in UI, choices logged
- [ ] 1.06 QUIZ — topics, partitions, offsets, brokers (3 questions)
- [ ] 1.07 WATCH — Sec 5 "Python - Producer and Consumer"
- [ ] 1.08 SPEC → BUILD — I spec the entity model + config knobs; Claude writes `generator/config.yaml` + `generator/entities.py` (customers w/ home geo, cards, merchants w/ MCC + geo). Done: script prints sample entities
- [ ] 1.09 SPEC → BUILD — `generator/patterns.py`: I define the 4 fraud patterns (thresholds, timing, mix); Claude implements the injectors + `tests/test_patterns.py` from my spec. Done: tests pass, each pattern is generated and labeled
- [ ] 1.10 WATCH — Sec 5 "Kafka Producers In-Depth" Part 1 + Part 2
- [ ] 1.11 SPEC → BUILD — I decide key, acks, idempotence, error handling; Claude writes `generator/producer.py`: key=card_id, acks=all, idempotence, callbacks; transactions → `transactions.raw`, labels → `fraud.labels`; configurable TPS. Done: messages flowing in UI, no labels in raw
- [ ] 1.12 WATCH — Sec 6 Broker, Topics & Partitions (all 3). Log the partition-key decision in PROGRESS.md
- [ ] 1.13 WATCH — Sec 5 Consumers Part 1–3
- [ ] 1.14 SPEC → BUILD — I decide commit strategy + checks; Claude writes `tests/consume_check.py`: consumer group, manual commit, reports counts + fraud rate per pattern by joining raw + labels on txn_id. Done: rates match config within tolerance
- [ ] 1.15 BREAK — kill broker mid-produce; crash consumer before commit; add a partition. Log observations
- [ ] 1.16 QUIZ — producer delivery guarantees, consumer commits, rebalancing, key ordering (5 questions)
- [ ] 1.17 Design review — I explain the Stage 1 architecture, Claude probes; update README section; `git tag stage-1`

## Stage 1.5 — Avro + Schema Registry
- [ ] 1.5 (expand when started) — WATCH Sec 8 → add Schema Registry to compose → migrate producer/consumer JSON → Avro

## Stage 2 — Spark scoring (expand when started; SPEC → BUILD)
WATCH Sec 10 "Window Function"; Stock project: Spark batch + real-time lectures → `streaming/rules.py` (my rule spec + reason codes) → `score_stream.py` → `transactions.scored` + `alerts` → `ml/` features, XGBoost, rules-vs-model eval → latency measurement

## Stage 3 — Snowflake + dbt (expand when started; SPEC → BUILD; start Snowflake trial here)
WATCH Stock project: Snowflake incremental; Sec 9 Kafka Connect intro → decide on sink method → raw tables → dbt staging/intermediate/marts → metrics marts

## Stage 4 — Airflow (expand when started; SPEC → BUILD)
WATCH Stock project: Airflow → DAGs: dbt run/test, daily eval, model retrain

## Stage 5 — AI explainer (expand when started)
Whitelisted SQL tools → prompts → app; numbers only from SQL

## Stage 6 — AWS + docs (expand when started)
Terraform infra → deploy → architecture diagram → final README with metrics
