from starlette.requests import Request

from app.core.client_ip import get_client_ip


def make_request(peer_ip: str, real_ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-real-ip", real_ip.encode())],
            "client": (peer_ip, 12345),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_client_ip_uses_header_from_trusted_proxy(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_network", "172.28.0.0/16")

    request = make_request("172.28.0.3", "198.51.100.10")

    assert get_client_ip(request) == "198.51.100.10"


def test_client_ip_ignores_header_from_untrusted_peer(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "trusted_proxy_network", "172.28.0.0/16")

    request = make_request("192.0.2.20", "198.51.100.10")

    assert get_client_ip(request) == "192.0.2.20"
