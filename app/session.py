"""
session.py
Session save/resume (.speck files) and metadata management.
No PyQt6 dependency — pure Python for testability.

A .speck file covers an entire batch (one directory of images).
Top-level structure:
{
    "speck_version": "1.0",
    "codeset_name": "...",
    "codeset_path": "...",
    "batch_metadata": { field_name: value, ... },
    "image_dir": "...",
    "created_at": float,
    "saved_at": float,
    "images": [
        {
            "image_path": "...",
            "panel_id": "...",
            "status": "untouched" | "in_progress" | "complete",
            "boundary": [[x, y], ...],
            "grid_type": "uniform" | "random" | "stratified",
            "grid_rows": int,
            "grid_cols": int,
            "grid_n": int,
            "points": { point data }
        },
        ...
    ]
}
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


@dataclass
class MetadataFieldDef:
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    default: Any = None
    choices: list[str] = field(default_factory=list)


class ImageEntry:
    STATUS_UNTOUCHED = "untouched"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETE = "complete"

    def __init__(self, image_path: str):
        self.image_path: str = image_path
        self.panel_id: str = os.path.splitext(os.path.basename(image_path))[0]
        self.status: str = self.STATUS_UNTOUCHED
        self.boundary: list[tuple[float, float]] = []
        self.grid_type: str = ""
        self.grid_rows: int = 0
        self.grid_cols: int = 0
        self.grid_n: int = 0
        self._point_data: dict = {}

    @property
    def image_filename(self) -> str:
        return os.path.basename(self.image_path)

    @property
    def is_complete(self) -> bool:
        return self.status == self.STATUS_COMPLETE

    @property
    def is_untouched(self) -> bool:
        return self.status == self.STATUS_UNTOUCHED

    def store_points(self, point_dict: dict) -> None:
        self._point_data = point_dict

    def get_point_data(self) -> dict:
        return self._point_data

    def to_dict(self) -> dict:
        return {
            "image_path": self.image_path,
            "panel_id": self.panel_id,
            "status": self.status,
            "boundary": [list(v) for v in self.boundary],
            "grid_type": self.grid_type,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "grid_n": self.grid_n,
            "points": self._point_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImageEntry":
        entry = cls(data["image_path"])
        entry.panel_id = data.get("panel_id", entry.panel_id)
        entry.status = data.get("status", cls.STATUS_UNTOUCHED)
        entry.boundary = [tuple(v) for v in data.get("boundary", [])]
        entry.grid_type = data.get("grid_type", "")
        entry.grid_rows = data.get("grid_rows", 0)
        entry.grid_cols = data.get("grid_cols", 0)
        entry.grid_n = data.get("grid_n", 0)
        entry._point_data = data.get("points", {})
        return entry


class Batch:
    SPECK_VERSION = "1.0"

    def __init__(self):
        self.speck_version: str = self.SPECK_VERSION
        self.codeset_name: str = ""
        self.codeset_path: str = ""
        self.batch_metadata: dict[str, Any] = {}
        self.image_dir: str = ""
        self.images: list[ImageEntry] = []
        self.created_at: Optional[float] = None
        self.saved_at: Optional[float] = None
        self._current_index: int = 0

    def initialize(
        self,
        image_dir: str,
        codeset_name: str,
        codeset_path: str,
        batch_metadata: dict[str, Any],
    ) -> None:
        self.image_dir = image_dir
        self.codeset_name = codeset_name
        self.codeset_path = codeset_path
        self.batch_metadata = batch_metadata
        self.created_at = time.time()
        self.saved_at = None
        self._current_index = 0
        self.images = self._scan_directory(image_dir)

    @staticmethod
    def _scan_directory(directory: str) -> list[ImageEntry]:
        entries = []
        for fname in sorted(os.listdir(directory)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                entries.append(ImageEntry(os.path.join(directory, fname)))
        return entries

    @property
    def current_image(self) -> Optional[ImageEntry]:
        if not self.images:
            return None
        return self.images[self._current_index]

    @property
    def current_index(self) -> int:
        return self._current_index

    def go_to(self, index: int) -> bool:
        if 0 <= index < len(self.images):
            self._current_index = index
            return True
        return False

    def next_image(self) -> bool:
        if self._current_index < len(self.images) - 1:
            self._current_index += 1
            return True
        return False

    def previous_image(self) -> bool:
        if self._current_index > 0:
            self._current_index -= 1
            return True
        return False

    def next_incomplete(self) -> bool:
        n = len(self.images)
        for offset in range(1, n + 1):
            idx = (self._current_index + offset) % n
            if not self.images[idx].is_complete:
                self._current_index = idx
                return True
        return False

    @property
    def total_images(self) -> int:
        return len(self.images)

    @property
    def complete_count(self) -> int:
        return sum(1 for img in self.images if img.is_complete)

    @property
    def in_progress_count(self) -> int:
        return sum(1 for img in self.images
                   if img.status == ImageEntry.STATUS_IN_PROGRESS)

    @property
    def is_batch_complete(self) -> bool:
        return self.total_images > 0 and self.complete_count == self.total_images

    def save(self, filepath: str) -> None:
        self.saved_at = time.time()
        data = {
            "speck_version": self.SPECK_VERSION,
            "codeset_name": self.codeset_name,
            "codeset_path": self.codeset_path,
            "batch_metadata": self.batch_metadata,
            "image_dir": self.image_dir,
            "current_index": self._current_index,
            "created_at": self.created_at,
            "saved_at": self.saved_at,
            "images": [img.to_dict() for img in self.images],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str) -> None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Session file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "speck_version" not in data:
            raise ValueError(f"Not a valid SPECK session file: {filepath}")
        self.speck_version = data.get("speck_version", self.SPECK_VERSION)
        self.codeset_name = data.get("codeset_name", "")
        self.codeset_path = data.get("codeset_path", "")
        self.batch_metadata = data.get("batch_metadata", {})
        self.image_dir = data.get("image_dir", "")
        self.created_at = data.get("created_at")
        self.saved_at = data.get("saved_at")
        self._current_index = data.get("current_index", 0)
        self.images = [ImageEntry.from_dict(d) for d in data.get("images", [])]

    @property
    def display_name(self) -> str:
        return os.path.basename(self.image_dir) or "Untitled batch"

    @property
    def is_new(self) -> bool:
        return self.saved_at is None


class Codeset:
    def __init__(self):
        self.name: str = ""
        self.version: str = ""
        self.description: str = ""
        self.author: str = ""
        self.codes: list[dict] = []
        self.metadata_fields: list[MetadataFieldDef] = []
        self._code_map: dict[str, dict] = {}

    def load(self, filepath: str) -> None:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Codeset file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.name = data.get("name", "")
        self.version = data.get("version", "")
        self.description = data.get("description", "")
        self.author = data.get("author", "")
        self.codes = data.get("codes", [])
        self._code_map = {c["code"]: c for c in self.codes}
        self.metadata_fields = []
        for fd in data.get("metadata_fields", []):
            self.metadata_fields.append(MetadataFieldDef(
                name=fd.get("name", ""),
                label=fd.get("label", fd.get("name", "")),
                field_type=fd.get("field_type", "text"),
                required=fd.get("required", False),
                default=fd.get("default", None),
                choices=fd.get("choices", []),
            ))

    def get_code(self, code: str) -> Optional[dict]:
        return self._code_map.get(code)

    def get_color(self, code: str) -> str:
        entry = self._code_map.get(code)
        return entry["color"] if entry else "#888888"

    def get_name(self, code: str) -> str:
        entry = self._code_map.get(code)
        return entry["name"] if entry else code

    def empty_metadata(self) -> dict[str, Any]:
        return {f.name: f.default for f in self.metadata_fields}

    def validate_metadata(self, metadata: dict[str, Any]) -> list[str]:
        errors = []
        for f in self.metadata_fields:
            if f.required:
                val = metadata.get(f.name)
                if val is None or str(val).strip() == "":
                    errors.append(f"'{f.label}' is required.")
        return errors
