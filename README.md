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

## How it works

```
             ┌── Wi-Fi ───┐
Tibia ─ PC ──┼── Cable ───┼─ your free Oracle server ─ Tibia game server
             └── Phone ───┘
```

- Only Tibia **game** traffic uses the tunnel. Everything else, including the Tibia login, uses your normal internet.
- A small floating pill shows each connection live: green = working, red = failing. It also shows how much phone data the tunnel used this month.
- If the server stops answering, it switches back to your normal internet and tells you.

Why not route all traffic? Cloudflare blocks the Tibia login from datacenter IPs. Only the game servers go through the tunnel.

## What you need

- A second internet connection. Wi-Fi and cable to the same router protect you from Wi-Fi drops, but not from your provider going down. For that, use your phone or a second provider.
- A free [Oracle Cloud](https://www.oracle.com/cloud/free/) account. It needs a credit or debit card for an identity check. You are not charged if you stay on the Always Free resources.

The same server works for both versions, so you can use it from a Mac and a PC, one at a time.

## License

Public domain ([Unlicense](LICENSE)). Do whatever you want with it.
