from pathlib import Path
from unittest.mock import patch

from flac_to_opus.opusenc import OpusencEncoder, build_opusenc_cmd


def test_build_opusenc_cmd():
    assert build_opusenc_cmd(Path("a.flac"), Path("a.opus"), "192") == [
        "opusenc",
        "--bitrate",
        "192",
        "--quiet",
        "a.flac",
        "a.opus",
    ]


def test_encoder_success_uses_captured_stderr(tmp_path):
    src = tmp_path / "a.flac"
    dest = tmp_path / "a.opus"
    src.write_bytes(b"f")

    class Proc:
        returncode = 0
        stderr = "ok\n"

        def __init__(self, *a, **k):
            dest.write_bytes(b"opus")

    with patch("flac_to_opus.opusenc.subprocess.run", return_value=Proc()):
        result = OpusencEncoder().encode(src, dest, "192")
    assert result.ok is True
    assert result.returncode == 0
    assert result.stderr == "ok\n"
    assert result.duration_s >= 0


def test_encoder_nonzero_is_failure(tmp_path):
    src = tmp_path / "a.flac"
    dest = tmp_path / "a.opus"
    src.write_bytes(b"f")

    class Proc:
        returncode = 1
        stderr = "boom"

    with patch("flac_to_opus.opusenc.subprocess.run", return_value=Proc()):
        result = OpusencEncoder().encode(src, dest, "192")
    assert result.ok is False
    assert result.stderr == "boom"
