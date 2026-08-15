from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EncodeResult:
    ok: bool
    returncode: int
    stderr: str
    duration_s: float


class Encoder(Protocol):
    def encode(self, src: Path, dest: Path, bitrate: str) -> EncodeResult: ...
