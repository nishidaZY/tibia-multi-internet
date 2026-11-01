// Tibia Multi-Internet: a tiny pill that floats over the game.
// [● Wi-Fi ● iPhone  1.2 GB  Connect]  GB = iPhone data used by the tunnel this month.  green = that internet works, red = failing. Drag to move. Right-click: Quit (disconnects).
import AppKit

let guardScript = "/usr/local/tibia-mi/tibia-guard.sh"
let statusFile = "/var/run/tibia-mi.json"
let healthy = 2.5  // seconds without a server heartbeat before a path counts as down

final class Pill: NSView {
    var onClick: () -> Void = {}
    override func mouseDown(with e: NSEvent) {
        let start = e.locationInWindow
        var dragged = false
        while let ev = window?.nextEvent(matching: [.leftMouseDragged, .leftMouseUp]), ev.type == .leftMouseDragged {
            dragged = true
            let p = NSEvent.mouseLocation
            window?.setFrameOrigin(NSPoint(x: p.x - start.x, y: p.y - start.y))
        }
        _ = dragged
    }
}

final class ClickButton: NSButton {  // react on the first click even while Tibia has focus
    override func acceptsFirstMouse(for e: NSEvent?) -> Bool { true }
}

final class KeyPanel: NSPanel { override var canBecomeKey: Bool { true } }

final class App: NSObject, NSApplicationDelegate {
    var panel: KeyPanel!
    let label = NSTextField(labelWithString: "")
    var lastPhoneBytes = 0.0  // duplicator's per-run counter; we add its growth to the monthly total
    let button = ClickButton(title: "Connect", target: nil, action: nil)
    var on = false, busy = false
    var shown: [String: Bool] = [:], pending: [String: Int] = [:]  // debounce: alert only after 2 ticks (1s)

