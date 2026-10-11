"""Replay the generated dataset into Kafka on the simulated clock (1.11).

Run `python -m generator.producer` (or `--speed max` for a fast load).

Transactions -> transactions.raw (key card_id), labels -> fraud.labels (key txn_id).
Delivery is at-least-once (#46, #47): acks=all + idempotence stop retry duplicates
inside one run, but a restart resends everything with the same txn_ids.
Stage 2 dedupes on txn_id within the watermark.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Callable

from generator.clock import SimClock, parse_utc, to_iso
from generator.entities import load_config
from generator.patterns import Dataset, generate
from streaming.schemas import LABEL_FIELDS, RAW_FIELDS, TOPIC_LABELS, TOPIC_RAW

PROGRESS_EVERY_S = 10.0
FLUSH_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Message:
    send_time: datetime   # simulated moment it is due
    topic: str
    key: str
    value: dict


def build_schedule(ds: Dataset) -> list[Message]:
    """Every message the run will send, in send order. No Kafka here, so it's testable."""
    rows: list[tuple[datetime, int, int, Message]] = []
    txn_send_time: dict[str, datetime] = {}
    for i, e in enumerate(ds.events):
        value = {f: e.txn[f] for f in RAW_FIELDS}   # only raw fields can leave, whatever Event.txn holds
        txn_send_time[e.txn["txn_id"]] = e.send_time
        rows.append((e.send_time, 0, i, Message(e.send_time, TOPIC_RAW, e.txn["card_id"], value)))
    for i, label in enumerate(ds.labels):
        # A label never goes out before its own txn (#48): a late txn's label waits for it
        send_time = max(parse_utc(label["label_time"]), txn_send_time[label["txn_id"]])
        value = {f: label[f] for f in LABEL_FIELDS}
        rows.append((send_time, 1, i, Message(send_time, TOPIC_LABELS, label["txn_id"], value)))
    rows.sort(key=lambda r: r[:3])   # same moment: txn before label
    return [r[3] for r in rows]


def encode(value: dict) -> bytes:
    # allow_nan=False: NaN/inf would be invalid JSON that Spark silently nulls; fail loudly here instead
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


@dataclass
class Stats:
    queued: int = 0
    delivered: dict[str, int] = field(default_factory=dict)
    failed: int = 0

    def on_delivery(self, err, msg) -> None:
        """Called by Kafka once per message, after its retries are used up or it succeeded."""
        if err is not None:
            self.failed += 1
            print(f"FAILED {msg.topic()} key={msg.key().decode()} : {err}", file=sys.stderr)
        else:
            self.delivered[msg.topic()] = self.delivered.get(msg.topic(), 0) + 1


def replay(schedule: list[Message], producer, stats: Stats, clock: SimClock | None,
           now: Callable[[], float] = time.monotonic) -> None:
    """Send the schedule. clock=None means as fast as possible (--speed max)."""
    t0 = last_progress = now()
    for msg in schedule:
        if clock is not None:
            due = clock.wall_offset_s(msg.send_time)
            while (wait := due - (now() - t0)) > 0:
                producer.poll(min(wait, 0.1))   # wait, but keep serving delivery callbacks
        while True:
            try:
                producer.produce(msg.topic, key=msg.key.encode(), value=encode(msg.value),
                                 on_delivery=stats.on_delivery)
                break
            except BufferError:   # local queue full: let Kafka drain it, then retry; never drop
                producer.poll(0.5)
        stats.queued += 1
        producer.poll(0)
        if now() - last_progress >= PROGRESS_EVERY_S:
            last_progress = now()
            behind = "" if clock is None else f" | behind clock {max(0.0, now() - t0 - due):.1f}s"
            print(f"sim {to_iso(msg.send_time)} | queued {stats.queued:,} | delivered "
                  f"{sum(stats.delivered.values()):,} | failed {stats.failed}{behind}", flush=True)


def make_producer(bootstrap: str):
    from confluent_kafka import Producer
    return Producer({
        "bootstrap.servers": bootstrap,
        "client.id": "fraud-generator",
        "acks": "all",                 # #46: wait for all in-sync replicas
        "enable.idempotence": True,    # #46: broker drops retry duplicates, keeps per-partition order
        # delivery.timeout.ms stays at the 5 min default: Kafka retries on its own until then (#49)
    })


def check_topics(producer) -> None:
    """Fail fast with a clear message: auto-create is off (#12), and a dead broker would only time out."""
    from confluent_kafka import KafkaException
    try:
        topics = producer.list_topics(timeout=10).topics
    except KafkaException as exc:
        sys.exit(f"Cannot reach Kafka ({exc}). Is it running? Try `make up`.")
    missing = [t for t in (TOPIC_RAW, TOPIC_LABELS) if t not in topics]
    if missing:
        sys.exit(f"Missing topics {missing}. Run `make topics`.")


def exit_code(stats: Stats, undelivered: int, interrupted: bool) -> int:
    if interrupted:
        return 130
    return 1 if stats.failed or undelivered else 0


def parse_speed(text: str) -> float | None:
    """'max' -> None (no pacing), else a positive number."""
    if text == "max":
        return None
    try:
        speed = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a number or 'max', got {text!r}") from None
    if not speed > 0:   # also rejects nan
        raise argparse.ArgumentTypeError(f"must be > 0, got {text}")
    return speed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay generated transactions + labels into Kafka.")
    parser.add_argument("--speed", type=parse_speed, default=argparse.SUPPRESS,
                        help="simulated seconds per real second, or 'max' (default: config.yaml)")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv()
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    cfg = load_config()
    clock: SimClock | None = SimClock.from_config(cfg)
    if hasattr(args, "speed"):
        clock = None if args.speed is None else replace(clock, speed=args.speed)

    producer = make_producer(bootstrap)
    check_topics(producer)   # before generating, so a dead broker fails in seconds

    print("Generating dataset...", flush=True)
    schedule = build_schedule(generate(cfg))
    n_labels = sum(m.topic == TOPIC_LABELS for m in schedule)
    pace = "max speed" if clock is None else f"speed {clock.speed:g} (~{clock.wall_offset_s(clock.end) / 60:.0f} min)"
    print(f"{len(schedule) - n_labels:,} txns + {n_labels:,} labels -> {bootstrap}, {pace}", flush=True)

    stats, interrupted = Stats(), False
    try:
        replay(schedule, producer, stats, clock)
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted: stop sending, flush what is queued (Ctrl+C again to skip)...", flush=True)
    try:
        undelivered = producer.flush(FLUSH_TIMEOUT_S)
    except KeyboardInterrupt:
        interrupted, undelivered = True, len(producer)   # messages still in the local queue are lost

    print(f"Done. queued {stats.queued:,} | delivered {stats.delivered} | failed {stats.failed} "
          f"| undelivered after flush {undelivered}")
    return exit_code(stats, undelivered, interrupted)


if __name__ == "__main__":
    sys.exit(main())
