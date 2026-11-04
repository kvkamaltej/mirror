# Mirror on Linux and macOS — plan

Status: **plan only**, nothing implemented yet. Written 2026-11-04 against Mirror 3.0.0 (`mirror.pyw`, ~2,800 lines).

## 1. Where we start

Most of Mirror is already portable: Python + Tk + the sv-ttk theme, scrcpy, adb, mDNS, the LAN scanner's TCP
probes, the QR code and the settings logic all run on Linux and macOS.

The Windows-only parts (from `grep` of `mirror.pyw`):

| Area | Windows code today | Lines |
|---|---|---|
| Find / track / hide the scrcpy window, send it Alt+key shortcuts, keep-on-top, close it | `class Win` (user32 / dwmapi via ctypes), `PostMessageW(WM_CLOSE)`, `ShowWindow(SW_HIDE)` | 615–740, 863, 887 |
| Remote bar docking, rounded corners, dark title bar | `wm_frame()` HWNDs, `DwmSetWindowAttribute` | 756–762, 1095, 1172 |
| Drag & drop of APK files | `WM_DROPFILES` subclassing | 572–610 |
| Phone detection with USB debugging off | PowerShell `Win32_PnPEntity` query | 516–550 |
| "No developer mode" options | Miracast (`ms-settings:project`), Phone Link (`shell:AppsFolder`) | 1720–1733 |
| Process handling | `CREATE_NO_WINDOW`, `taskkill /T /F` | 40, 184, 243, 852, 2189 |
| OS integration | `os.startfile`, `explorer /select`, `winreg` dark-mode, `SetProcessDpiAwareness` | 554, 747, 2716, 2776, 2805 |
| Paths & names | `%APPDATA%`, `%LOCALAPPDATA%`, `adb.exe`, `scrcpy.exe`, Android SDK path | 57, 83–86, 214–217 |
| Fonts | Segoe UI Variable + **Segoe Fluent Icons** (every icon in the app is a Segoe glyph) | 128, 1435–1437 |
| Network | `arp -a` output format | 395 |
| Packaging | `build.bat`, PyInstaller one-file `.exe`, scrcpy **win64** release | build.bat, get-scrcpy.ps1 |

## 2. Approach

Keep **one codebase**. Move every OS-specific call behind a small `platform/` layer with three implementations
(`win.py`, `linux.py`, `mac.py`) and one interface. Feature code (`App`, `RemoteBar`, `Recorder`, …) stops calling
ctypes or shell commands directly.

```
mirror/
  app.py            UI and feature logic (from mirror.pyw)
  platform/
    base.py         interface + safe no-op defaults
    win.py          today's Win32 code, moved, not rewritten
    linux.py
    mac.py
  assets/icons.ttf  bundled icon font (replaces Segoe Fluent Icons)
```

Interface (first cut):

| Method | Windows | Linux (X11) | Linux (Wayland) | macOS |
|---|---|---|---|---|
| `find_window(pid)` / `window_rect` / `is_minimized` / `is_fullscreen` | user32 | `python-xlib` (`_NET_WM_PID`, geometry, `_NET_WM_STATE`) | **not possible** (no global window positions) | Quartz `CGWindowListCopyWindowInfo` (pyobjc) |
| `send_shortcut(win, key)` (scrcpy Alt/Cmd + key) | `keybd_event` | XTest via python-xlib (or `xdotool`) | **not possible** → adb fallback | `CGEventPost` (needs Accessibility permission) |
| `set_topmost(win)` | `SetWindowPos` | `_NET_WM_STATE_ABOVE` | no | AX API, or scrcpy `--always-on-top` at start |
| `close_gracefully(proc)` (recorder) | `WM_CLOSE` | **`SIGINT`** | `SIGINT` | `SIGINT` |
| `kill_tree(proc)` | `taskkill /T` | `os.killpg` (start with `start_new_session=True`) | same | same |
| `usb_phones()` (debugging off) | PnP / CompatibleID | `/sys/bus/usb/devices/*` (interface class `ff/42/01` = adb, `06/01/01` = MTP) | same | `system_profiler SPUSBDataType -json` / `ioreg` |
| `open_uri / reveal_file` | `os.startfile`, `explorer /select` | `xdg-open` | same | `open`, `open -R` |
| `system_dark_mode()` | registry | `gsettings … color-scheme` / portal | same | `defaults read -g AppleInterfaceStyle` |
| `config_dir / data_dir` | `%APPDATA%`, `%LOCALAPPDATA%` | `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME` | same | `~/Library/Application Support/Mirror` |
| `neighbours()` (ARP) | `arp -a` | `ip neigh` | same | `arp -an` |
| `file_drop(widget, cb)` | WM_DROPFILES | `tkinterdnd2` | `tkinterdnd2` | `tkinterdnd2` |

Notes:
- **Graceful recorder stop gets simpler on Linux and macOS.** scrcpy finalises the file on `SIGINT`, so the hidden-window trick is
  Windows-only. Verify this with an MP4 before relying on it, as we did on Windows.
- **The scrcpy shortcut modifier on macOS** should be `--shortcut-mod=lcmd`, because Alt is used for typing characters on macOS.

## 3. Platform-specific decisions

