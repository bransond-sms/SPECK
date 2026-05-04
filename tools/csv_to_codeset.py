"""
csv_to_codeset.py
Standalone command-line tool to convert a two-column taxon CSV into a
SPECK codeset JSON file.

CSV format (header row required):
    label,taxon
    barn,Barnacles
    e_bryo,Encrusting bryozoans
    os,Open Space

Usage:
    python tools/csv_to_codeset.py input.csv output.json
    python tools/csv_to_codeset.py input.csv output.json --name "My Codeset" --author "Jane Smith"
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# --- Color palette -----------------------------------------------------------
# 32 perceptually distinct colors derived from ColorBrewer qualitative sets
# and extended with additional hue-shifted values. Adjacent colors in this
# list are chosen to contrast in both hue and brightness.

PALETTE = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2",
    "#D55E00", "#CC79A7", "#1B9E77", "#D95F02", "#7570B3",
    "#E7298A", "#66A61E", "#E6AB02", "#A6761D", "#666666",
    "#8DD3C7", "#BEBADA", "#FB8072", "#80B1D3", "#FDB462",
    "#B3DE69", "#FCCDE5", "#BC80BD", "#CCEBC5", "#FFED6F",
    "#A6CEE3", "#1F78B4", "#B2DF8A", "#33A02C", "#FB9A99",
    "#E31A1C", "#FDBF6F",
]

MAX_LABEL_LENGTH = 8


def load_csv(filepath: str) -> tuple[list[dict], list[str]]:
    """
    Load and validate a taxon CSV file.
    Returns (rows, errors) where rows is a list of {label, taxon} dicts
    and errors is a list of human-readable problem strings.
    """
    errors = []
    rows = []

    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]

            if "label" not in headers or "taxon" not in headers:
                errors.append(
                    "CSV must have 'label' and 'taxon' column headers "
                    "(case-insensitive)."
                )
                return [], errors

            seen_labels = {}
            seen_taxa = {}

            for i, raw_row in enumerate(reader, start=2):  # row 1 is header
                label = raw_row.get("label", "").strip()
                taxon = raw_row.get("taxon", "").strip()

                if not label and not taxon:
                    continue  # skip blank rows silently

                if not label:
                    errors.append(f"Row {i}: missing label (taxon: '{taxon}').")
                    continue

                if not taxon:
                    errors.append(f"Row {i}: missing taxon name (label: '{label}').")
                    continue

                row_ok = True

                if len(label) > MAX_LABEL_LENGTH:
                    errors.append(
                        f"Row {i}: label '{label}' is {len(label)} characters — "
                        f"maximum is {MAX_LABEL_LENGTH}."
                    )
                    row_ok = False

                if label.lower() in seen_labels:
                    errors.append(
                        f"Row {i}: duplicate label '{label}' "
                        f"(first seen on row {seen_labels[label.lower()]})."
                    )
                    row_ok = False
                else:
                    seen_labels[label.lower()] = i

                if taxon.lower() in seen_taxa:
                    errors.append(
                        f"Row {i}: duplicate taxon '{taxon}' "
                        f"(first seen on row {seen_taxa[taxon.lower()]})."
                    )
                    row_ok = False
                else:
                    seen_taxa[taxon.lower()] = i

                if row_ok:
                    rows.append({"label": label, "taxon": taxon})

    except FileNotFoundError:
        errors.append(f"File not found: {filepath}")
    except Exception as e:
        errors.append(f"Could not read CSV: {e}")

    return rows, errors


def assign_colors(rows: list[dict]) -> list[dict]:
    """
    Assign a color to each row, cycling through PALETTE with contrast
    between adjacent entries.
    """
    n = len(PALETTE)
    result = []
    for i, row in enumerate(rows):
        result.append({
            "code":      row["label"],
            "name":      row["taxon"],
            "color":     PALETTE[i % n],
            "catch_all": False,
        })
    return result


def build_codeset(
    codes: list[dict],
    name: str,
    version: str,
    description: str,
    author: str,
) -> dict:
    """Build the full codeset JSON structure."""
    return {
        "name":        name,
        "version":     version,
        "description": description,
        "author":      author,
        "metadata_fields": [],  # User defines these in the batch wizard
        "codes":       codes,
    }


def convert(
    input_path: str,
    output_path: str,
    name: str = "",
    version: str = "1.0",
    description: str = "",
    author: str = "",
) -> tuple[bool, list[str]]:
    """
    Full conversion pipeline.
    Returns (success, messages) where messages is a list of info/error strings.
    """
    rows, errors = load_csv(input_path)

    if errors:
        return False, errors

    if not rows:
        return False, ["No valid rows found in CSV."]

    codes  = assign_colors(rows)
    cs_name = name or Path(input_path).stem
    codeset = build_codeset(codes, cs_name, version, description, author)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(codeset, f, indent=2)
    except OSError as e:
        return False, [f"Could not write output file: {e}"]

    return True, [f"Wrote {len(codes)} codes to {output_path}."]


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a taxon CSV to a SPECK codeset JSON file."
    )
    parser.add_argument("input",  help="Path to input CSV file")
    parser.add_argument("output", help="Path to output JSON file")
    parser.add_argument("--name",        default="", help="Codeset name")
    parser.add_argument("--version",     default="1.0", help="Codeset version")
    parser.add_argument("--description", default="", help="Codeset description")
    parser.add_argument("--author",      default="", help="Codeset author")
    args = parser.parse_args()

    success, messages = convert(
        input_path  = args.input,
        output_path = args.output,
        name        = args.name,
        version     = args.version,
        description = args.description,
        author      = args.author,
    )

    for msg in messages:
        print(msg)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
