"""In-memory placeholder mapping for sanitized PII."""

from collections import defaultdict

PLACEHOLDER_PREFIXES = {
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CN_PHONE": "CN_PHONE",
    "CN_ID": "CN_ID",
}


class InMemoryPiiMap:
    """Track placeholder-to-original mappings in memory only."""

    def __init__(self) -> None:
        self._entries: dict[str, str] = {}
        self._counts: defaultdict[str, int] = defaultdict(int)

    def add(self, entity_type: str, original_value: str) -> str:
        """Create a new placeholder for the given entity value."""

        prefix = PLACEHOLDER_PREFIXES.get(entity_type, entity_type)
        self._counts[prefix] += 1
        placeholder = f"[{prefix}_{self._counts[prefix]}]"
        self._entries[placeholder] = original_value
        return placeholder

    def to_dict(self) -> dict[str, str]:
        """Return a copy of the in-memory mapping."""

        return dict(self._entries)
