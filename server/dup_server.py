#!/usr/bin/env python3
"""Server side: receive both copies from the Mac, hand them to WireGuard (it drops the
duplicate), and send every reply back over every path seen in the last few seconds.
1-byte heartbeats from the Mac are echoed straight back on the same path."""
import selectors, socket, time

LISTEN, WG, KEEP, HB = ("0.0.0.0", 51821), ("127.0.0.1", 51820), 3.0, b"\x00"

pub = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); pub.bind(LISTEN)
wg = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); wg.bind(("127.0.0.1", 0)); wg.connect(WG)
for s in (pub, wg): s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
clients = {}  # addr -> last seen

sel = selectors.DefaultSelector()
sel.register(pub, selectors.EVENT_READ, "pub"); sel.register(wg, selectors.EVENT_READ, "wg")
while True:
    for key, _ in sel.select():
        if key.data == "pub":
            data, addr = pub.recvfrom(2048)
            clients[addr] = time.monotonic()
            if data == HB:
                pub.sendto(HB, addr)
            else:
                wg.send(data)
        else:
            data = wg.recv(2048)
            now = time.monotonic()
            for addr, seen in list(clients.items()):
                if now - seen > KEEP:
                    del clients[addr]
                else:
                    pub.sendto(data, addr)
