from __future__ import annotations

import subprocess
import time
from pathlib import Path

from flac_to_opus.engine import EncodeResult


def build_opusenc_cmd(src: Path, dest: Path, bitrate: str) -> list[str]:
    return ["opusenc", "--bitrate", bitrate, "--quiet", str(src), str(dest)]


class OpusencEncoder:
    def encode(self, src: Path, dest: Path, bitrate: str) -> EncodeResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        completed = subprocess.run(
            build_opusenc_cmd(src, dest, bitrate),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return EncodeResult(
            ok=completed.returncode == 0,
            returncode=completed.returncode,
            stderr=completed.stderr or "",
            duration_s=time.perf_counter() - started,
        )
