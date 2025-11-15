"""Test basic package functionality."""

import taskmaster


def test_version_exists():
    """Test that the package has a version attribute."""
    assert hasattr(taskmaster, "__version__")


def test_version_format():
    """Test that version follows semantic versioning."""
    version = taskmaster.__version__
    assert isinstance(version, str)
    parts = version.split(".")
    assert len(parts) == 3, "Version should be in format X.Y.Z"
    for part in parts:
        assert part.isdigit(), "Version parts should be numeric"


def test_package_docstring():
    """Test that the package has a docstring."""
    assert taskmaster.__doc__ is not None
    assert len(taskmaster.__doc__) > 0
