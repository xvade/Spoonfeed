"""Offscreen smoke test for Spoonfeed's native Qt window."""

import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

# Must be selected before Qt creates its single QApplication instance.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from unittest.mock import patch

from spoonfeed.native import SpoonfeedWindow
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
            with patch("spoonfeed.native.CALMING_IMAGE_DIRECTORY", image_directory):
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


if __name__ == "__main__":
    unittest.main()
