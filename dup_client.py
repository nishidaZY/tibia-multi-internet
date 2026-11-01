#!/usr/bin/env python3
"""Mac side: copy every WireGuard packet out Wi-Fi AND iPhone at once.
WireGuard drops the duplicate copy itself (replay counter), so no dedup needed.
Each path also exchanges a 1-byte heartbeat with the server every 0.5s so we know it's alive.
Usage: dup_client.py SERVER_IP SERVER_PORT LOCAL_PORT IFACE [IFACE ...]   (IFACE may be "wifi" or "iphone")"""
import json, os, selectors, socket, subprocess, sys, threading, time

server = (sys.argv[1], int(sys.argv[2]))
local_port = int(sys.argv[3])
ifaces = sys.argv[4:]
IP_BOUND_IF = 25  # macOS: pin a socket to one interface
HB = b"\x00"      # heartbeat; real WireGuard packets are >= 32 bytes
STATUS = "/var/run/tibia-mi.json"  # read by the menu app

wg = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
wg.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
wg.bind(("127.0.0.1", local_port))
wg_peer = None
sel = selectors.DefaultSelector()
sel.register(wg, selectors.EVENT_READ, "wg")
paths = {}    # iface -> socket (swapped whole by the manager thread, read by the forwarder)
last_rx = {}  # iface -> monotonic time of last packet from server
used = {}     # iface -> bytes sent+received this run, incl. 28-byte IP/UDP header (what the carrier bills)
lock = threading.Lock()


PORTS = {"wifi": "Wi-Fi", "iphone": "iPhone USB"}  # macOS hardware port names
label = {}  # real iface (en0, en7...) -> what the app shows ("wifi", "iphone")


def port_iface(port):
    out = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True).stdout.splitlines()
    for i, line in enumerate(out):
        if line.startswith("Hardware Port: " + port) and i + 1 < len(out):
            return out[i + 1].split()[-1]


def manager():
    """Slow work lives here so it never stalls packet forwarding: detect interfaces,
    open/close path sockets, send heartbeats, write status for the app."""
    global paths
    names, next_scan = [], 0
    while True:
        now = time.monotonic()
        if now >= next_scan:  # interface scan spawns processes: every 2s is plenty
            names = []
            for i in ifaces:
                n = port_iface(PORTS[i]) if i in PORTS else i
                if n: names.append(n); label[n] = i
            next_scan = now + 2
            new = dict(paths)
            for name in names:
                up = subprocess.run(["ipconfig", "getifaddr", name], capture_output=True).returncode == 0
                if up and name not in new:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
                        s.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, socket.if_nametoindex(name))
                        s.connect(server)
                        s.setblocking(False)
                        new[name] = s
                        with lock: sel.register(s, selectors.EVENT_READ, name)
                        print(f"path up: {name}", flush=True)
                    except OSError:
                        pass
                elif not up and name in new:
                    s = new.pop(name)
                    with lock: sel.unregister(s)
                    s.close(); print(f"path down: {name}", flush=True)
            paths = new
        for n, s in list(paths.items()):
            try: s.send(HB); used[n] = used.get(n, 0) + 29
            except OSError: pass
        t = time.monotonic()
        st = {label.get(n, n): round(t - last_rx.get(n, -1e9), 1) for n in paths}  # seconds since server last answered
        try:
            with open(STATUS + ".tmp", "w") as f: json.dump({"t": time.time(), "paths": st, "bytes": {label.get(n, n): b for n, b in dict(used).items()}}, f)
            os.chmod(STATUS + ".tmp", 0o644); os.replace(STATUS + ".tmp", STATUS)
        except OSError:
            pass
        time.sleep(0.5)


threading.Thread(target=manager, daemon=True).start()

while True:  # forwarder: nothing slow in here
    with lock:
        events = sel.select(timeout=0.2)
    for key, _ in events:
        try:
            data, addr = key.fileobj.recvfrom(2048)
        except OSError:
            continue
        if key.data == "wg":
            wg_peer = addr
            for n, s in list(paths.items()):
                try: s.send(data); used[n] = used.get(n, 0) + len(data) + 28
                except OSError: pass
        else:
            last_rx[key.data] = time.monotonic()
            used[key.data] = used.get(key.data, 0) + len(data) + 28
            if data != HB and wg_peer:
                wg.sendto(data, wg_peer)
