"""SQLite persistence for Spoonfeed's currently implemented task features.

The UI deliberately talks only to :class:`TaskStore`.  That keeps database
rules testable and gives future work (repeating tasks, subtasks, undo) one
place to extend the data model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Optional


def utc_now() -> datetime:
    """Return an aware UTC timestamp, suitable for unambiguous persistence."""
    return datetime.now(timezone.utc)


def to_storage(value: datetime) -> str:
    """Serialize a datetime as a UTC ISO-8601 value understood by SQLite text order."""
    if value.tzinfo is None:
        raise ValueError("Datetimes stored by Spoonfeed must include a timezone")
    return value.astimezone(timezone.utc).isoformat()


def from_storage(value: Optional[str]) -> Optional[datetime]:
    """Turn a stored ISO timestamp back into an aware datetime."""
    return datetime.fromisoformat(value) if value is not None else None


@dataclass(frozen=True)
class Task:
    """A persisted task; completed and deleted tasks remain available for future views."""

    id: int
    title: str
    notes: str
    created_at: datetime
    defer_at: datetime
    completed_at: Optional[datetime]
    deleted_at: Optional[datetime]
    repeat_interval_seconds: Optional[int] = None
    repeat_start_at: Optional[datetime] = None
    # A repeating series becomes a virtual task per visible occurrence.  This
    # is None for an ordinary task and identifies the instance being acted on.
    occurrence_at: Optional[datetime] = None
    parent_id: Optional[int] = None
    depth: int = 0
    hidden_child_count: int = 0
    predecessor_id: Optional[int] = None
    due_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Whether this task has not been completed or deleted."""
        return self.completed_at is None and self.deleted_at is None

    @property
    def is_repeating(self) -> bool:
        """Whether this task is a series that produces virtual occurrences."""
        return self.repeat_interval_seconds is not None


