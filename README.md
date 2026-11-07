# Mirror

A small Windows app that mirrors and controls an Android phone from the PC, over USB or Wi-Fi.
`dist\Mirror.exe` is one portable file (about 18 MB) with scrcpy 2.5 and adb built in.
Nothing needs to be installed on the PC. It uses a Windows 11 style with light and dark themes
(it follows Windows by default).

## Phone setup (once) — the Get started page
Mirror opens on **Get started** the first time, and whenever a phone is plugged in but not ready. It works for any
Android phone:
1. Open Settings and search for **Build number** (on some phones *Software version* or *OS version*). Tap it 7 times.
2. Search Settings for **USB debugging** and turn it on.
3. Plug in the phone and tap **Allow** (tick *Always allow from this computer*).

A live checklist (*plugged in → USB debugging on → PC allowed*) updates by itself. Mirror sees a plugged-in phone
even while debugging is still off: it looks for the USB interfaces every Android phone has (adb, or MTP file
transfer), not a list of brands. When the brand is known, the page also shows its exact Settings path
(Samsung, Xiaomi, OnePlus/OPPO/Realme, vivo, Huawei/Honor, Pixel and others).

**No developer mode?** The same page offers view-only options that need no phone settings: Windows
**Wireless Display** (Miracast) and Microsoft **Phone Link**.

## Linux and macOS
Not supported yet. See [docs/cross-platform-plan.md](docs/cross-platform-plan.md).

## Pages
- **Mirror:** Start or stop mirroring. Quality can be Auto (USB High, Wi-Fi Low), Low, Medium or High.
  Switches: screen off, keep awake, always on top, remote beside the phone, view only, audio,
  record to MP4, auto-reconnect on Wi-Fi.
