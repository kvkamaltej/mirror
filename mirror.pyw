"""Mirror - a small Windows app to mirror and control an Android phone.

Wraps scrcpy + adb (bundled in ./bin, inside the exe when frozen). An adb that is
already installed on the PC is preferred over the bundled one so the two never
fight over the adb server. Wireless: QR pairing, code pairing (auto-detected),
connect by IP, USB->Wi-Fi, and a small LAN scanner that suggests phone IPs.
"""
import datetime
import json
import os
import queue
import random
import re
import shutil
import socket
import string
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox, ttk

try:
    import sv_ttk  # Windows 11 "Sun Valley" theme
except ImportError:
    sv_ttk = None
try:
    import qrcode
except ImportError:
    qrcode = None

from devtools import DevToolsMixin  # Logcat, Shell, Apps and Device pages
import skins                         # Light/Dark (sv-ttk) + drawn custom skins

APP = "Mirror"
OLD_APP = "PhoneMirror"  # previous name: settings are migrated from it
VERSION = "3.0.0"
IS_WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW: no console flashes


def _base_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _other_instances_running():
    """True if another Mirror / PhoneMirror exe (not this one or its launcher) is running."""
    if not IS_WIN:
        return False
    mine = {os.getpid(), os.getppid()}
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], stdin=subprocess.DEVNULL, capture_output=True,
                             creationflags=0x08000000, timeout=10).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return True  # unsure: keep the old folders
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) > 1 and cols[0].lower() in ("mirror.exe", "phonemirror.exe"):
            try:
                if int(cols[1]) not in mine:
                    return True
            except ValueError:
                pass
    return False


def _runtime_bin():
    """Where scrcpy/adb run from.

    In the one-file exe, the bundled tools are copied once to a fixed folder and run
    from there - never from the exe's temp folder - so a scrcpy/adb still running
    (or a recording still saving) when the app closes can't block that temp folder's
    cleanup ("Failed to remove temporary directory")."""
    src = os.path.join(_base_dir(), "bin")
    if not getattr(sys, "frozen", False):
        return src
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    dst = os.path.join(root, APP, "runtime-" + VERSION)
    try:
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            s, d = os.path.join(src, name), os.path.join(dst, name)
            if not os.path.isfile(d) or os.path.getsize(d) != os.path.getsize(s):
                shutil.copy2(s, d)
    except OSError:
        return src  # read-only profile etc.: fall back to the temp copy
    # tidy up runtime folders of older versions / the old app name - but never while
    # another copy of the app is running: it would lose its scrcpy/adb mid-session
    if _other_instances_running():
        return dst
    for base in (os.path.join(root, APP), os.path.join(root, OLD_APP)):
        try:
            for name in os.listdir(base):
                path = os.path.join(base, name)
                if name.startswith("runtime-") and os.path.normcase(path) != os.path.normcase(dst):
                    shutil.rmtree(path, ignore_errors=True)
            if base.endswith(OLD_APP) and not os.listdir(base):
                os.rmdir(base)
        except OSError:
            pass
    return dst


BIN = _runtime_bin()
BUNDLED_ADB = os.path.join(BIN, "adb.exe")
BUNDLED_SCRCPY = os.path.join(BIN, "scrcpy.exe")

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# name -> (max size px, bit rate, max fps); max size 0 = phone's native size
PRESETS = {
    "Low": ("1024", "4M", "30"),
    "Medium": ("1600", "8M", "60"),
    "High": ("0", "16M", "60"),
}
QUALITY_HELP = {
    "Auto": "High on USB, Low on Wi-Fi",
    "Low": "1024 px  ·  4 Mbps  ·  30 fps",
    "Medium": "1600 px  ·  8 Mbps  ·  60 fps",
    "High": "Full resolution  ·  16 Mbps  ·  60 fps",
}

DEFAULTS = {
    "quality": "Auto",
    "screen_off": True,
    "stay_awake": True,
    "on_top": False,
    "remote": True,
    "bar_pos": "Right",
    "rec_quality": "High",
    "rec_format": "MP4 video",
    "rec_audio": True,
    "view_only": False,
    "audio": True,
    "record": False,
    "auto_reconnect": True,
    "adb_path": "",
    "theme": "System",
    "out_dir": os.path.join(os.path.expanduser("~"), "Pictures", APP),
    "recent": [],  # [{"addr": "192.168.1.5:5555", "name": "LE2111"}]
}

KEYS = {
    "Home": "KEYCODE_HOME", "Back": "KEYCODE_BACK", "Recents": "KEYCODE_APP_SWITCH",
    "Power": "KEYCODE_POWER", "Volume up": "KEYCODE_VOLUME_UP",
    "Volume down": "KEYCODE_VOLUME_DOWN", "Enter": "KEYCODE_ENTER",
}

# Segoe Fluent Icons / MDL2 glyphs
ICON = {
    "logcat": "", "shell": "", "apps": "", "device": "",
    "setup": "", "mirror": "", "connect": "", "scan": "", "tools": "",
    "settings": "", "phone": "", "refresh": "",
}

PALETTE = {
    "dark": {"bg": "#1c1c1c", "side": "#202020", "hover": "#2a2a2a", "sel": "#2d2d2d",
             "accent": "#57c8ff", "fg": "#fafafa", "muted": "#9d9d9d", "field": "#262626",
             "ok": "#6ccb5f", "warn": "#fce100"},
    "light": {"bg": "#fafafa", "side": "#f0f0f0", "hover": "#e8e8e8", "sel": "#e3e3e3",
              "accent": "#005fb8", "fg": "#1c1c1c", "muted": "#5f5f5f", "field": "#ffffff",
              "ok": "#0f7b0f", "warn": "#9d5d00"},
}

QR_PX = 176
ADDR_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})\b")
PHONE_WORDS = ("android", "oneplus", "samsung", "galaxy", "redmi", "xiaomi", "poco", "oppo", "vivo",
               "realme", "pixel", "moto", "nokia", "iqoo", "nothing", "huawei", "honor", "phone", "tecno")


# =========================================================================== helpers
def load_config():
    cfg = dict(DEFAULTS)
    old = os.path.join(os.path.dirname(CONFIG_DIR), OLD_APP, "config.json")
    path = CONFIG_FILE if os.path.isfile(CONFIG_FILE) else old  # first run after the rename
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    if cfg.get("quality") not in PRESETS and cfg.get("quality") != "Auto":
        cfg["quality"] = "Auto"
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def adb_env():
    env = dict(os.environ)
    env["ADB_MDNS_OPENSCREEN"] = "1"  # adb's built-in mDNS (needed for wireless discovery)
    return env


def run(cmd, timeout=20, binary=False, env=None):
    """Run a command without a console window. Returns (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, creationflags=NO_WINDOW, env=env,
        )
        out = p.stdout if binary else p.stdout.decode("utf-8", "replace")
        return p.returncode, out, p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -1, b"" if binary else "", "timed out"
    except OSError as e:
        return -1, b"" if binary else "", str(e)


def _is_bundled(path):
    try:
        return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(BIN)))
    except (OSError, ValueError):
        return False


def adb_candidates(custom=""):
    """Every adb Mirror may use, in priority order: (source label, path).

    The Android SDK's adb comes before PATH on purpose: Android Studio and Flutter
    use the SDK's adb, and adb copies with different protocol versions kill each
    other's server ("adb server version doesn't match"). A PATH adb is often a
    copy that came with another tool (e.g. Chocolatey's scrcpy package)."""
    c = []
    if custom:
        c.append(("Settings", custom))
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(var)
        if root:
            c.append(("Android SDK (%s)" % var, os.path.join(root, "platform-tools", "adb.exe")))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        c.append(("Android SDK (Android Studio)", os.path.join(local, "Android", "Sdk", "platform-tools", "adb.exe")))
    which = shutil.which("adb")
    if which:
        c.append(("PATH", which))
    return c


def adb_info(path):
    """(version string, real path) from `adb version`; a PATH shim reports where the real adb is."""
    rc, out, err = run([path, "version"], timeout=10)
    if rc != 0 or "Android Debug Bridge" not in out:
        return None, (err or out).strip() or "rc=%s" % rc
    v = re.search(r"Version (\S+)", out)
    real = re.search(r"Installed as (.+)", out)
    return (v.group(1) if v else "?"), (real.group(1).strip() if real else path)


def find_adb(custom=""):
    """Pick the adb to use (see adb_candidates for the order); built-in is the fallback.

    Returns (source label, path, [notes]). Notes list the other adbs found, so a
    second version on the PC is visible."""
    notes, seen, chosen = [], set(), None
    for src, path in adb_candidates(custom):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen or not os.path.isfile(path) or _is_bundled(path):
            continue
        seen.add(key)
        ver, real = adb_info(path)
        if ver is None:
            notes.append("Skipped %s adb (%s): %s" % (src, path, real))
            continue
        where = path if os.path.normcase(real) == key else "%s → %s" % (path, real)
        if chosen is None:
            chosen = (src, path, ver)
        else:
            notes.append("Also found %s adb v%s (%s), not used" % (src, ver, where))
    if chosen:
        return chosen[0], chosen[1], notes
    return "built-in", BUNDLED_ADB, notes


def adb_version(path):
    rc, out, _ = run([path, "version"], timeout=10)
    m = re.search(r"Version (\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


def kill_tree(proc):
    """Stop scrcpy and the adb client it spawned (that child keeps our pipe open)."""
    if proc.poll() is not None:
        return
    if IS_WIN:
        run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], timeout=10)
    else:
        proc.terminate()


def parse_devices(out):
    devs = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        serial = parts[0]
        devs.append({
            "serial": serial,
            "state": parts[1] if len(parts) > 1 else "?",
            "model": info.get("model", "").replace("_", " "),
            "wifi": bool(ADDR_RE.search(serial)) or "_adb-tls-connect" in serial,
        })
    return devs


def shell_escape_text(text):
    """Escape text for `adb shell input text`."""
    special = set("()<>|;&*\\~\"'`$!?#[]{}")
    return "".join("%s" if c == " " else ("\\" + c if c in special else c) for c in text)


