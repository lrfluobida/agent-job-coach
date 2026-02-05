import inspect

from src.api import routes_retrieve


def test_no_retrieve_handler_name_collision():
    assert not hasattr(routes_retrieve, "retrieve")
    source = inspect.getsource(routes_retrieve)
    assert "def retrieve_route" in source
