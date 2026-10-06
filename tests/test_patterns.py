"""Acceptance checks for the 1.09 generator: normal traffic, fraud patterns, labels."""

import copy
from collections import Counter, defaultdict
from datetime import timedelta

import pytest

from generator.clock import parse_utc
from generator.entities import load_config
from generator.patterns import LABEL_FIELDS, PATTERNS, generate
from generator.traffic import RAW_FIELDS, haversine_km


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def ds(cfg):
    return generate(cfg)


@pytest.fixture(scope="module")
def fraud_by_attack(ds):
    groups = defaultdict(list)
    for e in ds.events:
        if e.attack_id:
            groups[e.attack_id].append(e)
    return {aid: sorted(evs, key=lambda e: e.attack_seq) for aid, evs in groups.items()}


def attacks(ds, fraud_by_attack, pattern, shape=None):
    found = [fraud_by_attack[a.attack_id] for a in ds.attacks
             if a.pattern == pattern and (shape is None or a.shape == shape)]
    assert found, f"no {pattern} {shape or ''} attacks generated"
    return found


def small_cfg(cfg, seed=None, delay_enabled=False):
    c = copy.deepcopy(cfg)
    c["counts"]["customers"] = 200
    c["clock"]["days"] = 6
    c["labels"]["delay_enabled"] = delay_enabled
    if seed is not None:
        c["seed"] = seed
    return c


def gap_s(a, b):
    return (b.event_time - a.event_time).total_seconds()


# ---- leakage + schema --------------------------------------------------------

def test_raw_txn_has_exactly_the_raw_fields(ds):
    for e in ds.events:
        assert tuple(e.txn) == RAW_FIELDS


def test_raw_txn_has_no_fraud_fields(ds):
    forbidden = {"is_fraud", "fraud_pattern", "attack_id", "attack_seq", "kind", "label_time", "send_time"}
    assert not forbidden & set(RAW_FIELDS)


def test_label_has_exactly_the_label_fields(ds):
    assert ds.labels
    for label in ds.labels:
        assert tuple(label) == LABEL_FIELDS
        assert label["fraud_pattern"] in PATTERNS


# ---- integrity ---------------------------------------------------------------

def test_txn_ids_unique(ds):
    ids = [e.txn["txn_id"] for e in ds.events]
    assert len(ids) == len(set(ids))


def test_every_label_maps_to_exactly_one_fraud_txn(ds):
    fraud_ids = {e.txn["txn_id"] for e in ds.events if e.attack_id}
    label_ids = [label["txn_id"] for label in ds.labels]
    assert len(label_ids) == len(set(label_ids))
    assert set(label_ids) == fraud_ids


def test_attack_seq_is_1_to_n(fraud_by_attack):
    for evs in fraud_by_attack.values():
        assert [e.attack_seq for e in evs] == list(range(1, len(evs) + 1))


def test_references_exist(ds):
    tr = ds.traffic
    card_owner = {c.card_id: c.customer_id for c in tr.world.cards}
    for e in ds.events:
        assert card_owner[e.txn["card_id"]] == e.txn["customer_id"]
        assert e.txn["merchant_id"] in tr.merchants
        assert e.txn["mcc"] == tr.merchants[e.txn["merchant_id"]].mcc


def test_field_values_valid(ds):
    mccs = set(ds.traffic.world.categories)
    for e in ds.events:
        x = e.txn
        assert x["amount"] > 0
        assert x["currency"] == "USD"
        assert x["mcc"] in mccs
        assert x["status"] in ("approved", "declined")
        assert x["channel"] in ("in_store", "online")
        if x["channel"] == "online":
            assert x["lat"] is None and x["lon"] is None
        else:
            assert -90 <= x["lat"] <= 90 and -180 <= x["lon"] <= 180


def test_times_are_iso_utc(ds):
    for e in ds.events:
        assert e.txn["event_time"].endswith("Z")
        assert parse_utc(e.txn["event_time"]) == e.event_time
    for label in ds.labels:
        assert label["label_time"].endswith("Z")


# ---- prevalence + timing -----------------------------------------------------

def test_fraud_share_near_target(ds, cfg):
    share = sum(1 for e in ds.events if e.attack_id) / len(ds.events)
    assert abs(share - cfg["fraud"]["target_share"]) < 0.002


