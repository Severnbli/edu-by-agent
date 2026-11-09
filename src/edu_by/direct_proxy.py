"""Minimal local HTTP proxy whose outgoing connections are bound to one network interface.

Lets containers and Chromium (which only understand proxies) reach the site over a chosen
interface, e.g. the physical uplink, bypassing a VPN that owns the default route
(wg-quick policy routing). Uses SO_BINDTODEVICE, which needs no root since Linux 5.7.

Supports CONNECT (HTTPS) and absolute-URI requests (plain HTTP). Listens on localhost only.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
from urllib.parse import urlsplit

SO_BINDTODEVICE = getattr(socket, "SO_BINDTODEVICE", 25)
MAX_HEADER = 64 * 1024


async def open_bound(host: str, port: int, interface: str | None, timeout: float = 15):
    """Connect to host:port with the socket bound to `interface`."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    last: Exception | None = None
    for family, type_, proto, _, addr in infos:
        sock = socket.socket(family, type_, proto)
        try:
            if interface:
                sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, interface.encode())
            sock.setblocking(False)
            await asyncio.wait_for(loop.sock_connect(sock, addr), timeout)
            return await asyncio.open_connection(sock=sock)
        except Exception as e:  # try the next address
            sock.close()
            last = e
    raise ConnectionError(f"cannot connect to {host}:{port} via {interface}: {last}")


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


def _split_hostport(value: str, default_port: int) -> tuple[str, int]:
    """'host:port' or '[v6]:port' -> (host, port)."""
    if value.startswith("["):
        host, _, rest = value[1:].partition("]")
        return host, int(rest[1:]) if rest.startswith(":") else default_port
    host, sep, port = value.rpartition(":")
    if sep and port.isdigit() and ":" not in host:
        return host, int(port)
    return value, default_port


async def handle(client_r, client_w, interface: str | None) -> None:
    try:
        head = await client_r.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        client_w.close()
        return
    lines = head.decode("latin-1").split("\r\n")
    try:
        method, target, version = lines[0].split(" ", 2)
    except ValueError:
        client_w.close()
        return

    try:
        if method.upper() == "CONNECT":
            host, port = _split_hostport(target, 443)
            up_r, up_w = await open_bound(host, port, interface)
            client_w.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_w.drain()
        else:
            url = urlsplit(target)
            if not url.hostname:
                raise ValueError("absolute URL required")
            up_r, up_w = await open_bound(url.hostname, url.port or 80, interface)
            path = (url.path or "/") + (f"?{url.query}" if url.query else "")
            headers = [
                h
                for h in lines[1:]
                if h
                and not h.lower().startswith(("proxy-connection:", "connection:", "keep-alive:"))
            ]
            # One request per upstream connection keeps the forwarding trivial.
            req = "\r\n".join([f"{method} {path} {version}", *headers, "Connection: close", "", ""])
            up_w.write(req.encode("latin-1"))
            await up_w.drain()
    except Exception as e:
        msg = f"proxy error: {e}".encode()
        client_w.write(
            b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\nConnection: close\r\n"
            + f"Content-Length: {len(msg)}\r\n\r\n".encode()
            + msg
        )
        with contextlib.suppress(Exception):
            await client_w.drain()
        client_w.close()
        return

    await asyncio.gather(_pipe(client_r, up_w), _pipe(up_r, client_w))


async def serve(host: str, port: int, interface: str | None) -> asyncio.base_events.Server:
    return await asyncio.start_server(
        lambda r, w: handle(r, w, interface), host, port, limit=MAX_HEADER
    )


def run(host: str, port: int, interface: str | None) -> None:
    async def main() -> None:
        server = await serve(host, port, interface)
        async with server:
            await server.serve_forever()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
