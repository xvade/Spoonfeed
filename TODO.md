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
- The Show successor tasks view now labels both sides of each visible
  dependency: successor rows identify the predecessor they follow and
  predecessor rows list the tasks they unlock.
- Parent and predecessor dropdowns now intersect their safe candidates with
  the tasks visible in the current as-of view and active filters.
- Added the Checked off since history window, opened by its header button or
  `T`. It defaults to the previous local midnight, filters out deleted tasks,
  includes completed recurring occurrences, and closes with Escape.
- Added in-session undo/redo snapshots for task mutations, including recurring
  occurrence completions, bound to Cmd/Ctrl+Z and Cmd/Ctrl+Shift+Z.
- Added an as-of view bar with successor and recently closed filters, plus due
  dates with recursive deadline validation for parent-child and dependency paths.
- Added lifecycle tests in `tests/test_store.py`, an offscreen native GUI smoke
  test, and a runnable README.
- Added `scripts/migrate_old_db.py`, a non-destructive converter from the
  legacy `old.db` task schema to Spoonfeed's current SQLite format.
- Added optional completion audio: a root-level `hero.m4a` plays after a task
  is successfully checked off (but never after deletion).
- Defer actions now use the active View as of timestamp: `+1 hour` adds an
  hour to it, while Shift-held Next midnight finds the following local midnight
  after it. The live Now view continues to use the current time.
- Repeating-task defer actions now persist a display-time override only for the
  selected occurrence. The series start and interval remain unchanged, and the
  override participates in undo/redo and refresh scheduling.
- Consecutive repeating occurrences now form an implicit predecessor chain:
  only the next incomplete occurrence shows normally; Show successor tasks
  reveals later occurrences and marks their previous-occurrence dependency.
- Added an optional post-completion calming-image flow. `.images/` is ignored;
  for one minute after a check-off, `D` offers one random image and works only
  once until the next check-off. The image window closes on any keypress or
  after one minute. The app-level key route also works if focus changes as the
  completed row disappears. Closing an image clears its tracked window object,
  which prevents a prior viewer from blocking the next completion's `D` prompt.
  Confirming the prompt displays an image with a 20% probability.

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
