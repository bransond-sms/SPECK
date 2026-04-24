"""
image_canvas.py
Image display, zoom/pan, boundary drawing, point overlay, rubber-band selection,
grid overlay.

Emits:
    point_activated(int)          -- user clicked a point (0-based index)
    boundary_complete(list)       -- boundary finalized, list of (x,y) image coords
    points_selected(list)         -- rubber-band selection complete, list of 0-based indices
"""

import math
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QPen, QBrush, QFont, QCursor, QFontMetrics
)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

DEFAULT_ACTIVE_COLOR       = QColor(0, 255, 255)       # Cyan
DEFAULT_UNCLASSIFIED_COLOR = QColor(255, 0, 0)         # Red
DEFAULT_SELECTED_COLOR     = QColor(255, 165, 0)       # Orange
BOUNDARY_COLOR             = QColor(255, 200, 0)       # Amber
BOUNDARY_VERTEX_COLOR      = QColor(255, 220, 50)
SELECTION_RECT_COLOR       = QColor(255, 255, 255, 80)
SELECTION_RECT_BORDER      = QColor(255, 255, 255, 200)
GRID_OVERLAY_COLOR         = QColor(255, 255, 255, 50) # Translucent white grid

CROSS_SIZE       = 12   # px half-length, active point (was 8)
CROSS_THICK      = 2    # px line width, active point
CROSS_SMALL      = 8    # px half-length, non-active (was 5)
CROSS_SMALL_THICK = 1   # px line width, non-active
POINT_HIT_RADIUS = 12
FONT_SIZE = 9


class ImageCanvas(QWidget):
    point_activated   = pyqtSignal(int)
    boundary_complete = pyqtSignal(list)
    points_selected   = pyqtSignal(list)

    MODE_VIEW     = "view"
    MODE_BOUNDARY = "boundary"
    MODE_SELECT   = "select"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        self._pixmap: QPixmap | None = None
        self._image_w: int = 0
        self._image_h: int = 0

        self._scale: float = 1.0
        self._offset: QPointF = QPointF(0, 0)
        self._pan_start: QPointF | None = None
        self._pan_offset_start: QPointF | None = None

        self._mode: str = self.MODE_VIEW
        self._boundary_vertices: list[tuple] = []
        self._boundary_final: list[tuple] = []
        self._cursor_pos: QPointF | None = None

        self._select_start: QPointF | None = None
        self._select_rect: QRectF | None = None

        self._points: list = []
        self._active_index: int = -1
        self._selected_indices: set[int] = set()
        self._show_all_points: bool = False
        self._show_grid_overlay: bool = False
        self._code_colors: dict[str, QColor] = {}

        # Grid overlay parameters (set from main_window after grid generation)
        self._grid_type: str = ""
        self._grid_rows: int = 0
        self._grid_cols: int = 0

        self._active_color       = DEFAULT_ACTIVE_COLOR
        self._unclassified_color = DEFAULT_UNCLASSIFIED_COLOR
        self._selected_color     = DEFAULT_SELECTED_COLOR

        self._font = QFont("Arial", FONT_SIZE)
        self._font_metrics = QFontMetrics(self._font)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_image(self, image_path: str) -> bool:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return False
        self._pixmap = pixmap
        self._image_w = pixmap.width()
        self._image_h = pixmap.height()
        self._boundary_vertices = []
        self._boundary_final = []
        self._points = []
        self._active_index = -1
        self._selected_indices = set()
        self._show_grid_overlay = False
        self._fit_to_window()
        self.update()
        return True

    def set_points(self, points: list, code_colors: dict[str, str]) -> None:
        self._points = points
        self._code_colors = {code: QColor(color) for code, color in code_colors.items()}
        self._selected_indices = set()
        self.update()

    def set_active_point(self, index: int) -> None:
        self._active_index = index
        self.update()

    def set_active_point_and_center(self, index: int) -> None:
        """
        Set the active point and, if zoomed in, pan so the point is
        centered in the visible canvas area.
        """
        self._active_index = index
        if 0 <= index < len(self._points):
            point = self._points[index]
            wx, wy = self._image_to_widget(point.x, point.y)
            cw, ch = self.width(), self.height()
            margin = 80  # px from edge before we consider it "out of view"
            if not (margin < wx < cw - margin and margin < wy < ch - margin):
                # Reposition offset so the point lands at canvas center
                self._offset = QPointF(
                    cw / 2 - point.x * self._scale,
                    ch / 2 - point.y * self._scale,
                )
                self._clamp_offset()
        self.update()

    def set_show_all_points(self, show_all: bool) -> None:
        self._show_all_points = show_all
        self.update()

    def set_show_grid_overlay(self, show: bool) -> None:
        self._show_grid_overlay = show
        self.update()

    def set_grid_params(self, grid_type: str, rows: int, cols: int) -> None:
        """Supply grid parameters so the overlay can draw the cell structure."""
        self._grid_type = grid_type
        self._grid_rows = rows
        self._grid_cols = cols

    def set_point_colors(self, active: QColor, unclassified: QColor) -> None:
        self._active_color = active
        self._unclassified_color = unclassified
        self.update()

    def set_boundary(self, vertices: list[tuple]) -> None:
        self._boundary_final = list(vertices)
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.update()

    def get_boundary(self) -> list[tuple]:
        return list(self._boundary_final)

    def clear_boundary(self) -> None:
        self._boundary_final = []
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.update()

    def start_boundary_drawing(self) -> None:
        self._boundary_vertices = []
        self._mode = self.MODE_BOUNDARY
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.update()

    def cancel_boundary_drawing(self) -> None:
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def start_selection_mode(self) -> None:
        self._mode = self.MODE_SELECT
        self._selected_indices = set()
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.update()

    def cancel_selection_mode(self) -> None:
        self._mode = self.MODE_VIEW
        self._select_start = None
        self._select_rect = None
        self._selected_indices = set()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def clear_selection(self) -> None:
        self._selected_indices = set()
        self.update()

    def has_boundary(self) -> bool:
        return len(self._boundary_final) >= 3

    def has_image(self) -> bool:
        return self._pixmap is not None

    def fit_to_window(self) -> None:
        self._fit_to_window()
        self.update()

    # ------------------------------------------------------------------
    # Coordinate mapping
    # ------------------------------------------------------------------

    def _widget_to_image(self, wx: float, wy: float) -> tuple[float, float]:
        ix = (wx - self._offset.x()) / self._scale
        iy = (wy - self._offset.y()) / self._scale
        return ix, iy

    def _image_to_widget(self, ix: float, iy: float) -> tuple[float, float]:
        wx = ix * self._scale + self._offset.x()
        wy = iy * self._scale + self._offset.y()
        return wx, wy

    def _fit_to_window(self) -> None:
        if not self._pixmap:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        self._scale = min(w / self._image_w, h / self._image_h) * 0.95
        self._center_image()

    def _center_image(self) -> None:
        disp_w = self._image_w * self._scale
        disp_h = self._image_h * self._scale
        self._offset = QPointF(
            (self.width() - disp_w) / 2,
            (self.height() - disp_h) / 2,
        )

    def _clamp_offset(self) -> None:
        if not self._pixmap:
            return
        disp_w = self._image_w * self._scale
        disp_h = self._image_h * self._scale
        margin = 50
        ox = max(margin - disp_w, min(self.width() - margin, self._offset.x()))
        oy = max(margin - disp_h, min(self.height() - margin, self._offset.y()))
        self._offset = QPointF(ox, oy)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self._pixmap:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "No image loaded.\nUse File menu to open an image or start a batch.")
            return

        from PyQt6.QtGui import QTransform
        painter.setTransform(
            QTransform()
            .translate(self._offset.x(), self._offset.y())
            .scale(self._scale, self._scale)
        )
        painter.drawPixmap(0, 0, self._pixmap)
        painter.resetTransform()

        # Grid overlay (before boundary so boundary draws on top)
        if self._show_grid_overlay:
            self._draw_grid_overlay(painter)

        # Boundary
        if self._boundary_final:
            self._draw_boundary(painter, self._boundary_final, final=True)
        if self._boundary_vertices:
            self._draw_boundary(painter, self._boundary_vertices, final=False)
            if self._cursor_pos and self._boundary_vertices:
                last = self._boundary_vertices[-1]
                lx, ly = self._image_to_widget(*last)
                painter.setPen(QPen(BOUNDARY_COLOR, 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(lx, ly), self._cursor_pos)

        # Points
        self._draw_points(painter)

        # Rubber-band selection rect
        if self._select_rect:
            painter.setPen(QPen(SELECTION_RECT_BORDER, 1, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(SELECTION_RECT_COLOR))
            painter.drawRect(self._select_rect)

    def _draw_grid_overlay(self, painter: QPainter) -> None:
        """
        Draw a translucent cell grid over the boundary area.
        Only meaningful for uniform and stratified grids.
        For random grids just re-draws the boundary outline.
        """
        if not self._boundary_final or len(self._boundary_final) < 3:
            return

        pen = QPen(GRID_OVERLAY_COLOR, 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Bounding box of the boundary in image space
        xs = [v[0] for v in self._boundary_final]
        ys = [v[1] for v in self._boundary_final]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        rows = max(self._grid_rows, 1)
        cols = max(self._grid_cols, 1)

        if self._grid_type == "random":
            # No grid structure — just highlight the boundary fill
            wpts = [QPointF(*self._image_to_widget(*v)) for v in self._boundary_final]
            from PyQt6.QtGui import QPolygonF
            painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
            painter.drawPolygon(QPolygonF(wpts))
            return

        cell_w = (max_x - min_x) / cols
        cell_h = (max_y - min_y) / rows

        # Draw vertical lines
        for c in range(cols + 1):
            ix = min_x + c * cell_w
            wx1, wy1 = self._image_to_widget(ix, min_y)
            wx2, wy2 = self._image_to_widget(ix, max_y)
            painter.drawLine(QPointF(wx1, wy1), QPointF(wx2, wy2))

        # Draw horizontal lines
        for r in range(rows + 1):
            iy = min_y + r * cell_h
            wx1, wy1 = self._image_to_widget(min_x, iy)
            wx2, wy2 = self._image_to_widget(max_x, iy)
            painter.drawLine(QPointF(wx1, wy1), QPointF(wx2, wy2))

    def _draw_boundary(self, painter, vertices, final):
        if not vertices:
            return
        wpts = [QPointF(*self._image_to_widget(*v)) for v in vertices]
        pen = QPen(BOUNDARY_COLOR, 2 if final else 1,
                   Qt.PenStyle.SolidLine if final else Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(len(wpts) - 1):
            painter.drawLine(wpts[i], wpts[i + 1])
        if final and len(wpts) >= 3:
            painter.drawLine(wpts[-1], wpts[0])
        painter.setBrush(QBrush(BOUNDARY_VERTEX_COLOR))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for pt in wpts:
            painter.drawEllipse(pt, 4, 4)

    def _draw_cross(self, painter, wx, wy, size, thick, color, outline=True):
        if outline:
            painter.setPen(QPen(QColor(0, 0, 0), thick + 2))
            painter.drawLine(QPointF(wx - size, wy), QPointF(wx + size, wy))
            painter.drawLine(QPointF(wx, wy - size), QPointF(wx, wy + size))
        painter.setPen(QPen(color, thick))
        painter.drawLine(QPointF(wx - size, wy), QPointF(wx + size, wy))
        painter.drawLine(QPointF(wx, wy - size), QPointF(wx, wy + size))

    def _draw_points(self, painter):
        if not self._points:
            return
        for i, point in enumerate(self._points):
            is_active   = (i == self._active_index)
            is_selected = (i in self._selected_indices)

            if not self._show_all_points and not is_active and not is_selected:
                continue

            wx, wy = self._image_to_widget(point.x, point.y)

            if is_active:
                color = (self._code_colors.get(point.code, self._active_color)
                         if point.code else self._active_color)
                self._draw_cross(painter, wx, wy, CROSS_SIZE, CROSS_THICK, color)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(
                    QPointF(wx + CROSS_SIZE + 2, wy - CROSS_SIZE), str(point.index))
            elif is_selected:
                self._draw_cross(
                    painter, wx, wy, CROSS_SMALL, CROSS_SMALL_THICK, self._selected_color)
            else:
                color = (self._code_colors.get(point.code, QColor(180, 180, 180))
                         if point.code else self._unclassified_color)
                self._draw_cross(
                    painter, wx, wy, CROSS_SMALL, CROSS_SMALL_THICK, color)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if not self._pixmap:
            return
        pos = event.position()

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = pos
            self._pan_offset_start = QPointF(self._offset)
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.RightButton:
                if self._boundary_vertices:
                    self._boundary_vertices.pop()
                    self.update()
            return

        if self._mode == self.MODE_SELECT:
            if event.button() == Qt.MouseButton.LeftButton:
                self._select_start = pos
                self._select_rect = QRectF(pos, pos)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_point(pos.x(), pos.y())
            if hit is not None:
                self.point_activated.emit(hit)
            else:
                self._pan_start = pos
                self._pan_offset_start = QPointF(self._offset)
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseDoubleClickEvent(self, event):
        if not self._pixmap:
            return
        pos = event.position()
        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.LeftButton:
                ix, iy = self._widget_to_image(pos.x(), pos.y())
                ix = max(0, min(ix, self._image_w))
                iy = max(0, min(iy, self._image_h))
                self._boundary_vertices.append((ix, iy))
                if len(self._boundary_vertices) >= 3:
                    self._boundary_final = list(self._boundary_vertices)
                    self._boundary_vertices = []
                    self._mode = self.MODE_VIEW
                    self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                    self.boundary_complete.emit(self._boundary_final)
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._cursor_pos = pos

        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._offset = self._pan_offset_start + delta
            self._clamp_offset()
            self.update()
            return

        if self._mode == self.MODE_BOUNDARY:
            self.update()
            return

        if self._mode == self.MODE_SELECT and self._select_start is not None:
            self._select_rect = QRectF(self._select_start, pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        pos = event.position()

        if self._pan_start is not None:
            self._pan_start = None
            self._pan_offset_start = None
            cursor = (Qt.CursorShape.CrossCursor
                      if self._mode in (self.MODE_BOUNDARY, self.MODE_SELECT)
                      else Qt.CursorShape.ArrowCursor)
            self.setCursor(QCursor(cursor))
            return

        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.LeftButton:
                ix, iy = self._widget_to_image(pos.x(), pos.y())
                ix = max(0, min(ix, self._image_w))
                iy = max(0, min(iy, self._image_h))
                self._boundary_vertices.append((ix, iy))
                self.update()
            return

        if self._mode == self.MODE_SELECT:
            if event.button() == Qt.MouseButton.LeftButton and self._select_rect:
                hits = [
                    i for i, point in enumerate(self._points)
                    if self._select_rect.contains(
                        QPointF(*self._image_to_widget(point.x, point.y)))
                ]
                self._selected_indices = set(hits)
                self._select_start = None
                self._select_rect = None
                self._mode = self.MODE_VIEW
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                self.update()
                if hits:
                    self.points_selected.emit(hits)

    def wheelEvent(self, event):
        if not self._pixmap:
            return
        pos = event.position()
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_scale = max(0.05, min(self._scale * factor, 20.0))
        factor = new_scale / self._scale
        self._offset = QPointF(
            pos.x() - factor * (pos.x() - self._offset.x()),
            pos.y() - factor * (pos.y() - self._offset.y()),
        )
        self._scale = new_scale
        self._clamp_offset()
        self.update()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._mode == self.MODE_BOUNDARY:
                self.cancel_boundary_drawing()
            elif self._mode == self.MODE_SELECT:
                self.cancel_selection_mode()
        elif event.key() == Qt.Key.Key_F:
            self.fit_to_window()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self._fit_to_window()

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def _hit_test_point(self, wx: float, wy: float) -> int | None:
        best_idx = None
        best_dist = float("inf")
        for i, point in enumerate(self._points):
            if not self._show_all_points and i != self._active_index:
                continue
            px, py = self._image_to_widget(point.x, point.y)
            dist = math.hypot(wx - px, wy - py)
            if dist < POINT_HIT_RADIUS and dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx
