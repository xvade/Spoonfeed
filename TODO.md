# Spoonfeed handoff notes

## Completed in this pass

- Replaced the unavailable Tk/web fallback with a native PySide6 (Qt) desktop
  application launched by `app.py`. The dependency is pinned in
  `requirements.txt` and installed into the local `.venv`.
- Added SQLite persistence with a deliberately small `tasks` schema:
  `title`, `notes`, `created_at`, `defer_at`, `completed_at`, and `deleted_at`.
- Implemented the priority-one daily flow: create (including `N`), visible task
  list ordered by creation time, double-click editing, complete/delete status,
  notes, and both defer shortcuts.
- Added repeating tasks backed by one series row plus virtual occurrences. A
  completion applies to one occurrence; edit/delete and series deferral apply
  to every occurrence, as required by the brief.
- Added nested subtasks with parent selection and quick creation from a task
  row. The store prevents cycles and repeating-task relationships, hides a child
  with its hidden parent, and blocks parent closure while descendants are open.
- Added predecessor selection and database validation for dependency cycles and
  parent/successor conflicts. A task stays hidden until its predecessor closes.
- Added in-session undo/redo snapshots for task mutations, including recurring
  occurrence completions, bound to Cmd/Ctrl+Z and Cmd/Ctrl+Shift+Z.
- Added an as-of view bar with successor and recently closed filters, plus due
  dates with recursive deadline validation for parent-child and dependency paths.
- Added lifecycle tests in `tests/test_store.py`, an offscreen native GUI smoke
  test, and a runnable README.
- Added `scripts/migrate_old_db.py`, a non-destructive converter from the
  legacy `old.db` task schema to Spoonfeed's current SQLite format.

## Next work, in prompt order

- [x] Every feature from the original prompt is implemented. Keep future work
  focused on UX polish, migrations, and expanded test scenarios rather than
  changing the established task rules.

## Useful implementation details

- `TaskStore.list_visible(now)` is the current source of truth for default
  visibility. It intentionally accepts a timestamp already, which will support
  the future as-of view.
- Records are soft-closed: completed/deleted tasks are retained and only hidden
  by the default query. No destructive SQL delete is used.
- Timestamp text is ISO-8601 UTC so SQLite's lexical ordering remains
  chronological. `TaskDialog` converts to and from local time for people.
- Repeating series are not expanded into future database rows. `TaskStore`
  materializes due virtual occurrences and records only completed occurrences
  in `completed_occurrences`; this keeps a series finite in SQLite while
  preserving its infinite-task behavior.
- The native window uses a one-shot timer for the earliest deferred active task
  so it refreshes when that task becomes eligible to display. This replaces the
  former polling cadence, which could leave a task hidden for nearly a minute.