def test_attack_split_near_config(ds, cfg):
    counts = Counter(a.pattern for a in ds.attacks)
    for pattern, want in cfg["fraud"]["split"].items():
        assert abs(counts[pattern] / len(ds.attacks) - want) < 0.1, pattern


def test_no_attacks_during_warmup(ds, cfg):
    warmup_end = ds.traffic.clock.start + timedelta(days=cfg["fraud"]["warmup_days"])
    assert all(e.event_time >= warmup_end for e in ds.events if e.attack_id or e.kind == "travel_anchor")


def test_labels_instant_when_delay_disabled(ds):
    event_time = {e.txn["txn_id"]: e.txn["event_time"] for e in ds.events}
    assert all(label["label_time"] == event_time[label["txn_id"]] for label in ds.labels)


def test_label_delay_when_enabled(cfg):
    small = generate(small_cfg(cfg, delay_enabled=True))
    event_time = {e.txn["txn_id"]: e.event_time for e in small.events}
    assert small.labels
    for label in small.labels:
        delay = parse_utc(label["label_time"]) - event_time[label["txn_id"]]
        assert timedelta(days=1) <= delay <= timedelta(days=30, seconds=1)


# ---- pattern structure -------------------------------------------------------

def test_velocity_burst_structure(ds, fraud_by_attack, cfg):
    c = cfg["fraud"]["velocity_burst"]
    for evs in attacks(ds, fraud_by_attack, "velocity_burst"):
        assert c["txns"]["min"] <= len(evs) <= c["txns"]["max"]
        assert len({e.txn["card_id"] for e in evs}) == 1
        for a, b in zip(evs, evs[1:]):
            assert c["gap_s"]["min"] - 0.01 <= gap_s(a, b) <= c["gap_s"]["max"] + 0.01


def test_impossible_travel_structure(ds, fraud_by_attack, cfg):
    c = cfg["fraud"]["impossible_travel"]
    tr = ds.traffic
    anchors = {(e.txn["card_id"], e.event_time): e for e in ds.events if e.kind == "travel_anchor"}
    speed_kmh = cfg["traffic"]["travel"]["flight_kmh"]
    buffer_h = cfg["traffic"]["travel"]["airport_buffer_h"]
    for evs in attacks(ds, fraud_by_attack, "impossible_travel"):
        first = evs[0]
        anchor = next(a for (card, t), a in anchors.items()
                      if card == first.txn["card_id"] and timedelta(0) < first.event_time - t <= timedelta(minutes=c["gap_min"]["max"]))
        assert anchor.attack_id is None and anchor.txn["channel"] == "in_store"
        assert c["gap_min"]["min"] * 60 - 0.01 <= gap_s(anchor, first) <= c["gap_min"]["max"] * 60 + 0.01
        for e in evs:
            assert e.txn["channel"] == "in_store"
            km = haversine_km(anchor.txn["lat"], anchor.txn["lon"], e.txn["lat"], e.txn["lon"])
            assert km >= c["min_distance_km"] - 20   # city jitter
            # Faster than the legit-travel model allows: physically implausible
            assert gap_s(anchor, e) / 3600 < km / speed_kmh + buffer_h
        assert tr.merchants[first.txn["merchant_id"]].city != tr.customers[first.txn["customer_id"]].home_city


def test_amount_spike_structure(ds, fraud_by_attack, cfg):
    c = cfg["fraud"]["amount_spike"]
    tr = ds.traffic
    for evs in attacks(ds, fraud_by_attack, "amount_spike"):
        assert len(evs) == 1
        x = evs[0].txn
        ratio = x["amount"] / tr.category_mean(x["customer_id"], x["mcc"])
        assert c["mult"]["min"] - 0.01 <= ratio <= c["mult"]["max"] + 0.01
        if x["channel"] == "in_store":   # spikes happen at home: geography must not give them away
            assert tr.merchants[x["merchant_id"]].city == tr.customers[x["customer_id"]].home_city


