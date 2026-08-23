from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_documentation_artifacts_describe_current_contracts() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for marker in (
        "uv tool install .",
        "uv sync --group dev",
        "uv run pytest -q",
        "uv run ruff check .",
        "uv run ty check src",
        "opusenc",
        "flac-to-opus",
        "-b",
        "-j",
        "-d",
        "-v",
        "Python 3.12+",
        "192k",
        "exit status 0",
        "exit status 1",
        "exit status 2",
    ):
        assert marker in readme

    for marker in (
        "src/flac_to_opus/",
        "uv run pytest -q",
        "do not push",
        "opusenc adapter seam",
        "plan.py",
        "engine.py",
        "Turbo <dev@turbo.ooo>",
        "renovate.json",
    ):
        assert marker in agents

    for source in (readme, agents):
        for stale_marker in (
            "poetry",
            "pip install",
            "python-3.x",
            "TranscoderTool",
            "Progress Indicators",
            "progress bars",
        ):
            assert stale_marker not in source
