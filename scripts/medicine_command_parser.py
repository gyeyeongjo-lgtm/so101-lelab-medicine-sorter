#!/usr/bin/env python3
"""Parse one Korean medicine-to-basket command without any robot integration."""

from __future__ import annotations

import argparse
import json
import re


COLOR_ALIASES = {
    "빨강": "RED",
    "빨간": "RED",
    "빨간색": "RED",
    "초록": "GREEN",
    "초록색": "GREEN",
    "파랑": "BLUE",
    "파란": "BLUE",
    "파란색": "BLUE",
}

_COLOR_PATTERN = "|".join(sorted(map(re.escape, COLOR_ALIASES), key=len, reverse=True))
_COMMAND = re.compile(
    rf"^\s*(?P<object>[ABC])\s*(?:를|을)?\s*"
    rf"(?P<color>{_COLOR_PATTERN})\s*(?:바구니|박스)\s*"
    rf"(?:에|으로|로)?\s*(?:넣어(?:줘|라)?|옮겨(?:줘|라)?)\s*[.!?。]?\s*$",
    re.IGNORECASE,
)


def parse_pick_place_command(command: str) -> dict[str, str]:
    """Return one identity-only route; coordinates and motion are intentionally absent."""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("empty_command")
    match = _COMMAND.fullmatch(command)
    if match is None:
        raise ValueError("unsupported_or_ambiguous_command")
    object_name = match.group("object").upper()
    if object_name not in {"A", "B", "C"}:
        raise ValueError("unknown_object")
    return {
        "object": object_name,
        "destination": COLOR_ALIASES[match.group("color")],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    args = parser.parse_args()
    try:
        result = parse_pick_place_command(args.command)
    except ValueError as error:
        parser.exit(2, f"command not parsed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
