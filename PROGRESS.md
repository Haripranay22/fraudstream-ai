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
| 27 | Labels per txn + `attack_id` + `attack_seq` (option C, Claude-recommended, 1.09). Card testing shape 2: one `attack_id` for the whole merchant campaign | Mirrors industry: issuers get fraud reports per txn (Visa TC40 / Mastercard SAFE) and models train per txn, while ops work cases. Gives txn-level training + attack-level recall and time-to-detect from one topic |
| 28 | Fraud injected per attack, tuned to ~1.5% of txns; attack split velocity 30 / spike 30 / travel 20 / testing 20 (Claude-recommended, 1.09) | Real card fraud is ~0.1–0.2%: too few examples per pattern at 1k customers. Oversampled but still imbalanced; split by attacks so card testing (10–30 txns each) doesn't swamp the fraud data. State the oversampling in the README |
| 29 | Keep 1,000 customers for Stage 1; consider 10k in Stage 2 (1.09) | Customer count = number of histories, not volume (volume = run time × TPS). Small world is readable in Kafka UI and gets customers past cold start; more customers at the same TPS = sparser histories |
| 30 | Velocity burst: 5–10 txns, 15–90 s apart (event time), different merchant each, mostly online, weighted to digital_goods/electronics/department; amounts upper half of the category's normal range; normal decline rate (Claude-recommended, 1.09) | Stolen card is spent fast before a block, on resellable goods. Normal amounts + normal declines keep it separable from spike and card testing, so per-pattern recall means something |
| 31 | Generator runs a simulated clock: each customer ~2–6 txns per simulated day, simulated time runs faster than wall clock (Claude-recommended, 1.09) | With event_time = wall clock at 50 TPS / 1k customers, every customer transacts every ~20 s and looks like a velocity burst. Simulated clock gives realistic event times and fast data |
| 32 | Impossible travel: normal in-store home txn (legit), then 1–2 fraud in-store txns in a city ≥ 1,000 km away, 10–120 min later; fuel/electronics/department; normal amounts; only far txns labeled. ~2% of legit customers travel (airlines txn, then txns after distance/700 km/h + 2 h) (Claude-recommended, 1.09) | Clone used while the real card is in use at home. Online txns have no cardholder location, so in-store only. Legit travel gives the rule real negatives: speed decides fraud, not 'different city'. Rule needs far apart AND too fast (short hops give fake huge speeds) |
| 33 | `event_time` is ISO-8601 UTC everywhere (1.09) | Mixing local times breaks speed math across time zones (NY→LA gap looks 3 h shorter); flying east would flag legit travelers |
| 34 | Amount spike: 1 txn, 4–12× the customer's category mean, weighted to electronics/department/airlines, mostly online, home location, normal declines. ~1% of legit txns are splurges at 2–5× (Claude-recommended, 1.09) | One big purchase on a stolen card. Legit splurges give real negatives; the 4–5× overlap makes the single-threshold rule imperfect, so XGBoost (Stage 2) has room to improve |
| 35 | Card testing (split 50/50). Shape 1 per card: 2–6 probes $0.50–$5 at donations/digital_goods, 20–120 s apart, 30–70% declined (≥1 approved), then 1–2 cash-out txns at electronics/department (upper-normal amounts) 10–60 min later. Shape 2 per merchant: 10–30 distinct cards × 1 probe at one donations/digital_goods merchant within 5–30 min, 60–90% declined, no cash-out. All probes labeled incl. declined. Legit decline rate 3% (Claude-recommended, 1.09) | Stolen numbers are tested with tiny charges at low-friction merchants; declines are the signature. Shape 2 has 1 txn per card, so per-card rules are blind: needs a per-merchant view (regroup by merchant in Spark, since the key is card_id) |
| 36 | Late events: 2% of all txns (legit and fraud alike) sent late; 80% delayed 30 s–5 min, 20% delayed 30 min–3 h (simulated time); event_time always the true swipe time; send time kept generator-only as `scheduled_send_time` (Claude-recommended, 1.09) | Offline terminals + retries make data arrive out of order. Same rate for fraud avoids 'late = fraud' leakage. Short + long delays let Stage 2 show the watermark trade-off: completeness vs alert speed and memory |
| 37 | Lean customer behavior: preferred categories + merchants, channel tendency, shared daily curve (local time), weekend multiplier, per-customer travel tendency. Skipped: payday/holidays, per-customer decline rates (1.09) | Enough realism that normal depends on the customer, without turning 1.09 into a simulation project |
| 38 | Keep `entities.py`; add `clock.py`, `traffic.py`, `patterns.py` (1.09) | Don't refactor working, tested 1.08 code to match a tidier layout |
| 39 | `label_time = event_time + configurable delay`; `labels.delay_enabled: false` for Stage 1 (delay 1–30 days when on) (1.09) | Schema doesn't assume instant labels; real labels arrive after investigation/chargeback. Switch on later for honest model evaluation |
| 40 | Checklist additions (1.09): legit rapid purchases (mall trips, app sprees) as velocity look-alikes; velocity may reuse a merchant; card-testing cash-out only 60% of the time; spikes sometimes at the customer's usual category/merchant; merchants differ in popularity and fraud targets categories by weight (generator-only); 3-day warm-up with no attacks; anti-shortcut tests | Every pattern gets realistic negatives and variation, so no single field (declined, amount, away, late, online) identifies fraud on its own |
| 41 | Raw txn schema: txn_id, card_id, customer_id, merchant_id, mcc, amount, currency, channel, lat, lon (merchant location; null online), status, event_time. Labels: txn_id, fraud_pattern, attack_id, attack_seq, label_time (1.09) | Nothing in raw says fraud; generator internals (profiles, kind tags, send time, attack ids) never leave the generator |
| 42 | Attack start time is blended: 75% follow the legit daily curve (victim's local time), 25% a flatter curve weighted to night. Result: 15% of attacks start 00–06 local vs 4% of legit txns (1.09) | Real fraud skews to odd hours, but fully uniform timing made hour-of-day a synthetic artifact the model could exploit. Blend keeps it a weak signal (night alone F1 0.08) |
| 43 | Keep `RAW_FIELDS` / `LABEL_FIELDS` in the generator for 1.09; move the canonical schema to `streaming/schemas.py` in 1.11 (#3) | No dependency on a module that doesn't exist yet; the producer is the first consumer of the schema |
| 44 | Project review agents in `.claude/` (8 reviewers + `fraud-engineering-review` skill), committed. Pre-commit review at the end of each BUILD task; full review only at stage-end design reviews | Independent checks for leakage, realism, streaming semantics and tests catch what passing tests miss. Full review = 8 agents re-reading the repo, so keep it for milestones |

## Setup gotchas
- Docker Hub pulls failed with `EOF` when both images downloaded in parallel. Fix: `docker pull apache/kafka:4.0.0` on its own, then `make up`.
- Git Bash rewrites `/opt/...` paths in `docker exec`. Use PowerShell, or prefix `MSYS_NO_PATHCONV=1`.
- `make topics` failed with `Bash/Service/0x80072747`: on Windows, plain `bash` is the WSL launcher (System32\bash.exe), not Git Bash. Fix: Makefile calls Git Bash by full path on Windows.
- Kafka logs a few `ERROR ... DUPLICATE_BROKER_REGISTRATION / timed out` lines at startup — harmless race in combined mode; it registers seconds later.

## Kafka topics
transactions.raw · fraud.labels · transactions.scored · alerts

## Generator baselines (1.09, seed 42)
60.6k txns over 14 simulated days · fraud 1.50% · late 2.0% · 27 legit trips
Shortcut F1 (each field alone as a fraud rule): declined 0.14 · online 0.05 · late 0.02 · away_from_home 0.12 · night 0.08 · amount>300 0.07 · amount>1000 0.11 · amount>2000 0.05
Re-check after any generator change: a big jump means a look-alike broke (`tests/test_patterns.py` fails above 0.5).

## Metrics to report
Precision, recall, F1, dollar-weighted recall, FPR, p50/p95 alert latency — per fraud pattern, rules vs XGBoost

## Watch log
<!-- 3 lines per WATCH task: ### <task #> — <lecture>, then key idea / how it applies here / open question -->

## Break log
<!-- 1.15 etc.: what I broke, what happened, what I learned -->

## Next
See ROADMAP.md → 1.03b QUIZ, then 1.05 SPEC
