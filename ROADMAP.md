# Roadmap

Modes: WATCH · BUILD-ME (I code, Claude hints + reviews) · CHECK (Claude writes acceptance tests, I make them pass) · BREAK · QUIZ
Default is BUILD-ME: I build and run every pipeline and DAG. Claude writes code only when I say "write it". See CLAUDE.md → Coaching mode.
Course: "Apache Kafka for Data Engineering" (DataVidhya). Watch at 1.5x; log 3 lines per WATCH in PROGRESS.md.

## Stage 0 — Setup ✅
- [x] 0.01 Problem framing, repo structure, CLAUDE.md, PROGRESS.md
- [x] 0.02 git init, .gitignore, .env.example, README stub

## Stage 1 — Generator + Kafka
- [ ] 1.01 WATCH — Sec 1 "Real-time Analytics Stack"; Sec 2 "Apache Kafka Masterclass", "Why Do We Need Kafka?"
- [ ] 1.02 WATCH — Sec 3 Docker (first 2 lectures, skip if familiar); Sec 4 "Kafka Installation Guide Docker"
- [x] 1.03 BUILD-CLAUDE — `docker-compose.yml` (Kafka KRaft + Kafka UI), `Makefile` (up/down/logs), `requirements.txt`. Done: `make up` works, Kafka UI shows the cluster at localhost:8080 (built by Claude before coaching mode)
- [ ] 1.03b BUILD-ME — Own the infra: `make clean` → `make up` yourself; explain every line of docker-compose.yml in your own words (Claude quizzes); change the UI port to 8081 and back. Done: you can answer "why two listeners?" without notes
- [ ] 1.04 WATCH — Sec 5 "Kafka CLI Tools Basics", "Explore How Kafka Works (Internals)"
- [ ] 1.05 BUILD-ME — `scripts/create_topics.sh`: create the 4 topics (3 partitions each) via CLI; produce/consume a test message by hand. Done: topics visible in UI
- [ ] 1.06 QUIZ — topics, partitions, offsets, brokers (3 questions)
- [ ] 1.07 WATCH — Sec 5 "Python - Producer and Consumer"
- [ ] 1.08 BUILD-ME — `generator/config.yaml` + `generator/entities.py` (customers w/ home geo, cards, merchants w/ MCC + geo). Done: script prints sample entities
- [ ] 1.09 BUILD-ME + CHECK — `generator/patterns.py`: I define the 4 fraud patterns (thresholds, timing, mix) and implement the injectors; Claude writes `tests/test_patterns.py` from my spec. Done: tests pass, each pattern is generated and labeled
- [ ] 1.10 WATCH — Sec 5 "Kafka Producers In-Depth" Part 1 + Part 2
- [ ] 1.11 BUILD-ME — `generator/producer.py`: key=card_id, acks=all, idempotence, callbacks; transactions → `transactions.raw`, labels → `fraud.labels`; configurable TPS. Done: messages flowing in UI, no labels in raw
- [ ] 1.12 WATCH — Sec 6 Broker, Topics & Partitions (all 3). Log the partition-key decision in PROGRESS.md
- [ ] 1.13 WATCH — Sec 5 Consumers Part 1–3
- [ ] 1.14 BUILD-ME — `tests/consume_check.py`: consumer group, manual commit, reports counts + fraud rate per pattern by joining raw + labels on txn_id. Done: rates match config within tolerance
- [ ] 1.15 BREAK — kill broker mid-produce; crash consumer before commit; add a partition. Log observations
- [ ] 1.16 QUIZ — producer delivery guarantees, consumer commits, rebalancing, key ordering (5 questions)
- [ ] 1.17 Stage review — Claude reviews Stage 1 code; update README section; `git tag stage-1`

## Stage 1.5 — Avro + Schema Registry
- [ ] 1.5 (expand when started) — WATCH Sec 8 → add Schema Registry to compose → migrate producer/consumer JSON → Avro

## Stage 2 — Spark scoring (expand when started; all BUILD-ME)
WATCH Sec 10 "Window Function"; Stock project: Spark batch + real-time lectures → `streaming/rules.py` (BUILD-ME, reason codes) → `score_stream.py` → `transactions.scored` + `alerts` → `ml/` features, XGBoost, rules-vs-model eval → latency measurement

## Stage 3 — Snowflake + dbt (expand when started; all BUILD-ME; start Snowflake trial here)
WATCH Stock project: Snowflake incremental; Sec 9 Kafka Connect intro → decide on sink method → raw tables → dbt staging/intermediate/marts → metrics marts

## Stage 4 — Airflow (expand when started; all BUILD-ME)
WATCH Stock project: Airflow → DAGs: dbt run/test, daily eval, model retrain

## Stage 5 — AI explainer (expand when started)
Whitelisted SQL tools → prompts → app; numbers only from SQL

## Stage 6 — AWS + docs (expand when started)
Terraform infra → deploy → architecture diagram → final README with metrics
