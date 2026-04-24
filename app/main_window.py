"""
main_window.py
Main application window — UI layout, menus, toolbar, and component wiring.

Change items addressed:
1. Single image mode via File > Open Image
2. Panel ID removed from batch metadata form (per-image only)
3. Point markers changed to crosshair; active=cyan, unclassified=red
4. Image formats: jpg/jpeg/png/tif/tiff/bmp/webp all supported
5. Rubber-band multi-point selection and bulk classification
6. Organism panel resizable via splitter; buttons smaller (20px, 12 per row)
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QToolBar, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QComboBox, QSpinBox,
    QGridLayout, QSizePolicy, QTextEdit, QColorDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSlot
from PyQt6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QIcon, QPixmap
)

from app.image_canvas import ImageCanvas, SUPPORTED_EXTENSIONS
from app.point_manager import PointManager
from app.session import Batch, Codeset, ImageEntry, IMAGE_EXTENSIONS
from app.export import export_summary, export_detailed, suggest_export_filename

FONT_SIZE = 9
APP_FONT = QFont("Arial", FONT_SIZE)

# Per-image fields that should NOT appear in the batch metadata wizard
PER_IMAGE_FIELDS = {"panel_id"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPECK — Substrate Point Enumeration and Classification Kit")
        self.setMinimumSize(1024, 700)
        self.resize(1280, 800)

        self._batch: Batch | None = None
        self._codeset: Codeset | None = None
        self._point_manager: PointManager = PointManager()
        self._session_filepath: str | None = None
        self._unsaved_changes: bool = False

        # Point colors (user-configurable)
        self._active_color      = QColor(0, 255, 255)   # Cyan
        self._unclassified_color = QColor(255, 0, 0)    # Red

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

        # File
        file_menu = mb.addMenu("&File")

        self._act_new_batch = QAction("&New Batch...", self)
        self._act_new_batch.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new_batch.triggered.connect(self._on_new_batch)

        self._act_open_image = QAction("Open &Image...", self)
        self._act_open_image.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._act_open_image.triggered.connect(self._on_open_single_image)

        self._act_open = QAction("&Open Batch...", self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._on_open_batch)

        self._act_save = QAction("&Save", self)
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.triggered.connect(self._on_save_batch)

        self._act_save_as = QAction("Save &As...", self)
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

        for act in [self._act_new_batch, self._act_open_image, self._act_open]:
            file_menu.addAction(act)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self._act_export_summary)
        file_menu.addAction(self._act_export_detailed)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        # Batch
        batch_menu = mb.addMenu("&Batch")
        self._act_prev_image = QAction("&Previous Image", self)
        self._act_prev_image.setShortcut(QKeySequence("Ctrl+Left"))
        self._act_prev_image.triggered.connect(self._on_prev_image)

        self._act_next_image = QAction("&Next Image", self)
        self._act_next_image.setShortcut(QKeySequence("Ctrl+Right"))
        self._act_next_image.triggered.connect(self._on_next_image)

        self._act_next_incomplete = QAction("Next &Incomplete", self)
        self._act_next_incomplete.setShortcut(QKeySequence("Ctrl+I"))
        self._act_next_incomplete.triggered.connect(self._on_next_incomplete)

        batch_menu.addAction(self._act_prev_image)
        batch_menu.addAction(self._act_next_image)
        batch_menu.addSeparator()
        batch_menu.addAction(self._act_next_incomplete)

        # Points
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

        self._act_select_points = QAction("&Select Points (rubber-band)", self)
        self._act_select_points.setShortcut(QKeySequence("Ctrl+R"))
        self._act_select_points.triggered.connect(self._on_start_selection)

        self._act_undo = QAction("&Undo", self)
        self._act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self._act_undo.triggered.connect(self._on_undo)

        for act in [self._act_draw_boundary, self._act_copy_boundary]:
            points_menu.addAction(act)
        points_menu.addSeparator()
        points_menu.addAction(self._act_generate_grid)
        points_menu.addSeparator()
        points_menu.addAction(self._act_toggle_points)
        points_menu.addAction(self._act_select_points)
        points_menu.addSeparator()
        points_menu.addAction(self._act_undo)

        # View
        view_menu = mb.addMenu("&View")
        act_fit = QAction("&Fit Image to Window", self)
        act_fit.setShortcut(QKeySequence("F"))
        act_fit.triggered.connect(lambda: self._canvas.fit_to_window())
        view_menu.addAction(act_fit)

        act_colors = QAction("Point &Colors...", self)
        act_colors.triggered.connect(self._on_point_colors)
        view_menu.addAction(act_colors)

        # Help
        help_menu = mb.addMenu("&Help")
        act_about = QAction("&About SPECK", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main toolbar")
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        self.addToolBar(tb)
        for act in [
            self._act_new_batch, self._act_open_image, self._act_open,
            self._act_save, None,
            self._act_draw_boundary, self._act_generate_grid, None,
            self._act_toggle_points, self._act_select_points,
            self._act_undo, None,
            self._act_prev_image, self._act_next_image, None,
            self._act_export_summary,
        ]:
            if act is None:
                tb.addSeparator()
            else:
                tb.addAction(act)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Left column: canvas + organism panel (vertical splitter) ----
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        self._canvas = ImageCanvas()
        self._canvas.point_activated.connect(self._on_point_activated)
        self._canvas.boundary_complete.connect(self._on_boundary_complete)
        self._canvas.points_selected.connect(self._on_points_selected)
        left_splitter.addWidget(self._canvas)

        # Organism panel
        org_frame = QFrame()
        org_frame.setFrameShape(QFrame.Shape.StyledPanel)
        org_outer = QVBoxLayout(org_frame)
        org_outer.setContentsMargins(4, 2, 4, 2)
        org_outer.setSpacing(2)

        org_top = QHBoxLayout()
        self._org_search = QLineEdit()
        self._org_search.setPlaceholderText("Filter organisms...")
        self._org_search.setFont(APP_FONT)
        self._org_search.textChanged.connect(self._on_org_filter)
        org_top.addWidget(self._org_search)
        org_outer.addLayout(org_top)

        self._org_scroll = QScrollArea()
        self._org_scroll.setWidgetResizable(True)
        self._org_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._org_button_container = QWidget()
        self._org_grid = QGridLayout(self._org_button_container)
        self._org_grid.setContentsMargins(2, 2, 2, 2)
        self._org_grid.setSpacing(2)
        self._org_scroll.setWidget(self._org_button_container)
        org_outer.addWidget(self._org_scroll)

        left_splitter.addWidget(org_frame)
        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)

        # ---- Right column: progress + points list + notes ----
        right_widget = QWidget()
        right_widget.setFixedWidth(220)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)

        self._progress_label = QLabel("0 / 0 classified")
        self._progress_label.setFont(APP_FONT)
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self._progress_label)

        self._image_label = QLabel("No image loaded")
        self._image_label.setFont(APP_FONT)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setWordWrap(True)
        right_layout.addWidget(self._image_label)

        # Panel ID row
        pid_row = QHBoxLayout()
        pid_lbl = QLabel("Panel ID:")
        pid_lbl.setFont(APP_FONT)
        self._panel_id_edit = QLineEdit()
        self._panel_id_edit.setFont(APP_FONT)
        self._panel_id_edit.setPlaceholderText("auto from filename")
        self._panel_id_edit.editingFinished.connect(self._on_panel_id_changed)
        pid_row.addWidget(pid_lbl)
        pid_row.addWidget(self._panel_id_edit)
        right_layout.addLayout(pid_row)

        right_layout.addWidget(QLabel("Points"))
        self._points_list = QListWidget()
        self._points_list.setFont(APP_FONT)
        self._points_list.currentRowChanged.connect(self._on_points_list_row_changed)
        right_layout.addWidget(self._points_list, stretch=1)

        right_layout.addWidget(QLabel("Point notes"))
        self._notes_field = QTextEdit()
        self._notes_field.setFont(APP_FONT)
        self._notes_field.setMaximumHeight(60)
        self._notes_field.setPlaceholderText("Notes for active point...")
        self._notes_field.textChanged.connect(self._on_notes_changed)
        right_layout.addWidget(self._notes_field)

        # Horizontal splitter: left column | right panel
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(right_widget)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 0)
        root.addWidget(h_splitter)

    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setFont(APP_FONT)
        self._status_msg   = QLabel("Open or create a batch to begin.")
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
        while self._org_grid.count():
            item = self._org_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._codeset:
            return

        codes = self._codeset.codes
        if filter_text:
            fl = filter_text.lower()
            codes = [c for c in codes
                     if fl in c["code"].lower() or fl in c["name"].lower()]

        cols = 12   # More buttons per row
        for idx, ce in enumerate(codes):
            btn = QPushButton(ce["code"][:6])
            btn.setFont(APP_FONT)
            btn.setFixedHeight(20)   # Compact height
            btn.setToolTip(ce["name"])
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            hex_c = ce.get("color", "#888888")
            color = QColor(hex_c)
            lum = 0.299*color.red() + 0.587*color.green() + 0.114*color.blue()
            tc = "#000" if lum > 128 else "#fff"
            btn.setStyleSheet(
                f"QPushButton{{background:{hex_c};color:{tc};"
                f"border:1px solid #555;border-radius:2px;padding:0 2px;}}"
                f"QPushButton:hover{{border:2px solid #fff;}}"
            )
            code = ce["code"]
            btn.clicked.connect(lambda checked, c=code: self._on_organism_clicked(c))
            self._org_grid.addWidget(btn, idx // cols, idx % cols)

    @pyqtSlot(str)
    def _on_org_filter(self, text: str):
        self._rebuild_organism_buttons(text)

    # ------------------------------------------------------------------
    # Points list
    # ------------------------------------------------------------------

    def _rebuild_points_list(self):
        self._points_list.blockSignals(True)
        self._points_list.clear()
        for i, point in enumerate(self._point_manager.points):
            note_ind = " *" if point.notes else ""
            code_str = point.code or ""
            text = f"{point.index:>3}  {code_str:<8}{note_ind}"
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
        idx = self._canvas._active_index
        if 0 <= idx < self._points_list.count():
            self._points_list.blockSignals(True)
            self._points_list.setCurrentRow(idx)
            self._points_list.scrollToItem(
                self._points_list.item(idx),
                QListWidget.ScrollHint.PositionAtCenter
            )
            self._points_list.blockSignals(False)

    @pyqtSlot(int)
    def _on_points_list_row_changed(self, row: int):
        if row >= 0 and self._point_manager.points:
            self._set_active_point(row)

    # ------------------------------------------------------------------
    # Active point management
    # ------------------------------------------------------------------

    def _set_active_point(self, index: int):
        if not self._point_manager.points:
            return
        index = max(0, min(index, len(self._point_manager.points) - 1))
        self._canvas.set_active_point(index)
        self._notes_field.blockSignals(True)
        self._notes_field.setPlainText(self._point_manager.points[index].notes or "")
        self._notes_field.blockSignals(False)
        self._sync_points_list_selection()
        self._update_status()

    def _advance_to_next_unclassified(self):
        next_idx = self._point_manager.next_unclassified(
            after_index=self._canvas._active_index)
        if next_idx is not None:
            self._set_active_point(next_idx)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _on_organism_clicked(self, code: str):
        """Classify active point — or all selected points if a selection exists."""
        if not self._point_manager.points:
            return

        selected = list(self._canvas._selected_indices)
        if selected:
            # Bulk classify all selected points
            for idx in selected:
                self._point_manager.classify(idx, code)
            self._canvas.clear_selection()
            self._set_status(f"Classified {len(selected)} points as {code}.")
        else:
            idx = self._canvas._active_index
            if idx < 0:
                return
            self._point_manager.classify(idx, code)
            self._advance_to_next_unclassified()

        self._unsaved_changes = True
        self._refresh_canvas_points()
        self._rebuild_points_list()
        self._update_progress()
        self._check_image_complete()
        self._update_status()

    # ------------------------------------------------------------------
    # Canvas signal handlers
    # ------------------------------------------------------------------

    @pyqtSlot(int)
    def _on_point_activated(self, index: int):
        self._set_active_point(index)

    @pyqtSlot(list)
    def _on_boundary_complete(self, vertices: list):
        if not self._batch or not self._batch.current_image:
            return
        self._batch.current_image.boundary = vertices
        self._generate_grid_for_current_image()

    @pyqtSlot(list)
    def _on_points_selected(self, indices: list):
        count = len(indices)
        self._set_status(
            f"{count} point(s) selected. Click an organism button to classify all.")

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

        gt   = img.grid_type  or self._batch.batch_metadata.get("grid_type", "stratified")
        rows = img.grid_rows  or self._batch.batch_metadata.get("grid_rows", 10)
        cols = img.grid_cols  or self._batch.batch_metadata.get("grid_cols", 10)
        n    = img.grid_n     or self._batch.batch_metadata.get("grid_n", 100)

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
            f"Grid: {self._point_manager.total} points ({gt}).")
        self._unsaved_changes = True

    # ------------------------------------------------------------------
    # Image loading and navigation
    # ------------------------------------------------------------------

    def _load_current_image(self):
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        if not self._canvas.load_image(img.image_path):
            self._set_status(f"Could not load: {img.image_filename}")
            return

        if img.boundary:
            self._canvas.set_boundary(img.boundary)

        point_data = img.get_point_data()
        if point_data and point_data.get("points"):
            self._point_manager.from_dict(point_data)
            self._refresh_canvas_points()
            self._rebuild_points_list()
            self._update_progress()
            next_idx = self._point_manager.next_unclassified()
            self._set_active_point(next_idx if next_idx is not None else 0)
        else:
            self._point_manager = PointManager()
            self._canvas.set_points([], {})
            self._points_list.clear()
            self._update_progress()

        self._panel_id_edit.setText(img.panel_id)
        self._image_label.setText(
            f"{self._batch.current_index + 1} / {self._batch.total_images}  "
            f"{img.image_filename}"
        )
        self._update_status()

    def _refresh_canvas_points(self):
        if not self._codeset:
            return
        code_colors = {c["code"]: c["color"] for c in self._codeset.codes}
        self._canvas.set_points(self._point_manager.points, code_colors)

    # ------------------------------------------------------------------
    # Notes and panel ID
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_notes_changed(self):
        idx = self._canvas._active_index
        if idx < 0 or not self._point_manager.points:
            return
        self._point_manager.points[idx].notes = self._notes_field.toPlainText()
        self._unsaved_changes = True
        item = self._points_list.item(idx)
        if item:
            p = self._point_manager.points[idx]
            item.setText(f"{p.index:>3}  {p.code or '':<8}{' *' if p.notes else ''}")

    @pyqtSlot()
    def _on_panel_id_changed(self):
        if self._batch and self._batch.current_image:
            self._batch.current_image.panel_id = self._panel_id_edit.text().strip()
            self._unsaved_changes = True

    # ------------------------------------------------------------------
    # Single image mode
    # ------------------------------------------------------------------

    def _on_open_single_image(self):
        if not self._confirm_discard_changes():
            return

        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            f"Image files ({exts});;All files (*)"
        )
        if not path:
            return

        # Load codeset
        cs_path, _ = QFileDialog.getOpenFileName(
            self, "Select Codeset", "codesets", "JSON files (*.json)"
        )
        if not cs_path:
            return

        try:
            cs = Codeset()
            cs.load(cs_path)
        except Exception as e:
            QMessageBox.critical(self, "Codeset error", str(e))
            return

        # Build a single-image batch
        image_dir = os.path.dirname(path)
        batch = Batch()
        batch.codeset_name = cs.name
        batch.codeset_path = cs_path
        batch.image_dir    = image_dir
        batch.batch_metadata = cs.empty_metadata()
        batch.batch_metadata.update({
            "grid_type": "stratified",
            "grid_rows": 10,
            "grid_cols": 10,
            "grid_n":    100,
        })

        entry = ImageEntry(path)
        batch.images = [entry]

        self._batch   = batch
        self._codeset = cs
        self._session_filepath = None
        self._unsaved_changes  = True
        self._point_manager    = PointManager()

        self._rebuild_organism_buttons()
        self._load_current_image()
        self._update_ui_state()
        self._set_status(f"Single image: {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Menu / toolbar action handlers
    # ------------------------------------------------------------------

    def _on_new_batch(self):
        if not self._confirm_discard_changes():
            return
        wizard = NewBatchWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            self._start_batch(wizard.result())

    def _on_open_batch(self):
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Batch", "", "SPECK Session (*.speck)")
        if path:
            self._load_batch(path)

    def _on_save_batch(self):
        if self._session_filepath:
            self._save_batch(self._session_filepath)
        else:
            self._on_save_batch_as()

    def _on_save_batch_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Batch", "", "SPECK Session (*.speck)")
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
        if not self._batch.next_incomplete():
            QMessageBox.information(self, "SPECK", "All images are complete.")

    def _on_draw_boundary(self):
        if not self._canvas.has_image():
            self._set_status("Load an image first.")
            return
        self._canvas.start_boundary_drawing()
        self._set_status(
            "Click to place vertices. Double-click to close. "
            "Right-click removes last vertex. Escape cancels.")

    def _on_copy_boundary(self):
        if not self._batch or self._batch.current_index == 0:
            self._set_status("No previous image to copy from.")
            return
        prev = self._batch.images[self._batch.current_index - 1]
        if not prev.boundary:
            self._set_status("Previous image has no boundary.")
            return
        self._canvas.set_boundary(prev.boundary)
        if self._batch.current_image:
            self._batch.current_image.boundary = list(prev.boundary)
        self._generate_grid_for_current_image()
        self._set_status("Boundary copied and grid generated.")

    def _on_generate_grid(self):
        if not self._canvas.has_boundary():
            self._set_status("Draw a boundary first (Ctrl+B).")
            return
        self._generate_grid_for_current_image()

    def _on_toggle_points(self, checked: bool):
        self._canvas.set_show_all_points(checked)

    def _on_start_selection(self):
        if not self._point_manager.points:
            self._set_status("Generate a grid first.")
            return
        self._canvas.set_show_all_points(True)
        self._act_toggle_points.setChecked(True)
        self._canvas.start_selection_mode()
        self._set_status(
            "Drag to select points. Click an organism button to classify all selected.")

    def _on_undo(self):
        idx = self._point_manager.undo()
        if idx is not None:
            self._refresh_canvas_points()
            self._rebuild_points_list()
            self._update_progress()
            self._set_active_point(idx)
            self._unsaved_changes = True
            self._set_status("Undo.")
        else:
            self._set_status("Nothing to undo.")

    def _on_point_colors(self):
        """Let user pick active and unclassified point colors."""
        active = QColorDialog.getColor(
            self._active_color, self, "Active point color")
        if active.isValid():
            self._active_color = active

        unclass = QColorDialog.getColor(
            self._unclassified_color, self, "Unclassified point color")
        if unclass.isValid():
            self._unclassified_color = unclass

        self._canvas.set_point_colors(self._active_color, self._unclassified_color)

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
        key  = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Tab and not (mods & Qt.KeyboardModifier.ShiftModifier):
            self._advance_to_next_unclassified()
        elif key == Qt.Key.Key_Tab and (mods & Qt.KeyboardModifier.ShiftModifier):
            idx = self._canvas._active_index
            if idx > 0:
                self._set_active_point(idx - 1)
        elif key == Qt.Key.Key_Space:
            checked = not self._act_toggle_points.isChecked()
            self._act_toggle_points.setChecked(checked)
            self._on_toggle_points(checked)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Batch lifecycle
    # ------------------------------------------------------------------

    def _start_batch(self, wizard_result: dict):
        cs = Codeset()
        cs.load(wizard_result["codeset_path"])
        self._codeset = cs

        batch = Batch()
        batch.initialize(
            image_dir     = wizard_result["image_dir"],
            codeset_name  = cs.name,
            codeset_path  = wizard_result["codeset_path"],
            batch_metadata= wizard_result["metadata"],
        )
        batch.batch_metadata.update({
            "grid_type": wizard_result["grid_type"],
            "grid_rows": wizard_result["grid_rows"],
            "grid_cols": wizard_result["grid_cols"],
            "grid_n":    wizard_result["grid_n"],
        })

        self._batch = batch
        self._session_filepath = None
        self._unsaved_changes  = True
        self._point_manager    = PointManager()

        self._rebuild_organism_buttons()
        self._load_current_image()
        self._update_ui_state()
        self._update_batch_status()
        self._set_status(
            f"Batch: {batch.total_images} image(s) in "
            f"{os.path.basename(wizard_result['image_dir'])}")

    def _load_batch(self, filepath: str):
        try:
            batch = Batch()
            batch.load(filepath)
            cs = Codeset()
            cs.load(batch.codeset_path)
            self._batch = batch
            self._codeset = cs
            self._session_filepath = filepath
            self._unsaved_changes  = False
            self._point_manager    = PointManager()
            self._rebuild_organism_buttons()
            self._load_current_image()
            self._update_ui_state()
            self._update_batch_status()
            self._set_status(f"Loaded: {os.path.basename(filepath)}")
        except (FileNotFoundError, ValueError, KeyError) as e:
            QMessageBox.critical(self, "Error loading batch", str(e))

    def _save_batch(self, filepath: str):
        if not self._batch:
            return
        self._save_current_image_state()
        try:
            self._batch.save(filepath)
            self._unsaved_changes = False
            self._set_status(f"Saved: {os.path.basename(filepath)}")
        except OSError as e:
            QMessageBox.critical(self, "Error saving", str(e))

    def _save_current_image_state(self):
        if not self._batch or not self._batch.current_image:
            return
        img = self._batch.current_image
        if self._point_manager.points:
            img.store_points(self._point_manager.to_dict())
            img.status = (ImageEntry.STATUS_COMPLETE
                          if self._point_manager.is_complete
                          else ImageEntry.STATUS_IN_PROGRESS
                          if self._point_manager.classified_count > 0
                          else img.status)

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
            self, "Export CSV", suggested, "CSV files (*.csv)")
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"
        try:
            fn = export_detailed if detailed else export_summary
            rows, warnings = fn(self._batch, self._codeset, path)
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
        has_batch  = self._batch is not None
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
        self._act_select_points.setEnabled(has_points)
        self._act_undo.setEnabled(has_points)

    def _update_progress(self):
        total      = self._point_manager.total
        classified = self._point_manager.classified_count
        self._progress_label.setText(f"{classified} / {total} classified")
        self._update_ui_state()

    def _update_batch_status(self):
        if not self._batch:
            self._status_batch.setText("")
            return
        self._status_batch.setText(
            f"Batch: {self._batch.complete_count}/{self._batch.total_images} complete")

    def _update_status(self):
        if not self._batch or not self._batch.current_image:
            return
        idx = self._canvas._active_index
        if 0 <= idx < len(self._point_manager.points):
            p = self._point_manager.points[idx]
            self._set_status(
                f"Point {p.index} / {self._point_manager.total} — "
                f"{p.code or 'unclassified'}")
        self._status_image.setText(
            f"Image {self._batch.current_index + 1} / {self._batch.total_images}")

    def _set_status(self, msg: str):
        self._status_msg.setText(msg)

    def _confirm_discard_changes(self) -> bool:
        if not self._unsaved_changes:
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes", "Discard unsaved changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved changes", "Save before quitting?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Batch")
        self.setMinimumWidth(500)
        self.setFont(APP_FONT)
        self._result: dict = {}
        self._codeset: Codeset | None = None

        layout = QVBoxLayout(self)

        # Step 1
        layout.addWidget(self._section("Step 1: Image Directory and Codeset"))
        form1 = QFormLayout()

        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._browse_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(dir_btn)
        form1.addRow("Image directory:", dir_row)

        self._cs_edit = QLineEdit()
        self._cs_edit.setReadOnly(True)
        cs_btn = QPushButton("Browse...")
        cs_btn.clicked.connect(self._browse_codeset)
        cs_row = QHBoxLayout()
        cs_row.addWidget(self._cs_edit)
        cs_row.addWidget(cs_btn)
        form1.addRow("Codeset file:", cs_row)

        self._img_count = QLabel("No directory selected.")
        form1.addRow("", self._img_count)
        layout.addLayout(form1)

        # Step 2
        layout.addWidget(self._section("Step 2: Grid Configuration"))
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
        form2.addRow("Number of points (random only):", self._grid_n)
        layout.addLayout(form2)

        # Step 3 — populated dynamically after codeset loads
        layout.addWidget(self._section("Step 3: Batch Metadata"))
        self._metadata_form = QFormLayout()
        self._metadata_widgets: dict[str, QWidget] = {}
        layout.addLayout(self._metadata_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setFont(APP_FONT)
        return lbl

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select image directory")
        if path:
            self._dir_edit.setText(path)
            count = sum(1 for f in os.listdir(path)
                        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS)
            self._img_count.setText(f"{count} image(s) found.")

    def _browse_codeset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select codeset", "codesets", "JSON files (*.json)")
        if path:
            try:
                cs = Codeset()
                cs.load(path)
                self._codeset = cs
                self._cs_edit.setText(path)
                self._build_metadata_form()
            except Exception as e:
                QMessageBox.critical(self, "Codeset error", str(e))

    def _build_metadata_form(self):
        while self._metadata_form.rowCount():
            self._metadata_form.removeRow(0)
        self._metadata_widgets.clear()
        if not self._codeset:
            return
        for fd in self._codeset.metadata_fields:
            # Skip per-image fields
            if fd.name in PER_IMAGE_FIELDS:
                continue
            if fd.field_type == "select" and fd.choices:
                w = QComboBox()
                w.addItems(fd.choices)
                w.setFont(APP_FONT)
            else:
                w = QLineEdit()
                w.setFont(APP_FONT)
                if fd.default is not None:
                    w.setText(str(fd.default))
                if fd.required:
                    w.setPlaceholderText("(required)")
            label = fd.label + ("*" if fd.required else "")
            self._metadata_form.addRow(label + ":", w)
            self._metadata_widgets[fd.name] = w

    def _on_grid_type_changed(self, index: int):
        is_random = (index == 2)
        self._grid_rows.setEnabled(not is_random)
        self._grid_cols.setEnabled(not is_random)
        self._grid_n.setEnabled(is_random)

    def _on_accept(self):
        if not self._dir_edit.text():
            QMessageBox.warning(self, "Validation", "Select an image directory.")
            return
        if not self._cs_edit.text():
            QMessageBox.warning(self, "Validation", "Select a codeset file.")
            return

        metadata = {}
        if self._codeset:
            for fd in self._codeset.metadata_fields:
                if fd.name in PER_IMAGE_FIELDS:
                    continue
                w = self._metadata_widgets.get(fd.name)
                if w is None:
                    continue
                if isinstance(w, QComboBox):
                    metadata[fd.name] = w.currentText()
                else:
                    val = w.text().strip()
                    if fd.field_type == "number" and val:
                        try:
                            val = int(val)
                        except ValueError:
                            try:
                                val = float(val)
                            except ValueError:
                                pass
                    metadata[fd.name] = val or None

            # Validate (skip panel_id which is per-image)
            errors = [e for e in self._codeset.validate_metadata(metadata)
                      if "panel" not in e.lower()]
            if errors:
                QMessageBox.warning(
                    self, "Required fields",
                    "Please fill required fields:\n\n" + "\n".join(errors))
                return

        type_map = {
            "Stratified Random": "stratified",
            "Uniform": "uniform",
            "Random": "random"
        }
        self._result = {
            "image_dir":    self._dir_edit.text(),
            "codeset_path": self._cs_edit.text(),
            "metadata":     metadata,
            "grid_type":    type_map[self._grid_type.currentText()],
            "grid_rows":    self._grid_rows.value(),
            "grid_cols":    self._grid_cols.value(),
            "grid_n":       self._grid_n.value(),
        }
        self.accept()

    def result(self) -> dict:
        return self._result
