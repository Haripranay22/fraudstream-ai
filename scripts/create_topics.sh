#!/usr/bin/env bash
# Create the 4 pipeline topics inside the running `kafka` container.
# Safe to re-run: existing topics are skipped (their config is NOT changed).
# Usage: make topics   (or: bash scripts/create_topics.sh)
set -euo pipefail

# Git Bash on Windows rewrites /opt/... paths in docker exec; stop it.
export MSYS_NO_PATHCONV=1

BOOTSTRAP="localhost:9092"   # runs inside the kafka container, so localhost is the broker itself
DAY_MS=$((24 * 60 * 60 * 1000))
GB=$((1024 * 1024 * 1024))

# name | partitions | retention days | cleanup policy   (decisions #18-#21 in PROGRESS.md)
TOPICS=(
  "transactions.raw|3|30|delete"      # source of truth until Snowflake; replayable through Stage 2
  "fraud.labels|3|30|delete"          # same retention as raw, so every label still has its transaction
  "transactions.scored|3|7|delete"    # derived: rebuild by re-running Spark over raw
  "alerts|3|7|delete"                 # derived: rebuild by re-running Spark over raw
)

kt() { docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" "$@"; }

for spec in "${TOPICS[@]}"; do
  IFS='|' read -r name partitions days cleanup <<< "$spec"
  echo "→ $name: partitions=$partitions retention=${days}d cleanup=$cleanup"
  kt --create --if-not-exists \
     --topic "$name" \
     --partitions "$partitions" \
     --replication-factor 1 \
     --config retention.ms=$((days * DAY_MS)) \
     --config retention.bytes=$GB \
     --config cleanup.policy="$cleanup"
done

echo
echo "Topics now on the broker:"
kt --describe --exclude-internal | grep -v "^\s*Topic: .*Partition:" || true
