"""Fraud attacks injected into legit traffic, plus their labels (1.09).

Run `python -m generator.patterns` to generate a dataset and print a summary.

Labels exist only in Dataset.labels (-> topic fraud.labels). A raw txn has no
fraud fields: attack_id / attack_seq live on the generator-only Event (#27, #41).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from generator.clock import to_iso
from generator.entities import Card, Customer, Merchant, World, build_world, load_config
from generator.traffic import Event, Traffic, haversine_km, new_id, randint, schedule_sends, uniform

PATTERNS = ("velocity_burst", "impossible_travel", "amount_spike", "card_testing")
LABEL_FIELDS = ("txn_id", "fraud_pattern", "attack_id", "attack_seq", "label_time")


@dataclass(frozen=True)
class Attack:
    """Generator-only record of one attack, for debugging and tests."""
    attack_id: str
    pattern: str
    shape: str | None   # card_testing only: per_card | per_merchant


@dataclass
class Dataset:
    events: list[Event]    # sorted by send_time: the order the producer (1.11) will send them
    labels: list[dict]     # fraud.labels records
    attacks: list[Attack]
    traffic: Traffic       # generator-only internals (profiles, trips) for tests and debugging


def generate(cfg: dict, world: World | None = None) -> Dataset:
    world = world or build_world(cfg)
    rng = random.Random(f"{cfg['seed']}-1.09")
    traffic = Traffic(world, cfg, rng)
    events = traffic.generate()
    attacks = Injector(traffic, cfg, rng).run(events)
    schedule_sends(events, cfg, rng)
    events.sort(key=lambda e: (e.send_time, e.event_time, e.txn["txn_id"]))
    labels = make_labels(events, attacks, cfg, rng)
    return Dataset(events, labels, attacks, traffic)


class Injector:
    """Adds attacks one at a time until fraud reaches target_share of all txns (#28)."""

    def __init__(self, traffic: Traffic, cfg: dict, rng: random.Random):
        self.tr, self.f, self.rng = traffic, cfg["fraud"], rng
        clock = traffic.clock
        self.window = (clock.start + timedelta(days=self.f["warmup_days"]), clock.end - timedelta(hours=6))

    def run(self, events: list[Event]) -> list[Attack]:
        builders = {
            "velocity_burst": self.velocity_burst,
            "impossible_travel": self.impossible_travel,
            "amount_spike": self.amount_spike,
            "card_testing": self.card_testing,
        }
        split = self.f["split"]
        legit, fraud, attacks, failures = len(events), 0, [], 0
        while fraud < self.f["target_share"] * (legit + fraud):
            pattern = self.rng.choices(list(split), weights=list(split.values()))[0]
            attack_id = new_id(self.rng)
            new, shape = builders[pattern](attack_id)
            if not new:
                failures += 1
                if failures > 1000:
                    raise RuntimeError("cannot place attacks: check merchants/categories in config")
                continue
            events += new
            n_fraud = sum(e.attack_id is not None for e in new)
            fraud += n_fraud
            legit += len(new) - n_fraud
            attacks.append(Attack(attack_id, pattern, shape))
        return attacks

    # ---- helpers ------------------------------------------------------------

    def _start(self, cust: Customer) -> datetime:
        """Attack start in the victim's local time (#42): mostly the legit daily curve, some off-hours."""
        lo, hi = self.window
        timing = self.f["timing"]
        day0 = datetime.combine(lo.date(), time())
        while True:
            weights = (self.tr.t["hourly_weights"] if self.rng.random() < timing["daily_curve_share"]
                       else timing["off_hours_weights"])
            hour = self.rng.choices(range(24), weights=weights)[0]
            day = day0 + timedelta(days=self.rng.randint(0, (hi - lo).days + 1))
            ts = self.tr.local_to_utc(cust.home_city, day, hour * 3600 + self.rng.uniform(0, 3600))
            if lo <= ts < hi:
                return ts

    def _victim(self) -> tuple[Card, Customer, datetime]:
        """A random card, and an attack start when its owner is at home (keeps patterns apart from legit trips)."""
        while True:
            card = self.rng.choice(self.tr.world.cards)
            cust = self.tr.customers[card.customer_id]
            ts = self._start(cust)
            if self.tr.where(cust, ts) == cust.home_city:
                return card, cust, ts

    def _category(self, weights: dict[str, float]) -> str:
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def _merchant(self, cust: Customer, categories: dict[str, float], online_share: float,
                  city: str | None = None) -> Merchant | None:
        """A merchant from the attack's target categories; tries the preferred channel first."""
        for _ in range(10):
            mcc = self._category(categories)
            want = "online" if self.rng.random() < online_share else "in_store"
            for channel in (want, "in_store" if want == "online" else "online"):
                m = self.tr.pick_merchant(cust, mcc, city=city, channel=channel, use_prefs=False)
                if m:
                    return m
        return None

    def _fraud(self, event: Event, attack_id: str, seq: int) -> Event:
        event.kind, event.attack_id, event.attack_seq = "fraud", attack_id, seq
        return event

    # ---- patterns -----------------------------------------------------------

    def velocity_burst(self, attack_id: str) -> tuple[list[Event], None]:
        """5-10 high-normal txns, seconds apart, mostly online (#30)."""
        c = self.f["velocity_burst"]
        card, cust, t = self._victim()
        out, used = [], []
        for seq in range(1, randint(self.rng, c["txns"]) + 1):
            if used and self.rng.random() < c["merchant_reuse"]:
                m = self.rng.choice(used)
            else:
                m = self._merchant(cust, c["categories"], c["online_share"])
                if m is None:
                    return [], None
                used.append(m)
            amount = self.tr.category_mean(cust.customer_id, m.mcc) * uniform(self.rng, c["amount_mult"])
            out.append(self._fraud(self.tr.make_event(card, m, amount, t, "fraud"), attack_id, seq))
            t += timedelta(seconds=uniform(self.rng, c["gap_s"]))
        return out, None

    def impossible_travel(self, attack_id: str) -> tuple[list[Event], None]:
        """Legit in-store txn at home, then 1-2 in-store fraud txns >= 1,000 km away, minutes later (#32)."""
        c = self.f["impossible_travel"]
        card, cust, t = self._victim()
        far = [city for city in self.tr.in_store_cities
               if haversine_km(cust.home_lat, cust.home_lon, self.tr.cities[city]["lat"],
                               self.tr.cities[city]["lon"]) >= c["min_distance_km"]]
        home_m = next((m for m in (self.tr.pick_merchant(cust, self.tr.pick_category(cust.customer_id),
                                                         channel="in_store") for _ in range(20)) if m), None)
        if not far or home_m is None:
            return [], None
        # The real cardholder pays at home: legit, never labeled
        anchor = self.tr.make_event(card, home_m, self.tr.normal_amount(cust.customer_id, home_m.mcc),
                                    t, "travel_anchor")
        city = self.rng.choice(far)
        t += timedelta(minutes=uniform(self.rng, c["gap_min"]))
        out = [anchor]
        for seq in range(1, randint(self.rng, c["fraud_txns"]) + 1):
            m = self._merchant(cust, c["categories"], 0.0, city=city)
            if m is None or m.channel != "in_store":
                pool = [m for (cty, _), ms in self.tr.in_store.items() if cty == city for m in ms]
                m = self.tr.popular(pool)
            amount = self.tr.normal_amount(cust.customer_id, m.mcc)
            out.append(self._fraud(self.tr.make_event(card, m, amount, t, "fraud"), attack_id, seq))
            t += timedelta(minutes=uniform(self.rng, c["next_gap_min"]))
        return out, None

    def amount_spike(self, attack_id: str) -> tuple[list[Event], None]:
        """One txn at 4-12x the customer's category mean, at home (#34)."""
        c = self.f["amount_spike"]
        card, cust, t = self._victim()
        m = None
        if self.rng.random() < c["usual_category_share"]:
            # A category the customer already uses, often a familiar merchant
            m = self.tr.pick_merchant(cust, self.tr.pick_category(cust.customer_id))
        if m is None:
            m = self._merchant(cust, c["categories"], c["online_share"])
        if m is None:
            return [], None
        amount = self.tr.category_mean(cust.customer_id, m.mcc) * uniform(self.rng, c["mult"])
        return [self._fraud(self.tr.make_event(card, m, amount, t, "fraud"), attack_id, 1)], None

    def card_testing(self, attack_id: str) -> tuple[list[Event], str]:
        """Tiny probes with heavy declines; per card or per merchant (#26, #35)."""
        shapes = self.f["card_testing"]["shape_split"]
        shape = self._category(shapes)
        builder = self._testing_per_card if shape == "per_card" else self._testing_per_merchant
        return builder(attack_id), shape

    def _testing_per_card(self, attack_id: str) -> list[Event]:
        c = self.f["card_testing"]
        p = c["per_card"]
        card, cust, t = self._victim()
        m = self._merchant(cust, c["probe_categories"], 1.0)
        if m is None:
            return []
        decline_rate = uniform(self.rng, p["decline_rate"])
        n = randint(self.rng, p["probes"])
        out = []
        for i in range(n):
            # Keep probing until one works: the last probe is the approved one
            status = "approved" if i == n - 1 else ("declined" if self.rng.random() < decline_rate else "approved")
            amount = uniform(self.rng, c["probe_amount"])
            out.append(self._fraud(self.tr.make_event(card, m, amount, t, "fraud", status), attack_id, i + 1))
            t += timedelta(seconds=uniform(self.rng, p["gap_s"]))
        if self.rng.random() < p["cashout_prob"]:
            t = out[-1].event_time + timedelta(minutes=uniform(self.rng, p["cashout_delay_min"]))
            for _ in range(randint(self.rng, p["cashout_txns"])):
                cm = self._merchant(cust, p["cashout_categories"], 1.0)
                if cm is None:
                    break
                amount = self.tr.category_mean(cust.customer_id, cm.mcc) * uniform(self.rng, p["cashout_amount_mult"])
                out.append(self._fraud(self.tr.make_event(card, cm, amount, t, "fraud"), attack_id, len(out) + 1))
                t += timedelta(minutes=uniform(self.rng, p["cashout_gap_min"]))
        return out

    def _testing_per_merchant(self, attack_id: str) -> list[Event]:
        c = self.f["card_testing"]
        p = c["per_merchant"]
        pool = self.tr.online[self._category(c["probe_categories"])]
        if not pool:
            return []
        m = self.rng.choice(pool)
        cards = self.rng.sample(self.tr.world.cards, randint(self.rng, p["cards"]))
        start = self._start(self.tr.customers[self.rng.choice(self.tr.world.cards).customer_id])  # the fraudster keeps some customer's hours
        window = timedelta(minutes=uniform(self.rng, p["window_min"]))
        times = sorted(start + window * self.rng.random() for _ in cards)
        decline_rate = uniform(self.rng, p["decline_rate"])
        out = []
        for seq, (card, ts) in enumerate(zip(cards, times), 1):
            status = "declined" if self.rng.random() < decline_rate else "approved"
            amount = uniform(self.rng, c["probe_amount"])
            out.append(self._fraud(self.tr.make_event(card, m, amount, ts, "fraud", status), attack_id, seq))
        return out


def make_labels(events: list[Event], attacks: list[Attack], cfg: dict, rng: random.Random) -> list[dict]:
    """One label per fraud txn (#27). label_time = event_time + per-attack delay (#39)."""
    lc = cfg["labels"]
    pattern_of = {a.attack_id: a.pattern for a in attacks}
    delay_of: dict[str, timedelta] = {}
    labels = []
    for e in sorted((e for e in events if e.attack_id), key=lambda e: (e.event_time, e.attack_seq)):
        if e.attack_id not in delay_of:
            days = rng.uniform(lc["delay_days_min"], lc["delay_days_max"]) if lc["delay_enabled"] else 0
            delay_of[e.attack_id] = timedelta(days=days)
        labels.append({
            "txn_id": e.txn["txn_id"],
            "fraud_pattern": pattern_of[e.attack_id],
            "attack_id": e.attack_id,
            "attack_seq": e.attack_seq,
            "label_time": to_iso(e.event_time + delay_of[e.attack_id]),
        })
    return labels


def _print_summary(ds: Dataset) -> None:
    events, n = ds.events, len(ds.events)
    fraud = [e for e in events if e.attack_id]
    late = sum(e.send_time > e.event_time for e in events)
    print(f"{n:,} txns | fraud {len(fraud):,} ({len(fraud) / n:.2%}) | late {late:,} ({late / n:.2%})")
    print(f"legit kinds: {dict(Counter(e.kind for e in events if not e.attack_id))}")
    print(f"legit trips: {sum(len(t) for t in ds.traffic.trips_of.values())}\n")

    pattern_of = {a.attack_id: (a.pattern, a.shape) for a in ds.attacks}
    print("attacks by pattern:", dict(Counter(a.pattern for a in ds.attacks)))
    print("fraud txns by pattern:", dict(Counter(pattern_of[e.attack_id][0] for e in fraud)), "\n")

    by_attack = defaultdict(list)
    for e in fraud:
        by_attack[e.attack_id].append(e)
    shown = set()
    for a in ds.attacks:
        key = (a.pattern, a.shape)
        if key in shown:
            continue
        shown.add(key)
        print(f"{a.pattern}{f' ({a.shape})' if a.shape else ''}  attack {a.attack_id[:8]}")
        for e in sorted(by_attack[a.attack_id], key=lambda e: e.attack_seq):
            x = e.txn
            print(f"  #{e.attack_seq:<2} {x['event_time']}  {x['card_id']}  {x['merchant_id']} {x['mcc']} "
                  f"{x['channel']:<8} ${x['amount']:>8.2f}  {x['status']}")


if __name__ == "__main__":
    _print_summary(generate(load_config()))
