"""Tibia Multi-Internet for Windows: a small pill that floats over Tibia. While connected, every
Tibia game packet goes to your Oracle server over ALL your connections at once (Wi-Fi, cable,
iPhone USB or hotspot, Android USB). If one drops, the other copy is already arriving.
[● Wi-Fi ● Cable ● iPhone  12 MB  Connect]   green = working, red = failing, grey = not connected.
MB = phone data used by the tunnel this month. Drag to move. Right-click: reset counter / quit.
Run: pythonw multi_internet.pyw   (asks for admin: WireGuard needs it)
Self-check without Windows: python3 multi_internet.pyw --selftest"""
import ctypes, json, os, selectors, socket, struct, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # keys, server.ip and game-routes.txt live in the project folder
TUNNEL = "tibia-mi"
LOCAL, SERVER_PORT = 51830, 51821
HB = b"\x00"          # heartbeat; real WireGuard packets are >= 32 bytes
HEALTHY, DEAD = 2.5, 8  # seconds without a server answer: path counts as down / server counts as dead
IP_UNICAST_IF = 31    # Windows: send this socket's packets out one interface (index, network byte order)
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flashing over the game
PHONES = ("iPhone", "Phone")  # their data is counted
SKIP = ("wireguard", "wintun", "hyper-v", "virtualbox", "vmware", "tap-", "loopback")

# every IPv4 adapter that is up and has its own default gateway = one internet path
SCAN = ("Get-NetIPConfiguration | ? { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | % { "
        "[pscustomobject]@{i=$_.InterfaceIndex; ip=$_.IPv4Address[0].IPAddress; "
        "d=[string]$_.InterfaceDescription; m=[string]$_.NetAdapter.PhysicalMediaType} } | ConvertTo-Json -Compress")


def kind(desc, media, ip=""):
    d = desc.lower()
    if "apple mobile device" in d: return "iPhone"   # iPhone USB tethering (needs Apple Devices or iTunes)
    if ip.startswith("172.20.10."): return "iPhone"  # iPhone Personal Hotspot over Wi-Fi always uses 172.20.10.0/28
    if "ndis" in d: return "Phone"                   # Android USB tethering (Remote NDIS)
    if "802.11" in media or "wireless" in d or "wi-fi" in d or "wifi" in d: return "Wi-Fi"
    return "Cable"


def parse_scan(out):
    """PowerShell JSON -> {(ifindex, ip): label}; same-kind adapters get numbered (Cable, Cable 2)."""
    items = json.loads(out) if out.strip() else []
    if isinstance(items, dict): items = [items]  # ConvertTo-Json gives an object, not a list, for one adapter
    paths, seen = {}, {}
    for a in sorted(items, key=lambda a: a["i"]):
        if not a.get("ip") or any(s in a["d"].lower() for s in SKIP): continue
        k = kind(a["d"], a["m"], a["ip"]); seen[k] = seen.get(k, 0) + 1
        paths[(a["i"], a["ip"])] = k if seen[k] == 1 else f"{k} {seen[k]}"
    return paths


def make_conf(key, server_pub, routes):
    """WireGuard sends to our duplicator on 127.0.0.1; only the game routes enter the tunnel
    (Cloudflare blocks the Tibia login from datacenter IPs, so never the whole internet)."""
    return ("[Interface]\nPrivateKey = %s\nAddress = 10.66.0.2/32\nMTU = 1280\n\n[Peer]\nPublicKey = %s\n"
            "Endpoint = 127.0.0.1:%d\nAllowedIPs = %s\nPersistentKeepalive = 1\n"
            % (key, server_pub, LOCAL, ", ".join(r for r in routes if r)))


