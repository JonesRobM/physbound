"""Packaging tests — typed marker and packaged data files."""

import importlib.resources


def test_py_typed_marker_is_packaged():
    """PEP 561: the py.typed marker must ship inside the physbound package."""
    assert importlib.resources.files("physbound").joinpath("py.typed").is_file()


def test_py_typed_marker_is_empty():
    content = importlib.resources.files("physbound").joinpath("py.typed").read_text()
    assert content == ""
