from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QInputDialog, QMessageBox, QProgressBar, QPushButton, QRadioButton, QSlider, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import __version__
from .media import PreviewManager, export_combined, export_individual, media_duration
from .models import ClipCandidate, TranscriptSegment
from .timecode import format_timecode, parse_timecode
from .transcription import Transcriber, save_transcript
from .updater import (
    download_update, extract_update, read_update_manifest, schedule_app_replacement,
    version_tuple,
)


class Worker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    status = Signal(str)
    finished = Signal()

    def __init__(self, fn: Callable) -> None:
        super().__init__()
        self.fn = fn

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self.fn(self.status.emit))
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mp3", ".m4a", ".wav", ".aac", ".flac"}

    def __init__(self) -> None:
        super().__init__()
        self.source_path: Path | None = None
        self.source_duration: float | None = None
        self.segments: list[TranscriptSegment] = []
        self.candidates: list[ClipCandidate] = []
        self.preview_manager = PreviewManager()
        self.transcriber = Transcriber()
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self._success_callback: Callable[[object], None] | None = None
        self._show_worker_errors = True
        self.settings = QSettings("Crestvale", "StreamClipAnalyzer")
        self.setWindowTitle(f"Stream Clip Analyzer v{__version__}")
        self.resize(1280, 850)
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menu()
        QTimer.singleShot(2500, self.auto_check_update)

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("ヘルプ")
        check = QAction("アップデートを確認", self)
        check.triggered.connect(lambda: self.check_for_updates(True))
        help_menu.addAction(check)
        update = QAction("更新ZIPからアップデート…", self)
        update.triggered.connect(self.update_from_zip)
        help_menu.addAction(update)
        update_url = QAction("更新URLを設定…", self)
        update_url.triggered.connect(self.set_update_url)
        help_menu.addAction(update_url)
        about = QAction("このアプリについて", self)
        about.triggered.connect(lambda: QMessageBox.information(self, "Stream Clip Analyzer", f"Stream Clip Analyzer v{__version__}"))
        help_menu.addAction(about)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        source_box = QGroupBox("1. 配信動画 / 音声")
        source_layout = QHBoxLayout(source_box)
        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        choose = QPushButton("ファイルを選択")
        choose.clicked.connect(self.choose_source)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(choose)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["base", "small", "medium", "large-v3"])
        self.model_combo.setCurrentText("small")
        self.suppress_check = QCheckBox("反復・幻覚抑制")
        self.suppress_check.setChecked(True)
        transcribe = QPushButton("文字起こし開始")
        transcribe.clicked.connect(self.start_transcription)
        source_layout.addWidget(QLabel("Whisper:"))
        source_layout.addWidget(self.model_combo)
        source_layout.addWidget(self.suppress_check)
        source_layout.addWidget(transcribe)
        layout.addWidget(source_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("2. 文字起こし（連続行を選択）"))
        self.transcript_table = QTableWidget(0, 4)
        self.transcript_table.setHorizontalHeaderLabels(["#", "開始", "終了", "文字起こし"])
        self.transcript_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.transcript_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.transcript_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.transcript_table)
        add = QPushButton("選択範囲を切り抜き候補に追加")
        add.clicked.connect(self.add_candidate)
        left_layout.addWidget(add)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("3. 切り抜き候補（確定済みだけ書き出します）"))
        self.candidate_table = QTableWidget(0, 6)
        self.candidate_table.setHorizontalHeaderLabels(["名前", "開始", "終了", "長さ", "縦9:16", "状態"])
        self.candidate_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidate_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.candidate_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.candidate_table.itemSelectionChanged.connect(self.load_candidate)
        self.candidate_table.itemChanged.connect(self.candidate_item_changed)
        right_layout.addWidget(self.candidate_table)
        row_buttons = QHBoxLayout()
        for text, handler in (("↑", self.move_up), ("↓", self.move_down), ("削除", self.remove_candidate)):
            button = QPushButton(text)
            button.clicked.connect(handler)
            row_buttons.addWidget(button)
        row_buttons.addStretch()
        right_layout.addLayout(row_buttons)

        preview_box = QGroupBox("4. プレビュー・微調整")
        preview_layout = QVBoxLayout(preview_box)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(260)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self._player_position)
        self.player.durationChanged.connect(lambda value: self.seek.setMaximum(max(0, value)))
        preview_layout.addWidget(self.video)
        playback = QHBoxLayout()
        self.play_button = QPushButton("▶ 再生")
        self.play_button.clicked.connect(self.toggle_play)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.position_label = QLabel("00:00:00 / 00:00:00")
        playback.addWidget(self.play_button)
        playback.addWidget(self.seek, 1)
        playback.addWidget(self.position_label)
        preview_layout.addLayout(playback)
        form = QFormLayout()
        self.start_edit, self.end_edit = QLineEdit(), QLineEdit()
        self.start_edit.editingFinished.connect(self.range_edited)
        self.end_edit.editingFinished.connect(self.range_edited)
        form.addRow("開始", self._adjust_row("start", self.start_edit))
        form.addRow("終了", self._adjust_row("end", self.end_edit))
        preview_layout.addLayout(form)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("プレビュー作成 / 再プレビュー")
        self.preview_button.clicked.connect(self.create_preview)
        self.confirm_button = QPushButton("✓ この範囲で確定")
        self.confirm_button.clicked.connect(self.confirm_candidate)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.confirm_button)
        preview_layout.addLayout(actions)
        right_layout.addWidget(preview_box)
        splitter.addWidget(right)
        splitter.setSizes([580, 700])
        layout.addWidget(splitter, 1)

        export_box = QGroupBox("5. 書き出し")
        export_layout = QHBoxLayout(export_box)
        self.individual_radio = QRadioButton("個別ファイル")
        self.combined_radio = QRadioButton("1本に結合")
        self.individual_radio.setChecked(True)
        self.combined_name = QLineEdit("combined_clip")
        self.combined_vertical = QCheckBox("結合動画を縦9:16")
        export_button = QPushButton("確定済みを書き出す")
        export_button.clicked.connect(self.start_export)
        open_button = QPushButton("Finderで出力先を開く")
        open_button.clicked.connect(self.open_output)
        export_layout.addWidget(self.individual_radio)
        export_layout.addWidget(self.combined_radio)
        export_layout.addWidget(QLabel("結合名:"))
        export_layout.addWidget(self.combined_name)
        export_layout.addWidget(self.combined_vertical)
        export_layout.addWidget(export_button)
        export_layout.addWidget(open_button)
        layout.addWidget(export_box)
        self.status_label = QLabel("動画を選択するか、ここへドラッグ＆ドロップしてください")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        self.setCentralWidget(root)

    def _adjust_row(self, edge: str, edit: QLineEdit) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        for delta in (-1.0, -0.5, 0.5, 1.0):
            button = QPushButton(f"{delta:+g}秒")
            button.clicked.connect(lambda _checked=False, e=edge, d=delta: self.adjust_candidate(e, d))
            layout.addWidget(button)
        return widget

    def choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "動画または音声を選択")
        if path:
            self.set_source(Path(path))

    def set_source(self, path: Path) -> None:
        if path.suffix.lower() not in self.MEDIA_EXTENSIONS:
            QMessageBox.warning(self, "未対応形式", "対応している動画または音声ファイルを選択してください")
            return
        self.player.stop()
        self.preview_manager.cleanup()
        self.preview_manager = PreviewManager()
        self.segments.clear()
        self.candidates.clear()
        self.transcript_table.setRowCount(0)
        self.candidate_table.setRowCount(0)
        self.source_path = path
        self.source_edit.setText(str(path))
        try:
            self.source_duration = media_duration(path)
            self.status_label.setText(f"読込完了: {path.name}（{format_timecode(self.source_duration, False)}）")
        except Exception as exc:
            self.source_duration = None
            QMessageBox.warning(self, "動画情報", str(exc))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.set_source(Path(urls[0].toLocalFile()))

    def _run_worker(self, fn: Callable, success: Callable[[object], None], show_errors: bool = True) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "処理中", "現在の処理が終わるまでお待ちください")
            return
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.thread = QThread(self)
        self.worker = Worker(fn)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status_label.setText)
        self._success_callback = success
        self._show_worker_errors = show_errors
        self.worker.succeeded.connect(self._worker_succeeded, Qt.ConnectionType.QueuedConnection)
        self.worker.failed.connect(self._worker_failed, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._worker_finished, Qt.ConnectionType.QueuedConnection)
        self.thread.start()

    @Slot(object)
    def _worker_succeeded(self, result: object) -> None:
        callback = self._success_callback
        if callback:
            callback(result)

    @Slot(str)
    def _worker_failed(self, message: str) -> None:
        if self._show_worker_errors:
            QMessageBox.critical(self, "エラー", message)
        else:
            self.status_label.setText("更新確認をスキップしました")

    @Slot()
    def _worker_finished(self) -> None:
        self.progress.setVisible(False)
        self.thread = None
        self.worker = None
        self._success_callback = None

    def start_transcription(self) -> None:
        if not self.source_path:
            QMessageBox.warning(self, "動画未選択", "先に動画または音声を選択してください")
            return
        source, model, suppress = self.source_path, self.model_combo.currentText(), self.suppress_check.isChecked()
        def task(status):
            segments = self.transcriber.transcribe(source, model, suppress, status)
            folder = source.parent / source.stem / "transcript"
            save_transcript(segments, folder, source.stem)
            return segments
        self._run_worker(task, self.transcription_finished)

    def transcription_finished(self, result: object) -> None:
        self.segments = list(result)  # type: ignore[arg-type]
        self.transcript_table.setRowCount(len(self.segments))
        for row, segment in enumerate(self.segments):
            values = (str(row + 1), format_timecode(segment.start), format_timecode(segment.end), segment.text)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.transcript_table.setItem(row, col, item)
        self.status_label.setText(f"文字起こし完了: {len(self.segments)}区間")

    def add_candidate(self) -> None:
        rows = sorted({index.row() for index in self.transcript_table.selectedIndexes()})
        if not rows:
            QMessageBox.warning(self, "未選択", "文字起こしの行を選択してください")
            return
        candidate = ClipCandidate(f"clip_{len(self.candidates) + 1:03d}", self.segments[rows[0]].start, self.segments[rows[-1]].end)
        self.candidates.append(candidate)
        self.refresh_candidates(len(self.candidates) - 1)

    def current_index(self) -> int:
        return self.candidate_table.currentRow()

    def refresh_candidates(self, selected: int | None = None) -> None:
        self.candidate_table.blockSignals(True)
        self.candidate_table.setRowCount(len(self.candidates))
        for row, item in enumerate(self.candidates):
            values = [item.name, format_timecode(item.start), format_timecode(item.end), format_timecode(item.duration), "✓" if item.vertical else "—", "✅ 確定" if item.confirmed else "⚠ 未確認"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 4:
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    cell.setCheckState(Qt.CheckState.Checked if item.vertical else Qt.CheckState.Unchecked)
                elif col != 0:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.candidate_table.setItem(row, col, cell)
        self.candidate_table.blockSignals(False)
        if selected is not None and 0 <= selected < len(self.candidates):
            self.candidate_table.selectRow(selected)

    def candidate_item_changed(self, cell: QTableWidgetItem) -> None:
        row = cell.row()
        if not (0 <= row < len(self.candidates)):
            return
        if cell.column() == 0:
            self.candidates[row].name = cell.text().strip() or f"clip_{row + 1:03d}"
        elif cell.column() == 4:
            new_value = cell.checkState() == Qt.CheckState.Checked
            if self.candidates[row].vertical != new_value:
                self.preview_manager.invalidate(self.candidates[row])
                self.candidates[row].vertical = new_value
                self.refresh_candidates(row)

    def load_candidate(self) -> None:
        row = self.current_index()
        if 0 <= row < len(self.candidates):
            item = self.candidates[row]
            self.start_edit.setText(format_timecode(item.start))
            self.end_edit.setText(format_timecode(item.end))
            self.confirm_button.setEnabled(bool(item.preview_path) and not item.confirmed)

    def range_edited(self) -> None:
        row = self.current_index()
        if row < 0:
            return
        try:
            self.preview_manager.invalidate(self.candidates[row])
            self.candidates[row].set_range(parse_timecode(self.start_edit.text()), parse_timecode(self.end_edit.text()), self.source_duration)
            self.refresh_candidates(row)
        except ValueError as exc:
            QMessageBox.warning(self, "時刻エラー", str(exc))
            self.load_candidate()

    def adjust_candidate(self, edge: str, delta: float) -> None:
        row = self.current_index()
        if row < 0:
            return
        try:
            self.preview_manager.invalidate(self.candidates[row])
            self.candidates[row].adjust(edge, delta, self.source_duration)
            self.refresh_candidates(row)
        except ValueError as exc:
            QMessageBox.warning(self, "調整できません", str(exc))

    def create_preview(self) -> None:
        row = self.current_index()
        if row < 0 or not self.source_path:
            QMessageBox.warning(self, "候補未選択", "プレビューする候補を選択してください")
            return
        self.player.stop()
        def task(status):
            status("プレビューを作成中…")
            return self.preview_manager.create(self.source_path, self.candidates[row], row)
        self._run_worker(task, lambda path: self.preview_ready(Path(path), row))

    def preview_ready(self, path: Path, row: int) -> None:
        if row != self.current_index():
            self.candidate_table.selectRow(row)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()
        self.play_button.setText("⏸ 一時停止")
        self.confirm_button.setEnabled(True)
        self.status_label.setText("プレビューを確認し、問題なければ範囲を確定してください")

    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_button.setText("▶ 再生")
        else:
            self.player.play()
            self.play_button.setText("⏸ 一時停止")

    def _player_position(self, value: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(value)
        self.position_label.setText(f"{format_timecode(value / 1000, False)} / {format_timecode(self.player.duration() / 1000, False)}")

    def confirm_candidate(self) -> None:
        row = self.current_index()
        if row < 0:
            return
        try:
            self.candidates[row].confirm()
            self.refresh_candidates(row)
            self.status_label.setText(f"{self.candidates[row].name} を確定しました")
        except ValueError as exc:
            QMessageBox.warning(self, "確定できません", str(exc))

    def move_up(self) -> None:
        row = self.current_index()
        if row > 0:
            self.candidates[row - 1], self.candidates[row] = self.candidates[row], self.candidates[row - 1]
            self.refresh_candidates(row - 1)

    def move_down(self) -> None:
        row = self.current_index()
        if 0 <= row < len(self.candidates) - 1:
            self.candidates[row + 1], self.candidates[row] = self.candidates[row], self.candidates[row + 1]
            self.refresh_candidates(row + 1)

    def remove_candidate(self) -> None:
        row = self.current_index()
        if row >= 0:
            self.preview_manager.invalidate(self.candidates[row])
            del self.candidates[row]
            self.refresh_candidates(min(row, len(self.candidates) - 1))

    def output_dir(self) -> Path | None:
        return self.source_path.parent / self.source_path.stem / "clips" if self.source_path else None

    def start_export(self) -> None:
        if not self.source_path or not any(item.confirmed for item in self.candidates):
            QMessageBox.warning(self, "確定済みなし", "プレビュー確認後、「この範囲で確定」を押してください")
            return
        source, output = self.source_path, self.output_dir()
        candidates = list(self.candidates)
        if self.individual_radio.isChecked():
            task = lambda status: (status("確定済みクリップを書き出し中…"), export_individual(source, candidates, output))[1]
        else:
            name = self.combined_name.text().strip() or "combined_clip"
            target = output / f"{name}.mp4"
            vertical = self.combined_vertical.isChecked()
            task = lambda status: (status("確定済みクリップを結合中…"), export_combined(source, candidates, target, vertical))[1]
        self._run_worker(task, lambda result: self.export_finished(result))

    def export_finished(self, result: object) -> None:
        count = len(result) if isinstance(result, list) else 1
        self.status_label.setText(f"書き出し完了: {count}ファイル")
        QMessageBox.information(self, "完了", f"確定済みの動画を書き出しました。\n{self.output_dir()}")

    def open_output(self) -> None:
        output = self.output_dir()
        if output:
            output.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def update_from_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "更新ZIPを選択", filter="ZIP (*.zip)")
        if not path:
            return
        self.install_update_zip(Path(path))

    def install_update_zip(self, path: Path, remove_after: bool = False) -> None:
        try:
            new_app = extract_update(path)
            executable = Path(sys.executable).resolve()
            current_app = next((parent for parent in executable.parents if parent.suffix == ".app"), None)
            if not current_app:
                raise ValueError("ソース起動中は自動更新できません。.app版から実行してください")
            answer = QMessageBox.question(self, "アップデート", "現在のアプリをバックアップして更新します。続行しますか？")
            if answer == QMessageBox.StandardButton.Yes:
                schedule_app_replacement(new_app, current_app)
                QApplication.quit()
        except Exception as exc:
            QMessageBox.critical(self, "更新エラー", str(exc))
        finally:
            if remove_after:
                path.unlink(missing_ok=True)

    def set_update_url(self) -> None:
        current = str(self.settings.value("update_url", ""))
        url, accepted = QInputDialog.getText(self, "更新URL", "update.json のURL:", text=current)
        if accepted:
            self.settings.setValue("update_url", url.strip())

    def auto_check_update(self) -> None:
        if self.thread is None and str(self.settings.value("update_url", "")).strip():
            self.check_for_updates(False)

    def check_for_updates(self, manual: bool) -> None:
        url = str(self.settings.value("update_url", "")).strip()
        if not url:
            if manual:
                self.set_update_url()
                url = str(self.settings.value("update_url", "")).strip()
            if not url:
                return
        def task(status):
            status("アップデートを確認中…")
            return read_update_manifest(url)
        self._run_worker(task, lambda data: self.update_manifest_ready(data, manual), show_errors=manual)

    def update_manifest_ready(self, result: object, manual: bool) -> None:
        manifest = dict(result)  # type: ignore[arg-type]
        if version_tuple(str(manifest["version"])) <= version_tuple(__version__):
            self.status_label.setText("最新バージョンです")
            if manual:
                QMessageBox.information(self, "アップデート", "現在のバージョンが最新です")
            return
        notes = manifest.get("notes", "")
        if isinstance(notes, list):
            notes = "\n".join(f"・{item}" for item in notes)
        message = f"v{manifest['version']} があります。ダウンロードして更新しますか？"
        if notes:
            message += f"\n\n{notes}"
        if QMessageBox.question(self, "新しいバージョン", message) != QMessageBox.StandardButton.Yes:
            return
        def task(status):
            status("更新ZIPをダウンロード中…")
            return download_update(manifest)
        self._run_worker(task, lambda path: self.install_update_zip(Path(path), True))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "処理中", "動画処理が終わってからアプリを終了してください")
            event.ignore()
            return
        self.player.stop()
        self.player.setSource(QUrl())
        self.preview_manager.cleanup()
        event.accept()
