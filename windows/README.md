# Tibia Multi-Internet (Windows)

**[Download ZIP](https://github.com/nishidaZY/tibia-multi-internet/archive/refs/heads/main.zip)**, then follow the steps below. On a Mac? See the [macOS guide](../macos/README.md).

Every Tibia game packet is sent over **all your connections at once**. If one connection drops or lags, the other copy is already arriving, so you don't disconnect.

It works with any two (or more) of:

- **Wi-Fi**
- **Cable** (Ethernet)
- **iPhone** (USB tethering)
- **Android phone** (USB tethering)

A small pill floats over Tibia and shows each connection live:

```
[● Wi-Fi ● Cable ● iPhone   12 MB   Connect]
```

Green means the connection is working, red means it's failing, and grey means you're not connected.
The MB number is the phone data the tunnel used this month.

```
             ┌── Wi-Fi ───┐
Tibia ─ PC ──┼── Cable ───┼─ your free Oracle server ─ Tibia game server
             └── iPhone ──┘
```

> **Wi-Fi + cable to the same router is still the same internet.** It protects you from Wi-Fi drops and
> interference, but not from your provider going down. For that, add a connection from a **different
> internet**: your phone, a second provider, or a 4G router.

**Requirements:** Windows 10 or 11, a free Oracle Cloud server, and a credit/debit card for Oracle's identity check.
You are not charged if you stay on the Always Free resources. You can also use a server you created with the Mac version.

---

## 1. Download the project

**[Download the ZIP](https://github.com/nishidaZY/tibia-multi-internet/archive/refs/heads/main.zip)** and unzip it, e.g. to `C:\tibia-multi-internet`.
Or use `git clone` if you have Git.

Open **PowerShell** in the folder that contains `README.md`: in File Explorer, open that folder, click the address bar, type `powershell`, and press Enter.

**Already have a server from the Mac version?** Copy these 4 files from the Mac's project folder into this folder:
`server.ip`, `server.pub`, `mac.key`, `game-routes.txt`. Run the command in step 2, then go to step 5.

## 2. Find where your Tibia world is hosted

Your server should sit close to the **game server**, not close to you. Log into your Tibia world, then run:

```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1
```

This installs **Python** and **WireGuard** with `winget` if they are missing. If it installs Python, it asks you to reopen PowerShell and run the command again.

It then finds your world's game server (and your TeamSpeak 3 server, if TeamSpeak is open) and prints the Oracle region to choose, for example:

```
Wrote game-routes.txt: Tibia 172.65.196.38 18.228.57.100, TeamSpeak 51.81.31.251
  sa-east-1 -> pick Oracle home region: sa-saopaulo-1
```

Only these addresses go through the tunnel. YouTube, Twitch, Spotify, Discord and everything else stay on your
normal internet, so they never use phone data.

If you don't have a server yet, it stops here and asks for your Oracle home region. That's expected: you create the account in the next step.

If it can't find your game connection, name the AWS region yourself (`py windows\make_routes_win.py eu-central-1`). Common ones:

| Your world's AWS region | Oracle home region to choose |
|---|---|
| `sa-east-1` (South America) | `sa-saopaulo-1` (Brazil East, São Paulo) |
| `us-east-1` / `us-east-2` (North America) | `us-ashburn-1` (US East, Ashburn) |
| `eu-central-1` (Europe) | `eu-frankfurt-1` (Germany Central, Frankfurt) |
| `eu-west-1` / `eu-west-2` | `uk-london-1` (UK South, London) |
| `ap-southeast-2` (Oceania) | `ap-sydney-1` (Australia East, Sydney) |

## 3. Create your free Oracle Cloud account

1. Go to <https://www.oracle.com/cloud/free/> and click **Start for free**.
2. Fill in your details. For **Home Region**, choose the region from step 2.
   **This is permanent**, and free servers can only be created in the home region.
3. Add a card. Oracle uses it only to check your identity. You may see a small temporary hold.
4. Wait for the "account ready" email. This takes from a few minutes up to a few hours.
5. Optional, but recommended: in the console, go to **Billing → Upgrade and Manage Payment** and upgrade to
   **Pay As You Go**. Always Free resources stay free. You also get a much better chance of a free server
   being available, and Oracle won't reclaim it for being idle. Set a budget alert (**Billing → Budgets**,
   e.g. $1) if you want to be safe.

## 4. Finish setup

Run setup again with **your** Oracle home region:

```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1 sa-saopaulo-1
```

Setup then:

- creates your keys. They stay on your PC, never share them.
- opens your browser so you can log into Oracle
- creates the free server. "Out of capacity" is normal; it retries every 2 minutes on its own.
- puts a **Multi-Internet** shortcut on your desktop

Setup is safe to rerun: it continues where it stopped.

## 5. Connect your second internet

- **Wi-Fi + cable:** plug in the cable and stay connected to Wi-Fi too. Windows keeps both connections up.
- **iPhone:** install **Apple Devices** from the Microsoft Store (or iTunes) and open it once, so it installs the iPhone driver.
  Connect the iPhone by USB, tap **Trust**, and turn on **Settings → Personal Hotspot → Allow Others to Join**.
  You can also join the iPhone's hotspot over Wi-Fi (with cable for your home internet): the pill still shows it as iPhone and counts its data.
- **Android:** connect by USB and turn on **Settings → Hotspot & tethering → USB tethering**.

Before you connect, the pill shows each connection it found as a grey dot. If one is missing, Windows doesn't see it as an internet connection yet.

## 6. Play

Double-click **Multi-Internet** on the desktop and click **Yes** on the Windows prompt
(WireGuard needs administrator rights). Click **Connect**, wait for the green dots, then log into Tibia.

- **Drag** the pill anywhere.
- **Disconnect**: click it twice. The first click turns it red ("Sure?"), so a misclick mid-hunt does nothing.
- **Right-click**: reset the data counter, or quit. Quitting disconnects and restores your normal internet.
- If the server stops answering, the app switches back to your normal internet and tells you on the pill.

**Seeing the pill over Tibia:** the pill stays on top the same way [OnTopReplica](https://github.com/LorenzCK/OnTopReplica) does:
it's a Windows "always on top" (topmost) window. It also re-raises itself every second, and clicking it never takes focus away from the game.
This works when Tibia runs in a **window** (maximized or borderless). Windows doesn't let any normal app draw over an
*exclusive* fullscreen game; only programs that hook into the game itself can, and that risks BattlEye.
If you play fullscreen and can't see the pill, switch Tibia to windowed, maximized. You'll still hear a beep when a connection goes down.

**Phone data:** the tunnel sends every game packet over the phone too. Tibia uses about 15–20 MB per hour,
TeamSpeak voice about 30–50 MB per hour. Videos, streams and music don't go through the tunnel. The pill counts
the phone data and tells you every 1 GB.

**Other worlds and new addresses are picked up by themselves.** If Tibia connects to a game server that isn't in
the tunnel yet (an alt on another world, or a world that moved), the pill turns red: **"Tibia NOT protected: relog"**.
It adds that server's whole Amazon block on its own (Tibia gets a different address on each login), and after you log out it reloads the tunnel. From your next login, that world is protected.
A new TeamSpeak 3 server is added the same way. TeamSpeak reconnects by itself after the reload.
This only reads Windows' list of open connections (like `netstat`). It never touches Tibia's process, files or memory.

---

## Troubleshooting

- **"WireGuard failed"**: reinstall WireGuard from <https://www.wireguard.com/install/>.
- **Tibia stopped connecting after a crash**: open Multi-Internet and quit it. This removes any leftover tunnel.
  Or run this as administrator: `& "C:\Program Files\WireGuard\wireguard.exe" /uninstalltunnelservice tibia-mi`.
- **Can't find the pill**: open Multi-Internet again. Only one copy can run, so this doesn't disturb your connection: it moves the open pill to the bottom-right corner of your main monitor. If that copy has frozen, a message tells you what to do.
- **Windows Firewall asks about Python**: allow it on private networks.
- **"Tibia NOT protected: relog"**: that world isn't in the tunnel yet. It has already been added: log out and back in.
- **Set up before this version?** Your `game-routes.txt` holds every AWS range in your region, so some video and website traffic uses phone data too.
  To keep only Tibia and TeamSpeak: log into a world, open TeamSpeak, then run `py windows\make_routes_win.py` and restart the pill.
- **Mac and PC with the same server**: they share the same key (`mac.key`), so use one at a time.

## Files

| File | What it does |
|---|---|
| `windows\setup.ps1` | Installs the tools, creates keys, routes, the Oracle server (or reuses yours), and the desktop shortcut |
| `windows\make_routes_win.py` | Writes `game-routes.txt` from Tibia's game connection (port 7171) and TeamSpeak 3's log, and prints your Oracle region. Name a region (`sa-east-1`) for the old, broad list from `make_routes.py` |
| `windows\multi_internet.pyw` | The pill and the duplicator. It sends each WireGuard packet out every connection (`IP_UNICAST_IF` pins a socket to one adapter). It also starts and stops the WireGuard tunnel service, which carries only the game routes, and adds new Tibia or TeamSpeak servers to them |

The server side (`server\`) is the same as the Mac version, with no changes.

To uninstall: delete the folder, the desktop shortcut and `C:\ProgramData\tibia-mi`, then terminate the instance in the Oracle console.
