# Tibia Multi-Internet

**For Windows and macOS.** Play Tibia over several internet connections at once.

Every game packet is sent over all of them. If one connection drops or lags, the other copy is already
arriving, so you don't disconnect. It works like ExitLag/NoPing "multi-internet", but it runs on your
own free server and costs nothing.

## Download

| | Connections it can use | Get it |
|---|---|---|
| **Windows 10 or 11** | Wi-Fi, cable, iPhone, Android | **[Download ZIP](https://github.com/nishidaZY/tibia-multi-internet/archive/refs/heads/main.zip)**, then follow the **[Windows guide](windows/README.md)** |
| **macOS** (Apple Silicon or Intel) | Wi-Fi, iPhone | Follow the **[macOS guide](macos/README.md)** |

The project is free and has no installer. The guide walks you through a setup script, which creates your own server.

### Which version?

| | **v2 (current, recommended)** | **v1 (old)** |
|---|---|---|
| What goes through the tunnel | Only your Tibia game servers and, on Windows, your TeamSpeak 3 server | Every Amazon address in your world's region, plus Tibia's Cloudflare range |
| YouTube, Twitch, Spotify, Discord | Never on your phone | Some of it lands in the tunnel and uses phone data |
| Streaming with OBS to Twitch | Normal internet only | Twitch's Brazil ingest is in the list: the upload is copied onto your phone (about 2.5–3 GB per hour) |
| A world on a new address | Detected by itself. The pill shows "Tibia NOT protected: relog" once, then that world is protected from the next login | Always covered, no relog needed |
| Download | **[v2 ZIP](https://github.com/nishidaZY/tibia-multi-internet/archive/refs/tags/v2.zip)** (or the main branch above) | **[v1 ZIP](https://github.com/nishidaZY/tibia-multi-internet/archive/refs/tags/v1.zip)** |

Both use the same server and the same keys, so you can switch any time: copy `server.ip`, `server.pub`, `mac.key` into the other version's folder, then log into a world and run setup to make that version's `game-routes.txt`.
v2's changes are on Windows. On macOS, both versions use the v1 route list.

## How it works

```
             ┌── Wi-Fi ───┐
Tibia ─ PC ──┼── Cable ───┼─ your free Oracle server ─ Tibia game server
             └── Phone ───┘
```

- Only Tibia **game** traffic (and, on Windows, your TeamSpeak 3 voice) uses the tunnel. Everything else, including the
  Tibia login, YouTube, Twitch and Spotify, uses your normal internet, so it never costs phone data.
- On Windows, a world you play later is detected and added by itself. The pill warns you until you relog.
  It only reads Windows' connection list, and never touches Tibia's process (BattlEye).
- A small floating pill shows each connection live: green = working, red = failing. It also shows how much phone data the tunnel used this month.
- If the server stops answering, it switches back to your normal internet and tells you.

Why not route all traffic? Cloudflare blocks the Tibia login from datacenter IPs. Only the game servers go through the tunnel.

## What you need

- A second internet connection. Wi-Fi and cable to the same router protect you from Wi-Fi drops, but not from your provider going down. For that, use your phone or a second provider.
- A free [Oracle Cloud](https://www.oracle.com/cloud/free/) account. It needs a credit or debit card for an identity check. You are not charged if you stay on the Always Free resources.

The same server works for both versions, so you can use it from a Mac and a PC, one at a time.

## License

Public domain ([Unlicense](LICENSE)). Do whatever you want with it.
