"""Behavior tests for the SQLite task lifecycle."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from spoonfeed.store import TaskStore


NOW = datetime(2026, 8, 21, 18, 0, tzinfo=timezone.utc)


class TaskStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.store = TaskStore(Path(self.directory.name) / "tasks.db")

    def tearDown(self) -> None:
        self.store.close()
        self.directory.cleanup()

    def test_create_records_name_notes_and_timestamps(self) -> None:
        task = self.store.create_task("  Buy milk  ", "Oat milk", created_at=NOW)

        self.assertEqual(task.title, "Buy milk")
        self.assertEqual(task.notes, "Oat milk")
        self.assertEqual(task.created_at, NOW)
        self.assertEqual(task.defer_at, NOW)

    def test_visible_tasks_are_oldest_first_and_hide_future_deferred(self) -> None:
        later = self.store.create_task("Later", defer_at=NOW + timedelta(hours=1), created_at=NOW)
        first = self.store.create_task("First", created_at=NOW - timedelta(minutes=2))
        second = self.store.create_task("Second", created_at=NOW - timedelta(minutes=1))

        self.assertEqual([task.id for task in self.store.list_visible(NOW)], [first.id, second.id])
        self.assertNotIn(later.id, [task.id for task in self.store.list_visible(NOW)])

    def test_edit_updates_notes_and_defer_time(self) -> None:
        task = self.store.create_task("Draft", created_at=NOW)
        updated = self.store.update_task(task.id, "Publish", "Review links", NOW + timedelta(days=1))

        self.assertEqual(updated.title, "Publish")
        self.assertEqual(updated.notes, "Review links")
        self.assertEqual(updated.defer_at, NOW + timedelta(days=1))

    def test_next_deferred_time_ignores_closed_and_already_visible_tasks(self) -> None:
        visible = self.store.create_task("Visible", created_at=NOW)
        first_future = self.store.create_task("First future", defer_at=NOW + timedelta(minutes=2), created_at=NOW)
        closed_future = self.store.create_task("Closed future", defer_at=NOW + timedelta(minutes=1), created_at=NOW)
        self.store.complete_task(closed_future.id, NOW)

        self.assertEqual(self.store.next_deferred_at(NOW), first_future.defer_at)
        self.assertNotEqual(self.store.next_deferred_at(NOW), visible.defer_at)

    def test_complete_and_delete_preserve_records_but_hide_them(self) -> None:
        complete = self.store.create_task("Complete", created_at=NOW)
        deleted = self.store.create_task("Delete", created_at=NOW)

        self.store.complete_task(complete.id, NOW + timedelta(minutes=1))
        self.store.delete_task(deleted.id, NOW + timedelta(minutes=2))

        self.assertEqual(self.store.list_visible(NOW + timedelta(days=1)), [])
        self.assertEqual(self.store.get_task(complete.id).completed_at, NOW + timedelta(minutes=1))
        self.assertEqual(self.store.get_task(deleted.id).deleted_at, NOW + timedelta(minutes=2))

    def test_completed_history_includes_repeating_occurrences_but_not_deleted_tasks(self) -> None:
        normal = self.store.create_task("Normal", created_at=NOW)
        deleted = self.store.create_task("Deleted", created_at=NOW)
        series = self.store.create_task(
            "Recurring",
            repeat_interval_seconds=3_600,
            repeat_start_at=NOW,
            created_at=NOW,
        )
        self.store.complete_task(normal.id, NOW + timedelta(minutes=1))
        self.store.delete_task(deleted.id, NOW + timedelta(minutes=2))
        self.store.complete_task(series.id, NOW + timedelta(minutes=3), occurrence_at=NOW)

        completed = self.store.list_completed_since(NOW)

        self.assertEqual([task.title for task in completed], ["Recurring", "Normal"])
        self.assertEqual(completed[0].occurrence_at, NOW)
        self.assertEqual(completed[0].completed_at, NOW + timedelta(minutes=3))

    def test_closed_tasks_cannot_be_edited_or_closed_again(self) -> None:
        task = self.store.create_task("One-shot", created_at=NOW)
        self.store.complete_task(task.id, NOW)

        with self.assertRaises(ValueError):
            self.store.update_task(task.id, "Changed", "", NOW)
        with self.assertRaises(ValueError):
            self.store.delete_task(task.id, NOW)

    def test_repeating_task_materializes_due_occurrences_and_completes_one_at_a_time(self) -> None:
        series = self.store.create_task(
            "Drink water",
            repeat_interval_seconds=3_600,
            repeat_start_at=NOW - timedelta(hours=2),
            created_at=NOW - timedelta(hours=3),
        )

        visible = self.store.list_visible(NOW)
        self.assertEqual([task.occurrence_at for task in visible], [
            NOW - timedelta(hours=2),
            NOW - timedelta(hours=1),
            NOW,
        ])
        self.assertTrue(all(task.id == series.id and task.is_repeating for task in visible))

        self.store.complete_task(series.id, NOW, occurrence_at=visible[1].occurrence_at)
        remaining = self.store.list_visible(NOW)
        self.assertEqual([task.occurrence_at for task in remaining], [NOW - timedelta(hours=2), NOW])

    def test_editing_or_deleting_a_repeating_occurrence_changes_the_whole_series(self) -> None:
        series = self.store.create_task(
            "Old title",
            repeat_interval_seconds=60,
            repeat_start_at=NOW - timedelta(minutes=1),
            created_at=NOW - timedelta(minutes=2),
        )
        occurrence = self.store.list_visible(NOW)[0]
        self.store.update_task(
            occurrence.id,
            "New title",
            "Series notes",
            NOW - timedelta(minutes=1),
            repeat_interval_seconds=60,
            repeat_start_at=NOW - timedelta(minutes=1),
        )

        self.assertEqual({task.title for task in self.store.list_visible(NOW)}, {"New title"})
        self.assertEqual({task.notes for task in self.store.list_visible(NOW)}, {"Series notes"})
        self.store.delete_task(series.id, NOW)
        self.assertEqual(self.store.list_visible(NOW + timedelta(days=1)), [])

    def test_repeating_series_contributes_its_next_occurrence_to_refresh_schedule(self) -> None:
        self.store.create_task(
            "Future series",
            repeat_interval_seconds=3_600,
            repeat_start_at=NOW - timedelta(minutes=30),
            created_at=NOW,
        )

        self.assertEqual(self.store.next_deferred_at(NOW), NOW + timedelta(minutes=30))

    def test_repeating_task_requires_positive_interval_and_start_time(self) -> None:
        with self.assertRaises(ValueError):
            self.store.create_task("Invalid", repeat_interval_seconds=60)
        with self.assertRaises(ValueError):
            self.store.create_task("Invalid", repeat_interval_seconds=0, repeat_start_at=NOW)

    def test_subtasks_are_nested_and_hidden_with_their_parent(self) -> None:
        parent = self.store.create_task("Parent", created_at=NOW - timedelta(minutes=3))
        child = self.store.create_task("Child", parent_id=parent.id, created_at=NOW - timedelta(minutes=2))
        grandchild = self.store.create_task("Grandchild", parent_id=child.id, created_at=NOW - timedelta(minutes=1))

        visible = self.store.list_visible(NOW)
        self.assertEqual([task.title for task in visible], ["Parent", "Child", "Grandchild"])
        self.assertEqual([task.depth for task in visible], [0, 1, 2])

        self.store.defer_task(parent.id, NOW + timedelta(hours=1))
        self.assertEqual(self.store.list_visible(NOW), [])

    def test_parent_reports_hidden_direct_children_at_bottom_of_visible_branch(self) -> None:
        parent = self.store.create_task("Parent", created_at=NOW)
        shown = self.store.create_task("Shown", parent_id=parent.id, created_at=NOW)
        self.store.create_task("Later", parent_id=parent.id, defer_at=NOW + timedelta(hours=1), created_at=NOW)

        visible = self.store.list_visible(NOW)
        self.assertEqual([task.id for task in visible], [parent.id, shown.id])
        self.assertEqual(visible[0].hidden_child_count, 1)

    def test_parent_cannot_be_completed_or_deleted_before_its_subtasks(self) -> None:
        parent = self.store.create_task("Parent", created_at=NOW)
        child = self.store.create_task("Child", parent_id=parent.id, created_at=NOW)

        with self.assertRaisesRegex(ValueError, "subtasks"):
            self.store.complete_task(parent.id, NOW)
        with self.assertRaisesRegex(ValueError, "subtasks"):
            self.store.delete_task(parent.id, NOW)

        self.store.complete_task(child.id, NOW)
        self.store.complete_task(parent.id, NOW)
        self.assertIsNotNone(self.store.get_task(parent.id).completed_at)

    def test_subtask_relationships_reject_repeating_parents_children_and_cycles(self) -> None:
        parent = self.store.create_task("Parent", created_at=NOW)
        child = self.store.create_task("Child", parent_id=parent.id, created_at=NOW)
        repeating = self.store.create_task(
            "Repeating",
            repeat_interval_seconds=60,
            repeat_start_at=NOW,
            created_at=NOW,
        )

        with self.assertRaises(ValueError):
            self.store.create_task("Repeated child", parent_id=parent.id, repeat_interval_seconds=60, repeat_start_at=NOW)
        with self.assertRaises(ValueError):
            self.store.create_task("Child of series", parent_id=repeating.id)
        with self.assertRaises(ValueError):
            self.store.update_task(parent.id, "Parent", "", NOW, parent_id=child.id)
        with self.assertRaises(ValueError):
            self.store.update_task(
                parent.id,
                "Parent",
                "",
                NOW,
                repeat_interval_seconds=60,
                repeat_start_at=NOW,
            )

    def test_predecessor_hides_successor_until_predecessor_is_closed(self) -> None:
        first = self.store.create_task("First", created_at=NOW)
        second = self.store.create_task("Second", predecessor_id=first.id, created_at=NOW)

        self.assertEqual([task.id for task in self.store.list_visible(NOW)], [first.id])
        self.store.complete_task(first.id, NOW)
        self.assertEqual([task.id for task in self.store.list_visible(NOW)], [second.id])

    def test_predecessor_relationships_cannot_cycle_or_depend_on_parent_successor(self) -> None:
        parent = self.store.create_task("Parent", created_at=NOW)
        child = self.store.create_task("Child", parent_id=parent.id, created_at=NOW)
        other = self.store.create_task("Other", predecessor_id=parent.id, created_at=NOW)
        successor = self.store.create_task("Successor", predecessor_id=child.id, created_at=NOW)

        with self.assertRaises(ValueError):
            self.store.update_task(child.id, "Child", "", NOW, parent_id=parent.id, predecessor_id=successor.id)
        with self.assertRaises(ValueError):
            self.store.update_task(child.id, "Child", "", NOW, parent_id=parent.id, predecessor_id=other.id)

    def test_closed_tasks_cannot_be_selected_as_predecessors(self) -> None:
        completed = self.store.create_task("Completed", created_at=NOW)
        deleted = self.store.create_task("Deleted", created_at=NOW)
        target = self.store.create_task("Target", created_at=NOW)
        self.store.complete_task(completed.id, NOW)
        self.store.delete_task(deleted.id, NOW)

        with self.assertRaisesRegex(ValueError, "predecessor must be active"):
            self.store.update_task(target.id, "Target", "", NOW, predecessor_id=completed.id)
        with self.assertRaisesRegex(ValueError, "predecessor must be active"):
            self.store.update_task(target.id, "Target", "", NOW, predecessor_id=deleted.id)
        self.assertNotIn(completed.id, [task.id for task in self.store.list_predecessor_candidates()])
        self.assertNotIn(deleted.id, [task.id for task in self.store.list_predecessor_candidates()])

    def test_undo_and_redo_restore_task_and_repeating_occurrence_changes(self) -> None:
        task = self.store.create_task("Undo me", created_at=NOW)
        self.store.complete_task(task.id, NOW)
        self.assertEqual(self.store.list_visible(NOW), [])

        self.assertTrue(self.store.undo())
        self.assertEqual([item.id for item in self.store.list_visible(NOW)], [task.id])
        self.assertTrue(self.store.redo())
        self.assertEqual(self.store.list_visible(NOW), [])

        series = self.store.create_task("Series", repeat_interval_seconds=60, repeat_start_at=NOW, created_at=NOW)
        self.store.complete_task(series.id, NOW, occurrence_at=NOW)
        self.assertEqual([item.title for item in self.store.list_visible(NOW)], [])
        self.assertTrue(self.store.undo())
        self.assertEqual([item.title for item in self.store.list_visible(NOW)], ["Series"])

    def test_view_options_support_as_of_successors_and_recently_closed(self) -> None:
        first = self.store.create_task("First", created_at=NOW)
        successor = self.store.create_task("Successor", predecessor_id=first.id, created_at=NOW)
        closed = self.store.create_task("Closed", created_at=NOW)
        self.store.complete_task(closed.id, NOW + timedelta(minutes=5))

        self.assertEqual([item.title for item in self.store.list_visible(NOW)], ["First", "Closed"])
        self.assertEqual({item.title for item in self.store.list_visible(NOW, show_successors=True)}, {"First", "Successor", "Closed"})
        recent = self.store.list_visible(NOW + timedelta(minutes=10), recent_closed_since=NOW)
        self.assertEqual([item.title for item in recent if not item.is_active], ["Closed"])

    def test_due_dates_block_deferring_task_parent_or_predecessor_past_deadline(self) -> None:
        own_due = self.store.create_task("Own due", due_at=NOW + timedelta(hours=1), created_at=NOW)
        with self.assertRaisesRegex(ValueError, "due date"):
            self.store.defer_task(own_due.id, NOW + timedelta(hours=1))

        parent = self.store.create_task("Parent", created_at=NOW)
        self.store.create_task("Child due", parent_id=parent.id, due_at=NOW + timedelta(hours=1), created_at=NOW)
        with self.assertRaisesRegex(ValueError, "due date"):
            self.store.defer_task(parent.id, NOW + timedelta(hours=1))

        predecessor = self.store.create_task("Predecessor", created_at=NOW)
        self.store.create_task("Successor due", predecessor_id=predecessor.id, due_at=NOW + timedelta(hours=1), created_at=NOW)
        with self.assertRaisesRegex(ValueError, "due date"):
            self.store.defer_task(predecessor.id, NOW + timedelta(hours=1))


if __name__ == "__main__":
    unittest.main()
