"""Skins for Mirror.

"Light" and "Dark" are the Windows 11 look (sv-ttk). The other skins are a
custom ttk theme on top of 'clam': colours, fonts and rounded buttons / cards /
switches drawn at runtime (anti-aliased, no image files), plus a few
decorations (gradient brand and glow strip, Gamer's colour cycling, Hacker's
blinking cursor). Pure Tk: works inside the one-file exe.
"""
import colorsys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------- skin definitions
# engine "sv" = sv-ttk light/dark; "custom" = drawn here.
SKINS = {
    "Light": {"engine": "sv", "base": "light", "tagline": "Windows 11, light"},
    "Dark": {"engine": "sv", "base": "dark", "tagline": "Windows 11, dark"},
    "Developer": {
        "engine": "custom", "dark": True, "tagline": "Editor greys, blue status bar",
        "bg": "#1e1e1e", "side": "#181818", "hover": "#2a2d2e", "sel": "#37373d", "card": "#1e1e1e",
        "border": "#3c3c3c", "accent": "#0078d4", "accent2": "#3794ff", "on_accent": "#ffffff",
        "fg": "#cccccc", "muted": "#8b8b8b", "field": "#252526", "ok": "#89d185", "warn": "#cca700",
        "fonts": ("Segoe UI", "Segoe UI Semibold", "Cascadia Mono"), "radius": 4,
        "statusbar": True, "brand": "Mirror",
    },
    "Hacker": {
        "engine": "custom", "dark": True, "tagline": "Terminal green on black",
        "bg": "#030603", "side": "#000000", "hover": "#082010", "sel": "#0b2b14", "card": "#030603",
        "border": "#0f5a24", "accent": "#00ff66", "accent2": "#00b84a", "on_accent": "#001a08",
        "fg": "#9dffb8", "muted": "#3fa860", "field": "#010301", "ok": "#00ff66", "warn": "#e5ff00",
        "fonts": ("Consolas", "Consolas", "Consolas"), "radius": 0,
        "brand": "> mirror", "cursor": True, "logcolors": {"V": "#3fa860", "D": "#6dffa0", "I": "#00ff66"},
    },
    "Gamer": {
        "engine": "custom", "dark": True, "tagline": "Neon magenta + cyan, RGB glow",
        "bg": "#0d0221", "side": "#09011a", "hover": "#1c0842", "sel": "#260b57", "card": "#0d0221",
        "border": "#41168f", "accent": "#ff2bd6", "accent2": "#00e5ff", "on_accent": "#ffffff",
        "fg": "#f5e9ff", "muted": "#a596cf", "field": "#14042e", "ok": "#39ff14", "warn": "#ffd400",
        "fonts": ("Bahnschrift", "Bahnschrift SemiBold", "Cascadia Mono"), "radius": 10,
        "brand": "MIRROR", "gradient": True, "rgb": True,
    },
    "Aurora": {
        "engine": "custom", "dark": True, "tagline": "Midnight glass, violet-cyan glow",
        "bg": "#0b1020", "side": "#0a0e1d", "hover": "#141c3a", "sel": "#1b2550", "card": "#0b1020",
        "border": "#2a3566", "accent": "#7c5cff", "accent2": "#22d3ee", "on_accent": "#ffffff",
        "fg": "#e8ebf8", "muted": "#8d95bb", "field": "#10173a", "ok": "#34d399", "warn": "#fbbf24",
        "fonts": ("Segoe UI Variable Text", "Segoe UI Variable Display", "Cascadia Mono"), "radius": 14,
        "brand": "Mirror", "gradient": True,
    },
    "Paper": {
        "engine": "custom", "dark": False, "tagline": "Warm paper, coral ink",
        "bg": "#fbf7f0", "side": "#f3ecdf", "hover": "#ebe2d2", "sel": "#e4d8c3", "card": "#fbf7f0",
        "border": "#dccfb9", "accent": "#d9502f", "accent2": "#e8a33d", "on_accent": "#ffffff",
        "fg": "#2b2622", "muted": "#7a6f63", "field": "#fffdf8", "ok": "#3d8b40", "warn": "#b06b00",
        "fonts": ("Segoe UI", "Georgia", "Cascadia Mono"), "radius": 8,
        "brand": "Mirror", "serif_brand": True,
    },
    # ---- retro: glossy gradient buttons with a shine on the top half
    "Luna": {
        "engine": "custom", "dark": False, "tagline": "Retro XP-style: beige, blue, glossy",
        "bg": "#ece9d8", "side": "#c6d3f7", "hover": "#dbe4fb", "sel": "#a7bdf0", "card": "#ece9d8",
        "border": "#7f9db9", "accent": "#2a5bd7", "accent2": "#0a246a", "on_accent": "#ffffff",
        "fg": "#0a1e5a", "muted": "#4d5d86", "field": "#ffffff", "ok": "#2e8b2e", "warn": "#b8860b",
        "fonts": ("Tahoma", "Trebuchet MS", "Lucida Console"), "radius": 3,
        "brand": "Mirror", "gradient": True, "gloss": True,
        "btn_top": "#ffffff", "btn_bottom": "#e3e2d8", "btn_border": "#003c74",
    },
    "Aero": {
        "engine": "custom", "dark": False, "tagline": "Retro 7-style: pale glass, glossy blue",
        "bg": "#e8eff8", "side": "#d2e0f3", "hover": "#e4f0fc", "sel": "#c4def6", "card": "#e8eff8",
        "border": "#a6bbd6", "accent": "#2b7bc6", "accent2": "#7fc4ff", "on_accent": "#ffffff",
        "fg": "#1b2533", "muted": "#566b85", "field": "#ffffff", "ok": "#2e8540", "warn": "#a86b00",
        "fonts": ("Segoe UI", "Segoe UI Semibold", "Consolas"), "radius": 4,
        "brand": "Mirror", "gradient": True, "gloss": True,
        "btn_top": "#fbfbfb", "btn_bottom": "#d9dee5", "btn_border": "#707a86",
    },
}
ORDER = ["System", "Light", "Dark", "Developer", "Hacker", "Gamer", "Aurora", "Paper", "Luna", "Aero"]

