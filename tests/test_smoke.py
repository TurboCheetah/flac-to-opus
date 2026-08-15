from flac_to_opus import __version__
from flac_to_opus.main import TranscoderTool, main


def test_version():
    assert __version__ == "1.1.0"


def test_main_and_tool_importable():
    assert callable(main)
    assert TranscoderTool is not None
