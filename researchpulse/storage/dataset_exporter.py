"""
Dataset exporter — exports research items to CSV, JSON, and Parquet formats.

Supports filtering by source, date range, and tags.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from sqlmodel import SQLModel

from researchpulse.utils.logging import get_logger

logger = get_logger("storage.exporter")


def _model_to_dict(item: SQLModel) -> dict[str, Any]:
    """Convert a SQLModel instance to a plain dict for export."""
    data = {}
    for key, value in item.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data


def export_to_json(
    items: Sequence[SQLModel],
    output_path: str | Path,
) -> Path:
    """Export items to a JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records = [_model_to_dict(item) for item in items]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Exported to JSON", path=str(path), count=len(records))
    return path


def export_to_csv(
    items: Sequence[SQLModel],
    output_path: str | Path,
) -> Path:
    """Export items to a CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not items:
        logger.warning("No items to export")
        path.write_text("")
        return path

    records = [_model_to_dict(item) for item in items]
    fieldnames = list(records[0].keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    logger.info("Exported to CSV", path=str(path), count=len(records))
    return path


def export_to_parquet(
    items: Sequence[SQLModel],
    output_path: str | Path,
) -> Path:
    """
    Export items to a Parquet file.

    Requires pyarrow to be installed.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError(
            "pyarrow is required for Parquet export. "
            "Install with: pip install pyarrow"
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records = [_model_to_dict(item) for item in items]

    if not records:
        logger.warning("No items to export")
        # Create empty parquet file
        table = pa.table({})
        pq.write_table(table, path)
        return path

    table = pa.Table.from_pylist(records)
    pq.write_table(table, path)

    logger.info("Exported to Parquet", path=str(path), count=len(records))
    return path


def export_items(
    items: Sequence[SQLModel],
    output_dir: str | Path,
    formats: list[str],
    prefix: str = "researchpulse",
) -> list[Path]:
    """
    Export items to multiple formats.

    Args:
        items: The items to export.
        output_dir: Directory to write files to.
        formats: List of formats ("json", "csv", "parquet").
        prefix: Filename prefix.

    Returns:
        List of paths to created files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: list[Path] = []

    for fmt in formats:
        filename = f"{prefix}_{timestamp}.{fmt}"
        output_path = output_dir / filename

        if fmt == "json":
            paths.append(export_to_json(items, output_path))
        elif fmt == "csv":
            paths.append(export_to_csv(items, output_path))
        elif fmt == "parquet":
            paths.append(export_to_parquet(items, output_path))
        else:
            logger.warning("Unknown export format", format=fmt)

    return paths
