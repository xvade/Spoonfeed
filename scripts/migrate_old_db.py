#!/usr/bin/env python3
"""Convert Spoonfeed's legacy ``old.db`` schema into the current task schema.

The converter never changes the source database. By default it refuses to
overwrite the output path, so a failed or unexpected conversion is recoverable.
Legacy timestamps are naive local times; supply ``--timezone`` when the source
database was created in a different timezone.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo


# Let this standalone script import the application's SQLite-only store module.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from spoonfeed.store import TaskStore, to_storage  # noqa: E402


def parse_legacy_datetime(value: object, timezone: ZoneInfo) -> datetime | None:
    """Convert legacy SQLite datetime text into Spoonfeed's aware UTC format."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed


def legacy_notes(task: sqlite3.Row, goals: dict[int, str]) -> str:
    """Keep legacy fields without direct modern equivalents in the task notes."""
    parts = [str(task["description"] or "").strip()]
    metadata = {
        "Legacy goal": goals.get(task["associated_goal"]),
        "Legacy tags": task["tags"],
        "Legacy display condition": task["display_condition"],
        "Legacy check-off action": task["on_checkoff"],
        "Legacy priority": task["priority"],
        "Legacy times put off": task["times_put_off"],
        "Legacy midnight repeat": task["midnight_repeat"],
    }
    for label, value in metadata.items():
        if value not in (None, "", 0):
            parts.append(f"{label}: {value}")
    return "\n\n".join(part for part in parts if part)


def migrate(source_path: Path, output_path: Path, timezone_name: str, force: bool = False) -> int:
    """Copy legacy tasks into a new current-format database and return its count."""
    if source_path.resolve() == output_path.resolve():
        raise ValueError("Source and output paths must be different; the source is never modified")
    if not source_path.is_file():
        raise FileNotFoundError(f"Legacy database not found: {source_path}")
    if output_path.exists():
        if not force:
            raise FileExistsError(f"Output already exists: {output_path} (use --force to replace it)")
        output_path.unlink()

    timezone = ZoneInfo(timezone_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = sqlite3.connect(source_path)
    legacy.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in legacy.execute("PRAGMA table_info(tasks)")}
        required = {"task_id", "name", "checked_off", "display_date", "created_at"}
        if not required <= columns:
            missing = ", ".join(sorted(required - columns))
            raise ValueError(f"Not a supported legacy Spoonfeed database; missing: {missing}")
        goals = {
            row["goal_id"]: row["name"]
            for row in legacy.execute("SELECT goal_id, name FROM goals")
        }
        rows = legacy.execute("SELECT * FROM tasks ORDER BY task_id").fetchall()
        store = TaskStore(output_path)
        try:
            for row in rows:
                created_at = parse_legacy_datetime(row["created_at"], timezone)
                defer_at = parse_legacy_datetime(row["display_date"], timezone)
                due_at = parse_legacy_datetime(row["due_date"], timezone)
                if created_at is None or defer_at is None:
                    raise ValueError(f"Legacy task {row['task_id']} is missing a required timestamp")
                repeating = bool(row["repeats"])
                interval = row["repeat_interval"] if repeating else None
                if repeating and (interval is None or int(interval) <= 0):
                    raise ValueError(f"Legacy repeating task {row['task_id']} has no positive interval")
                # Insert directly to preserve legacy IDs and avoid treating the
                # whole import as one enormous undoable user action.
                store.connection.execute(
                    """
                    INSERT INTO tasks(
                        id, title, notes, created_at, defer_at, completed_at,
                        deleted_at, repeat_interval_seconds, repeat_start_at,
                        parent_id, predecessor_id, due_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, ?)
                    """,
                    (
                        row["task_id"],
                        str(row["name"]).strip() or "Untitled legacy task",
                        legacy_notes(row, goals),
                        to_storage(created_at),
                        to_storage(defer_at),
                        to_storage(defer_at) if bool(row["checked_off"]) else None,
                        int(interval) if interval is not None else None,
                        to_storage(defer_at) if repeating else None,
                        to_storage(due_at) if due_at is not None else None,
                    ),
                )
            store.connection.commit()
        finally:
            store.close()
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    finally:
        legacy.close()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("old.db"), help="legacy database (default: old.db)")
    parser.add_argument("output", nargs="?", type=Path, default=Path("spoonfeed-migrated.db"), help="new database path")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="timezone used by legacy naive timestamps")
    parser.add_argument("--force", action="store_true", help="replace an existing output database")
    args = parser.parse_args()
    try:
        count = migrate(args.source, args.output, args.timezone, args.force)
    except (FileNotFoundError, FileExistsError, ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    print(f"Migrated {count} tasks from {args.source} to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
