import pytest
import requests


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """테스트는 다나와·텔레그램에 실제 요청을 보내지 않는다. 보내려 하면 바로 실패."""
    def blocked(*args, **kwargs):
        raise RuntimeError("테스트에서 외부 네트워크 요청이 발생했습니다")
    monkeypatch.setattr(requests.Session, "request", blocked)
