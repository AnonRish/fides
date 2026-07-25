"""
Deterministic reduction primitives -- a narrow, honest slice of SITREP
item 6 ("Reproducible inference stack", not started). The supplement's own
framing is that non-determinism in ML inference isn't fundamental
(computers are deterministic machines) but creeps in through
optimizations -- most concretely, floating-point addition is not
associative, so a parallel reduction (e.g. summing partial results across
GPU thread blocks) that completes in a different, load-dependent order
produces a different bit pattern each run, even given the exact same
input.

This module doesn't reproduce a real inference stack (no GPU access here)
-- it isolates and fixes the specific, well-documented mechanism a real
one would need to fix: reduction order. `deterministic_sum` always reduces
in a fixed, index-based tree order regardless of runtime scheduling;
`racy_sum` simulates what an unconstrained, schedule-dependent reduction
looks like (same logical job, order varies run to run), so the difference
is demonstrated empirically in test_determinism.py rather than asserted.

Honest limitation: fixing the reduction algorithm is necessary but not
sufficient. If the values feeding the reduction arrive in a different
upstream order across runs (different batching, different tensor-parallel
shard assignment), a fixed-order reduction still produces different
results, because "fixed order" means fixed relative to input order, not
invariant to it. Real determinism needs both a fixed reduction algorithm
AND a canonicalized upstream data order; this module provides the former
only.
"""

import random


def deterministic_sum(values: list) -> float:
    """Fixed-order pairwise tree reduction. Same input list, same output,
    every time -- the combine order depends on list position only, never
    on runtime scheduling."""
    values = list(values)
    while len(values) > 1:
        next_level = []
        for i in range(0, len(values) - 1, 2):
            next_level.append(values[i] + values[i + 1])
        if len(values) % 2 == 1:
            next_level.append(values[-1])
        values = next_level
    return values[0] if values else 0.0


def racy_sum(values: list, seed: int = None) -> float:
    """Simulates a schedule-dependent reduction: the same logical value
    set, summed in a randomly varying order each call -- standing in for
    partial sums completing and being combined in whatever order threads
    happen to finish, which is exactly what an unconstrained parallel
    reduction does across repeated runs."""
    rng = random.Random(seed)
    shuffled = list(values)
    rng.shuffle(shuffled)
    total = 0.0
    for v in shuffled:
        total += v
    return total
