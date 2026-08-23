from __future__ import annotations

import logging
import math
import time
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from flac_to_opus.engine import RunResult


def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    sign = -1 if size_bytes < 0 else 1
    magnitude = abs(size_bytes)
    i = min(math.floor(math.log(magnitude, 1024)), len(size_name) - 1)
    p = math.pow(1024, i)
    s = round(sign * magnitude / p, 2)
    return f"{s} {size_name[i]}"


def setup_logging(dest_dir: Path, verbose: bool) -> tuple[logging.Logger, Path, Path]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    log_file = dest_dir / f"transcode_flac_to_opus_{timestamp}.log"
    error_log_file = dest_dir / f"transcode_flac_to_opus_{timestamp}.errors.log"

    logger = logging.getLogger("flac_to_opus")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    fh = logging.FileHandler(str(log_file))
    fh.setLevel(logging.INFO)
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    eh = logging.FileHandler(str(error_log_file))
    eh.setLevel(logging.ERROR)
    eh.setFormatter(file_formatter)
    logger.addHandler(eh)

    console_level = logging.INFO if verbose else logging.WARNING
    rich_handler = RichHandler(
        console=Console(), rich_tracebacks=True, show_time=True, show_level=True
    )
    rich_handler.setLevel(console_level)
    logger.addHandler(rich_handler)

    return logger, log_file, error_log_file


def summarize(
    console: Console,
    result: RunResult,
    total_flacs: int,
    log_file: Path,
    error_log_file: Path,
) -> None:
    summary_table_data = [
        ("Total FLAC files found", str(total_flacs)),
        ("Successfully transcoded", str(result.transcode_ok)),
        ("Failed to transcode", str(result.transcode_failed)),
        ("Skipped (already up-to-date)", str(result.transcode_skipped)),
        ("Dry-run", str(result.transcode_dry_run)),
        ("Main log", str(log_file)),
        ("Error log", str(error_log_file)),
        ("Total Source Size", format_size(result.source_bytes)),
        ("Total Destination Size", format_size(result.dest_bytes)),
        ("Space Saved", format_size(result.source_bytes - result.dest_bytes)),
    ]

    summary_table = Table(
        title="Transcoding Summary", show_header=True, header_style="bold magenta"
    )
    summary_table.add_column("Metric", style="dim", no_wrap=True)
    summary_table.add_column("Value", style="bold yellow")

    for metric, value in summary_table_data:
        summary_table.add_row(metric, value)

    console.print(summary_table)

    non_flac_table_data = [
        ("Copied", str(result.copy_ok)),
        ("Skipped (up-to-date)", str(result.copy_skipped)),
        ("Dry-run", str(result.copy_dry_run)),
        ("Failed", str(result.copy_failed)),
    ]

    non_flac_table = Table(
        title="Non-FLAC Files Copy Summary",
        show_header=True,
        header_style="bold magenta",
    )
    non_flac_table.add_column("Metric", style="dim", no_wrap=True)
    non_flac_table.add_column("Value", style="bold yellow")

    for metric, value in non_flac_table_data:
        non_flac_table.add_row(metric, value)

    console.print(non_flac_table)