### Linux
- **Wayland is the big limit.** Apps can't read other windows' positions or inject keys. On Wayland the remote bar
  becomes a **free-floating toolbar** (the user places it; the position is remembered) instead of docking. Buttons send
  `adb shell input keyevent` (about 150 ms slower), and full screen is a hint ("press Alt+F in the mirror window").
  X11 (and XWayland sessions) get the docked bar, like Windows.
- **USB permissions.** adb on Linux needs udev rules (`51-android.rules`, `plugdev` group). The Get started page
  gains a Linux step, "Allow USB access", with a one-click helper that runs `pkexec` to install the rules. Distros
  shipping `android-udev` already have them.
- **Without developer mode:** there's no Phone Link and no Miracast receiver on Linux. That card shows
  "not available on Linux" and points to the companion-app idea (section 6).

### macOS
- **Permissions.** Sending shortcuts and tracking windows needs **Accessibility** (and, on some versions, **Screen
  Recording** to read window titles). The Get started page checks both and opens the right pane in System Settings.
  Without them, the bar floats freely and uses adb for keys, like Wayland.
- **Gatekeeper.** An unsigned app is blocked. Shipping needs an Apple Developer ID (USD 99/year), code signing
  **and notarization** of the `.app`, including the bundled scrcpy/adb binaries.
- **Apple Silicon and Intel:** either two builds (`arm64`, `x86_64`) or one universal2 build.
- **Without developer mode:** macOS has no Android casting receiver and no Phone Link. Same as Linux.

### All platforms
- **Icons:** bundle an open icon font (e.g. Microsoft *Fluent UI System Icons*, MIT, which keeps the same look) and
  map glyph names instead of Segoe code points. Fonts: fall back to the system UI font.
- **Upgrade scrcpy 2.5 → 3.x.** 3.x publishes official Linux and macOS builds; 2.5 only has Windows. Recheck the
  flags we use (`--no-video`, `--record-format`, `--shortcut-mod`, `--window-*`) against 3.x. adb comes from the
  platform-tools for each OS.
- **Dropping the Windows-only `bin\*.exe` assumption:** `get-scrcpy.ps1` becomes `tools/get_scrcpy.py`, which
  downloads the right archive for the current OS and architecture.

## 4. Packaging

| | Windows | Linux | macOS |
|---|---|---|---|
| Format | one-file `Mirror.exe` (today) | **AppImage** (one file, runs on most distros) + optional `.deb` | `Mirror.app` in a `.dmg` |
| Build | PyInstaller on Windows | PyInstaller on an old-glibc base (e.g. Ubuntu 20.04 container) | PyInstaller on macOS (universal2 or two builds) |
| Signing | optional (SmartScreen warning) | none | **required**: codesign + notarize |
| Bundled | scrcpy win64 + adb | scrcpy linux-x86_64 + adb | scrcpy macos + adb |

**CI:** a GitHub Actions matrix (`windows-latest`, `ubuntu-22.04`, `macos-14`) builds all three on every tag and
attaches them to a GitHub Release. PyInstaller can't cross-compile, so every build runs on its own OS.

## 5. Phases

| # | Work | Outcome | Rough size |
|---|---|---|---|
| 0 | Split `mirror.pyw` into a package; move Win32 code into `platform/win.py` with **no behaviour change**; add smoke tests | Windows build identical to today | 1–2 days |
| 1 | Icon font + font fallback; config/data dirs; `kill_tree` / `open` / `reveal` / ARP / dark mode per OS | Runs on Linux and macOS: mirroring, recording, wireless, scanner. Remote bar floating, keys via adb | 2–3 days |
| 2 | Linux X11 docking + shortcuts (python-xlib); Linux USB detection (`/sys`) + udev helper on Get started | Linux X11 at parity with Windows | 2–3 days |
| 3 | macOS window tracking + shortcuts (pyobjc), permission checks on Get started, `lcmd` modifier | macOS at parity, given the permissions | 3–4 days |
| 4 | scrcpy 3.x upgrade + `get_scrcpy.py`; AppImage, `.app`/`.dmg`, notarization; CI matrix + Releases | Downloadable builds for all three | 2–4 days (+ Apple account setup) |
| 5 | Test pass on real machines: Ubuntu GNOME (Wayland + X11), Fedora KDE, macOS 14/15 Intel + Apple Silicon, 3–4 phone brands | Release | 2–3 days |

**Total:** about 2.5–4 weeks of focused work for one developer. Phases 0–1 alone give a usable Linux/macOS version.

## 6. "No developer mode" beyond Windows

On Windows, Miracast and Phone Link cover users who won't enable developer options. Linux and macOS have no such
built-in path. The only cross-platform answer is a **Mirror companion app** for Android:
- **Screen capture** through Android's normal screen-capture permission (MediaProjection): no developer options needed.
- **Streaming** to the desktop app over Wi-Fi or USB.
- **Control** (optional) through an Accessibility service, which the user enables like any other app.

That's a separate project (Android app, Play Store listing, protocol, encoder/decoder, about 4–6 weeks), and should be
decided on its own.

## 7. Risks / open questions

1. **Wayland docking:** check whether a portal or compositor-specific protocol (e.g. KDE's KWin scripting) is worth it,
   or whether the floating bar is good enough.
2. **macOS notarization** needs an Apple Developer account. Who owns it?
3. **scrcpy 3.x** may change flags or behaviour we depend on. It needs a regression pass on Windows too.
4. **Which Linux distros and desktops to support officially?** Proposed: Ubuntu LTS (GNOME) and Fedora (KDE).
