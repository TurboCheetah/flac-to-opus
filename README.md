# flac-to-opus

`flac-to-opus` batch-converts FLAC audio to Opus while preserving the source
layout and copying non-FLAC sidecar files.

## Requirements

- Python 3.12+
- [`opusenc`](https://github.com/xiph/opus-tools), provided by the
  [`opus-tools`](https://github.com/xiph/opus-tools) package and available on
  `PATH`

## Install

Install the command as a uv tool:

```bash
uv tool install .
```

## Usage

Convert a source tree into a destination tree using the default 192k bitrate:

```bash
flac-to-opus /path/to/source /path/to/destination
```

Choose a bitrate, run four parallel encode jobs, enable verbose output, or
preview the work without performing it:

```bash
flac-to-opus -b 256k /path/to/source /path/to/destination
flac-to-opus -j 4 /path/to/source /path/to/destination
flac-to-opus -v /path/to/source /path/to/destination
flac-to-opus -d /path/to/source /path/to/destination
```

`-b` accepts 6–512 kbit/s and defaults to 192k. If `-j` is omitted, the tool
auto-detects the CPU count. FLAC discovery is case-insensitive (`.flac`,
`.FLAC`, and so on). Each destination mirrors the source file's relative path;
FLAC files get an `.opus` suffix and sidecars are copied unchanged.

An up-to-date destination is skipped by modification time. Dry-run mode does
not perform encoding or copying. Each run creates a destination log and error
log file. Successful runs return exit status 0. Failed encodes or copies return
exit status 1. Missing or invalid prerequisites (such as a missing source
directory, invalid bitrate, or unavailable `opusenc`) return exit status 2.

## Architecture

- `cli.py` validates arguments and prerequisites, then orchestrates a run.
- `plan.py` performs pure, case-insensitive discovery and planning.
- `engine.py` executes planned encodes and copies through injected functions.
- `opusenc.py` adapts the external `opusenc` command.
- `display.py` owns file logging and Rich summary output.

## Development

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run ty check src
uv run pre-commit run --all-files
```

Installing the hooks is optional:

```bash
uv run pre-commit install
```
