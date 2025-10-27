"""Basic tests for multi-server-client."""


def test_import() -> None:
    """Test that the package can be imported."""
    import multi_server_client
    assert hasattr(multi_server_client, '__version__')


def test_version() -> None:
    """Test that version is defined."""
    from multi_server_client import __version__
    assert __version__ is not None
    assert isinstance(__version__, str)
