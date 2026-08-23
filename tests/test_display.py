from io import StringIO
from pathlib import Path

from rich.console import Console

from flac_to_opus.display import format_size, setup_logging, summarize
from flac_to_opus.engine import RunResult


def test_format_size_zero():
    assert format_size(0) == "0B"


def test_format_size_kibibyte():
    assert format_size(1024) == "1.0 KB"


def test_format_size_clamps_to_largest_unit():
    assert format_size(1024**5) == "1024.0 TB"


def test_format_size_preserves_negative_sign():
    assert format_size(-1024) == "-1.0 KB"


def test_setup_logging_creates_files_and_records_error(tmp_path):
    logger, log_file, error_log_file = setup_logging(tmp_path, verbose=False)
    assert log_file.exists()
    assert error_log_file.exists()
    assert log_file.name.startswith("transcode_flac_to_opus_")
    assert log_file.name.endswith(".log")
    assert error_log_file.name.endswith(".errors.log")
    logger.error("x")
    for handler in logger.handlers:
        handler.flush()
    assert "x" in error_log_file.read_text()


def test_summarize_emits_table_titles():
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=80)
    result = RunResult(
        transcode_ok=1,
        transcode_failed=0,
        transcode_skipped=2,
        transcode_dry_run=0,
        copy_ok=3,
        copy_failed=0,
        copy_skipped=1,
        copy_dry_run=0,
        source_bytes=2048,
        dest_bytes=1024,
    )
    summarize(
        console,
        result,
        total_flacs=3,
        log_file=Path("/tmp/main.log"),
        error_log_file=Path("/tmp/error.log"),
    )
    output = buffer.getvalue()
    assert "Transcoding Summary" in output
    assert "Non-FLAC Files Copy Summary" in output
