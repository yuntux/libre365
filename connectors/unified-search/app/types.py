"""Shared types for the unified-search connector.

Mirrors the previous ``src/types.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Optional

Source = Literal["matrix", "seafile", "vikunja", "grommunio"]


@dataclass
class SearchResultItem:
    source: Source
    id: str
    title: str
    url: str
    snippet: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "id": self.id,
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "timestamp": self.timestamp,
        }


@dataclass
class SourceSearchOutcome:
    source: Source
    ok: bool
    took_ms: float
    results: list[SearchResultItem] = field(default_factory=list)
    error: Optional[str] = None


# Signature of a per-service search connector. The user's Bearer token is
# relayed as-is (study 2.2 lines 391, 394): it is the source service that
# filters according to the user's native permissions, not this connector.
SourceSearchFn = Callable[[str, str], Awaitable[list[SearchResultItem]]]