def test_card_testing_per_card_structure(ds, fraud_by_attack, cfg):
    c = cfg["fraud"]["card_testing"]
    p = c["per_card"]
    tiny = c["probe_amount"]["max"]
    with_cashout = 0
    for evs in attacks(ds, fraud_by_attack, "card_testing", "per_card"):
        assert len({e.txn["card_id"] for e in evs}) == 1
        probes = [e for e in evs if e.txn["amount"] <= tiny and e.txn["mcc"] in c["probe_categories"]]
        cashout = evs[len(probes):]
        assert p["probes"]["min"] <= len(probes) <= p["probes"]["max"]
        assert probes[-1].txn["status"] == "approved"
        assert len(cashout) <= p["cashout_txns"]["max"]
        if cashout:
            with_cashout += 1
            assert gap_s(probes[-1], cashout[0]) >= p["cashout_delay_min"]["min"] * 60 - 0.01
    assert with_cashout > 0


def test_card_testing_per_merchant_structure(ds, fraud_by_attack, cfg):
    c = cfg["fraud"]["card_testing"]
    p = c["per_merchant"]
    for evs in attacks(ds, fraud_by_attack, "card_testing", "per_merchant"):
        assert p["cards"]["min"] <= len(evs) <= p["cards"]["max"]
        assert len({e.txn["card_id"] for e in evs}) == len(evs)      # one probe per card
        assert len({e.txn["merchant_id"] for e in evs}) == 1
        assert gap_s(evs[0], evs[-1]) <= p["window_min"]["max"] * 60 + 0.01
        assert all(e.txn["amount"] <= c["probe_amount"]["max"] for e in evs)


def test_card_testing_declines_heavier_than_legit(ds):
    def decline_rate(evs):
        return sum(e.txn["status"] == "declined" for e in evs) / len(evs)
    testing = {a.attack_id for a in ds.attacks if a.pattern == "card_testing"}
    probes = [e for e in ds.events if e.attack_id in testing]
    legit = [e for e in ds.events if not e.attack_id]
    assert decline_rate(probes) > 5 * decline_rate(legit)


# ---- normal behavior + look-alikes ------------------------------------------

def test_legit_lookalikes_exist(ds):
    kinds = Counter(e.kind for e in ds.events if not e.attack_id)
    for kind in ("splurge", "spree", "travel", "travel_booking"):
        assert kinds[kind] > 0, kind


def test_legit_decline_rate_near_config(ds, cfg):
    legit = [e for e in ds.events if not e.attack_id]
    rate = sum(e.txn["status"] == "declined" for e in legit) / len(legit)
    assert abs(rate - cfg["traffic"]["decline_rate"]) < 0.005


def test_legit_travel_is_always_plausible(ds):
    """No legit pair of in-store txns >= 300 km apart may imply flying faster than a plane."""
    by_customer = defaultdict(list)
    for e in ds.events:
        if not e.attack_id and e.txn["channel"] == "in_store":
            by_customer[e.txn["customer_id"]].append(e)
    checked = 0
    for evs in by_customer.values():
        evs.sort(key=lambda e: e.event_time)
        for a, b in zip(evs, evs[1:]):
            km = haversine_km(a.txn["lat"], a.txn["lon"], b.txn["lat"], b.txn["lon"])
            if km >= 300:
                checked += 1
                assert km / (gap_s(a, b) / 3600) <= 900, (a.txn, b.txn)
    assert checked > 0   # legit trips actually happened


def test_customer_txn_rate_reasonable(ds, cfg):
    days = cfg["clock"]["days"]
    per_customer = Counter(e.txn["customer_id"] for e in ds.events if e.kind == "normal")
    avg = sum(per_customer.values()) / len(ds.traffic.world.customers) / days
    assert cfg["traffic"]["txns_per_day"]["min"] <= avg <= cfg["traffic"]["txns_per_day"]["max"] * 1.3


def test_preferred_merchants_used_most(ds):
    tr = ds.traffic
    hits = total = 0
    for e in ds.events:
        if e.kind != "normal":
            continue
        prefs = tr.profiles[e.txn["customer_id"]].preferred.get((e.txn["mcc"], e.txn["channel"]), ())
        hits += e.txn["merchant_id"] in prefs
        total += 1
    assert hits / total >= 0.6


def test_weekend_busier_than_weekdays(ds):
    per_day = Counter(e.event_time.date() for e in ds.events if e.kind == "normal")
    weekend = [n for d, n in per_day.items() if d.weekday() >= 5]
    weekday = [n for d, n in per_day.items() if d.weekday() < 5]
    assert sum(weekend) / len(weekend) > sum(weekday) / len(weekday)


