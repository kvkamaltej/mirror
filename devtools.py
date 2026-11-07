"""Developer pages for Mirror: Logcat, Shell, Apps and Device.

A mixin for mirror.App. It only uses what App provides (adb_run, popen_adb,
kill_proc, bg, ui, log, card, wrap_label, need_device, selected, cfg, pal,
fonts), so it has no import of mirror.pyw itself.
"""
import base64
import collections
import datetime
import json
import os
import re
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------- pure helpers (unit-tested)
LEVELS = [("Verbose", "V"), ("Debug", "D"), ("Info", "I"), ("Warning", "W"), ("Error", "E"), ("Fatal", "F")]
BUFFERS = [("Default", ""), ("Main", "main"), ("System", "system"), ("Crash", "crash"), ("Events", "events"),
           ("Radio", "radio"), ("All", "all")]
LINE_RE = re.compile(r"^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+)\s+([VDIWEFA])\s")
TAG_RE = re.compile(r"^[\w.$\-]{1,64}$")
PKG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:\S+$")


def sh_quote(s):
    """Quote one word for the phone's /system/bin/sh (adb shell joins words with spaces)."""
    return "'" + s.replace("'", "'\\''") + "'"


def parse_line(line):
    """(pid, level) of a `logcat -v threadtime` line, or (None, None)."""
    m = LINE_RE.match(line)
    return (int(m.group(1)), m.group(3)) if m else (None, None)


def logcat_args(level="V", buffer="", tags="", regex="", tail=500):
    """adb arguments after `-s SERIAL` for a filtered logcat stream."""
    if level not in "VDIWEF" or len(level) != 1:
        raise ValueError("bad level")
    args = ["logcat", "-v", "threadtime"]
    if tail:
        args += ["-T", str(int(tail))]
    if buffer:
        if buffer not in dict((b, 1) for _, b in BUFFERS):
            raise ValueError("bad buffer")
        args += ["-b", buffer]
    if regex:
        if len(regex) > 200 or "\n" in regex:
            raise ValueError("regex too long")
        # no quoting here: these args go to `adb logcat`, which quotes each argument for the
        # phone's shell itself (unlike `adb shell CMD`); extra quotes would become part of the regex
        args += ["-e", regex]
    tag_list = [t.strip() for t in tags.replace(";", ",").split(",") if t.strip()]
    for t in tag_list:
        if not TAG_RE.match(t):
            raise ValueError("tag %r: use letters, digits and . _ $ -" % t)
    if tag_list:
        args += ["%s:%s" % (t, level) for t in tag_list] + ["*:S"]
    else:
        args.append("*:" + level)
    return args


def parse_packages(out):
    """`pm list packages [-3] --show-versioncode` -> [(package, versionCode)]."""
    pkgs = []
    for line in out.splitlines():
        m = re.match(r"package:(\S+?)(?:\s+versionCode:(\d+))?\s*$", line.strip())
        if m and PKG_RE.match(m.group(1)):
            pkgs.append((m.group(1), m.group(2) or ""))
    return sorted(pkgs)


def parse_forward_list(out):
    """`adb forward|reverse --list` -> [(serial-or-host, local, remote)]."""
    rows = []
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 3 and f[1].startswith(("tcp:", "localabstract:")):
            rows.append((f[0], f[1], f[2]))
    return rows


def parse_package_details(out):
    keys = {"versionName": None, "versionCode": None, "targetSdk": None, "minSdk": None,
            "firstInstallTime": None, "lastUpdateTime": None}
    for k in keys:
        m = re.search(r"\b%s=(\S+)" % k, out)
        if m:
            keys[k] = m.group(1)
    if keys["firstInstallTime"]:  # "2026-11-04 12:00:00" is split by the \S+ above
        m = re.search(r"firstInstallTime=([\d\- :]+)", out)
        keys["firstInstallTime"] = m.group(1).strip() if m else keys["firstInstallTime"]
    if keys["lastUpdateTime"]:
        m = re.search(r"lastUpdateTime=([\d\- :]+)", out)
        keys["lastUpdateTime"] = m.group(1).strip() if m else keys["lastUpdateTime"]
    return keys


SHELL_TIMEOUT = 120  # seconds; longer jobs belong in the terminal
ICON_PX = 24         # app icon size in the Apps list
HELPER_REMOTE = "/data/local/tmp/mirror-helper.dex"

SHELL_PRESETS = [
    "getprop ro.build.version.release",
    "pm list packages -3",
    "dumpsys battery",
    "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'",
    "df -h /data",
    "free -m",
    "top -n 1 -b | head -20",
    "ip -f inet addr show wlan0",
    "wm size; wm density",
    "settings list global",
    "logcat -d -b crash -t 50",
    "dumpsys meminfo PACKAGE",
    "run-as PACKAGE ls files",
]

# (key, label, read command, on command, off command, is-on test)
DEV_TOGGLES = [
    ("taps", "Show taps", "settings get system show_touches",
     "settings put system show_touches 1", "settings put system show_touches 0", lambda o: o.strip() == "1"),
    ("pointer", "Pointer location", "settings get system pointer_location",
     "settings put system pointer_location 1", "settings put system pointer_location 0", lambda o: o.strip() == "1"),
    ("bounds", "Layout bounds", "getprop debug.layout",
     "setprop debug.layout true; service call activity 1599295570 > /dev/null",
     "setprop debug.layout false; service call activity 1599295570 > /dev/null", lambda o: o.strip() == "true"),
    ("noanim", "Animations off", "settings get global window_animation_scale",
     "settings put global window_animation_scale 0; settings put global transition_animation_scale 0; "
     "settings put global animator_duration_scale 0",
     "settings put global window_animation_scale 1; settings put global transition_animation_scale 1; "
     "settings put global animator_duration_scale 1", lambda o: o.strip() in ("0", "0.0")),
    ("dark", "Dark mode", "cmd uimode night", "cmd uimode night yes", "cmd uimode night no",
     lambda o: "yes" in o.lower()),
    ("bigfont", "Large text (130%)", "settings get system font_scale",
     "settings put system font_scale 1.3", "settings put system font_scale 1.0",
     lambda o: o.strip() not in ("", "1", "1.0", "null")),
]

