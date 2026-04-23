"""
session.py
Session save/resume (.speck files) and metadata management.
No PyQt6 dependency — pure Python for testability.

A .speck file is a JSON file with the following top-level structure:
{
    "speck_version": "1.0",
    "codeset_name": "...",
    "metadata": { field_name: value, ... },
    "image_path": "...",
    "boundary": [[x, y], ...],
    "grid_type": "uniform" | "random" | "stratified",
    "grid_rows": int,
    "grid_cols": int,
    "grid_n": int,
    "points": { point data }
}
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional


# ------------------------------------------------------------------
# Metadata field definitions
# ------------------------------------------------------------------

@dataclass
class MetadataFieldDef:
    """
    Definition of a single metadata field, loaded from the codeset.
    field_type: "text" | "number" | "date" | "select"
    choices: list of strings, only used when field_type == "select"
    """
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    default: Any = None
    choices: list[str] = field(default_factory=list)


# ------------------------------------------------------------------
# Session
# ------------------------------------------------------------------

class Session:
    """
    Holds all state for a single image annotation session.
    Handles save/resume via .speck files (JSON).
    """

    SPECK_VERSION = "1.0"

    def __init__(self):
        self.speck_version: str = self.SPECK_VERSION
        self.codeset_name: str = ""
        self.metadata: dict[str, Any] = {}
        self.image_path: str = ""
        self.boundary: list[tuple[float, float]] = []
        self.grid_type: str = ""         # "uniform" | "random" | "stratified"
        self.grid_rows: int = 0
        self.grid_cols: int = 0
        self.grid_n: int = 0             # Used for random grid (number of points)
        self.created_at: Optional[float] = None
        self.saved_at: Optional[float] = None
        self._point_data: dict = {}      # Raw dict from PointManager.to_dict()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def initialize(
        self,
        image_path: str,
        codeset_name: str,
        metadata: dict[str, Any],
        boundary: list[tuple],
        grid_type: str,
        grid_rows: int = 0,
        grid_cols: int = 0,
        grid_n: int = 0,
    ) -> None:
        """Called when a new session is started."""
        self.image_path = image_path
        self.codeset_name = codeset_name
        self.metadata = metadata
        self.boundary = boundary
        self.grid_type = grid_type
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.grid_n = grid_n
        self.created_at = time.time()
        self.saved_at = None
        self._point_data = {}

    def store_points(self, point_dict: dict) -> None:
        """Store serialized point state from PointManager.to_dict()."""
        self._point_data = point_dict

    def get_point_data(self) -> dict:
        """Retrieve stored point data for restoring into a PointManager."""
        return self._point_data

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, filepath: str) -> None:
        """
        Save the session to a .speck file.
        filepath should end in .speck but is not enforced.
        """
        self.saved_at = time.time()
        data = {
            "speck_version": self.SPECK_VERSION,
            "codeset_name": self.codeset_name,
            "metadata": self.metadata,
            "image_path": self.image_path,
            "boundary": [list(v) for v in self.boundary],
            "grid_type": self.grid_type,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "grid_n": self.grid_n,
            "created_at": self.created_at,
            "saved_at": self.saved_at,
            "points": self._point_data,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, filepath: str) -> None:
        """
        Load a session from a .speck file.
        Raises FileNotFoundError if the file does not exist.
        Raises ValueError if the file is not a valid .speck file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Session file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "speck_version" not in data:
            raise ValueError(f"Not a valid SPECK session file: {filepath}")

        self.speck_version = data.get("speck_version", self.SPECK_VERSION)
        self.codeset_name = data.get("codeset_name", "")
        self.metadata = data.get("metadata", {})
        self.image_path = data.get("image_path", "")
        raw_boundary = data.get("boundary", [])
        self.boundary = [tuple(v) for v in raw_boundary]
        self.grid_type = data.get("grid_type", "")
        self.grid_rows = data.get("grid_rows", 0)
        self.grid_cols = data.get("grid_cols", 0)
        self.grid_n = data.get("grid_n", 0)
        self.created_at = data.get("created_at")
        self.saved_at = data.get("saved_at")
        self._point_data = data.get("points", {})

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def image_filename(self) -> str:
        """Just the filename portion of the image path, for display and export."""
        return os.path.basename(self.image_path)

    @property
    def is_new(self) -> bool:
        return self.saved_at is None

    @property
    def display_name(self) -> str:
        """
        Short human-readable session identifier for window titles and lists.
        Uses panel_id from metadata if available, otherwise the image filename.
        """
        return self.metadata.get("panel_id") or self.image_filename or "Untitled session"


# ------------------------------------------------------------------
# Codeset loader
# ------------------------------------------------------------------

class Codeset:
    """
    Loads and holds a codeset JSON file.
    Provides organism code lookup and metadata field definitions.
    """

    def __init__(self):
        self.name: str = ""
        self.version: str = ""
        self.description: str = ""
        self.author: str = ""
        self.codes: list[dict] = []           # Raw list of code dicts from JSON
        self.metadata_fields: list[MetadataFieldDef] = []
        self._code_map: dict[str, dict] = {}  # code -> full dict, for fast lookup

    def load(self, filepath: str) -> None:
        """
        Load a codeset from a JSON file.
        Raises FileNotFoundError or ValueError on bad input.
        """
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

        # Parse metadata field definitions if present
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
        """Return the full code dict for a given code string, or None."""
        return self._code_map.get(code)

    def get_color(self, code: str) -> str:
        """Return the hex color for a code, or a default gray if not found."""
        entry = self._code_map.get(code)
        return entry["color"] if entry else "#888888"

    def get_name(self, code: str) -> str:
        """Return the display name for a code, or the code itself if not found."""
        entry = self._code_map.get(code)
        return entry["name"] if entry else code

    def empty_metadata(self) -> dict[str, Any]:
        """Return a dict of {field_name: default_value} for initializing a new session."""
        return {f.name: f.default for f in self.metadata_fields}

    def validate_metadata(self, metadata: dict[str, Any]) -> list[str]:
        """
        Check that all required fields are filled.
        Returns a list of error strings. Empty list means valid.
        """
        errors = []
        for f in self.metadata_fields:
            if f.required:
                val = metadata.get(f.name)
                if val is None or str(val).strip() == "":
                    errors.append(f"'{f.label}' is required.")
        return errors
