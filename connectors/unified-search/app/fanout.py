"""Core of the real-time fan-out (study 2.2 line 395): each service is queried
concurrently with its own timeout, so that a stalled service does not block
the other responses. ``asyncio.gather(..., return_exceptions=True)`` is the
exact equivalent of ``Promise.allSettled`` on the TypeScript side: no
exception raised by one source ever breaks the aggregation of the others.

Deliberately pure with respect to the network: ``sources`` are injected as a
parameter, which lets the fan-out/timeout logic be tested with mocks, without
depending on the real HTTP/IMAP implementations.
"""

from __future__ import annotations

import asyncio
import time
from typing import Mapping

from app.types import SearchResultItem, SourceSearchFn, SourceSearchOutcome

DEFAULT_TIMEOUT_MS = 2000


async def _run_one(
    source: str,
    fn: SourceSearchFn,
    query: str,
    user_token: str,
    timeout_ms: int,
) -> SourceSearchOutcome:
    start = time.monotonic()
    try:
        results = await asyncio.wait_for(fn(query, user_token), timeout=timeout_ms / 1000)
        took_ms = (time.monotonic() - start) * 1000
        return SourceSearchOutcome(source=source, ok=True, took_ms=took_ms, results=results)
    except asyncio.TimeoutError:
        return SourceSearchOutcome(
            source=source,
            ok=False,
            took_ms=float(timeout_ms),
            results=[],
            error=f'timeout after {timeout_ms}ms querying source "{source}"',
        )
    except Exception as exc:  # noqa: BLE001 - mirrors Promise.allSettled catching any rejection
        return SourceSearchOutcome(
            source=source,
            ok=False,
            took_ms=(time.monotonic() - start) * 1000,
            results=[],
            error=str(exc),
        )


async def fan_out_search(
    query: str,
    user_token: str,
    sources: Mapping[str, SourceSearchFn],
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> list[SourceSearchOutcome]:
    """Queries every source concurrently and returns one outcome per source,
    in the same order as ``sources``. A slow or failing service never blocks
    the aggregation of the others: it just surfaces with ``ok=False``.
    """
    entries = list(sources.items())

    outcomes = await asyncio.gather(
        *(_run_one(source, fn, query, user_token, timeout_ms) for source, fn in entries),
        return_exceptions=True,
    )

    # asyncio.gather(return_exceptions=True) only returns an exception object
    # instead of a result if the coroutine itself raised outside of
    # _run_one's own try/except (which should not normally happen since
    # _run_one already swallows everything) - handled defensively here to
    # stay as safe as Promise.allSettled.
    final: list[SourceSearchOutcome] = []
    for (source, _fn), outcome in zip(entries, outcomes):
        if isinstance(outcome, BaseException):
            final.append(
                SourceSearchOutcome(
                    source=source,
                    ok=False,
                    took_ms=float(timeout_ms),
                    results=[],
                    error=str(outcome),
                )
            )
        else:
            final.append(outcome)
    return final


def merge_results(outcomes: list[SourceSearchOutcome]) -> list[SearchResultItem]:
    """Flattens the results from all sources that responded successfully,
    sorted by date desc."""

    def _timestamp_key(item: SearchResultItem) -> float:
        if not item.timestamp:
            return 0.0
        try:
            from datetime import datetime

            ts = item.timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(ts).timestamp()
        except ValueError:
            return 0.0

    all_results = [r for o in outcomes for r in o.results]
    return sorted(all_results, key=_timestamp_key, reverse=True)
