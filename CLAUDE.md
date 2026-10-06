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

## Architect mode (default)
I own the design decisions; Claude writes the code from my spec; I prove I understand it.
- SPEC (me): before each component, I write a short spec (inputs/outputs, schema, guarantees, trade-offs). If I ask, Claude first lays out 2-3 options with trade-offs; I choose. Don't pick design-level options for me.
- BUILD (Claude): Claude writes the code from my spec, plus tests. Keep it readable, and explain only the parts that are new to me.
- REVIEW (me): I read the diff before I run it. Claude points out the 2-3 lines that matter most.
- RUN (me): I run the pipeline commands and debug. When I'm stuck, give hints first (concept → where to look → fix), not the answer straight away.
- BREAK + QUIZ: Claude sets failure challenges and "why" questions. These stay hands-on; they are the learning.
- Domain logic stays mine: fraud patterns, thresholds, reason codes. Claude implements from my definitions and flags gaps.
- Each stage ends with a design review: I explain the architecture, and Claude probes the weak spots.
## Review agents (.claude/agents, skill `fraud-engineering-review`)
- End of each SPEC → BUILD task, before commit: "pre-commit review" (code-quality, test-engineer, ml-leakage, project-architect; + fraud-realism for generator/fraud changes, + streaming for Kafka/Spark/event-time changes).
- Stage-end design review (1.17, 2.x, ...): "full review" (all 8 agents).
- Don't run them for WATCH/QUIZ/BREAK tasks or small fixes. Each agent re-reads the repo, so they're slow and costly.
- Agents report findings; I still decide. Domain/design fixes they raise go through the normal propose → confirm loop.

Current stage: 1
