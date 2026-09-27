"""Unit tests for the shared in-memory circuit breaker utility."""

import pytest

from app.utils import circuit_breaker


@pytest.fixture(autouse=True)
def _clear_between_tests():
    circuit_breaker.clear_all()
    yield
    circuit_breaker.clear_all()


def test_is_open_false_for_a_provider_never_tripped():
    assert circuit_breaker.is_open("never-tripped") is False


def test_trip_makes_is_open_true_immediately():
    circuit_breaker.trip("openzenith", cooldown_s=30.0)
    assert circuit_breaker.is_open("openzenith") is True


def test_is_open_expires_after_the_cooldown():
    circuit_breaker.trip("openzenith", cooldown_s=0.05)
    assert circuit_breaker.is_open("openzenith") is True
    import time

    time.sleep(0.1)
    assert circuit_breaker.is_open("openzenith") is False


def test_trip_is_scoped_per_provider():
    circuit_breaker.trip("openzenith", cooldown_s=30.0)
    assert circuit_breaker.is_open("openzenith") is True
    assert circuit_breaker.is_open("overpass") is False


def test_clear_all_resets_every_provider():
    circuit_breaker.trip("openzenith", cooldown_s=30.0)
    circuit_breaker.trip("overpass", cooldown_s=30.0)

    circuit_breaker.clear_all()

    assert circuit_breaker.is_open("openzenith") is False
    assert circuit_breaker.is_open("overpass") is False
