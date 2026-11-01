# Tibia Multi-Internet (macOS)

> **On Windows?** See the [Windows version](windows/README.md): Wi-Fi + cable + iPhone/Android, no Mac needed.

Play Tibia over **two internet connections at once**: your Wi-Fi and your iPhone (USB tethering).
Every game packet is sent over both. If one connection drops or lags, the other copy is already
arriving, so you don't disconnect. It works like ExitLag/NoPing "multi-internet", but it runs
on your own free server and costs nothing.

```
            ┌── Wi-Fi ──────┐
Tibia ─ Mac ┤               ├─ your free Oracle server ─ Tibia game server
            └── iPhone USB ─┘
```

- Only Tibia **game** traffic uses the tunnel. Everything else (and the Tibia login) uses your normal internet.
- A small floating pill shows both connections live: green = working, red = failing. It also shows how much iPhone data the tunnel used this month.
- If the server stops answering, it switches back to your normal internet and shows a notification.

**Requirements:** a Mac (Apple Silicon or Intel), an iPhone with Personal Hotspot and a USB cable,
and a credit/debit card for Oracle's identity check. You are not charged if you stay on the Always Free resources.
Android phones are not supported: macOS has no built-in driver for Android USB tethering.

---

## 1. Find where your Tibia world is hosted

Your server should sit close to the **game server**, not close to you. Install the Apple command line tools
if you don't have them (`xcode-select --install`), then download this project:

```bash
git clone <this repository's URL>
cd tibia-multi-internet
```

Log into your Tibia world, then run:

```bash
python3 make_routes.py
```

It prints the region your world runs in and the Oracle region to choose, for example:

```
Wrote game-routes.txt (52 ranges) for: sa-east-1
  sa-east-1 -> pick Oracle home region: sa-saopaulo-1
```

If it can't find your game connection, name the region yourself (`python3 make_routes.py eu-central-1`).
Common ones:

| Your world's AWS region | Oracle home region to choose |
|---|---|
| `sa-east-1` (South America) | `sa-saopaulo-1` (Brazil East, São Paulo) |
| `us-east-1` / `us-east-2` (North America) | `us-ashburn-1` (US East, Ashburn) |
| `eu-central-1` (Europe) | `eu-frankfurt-1` (Germany Central, Frankfurt) |
| `eu-west-1` / `eu-west-2` | `uk-london-1` (UK South, London) |
| `ap-southeast-2` (Oceania) | `ap-sydney-1` (Australia East, Sydney) |

You play worlds in more than one region? Pass them all (`python3 make_routes.py sa-east-1 us-east-1`)
and pick the Oracle region nearest the world you play most.

## 2. Create your free Oracle Cloud account

1. Go to <https://www.oracle.com/cloud/free/> and click **Start for free**.
2. Fill in your details. For **Home Region**, choose the region from step 1.
   **This is permanent**, and free servers can only be created in the home region.
3. Add a card. Oracle uses it only to check your identity. You may see a small temporary hold.
4. Wait for the "account ready" email. This takes from a few minutes up to a few hours.
5. Optional, but recommended: in the console, go to **Billing → Upgrade and Manage Payment** and upgrade to
   **Pay As You Go**. Always Free resources stay free. You also get a much better chance of a free server
   being available, and Oracle won't reclaim it for being idle. Set a budget alert (**Billing → Budgets**,
   e.g. $1) if you want to be safe.

## 3. Run setup

You need [Homebrew](https://brew.sh). Then run setup with **your** home region:

```bash
./setup.sh sa-saopaulo-1
```

The script:
- installs `wireguard-tools` and `oci-cli`
- creates your private keys. They stay on your Mac, never commit them.
- opens your browser so you can log into Oracle. Pick your region and sign in.
- creates a small network that only lets in SSH and the tunnel port
- creates the free server (Ubuntu, Always Free shape), which installs WireGuard by itself

**"Out of capacity" is normal** for free servers in busy regions. The script retries every 2 minutes on its own.
Leave the terminal open (`caffeinate -i ./setup.sh <region>` keeps the Mac awake). It can take minutes or days.
Upgrading to Pay As You Go (step 2.5) usually fixes it right away. The Oracle login lasts 24 h.
If it expires, run `./setup.sh <region>` again. It continues where it stopped.

## 4. Install the app

```bash
sudo ./install.sh
```

This builds **Multi-Internet** into `/Applications` and lets it start and stop the tunnel without asking for your password.

## 5. Set up the iPhone

1. Connect the iPhone by USB and turn on **Settings → Personal Hotspot → Allow Others to Join**.
2. On the Mac, open **System Settings → Network → iPhone USB** and turn **Disable unless needed** OFF.
   Otherwise macOS keeps the iPhone idle while Wi-Fi works, and there is no second path.
3. On the Mac, go to **System Settings → Privacy & Security → Allow accessories to connect** and choose **Always**
   (or approve the iPhone when asked).
4. Drag **iPhone USB** *below* Wi-Fi in **System Settings → Network → ⋯ → Set Service Order**.
   This way normal browsing stays on Wi-Fi and doesn't use phone data.

## 6. Play

Open **Multi-Internet**, click **Connect**, and wait for two green dots. Then log into Tibia.
You can drag the pill anywhere. Right-click it to quit. Quitting disconnects the tunnel and restores normal internet.

**Phone data:** the tunnel sends every game packet over the iPhone too. Tibia uses little data, but
check your mobile plan. The pill counts it, and you get a notification every 1 GB.

---

## Troubleshooting

- **Dots stay grey / red right after creating the server**: the server needs ~3 minutes to install itself after it boots.
- **A world isn't covered** (lag goes away after Disconnect): log into that world, run `python3 make_routes.py`, then `sudo ./install.sh`.
- **Oracle deleted or stopped your server**: idle free servers can be reclaimed. Move `oci.instance` out of the folder,
  run `./setup.sh <region>` again, then `sudo ./install.sh` (the server IP changes).
- **Log in to the server**: `ssh -i oracle_ssh ubuntu@$(cat server.ip)`. Check the tunnel with `sudo wg` and `systemctl status dup`.
- **Logs on the Mac**: `/tmp/tibia-mi.log`.

## How it works

| File | What it does |
|---|---|
| `make_routes.py` | Builds `game-routes.txt` from AWS's public IP list for your world's region, plus Cloudflare `172.65.0.0/16` |
| `setup.sh` | Creates keys, routes, the Oracle network and the server |
| `server/userdata.sh` | First-boot script on the server: WireGuard, NAT, firewall, duplicator service, watchdog |
| `server/dup_server.py` | Server side: gets both copies, hands them to WireGuard (it drops the duplicate), sends every reply back over both paths |
| `dup_client.py` | Mac side: sends every WireGuard packet out Wi-Fi and the iPhone, each socket pinned to its interface. Heartbeats measure each path |
| `tibia-guard.sh` | Starts the tunnel, adds the game routes, turns off IPv6 (so the game can't bypass the tunnel), and falls back if the server dies |
| `app/MultiInternet.swift` | The floating pill |
| `install.sh` | Installs everything to `/usr/local/tibia-mi` and `/Applications` |

Why not route all traffic? Cloudflare blocks the Tibia login from datacenter IPs. Only the game servers go through the tunnel.

To uninstall: `sudo rm -rf /usr/local/tibia-mi /etc/sudoers.d/tibia-mi /Applications/Multi-Internet.app`,
then terminate the instance in the Oracle console.

## License

Public domain ([Unlicense](LICENSE)). Do whatever you want with it.