# sv-ttk palettes (match sv-ttk's own colours)
SV_PALETTE = {
    "dark": {"bg": "#1c1c1c", "side": "#202020", "hover": "#2a2a2a", "sel": "#2d2d2d", "accent": "#57c8ff",
             "accent2": "#57c8ff", "fg": "#fafafa", "muted": "#9d9d9d", "field": "#262626", "ok": "#6ccb5f",
             "warn": "#fce100", "border": "#3a3a3a", "on_accent": "#000000", "dark": True},
    "light": {"bg": "#fafafa", "side": "#f0f0f0", "hover": "#e8e8e8", "sel": "#e3e3e3", "accent": "#005fb8",
              "accent2": "#005fb8", "fg": "#1c1c1c", "muted": "#5f5f5f", "field": "#ffffff", "ok": "#0f7b0f",
              "warn": "#9d5d00", "border": "#e0e0e0", "on_accent": "#ffffff", "dark": False},
}


def resolve(name, system_dark):
    """Skin dict for a saved theme name ('System' follows Windows)."""
    if name == "System" or name not in SKINS:
        name = "Dark" if system_dark else "Light"
    s = dict(SKINS[name])
    s["name"] = name
    if s["engine"] == "sv":
        s.update(SV_PALETTE[s["base"]])
    return s


# ---------------------------------------------------------------- colour + raster helpers
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in c)


def mix(a, b, t):
    """Blend colour a toward b by t (0..1); accepts hex strings."""
    a, b = hex2rgb(a), hex2rgb(b)
    return rgb2hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


def _sd_round_box(px, py, cx, cy, hw, hh, r):
    """Signed distance from (px,py) to a rounded box (negative inside)."""
    qx = abs(px - cx) - (hw - r)
    qy = abs(py - cy) - (hh - r)
    ox, oy = max(qx, 0.0), max(qy, 0.0)
    return (ox * ox + oy * oy) ** 0.5 + min(max(qx, qy), 0.0) - r