if "--selftest" in sys.argv:
    p = parse_scan('[{"i":12,"ip":"192.168.0.5","d":"Intel(R) Wi-Fi 6 AX201 160MHz","m":"Native 802.11"},'
                   '{"i":7,"ip":"192.168.0.6","d":"Realtek PCIe GbE Family Controller","m":"802.3"},'
                   '{"i":30,"ip":"172.20.10.2","d":"Apple Mobile Device Ethernet","m":"802.3"},'
                   '{"i":9,"ip":"10.0.0.2","d":"Remote NDIS based Internet Sharing Device","m":"802.3"},'
                   '{"i":40,"ip":"172.30.0.1","d":"Hyper-V Virtual Ethernet Adapter","m":"802.3"},'
                   '{"i":8,"ip":"10.1.0.2","d":"Intel(R) Ethernet I219-V","m":"802.3"}]')
    assert p == {(7, "192.168.0.6"): "Cable", (8, "10.1.0.2"): "Cable 2", (9, "10.0.0.2"): "Phone",
                 (12, "192.168.0.5"): "Wi-Fi", (30, "172.20.10.2"): "iPhone"}, p
    assert parse_scan('[{"i":5,"ip":"172.20.10.4","d":"Realtek 8852CE WiFi 6E PCI-E NIC","m":"Native 802.11"},'
                      '{"i":6,"ip":"192.168.15.76","d":"Realtek PCIe GbE Family Controller","m":"802.3"}]') == \
        {(5, "172.20.10.4"): "iPhone", (6, "192.168.15.76"): "Cable"}
    assert parse_scan('{"i":3,"ip":"1.2.3.4","d":"Realtek","m":"802.3"}') == {(3, "1.2.3.4"): "Cable"}
    assert parse_scan("") == {}
    c = make_conf("K", "P", ["1.0.0.0/8", "172.65.0.0/16", ""])
    assert "AllowedIPs = 1.0.0.0/8, 172.65.0.0/16\n" in c and "Endpoint = 127.0.0.1:51830" in c
    print("selftest ok"); sys.exit()

import tkinter as tk  # noqa: E402  (after the selftest so it runs anywhere)

WG_EXE = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WireGuard", "wireguard.exe")
CONF_DIR = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "tibia-mi")
CONF = os.path.join(CONF_DIR, TUNNEL + ".conf")
USAGE = os.path.join(os.environ.get("APPDATA", HERE), "tibia-mi", "usage.json")


def run(args, timeout=30):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(args, 1, "", str(e))


def read(name):
    with open(os.path.join(ROOT, name)) as f: return f.read().strip()


class Scanner(threading.Thread):
    """Finds the connections every 3 s, even while disconnected (so you see them before connecting)."""
    # shortcut: spawns PowerShell each scan (~0.5 s CPU); use GetAdaptersAddresses via ctypes if that ever matters
    def __init__(self):
        super().__init__(daemon=True); self.paths = {}

    def run(self):
        while True:
            r = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SCAN])
            try: self.paths = parse_scan(r.stdout)
            except (ValueError, KeyError, TypeError): pass
            time.sleep(3)


