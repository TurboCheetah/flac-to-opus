from __future__ import annotations

import re

_BITRATE = re.compile(r"^(\d+(?:\.\d+)?)[kK]?$")
_MIN_BITRATE = 6.0
_MAX_BITRATE = 512.0


def parse_bitrate(raw: str) -> str:
    """Return the opusenc --bitrate value (no trailing k).

    After stripping a trailing k/K, the number must be finite and in [6, 512].
    6 is opusenc's documented minimum; 512 is stereo headroom (256/channel).
    """
    match = _BITRATE.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"invalid bitrate {raw!r}; expected e.g. 192 or 192k")
    number = match.group(1)
    value = float(number)
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
