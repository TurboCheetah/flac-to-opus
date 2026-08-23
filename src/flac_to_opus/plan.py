from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

_BITRATE = re.compile(r"^(\d+(?:\.\d+)?)[kK]?$")
_MIN_BITRATE = Decimal(6)
_MAX_BITRATE = Decimal(512)


def parse_bitrate(raw: str) -> str:
    """Return the opusenc --bitrate value (no trailing k).

    After stripping a trailing k/K, the number must be finite and in [6, 512].
    6 is opusenc's documented minimum; 512 is stereo headroom (256/channel).
    """
    match = _BITRATE.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"invalid bitrate {raw!r}; expected e.g. 192 or 192k")
    number = match.group(1)
    value = Decimal(number)
    if not (_MIN_BITRATE <= value <= _MAX_BITRATE):
        raise ValueError(
            f"bitrate {raw!r} out of range; expected {_MIN_BITRATE:g}–{_MAX_BITRATE:g} kbit/s"
        )
    return number


def resolve_jobs(jobs: int | None, cpu_count: int) -> int:
    if jobs is None:
        return max(1, cpu_count)
    if jobs < 1:
        raise ValueError("--jobs requires a positive integer")
    return jobs


Kind = Literal["transcode", "copy"]
Action = Literal["run", "skip", "dry-run"]


@dataclass(frozen=True)
class Settings:
    source_dir: Path
    dest_dir: Path
    bitrate: str
    dry_run: bool
    verbose: bool
    jobs: int


@dataclass(frozen=True)
class PlannedItem:
    kind: Kind
    src: Path
    dest: Path
    action: Action


def dest_for(source_dir: Path, dest_dir: Path, src: Path, kind: Kind) -> Path:
    rel = src.relative_to(source_dir)
    if kind == "transcode":
        return dest_dir / rel.with_suffix(".opus")
    return dest_dir / rel


def is_up_to_date(src: Path, dest: Path) -> bool:
    return dest.is_file() and src.stat().st_mtime <= dest.stat().st_mtime


def discover(source_dir: Path) -> tuple[list[Path], list[Path]]:
    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    flacs = [p for p in files if p.suffix.lower() == ".flac"]
    sidecars = [p for p in files if p.suffix.lower() != ".flac"]
    return flacs, sidecars


def _action(src: Path, dest: Path, dry_run: bool) -> Action:
    if is_up_to_date(src, dest):
        return "skip"
    if dry_run:
        return "dry-run"
    return "run"


def _reject_non_file_destination(dest: Path) -> None:
    if dest.exists() and not dest.is_file():
        raise ValueError(f"destination path exists and is not a file: {dest}")


def plan_items(settings: Settings) -> list[PlannedItem]:
    flacs, sidecars = discover(settings.source_dir)
    items: list[PlannedItem] = []
    transcode_destinations: set[Path] = set()
    for src in flacs:
        dest = dest_for(settings.source_dir, settings.dest_dir, src, "transcode")
        _reject_non_file_destination(dest)
        transcode_destinations.add(dest)
        items.append(
            PlannedItem("transcode", src, dest, _action(src, dest, settings.dry_run))
        )
    for src in sidecars:
        dest = dest_for(settings.source_dir, settings.dest_dir, src, "copy")
        if dest in transcode_destinations:
            continue
        _reject_non_file_destination(dest)
        items.append(
            PlannedItem("copy", src, dest, _action(src, dest, settings.dry_run))
        )
    return items
