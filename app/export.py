"""
export.py
CSV export — aggregates point classifications from a completed (or partial)
batch into a single long-format CSV file.

Output columns:
    site_code, location_name, panel_id, deployment_year, deployment_month,
    deployment_day, retrieval_year, retrieval_month, retrieval_day,
    data_collector, sample_processing_person, photo_filename,
    organism_name, point_count, total_points, notes

One row per organism per image. Images with no classifications are skipped.
Partially classified images are included with a warning in the notes column.
"""

import csv
import os
from typing import Optional

from app.session import Batch, Codeset, ImageEntry
from app.point_manager import PointManager


# Columns written to every export regardless of codeset
BASE_COLUMNS = [
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


def export_batch(
    batch: Batch,
    codeset: Codeset,
    output_path: str,
    include_incomplete: bool = True,
) -> tuple[int, list[str]]:
    """
    Export all classified images in a batch to a single long-format CSV.

    Args:
        batch:              The Batch object with all image state.
        codeset:            The Codeset used for organism name lookup.
        output_path:        Full path for the output CSV file.
        include_incomplete: If True, include partially classified images
                            with a warning note. If False, skip them.

    Returns:
        A tuple of (rows_written, warnings) where warnings is a list of
        human-readable strings about skipped or incomplete images.
    """
    warnings = []
    rows_written = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BASE_COLUMNS)
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
                    f"Included with warning (incomplete — {classified}/{total} points): "
                    f"{img.image_filename}"
                )

            summary = pm.get_summary()
            if not summary:
                warnings.append(f"Skipped (no classifications): {img.image_filename}")
                continue

            # Pull batch-level metadata, falling back to empty string
            meta = batch.batch_metadata
            base_note = meta.get("notes") or ""
            partial_note = f"INCOMPLETE: {classified}/{total} points classified." if is_partial else ""
            combined_notes = " | ".join(filter(None, [base_note, partial_note]))

            for code, count in sorted(summary.items()):
                row = {
                    "site_code":               meta.get("site_code", ""),
                    "location_name":           meta.get("location_name", ""),
                    "panel_id":                img.panel_id,
                    "deployment_year":         meta.get("deployment_year", ""),
                    "deployment_month":        meta.get("deployment_month", ""),
                    "deployment_day":          meta.get("deployment_day", ""),
                    "retrieval_year":          meta.get("retrieval_year", ""),
                    "retrieval_month":         meta.get("retrieval_month", ""),
                    "retrieval_day":           meta.get("retrieval_day", ""),
                    "data_collector":          meta.get("data_collector", ""),
                    "sample_processing_person": meta.get("sample_processing_person", ""),
                    "photo_filename":          img.image_filename,
                    "organism_name":           codeset.get_name(code),
                    "point_count":             count,
                    "total_points":            total,
                    "notes":                   combined_notes,
                }
                writer.writerow(row)
                rows_written += 1

    return rows_written, warnings


def suggest_export_filename(batch: Batch) -> str:
    """
    Generate a suggested export filename from batch metadata.
    Format: {site_code}_{location_name}_{retrieval_year}{retrieval_month}{retrieval_day}.csv
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

    if parts:
        # Replace any characters unsafe for filenames
        name = "_".join(parts)
        name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return name + ".csv"

    return "speck_export.csv"
