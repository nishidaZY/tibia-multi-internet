# Tibia Multi-Internet (Windows)

The Windows version of [Tibia Multi-Internet](../README.md). Every Tibia game packet is sent over
**all your connections at once**. If one connection drops or lags, the other copy is already arriving, so you don't disconnect.

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

**Requirements:** Windows 10 or 11, and a free Oracle Cloud server. You can use the one you created with
the Mac version, or create one here.

---

## 1. Download the project

Download this repository (**Code → Download ZIP** on GitHub) and unzip it, e.g. to `C:\tibia-multi-internet`.
Or use `git clone` if you have Git.

## 2. Run setup

Open **PowerShell** in that folder: in File Explorer, open the folder, click the address bar, type `powershell`, and press Enter.

**Already have a server from the Mac version?** Copy these 4 files from the Mac's project folder into this folder:
`server.ip`, `server.pub`, `mac.key`, `game-routes.txt`. Then run:

```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1
```

**No server yet?** First do steps 1–2 of the [main tutorial](../README.md#1-find-where-your-tibia-world-is-hosted):
find your world's region, then create the Oracle account. To find the region on Windows, log into your Tibia world and run:

```powershell
py windows\make_routes_win.py
```

Then run setup with **your** Oracle home region:

```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1 sa-saopaulo-1
```

Setup installs **Python** and **WireGuard** with `winget` if they are missing.
If it installs Python, it asks you to reopen PowerShell and run it again. Setup then:

- creates your keys. They stay on your PC, never share them.
- opens your browser so you can log into Oracle
- creates the free server. "Out of capacity" is normal; it retries every 2 minutes on its own.
- puts a **Multi-Internet** shortcut on your desktop

Setup is safe to rerun: it continues where it stopped.

## 3. Connect your second internet

- **Wi-Fi + cable:** plug in the cable and stay connected to Wi-Fi too. Windows keeps both connections up.
- **iPhone:** install **Apple Devices** from the Microsoft Store (or iTunes) so Windows has the iPhone driver.
  Connect the iPhone by USB, tap **Trust**, and turn on **Settings → Personal Hotspot → Allow Others to Join**.
- **Android:** connect by USB and turn on **Settings → Hotspot & tethering → USB tethering**.

Before you connect, the pill shows each connection it found as a grey dot. If one is missing, Windows doesn't see it as an internet connection yet.

## 4. Play

Double-click **Multi-Internet** on the desktop and click **Yes** on the Windows prompt
(WireGuard needs administrator rights). Click **Connect**, wait for the green dots, then log into Tibia.

- **Drag** the pill anywhere.
- **Disconnect**: click it twice. The first click turns it red ("Sure?"), so a misclick mid-hunt does nothing.
- **Right-click**: reset the data counter, or quit. Quitting disconnects and restores your normal internet.
- If the server stops answering, the app switches back to your normal internet and tells you on the pill.

**Seeing the pill over Tibia:** the pill stays on top the same way [OnTopReplica](https://github.com/LorenzCK/OnTopReplica) does:
a Windows "topmost" window that never takes focus away from the game, re-raised every second.
This works when Tibia runs in a **window** (maximized or borderless). Windows doesn't let any normal app draw over an
*exclusive* fullscreen game; only programs that hook into the game itself can, and that risks BattlEye.
If you play fullscreen and can't see the pill, switch Tibia to windowed, maximized. You'll still hear a beep when a connection goes down.

**Phone data:** the tunnel sends every game packet over the phone too. Tibia uses little data,
but check your plan. The pill counts it and tells you every 1 GB.

---

## Troubleshooting

- **"WireGuard failed"**: reinstall WireGuard from <https://www.wireguard.com/install/>.
- **Tibia stopped connecting after a crash**: open Multi-Internet and quit it. This removes any leftover tunnel.
  Or run this as administrator: `& "C:\Program Files\WireGuard\wireguard.exe" /uninstalltunnelservice tibia-mi`.
- **Windows Firewall asks about Python**: allow it on private networks.
- **A world isn't covered** (lag goes away after Disconnect): log into that world, delete `game-routes.txt`, and run setup again.
- **Mac and PC with the same server**: they share the same key (`mac.key`), so use one at a time.

## Files

| File | What it does |
|---|---|
| `windows\setup.ps1` | Installs the tools, creates keys, routes, the Oracle server (or reuses yours), and the desktop shortcut |
| `windows\make_routes_win.py` | Finds your world's AWS region from Tibia's connection, then runs `make_routes.py` |
| `windows\multi_internet.pyw` | The pill and the duplicator. It sends each WireGuard packet out every connection (`IP_UNICAST_IF` pins a socket to one adapter). It also starts and stops the WireGuard tunnel service, which carries only the game routes |

The server side (`server\`) is the same as the Mac version, with no changes.

To uninstall: delete the folder, the desktop shortcut and `C:\ProgramData\tibia-mi`, then terminate the instance in the Oracle console.
