"""LAN discovery answers a broadcast-style question with a reachable URL."""

import socket
import threading

from app import discovery


def test_discovery_replies_with_reachable_url():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))                     # private port: never clashes with a running server
    threading.Thread(target=discovery._serve, args=(server, 8123), daemon=True).start()

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(3)
    client.sendto(b"STORYVERSE?", server.getsockname())
    reply, _ = client.recvfrom(256)
    assert reply == b"STORYVERSE http://127.0.0.1:8123"

    client.sendto(b"something else", server.getsockname())   # ignored, no crash
    client.sendto(b"STORYVERSE?", server.getsockname())
    assert client.recvfrom(256)[0].startswith(b"STORYVERSE http://")
    client.close(); server.close()
