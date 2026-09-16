"""Deliberately flaky example: every function here is a classic flake source.

Run:  python3 -m unflake scan examples/flaky-pytest
Expect: FLK001 (sleep), FLK002 (wall clock), FLK003 (unseeded random),
        FLK004 (real network), FLK006 (hardcoded port).
"""

import datetime
import random
import time
import urllib.request


def compute_total(items):
    time.sleep(2)  # FLK001: fixed sleep instead of polling
    if datetime.datetime.now().second % 2 == 0:  # FLK002: wall clock
        time.sleep(1)
    discount = random.randint(0, 10)  # FLK003: unseeded random
    data = urllib.request.urlopen("http://localhost:9999/prices").read()  # FLK004 + FLK006
    return sum(items) - discount + len(data) % 2


def test_total():
    assert compute_total([10, 20]) >= 20


def test_discount():
    assert compute_total([5]) >= 0
