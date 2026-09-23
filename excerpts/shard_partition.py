"""Word-balanced contiguous sharding of a book across parallel TTS lanes.

Excerpt from scripts/shard-plan.py (WHITEPAPER section 7.2). This is the linear
partition problem: split a sequence of section word counts into at most k
contiguous runs, minimising the heaviest run. Binary search on the answer, with
a greedy feasibility check. Measured on two retail volumes: 5.6 h -> 3.2 h.
"""

from __future__ import annotations


def feasible(weights: list[int], lanes: int, cap: int) -> bool:
    """Can `weights` be cut into <= `lanes` contiguous runs, none exceeding cap?"""
    parts, cur = 1, 0
    for w in weights:
        if cur + w <= cap:
            cur += w
        else:
            parts += 1
            cur = w
            if parts > lanes:
                return False
    return True


def partition(weights: list[int], lanes: int) -> list[tuple[int, int]]:
    """Contiguous partition minimising the heaviest lane. Returns 0-based (lo, hi).

    Binary search on the answer: any cap >= max(weights) is achievable with
    enough lanes, and feasibility is monotonic in the cap, so the smallest
    feasible cap is the optimum. Lower bound is the largest single section --
    the indivisible unit -- which is why a book with one giant chapter cannot be
    sped up by adding lanes.
    """
    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(weights, lanes, mid):
            hi = mid
        else:
            lo = mid + 1

    ranges, start, cur = [], 0, 0
    for i, w in enumerate(weights):
        if cur + w > lo:
            ranges.append((start, i - 1))
            start, cur = i, 0
        cur += w
    ranges.append((start, len(weights) - 1))
    return ranges
