"""Behavioural tests for the excerpted algorithms. Run with: pytest excerpts/"""

from itertools import combinations
import random

from shard_partition import partition
from watermark import _fresh_dead_gaps, _passable_high


def chapters(*ranges):
    return {float(n) for lo, hi in ranges for n in range(lo, hi + 1)}


# --- watermark -------------------------------------------------------------

def test_watermark_stops_at_first_real_gap():
    have = chapters((1, 10), (12, 20))
    assert _passable_high(have, set(), 0) == 10.0


def test_confirmed_dead_chapter_is_bridged():
    have = chapters((1, 10), (12, 20))
    assert _passable_high(have, {11.0}, 0) == 20.0


def test_watermark_never_regresses():
    assert _passable_high(chapters((1, 5)), set(), 50) == 50.0


def test_short_bounded_hole_is_a_candidate():
    have = chapters((1, 10), (13, 30))
    assert _fresh_dead_gaps(have, set(), 0) == [11.0, 12.0]


def test_wide_gap_is_a_backlog_not_dead():
    have = chapters((1, 10), (20, 40))
    assert _fresh_dead_gaps(have, set(), 0) == []


def test_hole_near_the_frontier_is_not_flagged():
    # story does not clearly continue past the hole (only 2 chapters beyond it)
    have = chapters((1, 10), (12, 13))
    assert _fresh_dead_gaps(have, set(), 0) == []


# --- sharding --------------------------------------------------------------

def brute_force_best(weights, lanes):
    n, best = len(weights), sum(weights)
    for k in range(1, min(lanes, n) + 1):
        for cuts in combinations(range(1, n), k - 1):
            bounds = (0, *cuts, n)
            heaviest = max(sum(weights[a:b]) for a, b in zip(bounds, bounds[1:]))
            best = min(best, heaviest)
    return best


def test_partition_is_contiguous_and_complete():
    w = [5, 1, 9, 2, 2, 7, 3]
    ranges = partition(w, 3)
    assert ranges[0][0] == 0 and ranges[-1][1] == len(w) - 1
    assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))


def test_partition_matches_brute_force():
    rng = random.Random(7)
    for _ in range(300):
        w = [rng.randint(1, 100) for _ in range(rng.randint(1, 9))]
        lanes = rng.randint(1, 4)
        ranges = partition(w, lanes)
        assert len(ranges) <= lanes
        heaviest = max(sum(w[a:b + 1]) for a, b in ranges)
        assert heaviest == brute_force_best(w, lanes)


def test_one_giant_section_is_the_floor():
    assert max(sum([10, 500, 10, 10][a:b + 1]) for a, b in partition([10, 500, 10, 10], 4)) == 500
