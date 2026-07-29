"""Shared city-name matching used across the data tools.

Every tool maps a free-text destination ("New York", "tokyo, japan") onto a
small curated lookup table. They all used the same lenient substring match in
both directions, so the logic lives here once to keep the behavior identical
across flight/hotel/activity/weather/budget tools.
"""

from typing import Mapping, Optional, TypeVar

V = TypeVar("V")


def match_city(query: str, table: Mapping[str, V]) -> Optional[V]:
    """Return the table value whose city key loosely matches ``query``.

    Matching is case-insensitive and bidirectional: a key matches when it is a
    substring of the query *or* the query is a substring of the key (so both
    "tokyo, japan" and "toky" resolve to "tokyo"). Keys are tried in insertion
    order and the first match wins, mirroring the original per-tool loops.
    Returns ``None`` when nothing matches.
    """
    query_lower = query.lower().strip()
    for key, value in table.items():
        if key in query_lower or query_lower in key:
            return value
    return None
