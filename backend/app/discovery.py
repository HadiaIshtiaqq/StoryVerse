"""LAN discovery: headsets find this server even after the laptop's Wi-Fi IP changes.

A client broadcasts the UDP datagram ``STORYVERSE?`` to port 47800; the server replies (unicast) with
``STORYVERSE http://<this machine's address on that network>:<port>``. The address is chosen per request, so a
laptop with Wi-Fi + VirtualBox/WSL adapters always answers with the one the headset can actually reach.
Disable with DISCOVERY=0. If the port is taken (a second server, the test suite), discovery is skipped quietly.
"""

import logging
import os
import socket
import threading

log = logging.getLogger("storyverse.discovery")

DISCOVERY_PORT = 47800
_QUESTION = b"STORYVERSE?"
_thread: threading.Thread | None = None


def _address_towards(peer_ip: str) -> str:
    """The local IP the OS would use to reach `peer_ip` (no packet is sent by a UDP connect)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((peer_ip, DISCOVERY_PORT))
        return probe.getsockname()[0]
    finally:
        probe.close()


def _serve(sock: socket.socket, http_port: int) -> None:
    while True:
        try:
            data, (peer_ip, peer_port) = sock.recvfrom(256)
        except OSError:
            return
        if data.strip() != _QUESTION:
            continue
        try:
            reply = f"STORYVERSE http://{_address_towards(peer_ip)}:{http_port}".encode()
            sock.sendto(reply, (peer_ip, peer_port))
        except OSError as e:
            log.warning("discovery reply to %s failed: %s", peer_ip, e)


def start(http_port: int | None = None) -> bool:
    """Start the responder thread once. Returns False when disabled or the port is unavailable."""
    global _thread
    if _thread is not None:
        return True
    if os.getenv("DISCOVERY", "1") == "0":
        return False
    port = http_port or int(os.getenv("PORT", "8000"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
    except OSError as e:
        sock.close()
        log.info("LAN discovery not started (%s)", e)
        return False
    _thread = threading.Thread(target=_serve, args=(sock, port), name="lan-discovery", daemon=True)
    _thread.start()
    log.info("LAN discovery listening on UDP %d", DISCOVERY_PORT)
    return True
