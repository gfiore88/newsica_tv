"""NewsicaTV application package."""

# Forza IPv4 per evitare i blocchi e i caricamenti infiniti IPv6 della VPS
import socket
_original_getaddrinfo = socket.getaddrinfo
def _patched_getaddrinfo(host, port, family=0, *args, **kwargs):
    return _original_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
socket.getaddrinfo = _patched_getaddrinfo
