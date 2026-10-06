# fraudstream-ai

Real-time card fraud detection: Kafka → Spark Structured Streaming → Snowflake/dbt → Airflow, with an LLM analyst that explains alerts using only SQL-verified numbers.

Status: Stage 1 (generator + Kafka). See [ROADMAP.md](ROADMAP.md) and [PROGRESS.md](PROGRESS.md).

## Synthetic data

All data is synthetic, made by `generator/` (run `python -m generator.patterns` for a sample). Same seed + same `generator/config.yaml` = same dataset.

**Fraud prevalence is intentionally elevated.** About 1.5% of transactions are fraud, versus roughly 0.1–0.2% in real card portfolios. That gives each pattern enough examples to train and evaluate on. Results here should not be read as real-world rates, and the model will also be tested at lower prevalence.

### Fraud patterns
| Pattern | What happens |
|---|---|
| `velocity_burst` | A stolen card makes 5–10 normal-sized purchases seconds apart, mostly online |
| `impossible_travel` | A cloned card is used in a store ≥ 1,000 km from where the real card was just used |
| `amount_spike` | One purchase at 4–12× what the customer normally spends in that category |
| `card_testing` | Tiny probes with heavy declines: several on one card (sometimes followed by a cash-out), or many cards at one merchant |

Legit traffic includes look-alikes for each pattern: rapid purchase sprees, real trips, 2–5× splurges, 3% declines. 2% of all transactions arrive late, fraud and legit alike. No single field identifies fraud on its own; `tests/test_patterns.py` checks this.

### What gets published
- **`transactions.raw`**: `txn_id, card_id, customer_id, merchant_id, mcc, amount, currency, channel, lat, lon, status, event_time`. `lat`/`lon` are the merchant's location (null online). Times are ISO-8601 UTC.
- **`fraud.labels`**: `txn_id, fraud_pattern, attack_id, attack_seq, label_time`. One label per fraudulent transaction; `attack_id` groups the transactions of one attack.

**Hidden generator metadata** never leaves the generator: spend profiles, behavior profiles, merchant popularity, trips, scenario tags, scheduled send times, and fraud targeting weights.

### Known limitations
- 1,000 customers, 200 merchants, 10 US cities; USD only; no DST.
- No device, IP, account-takeover, recurring-payment, or merchant-compromise signals.
- Patterns don't overlap yet (no hybrid attacks).
- Labels are instant by default; a 1–30 day label delay exists in config but is off.
