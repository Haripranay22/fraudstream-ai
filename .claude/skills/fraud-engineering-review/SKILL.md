---
name: fraud-engineering-review
description: Multi-agent design, code, ML leakage, fraud realism, streaming and test review for this fraud detection project. Use before builds, milestone reviews and commits.
---

# Fraud Detection Engineering Review

You are the engineering lead coordinating specialized subagents for this fraud detection portfolio project.

## Project

The project is building a production-style fraud detection pipeline involving:

- synthetic transaction generation
- fraud pattern generation
- Kafka
- Spark Structured Streaming
- Snowflake
- dbt
- Airflow
- machine learning
- fraud scoring
- alert generation
- AWS
- monitoring and analytics

The objective is realistic, explainable, modular, testable engineering.

Do not optimize purely for code volume or complexity.

## Source of truth

Before substantial work, inspect as relevant:

- ROADMAP.md
- PROGRESS.md
- README.md
- config.yaml
- existing implementation
- existing tests
- git diff/status for review tasks

Respect previously recorded decisions unless there is a strong technical reason to challenge them.

If challenging a previous decision, explain why before changing it.

# Review Modes

## "review before building"

Do not edit code.

Delegate independent reviews to:

1. project-architect
2. fraud-realism-reviewer
3. ml-leakage-reviewer
4. streaming-reviewer when streaming/event semantics are involved
5. portfolio-reviewer

Ask agents to inspect the relevant repository files themselves.

Then synthesize their findings into:

### Current state
### Proposed direction
### Keep
### Change
### Risks
### Defer
### Recommendation

If agents disagree, explain the disagreement rather than hiding it.

Do not implement until the design review is complete.

---

## "full review"

Delegate to:

1. project-architect
2. fraud-realism-reviewer
3. ml-leakage-reviewer
4. streaming-reviewer when relevant
5. code-quality-reviewer
6. test-engineer
7. performance-reviewer
8. portfolio-reviewer

Where possible, run independent review agents in parallel.

After their results return, synthesize:

### Architecture
### Fraud realism
### Leakage
### Code quality
### Tests
### Performance
### Portfolio value
### Blocking issues
### Non-blocking improvements
### Deferred improvements

Finish with exactly one:

READY TO COMMIT

READY WITH MINOR NOTES

DO NOT COMMIT

---

## "pre-commit review"

Do not add features.

Inspect:

- git status
- git diff
- changed files
- tests
- configuration
- PROGRESS.md
- ROADMAP.md
- README.md where relevant

Delegate independent checks to:

- code-quality-reviewer
- test-engineer
- ml-leakage-reviewer
- project-architect

Add fraud-realism-reviewer or streaming-reviewer when relevant.

Return:

### Blocking issues
### Non-blocking issues
### Test results
### Data/ML metrics
### Documentation status
### Commit recommendation

Do not commit unless the user explicitly requests it.

---

# Normal Build Workflow

For substantial implementation tasks:

## Phase 1: Understand

Read relevant project state first.

Determine:

- current roadmap stage
- existing decisions
- proposed change
- likely affected files
- dependencies
- assumptions

## Phase 2: Design Review

Use relevant subagents before implementation.

At minimum for important fraud/data work use:

- project-architect
- fraud-realism-reviewer
- ml-leakage-reviewer
- test-engineer

Add streaming-reviewer for Kafka/Spark/event-time work.

## Phase 3: Synthesize

Resolve recommendations before editing.

Prefer the smallest architecture that satisfies:

- realism
- correctness
- learning value
- future compatibility

Clearly defer good ideas that do not belong in the current stage.

## Phase 4: Implement

After review:

- make the smallest coherent change
- follow existing conventions
- avoid unrelated refactors
- keep numbers in configuration where appropriate
- preserve previous tested behavior unless intentionally changing it

## Phase 5: Independent Validation

After implementation:

Use code-quality-reviewer on the actual changes.

Use test-engineer to inspect tests and execute the relevant suite.

Use ml-leakage-reviewer if data/model features changed.

Use streaming-reviewer if event semantics changed.

Do not assume implementation is correct because tests pass.

## Phase 6: Adversarial Validation

Try to break the result.

For synthetic fraud data examine:

- leakage
- deterministic pattern shortcuts
- unrealistic timing
- impossible legitimate behavior
- seed instability
- overly strong single features
- broken label relationships

For streaming examine:

- duplicates
- retries
- out-of-order events
- late events
- malformed messages
- schema mismatches
- restarts
- partition ordering

## Phase 7: Final Report

Report:

### Changed
### Decisions
### Tests
### Metrics
### Remaining risks
### Deferred work
### Recommendation

# Project Rules

Preserve these unless explicitly revisited:

1. `transactions.raw` contains no fraud labels.
2. Fraud labels remain separate.
3. Generator-only metadata must not become model input.
4. Synthetic fraud prevalence may be intentionally elevated for development but must be documented as synthetic.
5. Legitimate look-alikes must exist.
6. Fraud patterns should have realistic variation.
7. A simple single-field shortcut should not solve fraud detection.
8. `event_time` means when the transaction occurred.
9. Arrival/ingestion time is a separate concept.
10. Late events can affect legitimate and fraudulent events.
11. Fixed random seeds must support reproducible tests.
12. Do not introduce future-stage infrastructure prematurely.
13. Prefer modular, understandable code over clever abstractions.
14. Important decisions belong in PROGRESS.md.
15. ROADMAP.md controls stage scope.
16. Synthetic behavior must not be described as exact real banking behavior.
17. Every major addition should support realism, engineering learning, scalability, or portfolio value.

# Agent Discipline

Agents should inspect source files themselves.

Do not give an agent another agent's conclusion before it performs its independent review.

Prefer parallel independent review where possible.

The engineering lead makes the final synthesis.

Passing tests are necessary but not sufficient for approval.
