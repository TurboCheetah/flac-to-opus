from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

from flac_to_opus.plan import PlannedItem, Settings


@dataclass(frozen=True)
class EncodeResult:
    ok: bool
    returncode: int
    stderr: str
    duration_s: float


class Encoder(Protocol):
    def encode(self, src: Path, dest: Path, bitrate: str) -> EncodeResult: ...


@dataclass
class RunResult:
    transcode_ok: int = 0
    transcode_failed: int = 0
    transcode_skipped: int = 0
    transcode_dry_run: int = 0
    copy_ok: int = 0
    copy_failed: int = 0
    copy_skipped: int = 0
    copy_dry_run: int = 0
    source_bytes: int = 0
    dest_bytes: int = 0
    interrupted: bool = False

    @property
    def failed(self) -> int:
        return self.transcode_failed + self.copy_failed


def run_items(
    settings: Settings,
    items: list[PlannedItem],
    encoder: Encoder,
    copy_file: Callable[[Path, Path], None],
    on_progress=None,
) -> RunResult:
    result = RunResult()
    lock = Lock()

    def apply_item(item: PlannedItem) -> None:
        if item.action == "skip":
            with lock:
                if item.kind == "transcode":
                    result.transcode_skipped += 1
                else:
                    result.copy_skipped += 1
            return
        if item.action == "dry-run":
            with lock:
                if item.kind == "transcode":
                    result.transcode_dry_run += 1
                else:
                    result.copy_dry_run += 1
            return
        if item.kind == "transcode":
            encoded = encoder.encode(item.src, item.dest, settings.bitrate)
            with lock:
                if encoded.ok:
                    result.transcode_ok += 1
                    try:
                        result.source_bytes += item.src.stat().st_size
                        result.dest_bytes += item.dest.stat().st_size
                    except FileNotFoundError:
                        pass
                else:
                    result.transcode_failed += 1
            return
        try:
            copy_file(item.src, item.dest)
        except OSError:
            with lock:
                result.copy_failed += 1
            return
        with lock:
            result.copy_ok += 1

    try:
        if settings.jobs <= 1:
            for item in items:
                apply_item(item)
            return result

        serial_items: list[PlannedItem] = []
        transcode_runs: list[PlannedItem] = []
        for item in items:
            if item.kind == "transcode" and item.action == "run":
                transcode_runs.append(item)
            else:
                serial_items.append(item)

        for item in serial_items:
            apply_item(item)

        if transcode_runs:
            with ThreadPoolExecutor(max_workers=settings.jobs) as executor:
                futures = [executor.submit(apply_item, item) for item in transcode_runs]
                for future in as_completed(futures):
                    future.result()
    except KeyboardInterrupt:
        result.interrupted = True

    return result
