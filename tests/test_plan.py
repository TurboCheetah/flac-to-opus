import pytest

from flac_to_opus.plan import parse_bitrate, resolve_jobs


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


@pytest.mark.parametrize("raw", ["", "k", "abc", "192kb", "0", "5", "513", "-1", "192 k"])
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
