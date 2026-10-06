"""Normal (legit) card traffic: who buys what, where and when (1.09).

Only Event.txn ever leaves the generator: it is exactly a transactions.raw record.
Everything else here is generator-only ground truth: behavior profiles, merchant
popularity, trips, the `kind` tag, send times and attack ids (#24, #41).
"""

from __future__ import annotations

import math
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from generator.clock import SimClock, to_iso, truncate_ms
from generator.entities import Card, Customer, Merchant, World

# Exactly the fields of a transactions.raw record. Nothing here may say "fraud".
RAW_FIELDS = ("txn_id", "card_id", "customer_id", "merchant_id", "mcc", "amount", "currency",
              "channel", "lat", "lon", "status", "event_time")


@dataclass(frozen=True)
class BehaviorProfile:
    """One customer's habits (#37). Generator-only, like SpendProfile."""
    txns_per_day: float
    category_weights: dict[str, float]   # mcc -> weight; only categories they can buy at home
    online_affinity: float               # chance of online when a category offers both channels
    preferred: dict[tuple[str, str], tuple[str, ...]]   # (mcc, channel) -> merchant_ids
    travel_tendency: float


@dataclass(frozen=True)
class Trip:
    """A legit trip (#32). In-store txns stop at depart and resume at arrive, so speed stays plausible."""
    customer_id: str
    city: str
    depart: datetime
    arrive: datetime          # depart + distance / flight_kmh + airport buffer
    return_depart: datetime
    return_arrive: datetime


@dataclass
class Event:
    """One transaction plus generator-only bookkeeping."""
    txn: dict                        # the raw record: exactly RAW_FIELDS
    event_time: datetime             # same moment as txn["event_time"]
    kind: str                        # normal | splurge | spree | travel | travel_booking | travel_anchor | fraud
    send_time: datetime | None = None    # scheduled_send_time (#36)
    attack_id: str | None = None
    attack_seq: int | None = None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def new_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def uniform(rng: random.Random, r: dict) -> float:
    return rng.uniform(r["min"], r["max"])


def randint(rng: random.Random, r: dict) -> int:
    return rng.randint(r["min"], r["max"])


