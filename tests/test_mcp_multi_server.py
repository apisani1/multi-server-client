"""Basic tests for multi-server-client."""


def test_import() -> None:
    """Test that the package can be imported."""
    import mcp_multi_server
    assert hasattr(mcp_multi_server, '__version__')


def test_version() -> None:
    """Test that version is defined."""
    from mcp_multi_server import __version__
    assert __version__ is not None
    assert isinstance(__version__, str)
