"""Kafka topics and message schemas for the producer and (Stage 2) Spark (#3, #50).

No imports from generator/: this module is the contract both sides depend on.

Messages are JSON. Timestamps are ISO-8601 UTC strings ("...Z", #33).
"""

TOPIC_RAW = "transactions.raw"
TOPIC_LABELS = "fraud.labels"
TOPIC_SCORED = "transactions.scored"
TOPIC_ALERTS = "alerts"

# transactions.raw, key = card_id (#18). Exactly these fields. Nothing here may say "fraud" (#41).
RAW_FIELDS = ("txn_id", "card_id", "customer_id", "merchant_id", "mcc", "amount", "currency",
              "channel", "lat", "lon", "status", "event_time")

# fraud.labels, key = txn_id. One record per fraud txn (#27).
LABEL_FIELDS = ("txn_id", "fraud_pattern", "attack_id", "attack_seq", "label_time")
PATTERNS = ("velocity_burst", "impossible_travel", "amount_spike", "card_testing")
