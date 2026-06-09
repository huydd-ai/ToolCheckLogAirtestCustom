"""Pure helpers for the parallel multi-device runner. No Airtest imports."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def partition(items: list, n: int) -> list[list]:
    """Split items into n balanced contiguous chunks (sizes differ by <= 1).

    Remainder items are distributed to the first chunks:
    partition([a..g], 3) -> [[a,b,c],[d,e],[f,g]].
    """
    if n <= 0:
        return []
    k, r = divmod(len(items), n)
    chunks: list[list] = []
    start = 0
    for i in range(n):
        size = k + (1 if i < r else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks
