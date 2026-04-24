"""
image_canvas.py
Image display, zoom/pan, boundary drawing, and point overlay.

Emits:
    point_activated(int)       -- user clicked a point on the canvas (0-based index)
    boundary_complete(list)    -- boundary finalized, list of (x, y) image coordinates
    request_classify(int)      -- user double-clicked a point (0-based index)
"""

import math
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QPen, QBrush, QFont,
    QTransform, QCursor, QFontMetrics
)


# Visual constants
POINT_RADIUS = 5          # px, active point
POINT_RADIUS_SMALL = 4    # px, classified points in all-points mode
POINT_HIT_RADIUS = 12     # px, click detection radius
ACTIVE_POINT_COLOR = QColor(255, 255, 0)        # Yellow — active unclassified
UNCLASSIFIED_COLOR = QColor(200, 200, 200, 180) # Light gray — unclassified
BOUNDARY_COLOR = QColor(255, 200, 0)            # Amber boundary line
BOUNDARY_VERTEX_COLOR = QColor(255, 220, 50)
BOUNDARY_PENDING_COLOR = QColor(255, 200, 0, 120)
FONT_SIZE = 9


class ImageCanvas(QWidget):
    """
    Custom widget for image display, boundary drawing, and point overlay.
    All coordinates stored internally are image-space (unscaled).
    Display uses a QTransform to map image coords to widget coords.
    """

    point_activated = pyqtSignal(int)       # 0-based point index
    boundary_complete = pyqtSignal(list)    # list of (x, y) tuples in image space
    request_classify = pyqtSignal(int)      # 0-based point index (double-click)

    # Canvas modes
    MODE_VIEW = "view"
    MODE_BOUNDARY = "boundary"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

        # Image state
        self._pixmap: QPixmap | None = None
        self._image_w: int = 0
        self._image_h: int = 0

        # Transform state (zoom + pan)
        self._scale: float = 1.0
        self._offset: QPointF = QPointF(0, 0)
        self._pan_start: QPointF | None = None
        self._pan_offset_start: QPointF | None = None

        # Boundary state
        self._mode: str = self.MODE_VIEW
        self._boundary_vertices: list[tuple] = []   # image-space coords
        self._boundary_final: list[tuple] = []      # finalized boundary
        self._cursor_pos: QPointF | None = None     # for rubber-band line

        # Point display state
        self._points: list = []          # list of Point objects from PointManager
        self._active_index: int = -1     # 0-based
        self._show_all_points: bool = False
        self._code_colors: dict[str, QColor] = {}  # code -> QColor cache

        # Font
        self._font = QFont("Arial", FONT_SIZE)
        self._font_metrics = QFontMetrics(self._font)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_image(self, image_path: str) -> bool:
        """Load an image from disk. Returns True on success."""
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
        self._fit_to_window()
        self.update()
        return True

    def set_points(self, points: list, code_colors: dict[str, str]) -> None:
        """
        Set the point list from PointManager.points.
        code_colors: dict of {code: hex_color_string}
        """
        self._points = points
        self._code_colors = {
            code: QColor(color) for code, color in code_colors.items()
        }
        self.update()

    def set_active_point(self, index: int) -> None:
        """Set which point is currently active (0-based index)."""
        self._active_index = index
        self.update()

    def set_show_all_points(self, show_all: bool) -> None:
        """Toggle between showing all points and active point only."""
        self._show_all_points = show_all
        self.update()

    def set_boundary(self, vertices: list[tuple]) -> None:
        """
        Restore a saved boundary (e.g. from session load or copy-from-previous).
        vertices: list of (x, y) in image space.
        """
        self._boundary_final = list(vertices)
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.update()

    def get_boundary(self) -> list[tuple]:
        """Return the current finalized boundary vertices in image space."""
        return list(self._boundary_final)

    def clear_boundary(self) -> None:
        """Remove the current boundary and any in-progress drawing."""
        self._boundary_final = []
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.update()

    def start_boundary_drawing(self) -> None:
        """Enter boundary drawing mode."""
        self._boundary_vertices = []
        self._mode = self.MODE_BOUNDARY
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.update()

    def cancel_boundary_drawing(self) -> None:
        """Cancel in-progress boundary drawing without clearing finalized boundary."""
        self._boundary_vertices = []
        self._mode = self.MODE_VIEW
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def has_boundary(self) -> bool:
        return len(self._boundary_final) >= 3

    def has_image(self) -> bool:
        return self._pixmap is not None

    # ------------------------------------------------------------------
    # Coordinate mapping
    # ------------------------------------------------------------------

    def _widget_to_image(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert widget coordinates to image-space coordinates."""
        ix = (wx - self._offset.x()) / self._scale
        iy = (wy - self._offset.y()) / self._scale
        return ix, iy

    def _image_to_widget(self, ix: float, iy: float) -> tuple[float, float]:
        """Convert image-space coordinates to widget coordinates."""
        wx = ix * self._scale + self._offset.x()
        wy = iy * self._scale + self._offset.y()
        return wx, wy

    def _fit_to_window(self) -> None:
        """Scale and center the image to fit the widget."""
        if not self._pixmap:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        scale_x = w / self._image_w
        scale_y = h / self._image_h
        self._scale = min(scale_x, scale_y) * 0.95
        self._center_image()

    def _center_image(self) -> None:
        """Center the image in the widget at current scale."""
        disp_w = self._image_w * self._scale
        disp_h = self._image_h * self._scale
        self._offset = QPointF(
            (self.width() - disp_w) / 2,
            (self.height() - disp_h) / 2,
        )

    def _clamp_offset(self) -> None:
        """Prevent panning the image entirely off screen."""
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

        # Background
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self._pixmap:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No image loaded")
            return

        # Draw image
        painter.setTransform(
            QTransform()
            .translate(self._offset.x(), self._offset.y())
            .scale(self._scale, self._scale)
        )
        painter.drawPixmap(0, 0, self._pixmap)
        painter.resetTransform()

        # Draw finalized boundary
        if self._boundary_final:
            self._draw_boundary(painter, self._boundary_final, final=True)

        # Draw in-progress boundary
        if self._boundary_vertices:
            self._draw_boundary(painter, self._boundary_vertices, final=False)
            # Rubber-band line from last vertex to cursor
            if self._cursor_pos and len(self._boundary_vertices) >= 1:
                last = self._boundary_vertices[-1]
                lx, ly = self._image_to_widget(*last)
                pen = QPen(BOUNDARY_COLOR, 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(
                    QPointF(lx, ly), self._cursor_pos
                )

        # Draw points
        self._draw_points(painter)

    def _draw_boundary(self, painter: QPainter,
                       vertices: list[tuple], final: bool) -> None:
        if len(vertices) < 1:
            return

        widget_pts = [QPointF(*self._image_to_widget(*v)) for v in vertices]

        pen = QPen(BOUNDARY_COLOR, 2 if final else 1,
                   Qt.PenStyle.SolidLine if final else Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw lines between vertices
        for i in range(len(widget_pts) - 1):
            painter.drawLine(widget_pts[i], widget_pts[i + 1])

        # Close the polygon if final
        if final and len(widget_pts) >= 3:
            painter.drawLine(widget_pts[-1], widget_pts[0])

        # Draw vertex markers
        painter.setBrush(QBrush(BOUNDARY_VERTEX_COLOR))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        for pt in widget_pts:
            painter.drawEllipse(pt, 4, 4)

    def _draw_points(self, painter: QPainter) -> None:
        if not self._points:
            return

        for i, point in enumerate(self._points):
            is_active = (i == self._active_index)

            # Decide whether to draw this point
            if not self._show_all_points and not is_active:
                continue

            wx, wy = self._image_to_widget(point.x, point.y)
            wpt = QPointF(wx, wy)

            if is_active:
                # Active point — larger, bright outline
                radius = POINT_RADIUS + 2
                color = (self._code_colors.get(point.code, ACTIVE_POINT_COLOR)
                         if point.code else ACTIVE_POINT_COLOR)
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(wpt, radius, radius)

                # Point number label
                label = str(point.index)
                lx = wx + radius + 2
                ly = wy - radius
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(QPointF(lx, ly), label)

            else:
                # Non-active point
                radius = POINT_RADIUS_SMALL
                if point.code:
                    color = self._code_colors.get(point.code, QColor(180, 180, 180))
                    painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
                    painter.setBrush(QBrush(color))
                else:
                    painter.setPen(QPen(QColor(200, 200, 200), 1))
                    painter.setBrush(QBrush(UNCLASSIFIED_COLOR))
                painter.drawEllipse(wpt, radius, radius)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if not self._pixmap:
            return

        pos = event.position()

        if event.button() == Qt.MouseButton.MiddleButton:
            # Start pan
            self._pan_start = pos
            self._pan_offset_start = QPointF(self._offset)
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.RightButton:
                # Remove last vertex
                if self._boundary_vertices:
                    self._boundary_vertices.pop()
                    self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking near a point
            hit = self._hit_test_point(pos.x(), pos.y())
            if hit is not None:
                self.point_activated.emit(hit)
            else:
                # Start pan with left button when not hitting a point
                self._pan_start = pos
                self._pan_offset_start = QPointF(self._offset)
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseDoubleClickEvent(self, event):
        if not self._pixmap:
            return

        pos = event.position()

        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.LeftButton:
                # Place final vertex and close
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
            return

        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_point(pos.x(), pos.y())
            if hit is not None:
                self.request_classify.emit(hit)

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._cursor_pos = pos

        # Pan
        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._offset = self._pan_offset_start + delta
            self._clamp_offset()
            self.update()
            return

        if self._mode == self.MODE_BOUNDARY:
            self.update()

    def mouseReleaseEvent(self, event):
        pos = event.position()

        if self._pan_start is not None:
            self._pan_start = None
            self._pan_offset_start = None
            if self._mode == self.MODE_BOUNDARY:
                self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        if self._mode == self.MODE_BOUNDARY:
            if event.button() == Qt.MouseButton.LeftButton:
                ix, iy = self._widget_to_image(pos.x(), pos.y())
                ix = max(0, min(ix, self._image_w))
                iy = max(0, min(iy, self._image_h))
                self._boundary_vertices.append((ix, iy))
                self.update()

    def wheelEvent(self, event):
        if not self._pixmap:
            return

        # Zoom centered on cursor position
        pos = event.position()
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15

        new_scale = self._scale * factor
        new_scale = max(0.05, min(new_scale, 20.0))
        factor = new_scale / self._scale

        # Adjust offset so zoom centers on cursor
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
            self.cancel_boundary_drawing()
        elif event.key() == Qt.Key.Key_F:
            # F to fit image to window
            self._fit_to_window()
            self.update()
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
        """
        Return the 0-based index of the point closest to widget coords (wx, wy)
        within POINT_HIT_RADIUS, or None if no point is close enough.
        Prefers the active point in case of tie.
        """
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
