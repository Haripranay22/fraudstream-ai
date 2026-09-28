# Real-Time Fraud Detection Platform (portfolio)

Owner: Haripranay, a data analyst/engineer with 4 yrs of fintech fraud analytics. Learning Kafka, Spark, Airflow, dbt.
Goal: an end-to-end streaming fraud pipeline plus an LLM explainer. $0 until the final AWS stage.

## Stack
Python → Kafka (Docker, KRaft) → Spark Structured Streaming (local PySpark) → Snowflake + dbt → Airflow → LLM assistant → AWS

## Stages
1 generator + Kafka | 2 Spark scoring (rules, then XGBoost) | 3 Snowflake/dbt | 4 Airflow | 5 AI explainer | 6 AWS + README/diagram

## Rules
- Ground-truth labels go ONLY to topic `fraud.labels`, never into `transactions.raw` (no leakage).
- Topics: transactions.raw, fraud.labels, transactions.scored, alerts.
- Fraud patterns: velocity burst, impossible travel, amount spike, card testing. Each is labeled with `fraud_pattern`.
- Every rule emits a reason code.
- The LLM explainer uses only numbers returned by whitelisted SQL queries.
- No secrets in code; use .env (gitignored).
- Log every decision in PROGRESS.md (decision + why).

## Working style
Concise. Working code. Explain only concepts new to me. Don't jump ahead of the current stage.
Current stage: 1
