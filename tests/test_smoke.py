def test_import():
    import tools
    from tools import __version__
    assert isinstance(__version__, str)



