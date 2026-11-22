import ipaddress

from fastapi import Request

from app.core.config import settings


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        trusted_network = ipaddress.ip_network(settings.trusted_proxy_network, strict=False)
        if ipaddress.ip_address(peer) not in trusted_network:
            return peer
    except ValueError:
        return peer

    forwarded_ip = request.headers.get("X-Real-IP")
    if forwarded_ip:
        try:
            return str(ipaddress.ip_address(forwarded_ip))
        except ValueError:
            pass
    return peer
