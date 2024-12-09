#!/usr/bin/env python3
import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
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
from rich.table import Table


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
        self.non_flac_results = {"copied": 0, "skipped": 0, "dry-run": 0}

        # Tracking active subprocesses
        self.active_subprocesses = []
        self.subprocess_lock = threading.Lock()

        # Flag to indicate interruption
        self.interrupted = False

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

    def find_non_flac_files(self):
        """Find all non-FLAC files recursively in source_dir."""
        all_files = list(self.source_dir.rglob("*"))
        return [f for f in all_files if f.is_file() and f.suffix.lower() != ".flac"]

    def transcode_file(self, flac_path: Path):
        """Transcode a single FLAC file to OPUS."""
        if self.interrupted:
            return "skipped"

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

        with self.subprocess_lock:
            try:
                p = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                self.active_subprocesses.append(p)
            except Exception as e:
                self.logger.error(f"Failed to start subprocess for '{flac_path}': {e}")
                return "failed"

        try:
            p.wait()
            if p.returncode != 0:
                self.logger.error(
                    f"Failed to transcode '{flac_path}' to '{opus_full_path}'. opusenc exited with code {p.returncode}."
                )
                return "failed"
        except Exception as e:
            self.logger.error(f"Unexpected error transcoding '{flac_path}': {e}")
            return "failed"
        finally:
            with self.subprocess_lock:
                self.active_subprocesses.remove(p)

        end_time = time.time()
        duration = end_time - start_time
        try:
            src_size = flac_path.stat().st_size
            dest_size = opus_full_path.stat().st_size
        except FileNotFoundError:
            src_size = "N/A"
            dest_size = "N/A"

        self.logger.info(
            f"Successfully transcoded '{flac_path}' to '{opus_full_path}'."
        )
        self.logger.info(
            f"File Size: Source={src_size} bytes, Destination={dest_size} bytes."
        )
        self.logger.info(f"Conversion Duration: {duration:.2f} seconds.")
        return "success"

    def copy_non_flac_file(self, src_file: Path):
        """Copy a single non-FLAC file to the destination."""
        rel_path = src_file.relative_to(self.source_dir)
        dest_file = self.dest_dir / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Check modification times
        if dest_file.exists() and src_file.stat().st_mtime <= dest_file.stat().st_mtime:
            self.logger.info(
                f"Skipping copying '{src_file}' as '{dest_file}' is up-to-date."
            )
            return "skipped"

        if self.dry_run:
            self.logger.info(f"Dry-run: Would copy '{src_file}' to '{dest_file}'.")
            return "dry-run"

        try:
            shutil.copy2(src_file, dest_file)
        except Exception as e:
            self.logger.error(f"Unexpected error copying '{src_file}': {e}")
            return "failed"

        self.logger.info(f"Copied '{src_file}' to '{dest_file}'.")
        return "copied"

    def copy_non_flac_files(self):
        """Copy all non-FLAC files from source to dest."""
        non_flac_files = self.find_non_flac_files()
        total_non_flac = len(non_flac_files)

        if total_non_flac == 0:
            self.logger.info("No non-FLAC files found to copy.")
            return

        self.logger.info(f"Found {total_non_flac} non-FLAC files to copy.")

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
            task_id = progress.add_task("Copying non-FLAC files", total=total_non_flac)

            for src_file in non_flac_files:
                if self.interrupted:
                    self.logger.info(
                        "Interruption detected. Skipping remaining non-FLAC files."
                    )
                    break
                result = self.copy_non_flac_file(src_file)
                self.non_flac_results[result] = self.non_flac_results.get(result, 0) + 1
                progress.update(task_id, advance=1)

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

        summary_table = Table(
            title="Transcoding Summary", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("Metric", style="dim", no_wrap=True)
        summary_table.add_column("Value", style="bold yellow")

        for metric, value in table_data:
            summary_table.add_row(metric, value)

        self.console.print(summary_table)

        # Also print summary of non-FLAC file copying
        non_flac_table_data = [
            ("Copied", str(self.non_flac_results.get("copied", 0))),
            ("Skipped (up-to-date)", str(self.non_flac_results.get("skipped", 0))),
            ("Dry-run", str(self.non_flac_results.get("dry-run", 0))),
            ("Failed", str(self.non_flac_results.get("failed", 0))),
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

        self.console.print(non_flac_table)

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
            # Even if no FLAC files, we still copy non-FLAC files
            self.copy_non_flac_files()
            self.summarize(total_files)
            return

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
                # Single-threaded
                try:
                    for flac in flac_files:
                        result = transcode_wrapper(flac)
                        self.results[result] += 1
                        progress.update(task_id, advance=1)
                except KeyboardInterrupt:
                    self.logger.error(
                        "Interrupted by user (Ctrl-C). Terminating subprocesses..."
                    )
                    self.interrupted = True
                    self.terminate_active_subprocesses()
                    self.logger.error("All subprocesses terminated. Exiting.")
                    sys.exit(1)
            else:
                # Multi-threaded
                futures = {}
                try:
                    with ThreadPoolExecutor(max_workers=jobs) as executor:
                        futures = {
                            executor.submit(transcode_wrapper, flac): flac
                            for flac in flac_files
                        }
                        for future in as_completed(futures):
                            try:
                                result = future.result()
                                self.results[result] += 1
                            except Exception as e:
                                self.logger.error(f"Error processing file: {e}")
                                self.results["failed"] += 1
                            progress.update(task_id, advance=1)
                except KeyboardInterrupt:
                    self.logger.error(
                        "Interrupted by user (Ctrl-C). Terminating subprocesses..."
                    )
                    self.interrupted = True
                    self.terminate_active_subprocesses()
                    self.logger.error("All subprocesses terminated. Exiting.")
                    sys.exit(1)

        # After transcoding FLAC files, copy all non-FLAC files
        self.copy_non_flac_files()

        self.summarize(total_files)
        self.logger.info(f"Transcoding ended at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("All done!")

    def terminate_active_subprocesses(self):
        """Terminate all active subprocesses."""
        with self.subprocess_lock:
            for p in self.active_subprocesses:
                if p.poll() is None:  # Process is still running
                    try:
                        p.terminate()
                        self.logger.info(f"Terminated subprocess with PID {p.pid}.")
                    except Exception as e:
                        self.logger.error(
                            f"Failed to terminate subprocess {p.pid}: {e}"
                        )
            # Optionally, wait for them to terminate
            for p in self.active_subprocesses:
                if p.poll() is None:
                    try:
                        p.wait(timeout=5)
                        self.logger.info(f"Subprocess with PID {p.pid} has exited.")
                    except subprocess.TimeoutExpired:
                        self.logger.warning(
                            f"Subprocess with PID {p.pid} did not terminate in time. Killing it."
                        )
                        p.kill()


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
    try:
        tool.run()
    except KeyboardInterrupt:
        # Handle ctrl-c gracefully
        tool.logger.error("Interrupted by user (Ctrl-C). Exiting immediately.")
        tool.terminate_active_subprocesses()
        sys.exit(1)


if __name__ == "__main__":
    main()