def local_ipv4s():
    """This PC's IPv4 addresses (excluding loopback/link-local)."""
    try:
        ips = {ai[4][0] for ai in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        return []
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def rand_str(n, chars=string.ascii_letters + string.digits):
    return "".join(random.SystemRandom().choice(chars) for _ in range(n))


# --------------------------------------------------------------------------- mDNS
def _read_name(data, off):
    labels, jumped, end = [], False, off
    for _ in range(64):
        ln = data[off]
        if ln == 0:
            off += 1
            break
        if ln & 0xC0 == 0xC0:
            ptr = ((ln & 0x3F) << 8) | data[off + 1]
            if not jumped:
                end = off + 2
            jumped, off = True, ptr
            continue
        labels.append(data[off + 1:off + 1 + ln].decode("utf-8", "replace"))
        off += 1 + ln
    return ".".join(labels), (end if jumped else off)


def _parse_mdns(data, src_ip):
    """Return (ptr: {svc_type: [instance]}, srv: {instance: (target, port)}, a: {host: ip})."""
    ptr, srv, arec = {}, {}, {}
    _, _, qd, an, ns, ar = struct.unpack("!6H", data[:12])
    off = 12
    for _ in range(qd):
        _, off = _read_name(data, off)
        off += 4
    for _ in range(an + ns + ar):
        name, off = _read_name(data, off)
        rtype, _, _, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        rdata_off = off
        if rtype == 12:  # PTR
            target, _ = _read_name(data, rdata_off)
            ptr.setdefault(name.lower(), []).append(target)
        elif rtype == 33:  # SRV
            port = struct.unpack("!H", data[rdata_off + 4:rdata_off + 6])[0]
            target, _ = _read_name(data, rdata_off + 6)
            srv[name] = (target, port)
        elif rtype == 1 and rdlen == 4:  # A
            arec[name.lower()] = socket.inet_ntoa(data[rdata_off:rdata_off + 4])
        off = rdata_off + rdlen
    return ptr, srv, arec


MDNS_TYPES = {"_adb-tls-pairing._tcp.local": "pair", "_adb-tls-connect._tcp.local": "connect",
              "_adb._tcp.local": "connect"}


def mdns_browse(timeout=1.5):
    """Ask the LAN (on every local interface) for adb wireless-debugging services.

    Uses legacy-unicast mDNS queries so replies come straight back to us; needs no
    adb server support. Returns [{"name", "kind": pair|connect, "ip", "port"}]."""
    q = struct.pack("!6H", 0, 0, len(MDNS_TYPES), 0, 0, 0)
    for t in MDNS_TYPES:
        q += b"".join(bytes([len(p)]) + p.encode() for p in t.split(".")) + b"\0" + struct.pack("!HH", 12, 1)
    socks = []
    for ip in local_ipv4s():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((ip, 0))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            s.setblocking(False)
            s.sendto(q, ("224.0.0.251", 5353))
            socks.append(s)
        except OSError:
            continue
    found, deadline = {}, time.time() + timeout
    import select
    while socks and time.time() < deadline:
        r, _, _ = select.select(socks, [], [], max(0.05, deadline - time.time()))
        for s in r:
            try:
                data, (src, _) = s.recvfrom(9000)
                ptr, srv, arec = _parse_mdns(data, src)
            except (OSError, struct.error, IndexError, ValueError):
                continue
            for stype, kind in MDNS_TYPES.items():
                for inst in ptr.get(stype, []):
                    target, port = srv.get(inst, (None, None))
                    if not port:
                        continue
                    ip = arec.get((target or "").lower(), src)
                    found[(inst, ip, port)] = {"name": inst.split(".")[0], "kind": kind, "ip": ip, "port": port}
    for s in socks:
        s.close()
    return list(found.values())


# --------------------------------------------------------------------------- LAN scan
def tcp_probe(ip, port, timeout):
    """'open', 'closed' (host answered with RST = alive) or None (no answer)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        rc = s.connect_ex((ip, port))
    except OSError:
        rc = -1
    finally:
        s.close()
    if rc == 0:
        return "open"
    if rc in (10061, 111):
        return "closed"
    return None


def read_arp():
    rc, out, _ = run(["arp", "-a"], timeout=10)
    table = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})\s+(\w+)", line, re.I)
        if m and m.group(2).lower() != "ff-ff-ff-ff-ff-ff" and not m.group(2).lower().startswith("01-00-5e"):
            table[m.group(1)] = m.group(2).lower()
    return table


VM_MAC_PREFIXES = ("52-54-00", "00-15-5d", "00-50-56", "00-0c-29", "00-05-69", "08-00-27",
                   "0a-00-27", "02-42", "00-16-3e", "bc-24-11", "00-1c-42")


def is_vm_mac(mac):
    return bool(mac) and mac.lower().startswith(VM_MAC_PREFIXES)


def is_random_mac(mac):
    """Phones use a random (locally administered) MAC per Wi-Fi network by default."""
    if is_vm_mac(mac):
        return False
    try:
        return bool(int(mac[:2], 16) & 0x02)
    except (ValueError, TypeError):
        return False


def resolve_names(ips, wait=2.5):
    names = {}

    def one(ip):
        try:
            names[ip] = socket.gethostbyaddr(ip)[0]
        except OSError:
            pass
    threads = [threading.Thread(target=one, args=(ip,), daemon=True) for ip in ips]
    for t in threads:
        t.start()
    deadline = time.time() + wait
    for t in threads:
        t.join(max(0, deadline - time.time()))
    return dict(names)


def find_open_ports(ip, ports, progress=None, cancel=None, timeout=0.35):
    found, done = [], [0]
    lock = threading.Lock()

    def one(p):
        if cancel and cancel.is_set():
            return
        if tcp_probe(ip, p, timeout) == "open":
            with lock:
                found.append(p)
        with lock:
            done[0] += 1
            if progress and done[0] % 250 == 0:
                progress(done[0], len(ports))
    with ThreadPoolExecutor(max_workers=256) as pool:
        list(pool.map(one, ports))
    return sorted(found)


# --------------------------------------------------------------------------- setup guide
# brand -> (turn on Developer options, turn on USB debugging, extra tip or "")
BRAND_STEPS = {
    "Samsung": (
        "Settings › About phone › Software information › tap Build number 7 times",
        "Settings › Developer options › turn on USB debugging", ""),
    "Xiaomi / Redmi / POCO": (
        "Settings › About phone › tap OS version (HyperOS / MIUI) 7 times",
        "Settings › Additional settings › Developer options › turn on USB debugging",
        "To control the phone, also turn on 'USB debugging (Security settings)' (needs a Mi account)."),
    "OnePlus / OPPO / Realme": (
        "Settings › About device › Version › tap Build number 7 times",
        "Settings › System settings › Developer options › turn on USB debugging",
        "If 'Keep phone awake' is blocked, also turn on 'Disable permission monitoring'."),
    "vivo / iQOO": (
        "Settings › About phone › Software version › tap Software version 7 times",
        "Settings › System management › Developer options › turn on USB debugging", ""),
    "Huawei / Honor": (
        "Settings › About phone › tap Build number 7 times",
        "Settings › System & updates › Developer options › turn on USB debugging", ""),
    "Google Pixel / Motorola / Nokia / Nothing / other": (
        "Settings › About phone › tap Build number 7 times",
        "Settings › System › Developer options › turn on USB debugging", ""),
}
OTHER_BRAND = "Google Pixel / Motorola / Nokia / Nothing / other"
VID_BRAND = {  # USB vendor id -> brand (18D1 = Google, also used by many other phones)
    "04E8": "Samsung", "2717": "Xiaomi / Redmi / POCO", "2A70": "OnePlus / OPPO / Realme",
    "22D9": "OnePlus / OPPO / Realme", "2D95": "vivo / iQOO", "12D1": "Huawei / Honor",
    "339B": "Huawei / Honor", "22B8": OTHER_BRAND, "2E04": OTHER_BRAND, "18D1": None,
    "0FCE": OTHER_BRAND, "1004": OTHER_BRAND, "0B05": OTHER_BRAND, "17EF": OTHER_BRAND,
    "0BB4": OTHER_BRAND, "19D2": OTHER_BRAND, "1BBB": OTHER_BRAND, "2A45": OTHER_BRAND,
}


def brand_from_text(text):
    t = (text or "").lower()
    for words, brand in ((("samsung", "galaxy", "sm-"), "Samsung"),
                         (("xiaomi", "redmi", "poco", "mi "), "Xiaomi / Redmi / POCO"),
                         (("oneplus", "oppo", "realme", "le2", "cph", "rmx"), "OnePlus / OPPO / Realme"),
                         (("vivo", "iqoo"), "vivo / iQOO"),
                         (("huawei", "honor"), "Huawei / Honor")):
        if any(w in t for w in words):
            return brand
    return None


APPLE_VID = "05AC"  # iPhones also show up as portable devices - never "Android"


def usb_phones():
    """Android phones plugged in by USB, as Windows sees them - works for any brand
    and even when USB debugging is off.

    A USB device counts as an Android phone when it exposes something every Android
    phone has: the adb interface (class FF/42/01, when debugging is on) or an MTP /
    PTP file-transfer interface. The vendor-id list only catches phones in
    'charging only' mode, which expose neither.
    Returns [{"serial", "vid", "brand", "name", "adb_iface", "mtp", "sure"}]."""
    if not IS_WIN:
        return []
    ps = ("Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -like 'USB\\VID_*' -or $_.PNPClass -eq 'WPD' }"
          " | ForEach-Object { $_.DeviceID + '|' + $_.Name + '|' + $_.PNPClass + '|' + ($_.CompatibleID -join ' ') }")
    rc, out, _ = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=20)
    devices = {}
    for line in out.splitlines():
        parts = line.strip().split("|")
        if len(parts) < 4:
            continue
        dev_id, name, cls, compat = parts[0], parts[1], parts[2], parts[3].upper()
        m = re.match(r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(&MI_\d+)?\\(.+)$", dev_id, re.I)
        if not m:
            continue
        vid, pid, iface, inst = m.group(1).upper(), m.group(2).upper(), m.group(3), m.group(4)
        if vid == APPLE_VID:
            continue
        d = devices.setdefault(vid + pid, {"serial": "", "vid": vid, "brand": VID_BRAND.get(vid), "name": "",
                                           "adb_iface": False, "mtp": False, "known_vid": vid in VID_BRAND})
        if not iface:
            d["serial"] = inst
        if "CLASS_FF&SUBCLASS_42&PROT_01" in compat or "adb" in name.lower():
            d["adb_iface"] = True
        if cls == "WPD" or "MS_COMP_MTP" in compat or "CLASS_06&SUBCLASS_01" in compat:
            d["mtp"] = True
            if cls == "WPD" and name:
                d["name"] = name
    phones = []
    for d in devices.values():
        if not (d["adb_iface"] or d["mtp"] or d["known_vid"]):
            continue  # a mouse, keyboard, hub, ... - not a phone
        d["sure"] = d["adb_iface"] or d["mtp"]
        d["brand"] = brand_from_text(d["name"]) or d["brand"]
        phones.append(d)
    return phones


def open_uri(uri):
    if IS_WIN:
        try:
            os.startfile(uri)
            return True
        except OSError:
            return False
    return False


def has_phone_link():
    rc, out, _ = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                      "(Get-AppxPackage -Name Microsoft.YourPhone).PackageFamilyName"], timeout=20)
    return out.strip() or None


# --------------------------------------------------------------------------- Win32 bits
def enable_file_drop(root, callback):
    """Accept files dropped from Explorer onto the window (Win32, no extra deps)."""
    if not IS_WIN:
        return False
    import ctypes
    from ctypes import wintypes

    user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcW.restype = LRESULT
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
    shell32.DragQueryFileW.restype = ctypes.c_uint
    shell32.DragFinish.argtypes = [ctypes.c_void_p]
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

    root.update_idletasks()
    hwnd = int(root.wm_frame(), 16)
    state = {}

    def proc(h, msg, wp, lp):
        if msg == 0x0233:  # WM_DROPFILES
            files = []
            for i in range(shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                n = shell32.DragQueryFileW(wp, i, None, 0)
                buf = ctypes.create_unicode_buffer(n + 1)
                shell32.DragQueryFileW(wp, i, buf, n + 1)
                files.append(buf.value)
            shell32.DragFinish(wp)
            root.after(0, callback, files)
            return 0
        return user32.CallWindowProcW(state["old"], h, msg, wp, lp)

    state["new"] = WNDPROC(proc)
    root._drop_state = state  # keep the callback alive
    state["old"] = user32.SetWindowLongPtrW(hwnd, -4, ctypes.cast(state["new"], ctypes.c_void_p))
    shell32.DragAcceptFiles(hwnd, True)
    return True


class Win:
    """Tiny Win32 layer: find/track the scrcpy window and send it scrcpy shortcuts."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        self.u = ctypes.windll.user32
        self.k = ctypes.windll.kernel32
        try:
            self.dwm = ctypes.windll.dwmapi
        except OSError:
            self.dwm = None

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]
        self.RECT, self.MONITORINFO = RECT, MONITORINFO
        self.u.MonitorFromWindow.restype = ctypes.c_void_p
        self.u.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        self.u.GetForegroundWindow.restype = wintypes.HWND
        self.u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_uint]

    def find_window(self, pid):
        """Visible top-level window owned by process `pid`."""
        ct, wt = self.ct, self.wt
        found = []
        CB = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def cb(hwnd, _):
            p = wt.DWORD()
            self.u.GetWindowThreadProcessId(hwnd, ct.byref(p))
            if p.value == pid and self.u.IsWindowVisible(hwnd) and self.u.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
                return False
            return True
        self.u.EnumWindows(CB(cb), 0)
        return found[0] if found else None

    def alive(self, hwnd):
        return bool(self.u.IsWindow(hwnd))

    def minimized(self, hwnd):
        return bool(self.u.IsIconic(hwnd))

    def rect(self, hwnd):
        """Visible window bounds (without the invisible resize border)."""
        r = self.RECT()
        if not (self.dwm and self.dwm.DwmGetWindowAttribute(hwnd, 9, self.ct.byref(r), self.ct.sizeof(r)) == 0):
            self.u.GetWindowRect(hwnd, self.ct.byref(r))
        return r.left, r.top, r.right, r.bottom

    def monitor(self, hwnd):
        mi = self.MONITORINFO()
        mi.cbSize = self.ct.sizeof(mi)
        self.u.GetMonitorInfoW(self.u.MonitorFromWindow(hwnd, 2), self.ct.byref(mi))
        m, w = mi.rcMonitor, mi.rcWork
        return (m.left, m.top, m.right, m.bottom), (w.left, w.top, w.right, w.bottom)

    def foreground(self):
        return self.u.GetForegroundWindow()

    def cursor(self):
        p = self.wt.POINT()
        self.u.GetCursorPos(self.ct.byref(p))
        return p.x, p.y

    def set_topmost(self, hwnd, on):
        # HWND_TOPMOST / HWND_NOTOPMOST, SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE
        self.u.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)

    def round_corners(self, hwnd):
        if self.dwm:
            v = self.ct.c_int(2)  # DWMWCP_ROUND
            self.dwm.DwmSetWindowAttribute(hwnd, 33, self.ct.byref(v), self.ct.sizeof(v))

    def activate(self, hwnd):
        """Bring `hwnd` to the front. Returns True only if it really is in front."""
        u, wt = self.u, self.wt
        if u.GetForegroundWindow() == hwnd:
            return True
        fg_thread = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None)
        me = self.k.GetCurrentThreadId()
        attached = fg_thread and fg_thread != me and u.AttachThreadInput(me, fg_thread, True)
        try:
            u.SetForegroundWindow(hwnd)
            u.BringWindowToTop(hwnd)
        finally:
            if attached:
                u.AttachThreadInput(me, fg_thread, False)
        for _ in range(10):
            if u.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.02)
        return False

    def send_keys(self, hwnd, vk, shift=False):
        """Press Left-Alt(+Shift)+vk in `hwnd` (scrcpy's shortcut modifier).

        Never types into another app: gives up unless `hwnd` is really in front."""
        if not self.activate(hwnd):
            return False
        u = self.u
        ext = 0x0001 if vk in (0x25, 0x26, 0x27, 0x28) else 0  # arrows are extended keys
        mods = [0xA4] + ([0xA0] if shift else [])               # VK_LMENU, VK_LSHIFT
        for m in mods:
            u.keybd_event(m, u.MapVirtualKeyW(m, 0), 0, 0)
        u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), ext, 0)
        u.keybd_event(vk, u.MapVirtualKeyW(vk, 0), ext | 0x0002, 0)
        for m in reversed(mods):
            u.keybd_event(m, u.MapVirtualKeyW(m, 0), 0x0002, 0)
        return True


WIN = None


def win():
    global WIN
    if WIN is None and IS_WIN:
        WIN = Win()
    return WIN


def system_is_dark():
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def set_titlebar_dark(root, dark):
    if not IS_WIN:
        return
    try:
        import ctypes
        hwnd = int(root.wm_frame(), 16)
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