- **Remote position:** Right, Left, Top or Bottom (Mirror page, or the bar's ⋯ More menu). If there's no room
  on that side it flips to the opposite side. Buttons that don't fit along the phone window move into **More**.
  The least-used ones go first (rotate, screen off, pin, volume, power), and Back, Home, Full screen and Stop always stay.
- **Keyboard** (⌨ on the bar): a small "Type on phone" box. Text is pasted through scrcpy, so it's instant and works
  in any language. *Send + Enter* (or the Enter key) also presses Enter on the phone, and there's a ⌫ button.
  In view-only mode it falls back to adb (English characters only).
- **Recording** (● on the bar, or the Recording card): start or stop at any time while mirroring. The button blinks red
  while recording and turns yellow while saving. Choose the quality (Low 720p / Medium 1280p / High 1920p / Original) and
  the format: **MP4** or **MKV** video, or **M4A / Opus / FLAC / WAV** audio only, with or without phone audio.
  It runs as a second hidden scrcpy session, so the mirror keeps running, and it's closed cleanly so files always play.
  AVI isn't offered: scrcpy can't write it. MKV is the most robust choice.
- **Remote bar** (while mirroring): a strip of icons docked beside the phone window that moves with it.
  It floats over the right edge in full screen, where it fades out after 3 s without mouse movement and
  comes back when the mouse moves. It hides when the window is minimised.
  Buttons: Back · Home · Recent apps | Volume up/down · Power | Rotate · Screen off/on · Screenshot |
  Keep on top · **Full screen on/off** | **Stop**. The buttons send scrcpy's Alt shortcuts, so they respond instantly.
  If those can't be delivered, the phone keys fall back to adb. Shortcuts are only sent when the mirror
  window is really in front, so they never type into another app.
- **Wireless:**
  - **Pair with QR code** (easiest, Android 11+): click *Show QR code*. On the phone open
    Developer options → Wireless debugging → *Pair device with QR code* and scan it. Pairing and
    connecting then happen automatically.
  - **Pair with code:** open *Pair device with pairing code* on the phone. The address fills in by itself,
    so you only type the 6-digit code.
  - **Connect** a phone that was paired before (nearby phones and recent ones are listed),
    **Disconnect**, and **USB → Wi-Fi** (one click while the cable is plugged in).
- **Scan network:** checks every address on your /24 network (about 7 s) and lists the devices.
  Each one is labelled *Android phone* (adb open), *Likely phone* (from its name),
  *Possible phone* (private random MAC), *Virtual machine*, *Router* and so on, with phones listed first.
  Double-click to connect. **Find ADB port** checks ports 5555 and 30000–49999 on the selected device
  to find a Wireless-debugging port you don't know. Only scan networks you own or manage.
- **Tools:** phone buttons, rotate, screenshot, type text on the phone, install APKs
  (or drop them onto the window).
- **Logcat:** a live log stream, coloured by level, with filters for **level** (Verbose…Fatal), **buffer**
  (main, system, crash, events, radio, all), **app** (by package name; it keeps following the app when it restarts
  and gets a new process ID), **tags** (comma-separated) and **regex** (run on the phone). **Find** narrows and
  highlights what's shown without restarting the stream. Pause, Clear view, Clear phone log, and Save… (a `.txt` of
  what's shown). The last 20,000 lines are kept.
- **Shell:** run `adb shell` commands with streaming output, history (Up/Down) and a list of common commands.
  Each command stops after 2 minutes or 2 MB of output; **Stop** ends it sooner. *Open adb shell in a terminal* opens
  a real console for interactive programs (adb on PATH, `ANDROID_SERIAL` set to the selected phone).
- **Apps:** the installed apps with their **icons and real names**, version codes (system apps optional) and search
  (by name or package). Icons are cached per app version in `%APPDATA%\Mirror\icons`. Launch (or double-click),
  Force stop, Logcat for app, App info on the phone, **Clear data…** and **Uninstall…** (both ask first). Selecting an
  app shows its version, target/min SDK, last update and whether it's running.
- **Device:**
  - **Details:** model, Android and SDK, security patch, CPU, screen size and density, Wi-Fi IP, storage, memory, battery.
  - **Developer toggles:** show taps, pointer location, layout bounds, animations off, dark mode, large text.
    Mirror reads each setting back after changing it, and reports when a phone refuses one.
  - **Open on the phone:** a web address or a deep link (`myapp://orders/42`).
  - **Port forwarding:** reverse (the phone's `localhost:port` reaches this PC: local backend, dev server) and
    forward (this PC's port reaches the phone), with a list of what's active.
  - **adb server:** Restart, **Stop / Start** (while stopped, Mirror stops polling so it doesn't start adb again;
    use this when another tool needs adb to itself), and Open terminal.
- **Settings:** skin, which adb to use, and the folder for screenshots and recordings.

## Skins
Pick one in **Settings → Skin**. Each tile is a live preview.

| Skin | Look |
|---|---|
| System / Light / Dark | Windows 11 (sv-ttk); System follows Windows |
| Developer | editor greys, blue accents and a blue status bar, Cascadia Mono |
| Hacker | terminal green on black, monospace everywhere, square corners, blinking `> mirror` cursor, green log levels |
| Gamer | deep purple with neon magenta and cyan, Bahnschrift, RGB-cycling nav bar and moving gradient glow |
| Aurora | midnight navy, violet-to-cyan gradient title and glow strip, large rounded cards |
| Paper | warm light paper, coral ink, serif title |
| Luna | retro XP-style: beige window, blue accents, Tahoma, glossy gradient buttons |
| Aero | retro 7-style: pale glass blue, glossy gradient buttons |

Everything except Light/Dark is drawn by `skins.py` on top of Tk's `clam` theme: rounded and glossy buttons, cards and
switches are rendered at runtime with anti-aliased edges, so there are no image files.

## Which adb is used
The app checks these in order and uses the first that works: the path set in Settings → the **Android SDK**
(`ANDROID_HOME`, `ANDROID_SDK_ROOT`, then Android Studio's `%LOCALAPPDATA%\Android\Sdk`) → `adb` on PATH →
the built-in adb. The SDK comes before PATH because Android Studio and Flutter use the SDK's adb: using the same
one keeps everything on the SDK's version, and adb copies with a different protocol version kill each other's
server ("adb server version doesn't match"). Copies with the same protocol (e.g. 1.0.41) share one server fine.
An adb on PATH is often a copy that came with another tool (for example Chocolatey's scrcpy package).
A server that is already running keeps running until adb restarts (Device page → Restart). The Activity log names the adb in
use and lists any others it found; the status bar shows its version and source.
scrcpy is given the same adb, so two adb versions never fight. When the app starts the adb server itself,
it turns on adb's mDNS (`ADB_MDNS_OPENSCREEN=1`). It also sends its own mDNS queries,
so finding phones works even when another tool started adb without mDNS.

## Troubleshooting
- **"Keep phone awake" blocked** (OnePlus, Oppo, Xiaomi): mirroring still works. To allow it, turn on
  Developer options → *Disable permission monitoring* (OnePlus/Oppo) or
  *USB debugging (Security settings)* (Xiaomi).
- **Wi-Fi won't connect or no phones found:** the phone and PC must be on the same network, and
  mDNS (multicast) must be allowed on it. Office Wi-Fi with client isolation blocks this.
  In that case use Scan network → Find ADB port, or USB → Wi-Fi.
- **USB → Wi-Fi** leaves the phone listening for adb on port 5555 until it reboots.

## Build
```bat
python -m pip install pyinstaller sv-ttk qrcode
build.bat
```
The scrcpy and adb binaries aren't stored in git. On the first build, `build.bat` runs `python get_scrcpy.py`, which
downloads the official [scrcpy 2.5 Windows release](https://github.com/Genymobile/scrcpy/releases/tag/v2.5) into `bin\`
(standard library only). The archive is checked against GitHub's SHA-256 digest for the asset or, for older releases,
the release's own `SHA256SUMS.txt`; with no published checksum it refuses. Options: `--version`, `--dest`.
To run from source without building: run `python get_scrcpy.py` once, then `pythonw mirror.pyw`.
Licenses are listed in `NOTICE.txt` (sv-ttk is MIT, qrcode is BSD).

**App icon helper.** `assets/mirror-helper.dex` (3.6 KB, built from `android-helper/src/com/mirror/IconDump.java`) runs
on the phone through `app_process`, like scrcpy's server. It reads each app's name and icon from the package service and
the app's own APK resources. It is read-only. Mirror copies it to `/data/local/tmp` when the Apps page first loads. The `.dex`
is committed, so building Mirror doesn't need Java. To rebuild it you need a JDK and the Android SDK: run
`android-helper\build-helper.bat`.

At runtime, settings are saved in `%APPDATA%\Mirror\config.json` (settings from the old *PhoneMirror* name are
moved over automatically). The exe runs scrcpy and adb from `%LOCALAPPDATA%\Mirror\runtime-<version>\`, which it
copies there on first start; older runtime folders are removed.
