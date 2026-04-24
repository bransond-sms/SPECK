"""
main_window.py
Main application window — UI layout, menus, toolbar, and component wiring.
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QToolBar, QStatusBar, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QInputDialog, QDialog,
    QDialogButtonBox, QFormLayout, QComboBox, QSpinBox,
    QGridLayout, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QIcon,
    QPalette, QPixmap
)

from app.image_canvas import ImageCanvas
from app.point_manager import PointManager
from app.session import Batch, Codeset, ImageEntry, IMAGE_EXTENSIONS
from app.export import export_summary, export_detailed, suggest_export_filename

FONT_SIZE = 9
APP_FONT = QFont("Arial", FONT_SIZE)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPECK — Substrate Point Enumeration and Classification Kit")
        self.setMinimumSize(1024, 700)
        self.resize(1280, 800)

        # Application state
        self._batch: Batch | None = None
        self._codeset: Codeset | None = None
        self._point_manager: PointManager = PointManager()
        self._session_filepath: str | None = None
        self._unsaved_changes: bool = False

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._set_font_recursive(self, APP_FONT)
        self._update_ui_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")
        self._act_new_batch = QAction("&New Batch...", self)
        self._act_new_batch.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new_batch.triggered.connect(self._on_new_batch)

        self._act_open = QAction("&Open Batch...", self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._on_open_batch)

        self._act_save = QAction("&Save Batch", self)
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.triggered.connect(self._on_save_batch)

        self._act_save_as = QAction("Save Batch &As...", self)
        self._act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_save_as.triggered.connect(self._on_save_batch_as)

        self._act_export_summary = QAction("Export &Summary CSV...", self)
        self._act_export_summary.setShortcut(QKeySequence("Ctrl+E"))
        self._act_export_summary.triggered.connect(self._on_export_summary)

        self._act_export_detailed = QAction("Export &Detailed CSV...", self)
        self._act_export_detailed.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._act_export_detailed.triggered.connect(self._on_export_detailed)

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        file_menu.addAction(self._act_new_batch)
        file_menu.addAction(self._act_open)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self._act_export_summary)
        file_menu.addAction(self._act_export_detailed)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        # Batch menu
        batch_menu = mb.addMenu("&Batch")
        self._act_prev_image = QAction("&Previous Image", self)
        self._act_prev_image.setShortcut(QKeySequence("Ctrl+Left"))
        self._act_prev_image.triggered.connect(self._on_prev_image)

        self._act_next_image = QAction("&Next Image", self)
        self._act_next_image.setShortcut(QKeySequence("Ctrl+Right"))
        self._act_next_image.triggered.connect(self._on_next_image)

        self._act_next_incomplete = QAction("Next &Incomplete Image", self)
        self._act_next_incomplete.setShortcut(QKeySequence("Ctrl+I"))
        self._act_next_incomplete.triggered.connect(self._on_next_incomplete)

        batch_menu.addAction(self._act_prev_image)
        batch_menu.addAction(self._act_next_image)
        batch_menu.addSeparator()
        batch_menu.addAction(self._act_next_incomplete)

        # Points menu
        points_menu = mb.addMenu("&Points")
        self._act_draw_boundary = QAction("&Draw Boundary", self)
        self._act_draw_boundary.setShortcut(QKeySequence("Ctrl+B"))
        self._act_draw_boundary.triggered.connect(self._on_draw_boundary)

        self._act_copy_boundary = QAction("&Copy Boundary from Previous", self)
        self._act_copy_boundary.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self._act_copy_boundary.triggered.connect(self._on_copy_boundary)

        self._act_generate_grid = QAction("&Generate Grid", self)
        self._act_generate_grid.setShortcut(QKeySequence("Ctrl+G"))
        self._act_generate_grid.triggered.connect(self._on_generate_grid)

        self._act_toggle_points = QAction("Show &All Points", self)
        self._act_toggle_points.setShortcut(QKeySequence("Space"))
        self._act_toggle_points.setCheckable(True)
        self._act_toggle_points.triggered.connect(self._on_toggle_points)

        self._act_undo = QAction("&Undo Classification", self)
        self._act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self._act_undo.triggered.connect(self._on_undo)

        points_menu.addAction(self._act_draw_boundary)
        points_menu.addAction(self._act_copy_boundary)
        points_menu.addSeparator()
        points_menu.addAction(self._act_generate_grid)
        points_menu.addSeparator()
        points_menu.addAction(self._act_toggle_points)
        points_menu.addSeparator()
        points_menu.addAction(self._act_undo)

        # View menu
        view_menu = mb.addMenu("&View")
        act_fit = QAction("&Fit Image to Window", self)
        act_fit.setShortcut(QKeySequence("F"))
        act_fit.triggered.connect(lambda: self._canvas.keyPressEvent(
            type('E', (), {'key': lambda: Qt.Key.Key_F})()
        ))

        # Help menu
        help_menu = mb.addMenu("&Help")
        act_about = QAction("&About SPECK", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main toolbar")
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self._act_new_batch)
        tb.addAction(self._act_open)
        tb.addAction(self._act_save)
        tb.addSeparator()
        tb.addAction(self._act_draw_boundary)
        tb.addAction(self._act_generate_grid)
        tb.addSeparator()
        tb.addAction(self._act_toggle_points)
        tb.addAction(self._act_undo)
        tb.addSeparator()
        tb.addAction(self._act_prev_image)
        tb.addAction(self._act_next_image)
        tb.addSeparator()
        tb.addAction(self._act_export_summary)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left: canvas + organism buttons
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)

        # Canvas
        self._canvas = ImageCanvas()
        self._canvas.point_activated.connect(self._on_point_activated)
        self._canvas.boundary_complete.connect(self._on_boundary_complete)
        left_layout.addWidget(self._canvas, stretch=1)

        # Organism button area
        org_frame = QFrame()
        org_frame.setFrameShape(QFrame.Shape.StyledPanel)
        org_frame.setMaximumHeight(160)
        org_outer = QVBoxLayout(org_frame)
        org_outer.setContentsMargins(4, 4, 4, 4)
        org_outer.setSpacing(2)

        # Search box
        self._org_search = QLineEdit()
        self._org_search.setPlaceholderText("Filter organisms...")
        self._org_search.setFont(APP_FONT)
        self._org_search.textChanged.connect(self._on_org_filter)
        org_outer.addWidget(self._org_search)

        # Scrollable grid of buttons
        self._org_scroll = QScrollArea()
        self._org_scroll.setWidgetResizable(True)
        self._org_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._org_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._org_button_container = QWidget()
        self._org_grid = QGridLayout(self._org_button_container)
        self._org_grid.setContentsMargins(2, 2, 2, 2)
        self._org_grid.setSpacing(2)
        self._org_scroll.setWidget(self._org_button_container)
        org_outer.addWidget(self._org_scroll)

        left_layout.addWidget(org_frame)

        # Right: points panel
        right_widget = QWidget()
        right_widget.setFixedWidth(220)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        # Progress label
        self._progress_label = QLabel("0 / 0 classified")
        self._progress_label.setFont(APP_FONT)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._progress_label)

        # Image label
        self._image_label = QLabel("No image loaded")
        self._image_label.setFont(APP_FONT)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setWordWrap(True)
        right_layout.addWidget(self._image_label)

        # Points list
        points_label = QLabel("Points")
        points_label.setFont(APP_FONT)
        right_layout.addWidget(points_label)

        self._points_list = QListWidget()
        self._points_list.setFont(APP_FONT)
        self._points_list.currentRowChanged.connect(self._on_points_list_row_changed)
        right_layout.addWidget(self._points_list, stretch=1)

        # Notes field
        notes_label = QLabel("Point notes")
        notes_label.setFont(APP_FONT)
        right_layout.addWidget(notes_label)

        self._notes_field = QTextEdit()
        self._notes_field.setFont(APP_FONT)
        self._notes_field.setMaximumHeight(60)
        self._notes_field.setPlaceholderText("Notes for active point...")
        self._notes_field.textChanged.connect(self._on_notes_changed)
        right_layout.addWidget(self._notes_field)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        main_layout.addWidget(splitter)

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setFont(APP_FONT)
        self._status_msg = QLabel("Open or create a batch to begin.")
        self._status_batch = QLabel("")
        self._status_image = QLabel("")
        sb.addWidget(self._status_msg, 1)
        sb.addPermanentWidget(self._status_image)
        sb.addPermanentWidget(self._status_batch)

    def _set_font_recursive(self, widget, font):
        widget.setFont(font)
        for child in widget.findChildren(QWidget):
            child.setFont(font)

    # ------------------------------------------------------------------
    # Organism buttons
    # ------------------------------------------------------------------

    def _rebuild_organism_buttons(self, filter_text: str = ""):
        """Rebuild the organism button grid from the loaded codeset."""
        # Clear existing buttons
        while self._org_grid.count():
            item = self._org_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._codeset:
            return

        codes = self._codeset.codes
        if filter_text:
            fl = filter_text.lower()
            codes = [c for c in codes if
                     fl in c["code"].lower() or fl in c["name"].lower()]

        cols = 8
        for idx, code_entry in enumerate(codes):
            btn = QPushButton(code_entry["code"][:6])
            btn.setFont(APP_FONT)
            btn.setFixedHeight(26)
            btn.setToolTip(code_entry["name"])
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)

            # Color the button background
            hex_color = code_entry.get("color", "#888888")
            color = QColor(hex_color)
            # Determine text color based on background luminance
            lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
            text_color = "#000000" if lum > 128 else "#ffffff"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {hex_color}; color: {text_color}; "
                f"border: 1px solid #555; border-radius: 2px; padding: 1px 2px; }}"
                f"QPushButton:hover {{ border: 2px solid #fff; }}"
            )

            code = code_entry["code"]
            btn.clicked.connect(lambda checked, c=code: self._on_organism_clicked(c))
            row, col = divmod(idx, cols)
            self._org_grid.addWidget(btn, row, col)

    @pyqtSlot(str)
    def _on_org_filter(self, text: str):
        self._rebuild_organism_buttons(text)

    # ------------------------------------------------------------------
    # Points list
    # ------------------------------------------------------------------

    def _rebuild_points_list(self):
        """Rebuild the points list widget from current PointManager state."""
        self._points_list.blockSignals(True)
        self._points_list.clear()

        for i, point in enumerate(self._point_manager.points):
            code_name = ""
            if point.code and self._codeset:
                code_name = point.code
            elif point.code:
                code_name = point.code

            note_indicator = " *" if point.notes else ""
            text = f"{point.index:>3}  {code_name:<8}{note_indicator}"
            item = QListWidgetItem(text)
            item.setFont(APP_FONT)

            if point.code and self._codeset:
                color = QColor(self._codeset.get_color(point.code))
                lum = 0.299*color.red() + 0.587*color.green() + 0.114*color.blue()
                item.setBackground(color)
                item.setForeground(QColor("#000" if lum > 128 else "#fff"))

            self._points_list.addItem(item)

        self._points_list.blockSignals(False)
        self._sync_points_list_selection()

    def _sync_points_list_selection(self):
        """Scroll to and select the active point in the list."""
        idx = self._point_manager.points.index(
            self._point_manager.points[self._active_point_index]
        ) if self._point_manager.points and self._active_point_index >= 0 else -1

        if idx >= 0:
            self._points_list.blockSignals(True)
            self._points_list.setCurrentRow(idx)
            self._points_list.scrollToItem(
                self._points_list.item(idx),
                QListWidget.ScrollHint.PositionAtCenter
            )
            self._points_list.blockSignals(False)

    @pyqtSlot(int)
    def _on_points_list_row_changed(self, row: int):
        if row < 0 or not self._point_manager.points:
            return
        self._set_active_point(row)

    # ------------------------------------------------------------------
    # Active point management
    # ------------------------------------------------------------------

    @property
    def _active_point_index(self) -> int:
        return self._canvas._active_index

    def _set_active_point(self, index: int):
        if not self._point_manager.points:
            return
        index = max(0, min(index, len(self._point_manager.points) - 1))
        self._canvas.set_active_point(index)

        # Update notes field without triggering save
        self._notes_field.blockSignals(True)
        point = self._point_manager.points[index]
        self._notes_field.setPlainText(point.notes or "")
        self._notes_field.blockSignals(False)

        self._sync_points_list_selection()
        self._update_status()

    def _advance_to_next_unclassified(self):
        next_idx = self._point_manager.next_unclassified(
            after_index=self._active_point_index
        )
        if next_idx is not None:
            self._set_active_point(next_idx)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _on_organism_clicked(self, code: str):
        """Classify the active point with the given code."""
        if not self._point_manager.points:
            return
        idx = self._active_point_index
        if idx < 0:
            return

        self._point_manager.classify(idx, code)
        self._unsaved_changes = True

        # Update canvas points
        self._refresh_canvas_points()
        self._rebuild_points_list()
        self._update_progress()
        self._update_status()

        # Check if image is now complete
        self._check_image_complete()

        # Advance to next unclassified
        self._advance_to_next_unclassified()

    # ------------------------------------------------------------------
    # Canvas signal handlers
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def _on_point_activated(self, index: int):
        self._set_active_point(index)

    @pyqtSlot(list)
    def _on_boundary_complete(self, vertices: list):
        """Boundary has been drawn — store on current image and generate grid."""
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        img.boundary = vertices
        self._set_status(f"Boundary set ({len(vertices)} vertices). Generating grid...")
        self._generate_grid_for_current_image()

    # ------------------------------------------------------------------
    # Grid generation
    # ------------------------------------------------------------------

    def _generate_grid_for_current_image(self):
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        if not img.boundary:
            self._set_status("Draw a boundary first.")
            return

        gt = img.grid_type or self._batch.batch_metadata.get("grid_type", "stratified")
        rows = img.grid_rows or self._batch.batch_metadata.get("grid_rows", 10)
        cols = img.grid_cols or self._batch.batch_metadata.get("grid_cols", 10)
        n = img.grid_n or self._batch.batch_metadata.get("grid_n", 100)

        if gt == "uniform":
            self._point_manager.generate_uniform(rows, cols, img.boundary)
        elif gt == "random":
            self._point_manager.generate_random(n, img.boundary)
        else:
            self._point_manager.generate_stratified(rows, cols, img.boundary)

        img.store_points(self._point_manager.to_dict())
        if img.status == ImageEntry.STATUS_UNTOUCHED:
            img.status = ImageEntry.STATUS_IN_PROGRESS

        self._refresh_canvas_points()
        self._rebuild_points_list()
        self._update_progress()

        if self._point_manager.points:
            self._set_active_point(0)

        self._set_status(
            f"Grid generated: {self._point_manager.total} points "
            f"({gt})."
        )
        self._unsaved_changes = True

    # ------------------------------------------------------------------
    # Image loading and navigation
    # ------------------------------------------------------------------

    def _load_current_image(self):
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        success = self._canvas.load_image(img.image_path)
        if not success:
            self._set_status(f"Could not load image: {img.image_filename}")
            return

        # Restore boundary if present
        if img.boundary:
            self._canvas.set_boundary(img.boundary)

        # Restore points if present
        point_data = img.get_point_data()
        if point_data and point_data.get("points"):
            self._point_manager.from_dict(point_data)
            self._refresh_canvas_points()
            self._rebuild_points_list()
            self._update_progress()
            if self._point_manager.points:
                next_idx = self._point_manager.next_unclassified()
                self._set_active_point(next_idx if next_idx is not None else 0)
        else:
            self._point_manager = PointManager()
            self._canvas.set_points([], {})
            self._points_list.clear()
            self._update_progress()

        self._image_label.setText(
            f"{self._batch.current_index + 1} / {self._batch.total_images}  "
            f"{img.image_filename}"
        )
        self._update_status()

    def _refresh_canvas_points(self):
        """Push current PointManager state to the canvas."""
        if not self._codeset:
            return
        code_colors = {c["code"]: c["color"] for c in self._codeset.codes}
        self._canvas.set_points(self._point_manager.points, code_colors)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_notes_changed(self):
        idx = self._active_point_index
        if idx < 0 or not self._point_manager.points:
            return
        self._point_manager.points[idx].notes = self._notes_field.toPlainText()
        self._unsaved_changes = True
        # Update the list item indicator
        item = self._points_list.item(idx)
        if item:
            point = self._point_manager.points[idx]
            code_name = point.code or ""
            note_indicator = " *" if point.notes else ""
            item.setText(f"{point.index:>3}  {code_name:<8}{note_indicator}")

    # ------------------------------------------------------------------
    # Menu / toolbar action handlers
    # ------------------------------------------------------------------

    def _on_new_batch(self):
        if not self._confirm_discard_changes():
            return
        wizard = NewBatchWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            result = wizard.result()
            self._start_batch(result)

    def _on_open_batch(self):
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Batch", "", "SPECK Session (*.speck)"
        )
        if path:
            self._load_batch(path)

    def _on_save_batch(self):
        if self._session_filepath:
            self._save_batch(self._session_filepath)
        else:
            self._on_save_batch_as()

    def _on_save_batch_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Batch", "", "SPECK Session (*.speck)"
        )
        if path:
            if not path.endswith(".speck"):
                path += ".speck"
            self._session_filepath = path
            self._save_batch(path)

    def _on_export_summary(self):
        self._do_export(detailed=False)

    def _on_export_detailed(self):
        self._do_export(detailed=True)

    def _on_prev_image(self):
        if not self._batch:
            return
        self._save_current_image_state()
        if self._batch.previous_image():
            self._load_current_image()

    def _on_next_image(self):
        if not self._batch:
            return
        self._save_current_image_state()
        if self._batch.next_image():
            self._load_current_image()

    def _on_next_incomplete(self):
        if not self._batch:
            return
        self._save_current_image_state()
        if self._batch.next_incomplete():
            self._load_current_image()
        else:
            QMessageBox.information(self, "SPECK", "All images in this batch are complete.")

    def _on_draw_boundary(self):
        if not self._canvas.has_image():
            self._set_status("Load an image first.")
            return
        self._canvas.start_boundary_drawing()
        self._set_status("Click to place boundary vertices. Double-click to close. "
                         "Right-click to remove last vertex. Escape to cancel.")

    def _on_copy_boundary(self):
        if not self._batch or self._batch.current_index == 0:
            self._set_status("No previous image to copy boundary from.")
            return
        prev_img = self._batch.images[self._batch.current_index - 1]
        if not prev_img.boundary:
            self._set_status("Previous image has no boundary.")
            return
        self._canvas.set_boundary(prev_img.boundary)
        if self._batch.current_image:
            self._batch.current_image.boundary = list(prev_img.boundary)
        self._generate_grid_for_current_image()
        self._set_status("Boundary copied from previous image. Grid generated.")

    def _on_generate_grid(self):
        if not self._canvas.has_boundary():
            self._set_status("Draw a boundary first (Ctrl+B).")
            return
        self._generate_grid_for_current_image()

    def _on_toggle_points(self, checked: bool):
        self._canvas.set_show_all_points(checked)

    def _on_undo(self):
        idx = self._point_manager.undo()
        if idx is not None:
            self._refresh_canvas_points()
            self._rebuild_points_list()
            self._update_progress()
            self._set_active_point(idx)
            self._unsaved_changes = True
            self._set_status("Undo: classification removed.")
        else:
            self._set_status("Nothing to undo.")

    def _on_about(self):
        QMessageBox.about(
            self, "About SPECK",
            "<b>SPECK</b> — Substrate Point Enumeration and Classification Kit<br><br>"
            "Version 0.1.0<br><br>"
            "Developed at the Smithsonian Marine Station at Fort Pierce.<br>"
            "Open source replacement for CPCe.<br><br>"
            "github.com/bransond-sms/SPECK"
        )

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Tab and not (mods & Qt.KeyboardModifier.ShiftModifier):
            self._advance_to_next_unclassified()
        elif key == Qt.Key.Key_Tab and (mods & Qt.KeyboardModifier.ShiftModifier):
            self._go_to_previous_point()
        elif key == Qt.Key.Key_Space:
            self._act_toggle_points.setChecked(
                not self._act_toggle_points.isChecked()
            )
            self._on_toggle_points(self._act_toggle_points.isChecked())
        else:
            super().keyPressEvent(event)

    def _go_to_previous_point(self):
        idx = self._active_point_index
        if idx > 0:
            self._set_active_point(idx - 1)

    # ------------------------------------------------------------------
    # Batch lifecycle
    # ------------------------------------------------------------------

    def _start_batch(self, wizard_result: dict):
        """Initialize a new batch from wizard results."""
        codeset = Codeset()
        codeset.load(wizard_result["codeset_path"])
        self._codeset = codeset

        batch = Batch()
        batch.initialize(
            image_dir=wizard_result["image_dir"],
            codeset_name=codeset.name,
            codeset_path=wizard_result["codeset_path"],
            batch_metadata=wizard_result["metadata"],
        )
        # Store grid config in batch_metadata for use during grid generation
        batch.batch_metadata["grid_type"] = wizard_result["grid_type"]
        batch.batch_metadata["grid_rows"] = wizard_result["grid_rows"]
        batch.batch_metadata["grid_cols"] = wizard_result["grid_cols"]
        batch.batch_metadata["grid_n"] = wizard_result["grid_n"]

        self._batch = batch
        self._session_filepath = None
        self._unsaved_changes = True
        self._point_manager = PointManager()

        self._rebuild_organism_buttons()
        self._load_current_image()
        self._update_ui_state()
        self._update_batch_status()
        self._set_status(
            f"New batch: {batch.total_images} image(s) in "
            f"{os.path.basename(wizard_result['image_dir'])}"
        )

    def _load_batch(self, filepath: str):
        """Load a batch from a .speck file."""
        try:
            batch = Batch()
            batch.load(filepath)

            codeset = Codeset()
            codeset.load(batch.codeset_path)

            self._batch = batch
            self._codeset = codeset
            self._session_filepath = filepath
            self._unsaved_changes = False
            self._point_manager = PointManager()

            self._rebuild_organism_buttons()
            self._load_current_image()
            self._update_ui_state()
            self._update_batch_status()
            self._set_status(f"Loaded: {os.path.basename(filepath)}")

        except (FileNotFoundError, ValueError, KeyError) as e:
            QMessageBox.critical(self, "Error loading batch", str(e))

    def _save_batch(self, filepath: str):
        """Save current batch state to a .speck file."""
        if not self._batch:
            return
        self._save_current_image_state()
        try:
            self._batch.save(filepath)
            self._unsaved_changes = False
            self._set_status(f"Saved: {os.path.basename(filepath)}")
        except OSError as e:
            QMessageBox.critical(self, "Error saving batch", str(e))

    def _save_current_image_state(self):
        """Flush current PointManager state back to the current ImageEntry."""
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        if self._point_manager.points:
            img.store_points(self._point_manager.to_dict())
            if self._point_manager.is_complete:
                img.status = ImageEntry.STATUS_COMPLETE
            elif self._point_manager.classified_count > 0:
                img.status = ImageEntry.STATUS_IN_PROGRESS

    def _check_image_complete(self):
        if self._point_manager.is_complete:
            if self._batch and self._batch.current_image:
                self._batch.current_image.status = ImageEntry.STATUS_COMPLETE
            self._update_batch_status()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _do_export(self, detailed: bool):
        if not self._batch or not self._codeset:
            self._set_status("No batch loaded.")
            return
        self._save_current_image_state()

        suggested = suggest_export_filename(self._batch, detailed=detailed)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", suggested, "CSV files (*.csv)"
        )
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"

        try:
            if detailed:
                rows, warnings = export_detailed(self._batch, self._codeset, path)
            else:
                rows, warnings = export_summary(self._batch, self._codeset, path)

            msg = f"Exported {rows} rows to {os.path.basename(path)}."
            if warnings:
                msg += f"\n\n{len(warnings)} warning(s):\n" + "\n".join(warnings)
                QMessageBox.warning(self, "Export complete", msg)
            else:
                QMessageBox.information(self, "Export complete", msg)

        except OSError as e:
            QMessageBox.critical(self, "Export error", str(e))

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _update_ui_state(self):
        has_batch = self._batch is not None
        has_points = bool(self._point_manager.points)
        self._act_save.setEnabled(has_batch)
        self._act_save_as.setEnabled(has_batch)
        self._act_export_summary.setEnabled(has_batch)
        self._act_export_detailed.setEnabled(has_batch)
        self._act_prev_image.setEnabled(has_batch)
        self._act_next_image.setEnabled(has_batch)
        self._act_next_incomplete.setEnabled(has_batch)
        self._act_draw_boundary.setEnabled(has_batch)
        self._act_copy_boundary.setEnabled(has_batch)
        self._act_generate_grid.setEnabled(has_batch)
        self._act_toggle_points.setEnabled(has_points)
        self._act_undo.setEnabled(has_points)

    def _update_progress(self):
        total = self._point_manager.total
        classified = self._point_manager.classified_count
        self._progress_label.setText(f"{classified} / {total} classified")
        self._update_ui_state()

    def _update_batch_status(self):
        if not self._batch:
            self._status_batch.setText("")
            return
        self._status_batch.setText(
            f"Batch: {self._batch.complete_count}/{self._batch.total_images} complete"
        )

    def _update_status(self):
        if not self._batch or not self._batch.current_image:
            return
        idx = self._active_point_index
        if idx >= 0 and self._point_manager.points:
            point = self._point_manager.points[idx]
            code_str = point.code or "unclassified"
            self._set_status(
                f"Point {point.index} of {self._point_manager.total} — {code_str}"
            )
        self._status_image.setText(
            f"Image {self._batch.current_index + 1} / {self._batch.total_images}"
        )

    def _set_status(self, msg: str):
        self._status_msg.setText(msg)

    def _confirm_discard_changes(self) -> bool:
        if not self._unsaved_changes:
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "Save before quitting?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save_batch()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# ------------------------------------------------------------------
# New Batch Wizard
# ------------------------------------------------------------------

class NewBatchWizard(QDialog):
    """
    Multi-step dialog for configuring a new batch.
    Steps: (1) Image directory + codeset, (2) Grid config, (3) Metadata
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Batch")
        self.setMinimumWidth(480)
        self.setFont(APP_FONT)
        self._result: dict = {}
        self._codeset: Codeset | None = None

        layout = QVBoxLayout(self)

        # Step 1: Image directory
        layout.addWidget(self._section_label("Step 1: Image Directory and Codeset"))
        form1 = QFormLayout()

        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._browse_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(dir_btn)
        form1.addRow("Image directory:", dir_row)

        self._codeset_edit = QLineEdit()
        self._codeset_edit.setReadOnly(True)
        cs_btn = QPushButton("Browse...")
        cs_btn.clicked.connect(self._browse_codeset)
        cs_row = QHBoxLayout()
        cs_row.addWidget(self._codeset_edit)
        cs_row.addWidget(cs_btn)
        form1.addRow("Codeset file:", cs_row)

        self._image_count_label = QLabel("No directory selected.")
        form1.addRow("", self._image_count_label)
        layout.addLayout(form1)

        # Step 2: Grid configuration
        layout.addWidget(self._section_label("Step 2: Grid Configuration"))
        form2 = QFormLayout()

        self._grid_type = QComboBox()
        self._grid_type.addItems(["Stratified Random", "Uniform", "Random"])
        self._grid_type.currentIndexChanged.connect(self._on_grid_type_changed)
        form2.addRow("Grid type:", self._grid_type)

        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(1, 50)
        self._grid_rows.setValue(10)
        form2.addRow("Rows:", self._grid_rows)

        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(1, 50)
        self._grid_cols.setValue(10)
        form2.addRow("Columns:", self._grid_cols)

        self._grid_n = QSpinBox()
        self._grid_n.setRange(1, 1000)
        self._grid_n.setValue(100)
        self._grid_n.setEnabled(False)
        form2.addRow("Number of points (random):", self._grid_n)

        layout.addLayout(form2)

        # Step 3: Metadata (populated after codeset loads)
        layout.addWidget(self._section_label("Step 3: Batch Metadata"))
        self._metadata_form = QFormLayout()
        self._metadata_widgets: dict[str, QWidget] = {}
        layout.addLayout(self._metadata_form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setFont(APP_FONT)
        return lbl

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select image directory")
        if path:
            self._dir_edit.setText(path)
            # Count images
            count = sum(
                1 for f in os.listdir(path)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            )
            self._image_count_label.setText(f"{count} image(s) found.")

    def _browse_codeset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select codeset", "codesets", "JSON files (*.json)"
        )
        if path:
            try:
                cs = Codeset()
                cs.load(path)
                self._codeset = cs
                self._codeset_edit.setText(path)
                self._build_metadata_form()
            except Exception as e:
                QMessageBox.critical(self, "Error loading codeset", str(e))

    def _build_metadata_form(self):
        """Populate metadata form from codeset field definitions."""
        # Clear existing
        while self._metadata_form.rowCount():
            self._metadata_form.removeRow(0)
        self._metadata_widgets.clear()

        if not self._codeset:
            return

        for fd in self._codeset.metadata_fields:
            if fd.field_type == "select" and fd.choices:
                widget = QComboBox()
                widget.addItems(fd.choices)
                widget.setFont(APP_FONT)
            else:
                widget = QLineEdit()
                widget.setFont(APP_FONT)
                if fd.default is not None:
                    widget.setText(str(fd.default))
                if fd.required:
                    widget.setPlaceholderText("(required)")

            label = fd.label + ("*" if fd.required else "")
            self._metadata_form.addRow(label + ":", widget)
            self._metadata_widgets[fd.name] = widget

    def _on_grid_type_changed(self, index: int):
        is_random = (index == 2)  # "Random" is index 2
        self._grid_rows.setEnabled(not is_random)
        self._grid_cols.setEnabled(not is_random)
        self._grid_n.setEnabled(is_random)

    def _on_accept(self):
        # Validate
        if not self._dir_edit.text():
            QMessageBox.warning(self, "Validation", "Please select an image directory.")
            return
        if not self._codeset_edit.text():
            QMessageBox.warning(self, "Validation", "Please select a codeset file.")
            return

        # Collect metadata
        metadata = {}
        for fd in self._codeset.metadata_fields:
            widget = self._metadata_widgets.get(fd.name)
            if widget is None:
                continue
            if isinstance(widget, QComboBox):
                metadata[fd.name] = widget.currentText()
            else:
                val = widget.text().strip()
                # Coerce numeric fields
                if fd.field_type == "number" and val:
                    try:
                        val = int(val)
                    except ValueError:
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                metadata[fd.name] = val or None

        # Validate required fields
        if self._codeset:
            errors = self._codeset.validate_metadata(metadata)
            if errors:
                QMessageBox.warning(
                    self, "Required fields",
                    "Please fill in required fields:\n\n" + "\n".join(errors)
                )
                return

        type_map = {"Stratified Random": "stratified", "Uniform": "uniform", "Random": "random"}
        grid_type = type_map[self._grid_type.currentText()]

        self._result = {
            "image_dir":    self._dir_edit.text(),
            "codeset_path": self._codeset_edit.text(),
            "metadata":     metadata,
            "grid_type":    grid_type,
            "grid_rows":    self._grid_rows.value(),
            "grid_cols":    self._grid_cols.value(),
            "grid_n":       self._grid_n.value(),
        }
        self.accept()

    def result(self) -> dict:
        return self._result
