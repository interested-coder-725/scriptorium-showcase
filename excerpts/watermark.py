"""Chapter watermark: contiguous completeness with two-run dead-gap confirmation.

Excerpt from scriptorium/workers/acquirer.py (WHITEPAPER section 5.3). The head
calls _fresh_dead_gaps after each acquisition to flag suspect holes, bridges a
flagged hole only if it is still missing on the next reconcile, and then
advances the watermark with _passable_high.
"""

from __future__ import annotations


def _passable_high(downloaded: set[float], dead: set[float], start: float) -> float:
    """Advance ``start`` over consecutive chapters we have *or* have given up on.

    The watermark means "we have every chapter up to here." Starting from the
    current watermark, step to the next integer chapter while it's either
    downloaded or confirmed *dead at the source* (a permanent empty/placeholder
    position — see :func:`_fresh_dead_gaps`), and stop at the first real gap.

    So the watermark only ever moves forward (never regresses when chapter rows
    are incomplete, e.g. migrated serials); a recoverable gap still caps it so the
    next acquire retries from there; but a permanent source hole no longer pins it
    forever and triggers endless full re-pulls.
    """
    watermark = start
    n = int(start) + 1
    while float(n) in downloaded or float(n) in dead:
        watermark = float(n)
        n += 1
    return watermark


def _fresh_dead_gaps(
    downloaded: set[float],
    known_dead: set[float],
    start: float,
    *,
    lookahead: int = 6,
    min_present: int = 3,
    max_gap: int = 3,
) -> list[float]:
    """Small holes above the watermark that look dead at the source.

    Scans for runs of missing chapters between the watermark and the highest
    downloaded chapter. A run is a candidate when it is short (<= ``max_gap``
    consecutive), *bounded* by chapters we have (the position just below is
    downloaded or is the watermark, and the position just above is downloaded),
    and the story clearly continues past it (>= ``min_present`` of the next
    ``lookahead`` chapters downloaded). Dead chapters at these sources cluster
    (e.g. a multi-part chapter split where one or two parts are empty stubs), so a
    single-hole-only rule would re-stick on a 2-3 chapter cluster.

    Candidates are only *flagged* here — not bridged until still missing on the
    next reconcile (two-run confirmation in
    :meth:`HttpWorkerAcquirer._record_chapters`). That way a chapter that merely
    failed transiently, and is recovered by the worker's in-run retry next cycle,
    is never skipped — only positions empty across runs are. A wide gap (a real
    backlog, or the live frontier of new chapters) is never flagged.
    """
    if not downloaded:
        return []
    out: list[float] = []
    top = int(max(downloaded))
    seen = downloaded | known_dead
    n = int(start) + 1
    while n < top:
        if float(n) in seen:
            n += 1
            continue
        a = n
        while n < top and float(n) not in seen:
            n += 1
        b = n - 1  # inclusive end of this missing run
        bounded = (float(a - 1) in seen or (a - 1) <= int(start)) and float(b + 1) in downloaded
        if (b - a + 1) <= max_gap and bounded:
            ahead = sum(1 for k in range(b + 1, b + 1 + lookahead) if float(k) in downloaded)
            if ahead >= min_present:
                out.extend(float(p) for p in range(a, b + 1))
    return out
