from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from flac_to_opus.display import setup_logging, summarize
from flac_to_opus.engine import run_items
from flac_to_opus.opusenc import OpusencEncoder
from flac_to_opus.plan import Settings, parse_bitrate, plan_items, resolve_jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcode FLAC files to OPUS.",
        add_help=True,
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Source directory containing FLAC files.",
    )
    parser.add_argument(
        "dest_dir",
        type=Path,
        help="Destination directory for OPUS files.",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        type=str,
        default="192k",
        help="Bitrate for OPUS encoding (default: 192k)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        nargs="?",
        default=None,
        help="Number of parallel jobs. If omitted, auto-detect CPU cores.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Perform a dry-run without actual transcoding",
    )
    return parser


def main(
    argv: list[str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    args = build_parser().parse_args(argv)

    source_dir = args.source_dir.resolve()
    dest_dir = args.dest_dir.resolve()

    if not source_dir.is_dir():
        print(f"Error: source directory {source_dir} does not exist.", file=sys.stderr)
        return 2

    try:
        bitrate = parse_bitrate(args.bitrate)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        jobs = resolve_jobs(args.jobs, os.cpu_count() or 1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if which("opusenc") is None:
        print(
            "Error: 'opusenc' not found. Please install 'opus-tools' and ensure it's in your PATH.",
            file=sys.stderr,
        )
        return 2

    dest_dir.mkdir(parents=True, exist_ok=True)
    _logger, log_file, error_log_file = setup_logging(dest_dir, args.verbose)
    settings = Settings(
        source_dir=source_dir,
        dest_dir=dest_dir,
        bitrate=bitrate,
        dry_run=args.dry_run,
        verbose=args.verbose,
        jobs=jobs,
    )
    items = plan_items(settings)
    result = run_items(
        settings,
        items,
        encoder=OpusencEncoder(),
        copy_file=shutil.copy2,
    )
    total_flacs = sum(1 for item in items if item.kind == "transcode")
    summarize(Console(), result, total_flacs, log_file, error_log_file)
    return 1 if result.failed or result.interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
