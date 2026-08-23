from pathlib import Path

from flac_to_opus.cli import build_parser, main


def test_missing_source_does_not_create_dest(tmp_path):
    dest = tmp_path / "out"
    rc = main([str(tmp_path / "missing"), str(dest)], which=lambda n: "/bin/opusenc")
    assert rc == 2
    assert not dest.exists()


def test_missing_opusenc_does_not_create_dest(tmp_path):
    src = tmp_path / "in"
    dest = tmp_path / "out"
    src.mkdir()
    rc = main([str(src), str(dest)], which=lambda n: None)
    assert rc == 2
    assert not dest.exists()


def test_dry_run_zero_and_creates_logs(tmp_path):
    src = tmp_path / "in"
    dest = tmp_path / "out"
    src.mkdir()
    (src / "a.flac").write_bytes(b"f")
    rc = main(["-d", str(src), str(dest)], which=lambda n: "/bin/opusenc")
    assert rc == 0
    assert list(dest.glob("transcode_flac_to_opus_*.log"))
    assert not list(dest.glob("*.opus"))


def test_failed_encode_exits_one(tmp_path, monkeypatch):
    from flac_to_opus.engine import EncodeResult
    from flac_to_opus.opusenc import OpusencEncoder

    src = tmp_path / "in"
    dest = tmp_path / "out"
    src.mkdir()
    (src / "a.flac").write_bytes(b"f")

    def fake_encode(self, src_path, dest_path, bitrate):
        return EncodeResult(ok=False, returncode=2, stderr="boom", duration_s=0.01)

    monkeypatch.setattr(OpusencEncoder, "encode", fake_encode)
    rc = main([str(src), str(dest)], which=lambda n: "/bin/opusenc")
    assert rc == 1


def test_nested_sidecar_copy_creates_destination_parent(tmp_path):
    src = tmp_path / "in"
    dest = tmp_path / "out"
    nested = src / "artwork"
    nested.mkdir(parents=True)
    (nested / "cover.jpg").write_bytes(b"cover")

    rc = main([str(src), str(dest)], which=lambda n: "/bin/opusenc")

    assert rc == 0
    assert (dest / "artwork" / "cover.jpg").read_bytes() == b"cover"


def test_bad_bitrate_does_not_create_dest(tmp_path):
    src = tmp_path / "in"
    dest = tmp_path / "out"
    src.mkdir()
    rc = main(["-b", "nope", str(src), str(dest)], which=lambda n: "/bin/opusenc")
    assert rc == 2
    assert not dest.exists()


def test_build_parser_flags():
    args = build_parser().parse_args(["-b", "256k", "-j", "4", "-v", "-d", "in", "out"])
    assert args.bitrate == "256k"
    assert args.jobs == 4
    assert args.verbose is True
    assert args.dry_run is True
    assert args.source_dir == Path("in")
    assert args.dest_dir == Path("out")
