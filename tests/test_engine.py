from pathlib import Path
from unittest.mock import patch

from flac_to_opus.engine import EncodeResult, run_items
from flac_to_opus.opusenc import OpusencEncoder, build_opusenc_cmd
from flac_to_opus.plan import PlannedItem, Settings


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


def test_encoder_process_launch_oserror_is_failure(tmp_path):
    src = tmp_path / "a.flac"
    dest = tmp_path / "nested" / "a.opus"
    src.write_bytes(b"f")

    with patch(
        "flac_to_opus.opusenc.subprocess.run", side_effect=OSError("missing opusenc")
    ):
        result = OpusencEncoder().encode(src, dest, "192")

    assert result.ok is False
    assert result.returncode == 1
    assert result.stderr == "missing opusenc"
    assert result.duration_s >= 0


def test_encoder_destination_creation_oserror_is_failure(tmp_path):
    src = tmp_path / "a.flac"
    blocked_parent = tmp_path / "blocked"
    dest = blocked_parent / "a.opus"
    src.write_bytes(b"f")
    blocked_parent.write_bytes(b"not a directory")

    result = OpusencEncoder().encode(src, dest, "192")

    assert result.ok is False
    assert result.returncode == 1


class FakeEncoder:
    def __init__(self, ok: bool = True, stderr: str = ""):
        self.calls: list[tuple[str, str, str]] = []
        self.ok = ok
        self.stderr = stderr

    def encode(self, src, dest, bitrate):
        self.calls.append((str(src), str(dest), bitrate))
        if self.ok:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"opus")
        return EncodeResult(
            ok=self.ok,
            returncode=0 if self.ok else 2,
            stderr=self.stderr,
            duration_s=0.01,
        )


def test_run_items_encodes_and_copies(tmp_path):
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out"
    src_dir.mkdir()
    flac = src_dir / "t.flac"
    cover = src_dir / "cover.jpg"
    flac.write_bytes(b"flac-bytes")
    cover.write_bytes(b"jpg")
    settings = Settings(src_dir, dest_dir, "192", False, False, 1)
    items = [
        PlannedItem("transcode", flac, dest_dir / "t.opus", "run"),
        PlannedItem("copy", cover, dest_dir / "cover.jpg", "run"),
    ]
    copied: list[tuple[str, str]] = []

    def copy_file(src, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        copied.append((str(src), str(dest)))

    encoder = FakeEncoder()
    result = run_items(settings, items, encoder, copy_file)
    assert result.transcode_ok == 1
    assert result.copy_ok == 1
    assert result.failed == 0
    assert encoder.calls == [(str(flac), str(dest_dir / "t.opus"), "192")]
    assert copied == [(str(cover), str(dest_dir / "cover.jpg"))]
    assert result.source_bytes == flac.stat().st_size
    assert result.dest_bytes == (dest_dir / "t.opus").stat().st_size


def test_run_items_skip_and_dry_run_do_not_call_encoder(tmp_path):
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out"
    src_dir.mkdir()
    flac = src_dir / "t.flac"
    cover = src_dir / "cover.jpg"
    flac.write_bytes(b"f")
    cover.write_bytes(b"c")
    settings = Settings(src_dir, dest_dir, "192", True, False, 1)
    items = [
        PlannedItem("transcode", flac, dest_dir / "t.opus", "skip"),
        PlannedItem("copy", cover, dest_dir / "cover.jpg", "dry-run"),
    ]
    encoder = FakeEncoder()
    result = run_items(
        settings,
        items,
        encoder,
        copy_file=lambda s, d: (_ for _ in ()).throw(AssertionError("copy")),
    )
    assert encoder.calls == []
    assert result.transcode_skipped == 1
    assert result.copy_dry_run == 1
    assert result.failed == 0


def test_run_items_counts_encoder_failure(tmp_path):
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out"
    src_dir.mkdir()
    flac = src_dir / "t.flac"
    flac.write_bytes(b"f")
    settings = Settings(src_dir, dest_dir, "192", False, False, 1)
    items = [PlannedItem("transcode", flac, dest_dir / "t.opus", "run")]
    result = run_items(
        settings,
        items,
        FakeEncoder(ok=False, stderr="nope"),
        copy_file=lambda s, d: None,
    )
    assert result.transcode_failed == 1
    assert result.failed == 1


def test_run_items_jobs_two_records_both_transcodes(tmp_path):
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out"
    src_dir.mkdir()
    flac_a = src_dir / "a.flac"
    flac_b = src_dir / "b.flac"
    flac_a.write_bytes(b"a")
    flac_b.write_bytes(b"b")
    settings = Settings(src_dir, dest_dir, "192", False, False, 2)
    items = [
        PlannedItem("transcode", flac_a, dest_dir / "a.opus", "run"),
        PlannedItem("transcode", flac_b, dest_dir / "b.opus", "run"),
    ]
    encoder = FakeEncoder()
    result = run_items(settings, items, encoder, copy_file=lambda s, d: None)
    assert {call[0] for call in encoder.calls} == {str(flac_a), str(flac_b)}
    assert result.transcode_ok == 2


def test_run_items_copy_exception_counts_failure(tmp_path):
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out"
    src_dir.mkdir()
    cover = src_dir / "cover.jpg"
    cover.write_bytes(b"c")
    settings = Settings(src_dir, dest_dir, "192", False, False, 1)
    items = [PlannedItem("copy", cover, dest_dir / "cover.jpg", "run")]

    def copy_file(src, dest):
        raise OSError("nope")

    result = run_items(settings, items, FakeEncoder(), copy_file=copy_file)
    assert result.copy_failed == 1
    assert result.failed == 1