def gloss(top, bottom, shine=True):
    """A vertical gradient fill; shine adds the glossy highlight over the top half (XP / 7 buttons)."""
    return ("grad", top, bottom, shine)


def _fill_at(fill, t):
    """Colour of a fill at relative height t (0 = top, 1 = bottom)."""
    if not isinstance(fill, tuple):
        return fill
    _, top, bottom, shine = fill
    c = mix(top, bottom, max(0.0, min(1.0, t)))
    if shine and t < 0.48:
        c = mix(c, "#ffffff", 0.18 + 0.32 * (1 - t / 0.48))
    return c


def raster(w, h, shapes, outside):
    """Draw anti-aliased rounded boxes into a PhotoImage.

    shapes: [(x, y, w, h, radius, fill, border, border_width)] painted in order.
    outside: colour used to blend the anti-aliased outer edge; pixels fully
    outside every shape are transparent."""
    img = tk.PhotoImage(width=w, height=h)
    rows, clear = [], []
    for y in range(h):
        row = []
        for x in range(w):
            col, alpha = None, 0.0
            for (sx, sy, sw, sh, r, fill, border, bw) in shapes:
                r = min(r, sw / 2.0, sh / 2.0)
                d = _sd_round_box(x + 0.5, y + 0.5, sx + sw / 2.0, sy + sh / 2.0, sw / 2.0, sh / 2.0, max(r, 0.01))
                cov = max(0.0, min(1.0, 0.5 - d))
                if cov <= 0:
                    continue
                c = _fill_at(fill, (y + 0.5 - sy) / max(sh, 1))
                if bw > 0:
                    inner = max(0.0, min(1.0, 0.5 - (d + bw)))
                    c = mix(border, c, inner)
                base = col if col is not None else outside
                col = mix(base, c, cov)
                alpha = max(alpha, cov)
            if col is None or alpha < 0.25:
                row.append(outside)
                clear.append((x, y))
            else:
                row.append(col)
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    for x, y in clear:
        img.transparency_set(x, y, True)
    return img


# ---------------------------------------------------------------- custom ttk theme
def _font(families, *alts):
    have = set(tkfont.families())
    for f in families if isinstance(families, (list, tuple)) else [families]:
        if f in have:
            return f
    for f in alts:
        if f in have:
            return f
    return "TkDefaultFont"


