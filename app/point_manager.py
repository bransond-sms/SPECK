"""
point_manager.py
Grid generation (uniform, random, stratified random) and point classification state.
No PyQt6 dependency — pure Python for testability.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Point:
    """Represents a single point in the grid."""
    x: float                          # Image pixel coordinate (unscaled)
    y: float                          # Image pixel coordinate (unscaled)
    index: int                        # Display index (1-based for UI)
    code: Optional[str] = None        # Assigned organism code, or None if unclassified
    classified_at: Optional[float] = None  # Unix timestamp of classification
    notes: Optional[str] = None       # Per-point analyst note (for QC, future use)

    @property
    def is_classified(self) -> bool:
        return self.code is not None


class PointManager:
    """
    Owns point grid generation and classification state for a single image session.

    Boundary is always passed as a list of (x, y) tuples. For rectangles, pass
    the four corners. For polygons, pass all vertices. Point containment uses
    the same ray-casting method regardless of shape.
    """

    def __init__(self):
        self._points: list[Point] = []
        self._undo_stack: list[tuple[int, Optional[str], Optional[float]]] = []
        # Each undo entry is (point_index, previous_code, previous_classified_at)

    # ------------------------------------------------------------------
    # Grid generation
    # ------------------------------------------------------------------

    def generate_uniform(self, rows: int, cols: int, boundary: list[tuple]) -> None:
        """
        Place points on a uniform grid within the boundary.
        Points are numbered sequentially left-to-right, top-to-bottom.
        """
        self._clear()
        min_x, min_y, max_x, max_y = self._bounding_box(boundary)
        cell_w = (max_x - min_x) / cols
        cell_h = (max_y - min_y) / rows

        idx = 1
        for r in range(rows):
            for c in range(cols):
                x = min_x + (c + 0.5) * cell_w
                y = min_y + (r + 0.5) * cell_h
                if self._point_in_boundary(x, y, boundary):
                    self._points.append(Point(x=x, y=y, index=idx))
                    idx += 1

    def generate_random(self, n: int, boundary: list[tuple]) -> None:
        """
        Place n points at random positions within the boundary.
        Points are numbered in the order they were generated (random).
        """
        self._clear()
        min_x, min_y, max_x, max_y = self._bounding_box(boundary)
        placed = 0
        max_attempts = n * 50  # Safety limit to avoid infinite loop on odd boundaries
        attempts = 0

        while placed < n and attempts < max_attempts:
            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)
            if self._point_in_boundary(x, y, boundary):
                self._points.append(Point(x=x, y=y, index=placed + 1))
                placed += 1
            attempts += 1

    def generate_stratified(self, rows: int, cols: int, boundary: list[tuple]) -> None:
        """
        Divide the boundary into a rows x cols grid of cells.
        Place one point at a random position within each cell.
        Points are numbered randomly across the full set (CPCe behavior).
        """
        self._clear()
        min_x, min_y, max_x, max_y = self._bounding_box(boundary)
        cell_w = (max_x - min_x) / cols
        cell_h = (max_y - min_y) / rows

        candidates = []
        for r in range(rows):
            for c in range(cols):
                cell_min_x = min_x + c * cell_w
                cell_min_y = min_y + r * cell_h
                cell_max_x = cell_min_x + cell_w
                cell_max_y = cell_min_y + cell_h

                # Try to place a point randomly within this cell
                placed = False
                for _ in range(50):
                    x = random.uniform(cell_min_x, cell_max_x)
                    y = random.uniform(cell_min_y, cell_max_y)
                    if self._point_in_boundary(x, y, boundary):
                        candidates.append((x, y))
                        placed = True
                        break

                if not placed:
                    # Cell is entirely outside boundary (edge case for polygons)
                    # Fall back to cell center if it's inside, otherwise skip
                    cx = (cell_min_x + cell_max_x) / 2
                    cy = (cell_min_y + cell_max_y) / 2
                    if self._point_in_boundary(cx, cy, boundary):
                        candidates.append((cx, cy))

        # Shuffle and assign random numbering (CPCe stratified random behavior)
        random.shuffle(candidates)
        for idx, (x, y) in enumerate(candidates, start=1):
            self._points.append(Point(x=x, y=y, index=idx))

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, point_index: int, code: str) -> None:
        """
        Assign a code to a point (0-based internal index).
        Pushes previous state onto the undo stack.
        """
        point = self._points[point_index]
        self._undo_stack.append((point_index, point.code, point.classified_at))
        point.code = code
        point.classified_at = time.time()

    def undo(self) -> Optional[int]:
        """
        Undo the most recent classification.
        Returns the 0-based index of the affected point, or None if stack is empty.
        """
        if not self._undo_stack:
            return None
        point_index, previous_code, previous_classified_at = self._undo_stack.pop()
        point = self._points[point_index]
        point.code = previous_code
        point.classified_at = previous_classified_at
        return point_index

    def clear_classification(self, point_index: int) -> None:
        """Clear the classification for a single point without undo stack entry."""
        self._points[point_index].code = None
        self._points[point_index].classified_at = None

    # ------------------------------------------------------------------
    # Progress and access
    # ------------------------------------------------------------------

    @property
    def points(self) -> list[Point]:
        return self._points

    @property
    def total(self) -> int:
        return len(self._points)

    @property
    def classified_count(self) -> int:
        return sum(1 for p in self._points if p.is_classified)

    @property
    def unclassified_indices(self) -> list[int]:
        """Returns 0-based indices of unclassified points."""
        return [i for i, p in enumerate(self._points) if not p.is_classified]

    @property
    def is_complete(self) -> bool:
        return self.total > 0 and self.classified_count == self.total

    def next_unclassified(self, after_index: int = -1) -> Optional[int]:
        """
        Returns the 0-based index of the next unclassified point after after_index.
        Wraps around to the beginning if needed. Returns None if all classified.
        """
        unclassified = self.unclassified_indices
        if not unclassified:
            return None
        for i in unclassified:
            if i > after_index:
                return i
        return unclassified[0]

    def get_summary(self) -> dict[str, int]:
        """
        Returns a dict of {code: count} for all classified points.
        Suitable for display and for driving CSV export.
        """
        summary = {}
        for p in self._points:
            if p.code:
                summary[p.code] = summary.get(p.code, 0) + 1
        return summary

    # ------------------------------------------------------------------
    # Serialization (for session save/resume)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize point state to a plain dict for JSON storage."""
        return {
            "points": [
                {
                    "x": p.x,
                    "y": p.y,
                    "index": p.index,
                    "code": p.code,
                    "classified_at": p.classified_at,
                    "notes": p.notes,
                }
                for p in self._points
            ]
        }

    def from_dict(self, data: dict) -> None:
        """Restore point state from a plain dict (loaded from JSON session file)."""
        self._clear()
        for entry in data.get("points", []):
            self._points.append(Point(
                x=entry["x"],
                y=entry["y"],
                index=entry["index"],
                code=entry.get("code"),
                classified_at=entry.get("classified_at"),
                notes=entry.get("notes"),
            ))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        self._points = []
        self._undo_stack = []

    @staticmethod
    def _bounding_box(boundary: list[tuple]) -> tuple[float, float, float, float]:
        """Returns (min_x, min_y, max_x, max_y) of the boundary vertices."""
        xs = [v[0] for v in boundary]
        ys = [v[1] for v in boundary]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _point_in_boundary(x: float, y: float, boundary: list[tuple]) -> bool:
        """
        Ray-casting algorithm for point-in-polygon test.
        Works for both rectangles (4 vertices) and arbitrary polygons.
        """
        n = len(boundary)
        inside = False
        px, py = x, y
        j = n - 1
        for i in range(n):
            xi, yi = boundary[i]
            xj, yj = boundary[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