class Traffic:
    """Builds legit events. patterns.py reuses its merchant picking and txn building."""

    def __init__(self, world: World, cfg: dict, rng: random.Random):
        self.world, self.rng, self.t = world, rng, cfg["traffic"]
        self.clock = SimClock.from_config(cfg)
        self.cities = {c["name"]: c for c in cfg["cities"]}
        self.customers = {c.customer_id: c for c in world.customers}
        self.merchants = {m.merchant_id: m for m in world.merchants}
        self.cards_of: dict[str, list[Card]] = defaultdict(list)
        for card in world.cards:
            self.cards_of[card.customer_id].append(card)

        # Merchant indexes: online by mcc, in-store by (city, mcc)
        self.online: dict[str, list[Merchant]] = defaultdict(list)
        self.in_store: dict[tuple[str, str], list[Merchant]] = defaultdict(list)
        for m in world.merchants:
            if m.channel == "online":
                self.online[m.mcc].append(m)
            else:
                self.in_store[(m.city, m.mcc)].append(m)
        self.in_store_cities = sorted({m.city for m in world.merchants if m.channel == "in_store"})
        self.popularity = {m.merchant_id: rng.lognormvariate(0, self.t["merchant_popularity_sigma"])
                           for m in world.merchants}

        self.profiles = {c.customer_id: self._build_profile(c) for c in world.customers}
        self.trips_of: dict[str, list[Trip]] = {}

    # ---- merchants --------------------------------------------------------

    def candidates(self, mcc: str, channel: str, city: str) -> list[Merchant]:
        return self.online[mcc] if channel == "online" else self.in_store[(city, mcc)]

    def channels_available(self, mcc: str, city: str) -> list[str]:
        return [ch for ch in ("in_store", "online") if self.candidates(mcc, ch, city)]

    def popular(self, pool: list[Merchant]) -> Merchant:
        return self.rng.choices(pool, weights=[self.popularity[m.merchant_id] for m in pool])[0]

    def pick_merchant(self, cust: Customer, mcc: str, city: str | None = None,
                      channel: str | None = None, use_prefs: bool = True) -> Merchant | None:
        """A merchant in `city` (default: home). None if the category has no merchant there."""
        city = city or cust.home_city
        prof = self.profiles[cust.customer_id]
        if channel is None:
            chans = self.channels_available(mcc, city)
            if not chans:
                return None
            channel = chans[0] if len(chans) == 1 else (
                "online" if self.rng.random() < prof.online_affinity else "in_store")
        pool = self.candidates(mcc, channel, city)
        if not pool:
            return None
        prefs = prof.preferred.get((mcc, channel)) if city == cust.home_city else None
        if use_prefs and prefs and self.rng.random() < self.t["preferred_share"]:
            return self.merchants[self.rng.choice(prefs)]
        return self.popular(pool)

    # ---- customers --------------------------------------------------------

    def _build_profile(self, cust: Customer) -> BehaviorProfile:
        rng, t = self.rng, self.t
        weights, preferred = {}, {}
        for cat in self.world.categories.values():
            chans = self.channels_available(cat.mcc, cust.home_city)
            if not chans:
                continue  # e.g. no fuel station in their city
            weights[cat.mcc] = cat.weight * rng.lognormvariate(0, t["category_pref_sigma"])
            for ch in chans:
                pool = self.candidates(cat.mcc, ch, cust.home_city)
                picks: set[str] = set()
                while len(picks) < min(t["preferred_merchants"], len(pool)):
                    picks.add(self.popular(pool).merchant_id)
                preferred[(cat.mcc, ch)] = tuple(sorted(picks))
        return BehaviorProfile(
            txns_per_day=uniform(rng, t["txns_per_day"]),
            category_weights=weights,
            online_affinity=rng.betavariate(t["online_affinity"]["alpha"], t["online_affinity"]["beta"]),
            preferred=preferred,
            travel_tendency=rng.lognormvariate(0, t["travel"]["tendency_sigma"]),
        )

    def pick_card(self, customer_id: str) -> Card:
        cards = self.cards_of[customer_id]
        return self.rng.choices(cards, weights=self.t["card_weights"][:len(cards)])[0]

    def pick_category(self, customer_id: str) -> str:
        w = self.profiles[customer_id].category_weights
        return self.rng.choices(list(w), weights=list(w.values()))[0]

    def category_mean(self, customer_id: str, mcc: str) -> float:
        return self.world.spend_profiles[(customer_id, mcc)].mean

    def normal_amount(self, customer_id: str, mcc: str) -> float:
        p = self.world.spend_profiles[(customer_id, mcc)]
        return max(self.rng.gauss(p.mean, p.std), 0.5)

    def where(self, cust: Customer, ts: datetime) -> str | None:
        """City the customer is in at ts, or None while flying."""
        for trip in self.trips_of.get(cust.customer_id, ()):
            if trip.depart <= ts < trip.arrive or trip.return_depart <= ts < trip.return_arrive:
                return None
            if trip.arrive <= ts < trip.return_depart:
                return trip.city
        return cust.home_city

    # ---- events -----------------------------------------------------------

    def make_event(self, card: Card, merchant: Merchant, amount: float, ts: datetime,
                   kind: str, status: str | None = None) -> Event:
        if status is None:
            status = "declined" if self.rng.random() < self.t["decline_rate"] else "approved"
        ts = truncate_ms(ts)
        txn = {
            "txn_id": new_id(self.rng),
            "card_id": card.card_id,
            "customer_id": card.customer_id,
            "merchant_id": merchant.merchant_id,
            "mcc": merchant.mcc,
            "amount": round(max(amount, 0.01), 2),
            "currency": "USD",
            "channel": merchant.channel,
            "lat": merchant.lat,      # merchant location; None online
            "lon": merchant.lon,
            "status": status,
            "event_time": to_iso(ts),
        }
        return Event(txn, ts, kind)

    def local_to_utc(self, city: str, local_midnight: datetime, seconds: float) -> datetime:
        offset = self.cities[city]["utc_offset"]
        return (local_midnight + timedelta(seconds=seconds, hours=-offset)).replace(tzinfo=timezone.utc)

    def generate(self) -> list[Event]:
        events: list[Event] = []
        for cust in self.world.customers:
            events += self._customer_events(cust)
        return [e for e in events if self.clock.start <= e.event_time < self.clock.end]

    def _customer_events(self, cust: Customer) -> list[Event]:
        rng, t = self.rng, self.t
        prof = self.profiles[cust.customer_id]
        trips = self._plan_trips(cust)
        self.trips_of[cust.customer_id] = trips
        day0 = datetime.combine(self.clock.start.date(), time())   # naive local midnight
        out: list[Event] = []
        for day in range(self.clock.days):
            local_midnight = day0 + timedelta(days=day)
            rate = prof.txns_per_day * (t["weekend_multiplier"] if local_midnight.weekday() >= 5 else 1)
            for _ in range(poisson(rng, rate)):
                hour = rng.choices(range(24), weights=t["hourly_weights"])[0]
                ts = self.local_to_utc(cust.home_city, local_midnight, hour * 3600 + rng.uniform(0, 3600))
                event = self._everyday_txn(cust, ts)
                if event:
                    out.append(event)
            if rng.random() < t["sprees"]["prob_per_day"]:
                out += self._spree(cust, local_midnight)
        for trip in trips:
            booking = self._airline_booking(cust, trip)
            if booking:
                out.append(booking)
        return out

    def _everyday_txn(self, cust: Customer, ts: datetime) -> Event | None:
        city = self.where(cust, ts)
        if city is None:
            return None   # in the air
        mcc = self.pick_category(cust.customer_id)
        merchant = self.pick_merchant(cust, mcc, city=city)
        if merchant is None:
            return None   # category not available in the destination city
        amount = self.normal_amount(cust.customer_id, mcc)
        kind = "normal" if city == cust.home_city else "travel"
        if kind == "normal" and self.rng.random() < self.t["splurge"]["rate"]:
            amount = self.category_mean(cust.customer_id, mcc) * uniform(self.rng, self.t["splurge"]["mult"])
            kind = "splurge"
        return self.make_event(self.pick_card(cust.customer_id), merchant, amount, ts, kind)

    def _spree(self, cust: Customer, local_midnight: datetime) -> list[Event]:
        """Legit rapid purchases on one card: a mall trip (in-store) or an app spree (online)."""
        rng = self.rng
        style = rng.choice(["mall", "app"])
        s = self.t["sprees"][style]
        channel = "in_store" if style == "mall" else "online"
        card = self.pick_card(cust.customer_id)
        ts = self.local_to_utc(cust.home_city, local_midnight, rng.uniform(10, 20) * 3600)
        out = []
        for _ in range(randint(rng, s["txns"])):
            if self.where(cust, ts) != cust.home_city:
                break
            mcc = rng.choice(s["mccs"])
            merchant = self.pick_merchant(cust, mcc, channel=channel)
            if merchant:
                out.append(self.make_event(card, merchant, self.normal_amount(cust.customer_id, mcc), ts, "spree"))
            ts += timedelta(seconds=uniform(rng, s["gap_s"]))
        return out

    def _plan_trips(self, cust: Customer) -> list[Trip]:
        rng, tr = self.rng, self.t["travel"]
        p = tr["trip_prob_per_day"] * self.profiles[cust.customer_id].travel_tendency
        destinations = [c for c in self.in_store_cities if c != cust.home_city]
        day0 = datetime.combine(self.clock.start.date(), time())
        trips, day = [], 0
        while day < self.clock.days:
            if rng.random() >= p:
                day += 1
                continue
            city = self.cities[rng.choice(destinations)]
            km = haversine_km(cust.home_lat, cust.home_lon, city["lat"], city["lon"])
            travel = timedelta(hours=km / tr["flight_kmh"] + tr["airport_buffer_h"])
            depart = self.local_to_utc(cust.home_city, day0 + timedelta(days=day), rng.uniform(6, 20) * 3600)
            arrive = depart + travel
            return_depart = arrive + timedelta(days=randint(rng, tr["stay_days"]))
            trips.append(Trip(cust.customer_id, city["name"], depart, arrive, return_depart, return_depart + travel))
            day = (return_depart + travel - self.clock.start).days + 1
        return trips

    def _airline_booking(self, cust: Customer, trip: Trip) -> Event | None:
        merchant = self.pick_merchant(cust, "4511", channel="online")
        if merchant is None:
            return None
        ts = trip.depart - timedelta(hours=self.rng.uniform(2, 72))
        amount = self.normal_amount(cust.customer_id, "4511")
        return self.make_event(self.pick_card(cust.customer_id), merchant, amount, ts, "travel_booking")


def schedule_sends(events: list[Event], cfg: dict, rng: random.Random) -> None:
    """Set each event's send time (#36). Fraud and legit get the same chance of being late."""
    late = cfg["late"]
    for event in events:
        delay = 0.0
        if rng.random() < late["share"]:
            delay = uniform(rng, late["short_s"] if rng.random() < late["short_share"] else late["long_s"])
        event.send_time = truncate_ms(event.event_time + timedelta(seconds=delay))