LOG_COLORS = {  # level -> (dark theme, light theme)
    "V": ("#9d9d9d", "#6b6b6b"), "D": ("#6cb6ff", "#0b5cad"), "I": ("#6ccb5f", "#0f7b0f"),
    "W": ("#fce100", "#9d5d00"), "E": ("#ff6b6b", "#c42b1c"), "F": ("#ff6b6b", "#c42b1c"),
    "A": ("#ff6b6b", "#c42b1c"), "S": ("#c586c0", "#8a2be2"),
}


class DevToolsMixin:
    """Logcat / Shell / Apps / Device pages."""

    # ============================================================ shared
    def _dev_init(self):
        self.lc_proc = None
        self.lc_lines = collections.deque(maxlen=20000)
        self.lc_pending = collections.deque()
        self.lc_state = {"pids": None}  # current stream's app filter (pids of the followed app)
        self.lc_paused = False
        self.lc_serial = None
        self.sh_proc = None
        self.sh_hist = list(self.cfg.get("shell_history", []))
        self.sh_hist_pos = None
        self.adb_stopped = False
        self.apps = []
        self.app_labels = {}       # package -> app name (from the phone)
        self.icon_imgs = {}        # (package, versionCode) -> PhotoImage (kept alive here)
        self.helper_pushed = set() # serials that already have mirror-helper.dex

    def mono_text(self, parent, height=10):
        box = ttk.Frame(parent)
        t = tk.Text(box, height=height, wrap="none", font=("Consolas", 9), relief="flat", borderwidth=0,
                    padx=8, pady=6, undo=False)
        ys = ttk.Scrollbar(box, orient="vertical", command=t.yview)
        xs = ttk.Scrollbar(box, orient="horizontal", command=t.xview)
        t.configure(yscrollcommand=ys.set, xscrollcommand=xs.set, state="disabled")
        t.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.dev_texts.append(t)
        return box, t

    def dev_theme(self):
        """Colours for the text panes (called from apply_theme)."""
        dark = bool(self.pal.get("dark"))
        mono = getattr(self, "mono", "Consolas")
        skin_log = getattr(self, "skin", {}).get("logcolors", {})  # e.g. Hacker: shades of green
        for t in getattr(self, "dev_texts", []):
            t.configure(bg=self.pal["field"], fg=self.pal["fg"], insertbackground=self.pal["fg"],
                        selectbackground=self.pal["accent"], font=(mono, 9))
            for lvl, (d, l) in LOG_COLORS.items():
                t.tag_configure("L" + lvl, foreground=skin_log.get(lvl) or (d if dark else l))
            t.tag_configure("cmd", foreground=self.pal["accent"], font=(mono, 9, "bold"))
            t.tag_configure("meta", foreground=self.pal["muted"])
            t.tag_configure("find", background="#7a5c00" if dark else "#fff3b0")
        for lb in getattr(self, "dev_lists", []):
            lb.configure(bg=self.pal["field"], fg=self.pal["fg"], selectbackground=self.pal["accent"],
                         selectforeground="#ffffff")

    @staticmethod
    def text_append(t, chunks, limit=20000):
        """chunks: [(text, tag)]; keeps the view at the bottom only if it was there."""
        at_end = t.yview()[1] > 0.999
        t.configure(state="normal")
        for s, tag in chunks:
            t.insert("end", s, tag)
        n = int(t.index("end-1c").split(".")[0])
        if n > limit:
            t.delete("1.0", "%d.0" % (n - limit + 1000))
        t.configure(state="disabled")
        if at_end:
            t.see("end")

    @staticmethod
    def text_clear(t):
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")

    def dev_serial(self):
        """Selected ready phone, or None (shows a message)."""
        if self.adb_stopped:
            messagebox.showinfo(self.APP_NAME, "The adb server is stopped. Start it on the Device page.")
            return None
        return self.need_device()

    # ============================================================ Logcat page
    def _page_logcat(self, parent):
        f = ttk.Frame(parent)
        r1 = ttk.Frame(f)
        r1.pack(fill="x", pady=(0, 6))
        ttk.Label(r1, text="Level").pack(side="left")
        self.lc_level = tk.StringVar(value=self.cfg.get("lc_level", "Verbose"))
        ttk.Combobox(r1, textvariable=self.lc_level, values=[n for n, _ in LEVELS], state="readonly",
                     width=9).pack(side="left", padx=(4, 10))
        ttk.Label(r1, text="Buffer").pack(side="left")
        self.lc_buffer = tk.StringVar(value="Default")
        ttk.Combobox(r1, textvariable=self.lc_buffer, values=[n for n, _ in BUFFERS], state="readonly",
                     width=8).pack(side="left", padx=(4, 10))
        ttk.Label(r1, text="App").pack(side="left")
        self.lc_pkg = tk.StringVar(value=self.cfg.get("lc_pkg", ""))
        self.lc_pkg_box = ttk.Combobox(r1, textvariable=self.lc_pkg)
        self.lc_pkg_box.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.lc_pkg_box.bind("<Button-1>", lambda e: self._fill_pkg_choices())

        r2 = ttk.Frame(f)
        r2.pack(fill="x", pady=(0, 6))
        ttk.Label(r2, text="Tags").pack(side="left")
        self.lc_tags = tk.StringVar(value=self.cfg.get("lc_tags", ""))
        ttk.Entry(r2, textvariable=self.lc_tags, width=18).pack(side="left", padx=(4, 10))
        ttk.Label(r2, text="Regex").pack(side="left")
        self.lc_regex = tk.StringVar(value=self.cfg.get("lc_regex", ""))
        ttk.Entry(r2, textvariable=self.lc_regex, width=18).pack(side="left", padx=(4, 10))
        ttk.Label(r2, text="Find").pack(side="left")
        self.lc_find = tk.StringVar()
        ttk.Entry(r2, textvariable=self.lc_find).pack(side="left", padx=(4, 0), fill="x", expand=True)
        self.lc_find.trace_add("write", lambda *_: self.lc_rerender())

        r3 = ttk.Frame(f)
        r3.pack(fill="x", pady=(0, 6))
        self.lc_btn = ttk.Button(r3, text="Start", style="Accent.TButton", command=self.lc_toggle)
        self.lc_btn.pack(side="left")
        self.lc_pause_btn = ttk.Button(r3, text="Pause", command=self.lc_pause)
        self.lc_pause_btn.pack(side="left", padx=(6, 0))
        ttk.Button(r3, text="Clear view", command=self.lc_clear_view).pack(side="left", padx=(6, 0))
        ttk.Button(r3, text="Clear phone log", command=self.lc_clear_device).pack(side="left", padx=(6, 0))
        ttk.Button(r3, text="Save…", command=self.lc_save).pack(side="left", padx=(6, 0))

        box, self.lc_text = self.mono_text(f, height=14)
        box.pack(fill="both", expand=True)
        self.lc_status = tk.StringVar(value="Pick filters and press Start. Tags: comma-separated, e.g. "
                                            "ActivityManager, flutter. App: follows the app across restarts.")
        ttk.Label(f, textvariable=self.lc_status, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.root.after(150, self._lc_pump)
        return f

    def _fill_pkg_choices(self):
        if self.apps:
            self.lc_pkg_box["values"] = [p for p, _ in self.apps]
        else:
            serial = self.selected()
            if serial and not self.adb_stopped:
                def work():
                    rc, out, _ = self.adb_run("shell", "pm", "list", "packages", "-3", serial=serial, timeout=20)
                    pk = [p for p, _ in parse_packages(out)]
                    self.ui(lambda: self.lc_pkg_box.configure(values=pk))
                self.bg(work)

    def lc_toggle(self):
        if self.lc_proc:
            self.lc_stop()
        else:
            self.lc_start()

    def lc_start(self, serial=None):
        serial = serial or self.dev_serial()
        if not serial:
            return
        level = dict(LEVELS)[self.lc_level.get()]
        buf = dict(BUFFERS)[self.lc_buffer.get()]
        pkg = self.lc_pkg.get().strip()
        if pkg and not PKG_RE.match(pkg):
            messagebox.showinfo(self.APP_NAME, "App must be a package name like com.example.app")
            return
        try:
            args = logcat_args(level, buf, self.lc_tags.get(), self.lc_regex.get().strip())
        except ValueError as e:
            messagebox.showinfo(self.APP_NAME, "Logcat filter: %s" % e)
            return
        for k, v in (("lc_level", self.lc_level.get()), ("lc_pkg", pkg), ("lc_tags", self.lc_tags.get()),
                     ("lc_regex", self.lc_regex.get())):
            self.cfg[k] = v
        self._set_cfg("lc_level", self.lc_level.get())
        self.lc_serial = serial
        self.lc_pkg_now = pkg
        try:
            proc = self.popen_adb(*args, serial=serial)
        except OSError as e:
            self.log("Logcat failed to start: %s" % e)
            return
        # Per-stream state: a stopped stream's threads can still be finishing, and
        # must never touch the new stream's app filter or queue.
        state = {"pids": set() if pkg else None}
        self.lc_state = state
        self.lc_pending.clear()
        self.lc_proc = proc
        self.lc_btn.configure(text="Stop")
        self._lc_meta("logcat started: %s" % " ".join(args[3:]))
        self.bg(self._lc_read, proc, state)
        if pkg:
            self.bg(self._lc_follow, proc, state, serial, pkg)

    def lc_stop(self):
        p, self.lc_proc = self.lc_proc, None
        if p:
            self.kill_proc(p)
            self._lc_meta("logcat stopped")
        self.lc_btn.configure(text="Start")

    def _lc_read(self, proc, state):
        for raw in iter(proc.stdout.readline, b""):
            if proc is not self.lc_proc:
                break
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                continue
            if line.startswith("--------- "):  # logcat's own "beginning of main" markers
                if state["pids"] is None and proc is self.lc_proc:
                    self.lc_pending.append(("S", line))
                continue
            pid, level = parse_line(line)
            pids = state["pids"]
            if pids is not None and (pid is None or pid not in pids):
                continue
            if proc is self.lc_proc:
                self.lc_pending.append((level or "V", line))
        rc = proc.wait()
        if proc is self.lc_proc:  # ended by itself (phone unplugged, bad regex, ...)
            self.lc_proc = None
            self.ui(lambda: (self.lc_btn.configure(text="Start"),
                             self._lc_meta("logcat ended (exit %s)" % rc)))

    def _lc_follow(self, proc, state, serial, pkg):
        """Keep the set of pids of pkg current, so the filter survives app restarts."""
        last = None
        while proc is self.lc_proc:
            rc, out, _ = self.adb_run("shell", "pidof", pkg, serial=serial, timeout=10)
            if proc is not self.lc_proc:
                break  # stream stopped while pidof ran
            pids = {int(x) for x in out.split() if x.isdigit()}
            state["pids"] = pids
            if pids != last:
                if not pids:
                    self.ui(self._lc_meta, "%s is not running — waiting for it to start" % pkg)
                else:
                    self.ui(self._lc_meta, "%s running (pid %s)" % (pkg, ", ".join(map(str, sorted(pids)))))
                last = pids
            time.sleep(2)

    def _lc_meta(self, msg):
        line = "--- %s %s ---" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
        self.lc_lines.append(("S", line))
        if self.lc_matches(line):
            self.text_append(self.lc_text, [(line + "\n", "meta")])

    def lc_matches(self, line):
        q = self.lc_find.get()
        return not q or q.lower() in line.lower()

    def _lc_pump(self):
        if self.closing:
            return
        if self.lc_pending:
            batch = []
            while self.lc_pending and len(batch) < 3000:
                batch.append(self.lc_pending.popleft())
            self.lc_lines.extend(batch)
            if not self.lc_paused:
                chunks = [(t + "\n", "L" + lvl) for lvl, t in batch if self.lc_matches(t)]
                if chunks:
                    self.text_append(self.lc_text, chunks)
        if self.lc_proc or self.lc_lines:
            state = "paused" if self.lc_paused else ("running" if self.lc_proc else "stopped")
            follow = " · following %s" % self.lc_pkg_now if self.lc_proc and getattr(self, "lc_pkg_now", "") else ""
            self.lc_status.set("%s · %d lines kept%s" % (state, len(self.lc_lines), follow))
        self.root.after(150, self._lc_pump)

    def lc_rerender(self):
        self.text_clear(self.lc_text)
        chunks = [(t + "\n", "meta" if lvl == "S" else "L" + lvl) for lvl, t in self.lc_lines if self.lc_matches(t)]
        self.text_append(self.lc_text, chunks[-20000:])
        q = self.lc_find.get()
        if q:
            idx = "1.0"
            for _ in range(2000):
                idx = self.lc_text.search(q, idx, nocase=True, stopindex="end")
                if not idx:
                    break
                end = "%s+%dc" % (idx, len(q))
                self.lc_text.tag_add("find", idx, end)
                idx = end

    def lc_pause(self):
        self.lc_paused = not self.lc_paused
        self.lc_pause_btn.configure(text="Resume" if self.lc_paused else "Pause")
        if not self.lc_paused:
            self.lc_rerender()

    def lc_clear_view(self):
        self.lc_lines.clear()
        self.lc_pending.clear()
        self.text_clear(self.lc_text)

    def lc_clear_device(self):
        serial = self.dev_serial()
        if serial:
            self.bg(lambda: (self.adb_run("logcat", "-c", serial=serial, timeout=15),
                             self.ui(self._lc_meta, "phone log buffer cleared")))

    def lc_save(self):
        if not self.lc_lines:
            messagebox.showinfo(self.APP_NAME, "Nothing to save yet.")
            return
        name = "logcat_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(title="Save logcat", initialdir=self.out_dir(), initialfile=name,
                                            defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(t for _, t in self.lc_lines if self.lc_matches(t)) + "\n")
            self.log("Logcat saved: %s" % path)

    def logcat_for(self, pkg):
        """Apps page → Logcat filtered to one app."""
        self.lc_pkg.set(pkg)
        if self.lc_proc:
            self.lc_stop()
        self.show_page("logcat")
        self.lc_start()

    # ============================================================ Shell page
    def _page_shell(self, parent):
        f = ttk.Frame(parent)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(0, 6))
        ttk.Label(r, text="adb shell").pack(side="left")
        self.sh_cmd = tk.StringVar()
        self.sh_entry = ttk.Combobox(r, textvariable=self.sh_cmd, values=SHELL_PRESETS, font=("Consolas", 10))
        self.sh_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.sh_entry.bind("<Return>", lambda e: self.sh_run())
        self.sh_entry.bind("<Up>", lambda e: self._sh_hist(-1))
        self.sh_entry.bind("<Down>", lambda e: self._sh_hist(1))
        self.sh_btn = ttk.Button(r, text="Run", style="Accent.TButton", command=self.sh_run)
        self.sh_btn.pack(side="left")
        ttk.Button(r, text="Clear", command=lambda: self.text_clear(self.sh_text)).pack(side="left", padx=(6, 0))
        r2 = ttk.Frame(f)
        r2.pack(fill="x", pady=(0, 6))
        self.wrap_label(r2, text="One command at a time; output streams in. Up/Down = history; the list has common "
                                 "commands (replace PACKAGE). Interactive programs (vi, top without -n) need the "
                                 "terminal.", style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="Open adb shell in a terminal", command=lambda: self.open_terminal(shell=True)).pack(side="right")
        box, self.sh_text = self.mono_text(f, height=16)
        box.pack(fill="both", expand=True)
        return f

    def _sh_hist(self, step):
        if not self.sh_hist:
            return "break"
        pos = len(self.sh_hist) if self.sh_hist_pos is None else self.sh_hist_pos
        pos = max(0, min(len(self.sh_hist), pos + step))
        self.sh_hist_pos = pos
        self.sh_cmd.set(self.sh_hist[pos] if pos < len(self.sh_hist) else "")
        self.sh_entry.icursor("end")
        return "break"

    def sh_run(self):
        if self.sh_proc:  # Stop
            p, self.sh_proc = self.sh_proc, None
            self.kill_proc(p)
            self.text_append(self.sh_text, [("^C stopped\n", "meta")])
            self.sh_btn.configure(text="Run")
            return
        cmd = self.sh_cmd.get().strip()
        if not cmd:
            return
        if "PACKAGE" in cmd:
            messagebox.showinfo(self.APP_NAME, "Replace PACKAGE with an app's package name (see the Apps page).")
            return
        serial = self.dev_serial()
        if not serial:
            return
        self.sh_hist = [h for h in self.sh_hist if h != cmd] + [cmd]
        self.sh_hist_pos = None
        self._set_cfg("shell_history", self.sh_hist[-50:])
        self.sh_cmd.set("")
        self.text_append(self.sh_text, [("$ %s\n" % cmd, "cmd")])
        try:
            proc = self.popen_adb("shell", cmd, serial=serial)
        except OSError as e:
            self.text_append(self.sh_text, [("%s\n" % e, "LE")])
            return
        self.sh_proc = proc
        self.sh_btn.configure(text="Stop")
        self.bg(self._sh_read, proc, time.time())

        def watchdog():  # a command that hangs without printing anything still ends
            if proc.poll() is None and self.sh_proc is proc:
                self.kill_proc(proc)
                self.text_append(self.sh_text, [("... stopped after %d s (use the terminal for long-running "
                                                 "commands)\n" % SHELL_TIMEOUT, "meta")])
        self.root.after(SHELL_TIMEOUT * 1000, watchdog)

    def _sh_read(self, proc, t0):
        buf, last, total = [], time.time(), 0
        for raw in iter(proc.stdout.readline, b""):
            total += len(raw)
            if total > 2_000_000:
                self.kill_proc(proc)
                buf.append(("... output stopped at 2 MB\n", "meta"))
                break
            buf.append((raw.decode("utf-8", "replace").replace("\r\n", "\n"), None))
            if time.time() - last > 0.15:
                self.ui(self.text_append, self.sh_text, buf, 50000)
                buf, last = [], time.time()
        rc = proc.wait()
        buf.append(("[exit %s · %.1f s]\n" % (rc, time.time() - t0), "meta"))
        self.ui(self.text_append, self.sh_text, buf, 50000)

        def done():
            if self.sh_proc is proc:
                self.sh_proc = None
                self.sh_btn.configure(text="Run")
        self.ui(done)

    def open_terminal(self, shell=False):
        """A console window with adb on PATH (and ANDROID_SERIAL set to the selected phone)."""
        serial = self.selected() if shell else self.selected()
        env = dict(os.environ)
        env["PATH"] = os.path.dirname(self.adb) + os.pathsep + env.get("PATH", "")
        banner = "echo adb is ready (%s)." % self.adb
        if serial:
            env["ANDROID_SERIAL"] = serial
            banner += " Every adb command here goes to %s." % serial
        cmd = banner + (" & adb shell" if shell and serial else "")
        try:
            subprocess.Popen(["cmd.exe", "/K", cmd], env=env, cwd=os.path.dirname(self.adb),
                             creationflags=0x00000010)  # CREATE_NEW_CONSOLE
        except OSError as e:
            self.log("Could not open a terminal: %s" % e)

    # ============================================================ Apps page
    def _page_apps(self, parent):
        f = ttk.Frame(parent)
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(0, 6))
        ttk.Label(r, text="Search").pack(side="left")
        self.app_q = tk.StringVar()
        ttk.Entry(r, textvariable=self.app_q, width=24).pack(side="left", padx=6)
        self.app_q.trace_add("write", lambda *_: self._apps_show())
        self.app_sys = tk.BooleanVar(value=False)
        ttk.Checkbutton(r, text="System apps too", variable=self.app_sys, style="Switch.TCheckbutton",
                        command=self.apps_refresh).pack(side="left", padx=8)
        ttk.Button(r, text="Refresh", command=self.apps_refresh).pack(side="left")
        ttk.Button(r, text="Install APK…", command=self.install_dialog).pack(side="right")

        box = ttk.Frame(f)
        box.pack(fill="both", expand=True)
        self.app_tree = ttk.Treeview(box, columns=("pkg", "ver"), show="tree headings", height=9, selectmode="browse",
                                     style="Apps.Treeview")
        self.app_tree.heading("#0", text="App", anchor="w")
        self.app_tree.heading("pkg", text="Package", anchor="w")
        self.app_tree.heading("ver", text="Version code", anchor="w")
        self.app_tree.column("#0", width=230, anchor="w")
        self.app_tree.column("pkg", width=280, anchor="w")
        self.app_tree.column("ver", width=100, anchor="w")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=sb.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.app_tree.bind("<<TreeviewSelect>>", lambda e: self.app_details())
        self.app_tree.bind("<Double-1>", lambda e: self.app_action("launch"))

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(8, 4))
        for text, act in (("Launch", "launch"), ("Force stop", "stop"), ("Logcat for app", "logcat"),
                          ("App info on phone", "settings"), ("Clear data…", "clear"), ("Uninstall…", "uninstall")):
            ttk.Button(b, text=text, command=lambda a=act: self.app_action(a),
                       style="Accent.TButton" if act == "launch" else "TButton").pack(side="left", padx=(0, 6))
        self.app_info = tk.StringVar(value="Select an app to see its details.")
        self.wrap_label(f, textvariable=self.app_info, style="Muted.TLabel").pack(fill="x")
        return f

    def apps_refresh(self):
        serial = self.dev_serial()
        if not serial:
            return
        self.app_info.set("Loading apps…")

        def work():
            args = ["shell", "pm", "list", "packages", "--show-versioncode"] + ([] if self.app_sys.get() else ["-3"])
            rc, out, err = self.adb_run(*args, serial=serial, timeout=40)
            if "versionCode" not in out:  # Android 8 and older: no --show-versioncode
                rc, out, err = self.adb_run(*[a for a in args if a != "--show-versioncode"], serial=serial, timeout=40)
            self.apps = parse_packages(out)
            self.ui(self._apps_show)
            self.ui(self.app_info.set, "%d apps. Double-click to launch." % len(self.apps))
            self._icons_load(serial, list(self.apps))
        self.bg(work)

    def _apps_show(self):
        q = self.app_q.get().strip().lower()
        self.app_tree.delete(*self.app_tree.get_children())
        apps = sorted(self.apps, key=lambda a: (self.app_labels.get(a[0]) or a[0]).lower())
        for pkg, ver in apps:
            label = self.app_labels.get(pkg, "")
            if q and q not in pkg.lower() and q not in label.lower():
                continue
            img = self.icon_imgs.get((pkg, ver))
            kw = {"image": img} if img else {}
            self.app_tree.insert("", "end", iid=pkg, text="  " + (label or pkg.rsplit(".", 1)[-1]),
                                 values=(pkg, ver), **kw)

    # ---- app icons: drawn on the phone by assets/mirror-helper.dex (android-helper/), cached per version
    def _icon_cache_dir(self):
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), self.APP_NAME, "icons")
        os.makedirs(d, exist_ok=True)
        return d

    def _icons_load(self, serial, apps):
        """Background: show cached icons, fetch the missing ones from the phone in batches."""
        cache = self._icon_cache_dir()
        labels_file = os.path.join(cache, "labels.json")
        try:
            with open(labels_file, encoding="utf-8") as fh:
                disk_labels = json.load(fh)
        except (OSError, ValueError):
            disk_labels = {}
        missing = []
        for pkg, ver in apps:
            key = "%s_%s" % (pkg, ver or "0")
            png = os.path.join(cache, key + ".png")
            if os.path.isfile(png) and key in disk_labels:
                self.ui(self._icon_set, pkg, ver, png, disk_labels[key])
            else:
                missing.append((pkg, ver))
        if not missing:
            self.ui(self._apps_resort)
            return
        helper = self.asset_path("mirror-helper.dex")
        if serial not in self.helper_pushed:
            rc, out, err = self.adb_run("push", helper, HELPER_REMOTE, serial=serial, timeout=30)
            if rc != 0:
                self.log("App icons unavailable: could not copy the helper to the phone (%s)" % (out + err).strip()[-120:])
                return
            self.helper_pushed.add(serial)
        vers = dict(missing)
        for i in range(0, len(missing), 40):
            batch = [p for p, _ in missing[i:i + 40]]
            rc, out, err = self.adb_run("shell", "CLASSPATH=%s app_process / com.mirror.IconDump %d %s"
                                        % (HELPER_REMOTE, ICON_PX, " ".join(batch)), serial=serial, timeout=60)
            got = 0
            for line in out.splitlines():
                f = line.rstrip("\r").split("\t")
                if len(f) != 3 or f[1] == "!" or f[0] not in vers:
                    continue
                try:
                    data = base64.b64decode(f[2])
                except ValueError:
                    continue
                key = "%s_%s" % (f[0], vers[f[0]] or "0")
                png = os.path.join(cache, key + ".png")
                with open(png, "wb") as fh:
                    fh.write(data)
                disk_labels[key] = f[1]
                self.ui(self._icon_set, f[0], vers[f[0]], png, f[1])
                got += 1
            if not got and i == 0:
                self.log("App icons unavailable on this phone: %s" % (err or out).strip()[-160:])
                break
        try:
            with open(labels_file, "w", encoding="utf-8") as fh:
                json.dump(disk_labels, fh)
        except OSError:
            pass
        self.ui(self._apps_resort)

    def _apps_resort(self):
        """Names have arrived: re-sort the list by name, keeping the selection."""
        sel = self._app_selected()
        self._apps_show()
        if sel and self.app_tree.exists(sel):
            self.app_tree.selection_set(sel)
            self.app_tree.see(sel)

    def _icon_set(self, pkg, ver, png, label):
        try:
            img = tk.PhotoImage(file=png)
        except tk.TclError:
            return
        self.icon_imgs[(pkg, ver)] = img
        self.app_labels[pkg] = label
        if self.app_tree.exists(pkg):
            self.app_tree.item(pkg, image=img, text="  " + label)
        elif not self.app_q.get().strip():
            pass

    def _app_selected(self):
        sel = self.app_tree.selection()
        return sel[0] if sel else None

    def app_details(self):
        pkg, serial = self._app_selected(), self.selected()
        if not pkg or not serial:
            return

        def work():
            rc, out, _ = self.adb_run("shell", "dumpsys package %s | grep -E "
                                      "'versionName|versionCode|targetSdk|minSdk|firstInstallTime|lastUpdateTime'"
                                      % sh_quote(pkg), serial=serial, timeout=20)
            d = parse_package_details(out)
            rc2, pid, _ = self.adb_run("shell", "pidof", pkg, serial=serial, timeout=10)
            parts = ["%s" % pkg]
            if d["versionName"]:
                parts.append("version %s (%s)" % (d["versionName"], d["versionCode"] or "?"))
            if d["targetSdk"]:
                parts.append("targets SDK %s, min %s" % (d["targetSdk"], d["minSdk"] or "?"))
            if d["lastUpdateTime"]:
                parts.append("updated %s" % d["lastUpdateTime"])
            parts.append("running (pid %s)" % pid.strip() if pid.strip() else "not running")
            if self._app_selected() == pkg:
                self.ui(self.app_info.set, "  ·  ".join(parts))
        self.bg(work)

    def app_action(self, act):
        pkg = self._app_selected()
        if not pkg:
            messagebox.showinfo(self.APP_NAME, "Select an app first (press Refresh to list them).")
            return
        serial = self.dev_serial()
        if not serial:
            return
        if act == "logcat":
            self.logcat_for(pkg)
            return
        if act == "clear" and not messagebox.askyesno(
                self.APP_NAME, "Clear all data of %s?\n\nIts files, databases, settings and logins on the phone "
                               "are deleted. This cannot be undone." % pkg, icon="warning"):
            return
        if act == "uninstall" and not messagebox.askyesno(
                self.APP_NAME, "Uninstall %s from the phone?\n\nThe app and its data are removed." % pkg,
                icon="warning"):
            return
        cmds = {
            "launch": ("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"),
            "stop": ("shell", "am", "force-stop", pkg),
            "clear": ("shell", "pm", "clear", pkg),
            "uninstall": ("uninstall", pkg),
            "settings": ("shell", "am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS",
                         "-d", "package:" + pkg),
        }

        def work():
            rc, out, err = self.adb_run(*cmds[act], serial=serial, timeout=60)
            msg = (out + err).strip()
            ok = rc == 0 and "Exception" not in msg and "Failure" not in msg and "No activities" not in msg
            label = {"launch": "Launched", "stop": "Stopped", "clear": "Cleared data of", "uninstall": "Uninstalled",
                     "settings": "Opened app info for"}[act]
            self.log("%s %s" % (label, pkg) if ok else "%s failed: %s" % (act, msg.splitlines()[-1] if msg else rc))
            if act == "uninstall" and ok:
                self.apps = [a for a in self.apps if a[0] != pkg]
                self.ui(self._apps_show)
            self.ui(self.app_details)
        self.bg(work)

    # ============================================================ Device page
    def _page_device(self, parent):
        f = ttk.Frame(parent)
        cols = ttk.Frame(f)
        cols.pack(fill="both", expand=True)
        left = ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(cols)
        right.pack(side="left", fill="both", expand=True)

        info = self.card(left, "Device")
        self.dev_info_box = ttk.Frame(info)
        self.dev_info_box.pack(fill="x", pady=(4, 6))
        ttk.Label(self.dev_info_box, text="Press Refresh to read the phone's details.", style="Muted.TLabel").grid(row=0, column=0)
        ttk.Button(info, text="Refresh", command=self.dev_refresh).pack(anchor="w")

        adb = self.card(left, "adb server")
        self.adb_state = tk.StringVar(value="running")
        self.wrap_label(adb, textvariable=self.adb_state, style="Muted.TLabel").pack(fill="x", pady=(0, 6))
        rb = ttk.Frame(adb)
        rb.pack(fill="x")
        ttk.Button(rb, text="Restart", command=self.adb_restart).pack(side="left")
        self.adb_stop_btn = ttk.Button(rb, text="Stop", command=self.adb_stop_toggle)
        self.adb_stop_btn.pack(side="left", padx=6)
        ttk.Button(rb, text="Open terminal", command=lambda: self.open_terminal(shell=False)).pack(side="left")

        tg = self.card(right, "Developer toggles", "Change settings on the phone for testing. Some phones block "
                                                   "a few of them; the activity log says so.")
        grid = ttk.Frame(tg)
        grid.pack(fill="x")
        self.dev_toggle_vars = {}
        for i, (key, label, *_rest) in enumerate(DEV_TOGGLES):
            v = tk.BooleanVar(value=False)
            self.dev_toggle_vars[key] = v
            ttk.Checkbutton(grid, text=label, variable=v, style="Switch.TCheckbutton",
                            command=lambda k=key: self.dev_toggle(k)).grid(row=i // 2, column=i % 2, sticky="w",
                                                                           padx=(0, 18), pady=2)
        ttk.Button(tg, text="Read current", command=self.dev_toggles_read).pack(anchor="w", pady=(6, 0))

        u = self.card(right, "Open on the phone", "A web address or a deep link, e.g. myapp://orders/42")
        ur = ttk.Frame(u)
        ur.pack(fill="x")
        self.dev_url = tk.StringVar(value=self.cfg.get("dev_url", "https://"))
        e = ttk.Entry(ur, textvariable=self.dev_url)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.dev_open_url())
        ttk.Button(ur, text="Open", style="Accent.TButton", command=self.dev_open_url).pack(side="left", padx=(6, 0))

        p = self.card(right, "Port forwarding", "Reverse: the phone's localhost:port reaches this PC (local backend, "
                                                "dev server). Forward: this PC's port reaches the phone.")
        pr = ttk.Frame(p)
        pr.pack(fill="x")
        self.fw_kind = tk.StringVar(value="Reverse")
        ttk.Combobox(pr, textvariable=self.fw_kind, values=["Reverse", "Forward"], state="readonly",
                     width=8).pack(side="left")
        ttk.Label(pr, text="phone").pack(side="left", padx=(8, 2))
        self.fw_phone = tk.StringVar(value="8000")
        ttk.Entry(pr, textvariable=self.fw_phone, width=7).pack(side="left")
        ttk.Label(pr, text="PC").pack(side="left", padx=(8, 2))
        self.fw_pc = tk.StringVar(value="8000")
        ttk.Entry(pr, textvariable=self.fw_pc, width=7).pack(side="left")
        self.fw_list = tk.Listbox(p, height=4, activestyle="none", relief="flat", borderwidth=0,
                                  highlightthickness=0, font=("Consolas", 9))
        self.fw_list.pack(fill="x", pady=(6, 4))
        self.dev_lists.append(self.fw_list)
        fb = ttk.Frame(p)
        fb.pack(fill="x")
        ttk.Button(fb, text="Add", style="Accent.TButton", command=self.fw_add).pack(side="left")
        ttk.Button(fb, text="Remove selected", command=self.fw_remove).pack(side="left", padx=6)
        ttk.Button(fb, text="Refresh", command=self.fw_refresh).pack(side="left")
        self.fw_rows = []
        return f

    # ---- device info
    def dev_refresh(self):
        serial = self.dev_serial()
        if not serial:
            return

        def work():
            parts = ["getprop ro.product.manufacturer", "getprop ro.product.model", "getprop ro.build.version.release",
                     "getprop ro.build.version.sdk", "getprop ro.build.version.security_patch",
                     "getprop ro.product.cpu.abi", "wm size | tail -1", "wm density | tail -1",
                     "ip -f inet addr show wlan0 | grep inet | head -1", "df -h /data | tail -1",
                     "grep MemTotal /proc/meminfo", "dumpsys battery | grep -E ' level| temperature'"]
            # one marker line between commands: a command that prints nothing can't shift the others
            rc, out, _ = self.adb_run("shell", "; echo @@MIRROR@@; ".join(parts), serial=serial, timeout=30)
            L = [s.strip() for s in out.split("@@MIRROR@@")] + [""] * 16
            ip = re.search(r"inet (\S+)", L[8])
            df = L[9].split()
            mem = re.search(r"(\d+)", L[10])
            batt = re.search(r"level: (\d+)", L[11])
            temp = re.search(r"temperature: (\d+)", L[11])
            rows = [
                ("Model", "%s %s" % (L[0].strip(), L[1].strip())),
                ("Android", "%s (SDK %s)" % (L[2].strip(), L[3].strip())),
                ("Security patch", L[4].strip()),
                ("CPU", L[5].strip()),
                ("Screen", "%s · %s" % (L[6].split(":")[-1].strip(), L[7].split(":")[-1].strip() + " dpi")),
                ("Wi-Fi IP", ip.group(1) if ip else "not on Wi-Fi"),
                ("Storage", "%s free of %s" % (df[3], df[1]) if len(df) >= 4 else "?"),
                ("Memory", "%.1f GB" % (int(mem.group(1)) / 1024 / 1024) if mem else "?"),
                ("Battery", "%s%%%s" % (batt.group(1), ", %.1f °C" % (int(temp.group(1)) / 10) if temp else "")
                 if batt else "?"),
                ("Serial", serial),
            ]
            self.ui(self._dev_show_info, rows)
            self.dev_toggles_read()
            self.fw_refresh()
        self.bg(work)

    def _dev_show_info(self, rows):
        for w in self.dev_info_box.winfo_children():
            w.destroy()
        for i, (k, v) in enumerate(rows):
            ttk.Label(self.dev_info_box, text=k, style="Muted.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 14))
            ttk.Label(self.dev_info_box, text=v).grid(row=i, column=1, sticky="w")

    # ---- toggles
    def dev_toggles_read(self):
        serial = self.selected()
        if not serial or self.adb_stopped:
            return

        def work():
            for key, _label, read, _on, _off, is_on in DEV_TOGGLES:
                rc, out, _ = self.adb_run("shell", read, serial=serial, timeout=10)
                self.ui(self.dev_toggle_vars[key].set, bool(is_on(out)))
        self.bg(work)

    def dev_toggle(self, key):
        serial = self.dev_serial()
        if not serial:
            return
        _k, label, read, on_cmd, off_cmd, is_on = next(t for t in DEV_TOGGLES if t[0] == key)
        want = self.dev_toggle_vars[key].get()

        def work():
            rc, out, err = self.adb_run("shell", on_cmd if want else off_cmd, serial=serial, timeout=15)
            rc2, now, _ = self.adb_run("shell", read, serial=serial, timeout=10)
            actual = bool(is_on(now))
            self.ui(self.dev_toggle_vars[key].set, actual)
            if actual != want:
                why = (out + err).strip().splitlines()
                self.log("The phone did not accept '%s'%s" % (label, (": " + why[-1][:160]) if why else "."))
            else:
                self.log("%s %s" % (label, "on" if want else "off"))
        self.bg(work)

    # ---- open URL
    def dev_open_url(self):
        url = self.dev_url.get().strip()
        if not URL_RE.match(url) or len(url) > 2000:
            messagebox.showinfo(self.APP_NAME, "Enter a full address with its scheme, e.g. https://example.com "
                                               "or myapp://screen")
            return
        serial = self.dev_serial()
        if not serial:
            return
        self._set_cfg("dev_url", url)

        def work():
            rc, out, err = self.adb_run("shell", "am start -a android.intent.action.VIEW -d %s" % sh_quote(url),
                                        serial=serial, timeout=20)
            msg = (out + err).strip()
            if "Error" in msg or "unable to resolve" in msg.lower():
                self.log("No app on the phone opens %s" % url)
            else:
                self.log("Opened %s on the phone" % url)
        self.bg(work)

    # ---- ports
    def fw_refresh(self):
        serial = self.selected()
        if not serial or self.adb_stopped:
            return

        def work():
            rows = []
            rc, out, _ = self.adb_run("reverse", "--list", serial=serial, timeout=10)
            rows += [("Reverse", r[1], r[2]) for r in parse_forward_list(out)]
            rc, out, _ = self.adb_run("forward", "--list", timeout=10)
            rows += [("Forward", r[1], r[2]) for r in parse_forward_list(out) if r[0] == serial]
            self.ui(self._fw_show, rows)
        self.bg(work)

    def _fw_show(self, rows):
        self.fw_rows = rows
        self.fw_list.delete(0, "end")
        for kind, a, b in rows:
            if kind == "Reverse":
                self.fw_list.insert("end", "Reverse  phone %-12s -> PC %s" % (a, b))
            else:
                self.fw_list.insert("end", "Forward  PC %-15s -> phone %s" % (a, b))
        if not rows:
            self.fw_list.insert("end", "(none)")

    def fw_add(self):
        try:
            phone_port, pc_port = int(self.fw_phone.get()), int(self.fw_pc.get())
            assert 0 < phone_port < 65536 and 0 < pc_port < 65536
        except (ValueError, AssertionError):
            messagebox.showinfo(self.APP_NAME, "Ports are numbers from 1 to 65535.")
            return
        serial = self.dev_serial()
        if not serial:
            return
        kind = self.fw_kind.get()
        if kind == "Reverse" and phone_port < 1024:
            messagebox.showinfo(self.APP_NAME, "Android doesn't allow phone ports below 1024 here; use e.g. 8080.")
            return
        args = ("reverse", "tcp:%d" % phone_port, "tcp:%d" % pc_port) if kind == "Reverse" else \
            ("forward", "tcp:%d" % pc_port, "tcp:%d" % phone_port)

        def work():
            rc, out, err = self.adb_run(*args, serial=serial, timeout=15)
            self.log("%s %s" % (kind, "added" if rc == 0 else "failed: " + (out + err).strip()))
            self.fw_refresh()
        self.bg(work)

    def fw_remove(self):
        sel = self.fw_list.curselection()
        if not sel or sel[0] >= len(self.fw_rows):
            return
        kind, local, _remote = self.fw_rows[sel[0]]
        serial = self.selected()

        def work():
            self.adb_run(kind.lower(), "--remove", local, serial=serial, timeout=15)
            self.fw_refresh()
        self.bg(work)

    # ---- adb server
    def adb_restart(self):
        if not messagebox.askyesno(self.APP_NAME, "Restart the adb server?\n\nMirroring, recordings and logcat stop. "
                                                  "Android Studio and other adb tools reconnect by themselves."):
            return
        self._adb_halt_sessions()

        def work():
            self.adb_run("kill-server", timeout=20)
            time.sleep(1)
            self.adb_run("start-server", timeout=30)
            self.adb_stopped = False
            self.ui(self._adb_state_show)
            self.log("adb server restarted")
            self.refresh_devices()
        self.bg(work)

    def adb_stop_toggle(self):
        if self.adb_stopped:
            self.adb_stopped = False
            self.adb_state.set("Starting…")
            self.adb_stop_btn.configure(text="Stop")
            self.bg(lambda: (self.adb_run("start-server", timeout=30), self.ui(self._adb_state_show),
                             self.log("adb server started"), self.refresh_devices()))
            return
        if not messagebox.askyesno(self.APP_NAME, "Stop the adb server?\n\nPhones disconnect until you start it again "
                                                  "(Mirror stops looking for them meanwhile). Use this when another "
                                                  "tool needs adb to itself."):
            return
        self._adb_halt_sessions()
        self.adb_stopped = True

        def work():
            self.adb_run("kill-server", timeout=20)
            self.ui(self._adb_state_show)
            self.ui(self._apply_devices, [])
            self.log("adb server stopped")
        self.bg(work)

    def _adb_halt_sessions(self):
        if self.lc_proc:
            self.lc_stop()
        if self.sh_proc:
            self.sh_run()
        for serial in list(self.procs):
            self.stop_mirror(serial)

    def _adb_state_show(self):
        if self.adb_stopped:
            self.adb_state.set("Stopped. Phones are disconnected until you start it again.")
            self.adb_stop_btn.configure(text="Start")
        else:
            self.adb_state.set("Running · %s" % self.adb)
            self.adb_stop_btn.configure(text="Stop")

    def dev_close(self):
        """App shutdown: end logcat / shell processes."""
        for p in (self.lc_proc, self.sh_proc):
            if p:
                self.kill_proc(p)
        self.lc_proc = self.sh_proc = None
