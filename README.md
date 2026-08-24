# Spoonfeed

Spoonfeed is a local-first native task manager written in Python. Its first
working slice focuses on the quick daily task loop: create tasks, edit their
details, defer them, complete them, and mark them deleted without losing the
historical record. The interface uses Qt's native desktop windows and controls.

## Run it

Create an isolated virtual environment and install the native GUI dependency:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

This opens Spoonfeed as a native desktop window and creates `spoonfeed.db`
beside the launcher if it does not already exist. The database is intentionally
ignored by Git because it contains local task data.

Place `hero.m4a` in the project root to play it whenever a task is completed.
Place calming images in the ignored `.images/` directory. For one minute after
a check-off, press `D` once to choose whether to display a random image. The
shortcut remains available even when focus changes as the completed row
disappears. Confirming displays an image only 20% of the time. Any key closes
the image window, which also closes automatically after one minute.

The `+1 hour` and Shift-held `Next midnight` defer actions are calculated from
the active **View as of** time. In the live `Now` view, that reference is the
current time.

When **Show successor tasks** is enabled, dependency cues show a successor's
predecessor (`after: …`) and the successors a task unlocks (`unlocks: …`).

Parent and predecessor dropdowns only offer tasks currently visible under the
active view and its filters.

Click **Checked off since**, or press `T`, to open a separate completed-task
history window. It defaults to the previous local midnight and never includes
deleted tasks. Press Escape to close it.

## Migrate `old.db`

To create a current-format copy of the legacy database without modifying the
source, run:

```sh
.venv/bin/python scripts/migrate_old_db.py old.db spoonfeed-migrated.db
```

The converter preserves task IDs, names, creation/display/due times, checked
state, and repeat schedules. It carries any unsupported legacy metadata into
notes. Legacy checked-off tasks do not include a check-off timestamp, so their
legacy display time becomes the completion timestamp. Review the six migrated
repeat intervals if their old application used a different time unit.

## Current interaction model

- Press `N`, or click **New task**, to open the task form. Press Return while
  entering the task name to save it.
- Press `T`, or click **Checked off since**, to open the completed-task history
  window. Adjust its datetime to change the lower bound.
- The main list contains active tasks whose defer time has passed, ordered by
  creation time.
- Double-click a task to edit its name, notes, or visibility time.
- **Complete** stores a completion timestamp and removes the task from the
  default list. Hold Shift to turn it into **Delete**, which instead stores a
  deletion timestamp.
- **+1 hour** defers the task by an hour. Hold Shift to make it defer until the
  next local midnight.
- In the task form, select **Repeat task** to set an interval and repeat start.
  Each due occurrence appears separately; completing one completes only that
  occurrence, while editing or deleting any occurrence changes the whole series.
- Choose a **Parent task** to make a nested subtask. Parents cannot be completed
  or deleted until all descendants are closed; hidden active children are shown
  as a count below the visible child block.
- Choose a **Predecessor task** to keep a task hidden until that predecessor is
  completed or deleted. Spoonfeed rejects dependency cycles and parent-conflicting
  dependencies.
- Use Cmd+Z / Cmd+Shift+Z (or Ctrl equivalents) to undo and redo task changes
  during the current application session.
- The view bar lets you inspect a past or future point, reveal successor tasks,
  and include recently completed/deleted tasks from a chosen time.
- Enable **Set due date** in the task form to prevent any defer action that
  would hide the task—or an affected subtask or successor—at/after its deadline.

All timestamps are stored in UTC, while the native form accepts and shows local
time.

## Development

Run the test suite with:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The storage boundary is in `spoonfeed/store.py`; `spoonfeed/native.py` owns the
Qt widgets and should be extended instead of issuing SQLite statements from an
interface directly. See [`TODO.md`](TODO.md) for follow-up and maintenance notes.
