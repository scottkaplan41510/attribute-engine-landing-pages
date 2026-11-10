"""Limits on what a run may fetch. Only public web pages, ever."""

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrl(ValueError):
    pass


def is_public_host(host):
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return False
    return bool(addresses) and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses)


def check_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrl(f"Not a web address: {url}")
    if parts.username or parts.password:
        raise UnsafeUrl(f"Web addresses cannot contain a login: {url}")
    if not is_public_host(parts.hostname):
        raise UnsafeUrl(f"Not a public website: {url}")
    return url
