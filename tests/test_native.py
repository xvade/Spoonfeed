"""Offscreen smoke test for Spoonfeed's native Qt window."""

import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

# Must be selected before Qt creates its single QApplication instance.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from unittest.mock import patch

from spoonfeed.native import SpoonfeedWindow, next_local_midnight, previous_local_midnight
from spoonfeed.store import utc_now


class NativeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_window_shows_visible_task_rows(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.store.create_task("Native task")
            window.refresh()

            self.assertEqual(window.windowTitle(), "Spoonfeed")
            self.assertEqual(window.task_layout.count(), 1)
            window.close()

    def test_window_arms_refresh_for_a_deferred_task(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.store.create_task("Later", defer_at=utc_now() + timedelta(minutes=1))
            window.refresh()

            self.assertTrue(window.refresh_timer.isActive())
            window.close()

    def test_default_view_tracks_now_instead_of_window_open_time(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            # A task created after the window's initial picker value must still
            # display while the default live-now view is active.
            window.as_of_input.setDateTime(window.as_of_input.dateTime().addSecs(-60))
            window.viewing_now = True
            window.store.create_task("Created later", created_at=utc_now())
            window.refresh()

            self.assertEqual(window.task_layout.count(), 1)
            window.close()

    def test_defer_actions_use_the_fixed_view_as_of_time(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.viewing_now = False
            window.as_of_input.setDateTime(QDateTime(2025, 2, 3, 14, 30, 0))
            view_time = window._view_as_of_time()

            hourly = window.store.create_task("One hour")
            window.defer_task(hourly)
            self.assertEqual(window.store.get_task(hourly.id).defer_at, view_time + timedelta(hours=1))

            midnight = window.store.create_task("Next midnight")
            window.shift_held = True
            window.defer_task(midnight)
            self.assertEqual(window.store.get_task(midnight.id).defer_at, next_local_midnight(view_time))
            window.close()

    def test_show_successors_marks_both_ends_of_a_dependency(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            first = window.store.create_task("First")
            window.store.create_task("Second", predecessor_id=first.id)

            window.show_successors_input.setChecked(True)
            indicators = [
                label.text()
                for label in window.task_container.findChildren(QLabel, "dependency-indicator")
            ]

            self.assertIn("after: First", indicators)
            self.assertIn("unlocks: Second", indicators)
            window.close()

    def test_show_successors_marks_repeating_occurrences_as_a_chain(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            now = utc_now()
            window.store.create_task(
                "Recurring",
                repeat_interval_seconds=3_600,
                repeat_start_at=now - timedelta(hours=2),
                created_at=now - timedelta(hours=3),
            )

            window.show_successors_input.setChecked(True)
            indicators = [
                label.text()
                for label in window.task_container.findChildren(QLabel, "dependency-indicator")
            ]

            self.assertTrue(any(text.startswith("after: previous occurrence") for text in indicators))
            window.close()

    def test_relationship_dropdown_candidates_are_limited_to_currently_visible_tasks(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            visible = window.store.create_task("Visible")
            hidden = window.store.create_task("Deferred", defer_at=utc_now() + timedelta(hours=1))
            window.store.create_task("Blocked", predecessor_id=visible.id)

            visible_ids = window._visible_relationship_task_ids()
            parent_ids = {task.id for task in window.store.list_parent_candidates() if task.id in visible_ids}
            predecessor_ids = {task.id for task in window.store.list_predecessor_candidates() if task.id in visible_ids}

            self.assertEqual(parent_ids, {visible.id})
            self.assertEqual(predecessor_ids, {visible.id})
            self.assertNotIn(hidden.id, visible_ids)
            window.close()

    def test_completed_history_window_defaults_to_previous_midnight_and_excludes_deleted(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            completed = window.store.create_task("Checked off")
            deleted = window.store.create_task("Deleted")
            window.store.complete_task(completed.id)
            window.store.delete_task(deleted.id)

            window.open_completed_history()
            history = window.completed_history_window

            self.assertIsNotNone(history)
            self.assertEqual(
                history.since_input.dateTime().toSecsSinceEpoch(),  # type: ignore[union-attr]
                int(previous_local_midnight().timestamp()),
            )
            labels = [label.text() for label in history.task_container.findChildren(QLabel)]  # type: ignore[union-attr]
            self.assertIn("Checked off", labels)
            self.assertNotIn("Deleted", labels)
            history.close()  # type: ignore[union-attr]
            window.close()

    def test_t_hotkey_opens_completed_history(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.show()
            calls: list[str] = []
            window.open_completed_history = lambda: calls.append("opened")  # type: ignore[method-assign]

            QTest.keyClick(window, Qt.Key.Key_T)
            self.application.processEvents()

            self.assertEqual(calls, ["opened"])
            window.close()

    def test_escape_closes_completed_history_window(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.open_completed_history()
            history = window.completed_history_window
            self.assertIsNotNone(history)

            QTest.keyClick(history, Qt.Key.Key_Escape)  # type: ignore[arg-type]
            self.application.processEvents()

            self.assertIsNone(window.completed_history_window)
            window.close()

    def test_calming_image_offer_expires_after_one_minute_and_is_once(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            window.last_check_off_at = utc_now() - timedelta(seconds=59)
            self.assertTrue(window._can_offer_completed_image())

            window.image_prompt_used = True
            self.assertFalse(window._can_offer_completed_image())
            window.image_prompt_used = False
            window.last_check_off_at = utc_now() - timedelta(minutes=2)
            self.assertFalse(window._can_offer_completed_image())
            window.close()

    def test_calming_image_shortcut_works_after_checkoff_with_picker_focus(self) -> None:
        with TemporaryDirectory() as directory:
            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            task = window.store.create_task("Completed task")
            window.show()
            window.close_task(task)
            calls: list[str] = []
            # The app-level key handler looks up this method when activated, so
            # this verifies dispatch without opening a real modal dialog.
            window.offer_completed_image = lambda: calls.append("offered")  # type: ignore[method-assign]
            window.as_of_input.setFocus()

            QTest.keyClick(window.as_of_input, Qt.Key.Key_D)
            self.application.processEvents()

            self.assertEqual(calls, ["offered"])
            window.close()

    def test_dismissed_image_does_not_block_the_next_completion_offer(self) -> None:
        """Regression test for the two-checkoff image flow described by the user."""
        with TemporaryDirectory() as directory:
            image_directory = Path(directory) / ".images"
            image_directory.mkdir()
            image_path = image_directory / "calm.png"
            image = QPixmap(2, 2)
            image.fill(Qt.GlobalColor.blue)
            self.assertTrue(image.save(str(image_path)))

            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            with (
                patch("spoonfeed.native.CALMING_IMAGE_DIRECTORY", image_directory),
                patch("spoonfeed.native.random.random", return_value=0.0),
            ):
                window.show_random_calming_image()
            viewer = window.calming_image_window
            self.assertIsNotNone(viewer)
            viewer.close()  # type: ignore[union-attr]
            self.application.processEvents()
            self.assertIsNone(window.calming_image_window)

            # A fresh check-off must restore the normal D prompt eligibility.
            window.last_check_off_at = utc_now()
            window.image_prompt_used = False
            calls: list[str] = []
            window.offer_completed_image = lambda: calls.append("offered")  # type: ignore[method-assign]
            window.as_of_input.setFocus()
            QTest.keyClick(window.as_of_input, Qt.Key.Key_D)
            self.application.processEvents()
            self.assertEqual(calls, ["offered"])
            window.close()

    def test_calming_image_display_is_skipped_outside_the_twenty_percent_roll(self) -> None:
        with TemporaryDirectory() as directory:
            image_directory = Path(directory) / ".images"
            image_directory.mkdir()
            image = QPixmap(2, 2)
            image.fill(Qt.GlobalColor.blue)
            self.assertTrue(image.save(str(image_directory / "calm.png")))

            window = SpoonfeedWindow(Path(directory) / "tasks.db")
            with (
                patch("spoonfeed.native.CALMING_IMAGE_DIRECTORY", image_directory),
                patch("spoonfeed.native.random.random", return_value=0.2),
            ):
                window.show_random_calming_image()

            self.assertIsNone(window.calming_image_window)
            window.close()


if __name__ == "__main__":
    unittest.main()