class Dup:
    """Copies every WireGuard packet out every path; WireGuard drops the duplicate itself (replay counter).
    Each path also exchanges a 1-byte heartbeat with the server every 0.5 s so we know it's alive."""
    def __init__(self, server, scanner):
        self.server, self.scanner = (server, SERVER_PORT), scanner
        self.wg = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wg.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        self.wg.bind(("127.0.0.1", LOCAL))
        self.sel, self.lock = selectors.DefaultSelector(), threading.Lock()
        self.sel.register(self.wg, selectors.EVENT_READ, "wg")
        self.paths, self.last_rx, self.used = {}, {}, {}  # key (ifindex, ip) -> socket / time / bytes incl. 28-byte IP+UDP header
        self.labels, self.peer, self.alive = {}, None, True
        for f in (self.forward, self.manage): threading.Thread(target=f, daemon=True).start()

    def manage(self):
        while self.alive:
            want = self.scanner.paths
            new = dict(self.paths)
            for k, label in want.items():
                self.labels[k] = label
                if k in new: continue
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
                    s.setsockopt(socket.IPPROTO_IP, IP_UNICAST_IF, struct.pack("!I", k[0]))
                    s.bind((k[1], 0)); s.connect(self.server); s.setblocking(False)
                except OSError:
                    continue
                new[k] = s
                with self.lock: self.sel.register(s, selectors.EVENT_READ, k)
            for k in [k for k in new if k not in want]:
                s = new.pop(k)
                with self.lock: self.sel.unregister(s)
                s.close()
            self.paths = new
            for k, s in list(new.items()):
                try: s.send(HB); self.used[k] = self.used.get(k, 0) + 29
                except OSError: pass
            time.sleep(0.5)

    def forward(self):  # nothing slow in here
        while self.alive:
            with self.lock:
                events = self.sel.select(timeout=0.2)
            for key, _ in events:
                try:
                    data, addr = key.fileobj.recvfrom(2048)
                except OSError:  # incl. Windows' WSAECONNRESET on UDP
                    continue
                if key.data == "wg":
                    self.peer = addr
                    for k, s in list(self.paths.items()):
                        try: s.send(data); self.used[k] = self.used.get(k, 0) + len(data) + 28
                        except OSError: pass
                else:
                    self.last_rx[key.data] = time.monotonic()
                    self.used[key.data] = self.used.get(key.data, 0) + len(data) + 28
                    if data != HB and self.peer:
                        try: self.wg.sendto(data, self.peer)
                        except OSError: pass

    def status(self):
        """[(label, seconds since the server last answered on that path)]"""
        t = time.monotonic()
        return [(self.labels.get(k, "?"), t - self.last_rx.get(k, -1e9)) for k in sorted(self.paths)]

    def phone_bytes(self):
        return sum(b for k, b in self.used.items() if self.labels.get(k, "").startswith(PHONES))

    def stop(self):
        self.alive = False
        time.sleep(0.6)
        for s in list(self.paths.values()) + [self.wg]:
            s.close()


def tunnel_down():
    run([WG_EXE, "/uninstalltunnelservice", TUNNEL])


def tunnel_up():
    routes = read("game-routes.txt").splitlines()
    tunnel_down()
    os.makedirs(CONF_DIR, exist_ok=True)
    # the config holds your private key: only Administrators and SYSTEM may read it
    run(["icacls", CONF_DIR, "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"])
    with open(CONF, "w", newline="\n") as f:
        f.write(make_conf(read("mac.key"), read("server.pub"), routes))
    return run([WG_EXE, "/installtunnelservice", CONF])


BG, KEY = "#141414", "#010203"  # KEY = transparent color outside the rounded pill
GREEN, RED, GREY = "#34c759", "#ff3b30", "#808080"
H = 28