# =========================================================================== UI widgets
class NavItem(tk.Frame):
    """Windows 11 style sidebar entry: accent bar + icon + label."""

    def __init__(self, master, app, key, icon, text):
        super().__init__(master, cursor="hand2")
        self.app, self.key = app, key
        self.bar = tk.Frame(self, width=3)
        self.bar.pack(side="left", fill="y", pady=8)
        self.icon = tk.Label(self, text=icon, font=(app.icon_font, 13), width=2)
        self.icon.pack(side="left", padx=(10, 6), pady=8)
        self.label = tk.Label(self, text=text, font=(app.font, 10), anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
        self.hover = False
        for w in (self, self.icon, self.label, self.bar):
            w.bind("<Button-1>", lambda e: app.show_page(key))
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        self.hover = on
        self.paint()

    def paint(self):
        pal = self.app.pal
        selected = self.app.page == self.key
        bg = pal["sel"] if selected else (pal["hover"] if self.hover else pal["side"])
        for w in (self, self.icon, self.label):
            w.configure(bg=bg)
        self.icon.configure(fg=pal["accent"] if selected else pal["fg"])
        self.label.configure(fg=pal["fg"])
        self.bar.configure(bg=pal["accent"] if selected else bg)


REC_QUALITY = {  # name -> (max size px, video bit rate)
    "Low": ("720", "2M"),
    "Medium": ("1280", "6M"),
    "High": ("1920", "12M"),
    "Original": ("0", "20M"),
}
REC_FORMATS = {  # label -> (extension, scrcpy --record-format, audio only, --audio-codec)
    "MP4 video": ("mp4", "mp4", False, None),
    "MKV video": ("mkv", "mkv", False, None),
    "M4A audio": ("m4a", "m4a", True, "aac"),
    "Opus audio": ("opus", "opus", True, "opus"),
    "FLAC audio": ("flac", "flac", True, "flac"),
    "WAV audio": ("wav", "wav", True, "raw"),
}
BAR_POSITIONS = ("Right", "Left", "Top", "Bottom")


class Recorder:
    """Records with a second, hidden scrcpy session, so recording can start and stop
    while mirroring. Stopped with WM_CLOSE so the file is finalised properly (a
    killed MP4 has no index and won't play)."""

    def __init__(self, app, serial):
        self.app, self.serial = app, serial
        cfg = app.cfg
        q = cfg.get("rec_quality", "High")
        fmt = cfg.get("rec_format", "MP4 video")
        size, rate = REC_QUALITY.get(q, REC_QUALITY["High"])
        ext, rformat, audio_only, acodec = REC_FORMATS.get(fmt, REC_FORMATS["MP4 video"])
        dev = app.devices.get(serial, {})
        name = re.sub(r"[^\w.-]+", "_", dev.get("model") or "phone")
        self.path = os.path.join(app.out_dir(), "%s_%s.%s" % (
            name, datetime.datetime.now().strftime("%Y%m%d_%H%M%S"), ext))
        args = [BUNDLED_SCRCPY, "--serial", serial, "--record=" + self.path, "--record-format=" + rformat,
                "--no-control", "--window-title=%s recorder" % APP, "--window-borderless",
                "--window-x=-4000", "--window-y=-4000", "--window-width=120", "--window-height=200"]
        self.error = None
        if audio_only:
            args += ["--no-video", "--audio-codec=" + acodec]
        else:
            args += ["--video-bit-rate", rate] + (["--max-size", size] if size != "0" else [])
            if not cfg.get("rec_audio", True):
                args.append("--no-audio")
        env = adb_env()
        env["ADB"] = app.adb
        self.started = time.time()
        self.hwnd = None
        self.stopping = False
        self.stopped_at = None
        self.label ="%s · %s" % (fmt, "audio only" if audio_only else q)
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, creationflags=NO_WINDOW, env=env, cwd=BIN)
        threading.Thread(target=self._hide_window, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()

    def _hide_window(self):
        w = win()
        for _ in range(300):  # its (off-screen) window appears ~1 s after start
            if self.proc.poll() is not None or not w:
                return
            self.hwnd = w.find_window(self.proc.pid)
            if self.hwnd:
                w.u.ShowWindow(self.hwnd, 0)  # SW_HIDE
                return
            time.sleep(0.03)

    def _watch(self):
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if "ERROR" in line:
                self.error = self.error or line.split("ERROR:", 1)[-1].strip()
                self.app.log("recorder: " + line)
        self.proc.wait()
        self.app.ui(self.app._recording_ended, self)

    def elapsed(self):
        s = int((self.stopped_at or time.time()) - self.started)
        return "%d:%02d" % (s // 60, s % 60)

    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        self.stopped_at = time.time()

        if self.hwnd and win():
            win().u.PostMessageW(self.hwnd, 0x0010, 0, 0)  # WM_CLOSE -> scrcpy finalises the file

        def work():
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                kill_tree(self.proc)
        threading.Thread(target=work, daemon=True).start()


class KeyboardPopup:
    """Small 'type on phone' box that opens next to the remote bar."""

    def __init__(self, bar):
        self.bar, app = bar, bar.app
        t = self.top = tk.Toplevel(app.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(bg=bar.BG)
        box = tk.Frame(t, bg=bar.BG, padx=10, pady=8)
        box.pack()
        head = tk.Frame(box, bg=bar.BG)
        head.pack(fill="x")
        tk.Label(head, text="Type on phone", bg=bar.BG, fg=bar.FG, font=(app.font, 10, "bold")).pack(side="left")
        x = tk.Label(head, text="", font=(app.icon_font, 9), bg=bar.BG, fg=bar.FG, cursor="hand2")
        x.pack(side="right")
        x.bind("<Button-1>", lambda e: self.close())
        self.var = tk.StringVar()
        self.entry = tk.Entry(box, textvariable=self.var, width=34, font=(app.font, 11), relief="flat",
                              bg="#2d2d2d", fg="#ffffff", insertbackground="#ffffff")
        self.entry.pack(fill="x", pady=(8, 8), ipady=5)
        self.entry.bind("<Return>", lambda e: self.send(enter=True))
        self.entry.bind("<Escape>", lambda e: self.close())
        row = tk.Frame(box, bg=bar.BG)
        row.pack(fill="x")
        for text, cmd in (("Send", lambda: self.send()), ("Send + Enter", lambda: self.send(enter=True)),
                          ("⌫", lambda: bar.app_key("KEYCODE_DEL")), ("Enter", lambda: bar.app_key("KEYCODE_ENTER"))):
            b = tk.Label(row, text=text, bg="#2d2d2d", fg=bar.FG, font=(app.font, 9), padx=10, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=bar.HOVER))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg="#2d2d2d"))
        tk.Label(box, text="Enter = send + Enter · Esc = close · any language", bg=bar.BG, fg="#9d9d9d",
                 font=(app.font, 8)).pack(anchor="w", pady=(6, 0))
        self.place()
        t.after(50, lambda: (t.focus_force(), self.entry.focus_set()))

    def place(self):
        bar = self.bar
        t = self.top
        t.update_idletasks()
        bx, by = bar.top.winfo_rootx(), bar.top.winfo_rooty()
        bw, bh = bar.top.winfo_width(), bar.top.winfo_height()
        w, h = t.winfo_reqwidth(), t.winfo_reqheight()
        if bar.side in ("Right", "Left"):
            x = bx + bw + 8 if bar.side == "Right" else bx - w - 8
            y = by
        else:
            x = bx
            y = by + bh + 8 if bar.side == "Bottom" else by - h - 8
        if bar.full:  # overlays sit inside the screen
            x = bx - w - 8 if bar.side == "Right" else x
        t.geometry("+%d+%d" % (x, y))

    def send(self, enter=False):
        text = self.var.get()
        if text:
            self.bar.type_text(text)
            self.var.set("")
        if enter:
            self.bar.app.root.after(250 if text else 0, lambda: self.bar.app_key("KEYCODE_ENTER"))
        self.bar.app.root.after(400, self.refocus)

    def refocus(self):
        try:
            self.top.focus_force()
            self.entry.focus_set()
        except tk.TclError:
            pass

    def close(self):
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        self.bar.keyboard = None