def build_custom(root, skin):
    """Create (once) and switch to the ttk theme for a custom skin."""
    st = ttk.Style(root)
    name = "mirror-" + skin["name"].lower()
    imgs = getattr(root, "_mirror_skin_imgs", {})
    root._mirror_skin_imgs = imgs
    first = name not in st.theme_names()
    if first:
        st.theme_create(name, parent="clam")
    st.theme_use(name)
    s = skin
    r = s["radius"]
    bg, card = s["bg"], s["card"]
    if first:
        br = min(r, 8)  # buttons: smaller radius than cards, or they get too tall
        R = max(br, 2)
        glossy = s.get("gloss")
        # glossy buttons: a full-height image whose middle barely stretches, so the gradient survives
        bw_, bh_ = 2 * R + 8, (30 if glossy else 2 * R + 8)

        def box(fill, border, bw=1, outside=bg, w=bw_, h=bh_, rr=br):
            return raster(w, h, [(0, 0, w, h, rr, fill, border, bw)], outside)
        btn = s["field"] if s["dark"] else mix(s["bg"], "#ffffff", 0.6)
        acc = s["accent"]
        if glossy:
            b_top, b_bot = s.get("btn_top", "#ffffff"), s.get("btn_bottom", mix(s["bg"], "#000000", 0.08))
            fills = {
                "btn": gloss(b_top, b_bot), "btn_hover": gloss(mix(b_top, acc, 0.10), mix(b_bot, acc, 0.22)),
                "btn_press": gloss(mix(b_bot, acc, 0.25), mix(b_top, acc, 0.15), False), "btn_dis": b_bot,
                "acc": gloss(mix(acc, "#ffffff", 0.25), mix(acc, "#000000", 0.18)),
                "acc_hover": gloss(mix(acc, "#ffffff", 0.40), acc),
                "acc_press": gloss(mix(acc, "#000000", 0.25), acc, False), "acc_dis": mix(acc, bg, 0.55),
            }
            btn_border = s.get("btn_border", s["border"])
        else:
            fills = {
                "btn": btn, "btn_hover": mix(btn, acc, 0.12), "btn_press": mix(btn, acc, 0.22), "btn_dis": btn,
                "acc": acc, "acc_hover": mix(acc, "#ffffff", 0.14), "acc_press": mix(acc, "#000000", 0.15),
                "acc_dis": mix(acc, bg, 0.55),
            }
            btn_border = s["border"]
        im = {
            "btn": box(fills["btn"], btn_border),
            "btn_hover": box(fills["btn_hover"], mix(btn_border, acc, 0.6)),
            "btn_press": box(fills["btn_press"], acc),
            "btn_dis": box(fills["btn_dis"], mix(btn_border, bg, 0.5)),
            "acc": box(fills["acc"], mix(acc, "#000000", 0.25) if glossy else acc),
            "acc_hover": box(fills["acc_hover"], mix(acc, "#000000", 0.2) if glossy else mix(acc, "#ffffff", 0.14)),
            "acc_press": box(fills["acc_press"], mix(acc, "#000000", 0.3)),
            "acc_dis": box(fills["acc_dis"], mix(acc, bg, 0.55)),
            "card": box(card, s["border"], rr=max(r, 2) + (2 if r >= 8 else 0),
                        w=2 * (max(r, 2) + 2) + 10, h=2 * (max(r, 2) + 2) + 10),
        }
        # switch: track 40x22, knob
        sw, sh = 40, 22
        im["sw_off"] = raster(sw, sh, [(0, 0, sw, sh, 11, s["field"], s["muted"], 1.2),
                                       (5, 5, 12, 12, 6, s["muted"], s["muted"], 0)], card)
        im["sw_on"] = raster(sw, sh, [(0, 0, sw, sh, 11, s["accent"], s["accent"], 0),
                                      (sw - 18, 4, 14, 14, 7, s["on_accent"], s["on_accent"], 0)], card)
        im["sw_dis"] = raster(sw, sh, [(0, 0, sw, sh, 11, s["field"], mix(s["muted"], card, 0.5), 1),
                                       (5, 5, 12, 12, 6, mix(s["muted"], card, 0.5), s["muted"], 0)], card)
        imgs[name] = im
        vb = (bh_ // 2 - 1) if glossy else R + 2
        b = (R + 2, vb, R + 2, vb)
        p = (R + 4, 4, R + 4, 4)  # content inset (independent of the stretch border)
        st.element_create("Skin.Button.border", "image", im["btn"], ("disabled", im["btn_dis"]),
                          ("pressed", im["btn_press"]), ("active", im["btn_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Accent.border", "image", im["acc"], ("disabled", im["acc_dis"]),
                          ("pressed", im["acc_press"]), ("active", im["acc_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Toggle.border", "image", im["btn"], ("disabled", im["btn_dis"]),
                          ("selected", im["acc"]), ("pressed", im["btn_press"]), ("active", im["btn_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Card.border", "image", im["card"], border=max(r, 2) + 4, sticky="nsew")
        st.element_create("Skin.Switch.indicator", "image", im["sw_off"], ("disabled", im["sw_dis"]),
                          ("selected", im["sw_on"]), sticky="")
        label = ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})
        st.layout("TButton", [("Skin.Button.border", {"sticky": "nsew", "children": [label]})])
        st.layout("Accent.TButton", [("Skin.Accent.border", {"sticky": "nsew", "children": [label]})])
        st.layout("Icon.TButton", [("Skin.Button.border", {"sticky": "nsew", "children": [label]})])
        st.layout("Toggle.TButton", [("Skin.Toggle.border", {"sticky": "nsew", "children": [label]})])
        st.layout("Card.TFrame", [("Skin.Card.border", {"sticky": "nsew"})])
        st.layout("Switch.TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [
            ("Skin.Switch.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.label", {"side": "left", "sticky": "nsew"})]})])

    ui, disp, mono = (_font(s["fonts"][0], "Segoe UI"), _font(s["fonts"][1], "Segoe UI"),
                      _font(s["fonts"][2], "Consolas"))
    fg, muted, acc, field, border = s["fg"], s["muted"], s["accent"], s["field"], s["border"]
    st.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=border,
                 lightcolor=border, darkcolor=border, troughcolor=s["side"], selectbackground=acc,
                 selectforeground=s["on_accent"], insertcolor=fg, focuscolor=acc, font=(ui, 10))
    st.configure("TFrame", background=bg)
    st.configure("Card.TFrame", background=card)
    st.configure("TLabel", background=bg, foreground=fg)
    pad = (4, 1)  # the button images add their own inset
    st.configure("TButton", foreground=fg, padding=pad, anchor="center")
    st.map("TButton", foreground=[("disabled", muted)])
    st.configure("Accent.TButton", foreground=s["on_accent"], padding=pad, anchor="center",
                 font=(ui, 10, "bold") if s["name"] in ("Gamer", "Hacker") else (ui, 10))
    st.map("Accent.TButton", foreground=[("disabled", mix(s["on_accent"], bg, 0.4))])
    st.configure("Toggle.TButton", foreground=fg, padding=pad, anchor="center")
    st.map("Toggle.TButton", foreground=[("selected", s["on_accent"]), ("disabled", muted)])
    st.configure("Icon.TButton", padding=(6, 4))
    st.configure("Switch.TCheckbutton", background=card, foreground=fg, padding=(2, 2))
    st.map("Switch.TCheckbutton", foreground=[("disabled", muted)], background=[("active", card)])
    st.configure("TCheckbutton", background=bg, foreground=fg, indicatorbackground=field,
                 indicatorforeground=acc, upperbordercolor=border, lowerbordercolor=border)
    st.map("TCheckbutton", background=[("active", bg)], indicatorbackground=[("selected", acc)])
    st.configure("TRadiobutton", background=bg, foreground=fg)
    for w in ("TEntry", "TCombobox"):
        st.configure(w, fieldbackground=field, foreground=fg, bordercolor=border, lightcolor=field,
                     darkcolor=field, insertcolor=fg, padding=(8, 5), arrowcolor=muted, background=field)
        st.map(w, bordercolor=[("focus", acc), ("hover", mix(border, acc, 0.5))],
               lightcolor=[("focus", acc)], darkcolor=[("focus", acc)],
               fieldbackground=[("readonly", field), ("disabled", bg)],
               foreground=[("disabled", muted), ("readonly", fg), ("", fg)], arrowcolor=[("hover", acc)])
    st.configure("TCombobox", selectbackground=field, selectforeground=fg)
    st.map("TCombobox", selectbackground=[("readonly", field), ("", field)],
           selectforeground=[("readonly", fg), ("", fg)])
    root.option_add("*TCombobox*Listbox.background", field)
    root.option_add("*TCombobox*Listbox.foreground", fg)
    root.option_add("*TCombobox*Listbox.selectBackground", acc)
    root.option_add("*TCombobox*Listbox.selectForeground", s["on_accent"])
    root.option_add("*TCombobox*Listbox.font", (ui, 10))
    for orient in ("Vertical", "Horizontal"):
        st.configure("%s.TScrollbar" % orient, background=mix(bg, muted, 0.35), troughcolor=bg,
                     bordercolor=bg, lightcolor=bg, darkcolor=bg, arrowcolor=muted, gripcount=0)
        st.map("%s.TScrollbar" % orient, background=[("active", acc), ("pressed", acc)])
    st.configure("Treeview", background=field, fieldbackground=field, foreground=fg, bordercolor=border,
                 lightcolor=border, darkcolor=border, rowheight=28, font=(ui, 10))
    st.map("Treeview", background=[("selected", mix(field, acc, 0.35))], foreground=[("selected", fg)])
    st.configure("Treeview.Heading", background=s["side"], foreground=muted, bordercolor=border,
                 lightcolor=s["side"], darkcolor=s["side"], relief="flat", font=(ui, 9, "bold"))
    st.map("Treeview.Heading", background=[("active", s["hover"])])
    st.configure("TProgressbar", background=acc, troughcolor=field, bordercolor=border,
                 lightcolor=acc, darkcolor=acc)
    st.configure("TSeparator", background=border)
    return {"ui": ui, "display": disp, "mono": mono}