    func applicationDidFinishLaunching(_ n: Notification) {
        panel = KeyPanel(contentRect: NSRect(x: 0, y: 0, width: 268, height: 28),
                        styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]  // stays over fullscreen Tibia
        panel.hidesOnDeactivate = false
        panel.isOpaque = false; panel.backgroundColor = .clear; panel.hasShadow = false
        panel.alphaValue = 0.8

        let pill = Pill(frame: panel.contentRect(forFrameRect: panel.frame))
        pill.wantsLayer = true
        pill.layer?.backgroundColor = NSColor.black.withAlphaComponent(0.55).cgColor
        pill.layer?.cornerRadius = 14
        pill.toolTip = "Drag to move · Right-click to quit"
        let menu = NSMenu()
        menu.addItem(withTitle: "Reset data counter", action: #selector(resetUsage), keyEquivalent: "").target = self
        menu.addItem(withTitle: "Quit (disconnects)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "")
        pill.menu = menu

        label.frame = NSRect(x: 10, y: 6, width: 174, height: 16)
        pill.addSubview(label)
        label.toolTip = "Number = iPhone data used by Multi-Internet this month (resets on the 1st). Your phone's own apps aren't counted."
        button.target = self; button.action = #selector(toggle)
        button.bezelStyle = .rounded; button.controlSize = .small
        button.font = .systemFont(ofSize: 11, weight: .semibold)
        button.frame = NSRect(x: 184, y: 3, width: 78, height: 22)
        pill.addSubview(button)
        panel.contentView = pill

        if let f = NSScreen.main?.visibleFrame { panel.setFrameOrigin(NSPoint(x: f.maxX - 280, y: f.minY + 8)) }
        panel.orderFrontRegardless()
        render(wifi: nil, phone: nil)
        Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in self.tick() }
    }

    func applicationWillTerminate(_ n: Notification) {  // never leave the tunnel running without the app
        if on || busy { stop() }
    }

    @objc func toggle() {
        if on || busy {
            guard confirm("Disconnect multi-internet?") else { return }
            stop(); busy = false; return
        }
        guard FileManager.default.fileExists(atPath: guardScript) else {
            alert("Not installed: run sudo ./install.sh in the tibia-multi-internet folder"); return
        }
        busy = true
        run("/usr/bin/sudo", ["-n", guardScript], log: "/tmp/tibia-mi.log")
    }

    func confirm(_ q: String) -> Bool {  // guards against misclicks mid-game
        NSApp.activate(ignoringOtherApps: true)
        let a = NSAlert(); a.messageText = q; a.informativeText = "If your Wi-Fi drops after this, Tibia can disconnect."
        a.addButton(withTitle: "Keep connected"); a.addButton(withTitle: "Disconnect")
        return a.runModal() == .alertSecondButtonReturn
    }

    func applicationShouldTerminate(_ s: NSApplication) -> NSApplication.TerminateReply {
        (on || busy) && !confirm("Quit and disconnect?") ? .terminateCancel : .terminateNow
    }

    func stop() { run("/usr/bin/sudo", ["-n", "/usr/bin/pkill", "-TERM", "-f", "tibia-guard.sh"], wait: true) }

    func run(_ cmd: String, _ args: [String], wait: Bool = false, log: String? = nil) {
        let p = Process(); p.executableURL = URL(fileURLWithPath: cmd); p.arguments = args
        var out = FileHandle.nullDevice
        if let log, FileManager.default.createFile(atPath: log, contents: nil), let h = FileHandle(forWritingAtPath: log) { out = h }
        p.standardOutput = out; p.standardError = out
        try? p.run()
        if wait { p.waitUntilExit() }
    }

    func tick() {
        var paths: [String: Double] = [:]
        var live = false
        if let d = try? Data(contentsOf: URL(fileURLWithPath: statusFile)),
           let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
           let t = j["t"] as? Double, Date().timeIntervalSince1970 - t < 3 {
            live = true; paths = j["paths"] as? [String: Double] ?? [:]
            let phoneBytes = (j["bytes"] as? [String: Double] ?? [:]).filter { $0.key != "wifi" }.values.reduce(0, +)
            addUsage(phoneBytes < lastPhoneBytes ? phoneBytes : phoneBytes - lastPhoneBytes)  // smaller = duplicator restarted
            lastPhoneBytes = phoneBytes
        }
        if live { busy = false }
        on = live
        guard on else { shown = [:]; pending = [:]; render(wifi: nil, phone: nil); return }
        let wifi = (paths["wifi"] ?? 99) < healthy
        let phone = paths.contains { $0.key != "wifi" && $0.value < healthy }
        for (name, up) in [("Wi-Fi", wifi), ("iPhone", phone)] {
            if shown[name] == nil { shown[name] = up; continue }
            if shown[name] != up {
                pending[name, default: 0] += 1
                if pending[name]! >= 2 { shown[name] = up; pending[name] = 0; alert("\(name) \(up ? "back" : "DOWN")") }
            } else { pending[name] = 0 }
        }
        render(wifi: shown["Wi-Fi"] ?? wifi, phone: shown["iPhone"] ?? phone)
    }

    func render(wifi: Bool?, phone: Bool?) {
        let s = NSMutableAttributedString()
        for (name, up) in [("Wi-Fi", wifi), ("iPhone", phone)] {  // grey = off, green = working, red = failing
            s.append(NSAttributedString(string: "●", attributes: [.foregroundColor:
                up == nil ? NSColor.gray : (up! ? NSColor.systemGreen : NSColor.systemRed),
                .font: NSFont.systemFont(ofSize: 14)]))
            s.append(NSAttributedString(string: " \(name)  ", attributes: [.foregroundColor: NSColor.white,
                .font: NSFont.systemFont(ofSize: 11, weight: .medium)]))
        }
        s.append(NSAttributedString(string: gb(monthBytes), attributes: [  // same field = same baseline as the names
            .foregroundColor: NSColor.white.withAlphaComponent(0.85), .font: NSFont.monospacedDigitSystemFont(ofSize: 11, weight: .medium)]))
        label.attributedStringValue = s
        button.title = busy && !on ? "…" : (on ? "Disconnect" : "Connect")
    }

    var monthKey: String { "usage-" + String(ISO8601DateFormatter().string(from: Date()).prefix(7)) }  // e.g. usage-2026-11
    var monthBytes: Double { UserDefaults.standard.double(forKey: monthKey) }
    func gb(_ b: Double) -> String { b < 1e9 ? "\(Int(b / 1e6)) MB" : String(format: "%.2f GB", b / 1e9) }

    func addUsage(_ d: Double) {
        guard d > 0 else { return }
        let before = monthBytes
        UserDefaults.standard.set(before + d, forKey: monthKey)
        if Int(before / 1e9) < Int((before + d) / 1e9) { alert("iPhone data: \(gb(before + d)) used this month") }  // every 1 GB
    }

    @objc func resetUsage() { UserDefaults.standard.set(0, forKey: monthKey); render(wifi: shown["Wi-Fi"], phone: shown["iPhone"]) }

    func alert(_ msg: String) {  // macOS banner shows over fullscreen games
        run("/usr/bin/osascript", ["-e", "display notification \"\(msg)\" with title \"Multi-Internet\""])
    }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
