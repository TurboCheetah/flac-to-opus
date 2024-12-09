#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class TranscoderTool:
    def __init__(
        self,
        source_dir: Path,
        dest_dir: Path,
        bitrate: str,
        dry_run: bool,
        verbose: bool,
        jobs: int = 0,
    ):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        # Create the dest dir here so that the logger doesn't fail
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self.bitrate = bitrate
        self.dry_run = dry_run
        self.verbose = verbose
        self.jobs = jobs
        self.console = Console()

        self.logger, self.log_file, self.error_log_file = self.setup_logging()

        # Results tracking
        self.results = {"success": 0, "failed": 0, "skipped": 0, "dry-run": 0}

    def setup_logging(self):
        """Set up logging with main and error logs, plus colorized console output via Rich."""
        timestamp = int(time.time())
        log_file = self.dest_dir / f"transcode_flac_to_opus_{timestamp}.log"
        error_log_file = (
            self.dest_dir / f"transcode_flac_to_opus_{timestamp}.errors.log"
        )

        logger = logging.getLogger("transcoder")
        logger.setLevel(logging.DEBUG)

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

        console_level = logging.INFO if self.verbose else logging.WARNING
        rich_handler = RichHandler(
            console=self.console, rich_tracebacks=True, show_time=True, show_level=True
        )
        rich_handler.setLevel(console_level)
        logger.addHandler(rich_handler)

        return logger, log_file, error_log_file

    def validate_bitrate(self):
        """Validate bitrate format (e.g., '192k')."""
        if not self.bitrate.endswith("k") or not self.bitrate[:-1].isdigit():
            self.console.print(
                f"[bold red]Error:[/bold red] Invalid bitrate format '{self.bitrate}'. Expected something like '192k'.",
                style="red",
            )
            sys.exit(1)

    def check_opusenc(self):
        """Check if opusenc is installed and available in PATH."""
        if shutil.which("opusenc") is None:
            self.console.print(
                "[bold red]Error:[/bold red] 'opusenc' not found. Please install 'opus-tools' and ensure it's in your PATH.",
                style="red",
            )
            sys.exit(1)

    def find_flac_files(self):
        """Find all FLAC files recursively in source_dir."""
        return list(self.source_dir.rglob("*.flac"))

    def transcode_file(self, flac_path: Path):
        """Transcode a single FLAC file to OPUS."""
        rel_path = flac_path.relative_to(self.source_dir)
        opus_rel_path = rel_path.with_suffix(".opus")
        opus_full_path = self.dest_dir / opus_rel_path
        opus_full_path.parent.mkdir(parents=True, exist_ok=True)

        # Check modification times
        if (
            opus_full_path.exists()
            and flac_path.stat().st_mtime <= opus_full_path.stat().st_mtime
        ):
            self.logger.info(
                f"Skipping '{flac_path}' as '{opus_full_path}' is up-to-date."
            )
            return "skipped"

        if self.dry_run:
            self.logger.info(
                f"Dry-run: Would transcode '{flac_path}' to '{opus_full_path}' with bitrate {self.bitrate}."
            )
            return "dry-run"

        start_time = time.time()
        cmd = [
            "opusenc",
            "--bitrate",
            self.bitrate,
            str(flac_path),
            str(opus_full_path),
        ]
        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Failed to transcode '{flac_path}' to '{opus_full_path}'. Error: {e}"
            )
            return "failed"
        except Exception as e:
            self.logger.error(f"Unexpected error transcoding '{flac_path}': {e}")
            return "failed"

        end_time = time.time()
        duration = end_time - start_time
        src_size = flac_path.stat().st_size
        dest_size = opus_full_path.stat().st_size

        self.logger.info(
            f"Successfully transcoded '{flac_path}' to '{opus_full_path}'."
        )
        self.logger.info(
            f"File Size: Source={src_size} bytes, Destination={dest_size} bytes."
        )
        self.logger.info(f"Conversion Duration: {duration:.2f} seconds.")
        return "success"

    def summarize(self, total: int):
        """Print the summary using rich."""
        table_data = [
            ("Total FLAC files found", str(total)),
            ("Successfully transcoded", str(self.results["success"])),
            ("Failed to transcode", str(self.results["failed"])),
            ("Skipped (already up-to-date)", str(self.results["skipped"])),
            ("Dry-run", str(self.results["dry-run"])),
            ("Main log", str(self.log_file)),
            ("Error log", str(self.error_log_file)),
        ]

        from rich.table import Table

        summary_table = Table(
            title="Transcoding Summary", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("Metric", style="dim", no_wrap=True)
        summary_table.add_column("Value", style="bold yellow")

        for metric, value in table_data:
            summary_table.add_row(metric, value)

        self.console.print(summary_table)

    def run(self):
        """Run the entire transcoding process."""
        self.validate_bitrate()
        self.check_opusenc()

        self.logger.info(f"Transcoding started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Source Directory        : {self.source_dir}")
        self.logger.info(f"Destination Directory   : {self.dest_dir}")
        self.logger.info(f"Bitrate                 : {self.bitrate}")
        self.logger.info(f"Verbose Mode            : {self.verbose}")
        self.logger.info(f"Dry-run Mode            : {self.dry_run}")

        if self.jobs is not None:
            if self.jobs < 1:
                self.logger.error("Error: --jobs requires a positive integer.")
                sys.exit(1)
            jobs = self.jobs
            self.logger.info(f"Number of parallel jobs set to: {jobs}")
        else:
            available_jobs = os.cpu_count() or 1
            jobs = available_jobs
            self.logger.info(f"No jobs specified, auto-detected {jobs} jobs.")

        if jobs == 1:
            self.logger.info("Single-threaded mode.")
        else:
            self.logger.info(f"Parallel mode with {jobs} jobs.")

        flac_files = self.find_flac_files()
        total_files = len(flac_files)
        if total_files == 0:
            self.logger.info(f"No FLAC files found in '{self.source_dir}'.")
            self.summarize(total_files)
            sys.exit(0)

        self.logger.info(f"Total FLAC files found: {total_files}")

        def transcode_wrapper(flac):
            return self.transcode_file(flac)

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            TimeElapsedColumn(),
            "•",
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Transcoding", total=total_files)

            if jobs == 1:
                for flac in flac_files:
                    result = transcode_wrapper(flac)
                    self.results[result] += 1
                    progress.update(task_id, advance=1)
            else:
                with ThreadPoolExecutor(max_workers=jobs) as executor:
                    futures = {
                        executor.submit(transcode_wrapper, flac): flac
                        for flac in flac_files
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        self.results[result] += 1
                        progress.update(task_id, advance=1)

        self.summarize(total_files)
        self.logger.info(f"Transcoding ended at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("All done!")


def main():
    parser = argparse.ArgumentParser(
        description="Transcode FLAC files to OPUS.", add_help=True
    )
    parser.add_argument(
        "source_dir", type=str, help="Source directory containing FLAC files."
    )
    parser.add_argument(
        "dest_dir", type=str, help="Destination directory for OPUS files."
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
        help="Number of parallel jobs. If omitted, auto-detect CPU cores.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Perform a dry-run without actual transcoding",
    )

    args = parser.parse_args()

    tool = TranscoderTool(
        source_dir=Path(args.source_dir).resolve(),
        dest_dir=Path(args.dest_dir).resolve(),
        bitrate=args.bitrate,
        dry_run=args.dry_run,
        verbose=args.verbose,
        jobs=args.jobs,
    )
    tool.run()


if __name__ == "__main__":
    main()