# ---------------------------------------------------------------- decorations
def draw_gradient(canvas, w, h, c1, c2, phase=0.0, steps=48):
    canvas.delete("g")
    for i in range(steps):
        t = (i / float(steps - 1) + phase) % 1.0
        t = 1 - abs(2 * t - 1)  # there and back: seamless when animated
        canvas.create_rectangle(i * w / steps, 0, (i + 1) * w / steps + 1, h, fill=mix(c1, c2, t), width=0,
                                tags="g")


def draw_brand(canvas, skin, font, text, cursor_on=True):
    """Sidebar brand: gradient letters for gradient skins, a prompt for Hacker."""
    canvas.delete("all")
    canvas.configure(bg=skin["side"])
    x, y = 18, 30
    f = tkfont.Font(family=font, size=15, weight="bold")
    if skin.get("gradient"):
        n = max(len(text) - 1, 1)
        for i, ch in enumerate(text):
            canvas.create_text(x, y, text=ch, anchor="w", font=f, fill=mix(skin["accent"], skin["accent2"], i / n))
            x += f.measure(ch) + (1 if skin["name"] == "Gamer" else 0)
    else:
        color = skin["accent"] if skin.get("cursor") else skin["fg"]
        canvas.create_text(x, y, text=text, anchor="w", font=f, fill=color)
        x += f.measure(text)
    if skin.get("cursor") and cursor_on:
        canvas.create_rectangle(x + 4, y - 9, x + 14, y + 9, fill=skin["accent"], width=0)


