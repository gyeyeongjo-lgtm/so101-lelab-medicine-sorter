#!/usr/bin/env python3
"""Reopen evaluation captures blocked only by an obsolete center threshold.

This never approves or exports a sample. It only moves eligible records back to
``pending_review`` while preserving the previous decision in ``recheck_history``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--threshold-px", type=float, default=3.0)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.threshold_px <= 0:
        raise SystemExit("--threshold-px must be positive")
    metadata_root = args.root / "metadata"
    if not metadata_root.is_dir():
        raise SystemExit(f"metadata directory not found: {metadata_root}")

    eligible: list[str] = []
    retained: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for path in sorted(metadata_root.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not (
            record.get("status") == "blocked"
            and record.get("expected") == "positive"
            and record.get("block_reasons") == ["near_duplicate"]
        ):
            continue
        distance = record.get("nearest_positive_center_px")
        if not isinstance(distance, (int, float)) or distance < args.threshold_px:
            retained.append(record.get("stem", path.stem))
            continue
        eligible.append(record.get("stem", path.stem))
        if not args.apply:
            continue
        history = record.setdefault("recheck_history", [])
        history.append({
            "rechecked_at": now,
            "previous_status": "blocked",
            "previous_block_reasons": ["near_duplicate"],
            "previous_threshold_px": 12.0,
            "new_threshold_px": args.threshold_px,
            "nearest_positive_center_px": distance,
        })
        record["status"] = "pending_review"
        record["block_reasons"] = []
        record["near_duplicate_threshold_px"] = args.threshold_px
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "threshold_px": args.threshold_px,
        "eligible_pending_review": eligible,
        "retained_blocked": retained,
        "approved": 0,
        "exported": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
