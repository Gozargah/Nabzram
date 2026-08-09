"""Version comparison helpers."""

import re


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string like '26.7.11' or 'v1.8.4' into comparable ints."""
    cleaned = version.strip().lstrip("vV")
    parts: list[int] = []
    for part in cleaned.split("."):
        match = re.match(r"(\d+)", part)
        parts.append(int(match.group(1)) if match else 0)
    return tuple(parts)


def version_gte(current: str | None, minimum: str) -> bool:
    """Return True if current version is greater than or equal to minimum."""
    if not current:
        return False
    return parse_version(current) >= parse_version(minimum)
