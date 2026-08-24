"""Offscreen smoke test for Spoonfeed's native Qt window."""

import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

# Must be selected before Qt creates its single QApplication instance.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