def test_attacks_lean_to_odd_hours_but_mostly_follow_the_daily_curve(ds):
    """#42: night (00-06 local) is a weak fraud signal, not a giveaway."""
    first = {}
    for e in ds.events:
        if e.attack_id and (e.attack_id not in first or e.attack_seq < first[e.attack_id].attack_seq):
            first[e.attack_id] = e
    legit = [e for e in ds.events if not e.attack_id]

    def night_share(evs):
        return sum(_local_hour(ds, e) < 6 for e in evs) / len(evs)
    assert night_share(legit) < night_share(first.values()) < 0.4


# ---- late + out of order -----------------------------------------------------

def test_late_share_near_config(ds, cfg):
    late = sum(e.send_time > e.event_time for e in ds.events) / len(ds.events)
    assert abs(late - cfg["late"]["share"]) < 0.004


def test_late_independent_of_fraud(ds):
    def late_rate(evs):
        return sum(e.send_time > e.event_time for e in evs) / len(evs)
    fraud = [e for e in ds.events if e.attack_id]
    legit = [e for e in ds.events if not e.attack_id]
    assert abs(late_rate(fraud) - late_rate(legit)) < 0.02


def test_events_sorted_by_send_time(ds):
    sends = [e.send_time for e in ds.events]
    assert sends == sorted(sends)


def test_some_cards_arrive_out_of_order(ds):
    last_seen, out_of_order = {}, 0
    for e in ds.events:   # send order
        card = e.txn["card_id"]
        if card in last_seen and e.event_time < last_seen[card]:
            out_of_order += 1
        last_seen[card] = max(last_seen.get(card, e.event_time), e.event_time)
    assert out_of_order > 0


# ---- anti-shortcut: no single field identifies fraud -------------------------
# Baseline F1 at seed 42, after #42 (attack timing blend). If a generator change pushes one
# of these up a lot, a look-alike broke or a pattern became too easy:
#   declined 0.14 | online 0.05 | late 0.02 | away_from_home 0.12 | night 0.08
#   amount>300 0.07 | amount>1000 0.11 | amount>2000 0.05

def _local_hour(ds, e):
    tr = ds.traffic
    offset = tr.cities[tr.customers[e.txn["customer_id"]].home_city]["utc_offset"]
    return (e.event_time + timedelta(hours=offset)).hour


def _away(ds):
    tr = ds.traffic
    return lambda e: (e.txn["channel"] == "in_store"
                      and tr.merchants[e.txn["merchant_id"]].city != tr.customers[e.txn["customer_id"]].home_city)


@pytest.mark.parametrize("name", ["declined", "online", "late", "away_from_home", "night",
                                  "amount>300", "amount>1000", "amount>2000"])
def test_shortcut_rule_is_far_from_perfect(ds, name):
    rules = {
        "declined": lambda e: e.txn["status"] == "declined",
        "online": lambda e: e.txn["channel"] == "online",
        "late": lambda e: e.send_time > e.event_time,
        "away_from_home": _away(ds),
        "night": lambda e: _local_hour(ds, e) < 6,
        "amount>300": lambda e: e.txn["amount"] > 300,
        "amount>1000": lambda e: e.txn["amount"] > 1000,
        "amount>2000": lambda e: e.txn["amount"] > 2000,
    }
    rule = rules[name]
    tp = sum(1 for e in ds.events if rule(e) and e.attack_id)
    fp = sum(1 for e in ds.events if rule(e) and not e.attack_id)
    fn = sum(1 for e in ds.events if not rule(e) and e.attack_id)
    f1 = 2 * tp / (2 * tp + fp + fn)
    assert f1 < 0.5, f"{name} alone scores F1={f1:.2f}: the look-alikes are too weak"


# ---- reproducibility ---------------------------------------------------------

def test_same_seed_same_dataset(cfg):
    a, b = generate(small_cfg(cfg)), generate(small_cfg(cfg))
    assert [e.txn for e in a.events] == [e.txn for e in b.events]
    assert a.labels == b.labels


def test_different_seed_different_dataset(cfg):
    a, b = generate(small_cfg(cfg)), generate(small_cfg(cfg, seed=cfg["seed"] + 1))
    assert [e.txn for e in a.events] != [e.txn for e in b.events]
