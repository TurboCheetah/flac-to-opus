from pathlib import Path

import pytest

from flac_to_opus.plan import (
    Settings,
    dest_for,
    discover,
    is_up_to_date,
    parse_bitrate,
    plan_items,
    resolve_jobs,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("192k", "192"),
        ("192K", "192"),
        ("192", "192"),
        ("192.0", "192.0"),
        ("256k", "256"),
        ("6", "6"),
    ],
)
def test_parse_bitrate_accepts_common_forms(raw, expected):
    assert parse_bitrate(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "k",
        "abc",
        "192kb",
        "0",
        "5",
        "5.9999999999999999999999",
        "512.000000000000000000001",
        "513",
        "-1",
        "192 k",
    ],
)
def test_parse_bitrate_rejects_bad_values(raw):
    with pytest.raises(ValueError):
        parse_bitrate(raw)


def test_resolve_jobs_none_uses_cpu_count():
    assert resolve_jobs(None, 16) == 16


def test_resolve_jobs_none_with_zero_cpu_becomes_one():
    assert resolve_jobs(None, 0) == 1


def test_resolve_jobs_explicit():
    assert resolve_jobs(4, 16) == 4


@pytest.mark.parametrize("value", [0, -1])
def test_resolve_jobs_rejects_non_positive(value):
    with pytest.raises(ValueError):
        resolve_jobs(value, 16)


def _settings(tmp_path: Path, dry_run: bool = False) -> Settings:
    src = tmp_path / "in"
    dest = tmp_path / "out"
    src.mkdir()
    return Settings(
        source_dir=src,
        dest_dir=dest,
        bitrate="192",
        dry_run=dry_run,
        verbose=False,
        jobs=1,
    )


def test_discover_is_case_insensitive_and_sorted(tmp_path):
    settings = _settings(tmp_path)
    (settings.source_dir / "b.FLAC").write_bytes(b"x")
    (settings.source_dir / "a.flac").write_bytes(b"x")
    nested = settings.source_dir / "disc"
    nested.mkdir()
    (nested / "c.flac").write_bytes(b"x")
    (settings.source_dir / "cover.jpg").write_bytes(b"y")
    (settings.source_dir / "notes.TXT").write_bytes(b"z")
    flacs, sidecars = discover(settings.source_dir)
    assert [p.relative_to(settings.source_dir).as_posix() for p in flacs] == [
        "a.flac",
        "b.FLAC",
        "disc/c.flac",
    ]
    assert [p.relative_to(settings.source_dir).as_posix() for p in sidecars] == [
        "cover.jpg",
        "notes.TXT",
    ]


def test_dest_for_transcode_swaps_suffix(tmp_path):
    settings = _settings(tmp_path)
    src = settings.source_dir / "disc" / "track.FLAC"
    assert dest_for(settings.source_dir, settings.dest_dir, src, "transcode") == (
        settings.dest_dir / "disc" / "track.opus"
    )


def test_dest_for_copy_keeps_name(tmp_path):
    settings = _settings(tmp_path)
    src = settings.source_dir / "cover.jpg"
    assert dest_for(settings.source_dir, settings.dest_dir, src, "copy") == (
        settings.dest_dir / "cover.jpg"
    )


def test_is_up_to_date_compares_mtime(tmp_path):
    src = tmp_path / "a.flac"
    dest = tmp_path / "a.opus"
    src.write_bytes(b"src")
    dest.write_bytes(b"dest")
    older = src.stat().st_mtime - 10
    dest.touch()
    # dest newer
    import os

    os.utime(src, (older, older))
    assert is_up_to_date(src, dest) is True
    os.utime(dest, (older - 10, older - 10))
    assert is_up_to_date(src, dest) is False
    dest.unlink()
    assert is_up_to_date(src, dest) is False
    dest.mkdir()
    assert is_up_to_date(src, dest) is False


def test_plan_items_dry_run_and_skip(tmp_path):
    settings = _settings(tmp_path, dry_run=True)
    flac = settings.source_dir / "t.flac"
    cover = settings.source_dir / "cover.jpg"
    flac.write_bytes(b"f")
    cover.write_bytes(b"c")
    stale = settings.dest_dir / "old.opus"
    settings.dest_dir.mkdir()
    stale.parent.mkdir(parents=True, exist_ok=True)
    # existing up-to-date opus
    opus = settings.dest_dir / "t.opus"
    opus.write_bytes(b"o")
    import os

    older = flac.stat().st_mtime - 10
    os.utime(flac, (older, older))
    items = plan_items(settings)
    by_src = {i.src.name: i for i in items}
    assert by_src["t.flac"].action == "skip"
    assert by_src["cover.jpg"].action == "dry-run"
    assert by_src["cover.jpg"].kind == "copy"


def test_plan_items_gives_transcode_destination_exclusive_ownership(tmp_path):
    settings = _settings(tmp_path)
    (settings.source_dir / "track.flac").write_bytes(b"flac")
    (settings.source_dir / "track.opus").write_bytes(b"old opus")

    items = plan_items(settings)

    assert [(item.kind, item.src.name, item.dest.name) for item in items] == [
        ("transcode", "track.flac", "track.opus")
    ]


def test_plan_items_rejects_non_file_destination_conflicts(tmp_path):
    settings = _settings(tmp_path)
    (settings.source_dir / "cover.jpg").write_bytes(b"cover")
    conflict = settings.dest_dir / "cover.jpg"
    conflict.mkdir(parents=True)

    with pytest.raises(ValueError, match="destination path exists and is not a file"):
        plan_items(settings)
