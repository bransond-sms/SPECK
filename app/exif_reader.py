"""
exif_reader.py
EXIF metadata extraction from image files using Pillow.
Provides GPS coordinates, altitude, and datetime.
No PyQt6 dependency — pure Python.

Public API:
    read_exif(image_path)  ->  ExifData dataclass
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


@dataclass
class ExifData:
    """Holds extracted EXIF values. All fields optional — None if not present."""
    gps_lat:    Optional[float] = None   # Decimal degrees, positive = N
    gps_lon:    Optional[float] = None   # Decimal degrees, positive = E
    gps_alt:    Optional[float] = None   # Metres above sea level (negative = below)
    datetime_taken: Optional[datetime] = None
    camera_make:  Optional[str] = None
    camera_model: Optional[str] = None

    @property
    def has_gps(self) -> bool:
        return self.gps_lat is not None and self.gps_lon is not None

    @property
    def has_datetime(self) -> bool:
        return self.datetime_taken is not None

    @property
    def retrieval_year(self) -> Optional[int]:
        return self.datetime_taken.year if self.datetime_taken else None

    @property
    def retrieval_month(self) -> Optional[int]:
        return self.datetime_taken.month if self.datetime_taken else None

    @property
    def retrieval_day(self) -> Optional[int]:
        return self.datetime_taken.day if self.datetime_taken else None


def read_exif(image_path: str) -> ExifData:
    """
    Extract EXIF metadata from an image file.
    Returns an ExifData instance. Fields are None if not present or unreadable.
    Never raises — returns empty ExifData on any error.
    """
    result = ExifData()

    if not os.path.exists(image_path):
        return result

    try:
        with Image.open(image_path) as img:
            exif_data = img.getexif()
            if not exif_data:
                return result

            # Map numeric tag IDs to names
            exif = {TAGS.get(tag, tag): value for tag, value in exif_data.items()}

            # --- DateTime ---
            for dt_field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                if dt_field in exif:
                    try:
                        result.datetime_taken = datetime.strptime(
                            str(exif[dt_field]), "%Y:%m:%d %H:%M:%S"
                        )
                        break
                    except ValueError:
                        continue

            # --- Camera ---
            result.camera_make  = _clean_str(exif.get("Make"))
            result.camera_model = _clean_str(exif.get("Model"))

            # --- GPS ---
            # getexif() returns the GPSInfo IFD as a raw offset integer; get_ifd fetches it properly
            gps_info_raw = exif_data.get_ifd(0x8825)
            if gps_info_raw:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}
                result.gps_lat = _parse_gps_coord(
                    gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N"))
                result.gps_lon = _parse_gps_coord(
                    gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E"))
                result.gps_alt = _parse_gps_altitude(
                    gps.get("GPSAltitude"), gps.get("GPSAltitudeRef", 0))

    except Exception:
        # Silently return whatever we have — never crash on EXIF read
        pass

    return result


def read_exif_from_directory(directory: str) -> ExifData:
    """
    Scan a directory for the first image that yields usable EXIF data.
    Returns that ExifData, or an empty ExifData if none found.
    Useful for pre-filling batch wizard fields.
    """
    from app.session import IMAGE_EXTENSIONS
    try:
        for fname in sorted(os.listdir(directory)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                exif = read_exif(os.path.join(directory, fname))
                if exif.has_datetime or exif.has_gps:
                    return exif
    except Exception:
        pass
    return ExifData()


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _clean_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().strip("\x00")
    return s if s else None


def _rational_to_float(value) -> Optional[float]:
    """Convert an EXIF rational (tuple of numerator, denominator) to float."""
    try:
        if hasattr(value, "numerator"):
            # IFDRational from Pillow
            return float(value)
        if isinstance(value, tuple) and len(value) == 2:
            num, den = value
            return float(num) / float(den) if den != 0 else None
        return float(value)
    except (TypeError, ZeroDivisionError, ValueError):
        return None


def _parse_gps_coord(dms_tuple, ref: str) -> Optional[float]:
    """
    Convert GPS DMS tuple ((deg_rat), (min_rat), (sec_rat)) and
    hemisphere reference to decimal degrees.
    Returns None if conversion fails.
    """
    if not dms_tuple or len(dms_tuple) < 3:
        return None
    try:
        deg = _rational_to_float(dms_tuple[0])
        mn  = _rational_to_float(dms_tuple[1])
        sec = _rational_to_float(dms_tuple[2])
        if any(v is None for v in (deg, mn, sec)):
            return None
        decimal = deg + mn / 60.0 + sec / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


def _parse_gps_altitude(alt_value, alt_ref) -> Optional[float]:
    """
    Parse GPS altitude rational and reference byte.
    alt_ref: 0 = above sea level, 1 = below sea level
    Returns metres, negative if below sea level.
    """
    if alt_value is None:
        return None
    alt = _rational_to_float(alt_value)
    if alt is None:
        return None
    # alt_ref may be bytes or int
    if isinstance(alt_ref, (bytes, bytearray)):
        alt_ref = alt_ref[0] if alt_ref else 0
    if alt_ref == 1:
        alt = -alt
    return round(alt, 2)
