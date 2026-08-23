# Agent and contributor guidance

## Scope and architecture

Work within `src/flac_to_opus/` and preserve the public command
`flac-to-opus`.

- `cli.py` validates arguments and prerequisites, then orchestrates the run.
- `plan.py` is pure discovery and planning: it finds FLAC files
  case-insensitively, maps relative destinations, and decides run/skip/dry-run
  actions.
- `engine.py` executes planned work through injected encoder and copy
  functions, including parallel encoding.
- `opusenc.py` is the opusenc adapter seam. Keep the external command isolated
  there.
- `display.py` owns logging and Rich summaries, including the destination log
  and error log files.

The destination mirrors source-relative paths, sidecars are copied, and an
up-to-date destination is skipped by modification time. The default bitrate is
192k; the accepted range is 6–512 kbit/s.

## Tests and checks

Use uv for repository test, lint, formatting, type, and hook commands:

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run ty check src
uv run pre-commit run --all-files
```

Install hooks only when useful with `uv run pre-commit install`. Follow TDD:
write a focused failing test first, implement one task at a time, then run the
focused test and the full suite. Do not invoke real opusenc in tests; inject
fakes through the engine or patch the adapter at its seam.

## CLI validation and exit statuses

Validation happens before the destination directory and log files are created:
source directory, bitrate, job count, and `opusenc` availability are checked in
that order. Missing or invalid prerequisites return exit status 2. Planning and
execution happen after validation; a dry-run plans the work but does not perform it.
Failed encodes or copies return exit status 1, while a successful run returns
0.

## Repository guardrails

- Keep the public command `flac-to-opus` stable.
- Commit author must remain `Turbo <dev@turbo.ooo>`.
- do not push; commits are local unless the task explicitly says otherwise.
- Do not modify `renovate.json`.
- Do not touch unrelated files. Before committing, verify `git diff --check`,
  `git diff`, and `git status --short`.
- Keep tests deterministic, use injected fakes, and avoid filesystem or process
  effects outside the test fixture.
