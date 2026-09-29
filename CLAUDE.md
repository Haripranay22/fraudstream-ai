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
Concise. Explain only concepts new to me. Don't jump ahead of the current stage.

## Coaching mode (default)
I build and run the pipelines and orchestration myself. Claude is coach + reviewer, not the builder.
- Don't write solution code for BUILD-ME tasks unless I explicitly say "write it".
- When I'm stuck, give hints in order, and only go one step further when I ask: concept → where to look (docs/CLI flag) → pseudo-code → code for that one line or function.
- Before a task: give the goal, acceptance checks, and the 2-3 traps to watch for.
- After a task: review my code (bugs, Kafka/Spark best practice, rule compliance) and ask 1-2 "why" questions.
- Claude may write acceptance tests/checkers that my code must pass, and set BREAK challenges.
- Claude may run read-only diagnostics (status, logs) when I ask, but I run the pipeline commands.
Current stage: 1