class RemoteBar:
    """A remote-control strip docked to the scrcpy window (right / left / top / bottom).

    Buttons that don't fit along the phone window go into the More (⋯) menu. Buttons
    send scrcpy's Alt+key shortcuts (instant) and fall back to adb when they can't."""

    BG, FG, HOVER, ON, RED, LINE = "#202020", "#ececec", "#363636", "#57c8ff", "#ff6b6b", "#3a3a3a"
    VK = {"b": 0x42, "h": 0x48, "s": 0x53, "p": 0x50, "o": 0x4F, "r": 0x52, "f": 0x46, "v": 0x56,
          "up": 0x26, "down": 0x28}
    # key, glyph, tooltip, group, keep-priority (lower stays on the bar longer)
    BUTTONS = [
        ("hide", "", "Minimize controls", -1, 0),
        ("back", "", "Back", 0, 1),
        ("home", "", "Home", 0, 2),
        ("recents", "", "Recent apps", 0, 6),
        ("volup", "", "Volume up", 1, 8),
        ("voldown", "", "Volume down", 1, 9),
        ("power", "", "Power", 1, 7),
        ("keyboard", "", "Type text", 2, 4),
        ("record", "", "Start recording", 2, 3),
        ("shot", "", "Screenshot", 2, 5),
        ("rotate", "", "Rotate phone", 3, 12),
        ("screen", "", "Phone screen off / on", 3, 11),
        ("pin", "", "Keep on top", 3, 10),
        ("full", "", "Full screen", 4, 0),
        ("more", "", "More", 4, 0),
        ("stop", "", "Stop mirroring", 4, 0),
    ]
    HIDE_AFTER = 3.0  # seconds without mouse movement in full screen

    def __init__(self, app, serial, proc, view_only, screen_off):
        self.app, self.serial, self.proc, self.view_only = app, serial, proc, view_only
        self.w = win()
        self.hwnd = None
        self.closed = False
        self.pinned = False
        self.full = False
        self.screen_off = screen_off
        self.started = time.time()
        self.last_geo = None
        self.topmost = None
        self.tip = None
        self.keyboard = None
        self.last_cursor = None
        self.last_move = time.time()
        self.hidden = False
        self.side = None          # where it is actually docked (may flip if no room)
        self.layout_key = None
        self.btn = {}
        self.cell = None
        self.collapsed = bool(app.cfg.get("bar_collapsed"))  # minimized to a small handle

        self.top = tk.Toplevel(app.root)
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.top.configure(bg=self.BG)
        self.box = tk.Frame(self.top, bg=self.BG)
        self.box.pack()
        app.root.after(300, self._find)

    @property
    def pos(self):
        p = self.app.cfg.get("bar_pos", "Right")
        return p if p in BAR_POSITIONS else "Right"

    # ---------------------------------------------------------------- layout
    def _measure(self):
        """Size of one icon button (px) - measured once from a probe label."""
        if not self.cell:
            probe = tk.Label(self.top, text="", font=(self.app.icon_font, 15), width=2, pady=7, padx=2)
            probe.update_idletasks()
            self.cell = (probe.winfo_reqwidth(), probe.winfo_reqheight())
            probe.destroy()
        return self.cell

    def _visible_keys(self, length, horizontal):
        """Which buttons fit along `length` px; the rest go into More."""
        if self.collapsed:
            return ["show"]
        cw, ch = self._measure()
        step = cw if horizontal else ch
        room = max(4, int((length - 24) // step))
        keys = [b[0] for b in self.BUTTONS]
        if len(keys) <= room:
            return keys
        by_priority = sorted(self.BUTTONS, key=lambda b: b[4])
        keep = {b[0] for b in by_priority[:room]} | {"hide", "more", "stop", "full"}
        return [k for k in keys if k in keep]

    def _layout(self, keys, horizontal):
        for child in self.box.winfo_children():
            child.destroy()
        self.btn = {}
        self.box.configure(padx=6 if horizontal else 4, pady=4 if horizontal else 6)
        side = "left" if horizontal else "top"
        prev_group = None
        f = self.app.icon_font
        if keys == ["show"]:  # minimized: one handle that brings the controls back
            self.box.configure(padx=3, pady=3)
            b = tk.Label(self.box, text="", font=(f, 13), width=2, pady=5, padx=1, bg=self.BG,
                         fg=self.ON, cursor="hand2")
            b.pack()
            b.bind("<Button-1>", lambda e: self.action("show"))
            b.bind("<Enter>", lambda e, w=b: (w.configure(bg=self.HOVER), self._tip(w, "Show controls")))
            b.bind("<Leave>", lambda e, w=b: (w.configure(bg=self.BG), self._tip(None, None)))
            self.btn = {"show": b}
            self.hidden_keys = []
            self.top.update_idletasks()
            return
        for key, glyph, tip, group, _ in self.BUTTONS:
            if key not in keys:
                continue
            if prev_group is not None and group != prev_group:
                if horizontal:
                    tk.Frame(self.box, bg=self.LINE, width=1, height=26).pack(side=side, padx=5)
                else:
                    tk.Frame(self.box, bg=self.LINE, height=1, width=28).pack(side=side, pady=5)
            prev_group = group
            b = tk.Label(self.box, text=glyph, font=(f, 15), width=2, pady=7, padx=2, bg=self.BG,
                         fg=self.RED if key == "stop" else self.FG, cursor="hand2")
            b.pack(side=side)
            b.bind("<Button-1>", lambda e, k=key: self.action(k))
            b.bind("<Enter>", lambda e, w=b, k=key: (w.configure(bg=self.HOVER), self._tip(w, self._tip_text(k))))
            b.bind("<Leave>", lambda e, w=b: (w.configure(bg=self.BG), self._tip(None, None)))
            self.btn[key] = b
        self.hidden_keys = [b[0] for b in self.BUTTONS if b[0] not in keys]
        self._paint_states()
        self.top.update_idletasks()

    # ---------------------------------------------------------------- tracking
    def _find(self):
        if self.closed:
            return
        self.hwnd = self.w.find_window(self.proc.pid) if self.w else None
        if self.hwnd:
            self.top.update_idletasks()
            self.w.round_corners(int(self.top.wm_frame(), 16))
            self._dock()
        elif time.time() - self.started < 25 and self.proc.poll() is None:
            self.app.root.after(250, self._find)

    def _dock(self):
        if self.closed:
            return
        w = self.w
        if not w.alive(self.hwnd):
            self.close()
            return
        if w.minimized(self.hwnd):
            if self.top.state() != "withdrawn":
                self.top.withdraw()
                self._tip(None, None)
        else:
            left, top, right, bottom = w.rect(self.hwnd)
            (ml, mt, mr, mb), work = w.monitor(self.hwnd)
            full = left <= ml and top <= mt and right >= mr and bottom >= mb
            if full != self.full:
                self.full = full
                self.last_move = time.time()
            if not full:  # docked: stay inside the work area (never over the taskbar)
                ml, mt, mr, mb = work
            pos = self.pos
            horizontal = pos in ("Top", "Bottom")
            if full:
                length = (mr - ml) if horizontal else (mb - mt)
            else:
                length = (right - left) if horizontal else (bottom - top)
            keys = self._visible_keys(length, horizontal)
            lk = (pos, tuple(keys))
            if lk != self.layout_key:
                self.layout_key = lk
                self._layout(keys, horizontal)
            bw, bh = self.top.winfo_reqwidth(), self.top.winfo_reqheight()
            side = pos
            if full:  # float inside the screen edge
                x = {"Right": mr - bw - 16, "Left": ml + 16}.get(pos, ml + (mr - ml - bw) // 2)
                y = {"Top": mt + 16, "Bottom": mb - bh - 16}.get(pos, mt + (mb - mt - bh) // 2)
            else:
                if pos == "Right" and right + 8 + bw > mr:
                    side = "Left"
                elif pos == "Left" and left - 8 - bw < ml:
                    side = "Right"
                elif pos == "Top" and top - 8 - bh < mt:
                    side = "Bottom"
                elif pos == "Bottom" and bottom + 8 + bh > mb:
                    side = "Top"
                if side in ("Right", "Left"):
                    x = right + 8 if side == "Right" else left - bw - 8
                    y = max(mt, min(top + (bottom - top - bh) // 2, mb - bh))
                else:
                    y = top - bh - 8 if side == "Top" else bottom + 8
                    x = max(ml, min(left + (right - left - bw) // 2, mr - bw))
                # no room on either side (e.g. a wide landscape window): float just inside
                # the chosen edge instead of going off-screen
                if x < ml or x + bw > mr or y < mt or y + bh > mb:
                    side = pos
                    if pos in ("Right", "Left"):
                        x = min(right, mr) - bw - 12 if pos == "Right" else max(left, ml) + 12
                    else:
                        y = max(top, mt) + 40 if pos == "Top" else min(bottom, mb) - bh - 12
                    x = max(ml, min(x, mr - bw))
                    y = max(mt, min(y, mb - bh))
            self.side = side
            geo = "+%d+%d" % (x, y)
            if geo != self.last_geo:
                self.top.geometry(geo)
                self.last_geo = geo
                if self.keyboard:
                    self.keyboard.place()
            if self.top.state() == "withdrawn":
                self.top.deiconify()
            self._autohide(full, x, y, bw, bh)
            fg = w.foreground()
            want = self.pinned or full or fg in (self.hwnd, int(self.top.wm_frame(), 16))
            if want != self.topmost:
                self.top.attributes("-topmost", want)
                self.topmost = want
        self._paint_record()
        self.app.root.after(80, self._dock)

    def _autohide(self, full, x, y, bw, bh):
        """Full screen: fade out when the mouse is idle, back on any movement/hover."""
        cur = self.w.cursor()
        over = x <= cur[0] <= x + bw and y <= cur[1] <= y + bh
        if cur != self.last_cursor or over or self.keyboard:
            self.last_move = time.time()
        self.last_cursor = cur
        hide = full and time.time() - self.last_move > self.HIDE_AFTER
        if hide != self.hidden:
            self.hidden = hide
            self.top.attributes("-alpha", 0.0 if hide else 1.0)
            if hide:
                self._tip(None, None)

    # ---------------------------------------------------------------- actions
    def action(self, key):
        app = self.app
        acts = {
            "back": lambda: self.press("b", "KEYCODE_BACK"),
            "home": lambda: self.press("h", "KEYCODE_HOME"),
            "recents": lambda: self.press("s", "KEYCODE_APP_SWITCH"),
            "volup": lambda: self.press("up", "KEYCODE_VOLUME_UP"),
            "voldown": lambda: self.press("down", "KEYCODE_VOLUME_DOWN"),
            "power": lambda: self.press("p", "KEYCODE_POWER"),
            "keyboard": self.toggle_keyboard,
            "record": lambda: app.toggle_recording(self.serial),
            "shot": app.screenshot,
            "rotate": lambda: self.press("r", None, app.rotate),
            "screen": self.toggle_screen,
            "pin": self.toggle_pin,
            "full": self.toggle_full,
            "more": self.show_more,
            "stop": lambda: app.stop_mirror(self.serial),
            "hide": lambda: self.set_collapsed(True),
            "show": lambda: self.set_collapsed(False),
        }
        self._tip(None, None)
        acts[key]()

    def set_collapsed(self, on):
        """Minimize the controls to a small handle (or bring them back); remembered."""
        self.collapsed = on
        self.app._set_cfg("bar_collapsed", on)
        if on and self.keyboard:
            self.keyboard.close()
        self.layout_key = None  # re-layout on the next dock tick
        self.last_geo = None

    def press(self, key, keycode, fallback=None):
        """scrcpy shortcut (fast); adb keyevent if the shortcut can't be delivered."""
        if not self.view_only and self.hwnd and self.w.send_keys(self.hwnd, self.VK[key]):
            return
        if fallback:
            fallback()
        elif keycode:
            self.app_key(keycode)

    def app_key(self, keycode):
        self.app.bg(lambda: self.app.adb_run("shell", "input", "keyevent", keycode, serial=self.serial, timeout=10))

    def type_text(self, text):
        """Paste through scrcpy (any language, instant); adb 'input text' as fallback."""
        root = self.app.root
        if not self.view_only and self.hwnd:
            try:
                saved = root.clipboard_get()
            except tk.TclError:
                saved = None
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            if self.w.send_keys(self.hwnd, self.VK["v"]):  # Alt+V: copy to phone + paste
                if saved is not None:
                    root.after(1500, lambda: (root.clipboard_clear(), root.clipboard_append(saved)))
                return
        if any(ord(c) > 127 for c in text):
            self.app.log("Typing non-English text needs control (turn off View only).")
            return
        self.app.bg(lambda: self.app.adb_run("shell", "input", "text", shell_escape_text(text), serial=self.serial))

    def toggle_keyboard(self):
        if self.keyboard:
            self.keyboard.close()
        else:
            self.keyboard = KeyboardPopup(self)

    def toggle_full(self):
        if self.hwnd and self.w.send_keys(self.hwnd, self.VK["f"]):
            return
        self.app.log("Couldn't switch full screen - click the phone window and press Alt+F.")

    def toggle_screen(self):
        if self.view_only:
            self.app.log("Screen on/off needs control (turn off View only).")
            return
        if self.hwnd and self.w.send_keys(self.hwnd, self.VK["o"], shift=self.screen_off):
            self.screen_off = not self.screen_off
            self._paint_states()

    def toggle_pin(self):
        if not self.hwnd:
            return
        self.pinned = not self.pinned
        self.w.set_topmost(self.hwnd, self.pinned)
        self.topmost = None
        self._paint_states()

    def set_pos(self, pos):
        self.app._set_cfg("bar_pos", pos)
        self.app.ui(self.app._sync_bar_pos)

    def set_cfg(self, key, value):
        self.app._set_cfg(key, value)
        self.app.ui(self.app._sync_rec_controls)

    def show_more(self):
        app = self.app
        m = tk.Menu(self.top, tearoff=0, bg="#2b2b2b", fg=self.FG, activebackground="#3d3d3d",
                    activeforeground="#ffffff", font=(app.font, 10), bd=0)
        names = {b[0]: b[2] for b in self.BUTTONS}
        for key in self.hidden_keys:
            label = self._tip_text(key)
            if key == "pin" and self.pinned or key == "screen" and self.screen_off:
                label += "  ✓"
            m.add_command(label=label, command=lambda k=key: self.action(k))
        if self.hidden_keys:
            m.add_separator()

        def radio_menu(title, options, current, setter):
            sub = tk.Menu(m, tearoff=0, bg="#2b2b2b", fg=self.FG, activebackground="#3d3d3d",
                          activeforeground="#ffffff", font=(app.font, 10), bd=0)
            for opt in options:
                sub.add_command(label=("●  " if opt == current else "     ") + opt,
                                command=lambda o=opt: setter(o))
            m.add_cascade(label=title, menu=sub)

        radio_menu("Bar position", BAR_POSITIONS, self.pos, self.set_pos)
        radio_menu("Recording quality", list(REC_QUALITY), app.cfg.get("rec_quality", "High"),
                   lambda v: self.set_cfg("rec_quality", v))
        radio_menu("Recording format", list(REC_FORMATS), app.cfg.get("rec_format", "MP4 video"),
                   lambda v: self.set_cfg("rec_format", v))
        audio = app.cfg.get("rec_audio", True)
        m.add_command(label=("✓  " if audio else "     ") + "Record phone audio",
                      command=lambda: self.set_cfg("rec_audio", not audio))
        m.add_separator()
        m.add_command(label="Open recordings folder", command=lambda: app.open_path(app.out_dir()))
        b = self.btn.get("more")
        x, y = (b.winfo_rootx(), b.winfo_rooty() + b.winfo_height()) if b else self.w.cursor()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()
        self.last_move = time.time()

    # ---------------------------------------------------------------- look
    def _tip_text(self, key):
        names = {b[0]: b[2] for b in self.BUTTONS}
        if key == "record":
            rec = self.app.recorders.get(self.serial)
            if rec and rec.stopping:
                return "Saving recording..."
            return "Stop recording (%s)" % rec.elapsed() if rec else \
                "Start recording · %s · %s" % (self.app.cfg.get("rec_format", "MP4 video"),
                                                self.app.cfg.get("rec_quality", "High"))
        if key == "full":
            return "Exit full screen" if self.full else "Full screen"
        return names.get(key, key)

    def _paint_states(self):
        b = self.btn
        if "pin" in b:
            b["pin"].configure(fg=self.ON if self.pinned else self.FG, text="" if self.pinned else "")
        if "full" in b:
            b["full"].configure(text="" if self.full else "", fg=self.ON if self.full else self.FG)
        if "screen" in b:
            b["screen"].configure(fg=self.ON if self.screen_off else self.FG)
        self._paint_record(force=True)

    def _paint_record(self, force=False):
        b = self.btn.get("record")
        if not b:
            return
        rec = self.app.recorders.get(self.serial)
        if rec and rec.stopping:  # saving the file
            want = ("", "#fce100")
        elif rec:  # blink while recording
            on = int(time.time() * 2) % 2 == 0
            want = ("", self.RED if on else "#7a2a2a")
        else:
            want = ("", self.FG)
        if force or (b.cget("text"), b.cget("fg")) != want:
            b.configure(text=want[0], fg=want[1])

    def _tip(self, widget, text):
        if self.tip:
            self.tip.destroy()
            self.tip = None
        if not widget or self.hidden:
            return
        t = tk.Toplevel(self.top)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        tk.Label(t, text=text, bg="#2b2b2b", fg="#f0f0f0", font=(self.app.font, 9), padx=8, pady=3).pack()
        t.update_idletasks()
        tw, th = t.winfo_reqwidth(), t.winfo_reqheight()
        wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
        ww, wh = widget.winfo_width(), widget.winfo_height()
        side = self.side or "Right"
        if self.full:  # inward, over the picture
            side = {"Right": "Left", "Left": "Right", "Top": "Bottom", "Bottom": "Top"}[self.pos]
        if side == "Right":
            x, y = wx + ww + 10, wy + (wh - th) // 2
        elif side == "Left":
            x, y = wx - tw - 10, wy + (wh - th) // 2
        elif side == "Bottom":
            x, y = wx + (ww - tw) // 2, wy + wh + 8
        else:
            x, y = wx + (ww - tw) // 2, wy - th - 8
        t.geometry("+%d+%d" % (x, y))
        self.tip = t

    def relayout(self):
        self.layout_key = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._tip(None, None)
        if self.keyboard:
            self.keyboard.close()
        try:
            self.top.destroy()
        except tk.TclError:
            pass


# =========================================================================== app
class App(DevToolsMixin):
    PAGES = [("setup", "Get started"), ("mirror", "Mirror"), ("connect", "Wireless"),
             ("scan", "Scan network"), ("tools", "Tools"), ("logcat", "Logcat"), ("shell", "Shell"),
             ("apps", "Apps"), ("device", "Device"), ("settings", "Settings")]
    APP_NAME = APP

    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.q = queue.Queue()
        self.adb = None
        self.adb_src = "detecting..."
        self.devices = {}
        self.label_to_serial = {}
        self.procs = {}
        self.remotes = {}       # serial -> RemoteBar
        self.recorders = {}     # serial -> Recorder
        self.battery_text = ""
        self.closing = False
        self.page = None
        self.refresh_lock = threading.Lock()
        self.qr_token = 0
        self.nearby = []
        self.scan_cancel = threading.Event()
        self.pal = dict(skins.SV_PALETTE["dark"])
        self.usb = []              # phones Windows sees on USB (even with debugging off)
        self.usb_checked = False
        self.brand_auto = True     # until the user picks a brand on Get started
        self.phone_link = None
        self.dev_texts = []        # text panes styled by dev_theme()
        self.dev_lists = []        # list boxes styled by dev_theme()
        self._dev_init()

        fams = set(tkfont.families(root))
        self.font = "Segoe UI Variable Text" if "Segoe UI Variable Text" in fams else "Segoe UI"
        self.font_display = "Segoe UI Variable Display" if "Segoe UI Variable Display" in fams else "Segoe UI"
        self.icon_font = "Segoe Fluent Icons" if "Segoe Fluent Icons" in fams else "Segoe MDL2 Assets"
        self.mono = "Cascadia Mono" if "Cascadia Mono" in fams else "Consolas"
        self.base_fonts = (self.font, self.font_display, self.mono)  # Light / Dark skins
        self.skin = skins.resolve("System", False)

        root.title(APP)
        root.geometry("900x700")
        root.minsize(820, 660)
        try:  # .ico for the title bar / taskbar, plus a 256 px PNG so large icons stay sharp
            root.iconbitmap(default=self.asset_path("icon.ico"))
            self._icon_png = tk.PhotoImage(file=self.asset_path("icon.png"))
            root.iconphoto(True, self._icon_png)
        except tk.TclError:
            pass

        self._build_ui()
        self.apply_theme(self.cfg.get("theme", "System"))
        self.show_page("mirror")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            enable_file_drop(root, self.on_drop)
        except Exception as e:
            self.log("Drag & drop unavailable: %s" % e)
        self.root.after(100, self._pump)
        self.bg(self._startup)

    # ---------------------------------------------------------------- threading
    def ui(self, fn, *args):
        self.q.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        if not self.closing:
            self.root.after(100, self._pump)

    def bg(self, fn, *args):
        def wrapper():
            try:
                fn(*args)
            except Exception as e:
                self.log("Error: %s" % e)
        threading.Thread(target=wrapper, daemon=True).start()

    def log(self, msg):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.ui(self._append_log, "%s  %s\n" % (stamp, msg))

    def _append_log(self, line):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        if int(self.log_box.index("end-1c").split(".")[0]) > 500:
            self.log_box.delete("1.0", "100.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------------------------------------------------------------- adb
    def adb_run(self, *args, serial=None, timeout=20, binary=False):
        cmd = [self.adb] + (["-s", serial] if serial else []) + list(args)
        return run(cmd, timeout=timeout, binary=binary, env=adb_env())

    def popen_adb(self, *args, serial=None):
        """A streaming adb process (stdout + stderr in one pipe), no console window."""
        cmd = [self.adb] + (["-s", serial] if serial else []) + list(args)
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=NO_WINDOW, env=adb_env())

    def kill_proc(self, proc):
        kill_tree(proc)

    @staticmethod
    def asset_path(name):
        return os.path.join(_base_dir(), "assets", name)

    def _startup(self):
        self._detect_adb()
        self.adb_run("start-server", timeout=30)
        rc, out, _ = self.adb_run("mdns", "check", timeout=10)
        self.adb_mdns = "unavailable" not in out and rc == 0
        self.phone_link = has_phone_link()
        self.ui(self._update_setup)
        first = True
        while not self.closing:
            if self.adb_stopped:  # stopped on the Device page: don't start it again by polling
                time.sleep(1)
                continue
            self.refresh_devices()
            # no usable phone over adb? look at USB the Windows way (works with debugging off)
            if not any(d["state"] == "device" for d in self.devices.values()):
                self.usb = usb_phones()
            else:
                self.usb = []
            self.usb_checked = True
            self.ui(self._update_setup)
            if first:
                first = False
                self.ui(self._first_run_page)
            time.sleep(3)

    def _first_run_page(self):
        """First launch, or no phone ready: open Get started instead of an empty Mirror page."""
        ready = any(d["state"] == "device" for d in self.devices.values())
        if not ready and (not self.cfg.get("setup_seen") or self.usb):
            self.show_page("setup")
        self._set_cfg("setup_seen", True)

    def _detect_adb(self):
        src, path, notes = find_adb(self.cfg.get("adb_path", ""))
        self.adb, self.adb_src = path, src
        ver = adb_version(path)
        self.adb_ver = (adb_info(path)[0] or "") if path else ""
        self.log("Using %s adb v%s: %s" % (src, self.adb_ver, path))
        for n in notes:
            self.log(n)
        if ver and ver < (30, 0):
            self.log("This adb is older than 30.0 - wireless pairing needs 30.0+. "
                     "Set a newer adb in Settings.")
        self.ui(self._update_status_bar)

    def refresh_devices(self):
        if not self.adb or self.adb_stopped or not self.refresh_lock.acquire(blocking=False):
            return
        try:
            rc, out, err = self.adb_run("devices", "-l", timeout=15)
            devs = parse_devices(out) if rc == 0 else []
            self.ui(self._apply_devices, devs)
            serial = self.selected()
            dev = self.devices.get(serial)
            if dev and dev["state"] == "device":
                self.battery_text = self._battery(serial)
                self.ui(self._update_device_info)
        finally:
            self.refresh_lock.release()

    def _battery(self, serial):
        rc, out, _ = self.adb_run("shell", "dumpsys", "battery", serial=serial, timeout=10)
        m = re.search(r"level:\s*(\d+)", out)
        if not m:
            return ""
        charging = re.search(r"status:\s*2\b", out) is not None
        return "Battery %s%%%s" % (m.group(1), " · charging" if charging else "")

    # ================================================================ UI build
    def _build_ui(self):
        root = self.root
        self.side = tk.Frame(root, width=200)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        self.brand = tk.Canvas(self.side, height=56, highlightthickness=0, bd=0)  # drawn per skin
        self.brand.pack(fill="x", pady=(6, 6))
        self.nav = {}
        for key, text in self.PAGES:
            item = NavItem(self.side, self, key, ICON[key], text)
            item.pack(fill="x", padx=6, pady=1)
            self.nav[key] = item
        self.side_foot = tk.Label(self.side, text="v" + VERSION, font=(self.font, 8), anchor="w")
        self.side_foot.pack(side="bottom", fill="x", padx=18, pady=10)

        main = ttk.Frame(root)
        main.pack(side="left", fill="both", expand=True)

        # phone header
        head = ttk.Frame(main, padding=(20, 16, 20, 8))
        head.pack(fill="x")
        self.phone_icon = ttk.Label(head, text=ICON["phone"], font=(self.icon_font, 26))
        self.phone_icon.pack(side="left", padx=(0, 12))
        txt = ttk.Frame(head)
        txt.pack(side="left", fill="x", expand=True)
        self.title_var = tk.StringVar(value="Looking for phones...")
        ttk.Label(txt, textvariable=self.title_var, style="Title.TLabel").pack(anchor="w")
        self.info_var = tk.StringVar(value="")
        ttk.Label(txt, textvariable=self.info_var, style="Muted.TLabel").pack(anchor="w")
        pick = ttk.Frame(head)
        pick.pack(side="right")
        self.dev_var = tk.StringVar()
        self.dev_combo = ttk.Combobox(pick, textvariable=self.dev_var, state="readonly", width=30)
        self.dev_combo.pack(side="left")
        self.dev_combo.bind("<<ComboboxSelected>>", lambda e: self._on_select())
        ttk.Button(pick, text=ICON["refresh"], style="Icon.TButton", width=3,
                   command=lambda: self.bg(self.refresh_devices)).pack(side="left", padx=(6, 0))
        self.glow = tk.Canvas(main, height=1, highlightthickness=0, bd=0)  # gradient strip (rich skins)
        self.glow.pack(fill="x", pady=(0, 8))
        self.glow.bind("<Configure>", lambda e: self._draw_glow())

        self.pages_box = ttk.Frame(main, padding=(20, 4, 20, 0))
        self.pages_box.pack(fill="both", expand=True)
        self.pages = {
            "setup": self._page_setup(self.pages_box),
            "mirror": self._page_mirror(self.pages_box),
            "connect": self._page_connect(self.pages_box),
            "scan": self._page_scan(self.pages_box),
            "tools": self._page_tools(self.pages_box),
            "logcat": self._page_logcat(self.pages_box),
            "shell": self._page_shell(self.pages_box),
            "apps": self._page_apps(self.pages_box),
            "device": self._page_device(self.pages_box),
            "settings": self._page_settings(self.pages_box),
        }

        # activity
        act = ttk.Frame(main, padding=(20, 6, 20, 0))
        act.pack(fill="x")
        ttk.Label(act, text="Activity", style="Head.TLabel").pack(anchor="w")
        self.log_box = tk.Text(act, height=4, state="disabled", font=("Consolas", 9), wrap="word",
                               relief="flat", borderwidth=0, padx=8, pady=6)
        self.log_box.pack(fill="x", pady=(4, 0))
        self.status_var = tk.StringVar()
        ttk.Label(main, textvariable=self.status_var, style="Status.TLabel",
                  padding=(20, 5, 20, 6)).pack(fill="x", pady=(6, 0))

    def card(self, parent, title=None, subtitle=None, **pack):
        c = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        opts = {"fill": "x", "pady": (0, 10)}
        opts.update(pack)
        c.pack(**opts)
        if title:
            ttk.Label(c, text=title, style="Head.TLabel").pack(anchor="w")
        if subtitle:
            self.wrap_label(c, text=subtitle, style="Muted.TLabel").pack(fill="x", pady=(2, 8))
        return c

    @staticmethod
    def wrap_label(parent, **kw):
        """A label that re-wraps its text to whatever width it gets."""
        lbl = ttk.Label(parent, justify="left", **kw)
        lbl.bind("<Configure>", lambda e: e.widget.configure(wraplength=max(80, e.width - 4)))
        return lbl

    def _opt(self, key):
        var = tk.BooleanVar(value=bool(self.cfg.get(key)))
        var.trace_add("write", lambda *_: self._set_cfg(key, var.get()))
        return var

    def _set_cfg(self, key, value):
        self.cfg[key] = value
        save_config(self.cfg)

    # ---------------------------------------------------------------- Get started page
    def _page_setup(self, parent):
        f = ttk.Frame(parent)
        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True)

        left = ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        s = self.card(left, "Set up your phone · one time, about 2 minutes",
                      "Works on any Android phone. Needed for full control, the remote and recording.",
                      fill="both", expand=True)
        steps = [
            ("1", "Turn on Developer options",
             "Open Settings and search for “Build number” (on some phones: “Software version” or “OS version”). "
             "Tap it 7 times until it says “You are now a developer”. Enter your PIN if asked."),
            ("2", "Turn on USB debugging",
             "Search Settings for “USB debugging” and turn it on. Tap OK on the warning."),
            ("3", "Plug in and allow",
             "Connect the phone with a USB cable. On the phone, tap Allow and tick "
             "“Always allow from this computer”."),
        ]
        for num, title, body in steps:
            row = ttk.Frame(s)
            row.pack(fill="x", pady=(2, 6))
            ttk.Label(row, text=num, style="Step.TLabel", width=2, anchor="center").pack(side="left", anchor="n", padx=(0, 10))
            box = ttk.Frame(row)
            box.pack(side="left", fill="x", expand=True)
            ttk.Label(box, text=title, style="Head.TLabel").pack(anchor="w")
            self.wrap_label(box, text=body, style="Muted.TLabel").pack(fill="x")

        hint = ttk.Frame(s)
        hint.pack(fill="x", pady=(2, 8))
        ttk.Label(hint, text="Exact path for", style="Muted.TLabel").pack(side="left")
        self.brand_var = tk.StringVar(value=OTHER_BRAND)
        cb = ttk.Combobox(hint, textvariable=self.brand_var, values=list(BRAND_STEPS), state="readonly", width=34)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: (setattr(self, "brand_auto", False), self._update_setup()))
        self.brand_hint = tk.StringVar()
        self.wrap_label(s, textvariable=self.brand_hint, style="Muted.TLabel").pack(fill="x", pady=(0, 8))

        ttk.Separator(s).pack(fill="x", pady=(2, 8))
        self.check_rows = {}
        for key, text in (("plugged", "Phone plugged in"), ("debug", "USB debugging on"),
                          ("allowed", "This PC allowed on the phone")):
            row = ttk.Frame(s)
            row.pack(fill="x", pady=1)
            icon = ttk.Label(row, text="", font=(self.icon_font, 12), width=2)
            icon.pack(side="left")
            ttk.Label(row, text=text).pack(side="left", padx=(6, 0))
            self.check_rows[key] = icon
        self.setup_status = tk.StringVar(value="Looking for your phone...")
        status_row = ttk.Frame(s)
        status_row.pack(fill="x", pady=(10, 0))
        self.setup_go = ttk.Button(status_row, text="Start mirroring", style="Accent.TButton",
                                   command=lambda: (self.show_page("mirror"), self.toggle_mirror()))
        self.wrap_label(status_row, textvariable=self.setup_status, style="Ok.TLabel").pack(
            side="left", fill="x", expand=True)

        right = ttk.Frame(cols, width=290)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)
        a = self.card(right, "No developer mode?", "Ways to see the phone without changing any phone "
                                                   "settings. View only: no remote, recording or typing.",
                      fill="both", expand=True)
        ttk.Label(a, text="Wireless Display", style="Head.TLabel").pack(anchor="w", pady=(4, 0))
        self.wrap_label(a, text="Windows shows the phone's screen (Miracast). In Projecting settings add the optional "
                                "feature “Wireless Display”, then on the phone use Cast, Smart View or "
                                "Screen cast. Not every phone or PC supports it.",
                        style="Muted.TLabel").pack(fill="x", pady=(2, 6))
        ttk.Button(a, text="Open Projecting settings",
                   command=lambda: open_uri("ms-settings:project")).pack(anchor="w")
        ttk.Label(a, text="Phone Link (Microsoft)", style="Head.TLabel").pack(anchor="w", pady=(14, 0))
        self.wrap_label(a, text="Install “Link to Windows” on the phone. Shows notifications, messages, photos "
                                "and calls; some phones can also mirror apps.",
                        style="Muted.TLabel").pack(fill="x", pady=(2, 6))
        self.phone_link_btn = ttk.Button(a, text="Open Phone Link", command=self.open_phone_link)
        self.phone_link_btn.pack(anchor="w")
        return f

    def open_phone_link(self):
        if self.phone_link:
            ok = open_uri("shell:AppsFolder\\%s!App" % self.phone_link)
        else:  # not installed: Microsoft Store page
            ok = open_uri("ms-windows-store://pdp/?productid=9NMPJ99VJBWV")
        if not ok:
            self.log("Could not open Phone Link.")

    def _update_setup(self):
        devs = list(self.devices.values())
        usb = self.usb
        ready = [d for d in devs if d["state"] == "device"]
        plugged = bool(usb) or bool(devs)
        debug = bool(devs) or any(p["adb_iface"] for p in usb)
        allowed = bool(ready)

        # brand: from the connected phone's name if we know it, else USB info
        if self.brand_auto:
            names = [d.get("model", "") for d in devs] + [p.get("name", "") for p in usb]
            brand = next((b for b in (brand_from_text(n) for n in names) if b), None) or \
                next((p["brand"] for p in usb if p.get("brand")), None)
            if brand:
                self.brand_var.set(brand)
        dev_opts, usb_dbg, extra = BRAND_STEPS.get(self.brand_var.get(), BRAND_STEPS[OTHER_BRAND])
        self.brand_hint.set("① %s\n② %s%s" % (dev_opts, usb_dbg, ("\n" + extra) if extra else ""))

        pal = self.pal
        for key, done in (("plugged", plugged), ("debug", debug), ("allowed", allowed)):
            self.check_rows[key].configure(text="" if done else "",
                                           foreground=pal["ok"] if done else pal["muted"])
        if allowed:
            msg = "All set - your phone is ready."
            self.setup_go.pack(side="right", padx=(10, 0))
        else:
            self.setup_go.pack_forget()
            if any(d["state"] == "unauthorized" for d in devs):
                msg = "Unlock the phone and tap Allow on the “Allow USB debugging?” message."
            elif debug:
                msg = ("USB debugging is on, but the phone isn't answering. Unplug it and plug it back in; "
                       "if asked, choose “File transfer”.")
            elif plugged:
                msg = "Phone found. Now do steps 1 and 2 on the phone - this page updates by itself."
            elif not self.usb_checked:
                msg = "Looking for your phone..."
            else:
                msg = ("Plug the phone into this PC with a USB cable. Nothing happening? Try another cable "
                       "(some only charge) or another USB port.")
        self.setup_status.set(msg)
        self.phone_link_btn.configure(text="Open Phone Link" if self.phone_link else "Get Phone Link")
        self._update_device_info()

    # ---------------------------------------------------------------- Mirror page
    def _page_mirror(self, parent):
        f = ttk.Frame(parent)
        q = self.card(f, "Mirror quality")
        seg = ttk.Frame(q)
        seg.pack(fill="x", pady=(6, 0))
        self.quality_var = tk.StringVar(value=self.cfg.get("quality", "Auto"))
        for name in ["Auto", "Low", "Medium", "High"]:
            ttk.Radiobutton(seg, text=name, value=name, variable=self.quality_var, style="Toggle.TButton",
                            width=8, command=self._quality_changed).pack(side="left", padx=(0, 4))
        self.quality_help = tk.StringVar()
        ttk.Label(seg, textvariable=self.quality_help, style="Muted.TLabel").pack(side="left", padx=10)
        self._quality_changed(save=False)

        o = self.card(f, "Options")
        grid = ttk.Frame(o)
        grid.pack(fill="x", pady=(6, 0))
        items = [
            ("screen_off", "Turn phone screen off"), ("stay_awake", "Keep phone awake"),
            ("on_top", "Window always on top"), ("remote", "Remote beside the phone"),
            ("view_only", "View only (no control)"), ("audio", "Forward phone audio"),
            ("record", "Record when mirroring starts"), ("auto_reconnect", "Auto-reconnect on Wi-Fi"),
        ]
        self.opt_vars = {}
        for i, (key, text) in enumerate(items):
            self.opt_vars[key] = self._opt(key)
            ttk.Checkbutton(grid, text=text, variable=self.opt_vars[key], style="Switch.TCheckbutton").grid(
                row=i // 2, column=i % 2, sticky="w", padx=(0, 24), pady=3)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        pr = ttk.Frame(o)
        pr.pack(fill="x", pady=(8, 0))
        ttk.Label(pr, text="Remote position").pack(side="left", padx=(0, 10))
        self.bar_pos_var = tk.StringVar(value=self.cfg.get("bar_pos", "Right"))
        for name in BAR_POSITIONS:
            ttk.Radiobutton(pr, text=name, value=name, variable=self.bar_pos_var, style="Toggle.TButton", width=7,
                            command=lambda: (self._set_cfg("bar_pos", self.bar_pos_var.get()),
                                             self._sync_bar_pos())).pack(side="left", padx=(0, 4))

        rc = self.card(f, "Recording")
        rr = ttk.Frame(rc)
        rr.pack(fill="x", pady=(6, 0))
        ttk.Label(rr, text="Quality").pack(side="left")
        self.rec_quality_var = tk.StringVar(value=self.cfg.get("rec_quality", "High"))
        cq = ttk.Combobox(rr, textvariable=self.rec_quality_var, values=list(REC_QUALITY), state="readonly", width=9)
        cq.pack(side="left", padx=(6, 14))
        cq.bind("<<ComboboxSelected>>", lambda e: self._set_cfg("rec_quality", self.rec_quality_var.get()))
        ttk.Label(rr, text="Format").pack(side="left")
        self.rec_format_var = tk.StringVar(value=self.cfg.get("rec_format", "MP4 video"))
        cf = ttk.Combobox(rr, textvariable=self.rec_format_var, values=list(REC_FORMATS), state="readonly", width=11)
        cf.pack(side="left", padx=(6, 14))
        cf.bind("<<ComboboxSelected>>", lambda e: self._set_cfg("rec_format", self.rec_format_var.get()))
        self.rec_audio_var = self._opt("rec_audio")
        ttk.Checkbutton(rr, text="Audio", variable=self.rec_audio_var, style="Switch.TCheckbutton").pack(side="left")
        self.rec_btn = ttk.Button(rr, text="● Record", command=lambda: self.toggle_recording(self.selected()))
        self.rec_btn.pack(side="right")

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(4, 0))
        self.mirror_btn = ttk.Button(row, text="Start mirroring", style="Accent.TButton", command=self.toggle_mirror)
        self.mirror_btn.pack(side="left", ipadx=24, ipady=6)
        self.wrap_label(row, text="Full screen, Back, Home, volume and Stop are on the remote beside the "
                                  "phone. In the mirror: right-click = Back · middle-click = Home.",
                        style="Muted.TLabel").pack(side="left", fill="x", expand=True, padx=16)
        return f

    def _quality_changed(self, save=True):
        q = self.quality_var.get()
        self.quality_help.set(QUALITY_HELP.get(q, ""))
        if save:
            self._set_cfg("quality", q)

    # ---------------------------------------------------------------- Wireless page
    def _page_connect(self, parent):
        f = ttk.Frame(parent)
        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True)

        # left: QR pairing (the easy way)
        left = ttk.Frame(cols)
        left.pack(side="left", fill="y", padx=(0, 10))
        qc = self.card(left, "Pair with QR code", "Easiest · Android 11+ · no cable", fill="y", expand=True)
        self.qr_canvas = tk.Canvas(qc, width=QR_PX, height=QR_PX, highlightthickness=0, bg="white")
        self.qr_canvas.pack(pady=(0, 8))
        self.qr_canvas.create_text(QR_PX // 2, QR_PX // 2, text="Click 'Show QR code'", fill="#555", font=(self.font, 9))
        ttk.Label(qc, text="Phone: Developer options › Wireless\ndebugging › Pair device with QR code",
                  style="Muted.TLabel", justify="left").pack(anchor="w")
        self.qr_status = tk.StringVar(value="")
        ttk.Label(qc, textvariable=self.qr_status, style="Ok.TLabel", wraplength=QR_PX + 20, justify="left").pack(anchor="w", pady=(4, 2))
        self.qr_progress = ttk.Progressbar(qc, mode="indeterminate", length=QR_PX)
        self.qr_btn = ttk.Button(qc, text="Show QR code", style="Accent.TButton", command=self.start_qr)
        self.qr_btn.pack(fill="x", side="bottom")

        right = ttk.Frame(cols)
        right.pack(side="left", fill="both", expand=True)

        pc = self.card(right, "Pair with code", "Phone: Wireless debugging > Pair device with pairing code. "
                                                "The address is filled in automatically when the phone is found.")
        r = ttk.Frame(pc)
        r.pack(fill="x")
        self.pair_addr = tk.StringVar()
        self.pair_code = tk.StringVar()
        ttk.Label(r, text="Address").grid(row=0, column=0, sticky="w")
        ttk.Entry(r, textvariable=self.pair_addr, width=22).grid(row=1, column=0, sticky="we", padx=(0, 8))
        ttk.Label(r, text="6-digit code").grid(row=0, column=1, sticky="w")
        code = ttk.Entry(r, textvariable=self.pair_code, width=10)
        code.grid(row=1, column=1, sticky="w", padx=(0, 8))
        code.bind("<Return>", lambda e: self.pair())
        ttk.Button(r, text="Pair", style="Accent.TButton", command=self.pair).grid(row=1, column=2)
        r.columnconfigure(0, weight=1)

        cc = self.card(right, "Connect", "A phone that is already paired, or switched over from USB.")
        r2 = ttk.Frame(cc)
        r2.pack(fill="x")
        self.addr_var = tk.StringVar()
        self.addr_combo = ttk.Combobox(r2, textvariable=self.addr_var, width=12)
        self.addr_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="Connect", style="Accent.TButton", command=self.connect).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="Disconnect", command=self.disconnect).pack(side="left", padx=(6, 0))
        r3 = ttk.Frame(cc)
        r3.pack(fill="x", pady=(10, 0))
        ttk.Button(r3, text="USB → Wi-Fi", command=self.usb_to_wifi).pack(side="left")
        self.wrap_label(r3, text="Plugged in? Switch it to Wi-Fi.", style="Muted.TLabel").pack(
            side="left", fill="x", expand=True, padx=10)
        self.nearby_var = tk.StringVar(value="Searching for phones with Wireless debugging on...")
        self.wrap_label(right, textvariable=self.nearby_var, style="Muted.TLabel").pack(fill="x")
        self._refresh_recent()
        return f

    # ---------------------------------------------------------------- Scan page
    def _page_scan(self, parent):
        f = ttk.Frame(parent)
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Network").pack(side="left")
        subnets = sorted({ip.rsplit(".", 1)[0] + ".0/24" for ip in local_ipv4s()})
        self.subnet_var = tk.StringVar(value=subnets[-1] if subnets else "192.168.1.0/24")
        ttk.Combobox(top, textvariable=self.subnet_var, values=subnets, width=18).pack(side="left", padx=8)
        self.scan_btn = ttk.Button(top, text="Scan", style="Accent.TButton", command=self.scan)
        self.scan_btn.pack(side="left")
        self.scan_progress = ttk.Progressbar(top, mode="determinate", length=160)
        self.scan_progress.pack(side="left", padx=12)
        self.scan_status = tk.StringVar(value="Finds devices on your network and suggests which are phones.")
        ttk.Label(f, textvariable=self.scan_status, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))

        box = ttk.Frame(f)
        box.pack(fill="both", expand=True)
        cols = ("ip", "name", "hint", "adb")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", height=8, selectmode="browse")
        for c, text, w in zip(cols, ("IP address", "Name", "Looks like", "ADB"), (120, 190, 150, 170)):
            self.tree.heading(c, text=text, anchor="w")
            self.tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.scan_connect())

        bot = ttk.Frame(f)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Button(bot, text="Connect", style="Accent.TButton", command=self.scan_connect).pack(side="left")
        ttk.Button(bot, text="Find ADB port", command=self.scan_find_port).pack(side="left", padx=6)
        ttk.Label(bot, text="Scan only networks you own or manage.", style="Muted.TLabel").pack(side="right")
        self.scan_rows = {}
        return f

    # ---------------------------------------------------------------- Tools page
    def _page_tools(self, parent):
        f = ttk.Frame(parent)
        b = self.card(f, "Phone buttons")
        grid = ttk.Frame(b)
        grid.pack(fill="x", pady=(6, 0))
        buttons = [("Home", None), ("Back", None), ("Recents", None), ("Power", None),
                   ("Volume up", None), ("Volume down", None), ("Rotate", self.rotate), ("Screenshot", self.screenshot)]
        for i, (name, cmd) in enumerate(buttons):
            cmd = cmd or (lambda n=name: self.key(KEYS[n]))
            ttk.Button(grid, text=name, command=cmd).grid(row=i // 4, column=i % 4, sticky="we", padx=3, pady=3)
        for c in range(4):
            grid.columnconfigure(c, weight=1)

        t = self.card(f, "Type on phone", "Plain English characters only. Handy for logins and OTPs.")
        r = ttk.Frame(t)
        r.pack(fill="x")
        self.text_var = tk.StringVar()
        e = ttk.Entry(r, textvariable=self.text_var)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.send_text())
        ttk.Button(r, text="Send", style="Accent.TButton", command=self.send_text).pack(side="left", padx=(8, 0))
        ttk.Button(r, text="Enter ↵", command=lambda: self.key(KEYS["Enter"])).pack(side="left", padx=(6, 0))

        a = self.card(f, "Install app", "Drop .apk files anywhere on this window, or choose them.")
        ttk.Button(a, text="Choose APK...", command=self.install_dialog).pack(anchor="w")
        return f

    # ---------------------------------------------------------------- Settings page
    def _page_settings(self, parent):
        f = ttk.Frame(parent)
        ap = self.card(f, "Skin")
        grid = ttk.Frame(ap, style="Card.TFrame")
        grid.pack(anchor="w", pady=(6, 4))
        self.theme_tiles = {}
        for i, name in enumerate(skins.ORDER):
            cv = tk.Canvas(grid, width=84, height=58, highlightthickness=0, bd=0, cursor="hand2")
            cv.grid(row=i // 7, column=i % 7, padx=(0, 6), pady=(0, 6))
            cv.bind("<Button-1>", lambda e, n=name: self.pick_theme(n))
            self.theme_tiles[name] = cv
        self.theme_note = tk.StringVar()
        self.wrap_label(ap, textvariable=self.theme_note, style="Muted.TLabel").pack(fill="x")

        a = self.card(f, "adb", "Order: path below > Android SDK (ANDROID_HOME / ANDROID_SDK_ROOT / Android Studio) "
                                "> adb on PATH > built-in. The SDK's adb wins: it is the one Android Studio and "
                                "Flutter use.")
        self.adb_info = tk.StringVar(value="detecting...")
        ttk.Label(a, textvariable=self.adb_info, wraplength=560, justify="left").pack(anchor="w", pady=(0, 6))
        r = ttk.Frame(a)
        r.pack(fill="x")
        self.adb_path_var = tk.StringVar(value=self.cfg.get("adb_path", ""))
        ttk.Entry(r, textvariable=self.adb_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text="Browse", command=self.pick_adb).pack(side="left", padx=(8, 0))
        ttk.Button(r, text="Apply", command=self.apply_adb).pack(side="left", padx=(6, 0))

        o = self.card(f, "Screenshots and recordings")
        r = ttk.Frame(o)
        r.pack(fill="x", pady=(6, 0))
        self.out_var = tk.StringVar(value=self.cfg.get("out_dir"))
        ttk.Entry(r, textvariable=self.out_var).pack(side="left", fill="x", expand=True)
        ttk.Button(r, text="Browse", command=self.pick_out).pack(side="left", padx=(8, 0))
        ttk.Button(r, text="Open", command=lambda: self.open_path(self.out_dir())).pack(side="left", padx=(6, 0))
        ttk.Label(f, text="%s %s · scrcpy 2.5 (Apache-2.0) · Android adb" % (APP, VERSION),
                  style="Muted.TLabel").pack(anchor="w")
        return f

    # ================================================================ theme / nav
    def apply_theme(self, mode):
        """Switch skin: sv-ttk for Light/Dark, a drawn clam theme for the others (skins.py)."""
        skin = skins.resolve(mode, system_is_dark())
        self.skin = skin
        st = ttk.Style()
        if skin["engine"] == "sv":
            if sv_ttk:
                sv_ttk.set_theme(skin["base"])
            self.font, self.font_display, self.mono = self.base_fonts
        else:
            f = skins.build_custom(self.root, skin)
            self.font, self.font_display, self.mono = f["ui"], f["display"], f["mono"]
        # sv-ttk's tk_setPalette stamps its colours onto every widget (ttk labels too); clear
        # them so each skin's styles apply, and keep labels made later from getting stamped.
        self.root.option_add("*TLabel.background", "", 80)
        self.root.option_add("*TLabel.foreground", "", 80)
        self._reset_ttk_colors(self.root)
        self.pal = pal = {k: skin[k] for k in ("bg", "side", "hover", "sel", "accent", "accent2", "fg", "muted",
                                               "field", "ok", "warn", "border", "on_accent")}
        pal["dark"] = skin.get("dark", skin.get("base") == "dark")
        st.configure("Title.TLabel", font=(self.font_display, 17, "bold"))
        st.configure("Head.TLabel", font=(self.font, 11, "bold"))
        st.configure("Muted.TLabel", foreground=pal["muted"], font=(self.font, 9))
        st.configure("Ok.TLabel", foreground=pal["ok"], font=(self.font, 9))
        st.configure("Step.TLabel", foreground=pal["accent"], font=(self.font_display, 16, "bold"))
        st.configure("Icon.TButton", font=(self.icon_font, 10))
        st.configure("TButton", font=(self.font, 10))
        st.configure("Toggle.TButton", font=(self.font, 10))
        st.configure("TCheckbutton", font=(self.font, 10))
        st.configure("Treeview", rowheight=28, font=(self.font, 10))
        st.configure("Apps.Treeview", rowheight=30, font=(self.font, 10))
        st.configure("Treeview.Heading", font=(self.font, 9, "bold"))
        if skin.get("statusbar"):  # Developer: a blue status bar
            st.configure("Status.TLabel", background=pal["accent"], foreground="#ffffff", font=(self.font, 9))
        else:
            st.configure("Status.TLabel", background=pal["bg"], foreground=pal["muted"], font=(self.font, 9))
        self.root.configure(bg=pal["bg"])
        self.side.configure(bg=pal["side"])
        self.side_foot.configure(bg=pal["side"], fg=pal["muted"], font=(self.font, 8))
        for item in self.nav.values():
            item.icon.configure(font=(self.icon_font, 13))
            item.label.configure(font=(self.font, 10))
            item.paint()
        self._draw_brand()
        self._draw_glow()
        self.log_box.configure(bg=pal["field"], fg=pal["muted"], insertbackground=pal["fg"], font=(self.mono, 9))
        self.phone_icon.configure(foreground=pal["accent"])
        self.tree.tag_configure("phone", foreground=pal["accent"])
        self.tree.tag_configure("adb", foreground=pal["ok"])
        self._update_setup()
        self.dev_theme()
        self._draw_theme_tiles()
        RemoteBar.ON = pal["accent"]
        self.root.update_idletasks()
        set_titlebar_dark(self.root, pal["dark"])
        self._set_glass(bool(skin.get("glass")))
        self._skin_anim_start()

    def _set_glass(self, on):
        """Glass skin: Windows 11 Acrylic behind the window (live blur of what is behind it).

        Tk draws with GDI, which the compositor adds on top of the blur: black is clear glass,
        dark greys are frosted tints - which is why the Glass palette is all light-on-dark."""
        if not IS_WIN:
            return
        try:
            import ctypes

            class MARGINS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]
            hwnd = int(self.root.wm_frame(), 16)
            m = MARGINS(-1, -1, -1, -1) if on else MARGINS(0, 0, 0, 0)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
            v = ctypes.c_int(3 if on else 1)  # DWMWA_SYSTEMBACKDROP_TYPE: 3 = Acrylic, 1 = none
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(v), ctypes.sizeof(v))
        except Exception:
            pass

    @staticmethod
    def transparency_on():
        """Windows' 'Transparency effects' switch (Glass shows a flat colour without it)."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "EnableTransparency")[0] != 0
        except OSError:
            return True

    def _reset_ttk_colors(self, w):
        for c in w.winfo_children():
            if c.winfo_class().startswith("T"):  # ttk widgets: TLabel, TFrame, TButton, ...
                for opt in ("background", "foreground"):
                    try:
                        if str(c.cget(opt)):
                            c.configure(**{opt: ""})
                    except tk.TclError:
                        pass
            self._reset_ttk_colors(c)

    # ---- skin decorations
    def _draw_brand(self, cursor_on=True):
        s = self.skin
        text = s.get("brand", APP) if s["engine"] == "custom" else APP
        font = "Georgia" if s.get("serif_brand") else self.font_display
        skins.draw_brand(self.brand, s, font, text, cursor_on)

    def _draw_glow(self, phase=0.0):
        s = self.skin
        if s.get("gradient"):
            self.glow.configure(height=3, bg=s["bg"])
            self.glow.update_idletasks()
            skins.draw_gradient(self.glow, max(self.glow.winfo_width(), 400), 3, s["accent"], s["accent2"], phase)
        else:
            self.glow.delete("all")
            self.glow.configure(height=1, bg=self.pal.get("border", self.pal["bg"]))

    def _skin_anim_start(self):
        """Hacker: blinking cursor. Gamer: RGB-cycling nav bar and moving glow."""
        self._anim_token = getattr(self, "_anim_token", 0) + 1
        token, s = self._anim_token, self.skin
        if not (s.get("cursor") or s.get("rgb")):
            return
        state = {"t": 0}

        def tick():
            if self.closing or token != self._anim_token:
                return
            state["t"] += 1
            if s.get("cursor") and state["t"] % 6 == 0:
                self._draw_brand(cursor_on=(state["t"] // 6) % 2 == 0)
            if s.get("rgb"):
                c = skins.hue_cycle(state["t"] / 90.0)
                item = self.nav.get(self.page)
                if item:
                    item.bar.configure(bg=c)
                    item.icon.configure(fg=c)
                if state["t"] % 2 == 0:
                    self._draw_glow(phase=state["t"] / 120.0)
            self.root.after(90, tick)
        self.root.after(90, tick)

    def _draw_theme_tiles(self):
        current = self.cfg.get("theme", "System")
        for name, cv in getattr(self, "theme_tiles", {}).items():
            sk = skins.resolve(name, system_is_dark())
            if name == "System":
                sk = dict(sk)
                sk["name"] = "System"
            skins.draw_preview(cv, sk, name == current, self.font)
        if hasattr(self, "theme_note"):
            sk = skins.SKINS.get(current)
            note = "%s — %s" % (current, sk["tagline"]) if sk else "System — follows Windows light / dark"
            if sk and sk.get("glass") and not self.transparency_on():
                note += ". Windows' Transparency effects are off, so the glass shows flat: turn them on in " \
                        "Settings › Personalization › Colors."
            self.theme_note.set(note)

    def pick_theme(self, name):
        self._set_cfg("theme", name)
        self.apply_theme(name)

    def show_page(self, key):
        if self.page == key:
            return
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        self.page = key
        for item in self.nav.values():
            item.paint()
        if key == "connect":
            self.bg(self._nearby_loop)
        ready = self.devices.get(self.selected(), {}).get("state") == "device" and not self.adb_stopped
        if key == "apps" and not self.apps and ready:
            self.apps_refresh()
        if key == "device":
            self._adb_state_show()
            if ready:
                self.dev_refresh()

    # ================================================================ UI state
    def selected(self):
        return self.label_to_serial.get(self.dev_var.get())

    def _label(self, d):
        kind = "Wi-Fi" if d["wifi"] else "USB"
        extra = {"unauthorized": " · allow on phone", "offline": " · offline"}.get(d["state"], "")
        return "%s · %s%s" % (d["model"] or d["serial"], kind, extra)

    def _apply_devices(self, devs):
        current = self.selected()
        self.devices = {d["serial"]: d for d in devs}
        self.label_to_serial = {}
        for d in devs:
            label = self._label(d)
            if label in self.label_to_serial:
                label += " (%s)" % d["serial"]
            self.label_to_serial[label] = d["serial"]
        labels = list(self.label_to_serial)
        self.dev_combo["values"] = labels
        if current in self.devices:
            self.dev_var.set(self._label_of(current))
        elif labels:
            ready = [l for l in labels if self.devices[self.label_to_serial[l]]["state"] == "device"]
            self.dev_var.set((ready or labels)[0])
            self.battery_text = ""
        else:
            self.dev_var.set("")
            self.battery_text = ""
        self._update_device_info()

    def _label_of(self, serial):
        return next((l for l, s in self.label_to_serial.items() if s == serial), "")

    def _on_select(self):
        self.battery_text = ""
        self._update_device_info()
        self.bg(self.refresh_devices)

    def _update_device_info(self):
        serial = self.selected()
        dev = self.devices.get(serial)
        if not dev and self.usb:
            self.title_var.set("Phone plugged in")
            self.info_var.set("USB debugging is off - open Get started to turn it on (about 2 minutes).")
        elif not dev:
            self.title_var.set("No phone connected")
            self.info_var.set("New here? Open Get started. Otherwise plug in with USB or use the Wireless page.")
        elif dev["state"] == "unauthorized":
            self.title_var.set(dev["model"] or "Phone found")
            self.info_var.set("Unlock the phone and tap 'Allow' on the USB debugging prompt.")
        else:
            self.title_var.set(dev["model"] or serial)
            parts = ["Wi-Fi" if dev["wifi"] else "USB", serial]
            if self.battery_text:
                parts.append(self.battery_text)
            if serial in self.procs:
                parts.append("● Mirroring")
            self.info_var.set("   ·   ".join(parts))
        self.mirror_btn.configure(text="Stop mirroring" if serial in self.procs else "Start mirroring")
        rec = self.recorders.get(serial)
        self.rec_btn.configure(text="Saving..." if rec and rec.stopping else
                               "■ Stop recording" if rec else "● Record")

    def _update_status_bar(self):
        v = getattr(self, "adb_ver", "")
        self.status_var.set("adb %s from %s · %s      scrcpy: built-in 2.5" % (v, self.adb_src, self.adb))
        self.adb_info.set("In use: adb %s from %s — %s" % (v, self.adb_src, self.adb))

    def _refresh_recent(self):
        nearby = ["%s:%s" % (s["ip"], s["port"]) for s in self.nearby if s["kind"] == "connect"]
        recent = [r["addr"] for r in self.cfg.get("recent", [])]
        values = nearby + [a for a in recent if a not in nearby]
        self.addr_combo["values"] = values
        if values and not self.addr_var.get():
            self.addr_var.set(values[0])

    def _remember(self, addr, name):
        recent = [r for r in self.cfg.get("recent", []) if r["addr"] != addr]
        recent.insert(0, {"addr": addr, "name": name})
        self._set_cfg("recent", recent[:8])
        self.ui(self._refresh_recent)

    def out_dir(self):
        d = self.out_var.get().strip() or DEFAULTS["out_dir"]
        os.makedirs(d, exist_ok=True)
        return d

    def need_device(self):
        serial = self.selected()
        dev = self.devices.get(serial)
        if not dev or dev["state"] != "device":
            messagebox.showinfo(APP, "Connect a phone first (USB or the Wireless page).")
            return None
        return serial

    # ================================================================ mirroring
    def toggle_mirror(self):
        serial = self.selected()
        if serial in self.procs:
            self.stop_mirror(serial)
        else:
            serial = self.need_device()
            if serial:
                self.start_mirror(serial)

    def scrcpy_args(self, serial):
        dev = self.devices.get(serial, {"model": "", "wifi": bool(ADDR_RE.search(serial))})
        o = {k: v.get() for k, v in self.opt_vars.items()}
        quality = self.quality_var.get()
        if quality == "Auto":
            quality = "Low" if dev["wifi"] else "High"
        size, rate, fps = PRESETS[quality]
        title = "%s - %s" % (dev["model"] or serial, APP)
        args = [BUNDLED_SCRCPY, "--serial", serial, "--window-title", title,
                "--video-bit-rate", rate, "--max-fps", fps,
                "--shortcut-mod=lalt"]  # the remote bar sends Left-Alt shortcuts
        if size != "0":
            args += ["--max-size", size]
        if o["view_only"]:
            args.append("--no-control")
            if o["screen_off"] or o["stay_awake"]:
                self.log("View only: phone screen-off and keep-awake need control, so they are skipped.")
        else:
            if o["screen_off"]:
                args.append("--turn-screen-off")
            if o["stay_awake"]:
                args.append("--stay-awake")
        if o["on_top"]:
            args.append("--always-on-top")
        if not o["audio"]:
            args.append("--no-audio")
        return args, quality

    def start_mirror(self, serial):
        args, quality = self.scrcpy_args(serial)
        env = adb_env()
        env["ADB"] = self.adb  # scrcpy must use the same adb as we do
        env["SCRCPY_ICON_PATH"] = self.asset_path("icon.png")  # Mirror's icon on the mirror window
        try:
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, creationflags=NO_WINDOW, env=env, cwd=BIN)
        except OSError as e:
            messagebox.showerror(APP, "Could not start scrcpy:\n%s" % e)
            return
        self.procs[serial] = {"proc": proc, "user_stop": False, "started": time.time()}
        o = {k: v.get() for k, v in self.opt_vars.items()}
        if o["remote"] and IS_WIN:
            self._close_remote(serial)
            self.remotes[serial] = RemoteBar(self, serial, proc, o["view_only"],
                                             o["screen_off"] and not o["view_only"])
        if o["record"]:
            self.root.after(1500, lambda: serial in self.procs and self.start_recording(serial))
        self.log("Mirroring %s (%s quality)" % (serial, quality))
        self._update_device_info()
        threading.Thread(target=self._watch, args=(serial, proc), daemon=True).start()

    def stop_mirror(self, serial):
        entry = self.procs.get(serial)
        if entry:
            entry["user_stop"] = True
            kill_tree(entry["proc"])
        self.stop_recording(serial)
        self._close_remote(serial)

    def _close_remote(self, serial):
        bar = self.remotes.pop(serial, None)
        if bar:
            bar.close()

    # ---- recording (a second hidden scrcpy session; works while mirroring)
    def toggle_recording(self, serial):
        if not serial:
            return
        rec = self.recorders.get(serial)
        if rec and rec.stopping:
            self.log("Still saving the last recording - one moment.")
        elif rec:
            self.stop_recording(serial)
        else:
            self.start_recording(serial)

    def start_recording(self, serial):
        dev = self.devices.get(serial)
        if not dev or dev["state"] != "device" or serial in self.recorders:
            if not dev or dev["state"] != "device":
                messagebox.showinfo(APP, "Connect a phone first.")
            return
        try:
            rec = Recorder(self, serial)
        except OSError as e:
            self.log("Could not start recording: %s" % e)
            return
        self.recorders[serial] = rec
        self.log("Recording started (%s) -> %s" % (rec.label, rec.path))
        self._sync_rec_controls()

    def stop_recording(self, serial):
        rec = self.recorders.get(serial)
        if rec and not rec.stopping:
            rec.stop()
            self.log("Stopping recording, saving the file...")
            self._sync_rec_controls()

    def _recording_ended(self, rec):
        if self.recorders.get(rec.serial) is rec:
            del self.recorders[rec.serial]
        if os.path.isfile(rec.path) and os.path.getsize(rec.path) > 0:
            self.log("Recording saved (%s, %.1f MB): %s" % (rec.elapsed(), os.path.getsize(rec.path) / 1e6, rec.path))
        else:
            self.log("Recording failed - no file was written%s." % (": " + rec.error if rec.error else ""))
            if rec.error and "audio" in rec.error.lower():
                self.log("Audio recording needs Android 11 or newer.")
        self._sync_rec_controls()

    def _sync_rec_controls(self):
        self.rec_quality_var.set(self.cfg.get("rec_quality", "High"))
        self.rec_format_var.set(self.cfg.get("rec_format", "MP4 video"))
        self.rec_audio_var.set(bool(self.cfg.get("rec_audio", True)))
        self._update_device_info()

    def _sync_bar_pos(self):
        self.bar_pos_var.set(self.cfg.get("bar_pos", "Right"))
        for bar in self.remotes.values():
            bar.relayout()

    def _watch(self, serial, proc):
        hinted = False
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if not line or line.startswith(("scrcpy 2", "<https", "at ", "... ", "Caused by", "com.genymobile")):
                continue
            self.log("scrcpy: " + line)
            if "stay_on_while_plugged_in" in line and not hinted:
                hinted = True
                self.log("The phone blocked 'Keep phone awake'. Mirroring still works. To allow it on "
                         "OnePlus/Oppo/Realme: Developer options > 'Disable permission monitoring'; "
                         "on Xiaomi: 'USB debugging (Security settings)'.")
        rc = proc.wait()
        entry = self.procs.get(serial)
        if not entry or entry["proc"] is not proc:
            return
        ran = time.time() - entry["started"]
        self.procs.pop(serial, None)
        self.ui(self.stop_recording, serial)
        self.ui(self._close_remote, serial)
        self.ui(self._update_device_info)
        if entry["user_stop"] or self.closing:
            self.log("Mirroring stopped.")
            return
        self.log("Mirror window closed (exit code %s)." % rc)
        if rc != 0 and ADDR_RE.search(serial) and self.opt_vars["auto_reconnect"].get() and ran > 10:
            self._reconnect(serial)

    def _reconnect(self, serial):
        addr = ADDR_RE.search(serial).group(0)
        for attempt in range(1, 6):
            if self.closing:
                return
            self.log("Wi-Fi dropped - reconnecting to %s (try %d/5)..." % (addr, attempt))
            self.adb_run("connect", addr, timeout=15)
            rc, out, _ = self.adb_run("get-state", serial=addr, timeout=10)
            if out.strip() == "device":
                self.log("Reconnected.")
                self.refresh_devices()
                self.ui(self.start_mirror, addr)
                return
            time.sleep(3)
        self.log("Could not reconnect to %s. Check the phone's Wi-Fi and press Connect." % addr)

    # ================================================================ wireless
    def discover(self, timeout=1.5):
        """Wireless-debugging services on the LAN: our own mDNS query + adb's, merged."""
        found = {}
        for s in mdns_browse(timeout):
            found[(s["kind"], s["ip"], s["port"])] = s
        if self.adb:
            rc, out, _ = self.adb_run("mdns", "services", timeout=10)
            for line in out.splitlines():
                m = ADDR_RE.search(line)
                if m and "_adb" in line:
                    kind = "pair" if "pairing" in line else "connect"
                    found.setdefault((kind, m.group(1), int(m.group(2))),
                                     {"name": line.split()[0], "kind": kind, "ip": m.group(1), "port": int(m.group(2))})
        return list(found.values())

    def _nearby_loop(self):
        """While the Wireless page is open, keep looking for phones (fills fields)."""
        if getattr(self, "_nearby_running", False):
            return
        self._nearby_running = True
        try:
            while self.page == "connect" and not self.closing:
                self.nearby = self.discover()
                self.ui(self._apply_nearby)
                time.sleep(2)
        finally:
            self._nearby_running = False

    def _apply_nearby(self):
        pair = [s for s in self.nearby if s["kind"] == "pair" and not s["name"].startswith("mirror-")]
        conn = [s for s in self.nearby if s["kind"] == "connect"]
        if pair:
            addr = "%s:%s" % (pair[0]["ip"], pair[0]["port"])
            cur = self.pair_addr.get().strip()
            if not cur or cur == getattr(self, "_auto_pair_addr", None):
                self.pair_addr.set(addr)
                self._auto_pair_addr = addr
        parts = []
        if conn:
            parts.append("Ready to connect: " + ", ".join("%s:%s" % (s["ip"], s["port"]) for s in conn))
        if pair:
            parts.append("Pairing screen open on %s — type the code." % pair[0]["ip"])
        self.nearby_var.set("  ·  ".join(parts) if parts else
                            "No phones with Wireless debugging found on this network yet.")
        self._refresh_recent()

    # --- QR pairing
    def start_qr(self):
        if not qrcode:
            messagebox.showerror(APP, "QR support is missing from this build.")
            return
        self.qr_token += 1
        token = self.qr_token
        name, password = "mirror-" + rand_str(6), rand_str(10)
        self.draw_qr("WIFI:T:ADB;S:%s;P:%s;;" % (name, password))
        self.qr_status.set("Waiting for the phone to scan...")
        self.qr_progress.pack(fill="x", pady=(0, 8), before=self.qr_btn)
        self.qr_progress.start(12)
        self.qr_btn.configure(text="New QR code")
        self.bg(self._qr_wait, token, name, password)

    def draw_qr(self, data):
        q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(data)
        q.make(fit=True)
        m = q.get_matrix()
        cell = max(2, QR_PX // len(m))
        size = cell * len(m)
        c = self.qr_canvas
        c.delete("all")
        c.configure(width=size, height=size, bg="white")
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    c.create_rectangle(x * cell, y * cell, (x + 1) * cell, (y + 1) * cell, fill="black", width=0)

    def _qr_done(self, token, msg):
        if token != self.qr_token:
            return
        self.qr_progress.stop()
        self.qr_progress.pack_forget()
        self.qr_status.set(msg)

    def _qr_wait(self, token, name, password):
        deadline = time.time() + 180
        while time.time() < deadline and token == self.qr_token and not self.closing:
            svc = next((s for s in self.discover(1.2) if s["kind"] == "pair" and s["name"] == name), None)
            if not svc:
                continue
            addr = "%s:%s" % (svc["ip"], svc["port"])
            self.ui(self.qr_status.set, "Phone found at %s — pairing..." % svc["ip"])
            rc, out, err = self.adb_run("pair", addr, password, timeout=40)
            if "Successfully paired" not in out + err:
                self.log("QR pairing failed: %s" % (out + err).strip())
                self.ui(self._qr_done, token, "Pairing failed — click New QR code and try again.")
                return
            self.log("Paired with %s via QR." % svc["ip"])
            ok = self._connect_after_pair(svc["ip"])
            self.ui(self._qr_done, token, "Connected ✓" if ok else
                    "Paired ✓ — now press Connect with the IP & port shown on the phone.")
            return
        self.ui(self._qr_done, token, "QR code expired — click New QR code." if token == self.qr_token else "")

    def _connect_after_pair(self, ip):
        for _ in range(8):
            target = next((s for s in self.discover(1.2) if s["kind"] == "connect" and s["ip"] == ip), None)
            if target:
                return self._connect("%s:%s" % (ip, target["port"]))
            # adb (with mDNS) often auto-connects a freshly paired phone
            rc, out, _ = self.adb_run("devices", timeout=10)
            if re.search(re.escape(ip) + r":\d+\s+device", out):
                self.refresh_devices()
                return True
            time.sleep(1)
        self.ui(self.addr_var.set, ip + ":")
        return False

    # --- code pairing
    def pair(self):
        addr, code = self.pair_addr.get().strip(), self.pair_code.get().strip()
        if not ADDR_RE.search(addr) or not code:
            messagebox.showinfo(APP, "Open 'Pair device with pairing code' on the phone. The address fills in "
                                     "by itself (or type the IP:port shown), then type the 6-digit code.")
            return
        self.bg(self._pair, addr, code)

    def _pair(self, addr, code):
        self.log("Pairing with %s..." % addr)
        rc, out, err = self.adb_run("pair", addr, code, timeout=40)
        msg = (out + err).strip()
        if "Successfully paired" not in msg:
            self.log("Pairing failed: %s" % (msg or "no response"))
            return
        self.log("Paired. Connecting...")
        self.ui(self.pair_code.set, "")
        if not self._connect_after_pair(addr.split(":")[0]):
            self.log("Paired. Type the 'IP address & Port' from the Wireless debugging screen "
                     "(not the pairing port) into Connect.")

    # --- connect / disconnect
    def _norm_addr(self, text):
        text = text.strip()
        if text and ":" not in text:
            text += ":5555"
        return text

    def connect(self, addr=None):
        addr = self._norm_addr(addr or self.addr_var.get())
        if not ADDR_RE.search(addr):
            messagebox.showinfo(APP, "Enter the phone's IP address, e.g. 192.168.1.20:5555.")
            return
        self.bg(self._connect, addr)

    def _connect(self, addr):
        self.log("Connecting to %s..." % addr)
        rc, out, err = self.adb_run("connect", addr, timeout=20)
        msg = (out + err).strip()
        if "connected to" in msg and "cannot" not in msg and "failed" not in msg:
            _, model, _ = self.adb_run("shell", "getprop", "ro.product.model", serial=addr, timeout=10)
            self._remember(addr, model.strip())
            self.log("Connected to %s %s" % (addr, model.strip()))
            self.refresh_devices()
            self.ui(self._select_serial, addr)
            return True
        self.log("Connect failed: %s" % (msg or "no response"))
        if "10060" in msg or "timed out" in msg.lower() or "refused" in msg.lower():
            self.log("Hint: same Wi-Fi? Wireless debugging uses a new port each time — use Scan network "
                     "or the QR code, or USB → Wi-Fi with the cable plugged in.")
        return False

    def _select_serial(self, serial):
        label = self._label_of(serial)
        if label:
            self.dev_var.set(label)
            self._update_device_info()

    def disconnect(self):
        serial = self.selected()
        addr = serial if serial and self.devices.get(serial, {}).get("wifi") else self._norm_addr(self.addr_var.get())
        if not addr:
            return
        if addr in self.procs:
            self.stop_mirror(addr)

        def work():
            rc, out, err = self.adb_run("disconnect", addr)
            self.log((out + err).strip() or "Disconnected %s" % addr)
            self.refresh_devices()
        self.bg(work)

    def usb_to_wifi(self):
        serial = self.need_device()
        if not serial:
            return
        if self.devices[serial]["wifi"]:
            messagebox.showinfo(APP, "This phone is already on Wi-Fi.")
            return
        self.bg(self._usb_to_wifi, serial)

    def _usb_to_wifi(self, serial):
        ip = None
        for cmd in (["ip", "-f", "inet", "addr", "show", "wlan0"], ["ip", "route"]):
            rc, out, _ = self.adb_run("shell", *cmd, serial=serial, timeout=10)
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out) or re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
            if m:
                ip = m.group(1)
                break
        if not ip:
            self.log("The phone has no Wi-Fi IP. Connect it to Wi-Fi first.")
            return
        self.log("Phone Wi-Fi IP is %s. Switching adb to TCP port 5555..." % ip)
        pc_ips = local_ipv4s()
        if pc_ips and not any(p.rsplit(".", 1)[0] == ip.rsplit(".", 1)[0] for p in pc_ips):
            self.log("Warning: phone is on %s.x but this PC is on %s - they look like different "
                     "networks, so Wi-Fi may not connect. Put both on the same Wi-Fi/LAN."
                     % (ip.rsplit(".", 1)[0], ", ".join(pc_ips)))
        rc, out, err = self.adb_run("tcpip", "5555", serial=serial, timeout=20)
        self.log((out + err).strip())
        time.sleep(2)
        if self._connect(ip + ":5555"):
            self.log("You can unplug the USB cable now.")

    # ================================================================ network scan
    def scan(self):
        if getattr(self, "_scanning", False):
            self.scan_cancel.set()
            return
        m = re.match(r"\s*(\d+\.\d+\.\d+)\.\d+(?:/24)?\s*$", self.subnet_var.get())
        if not m:
            messagebox.showinfo(APP, "Enter a network like 192.168.1.0/24.")
            return
        self.scan_cancel.clear()
        self._scanning = True
        self.scan_btn.configure(text="Stop")
        self.tree.delete(*self.tree.get_children())
        self.scan_rows = {}
        self.bg(self._scan, m.group(1))

    def _scan(self, prefix):
        try:
            mine = set(local_ipv4s())
            ips = ["%s.%d" % (prefix, i) for i in range(1, 255)]
            status, done = {}, [0]
            lock = threading.Lock()

            def one(ip):
                if self.scan_cancel.is_set():
                    return
                status[ip] = tcp_probe(ip, 5555, 0.6)
                with lock:
                    done[0] += 1
                    if done[0] % 10 == 0:
                        self.ui(self._scan_progress, done[0] * 70 // len(ips), "Probing %s.x ..." % prefix)
            with ThreadPoolExecutor(max_workers=96) as pool:
                list(pool.map(one, ips))
            if self.scan_cancel.is_set():
                self.ui(self._scan_finish, "Scan stopped.")
                return
            self.ui(self._scan_progress, 75, "Reading neighbours and wireless debugging...")
            arp = {ip: mac for ip, mac in read_arp().items() if ip.startswith(prefix + ".")}
            svcs = [s for s in self.discover(2.0) if s["ip"].startswith(prefix + ".")]
            alive = sorted({ip for ip, s in status.items() if s} | set(arp) | {s["ip"] for s in svcs},
                           key=lambda ip: int(ip.rsplit(".", 1)[1]))
            self.ui(self._scan_progress, 85, "Looking up names...")
            names = resolve_names(alive)
            rows = []
            for ip in alive:
                name = names.get(ip, "")
                mac = arp.get(ip, "")
                adb = ""
                conn = [s for s in svcs if s["ip"] == ip and s["kind"] == "connect"]
                pair = [s for s in svcs if s["ip"] == ip and s["kind"] == "pair"]
                if status.get(ip) == "open":
                    adb = "Ready · port 5555"
                elif conn:
                    adb = "Wireless debugging · %s" % conn[0]["port"]
                elif pair:
                    adb = "Pairing screen · %s" % pair[0]["port"]
                if ip in mine:
                    hint = "This PC"
                elif adb:
                    hint = "Android phone"
                elif any(w in name.lower() for w in PHONE_WORDS):
                    hint = "Likely phone"
                elif is_vm_mac(mac):
                    hint = "Virtual machine"
                elif mac and is_random_mac(mac):
                    hint = "Possible phone (private MAC)"
                elif ip.endswith((".1", ".254")):
                    hint = "Router / gateway"
                else:
                    hint = "Device"
                rank = 0 if adb else 1 if "phone" in hint.lower() else 2
                rows.append((rank, ip, name.split(".")[0] if name else "—", hint, adb or "—",
                             conn[0]["port"] if conn else (5555 if adb.startswith("Ready") else None)))
            rows.sort(key=lambda r: (r[0], int(r[1].rsplit(".", 1)[1])))
            phones = sum(1 for r in rows if r[0] < 2)
            self.ui(self._scan_show, rows)
            self.ui(self._scan_finish, "%d devices found · %d look like phones. Double-click to connect." % (len(rows), phones))
        finally:
            self._scanning = False

    def _scan_progress(self, pct, text):
        self.scan_progress["value"] = pct
        self.scan_status.set(text)

    def _scan_show(self, rows):
        self.tree.delete(*self.tree.get_children())
        self.scan_rows = {}
        for rank, ip, name, hint, adb, port in rows:
            tag = "adb" if rank == 0 else "phone" if rank == 1 else ""
            iid = self.tree.insert("", "end", values=(ip, name, hint, adb), tags=(tag,))
            self.scan_rows[iid] = {"ip": ip, "port": port}

    def _scan_finish(self, text):
        self._scanning = False
        self.scan_btn.configure(text="Scan")
        self.scan_progress["value"] = 100
        self.scan_status.set(text)

    def _scan_pick(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP, "Pick a device in the list first.")
            return None
        return self.scan_rows.get(sel[0])

    def scan_connect(self):
        row = self._scan_pick()
        if not row:
            return
        if row["port"]:
            self.connect("%s:%s" % (row["ip"], row["port"]))
        else:
            self.scan_find_port(connect=True)

    def scan_find_port(self, connect=True):
        row = self._scan_pick()
        if not row:
            return
        ip = row["ip"]
        self.scan_cancel.clear()
        self.scan_status.set("Searching %s for an open adb port (5555, 30000-49999)..." % ip)

        def work():
            ports = [5555] + list(range(30000, 50000))
            open_ports = find_open_ports(
                ip, ports, cancel=self.scan_cancel,
                progress=lambda d, n: self.ui(self._scan_progress, d * 100 // n, "Checking ports on %s ... %d/%d" % (ip, d, n)))
            if not open_ports:
                self.ui(self._scan_progress, 100, "No adb port open on %s. Turn on Wireless debugging "
                                                  "(or USB → Wi-Fi) and try again." % ip)
                return
            self.ui(self._scan_progress, 100, "Open on %s: %s" % (ip, ", ".join(map(str, open_ports))))
            row["port"] = open_ports[0]
            if connect:
                for p in open_ports[:3]:
                    if self._connect("%s:%s" % (ip, p)):
                        return
                self.log("Port found but not connected — the phone may need pairing first (Wireless page).")
        self.bg(work)

    # ================================================================ actions
    def key(self, code):
        serial = self.need_device()
        if serial:
            self.bg(lambda: self.adb_run("shell", "input", "keyevent", code, serial=serial, timeout=10))

    def rotate(self):
        serial = self.need_device()
        if not serial:
            return

        def work():
            rc, out, _ = self.adb_run("shell", "settings", "get", "system", "user_rotation", serial=serial)
            cur = int(out.strip()) if out.strip().isdigit() else 0
            nxt = (cur + 1) % 4
            self.adb_run("shell", "settings put system accelerometer_rotation 0; "
                         "settings put system user_rotation %d" % nxt, serial=serial)
            self.log("Rotation set to %d degrees (auto-rotate off)." % (nxt * 90))
        self.bg(work)

    def screenshot(self):
        serial = self.need_device()
        if not serial:
            return

        def work():
            rc, data, err = self.adb_run("exec-out", "screencap", "-p", serial=serial, timeout=30, binary=True)
            if not data.startswith(b"\x89PNG"):
                self.log("Screenshot failed: %s" % (err.strip() or "no image"))
                return
            name = re.sub(r"[^\w.-]+", "_", self.devices.get(serial, {}).get("model") or "phone")
            path = os.path.join(self.out_dir(), "%s_%s.png" % (name, datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
            with open(path, "wb") as f:
                f.write(data)
            self.log("Screenshot saved: %s" % path)
            if IS_WIN:
                subprocess.Popen(["explorer", "/select,", path], creationflags=NO_WINDOW)
        self.bg(work)

    def send_text(self):
        text = self.text_var.get()
        if not text:
            return
        if any(ord(c) > 127 for c in text):
            messagebox.showinfo(APP, "adb can only type plain English (ASCII) characters.")
            return
        serial = self.need_device()
        if serial:
            self.bg(lambda: self.adb_run("shell", "input", "text", shell_escape_text(text), serial=serial))
            self.text_var.set("")

    def install_dialog(self):
        paths = filedialog.askopenfilenames(title="Choose APK", filetypes=[("Android app", "*.apk")])
        if paths:
            self.install(list(paths))

    def on_drop(self, files):
        apks = [f for f in files if f.lower().endswith(".apk")]
        if not apks:
            self.log("Only .apk files can be dropped here.")
            return
        self.install(apks)

    def install(self, apks):
        serial = self.need_device()
        if not serial:
            return

        def work():
            for apk in apks:
                self.log("Installing %s ..." % os.path.basename(apk))
                rc, out, err = self.adb_run("install", "-r", apk, serial=serial, timeout=300)
                msg = (out + err).strip().splitlines()
                self.log("Install %s: %s" % ("OK" if rc == 0 and "Success" in out else "FAILED",
                                             msg[-1] if msg else "rc=%s" % rc))
        self.bg(work)

    # ================================================================ settings
    def pick_adb(self):
        p = filedialog.askopenfilename(title="Choose adb.exe", filetypes=[("adb", "adb.exe"), ("Programs", "*.exe")])
        if p:
            self.adb_path_var.set(p)

    def apply_adb(self):
        self._set_cfg("adb_path", self.adb_path_var.get().strip())
        self.bg(self._detect_adb)

    def pick_out(self):
        d = filedialog.askdirectory(title="Folder for screenshots and recordings")
        if d:
            self.out_var.set(d)
            self._set_cfg("out_dir", d)

    def open_path(self, path):
        if IS_WIN:
            os.startfile(path)

    def on_close(self):
        self.cfg["out_dir"] = self.out_var.get().strip() or DEFAULTS["out_dir"]
        save_config(self.cfg)
        if self.procs and not messagebox.askyesno(APP, "Stop mirroring and quit?"):
            return
        self.closing = True
        self.dev_close()
        self.scan_cancel.set()
        self.qr_token += 1
        self.qr_progress.stop()
        for entry in list(self.procs.values()):
            entry["user_stop"] = True
            kill_tree(entry["proc"])
        for serial in list(self.remotes):
            self._close_remote(serial)
        for rec in list(self.recorders.values()):
            rec.stop()  # posts WM_CLOSE now; scrcpy finishes writing the file on its own
        if self.adb and _is_bundled(self.adb):
            # our adb server runs from the exe's temp folder; stop it so the folder
            # can be cleaned up. A system adb's server is left alone (other tools use it).
            run([self.adb, "kill-server"], timeout=10)
        self.root.destroy()


def main():
    if IS_WIN:
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:  # our own taskbar identity: Mirror's icon and grouping, not python's / a generic one
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mirror.PhoneMirror.App")
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