class App:
    def __init__(self):
        self.scanner = Scanner(); self.scanner.start()
        self.dup, self.on, self.busy, self.since = None, False, False, 0
        self.shown, self.pending, self.msg, self.msg_until, self.sure_until = {}, {}, "", 0, 0
        self.last_phone, self.checking, self.server_dead = 0, False, False
        self.usage = self.load_usage()

        r = self.root = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True); r.attributes("-alpha", 0.85); r.attributes("-transparentcolor", KEY)
        self.c = tk.Canvas(r, height=H, bg=KEY, highlightthickness=0, bd=0)
        self.c.pack()
        self.c.bind("<ButtonPress-1>", self.press); self.c.bind("<B1-Motion>", self.drag)
        self.c.bind("<ButtonRelease-1>", self.release)
        m = self.menu = tk.Menu(r, tearoff=0)
        m.add_command(label="Reset data counter", command=self.reset_usage)
        m.add_command(label="Quit (disconnects)", command=self.quit)
        self.c.bind("<Button-3>", lambda e: m.tk_popup(e.x_root, e.y_root))
        r.update_idletasks()
        r.geometry(f"+{r.winfo_screenwidth() - 340}+{r.winfo_screenheight() - 90}")
        self.hwnd = ctypes.windll.user32.GetParent(r.winfo_id())
        u = ctypes.windll.user32
        # like OnTopReplica: a topmost tool window; NOACTIVATE = clicking it never takes focus away from Tibia
        u.SetWindowLongW(self.hwnd, -20, u.GetWindowLongW(self.hwnd, -20) | 0x80 | 0x08000000 | 0x8)
        r.protocol("WM_DELETE_WINDOW", self.quit)
        tunnel_down()  # a leftover tunnel from a crash would send the game into nothing
        self.tick(); self.keep_on_top()
        r.mainloop()

    # ---- topmost: Tibia (and fullscreen apps) can push themselves above us, so re-assert every second
    def keep_on_top(self):
        ctypes.windll.user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # HWND_TOPMOST, NOSIZE|NOMOVE|NOACTIVATE
        self.root.after(1000, self.keep_on_top)

    # ---- drag anywhere; a click without moving on the button = button press
    def press(self, e):
        self.start, self.moved = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()), False

    def drag(self, e):
        self.moved = True
        self.root.geometry(f"+{e.x_root - self.start[0]}+{e.y_root - self.start[1]}")

    def release(self, e):
        if not self.moved and "btn" in self.c.gettags(self.c.find_closest(e.x, e.y)[0]): self.toggle()

    # ---- connect / disconnect
    def toggle(self):
        if self.on or self.busy:
            if time.time() > self.sure_until:  # 2nd click within 3 s disconnects: a misclick mid-hunt does nothing
                self.sure_until = time.time() + 3; self.render(); return
            self.disconnect(); return
        missing = [f for f in ("server.ip", "server.pub", "mac.key", "game-routes.txt") if not os.path.exists(os.path.join(ROOT, f))]
        if missing: return self.say("Run windows\\setup.ps1 first")
        if not os.path.exists(WG_EXE): return self.say("Install WireGuard first")
        self.busy = True; self.render()
        threading.Thread(target=self.connect, daemon=True).start()

    def connect(self):
        try:
            self.dup = Dup(read("server.ip"), self.scanner)
        except OSError:
            self.busy = False; return self.say("Port 51830 busy: close other copies")
        r = tunnel_up()
        if r.returncode:
            self.dup.stop(); self.dup = None; self.busy = False
            return self.say("WireGuard failed: " + (r.stderr or r.stdout).strip()[:40])
        self.on, self.busy, self.since, self.last_phone = True, False, time.time(), 0

    def disconnect(self, why=""):
        self.on = self.busy = False; self.sure_until = 0
        tunnel_down()
        if self.dup: self.dup.stop(); self.dup = None
        self.shown, self.pending = {}, {}
        if why: self.say(why, 8)

    def quit(self):
        if (self.on or self.busy) and time.time() > self.sure_until:
            self.sure_until = time.time() + 3; self.say("Quit again to disconnect", 3); return
        self.disconnect(); self.save_usage(); self.root.destroy()

    # ---- every 0.5 s: path health, alerts, data counter, server watchdog
    def tick(self):
        self.root.after(500, self.tick)
        if self.server_dead:
            self.server_dead = False; self.disconnect("Server unreachable: normal internet now")
        if not (self.on and self.dup):
            return self.render()
        st = self.dup.status()
        pb = self.dup.phone_bytes(); self.add_usage(pb - self.last_phone); self.last_phone = pb
        for name, age in st:  # debounce: alert only after 2 ticks (1 s)
            up = age < HEALTHY
            if name not in self.shown: self.shown[name] = up; continue
            if self.shown[name] != up:
                self.pending[name] = self.pending.get(name, 0) + 1
                if self.pending[name] >= 2:
                    self.shown[name], self.pending[name] = up, 0
                    self.say(f"{name} {'back' if up else 'DOWN'}")
                    if not up: ctypes.windll.user32.MessageBeep(0x30)
            else:
                self.pending[name] = 0
        # server silent on every path while normal internet works -> server problem: fall back to normal internet
        if st and time.time() - self.since > 6 and min(a for _, a in st) >= DEAD and not self.checking:
            self.checking = True
            def check():
                ok = run(["ping", "-n", "1", "-w", "2000", "1.1.1.1"], 5).returncode == 0
                self.checking = False
                if ok and self.on: self.server_dead = True  # tk is only touched from the UI thread
            threading.Thread(target=check, daemon=True).start()
        self.render()

    def say(self, msg, secs=5):
        self.msg, self.msg_until = msg, time.time() + secs

    # ---- drawing
    def render(self):
        c = self.c; c.delete("all"); x = 12
        if self.on and self.dup:
            items = [(n, GREEN if self.shown.get(n, a < HEALTHY) else RED) for n, a in self.dup.status()]
        else:
            items = [(n, GREY) for n in sorted(set(self.scanner.paths.values()))] or [("no internet", GREY)]
        font, bold = ("Segoe UI", 9), ("Segoe UI Semibold", 9)
        for name, col in items:
            t = c.create_text(x, H / 2, text="●", fill=col, anchor="w", font=("Segoe UI", 11)); x = c.bbox(t)[2] + 3
            t = c.create_text(x, H / 2, text=name, fill="white", anchor="w", font=font); x = c.bbox(t)[2] + 10
        info = self.msg if time.time() < self.msg_until else gb(self.month_bytes())
        t = c.create_text(x, H / 2, text=info, fill="#d9d9d9", anchor="w", font=font); x = c.bbox(t)[2] + 10
        sure = time.time() < self.sure_until
        label = "Sure?" if sure else "…" if self.busy else "Disconnect" if self.on else "Connect"
        t = c.create_text(x + 9, H / 2, text=label, fill="white", anchor="w", font=bold, tags="btn")
        b = c.bbox(t)
        c.tag_lower(c.create_rectangle(b[0] - 8, 4, b[2] + 8, H - 4, fill=RED if sure else "#3a3a3c", outline="", tags="btn"))
        w = b[2] + 14
        rounded(c, 0, 0, w, H, 14, BG); c.config(width=w)

    # ---- phone data this month (resets on the 1st)
    def load_usage(self):
        try:
            with open(USAGE) as f: return json.load(f)
        except (OSError, ValueError): return {}

    def save_usage(self):
        try:
            os.makedirs(os.path.dirname(USAGE), exist_ok=True)
            with open(USAGE, "w") as f: json.dump(self.usage, f)
        except OSError: pass

    def month_bytes(self): return self.usage.get(time.strftime("%Y-%m"), 0)

    def add_usage(self, d):
        if d <= 0: return
        before = self.month_bytes(); self.usage[time.strftime("%Y-%m")] = before + d
        if int(before / 1e9) < int((before + d) / 1e9): self.say(f"Phone data: {gb(before + d)} this month", 8)  # every 1 GB
        if int(before / 1e6) != int((before + d) / 1e6): self.save_usage()

    def reset_usage(self): self.usage[time.strftime("%Y-%m")] = 0; self.save_usage()


def gb(b): return f"{int(b / 1e3)} KB" if b < 1e6 else f"{int(b / 1e6)} MB" if b < 1e9 else f"{b / 1e9:.2f} GB"


def rounded(c, x1, y1, x2, y2, r, fill):
    c.tag_lower(c.create_polygon(x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
                                 x1, y2, x1, y2 - r, x1, y1 + r, x1, y1, smooth=True, fill=fill, outline=""))


if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():  # WireGuard tunnels need admin: relaunch elevated (UAC prompt)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', HERE, 1)
        sys.exit()
    App()
