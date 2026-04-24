"""
export.py
CSV export — two modes:

1. Summary export (one row per organism per image)
   Columns: site_code, location_name, panel_id, deployment_year,
   deployment_month, deployment_day, retrieval_year, retrieval_month,
   retrieval_day, data_collector, sample_processing_person,
   photo_filename, organism_name, point_count, total_points, notes

2. Detailed export (one row per point per image)
   Columns: site_code, location_name, panel_id, deployment_year,
   deployment_month, deployment_day, retrieval_year, retrieval_month,
   retrieval_day, data_collector, sample_processing_person,
   photo_filename, point_number, point_x, point_y,
   organism_name, point_notes
"""

import csv
import os
from app.session import Batch, Codeset, ImageEntry
from app.point_manager import PointManager


SUMMARY_COLUMNS = [
    "site_code",
    "location_name",
    "panel_id",
    "deployment_year",
    "deployment_month",
    "deployment_day",
    "retrieval_year",
    "retrieval_month",
    "retrieval_day",
    "data_collector",
    "sample_processing_person",
    "photo_filename",
    "organism_name",
    "point_count",
    "total_points",
    "notes",
]

DETAILED_COLUMNS = [
    "site_code",
    "location_name",
    "panel_id",
    "deployment_year",
    "deployment_month",
    "deployment_day",
    "retrieval_year",
    "retrieval_month",
    "retrieval_day",
    "data_collector",
    "sample_processing_person",
    "photo_filename",
    "point_number",
    "point_x",
    "point_y",
    "organism_name",
    "point_notes",
]


def _base_row(meta: dict, img: ImageEntry) -> dict:
    """Build the metadata portion of a row shared by both export modes."""
    return {
        "site_code":                meta.get("site_code", ""),
        "location_name":            meta.get("location_name", ""),
        "panel_id":                 img.panel_id,
        "deployment_year":          meta.get("deployment_year", ""),
        "deployment_month":         meta.get("deployment_month", ""),
        "deployment_day":           meta.get("deployment_day", ""),
        "retrieval_year":           meta.get("retrieval_year", ""),
        "retrieval_month":          meta.get("retrieval_month", ""),
        "retrieval_day":            meta.get("retrieval_day", ""),
        "data_collector":           meta.get("data_collector", ""),
        "sample_processing_person": meta.get("sample_processing_person", ""),
        "photo_filename":           img.image_filename,
    }


def export_summary(
    batch: Batch,
    codeset: Codeset,
    output_path: str,
    include_incomplete: bool = True,
) -> tuple[int, list[str]]:
    """
    Export all classified images to a single long-format summary CSV.
    One row per organism per image.

    Returns (rows_written, warnings).
    """
    warnings = []
    rows_written = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()

        for img in batch.images:
            if img.is_untouched:
                warnings.append(f"Skipped (no data): {img.image_filename}")
                continue

            point_data = img.get_point_data()
            if not point_data or not point_data.get("points"):
                warnings.append(f"Skipped (no points): {img.image_filename}")
                continue

            pm = PointManager()
            pm.from_dict(point_data)

            total = pm.total
            classified = pm.classified_count
            is_partial = classified < total

            if is_partial and not include_incomplete:
                warnings.append(
                    f"Skipped (incomplete — {classified}/{total} points): "
                    f"{img.image_filename}"
                )
                continue

            if is_partial:
                warnings.append(
                    f"Included with warning (incomplete — {classified}/{total} "
                    f"points): {img.image_filename}"
                )

            summary = pm.get_summary()
            if not summary:
                warnings.append(f"Skipped (no classifications): {img.image_filename}")
                continue

            meta = batch.batch_metadata
            base_note = meta.get("notes") or ""
            partial_note = (
                f"INCOMPLETE: {classified}/{total} points classified."
                if is_partial else ""
            )
            combined_notes = " | ".join(filter(None, [base_note, partial_note]))

            for code, count in sorted(summary.items()):
                row = _base_row(meta, img)
                row.update({
                    "organism_name": codeset.get_name(code),
                    "point_count":   count,
                    "total_points":  total,
                    "notes":         combined_notes,
                })
                writer.writerow(row)
                rows_written += 1

    return rows_written, warnings


def export_detailed(
    batch: Batch,
    codeset: Codeset,
    output_path: str,
    include_incomplete: bool = True,
) -> tuple[int, list[str]]:
    """
    Export all images to a detailed CSV with one row per point.
    Unclassified points are included with empty organism_name and point_notes.

    Returns (rows_written, warnings).
    """
    warnings = []
    rows_written = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DETAILED_COLUMNS)
        writer.writeheader()

        for img in batch.images:
            if img.is_untouched:
                warnings.append(f"Skipped (no data): {img.image_filename}")
                continue

            point_data = img.get_point_data()
            if not point_data or not point_data.get("points"):
                warnings.append(f"Skipped (no points): {img.image_filename}")
                continue

            pm = PointManager()
            pm.from_dict(point_data)

            total = pm.total
            classified = pm.classified_count
            is_partial = classified < total

            if is_partial and not include_incomplete:
                warnings.append(
                    f"Skipped (incomplete — {classified}/{total} points): "
                    f"{img.image_filename}"
                )
                continue

            if is_partial:
                warnings.append(
                    f"Included with warning (incomplete — {classified}/{total} "
                    f"points): {img.image_filename}"
                )

            meta = batch.batch_metadata

            for point in pm.points:
                row = _base_row(meta, img)
                row.update({
                    "point_number":  point.index,
                    "point_x":       round(point.x, 2),
                    "point_y":       round(point.y, 2),
                    "organism_name": codeset.get_name(point.code) if point.code else "",
                    "point_notes":   point.notes or "",
                })
                writer.writerow(row)
                rows_written += 1

    return rows_written, warnings


def suggest_export_filename(batch: Batch, detailed: bool = False) -> str:
    """
    Generate a suggested export filename from batch metadata.
    Format: {site_code}_{location_name}_{retrieval_year}{month}{day}[_detailed].csv
    Falls back to 'speck_export.csv' if metadata is sparse.
    """
    meta = batch.batch_metadata
    parts = []

    site = meta.get("site_code", "").strip()
    location = meta.get("location_name", "").strip()
    year = meta.get("retrieval_year", "")
    month = meta.get("retrieval_month", "")
    day = meta.get("retrieval_day", "")

    if site:
        parts.append(site)
    if location:
        parts.append(location)
    if year and month and day:
        parts.append(f"{year}{str(month).zfill(2)}{str(day).zfill(2)}")
    if detailed:
        parts.append("detailed")

    if parts:
        name = "_".join(parts)
        name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return name + ".csv"

    return "speck_export_detailed.csv" if detailed else "speck_export.csv"