class TaskStore:
    """Own a SQLite connection and apply the core task lifecycle rules."""

    def __init__(self, database_path: str | Path = "spoonfeed.db") -> None:
        # The native app uses one UI thread. Disabling SQLite's creator-thread
        # assertion keeps the store usable by its offscreen GUI integration
        # tests; callers must still serialize database access.
        self.connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._undo_stack: list[tuple[tuple[tuple[object, ...], ...], tuple[tuple[object, ...], ...]]] = []
        self._redo_stack: list[tuple[tuple[tuple[object, ...], ...], tuple[tuple[object, ...], ...]]] = []
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        """Release the database handle when the local application stops."""
        self.connection.close()

    def _create_schema(self) -> None:
        """Create or migrate the schema for the currently implemented features."""
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                defer_at TEXT NOT NULL,
                completed_at TEXT,
                deleted_at TEXT,
                repeat_interval_seconds INTEGER,
                repeat_start_at TEXT,
                parent_id INTEGER REFERENCES tasks(id),
                predecessor_id INTEGER REFERENCES tasks(id),
                due_at TEXT
            )
            """
        )
        # Existing local databases predate repeating tasks. SQLite can add the
        # nullable columns in place, preserving every task the user already has.
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(tasks)")}
        if "repeat_interval_seconds" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN repeat_interval_seconds INTEGER")
        if "repeat_start_at" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN repeat_start_at TEXT")
        if "parent_id" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN parent_id INTEGER REFERENCES tasks(id)")
        if "predecessor_id" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN predecessor_id INTEGER REFERENCES tasks(id)")
        if "due_at" not in columns:
            self.connection.execute("ALTER TABLE tasks ADD COLUMN due_at TEXT")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_occurrences (
                task_id INTEGER NOT NULL REFERENCES tasks(id),
                occurrence_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY(task_id, occurrence_at)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS tasks_visible_index "
            "ON tasks(completed_at, deleted_at, defer_at, created_at)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS completed_occurrences_task_index "
            "ON completed_occurrences(task_id, occurrence_at)"
        )
        self.connection.execute("CREATE INDEX IF NOT EXISTS tasks_parent_index ON tasks(parent_id, created_at)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS tasks_predecessor_index ON tasks(predecessor_id)")
        self.connection.commit()

    def create_task(
        self,
        title: str,
        notes: str = "",
        defer_at: Optional[datetime] = None,
        *,
        created_at: Optional[datetime] = None,
        repeat_interval_seconds: Optional[int] = None,
        repeat_start_at: Optional[datetime] = None,
        parent_id: Optional[int] = None,
        predecessor_id: Optional[int] = None,
        due_at: Optional[datetime] = None,
    ) -> Task:
        """Persist a normal task or a repeating series.

        A series stores one task row and materializes occurrences only when
        querying. This avoids inserting an unbounded number of future rows.
        """
        before = self._snapshot()
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("A task needs a name")
        created = created_at or utc_now()
        self._validate_repeat(repeat_interval_seconds, repeat_start_at)
        self._validate_parent(parent_id, repeat_interval_seconds is not None)
        self._validate_predecessor(predecessor_id, parent_id)
        visible_after = repeat_start_at if repeat_interval_seconds is not None else (defer_at or created)
        self._validate_deferral(visible_after, due_at)
        cursor = self.connection.execute(
            """
            INSERT INTO tasks(title, notes, created_at, defer_at, repeat_interval_seconds, repeat_start_at, parent_id, predecessor_id, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cleaned_title,
                notes,
                to_storage(created),
                to_storage(visible_after),
                repeat_interval_seconds,
                to_storage(repeat_start_at) if repeat_start_at is not None else None,
                parent_id,
                predecessor_id,
                to_storage(due_at) if due_at is not None else None,
            ),
        )
        self.connection.commit()
        self._record_action(before)
        return self.get_task(cursor.lastrowid)

    def get_task(self, task_id: int) -> Task:
        """Return one task or raise KeyError when the id no longer exists."""
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"No task with id {task_id}")
        return self._task_from_row(row)

    def list_visible(
        self,
        now: Optional[datetime] = None,
        *,
        show_successors: bool = False,
        recent_closed_since: Optional[datetime] = None,
    ) -> list[Task]:
        """List tasks for an as-of view, with optional blocked/closed records."""
        point_in_time = now or utc_now()
        stamp = to_storage(point_in_time)
        active_at_point = "(completed_at IS NULL OR completed_at > ?) AND (deleted_at IS NULL OR deleted_at > ?)"
        predecessor_ready = "1 = 1" if show_successors else """(predecessor_id IS NULL OR EXISTS (
            SELECT 1 FROM tasks predecessor WHERE predecessor.id = tasks.predecessor_id
            AND ((predecessor.completed_at IS NOT NULL AND predecessor.completed_at <= ?)
              OR (predecessor.deleted_at IS NOT NULL AND predecessor.deleted_at <= ?))))"""
        rows = self.connection.execute(
            f"""
            SELECT * FROM tasks
            WHERE {active_at_point}
              AND created_at <= ?
              AND defer_at <= ?
              AND repeat_interval_seconds IS NULL
              AND {predecessor_ready}
            ORDER BY created_at ASC, id ASC
            """,
            (stamp, stamp, stamp, stamp, *(() if show_successors else (stamp, stamp))),
        ).fetchall()
        visible_normal = [self._task_from_row(row) for row in rows]
        series_rows = self.connection.execute(
            f"""
            SELECT * FROM tasks
            WHERE {active_at_point}
              AND created_at <= ?
              AND repeat_interval_seconds IS NOT NULL
              AND repeat_start_at <= ?
              AND {predecessor_ready}
            ORDER BY created_at ASC, id ASC
            """,
            (stamp, stamp, stamp, stamp, *(() if show_successors else (stamp, stamp))),
        ).fetchall()
        visible_repeats: list[Task] = []
        for row in series_rows:
            visible_repeats.extend(self._visible_occurrences(self._task_from_row(row), point_in_time))
        visible = self._order_visible_tasks(visible_normal, visible_repeats)
        if recent_closed_since is not None:
            closed_rows = self.connection.execute(
                """
                SELECT * FROM tasks
                WHERE (completed_at >= ? AND completed_at <= ?)
                   OR (deleted_at >= ? AND deleted_at <= ?)
                ORDER BY COALESCE(completed_at, deleted_at) DESC, id DESC
                """,
                (to_storage(recent_closed_since), stamp, to_storage(recent_closed_since), stamp),
            ).fetchall()
            visible.extend(self._task_from_row(row) for row in closed_rows)
        return visible

    def next_deferred_at(self, now: Optional[datetime] = None) -> Optional[datetime]:
        """Return the next active task or recurring occurrence visibility time.

        The native UI uses this to schedule one precise refresh rather than
        polling on an arbitrary interval that can make a newly visible task
        appear late.
        """
        point_in_time = now or utc_now()
        row = self.connection.execute(
            """
            SELECT MIN(defer_at) AS next_defer_at FROM tasks
            WHERE completed_at IS NULL
              AND deleted_at IS NULL
              AND repeat_interval_seconds IS NULL
              AND defer_at > ?
            """,
            (to_storage(point_in_time),),
        ).fetchone()
        next_times = [from_storage(row["next_defer_at"])]
        series_rows = self.connection.execute(
            """
            SELECT * FROM tasks
            WHERE completed_at IS NULL
              AND deleted_at IS NULL
              AND repeat_interval_seconds IS NOT NULL
            """
        ).fetchall()
        for row in series_rows:
            task = self._task_from_row(row)
            next_times.append(self._next_occurrence_after(task, point_in_time))
        candidates = [candidate for candidate in next_times if candidate is not None]
        return min(candidates) if candidates else None

    def update_task(
        self,
        task_id: int,
        title: str,
        notes: str,
        defer_at: datetime,
        *,
        repeat_interval_seconds: Optional[int] = None,
        repeat_start_at: Optional[datetime] = None,
        parent_id: Optional[int] = None,
        predecessor_id: Optional[int] = None,
        due_at: Optional[datetime] = None,
    ) -> Task:
        """Update an active task or every virtual task in a recurring series."""
        before = self._snapshot()
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("A task needs a name")
        self._validate_repeat(repeat_interval_seconds, repeat_start_at)
        self._validate_parent(parent_id, repeat_interval_seconds is not None, task_id=task_id)
        self._validate_predecessor(predecessor_id, parent_id, task_id=task_id)
        if repeat_interval_seconds is not None and self._descendant_ids(task_id):
            raise ValueError("A repeating task cannot be a parent task")
        visible_after = repeat_start_at if repeat_interval_seconds is not None else defer_at
        self._validate_deferral(visible_after, due_at, task_id=task_id)
        result = self.connection.execute(
            """
            UPDATE tasks
            SET title = ?, notes = ?, defer_at = ?,
                repeat_interval_seconds = ?, repeat_start_at = ?
                , parent_id = ?, predecessor_id = ?, due_at = ?
            WHERE id = ? AND completed_at IS NULL AND deleted_at IS NULL
            """,
            (
                cleaned_title,
                notes,
                to_storage(visible_after),
                repeat_interval_seconds,
                to_storage(repeat_start_at) if repeat_start_at is not None else None,
                parent_id,
                predecessor_id,
                to_storage(due_at) if due_at is not None else None,
                task_id,
            ),
        )
        self.connection.commit()
        if result.rowcount != 1:
            raise ValueError("Only active tasks can be edited")
        self._record_action(before)
        return self.get_task(task_id)

    def complete_task(
        self,
        task_id: int,
        at: Optional[datetime] = None,
        *,
        occurrence_at: Optional[datetime] = None,
    ) -> Task:
        """Complete one task, or exactly one occurrence of a recurring series."""
        before = self._snapshot()
        task = self.get_task(task_id)
        if task.is_repeating:
            if occurrence_at is None:
                raise ValueError("A repeating task needs an occurrence time to be completed")
            self.connection.execute(
                """
                INSERT OR IGNORE INTO completed_occurrences(task_id, occurrence_at, completed_at)
                VALUES (?, ?, ?)
                """,
                (task_id, to_storage(occurrence_at), to_storage(at or utc_now())),
            )
            self.connection.commit()
            self._record_action(before)
            return replace(task, defer_at=occurrence_at, occurrence_at=occurrence_at, completed_at=at or utc_now())
        self._ensure_children_closed(task_id)
        closed = self._close_task(task_id, "completed_at", at or utc_now())
        self._record_action(before)
        return closed

    def delete_task(self, task_id: int, at: Optional[datetime] = None) -> Task:
        """Mark a task deleted without erasing its record."""
        before = self._snapshot()
        self._ensure_children_closed(task_id)
        deleted = self._close_task(task_id, "deleted_at", at or utc_now())
        self._record_action(before)
        return deleted

    def defer_task(self, task_id: int, until: datetime) -> Task:
        """Hide a task; for a series, move its shared repeat start time."""
        before = self._snapshot()
        task = self.get_task(task_id)
        self._validate_deferral(until, task.due_at, task_id=task_id)
        if task.is_repeating:
            result = self.connection.execute(
                """
                UPDATE tasks SET defer_at = ?, repeat_start_at = ?
                WHERE id = ? AND completed_at IS NULL AND deleted_at IS NULL
                """,
                (to_storage(until), to_storage(until), task_id),
            )
        else:
            result = self.connection.execute(
                """
                UPDATE tasks SET defer_at = ?
                WHERE id = ? AND completed_at IS NULL AND deleted_at IS NULL
                """,
                (to_storage(until), task_id),
            )
        self.connection.commit()
        if result.rowcount != 1:
            raise ValueError("Only active tasks can be deferred")
        self._record_action(before)
        return self.get_task(task_id)

    def undo(self) -> bool:
        """Restore the state before the most recent user-visible mutation."""
        if not self._undo_stack:
            return False
        before, after = self._undo_stack.pop()
        self._restore_snapshot(before)
        self._redo_stack.append((before, after))
        return True

    def redo(self) -> bool:
        """Reapply the most recently undone user-visible mutation."""
        if not self._redo_stack:
            return False
        before, after = self._redo_stack.pop()
        self._restore_snapshot(after)
        self._undo_stack.append((before, after))
        return True

    @property
    def can_undo(self) -> bool:
        """Whether the current application session has an action to undo."""
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        """Whether the current application session has an action to redo."""
        return bool(self._redo_stack)

    def _close_task(self, task_id: int, column: str, at: datetime) -> Task:
        # ``column`` is internal and fixed by the public methods above; it is
        # not user input, so interpolation here cannot construct arbitrary SQL.
        result = self.connection.execute(
            f"UPDATE tasks SET {column} = ? "
            "WHERE id = ? AND completed_at IS NULL AND deleted_at IS NULL",
            (to_storage(at), task_id),
        )
        self.connection.commit()
        if result.rowcount != 1:
            raise ValueError("Only active tasks can be closed")
        return self.get_task(task_id)

    def _ensure_children_closed(self, task_id: int) -> None:
        """Prevent closing a parent while any direct or nested child remains active."""
        row = self.connection.execute(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT id FROM tasks WHERE parent_id = ?
                UNION ALL
                SELECT tasks.id FROM tasks JOIN descendants ON tasks.parent_id = descendants.id
            )
            SELECT 1 FROM tasks JOIN descendants ON tasks.id = descendants.id
            WHERE tasks.completed_at IS NULL AND tasks.deleted_at IS NULL
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        if row is not None:
            raise ValueError("A parent cannot be closed until all subtasks are closed")

    def _validate_deferral(self, until: datetime, due_at: Optional[datetime], task_id: Optional[int] = None) -> None:
        """Reject a defer that would hide a task, child, or successor past due."""
        due_dates = [due_at] if due_at is not None else []
        if task_id is not None:
            related_ids = self._descendant_ids(task_id) | self._successor_ids(task_id)
            if related_ids:
                placeholders = ", ".join("?" for _ in related_ids)
                rows = self.connection.execute(
                    f"SELECT due_at FROM tasks WHERE id IN ({placeholders}) AND due_at IS NOT NULL",
                    tuple(related_ids),
                ).fetchall()
                due_dates.extend(from_storage(row["due_at"]) for row in rows)
        if any(due is not None and until >= due for due in due_dates):
            raise ValueError("Cannot defer a task until or past an affected due date")

    def _snapshot(self) -> tuple[tuple[tuple[object, ...], ...], tuple[tuple[object, ...], ...]]:
        """Capture mutable task tables for in-session undo/redo restoration."""
        tasks = tuple(tuple(row) for row in self.connection.execute("SELECT * FROM tasks ORDER BY id"))
        occurrences = tuple(
            tuple(row)
            for row in self.connection.execute("SELECT * FROM completed_occurrences ORDER BY task_id, occurrence_at")
        )
        return tasks, occurrences

    def _record_action(self, before: tuple[tuple[tuple[object, ...], ...], tuple[tuple[object, ...], ...]]) -> None:
        """Store a completed mutation and invalidate redo after a divergent action."""
        after = self._snapshot()
        if after != before:
            self._undo_stack.append((before, after))
            self._redo_stack.clear()

    def _restore_snapshot(self, snapshot: tuple[tuple[tuple[object, ...], ...], tuple[tuple[object, ...], ...]]) -> None:
        """Replace mutable tables with a prior snapshot while honoring self FKs."""
        tasks, occurrences = snapshot
        self.connection.execute("PRAGMA defer_foreign_keys = ON")
        self.connection.execute("DELETE FROM completed_occurrences")
        self.connection.execute("DELETE FROM tasks")
        if tasks:
            placeholders = ", ".join("?" for _ in tasks[0])
            self.connection.executemany(f"INSERT INTO tasks VALUES ({placeholders})", tasks)
        if occurrences:
            self.connection.executemany("INSERT INTO completed_occurrences VALUES (?, ?, ?)", occurrences)
        self.connection.commit()

    @staticmethod
    def _validate_repeat(repeat_interval_seconds: Optional[int], repeat_start_at: Optional[datetime]) -> None:
        """Require both parts of a repeat schedule and a positive interval."""
        if (repeat_interval_seconds is None) != (repeat_start_at is None):
            raise ValueError("Repeating tasks need both an interval and a start time")
        if repeat_interval_seconds is not None and repeat_interval_seconds <= 0:
            raise ValueError("A repeat interval must be greater than zero")

    def _visible_occurrences(self, task: Task, now: datetime) -> list[Task]:
        """Materialize each due, incomplete occurrence of one repeating series."""
        if not task.is_repeating or task.repeat_start_at is None or task.repeat_interval_seconds is None:
            return []
        elapsed_seconds = (now - task.repeat_start_at).total_seconds()
        if elapsed_seconds < 0:
            return []
        last_index = int(elapsed_seconds // task.repeat_interval_seconds)
        completed_rows = self.connection.execute(
            "SELECT occurrence_at FROM completed_occurrences WHERE task_id = ?",
            (task.id,),
        ).fetchall()
        completed = {row["occurrence_at"] for row in completed_rows}
        occurrences: list[Task] = []
        for index in range(last_index + 1):
            occurrence_at = task.repeat_start_at + timedelta(seconds=task.repeat_interval_seconds * index)
            if to_storage(occurrence_at) not in completed:
                occurrences.append(replace(task, defer_at=occurrence_at, occurrence_at=occurrence_at))
        return occurrences

    def _next_occurrence_after(self, task: Task, now: datetime) -> Optional[datetime]:
        """Find the next future occurrence that has not already been completed."""
        if not task.is_repeating or task.repeat_start_at is None or task.repeat_interval_seconds is None:
            return None
        elapsed_seconds = (now - task.repeat_start_at).total_seconds()
        next_index = 0 if elapsed_seconds < 0 else int(elapsed_seconds // task.repeat_interval_seconds) + 1
        completed_rows = self.connection.execute(
            "SELECT occurrence_at FROM completed_occurrences WHERE task_id = ?",
            (task.id,),
        ).fetchall()
        completed = {row["occurrence_at"] for row in completed_rows}
        # The next occurrence is normally the next index. A completed row can
        # exist only when an old schedule was edited, so keep searching safely.
        while True:
            candidate = task.repeat_start_at + timedelta(seconds=task.repeat_interval_seconds * next_index)
            if to_storage(candidate) not in completed:
                return candidate
            next_index += 1

    def _order_visible_tasks(self, visible_normal: list[Task], visible_repeats: list[Task]) -> list[Task]:
        """Nest visible children under visible parents and count hidden children.

        A child is omitted when its parent is not currently visible. This makes
        a parent's defer/close state authoritative for every descendant.
        """
        active_rows = self.connection.execute(
            """
            SELECT * FROM tasks
            WHERE completed_at IS NULL AND deleted_at IS NULL
              AND repeat_interval_seconds IS NULL
            """
        ).fetchall()
        active_normal = [self._task_from_row(row) for row in active_rows]
        visible_by_id = {task.id: task for task in visible_normal}
        children: dict[Optional[int], list[Task]] = {}
        for task in visible_normal:
            children.setdefault(task.parent_id, []).append(task)
        for task_list in children.values():
            task_list.sort(key=lambda task: (task.created_at, task.id))
        hidden_counts: dict[int, int] = {}
        for task in active_normal:
            if task.parent_id is not None and task.id not in visible_by_id:
                hidden_counts[task.parent_id] = hidden_counts.get(task.parent_id, 0) + 1

        def append_branch(task: Task, depth: int, output: list[Task]) -> None:
            output.append(replace(task, depth=depth, hidden_child_count=hidden_counts.get(task.id, 0)))
            for child in children.get(task.id, []):
                append_branch(child, depth + 1, output)

        roots: list[Task] = [task for task in visible_normal if task.parent_id is None]
        roots.extend(visible_repeats)
        roots.sort(key=lambda task: (task.created_at, task.occurrence_at or task.defer_at, task.id))
        ordered: list[Task] = []
        for root in roots:
            append_branch(root, 0, ordered)
        return ordered

    def list_parent_candidates(self, task_id: Optional[int] = None) -> list[Task]:
        """Return active non-repeating tasks that can be selected as a parent."""
        excluded_ids = self._descendant_ids(task_id) if task_id is not None else set()
        if task_id is not None:
            excluded_ids.add(task_id)
        rows = self.connection.execute(
            """
            SELECT * FROM tasks
            WHERE completed_at IS NULL AND deleted_at IS NULL
              AND repeat_interval_seconds IS NULL
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        return [self._task_from_row(row) for row in rows if row["id"] not in excluded_ids]

    def list_predecessor_candidates(self, task_id: Optional[int] = None) -> list[Task]:
        """Return tasks that cannot introduce a predecessor cycle for ``task_id``."""
        excluded_ids = self._successor_ids(task_id) if task_id is not None else set()
        if task_id is not None:
            excluded_ids.add(task_id)
        rows = self.connection.execute(
            """
            SELECT * FROM tasks
            WHERE completed_at IS NULL AND deleted_at IS NULL
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        return [self._task_from_row(row) for row in rows if row["id"] not in excluded_ids]

    def _descendant_ids(self, task_id: int) -> set[int]:
        """Return every nested child id, used to prevent parent cycles in the UI."""
        rows = self.connection.execute(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT id FROM tasks WHERE parent_id = ?
                UNION ALL
                SELECT tasks.id FROM tasks JOIN descendants ON tasks.parent_id = descendants.id
            )
            SELECT id FROM descendants
            """,
            (task_id,),
        ).fetchall()
        return {row["id"] for row in rows}

    def _validate_parent(self, parent_id: Optional[int], repeating: bool, task_id: Optional[int] = None) -> None:
        """Enforce the parent rules before changing a task relationship."""
        if parent_id is None:
            return
        if repeating:
            raise ValueError("Repeating tasks cannot be subtasks")
        if parent_id == task_id:
            raise ValueError("A task cannot be its own parent")
        parent = self.get_task(parent_id)
        if not parent.is_active or parent.is_repeating:
            raise ValueError("A parent must be an active, non-repeating task")
        if task_id is not None and parent_id in self._descendant_ids(task_id):
            raise ValueError("A task cannot be placed under one of its descendants")

    def _validate_predecessor(
        self, predecessor_id: Optional[int], parent_id: Optional[int], task_id: Optional[int] = None
    ) -> None:
        """Reject predecessor cycles and dependencies on a task's parent tree."""
        if predecessor_id is None:
            return
        if predecessor_id == task_id:
            raise ValueError("A task cannot be its own predecessor")
        predecessor = self.get_task(predecessor_id)
        if not predecessor.is_active:
            raise ValueError("A predecessor must be active")
        if task_id is not None and predecessor_id in self._successor_ids(task_id):
            raise ValueError("Predecessor relationships must remain acyclic")
        if parent_id is not None and predecessor_id in {parent_id, *self._successor_ids(parent_id)}:
            raise ValueError("A task cannot depend on its parent or its parent's successors")

    def _successor_ids(self, task_id: int) -> set[int]:
        """Find dependency descendants for cycle validation."""
        rows = self.connection.execute(
            """
            WITH RECURSIVE successors(id) AS (
                SELECT id FROM tasks WHERE predecessor_id = ?
                UNION ALL
                SELECT tasks.id FROM tasks JOIN successors ON tasks.predecessor_id = successors.id
            ) SELECT id FROM successors
            """,
            (task_id,),
        ).fetchall()
        return {row["id"] for row in rows}

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            notes=row["notes"],
            created_at=from_storage(row["created_at"]),  # type: ignore[arg-type]
            defer_at=from_storage(row["defer_at"]),  # type: ignore[arg-type]
            completed_at=from_storage(row["completed_at"]),
            deleted_at=from_storage(row["deleted_at"]),
            repeat_interval_seconds=row["repeat_interval_seconds"],
            repeat_start_at=from_storage(row["repeat_start_at"]),
            parent_id=row["parent_id"],
            predecessor_id=row["predecessor_id"],
            due_at=from_storage(row["due_at"]),
        )