def draw_preview(canvas, skin, selected, label_font):
    """A mini drawing of a skin for the theme picker."""
    w, h = int(canvas["width"]), int(canvas["height"])
    canvas.delete("all")
    bg, side, acc = skin["bg"], skin["side"], skin["accent"]
    canvas.configure(bg=bg)
    canvas.create_rectangle(0, 0, 26, h, fill=side, width=0)
    for i in range(4):
        y = 12 + i * 11
        canvas.create_rectangle(6, y, 20, y + 5, fill=acc if i == 1 else skin["muted"], width=0)
    if skin.get("gradient"):
        for i in range(20):
            canvas.create_rectangle(26 + i * (w - 26) / 20, 0, 26 + (i + 1) * (w - 26) / 20 + 1, 3,
                                    fill=mix(acc, skin["accent2"], i / 19.0), width=0)
    canvas.create_rectangle(34, 10, w - 10, 14, fill=skin["fg"], width=0)
    canvas.create_rectangle(34, 19, w - 30, 22, fill=skin["muted"], width=0)
    canvas.create_rectangle(34, 29, w - 10, h - 16, outline=skin.get("border", skin["muted"]), width=1)
    canvas.create_rectangle(40, 35, 72, 44, fill=acc, width=0)
    canvas.create_rectangle(78, 35, w - 16, 44, outline=skin.get("border", skin["muted"]), width=1)
    canvas.create_text(w / 2 + 12, h - 8, text=skin["name"], fill=skin["fg"], font=(label_font, 8, "bold"))
    if selected:
        canvas.create_rectangle(1, 1, w - 2, h - 2, outline=acc, width=3)


def hue_cycle(t):
    """RGB-cycling colour for Gamer (t: any float)."""
    r, g, b = colorsys.hsv_to_rgb(t % 1.0, 0.85, 1.0)
    return rgb2hex((r * 255, g * 255, b * 255))
