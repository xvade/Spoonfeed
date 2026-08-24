"""Native Qt desktop interface for Spoonfeed's core task workflow.

This module owns presentation and user input only. All persistence and task
state rules remain in ``spoonfeed.store.TaskStore`` so later features can be
implemented without coupling them to Qt widgets.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
import math
from pathlib import Path
import random
import sys
from typing import Callable, Optional

from PySide6.QtCore import QDateTime, QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .store import Task, TaskStore, utc_now


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_OFF_SOUND_PATH = PROJECT_ROOT / "hero.m4a"
CALMING_IMAGE_DIRECTORY = PROJECT_ROOT / ".images"
SUPPORTED_IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def local_timezone() -> tzinfo:
    """Return the current system timezone used by Qt's native datetime editor."""
    return datetime.now().astimezone().tzinfo or timezone.utc


def next_local_midnight() -> datetime:
    """Calculate the next local midnight, then normalize it for SQLite storage."""
    now = datetime.now().astimezone()
    tomorrow = (now + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time(), now.tzinfo).astimezone(timezone.utc)


class TaskDialog(QDialog):
    """The shared native create/edit dialog for the properties implemented today."""

    def __init__(
        self,
        parent: QWidget,
        task: Optional[Task] = None,
        parent_choices: Optional[list[Task]] = None,
        predecessor_choices: Optional[list[Task]] = None,
        selected_parent_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New task" if task is None else "Edit task")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Task name"))
        self.title_input = QLineEdit(task.title if task else "")
        self.title_input.setPlaceholderText("What needs doing?")
        self.title_input.returnPressed.connect(self.accept)
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Notes (optional)"))
        self.notes_input = QTextEdit(task.notes if task else "")
        self.notes_input.setMinimumHeight(120)
        layout.addWidget(self.notes_input)

        self.defer_label = QLabel("Show after (local time)")
        layout.addWidget(self.defer_label)
        self.defer_input = QDateTimeEdit()
        self.defer_input.setCalendarPopup(True)
        self.defer_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        initial = task.defer_at if task else utc_now()
        # QDateTime presents this instant in the system's local time zone.
        self.defer_input.setDateTime(QDateTime.fromSecsSinceEpoch(int(initial.timestamp())))
        layout.addWidget(self.defer_input)

        self.repeat_checkbox = QCheckBox("Repeat task")
        self.repeat_checkbox.toggled.connect(self._toggle_repeat_fields)
        layout.addWidget(self.repeat_checkbox)
        self.repeat_fields = QWidget()
        repeat_layout = QVBoxLayout(self.repeat_fields)
        repeat_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Repeat every"))
        self.repeat_interval = QSpinBox()
        self.repeat_interval.setRange(1, 1_000_000)
        self.repeat_interval.setValue(1)
        interval_layout.addWidget(self.repeat_interval)
        self.repeat_unit = QComboBox()
        self.repeat_unit.addItem("seconds", 1)
        self.repeat_unit.addItem("minutes", 60)
        self.repeat_unit.addItem("hours", 3_600)
        self.repeat_unit.addItem("days", 86_400)
        self.repeat_unit.setCurrentIndex(2)
        interval_layout.addWidget(self.repeat_unit)
        interval_layout.addStretch()
        repeat_layout.addLayout(interval_layout)
        repeat_layout.addWidget(QLabel("Repeat start (local time)"))
        self.repeat_start_input = QDateTimeEdit()
        self.repeat_start_input.setCalendarPopup(True)
        self.repeat_start_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.repeat_start_input.setDateTime(QDateTime.fromSecsSinceEpoch(int(initial.timestamp())))
        repeat_layout.addWidget(self.repeat_start_input)
        layout.addWidget(self.repeat_fields)

        layout.addWidget(QLabel("Parent task (optional)"))
        self.parent_input = QComboBox()
        self.parent_input.addItem("No parent", None)
        for candidate in parent_choices or []:
            self.parent_input.addItem(candidate.title, candidate.id)
        wanted_parent = task.parent_id if task is not None else selected_parent_id
        if wanted_parent is not None:
            for index in range(self.parent_input.count()):
                if self.parent_input.itemData(index) == wanted_parent:
                    self.parent_input.setCurrentIndex(index)
                    break
        self.parent_input.currentIndexChanged.connect(self._parent_changed)
        layout.addWidget(self.parent_input)

        layout.addWidget(QLabel("Predecessor task (optional)"))
        self.predecessor_input = QComboBox()
        self.predecessor_input.addItem("No predecessor", None)
        for candidate in predecessor_choices or []:
            self.predecessor_input.addItem(candidate.title, candidate.id)
        if task is not None and task.predecessor_id is not None:
            for index in range(self.predecessor_input.count()):
                if self.predecessor_input.itemData(index) == task.predecessor_id:
                    self.predecessor_input.setCurrentIndex(index)
                    break
        layout.addWidget(self.predecessor_input)

        self.due_checkbox = QCheckBox("Set due date")
        self.due_checkbox.toggled.connect(lambda enabled: self.due_input.setVisible(enabled))
        layout.addWidget(self.due_checkbox)
        self.due_input = QDateTimeEdit()
        self.due_input.setCalendarPopup(True)
        self.due_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        due_initial = task.due_at if task is not None and task.due_at is not None else utc_now() + timedelta(days=1)
        self.due_input.setDateTime(QDateTime.fromSecsSinceEpoch(int(due_initial.timestamp())))
        self.due_checkbox.setChecked(task is not None and task.due_at is not None)
        self.due_input.setVisible(self.due_checkbox.isChecked())
        layout.addWidget(self.due_input)

        if task is not None and task.is_repeating:
            self.repeat_checkbox.setChecked(True)
            self._set_repeat_interval(task.repeat_interval_seconds or 1)
            start = task.repeat_start_at or task.defer_at
            self.repeat_start_input.setDateTime(QDateTime.fromSecsSinceEpoch(int(start.timestamp())))
        self._toggle_repeat_fields(self.repeat_checkbox.isChecked())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.title_input.setFocus()

    def accept(self) -> None:
        """Keep the native dialog open until it has a task name."""
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Could not save task", "A task needs a name")
            return
        super().accept()

    def _set_repeat_interval(self, seconds: int) -> None:
        """Present an existing interval using the largest exact UI unit."""
        for index, unit_seconds in reversed(list(enumerate((1, 60, 3_600, 86_400)))):
            if seconds % unit_seconds == 0:
                self.repeat_unit.setCurrentIndex(index)
                self.repeat_interval.setValue(seconds // unit_seconds)
                return

    def _toggle_repeat_fields(self, repeating: bool) -> None:
        """A repeating task has a start time instead of a one-off defer time."""
        self.defer_label.setVisible(not repeating)
        self.defer_input.setVisible(not repeating)
        self.repeat_fields.setVisible(repeating)
        self.parent_input.setEnabled(not repeating)
        if repeating and self.parent_input.currentData() is not None:
            self.parent_input.setCurrentIndex(0)

    def _parent_changed(self, _index: int) -> None:
        """Selecting a parent turns a task into a non-repeating child."""
        if self.parent_input.currentData() is not None and self.repeat_checkbox.isChecked():
            self.repeat_checkbox.setChecked(False)

    @staticmethod
    def _utc_value(editor: QDateTimeEdit) -> datetime:
        """Read a native local-time editor and normalize it for TaskStore."""
        selected = editor.dateTime().toPython()
        if selected.tzinfo is None:
            selected = selected.replace(tzinfo=local_timezone())
        return selected.astimezone(timezone.utc)

    def values(self) -> tuple[str, str, datetime, Optional[int], Optional[datetime], Optional[int], Optional[int], Optional[datetime]]:
        """Return one-off or repeating schedule values in TaskStore's UTC format."""
        if self.repeat_checkbox.isChecked():
            start = self._utc_value(self.repeat_start_input)
            interval_seconds = self.repeat_interval.value() * self.repeat_unit.currentData()
            return self.title_input.text(), self.notes_input.toPlainText(), start, interval_seconds, start, None, self.predecessor_input.currentData(), self._utc_value(self.due_input) if self.due_checkbox.isChecked() else None
        return (
            self.title_input.text(),
            self.notes_input.toPlainText(),
            self._utc_value(self.defer_input),
            None,
            None,
            self.parent_input.currentData(),
            self.predecessor_input.currentData(),
            self._utc_value(self.due_input) if self.due_checkbox.isChecked() else None,
        )


class TaskRow(QFrame):
    """A visible task with native per-task actions and double-click editing."""

    def __init__(
        self,
        task: Task,
        shift_held: bool,
        on_edit: Callable[[Task], None],
        on_close: Callable[[Task], None],
        on_defer: Callable[[Task], None],
        on_add_subtask: Callable[[Task], None],
    ) -> None:
        super().__init__()
        self.task = task
        self.on_edit = on_edit
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10 + task.depth * 24, 8, 10, 8)

        title = QLabel(task.title)
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        title.installEventFilter(self)
        layout.addWidget(title, 1)
        if task.is_repeating and task.occurrence_at is not None:
            occurrence = task.occurrence_at.astimezone().strftime("%Y-%m-%d %H:%M")
            schedule = QLabel(f"repeats · {occurrence}")
            schedule.setStyleSheet("color: palette(mid);")
            schedule.setToolTip("This is one occurrence of a repeating task")
            schedule.installEventFilter(self)
            layout.addWidget(schedule)
        if task.notes:
            notes = QLabel("notes")
            notes.setToolTip(task.notes)
            # Notes are useful task metadata, so make their indicator easier to spot.
            notes.setStyleSheet("color: #5f7184;")
            notes.installEventFilter(self)
            layout.addWidget(notes)

        if not task.is_active:
            status = QLabel("completed" if task.completed_at is not None else "deleted")
            status.setStyleSheet("color: #9aa0a6;")
            layout.addWidget(status)
            return

        close = QPushButton("Delete" if shift_held else "Complete")
        close.clicked.connect(lambda: on_close(task))
        layout.addWidget(close)
        if task.is_repeating:
            defer_label = "Move series to midnight" if shift_held else "Move series +1 hour"
        else:
            defer_label = "Next midnight" if shift_held else "+1 hour"
        defer = QPushButton(defer_label)
        defer.clicked.connect(lambda: on_defer(task))
        layout.addWidget(defer)
        if not task.is_repeating:
            add_subtask = QPushButton("Add subtask")
            add_subtask.clicked.connect(lambda: on_add_subtask(task))
            layout.addWidget(add_subtask)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self.on_edit(self.task)
            return True
        return super().eventFilter(watched, event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.on_edit(self.task)
        event.accept()


class CalmingImageWindow(QWidget):
    """A transient image viewer that closes on any keypress."""

    # QWidget.close() normally hides a top-level window instead of destroying
    # it, so the main window needs an explicit lifecycle notification.
    image_closed = Signal()

    def __init__(self, image_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("A moment for yourself")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        image = QPixmap(str(image_path))
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        screen = QApplication.primaryScreen().availableGeometry()
        label.setPixmap(image.scaled(
            int(screen.width() * 0.8),
            int(screen.height() * 0.8),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        self.resize(label.pixmap().size())
        # An image is a brief reset, not a modal screen that can be forgotten.
        QTimer.singleShot(60_000, self.close)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.close()
        event.accept()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Tell Spoonfeed it can offer an image after the viewer is dismissed."""
        self.image_closed.emit()
        super().closeEvent(event)


class SpoonfeedWindow(QMainWindow):
    """Main native window showing active, non-deferred tasks oldest first."""

    def __init__(self, database_path: str | Path = "spoonfeed.db") -> None:
        super().__init__()
        self.store = TaskStore(database_path)
        self.shift_held = False
        self.last_check_off_at: Optional[datetime] = None
        self.image_prompt_used = False
        self.calming_image_window: Optional[CalmingImageWindow] = None
        self._setup_check_off_sound()
        # The initial view tracks the clock; the picker becomes a fixed as-of
        # view only after the user intentionally changes it.
        self.viewing_now = True
        self.setWindowTitle("Spoonfeed")
        self.setMinimumSize(720, 360)
        self._build_layout()
        QApplication.instance().installEventFilter(self)  # type: ignore[union-attr]
        self.refresh_timer = QTimer(self)
        # Refresh exactly when the next deferred task becomes eligible rather
        # than on a polling cadence that can leave it hidden for nearly a minute.
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh()

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        header = QHBoxLayout()
        heading = QLabel("Spoonfeed")
        heading_font = heading.font()
        heading_font.setPointSize(18)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        header.addWidget(heading)
        header.addStretch()
        new_task = QPushButton("New task (N)")
        new_task.clicked.connect(lambda: self.open_create())
        header.addWidget(new_task)
        layout.addLayout(header)
        layout.addWidget(QLabel("Double-click a task to edit. Hold Shift for Delete and Next midnight actions."))

        view_bar = QHBoxLayout()
        view_bar.addWidget(QLabel("View as of"))
        self.as_of_input = QDateTimeEdit()
        self.as_of_input.setCalendarPopup(True)
        self.as_of_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.as_of_input.setDateTime(QDateTime.currentDateTime())
        self.as_of_input.dateTimeChanged.connect(self._set_custom_as_of_view)
        view_bar.addWidget(self.as_of_input)
        now_button = QPushButton("Now")
        now_button.clicked.connect(self.use_current_time_view)
        view_bar.addWidget(now_button)
        self.show_successors_input = QCheckBox("Show successor tasks")
        self.show_successors_input.toggled.connect(lambda _value: self.refresh())
        view_bar.addWidget(self.show_successors_input)
        self.show_recent_input = QCheckBox("Show recently closed since")
        self.show_recent_input.toggled.connect(lambda _value: self.refresh())
        view_bar.addWidget(self.show_recent_input)
        self.recent_since_input = QDateTimeEdit()
        self.recent_since_input.setCalendarPopup(True)
        self.recent_since_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.recent_since_input.setDateTime(QDateTime.currentDateTime().addDays(-1))
        self.recent_since_input.dateTimeChanged.connect(lambda _value: self.refresh())
        view_bar.addWidget(self.recent_since_input)
        view_bar.addStretch()
        layout.addLayout(view_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.task_container)
        layout.addWidget(scroll, 1)

    def _setup_check_off_sound(self) -> None:
        """Prepare the optional check-off audio once for low-latency playback."""
        self.check_off_sound_path = CHECK_OFF_SOUND_PATH
        self.check_off_player: Optional[QMediaPlayer] = None
        if not self.check_off_sound_path.is_file():
            return
        self.check_off_audio = QAudioOutput(self)
        self.check_off_audio.setVolume(1.0)
        self.check_off_player = QMediaPlayer(self)
        self.check_off_player.setAudioOutput(self.check_off_audio)
        self.check_off_player.setSource(QUrl.fromLocalFile(str(self.check_off_sound_path)))

    def play_check_off_sound(self) -> None:
        """Play ``hero.m4a`` after a successful completion, restarting if needed."""
        if self.check_off_player is None:
            return
        self.check_off_player.setPosition(0)
        self.check_off_player.play()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Provide app-wide N, D, and Shift behavior without stealing text input."""
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            modifiers = event.modifiers()
            has_command = bool(modifiers & (Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ControlModifier))
            if event.key() == Qt.Key.Key_Z and has_command and QApplication.activeModalWidget() is None:
                changed = self.store.redo() if modifiers & Qt.KeyboardModifier.ShiftModifier else self.store.undo()
                if changed:
                    self.refresh()
                return True
            if event.key() == Qt.Key.Key_D and self._can_handle_global_key() and self._can_offer_completed_image():
                self.offer_completed_image()
                return True
            if event.key() == Qt.Key.Key_Shift and not self.shift_held:
                self.shift_held = True
                self.refresh()
            elif event.key() == Qt.Key.Key_N and self._can_open_new_task():
                self.open_create()
                return True
        elif event.type() == QEvent.Type.KeyRelease and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Shift and self.shift_held:
                self.shift_held = False
                self.refresh()
        return super().eventFilter(watched, event)

    def _can_open_new_task(self) -> bool:
        focus = QApplication.focusWidget()
        return not isinstance(focus, (QLineEdit, QTextEdit, QDateTimeEdit)) and QApplication.activeModalWidget() is None

    def _can_handle_global_key(self) -> bool:
        """Allow D unless a dialog or the image window currently owns input.

        Date editors can retain focus after a row refresh, so this completion
        action must not be restricted to a particular focused child widget.
        """
        return QApplication.activeModalWidget() is None and self.calming_image_window is None

    def _can_offer_completed_image(self) -> bool:
        """The D flow is available once during the minute after a check-off."""
        return (
            self.last_check_off_at is not None
            and not self.image_prompt_used
            and utc_now() - self.last_check_off_at <= timedelta(minutes=1)
        )

    def offer_completed_image(self) -> None:
        """Ask once whether to display a random calming image after completion."""
        if not self._can_offer_completed_image():
            return
        # Pressing D consumes this completion's offer even if the user cancels.
        self.image_prompt_used = True
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Display image?")
        prompt.setText("Display a calming image?")
        confirm = prompt.addButton("Confirm", QMessageBox.ButtonRole.AcceptRole)
        prompt.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        prompt.setDefaultButton(confirm)
        prompt.exec()
        if prompt.clickedButton() is confirm:
            self.show_random_calming_image()

    def show_random_calming_image(self) -> None:
        """Open a randomly selected usable image from the ignored .images folder."""
        if not CALMING_IMAGE_DIRECTORY.is_dir():
            QMessageBox.information(self, "No images found", "Add images to .images to use this feature.")
            return
        candidates = [
            path for path in CALMING_IMAGE_DIRECTORY.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ]
        random.shuffle(candidates)
        for image_path in candidates:
            if not QPixmap(str(image_path)).isNull():
                self.calming_image_window = CalmingImageWindow(image_path)
                self.calming_image_window.image_closed.connect(self._clear_calming_image_window)
                self.calming_image_window.show()
                self.calming_image_window.activateWindow()
                self.calming_image_window.setFocus()
                return
        QMessageBox.information(self, "No images found", "No supported image files were found in .images.")

    def _clear_calming_image_window(self) -> None:
        """Clear a hidden viewer so the next completion can offer another image."""
        self.calming_image_window = None

    def _set_custom_as_of_view(self, _value: QDateTime) -> None:
        """Treat a picker edit as an explicit past/future view choice."""
        self.viewing_now = False
        self.refresh()

    def use_current_time_view(self) -> None:
        """Return from a fixed as-of view to the live current-time task list."""
        self.viewing_now = True
        self.as_of_input.blockSignals(True)
        self.as_of_input.setDateTime(QDateTime.currentDateTime())
        self.as_of_input.blockSignals(False)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the list so every action reflects the current SQLite state."""
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        point_in_time = utc_now() if self.viewing_now else TaskDialog._utc_value(self.as_of_input)
        recent_since = TaskDialog._utc_value(self.recent_since_input) if self.show_recent_input.isChecked() else None
        tasks = self.store.list_visible(
            point_in_time,
            show_successors=self.show_successors_input.isChecked(),
            recent_closed_since=recent_since,
        )
        if not tasks:
            empty = QLabel("Nothing to do right now.")
            # Keep the empty state present but visually quieter than task content.
            empty.setStyleSheet("color: #9aa0a6;")
            self.task_layout.addWidget(empty)
        else:
            for index, task in enumerate(tasks):
                self.task_layout.addWidget(
                    TaskRow(task, self.shift_held, self.open_edit, self.close_task, self.defer_task, self.open_create)
                )
                # A parent reports active children hidden by their own defer
                # rules after its visible child block, as requested in PROMPT.
                next_depth = tasks[index + 1].depth if index + 1 < len(tasks) else -1
                if task.hidden_child_count and next_depth <= task.depth:
                    hidden = QLabel(f"{task.hidden_child_count} hidden subtask(s)")
                    hidden.setStyleSheet("color: #9aa0a6;")
                    hidden.setContentsMargins(34 + task.depth * 24, 0, 0, 4)
                    self.task_layout.addWidget(hidden)
        if abs((point_in_time - utc_now()).total_seconds()) < 60 and not self.show_recent_input.isChecked():
            self._schedule_next_refresh(point_in_time)
        else:
            self.refresh_timer.stop()

    def _schedule_next_refresh(self, point_in_time: datetime) -> None:
        """Wake the UI when the earliest currently deferred task becomes visible."""
        next_defer_at = self.store.next_deferred_at(point_in_time)
        if next_defer_at is None:
            self.refresh_timer.stop()
            return
        # Add a small cushion for event-loop scheduling and SQLite timestamp
        # precision, then cap the timer so a long defer remains interruptible.
        milliseconds = math.ceil((next_defer_at - point_in_time).total_seconds() * 1000) + 50
        self.refresh_timer.start(max(1_000, min(milliseconds, 21_600_000)))

    def open_create(self, parent_task: Optional[Task] = None) -> None:
        dialog = TaskDialog(
            self,
            parent_choices=self.store.list_parent_candidates(),
            predecessor_choices=self.store.list_predecessor_candidates(),
            selected_parent_id=parent_task.id if parent_task is not None else None,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                title, notes, defer_at, interval_seconds, repeat_start_at, parent_id, predecessor_id, due_at = dialog.values()
                self.store.create_task(
                    title,
                    notes,
                    defer_at,
                    repeat_interval_seconds=interval_seconds,
                    repeat_start_at=repeat_start_at,
                    parent_id=parent_id,
                    predecessor_id=predecessor_id,
                    due_at=due_at,
                )
            except ValueError as error:
                QMessageBox.warning(self, "Could not save task", str(error))
                return
            self.refresh()

    def open_edit(self, task: Task) -> None:
        dialog = TaskDialog(
            self,
            task,
            parent_choices=self.store.list_parent_candidates(task.id),
            predecessor_choices=self.store.list_predecessor_candidates(task.id),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                title, notes, defer_at, interval_seconds, repeat_start_at, parent_id, predecessor_id, due_at = dialog.values()
                # Updating any virtual occurrence writes the shared series row,
                # so every occurrence reflects the edited title and schedule.
                self.store.update_task(
                    task.id,
                    title,
                    notes,
                    defer_at,
                    repeat_interval_seconds=interval_seconds,
                    repeat_start_at=repeat_start_at,
                    parent_id=parent_id,
                    predecessor_id=predecessor_id,
                    due_at=due_at,
                )
            except ValueError as error:
                QMessageBox.warning(self, "Could not save task", str(error))
                return
            self.refresh()

    def close_task(self, task: Task) -> None:
        if self.shift_held:
            self.store.delete_task(task.id)
        else:
            self.store.complete_task(task.id, occurrence_at=task.occurrence_at)
            self.play_check_off_sound()
            self.last_check_off_at = utc_now()
            self.image_prompt_used = False
        self.refresh()

    def defer_task(self, task: Task) -> None:
        target = next_local_midnight() if self.shift_held else utc_now() + timedelta(hours=1)
        self.store.defer_task(task.id, target)
        self.refresh()

    def closeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt naming convention)
        self.store.close()
        super().closeEvent(event)


def run(database_path: str | Path = "spoonfeed.db") -> int:
    """Start Spoonfeed's native event loop and return its exit status."""
    application = QApplication(sys.argv)
    application.setApplicationName("Spoonfeed")
    window = SpoonfeedWindow(database_path)
    window.show()
    return application.exec()
