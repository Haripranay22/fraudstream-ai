"""Acceptance checks for generator/entities.py (1.08)."""

import copy
from collections import Counter

import pytest

from generator.entities import build_world, load_config


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def world(cfg):
    return build_world(cfg)


def test_counts_match_config(world, cfg):
    assert len(world.customers) == cfg["counts"]["customers"]
    assert len(world.merchants) == cfg["counts"]["merchants"]


def test_same_seed_same_world(cfg):
    assert build_world(cfg) == build_world(cfg)


def test_different_seed_different_world(cfg):
    other = copy.deepcopy(cfg)
    other["seed"] = cfg["seed"] + 1
    assert build_world(other).customers != build_world(cfg).customers


def test_every_customer_has_1_to_3_cards(world):
    per_customer = Counter(card.customer_id for card in world.cards)
    for cust in world.customers:
        assert 1 <= per_customer[cust.customer_id] <= 3, cust.customer_id


def test_every_card_has_an_existing_owner(world):
    customer_ids = {c.customer_id for c in world.customers}
    assert all(card.customer_id in customer_ids for card in world.cards)


def test_ids_are_unique(world):
    for items, attr in [(world.customers, "customer_id"), (world.cards, "card_id"), (world.merchants, "merchant_id")]:
        ids = [getattr(x, attr) for x in items]
        assert len(ids) == len(set(ids)), attr


def test_online_merchants_have_no_location(world):
    for m in world.merchants:
        if m.channel == "online":
            assert (m.city, m.lat, m.lon) == (None, None, None), m
        else:
            assert m.city is not None and m.lat is not None and m.lon is not None, m


def test_merchant_channel_allowed_by_category(world):
    for m in world.merchants:
        assert m.channel in world.categories[m.mcc].channels, m


def test_both_channels_exist(world):
    assert {m.channel for m in world.merchants} == {"in_store", "online"}


def test_spend_profile_for_every_customer_and_category(world):
    assert len(world.spend_profiles) == len(world.customers) * len(world.categories)


def test_spend_profile_inside_category_range(world):
    for (_, mcc), p in world.spend_profiles.items():
        cat = world.categories[mcc]
        assert cat.amount_min <= p.mean <= cat.amount_max
        assert p.std > 0


def test_spend_profile_not_on_customer(world):
    # Leakage guard: the hidden profile must not travel with the Customer record
    fields = set(vars(world.customers[0]))
    assert not fields & {"spend_profile", "spend_profiles", "mean", "std"}
