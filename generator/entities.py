"""The fake world the generator draws transactions from: customers, cards, merchants.

Spend profiles live in World.spend_profiles, separate from Customer on purpose:
they are generator-only ground truth. Nothing downstream (Kafka, Spark, rules)
may read them; the detector must learn each customer's normal from the stream.

Run `python -m generator.entities` to print a sample.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from faker import Faker

CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass(frozen=True)
class Category:
    mcc: str
    name: str
    amount_min: float
    amount_max: float
    channels: tuple[str, ...]
    weight: float


@dataclass(frozen=True)
class Customer:
    customer_id: str
    home_city: str
    home_lat: float
    home_lon: float


@dataclass(frozen=True)
class Card:
    card_id: str
    customer_id: str
    card_type: str  # credit | debit


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    name: str
    mcc: str
    channel: str  # in_store | online
    city: str | None  # None for online merchants
    lat: float | None
    lon: float | None


@dataclass(frozen=True)
class SpendProfile:
    """How much one customer normally spends in one category. Generator-only."""
    mean: float
    std: float


@dataclass
class World:
    categories: dict[str, Category]  # by mcc
    customers: list[Customer]
    cards: list[Card]
    merchants: list[Merchant]
    # (customer_id, mcc) -> SpendProfile. HIDDEN: never publish, never read in detection.
    spend_profiles: dict[tuple[str, str], SpendProfile] = field(repr=False)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_world(cfg: dict) -> World:
    rng = random.Random(cfg["seed"])
    fake = Faker()
    fake.seed_instance(cfg["seed"])

    categories = {
        c["mcc"]: Category(c["mcc"], c["name"], float(c["amount_min"]), float(c["amount_max"]),
                           tuple(c["channels"]), float(c["weight"]))
        for c in cfg["categories"]
    }
    cities = cfg["cities"]
    jitter = cfg["city_jitter_deg"]

    def pick_city() -> dict:
        return rng.choices(cities, weights=[c["weight"] for c in cities])[0]

    def near(value: float) -> float:
        return round(value + rng.uniform(-jitter, jitter), 4)

    # Customers
    customers = []
    for i in range(1, cfg["counts"]["customers"] + 1):
        city = pick_city()
        customers.append(Customer(f"cust_{i:06d}", city["name"], near(city["lat"]), near(city["lon"])))

    # Cards: 1-3 per customer
    card_types = list(cfg["card_types"])
    card_weights = list(cfg["card_types"].values())
    lo, hi = cfg["cards_per_customer"]["min"], cfg["cards_per_customer"]["max"]
    cards = []
    for cust in customers:
        for _ in range(rng.randint(lo, hi)):
            card_type = rng.choices(card_types, weights=card_weights)[0]
            cards.append(Card(f"card_{len(cards) + 1:07d}", cust.customer_id, card_type))

    # Merchants: category by weight, channel from what the category allows
    cat_list = list(categories.values())
    merchants = []
    for i in range(1, cfg["counts"]["merchants"] + 1):
        cat = rng.choices(cat_list, weights=[c.weight for c in cat_list])[0]
        if len(cat.channels) == 1:
            channel = cat.channels[0]
        else:
            channel = "online" if rng.random() < cfg["online_share"] else "in_store"
        if channel == "online":
            merchants.append(Merchant(f"merch_{i:05d}", fake.company(), cat.mcc, channel, None, None, None))
        else:
            city = pick_city()
            merchants.append(Merchant(f"merch_{i:05d}", fake.company(), cat.mcc, channel,
                                      city["name"], near(city["lat"]), near(city["lon"])))

    # Spend profiles: category typical amount x customer level x per-category tweak
    sp = cfg["spend_profile"]
    spend_profiles = {}
    for cust in customers:
        level = rng.lognormvariate(0, sp["customer_level_sigma"])
        for cat in categories.values():
            typical = math.sqrt(cat.amount_min * cat.amount_max)  # geometric mid: ranges are skewed
            mean = typical * level * rng.lognormvariate(0, sp["category_tweak_sigma"])
            mean = min(max(mean, cat.amount_min), cat.amount_max)
            spend_profiles[(cust.customer_id, cat.mcc)] = SpendProfile(round(mean, 2), round(mean * sp["cv"], 2))

    return World(categories, customers, cards, merchants, spend_profiles)


def _print_sample(world: World) -> None:
    print(f"{len(world.customers)} customers, {len(world.cards)} cards, {len(world.merchants)} merchants\n")

    print("Customers + their cards:")
    for cust in world.customers[:3]:
        owned = [c for c in world.cards if c.customer_id == cust.customer_id]
        print(f"  {cust}")
        for card in owned:
            print(f"      {card}")

    print("\nMerchants (in-store and online):")
    in_store = [m for m in world.merchants if m.channel == "in_store"][:2]
    online = [m for m in world.merchants if m.channel == "online"][:2]
    for m in in_store + online:
        print(f"  {m}  [{world.categories[m.mcc].name}]")

    cust = world.customers[0]
    print(f"\nSpend profile of {cust.customer_id} (HIDDEN: generator-only):")
    for cat in world.categories.values():
        p = world.spend_profiles[(cust.customer_id, cat.mcc)]
        print(f"  {cat.name:<14} mean ${p.mean:>8.2f}  std ${p.std:>7.2f}   "
              f"(category range ${cat.amount_min:.0f}-{cat.amount_max:.0f})")


if __name__ == "__main__":
    _print_sample(build_world(load_config()))
