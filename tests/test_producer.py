"""1.11 producer checks. No Kafka needed: a fake producer stands in for the broker."""

import argparse
import json
from datetime import timedelta

import pytest

from generator.clock import SimClock, parse_utc, to_iso
from generator.entities import load_config
from generator.patterns import Dataset, generate
from generator.producer import Stats, build_schedule, encode, exit_code, parse_speed, replay
from generator.traffic import Event
from streaming.schemas import LABEL_FIELDS, RAW_FIELDS, TOPIC_LABELS, TOPIC_RAW


@pytest.fixture(scope="module")
def ds():
    return generate(load_config())


@pytest.fixture(scope="module")
def schedule(ds):
    return build_schedule(ds)


class FakeMsg:
    def __init__(self, topic, key):
        self._topic, self._key = topic, key

    def topic(self):
        return self._topic

    def key(self):
        return self._key


class FakeProducer:
    """Records sends. Delivers on poll/flush; keys in fail_keys get an error; can raise BufferError."""

    def __init__(self, clock=None, fail_keys=(), buffer_errors=0):
        self.clock = clock              # FakeClock: poll(timeout) advances it instead of sleeping
        self.fail_keys = set(fail_keys)
        self.buffer_errors = buffer_errors
        self.sent, self.pending = [], []

    def produce(self, topic, key, value, on_delivery):
        if self.buffer_errors:
            self.buffer_errors -= 1
            raise BufferError("queue full")
        self.sent.append((topic, key, value, self.clock.t if self.clock else None))
        self.pending.append((topic, key, on_delivery))

    def poll(self, timeout=0):
        if self.clock:
            self.clock.t += timeout
        for topic, key, cb in self.pending:
            cb("boom" if key in self.fail_keys else None, FakeMsg(topic, key))
        self.pending = []

    def flush(self, timeout=None):
        self.poll(0)
        return 0


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


# --- schedule ---------------------------------------------------------------

def test_every_txn_and_label_is_scheduled_once(ds, schedule):
    raw = [m for m in schedule if m.topic == TOPIC_RAW]
    labels = [m for m in schedule if m.topic == TOPIC_LABELS]
    assert len(raw) == len(ds.events) and len(labels) == len(ds.labels)
    assert len({m.value["txn_id"] for m in raw}) == len(raw)


def test_raw_values_have_exactly_the_raw_fields(schedule):
    # Leakage guard (#2, #41): nothing about fraud or generator internals reaches transactions.raw
    for m in schedule:
        expected = RAW_FIELDS if m.topic == TOPIC_RAW else LABEL_FIELDS
        assert tuple(m.value) == expected


def test_keys(schedule):
    for m in schedule:
        assert m.key == (m.value["card_id"] if m.topic == TOPIC_RAW else m.value["txn_id"])


def test_schedule_is_in_time_order(schedule):
    times = [m.send_time for m in schedule]
    assert times == sorted(times)


def test_no_label_before_its_txn(schedule):
    position = {}
    for i, m in enumerate(schedule):
        if m.topic == TOPIC_RAW:
            position[m.value["txn_id"]] = (i, m.send_time)
        else:
            txn_pos, txn_time = position[m.value["txn_id"]]   # KeyError = label came first
            assert i > txn_pos and m.send_time >= txn_time


def _tiny_dataset(send_delay_s, label_delay_days):
    """One fraud txn, sent send_delay_s late, labeled label_delay_days after it happened."""
    t = parse_utc("2026-09-05T12:00:00Z")
    txn = {f: None for f in RAW_FIELDS} | {"txn_id": "t1", "card_id": "c1", "event_time": to_iso(t)}
    event = Event(txn, t, "fraud", send_time=t + timedelta(seconds=send_delay_s), attack_id="a1", attack_seq=1)
    label = {"txn_id": "t1", "fraud_pattern": "amount_spike", "attack_id": "a1", "attack_seq": 1,
             "label_time": to_iso(t + timedelta(days=label_delay_days))}
    return Dataset([event], [label], [], None)


def test_late_txn_label_waits_for_the_txn():
    raw, label = build_schedule(_tiny_dataset(send_delay_s=600, label_delay_days=0))
    assert raw.topic == TOPIC_RAW and label.send_time == raw.send_time


def test_delayed_label_is_sent_at_label_time():
    raw, label = build_schedule(_tiny_dataset(send_delay_s=0, label_delay_days=10))
    assert label.send_time == raw.send_time + timedelta(days=10)


def test_extra_fields_on_a_txn_never_reach_the_wire():
    # The guard must hold even if a future generator change leaks fraud info into Event.txn
    ds = _tiny_dataset(send_delay_s=0, label_delay_days=0)
    ds.events[0].txn |= {"fraud_pattern": "amount_spike", "attack_id": "a1", "is_fraud": True, "kind": "fraud"}
    raw = next(m for m in build_schedule(ds) if m.topic == TOPIC_RAW)
    assert tuple(raw.value) == RAW_FIELDS
    wire = encode(raw.value).decode()
    assert "fraud" not in wire and "attack" not in wire


# --- encoding + CLI ---------------------------------------------------------

def test_encode_writes_null_for_missing_location():
    assert json.loads(encode({"lat": None, "lon": None})) == {"lat": None, "lon": None}
    assert b"null" in encode({"lat": None})


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_encode_rejects_values_that_are_not_valid_json(bad):
    with pytest.raises(ValueError):
        encode({"amount": bad})


def test_parse_speed():
    assert parse_speed("max") is None
    assert parse_speed("1200") == 1200.0
    for bad in ("0", "-5", "abc", "nan"):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_speed(bad)


# --- replay -----------------------------------------------------------------

def test_replay_paces_by_the_simulated_clock(schedule):
    clock = SimClock.from_config(load_config())   # speed 600
    part = schedule[:300]
    now = FakeClock()
    producer = FakeProducer(clock=now)
    replay(part, producer, Stats(), clock, now=now)
    for m, (_, _, value, sent_at) in zip(part, producer.sent):
        assert json.loads(value)["txn_id"] == m.value["txn_id"]       # order kept
        assert sent_at == pytest.approx(clock.wall_offset_s(m.send_time), abs=0.11)


def test_max_speed_sends_everything_in_order(schedule):
    producer, stats = FakeProducer(), Stats()
    replay(schedule, producer, stats, clock=None)
    producer.flush()
    assert [json.loads(v) for _, _, v, _ in producer.sent] == [m.value for m in schedule]
    assert stats.queued == len(schedule) and sum(stats.delivered.values()) == len(schedule)
    assert stats.failed == 0


def test_failed_deliveries_are_counted_and_fail_the_run(schedule):
    part = schedule[:50]
    bad = {part[3].key.encode(), part[10].key.encode()}
    producer, stats = FakeProducer(fail_keys=bad), Stats()
    replay(part, producer, stats, clock=None)
    producer.flush()
    n_bad = sum(m.key.encode() in bad for m in part)
    assert stats.failed == n_bad and sum(stats.delivered.values()) == len(part) - n_bad
    assert exit_code(stats, undelivered=0, interrupted=False) == 1


def test_full_local_queue_is_retried_not_dropped(schedule):
    part = schedule[:20]
    producer = FakeProducer(buffer_errors=5)
    replay(part, producer, Stats(), clock=None)
    assert len(producer.sent) == len(part)


def test_exit_codes():
    assert exit_code(Stats(), undelivered=0, interrupted=False) == 0
    assert exit_code(Stats(), undelivered=3, interrupted=False) == 1
    assert exit_code(Stats(), undelivered=0, interrupted=True) == 130
