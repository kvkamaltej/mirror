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
    # ---- morphism
    "Glass": {
        "engine": "custom", "dark": True, "tagline": "iOS-style frosted glass: live Windows 11 blur through the window",
        # Windows 11 Acrylic shows through what Tk draws: black = clear glass, dark greys = frosted tints,
        # so every colour here is a "light over glass" value and text is light.
        "bg": "#0c0c10", "side": "#000000", "hover": "#1c1c24", "sel": "#2a2a34", "card": "#0c0c10",
        "border": "#3c3c48", "accent": "#0a84ff", "accent2": "#5e5ce6", "on_accent": "#ffffff",
        "fg": "#ffffff", "muted": "#a3a3b0", "field": "#17171e", "ok": "#30d158", "warn": "#ffd60a",
        "fonts": ("Segoe UI Variable Text", "Segoe UI Variable Display", "Cascadia Mono"), "radius": 14,
        "brand": "Mirror", "glass": True, "switch_on": "#30d158", "switch_knob": "#ffffff",
    },
    "Neumorph": {
        "engine": "custom", "dark": False, "tagline": "Soft UI: raised and pressed-in surfaces",
        "bg": "#e4e9f0", "side": "#e4e9f0", "hover": "#dbe1ea", "sel": "#d3dae5", "card": "#e4e9f0",
        "border": "#d0d7e1", "accent": "#5b7cfa", "accent2": "#8f6bff", "on_accent": "#ffffff",
        "fg": "#38415a", "muted": "#7a8599", "field": "#dfe4ec", "ok": "#2f9e6a", "warn": "#c17c00",
        "fonts": ("Segoe UI Variable Text", "Segoe UI Variable Display", "Cascadia Mono"), "radius": 18,
        "brand": "Mirror", "style": "neu", "shadow_dark": "#a7b3c4", "shadow_light": "#ffffff",
        "toggle_sel_fg": "#5b7cfa",
    },
    "Clay": {
        "engine": "custom", "dark": False, "tagline": "Claymorphism: pastel, puffy, candy buttons",
        "bg": "#f4effd", "side": "#efe7fc", "hover": "#e8ddfb", "sel": "#dfd0fa", "card": "#f4effd",
        "border": "#e2d6fa", "accent": "#ff5fa2", "accent2": "#8b6cff", "on_accent": "#ffffff",
        "fg": "#3a2e5c", "muted": "#8a7fab", "field": "#ffffff", "ok": "#2fae6e", "warn": "#d88a00",
        "fonts": ("Segoe UI Variable Text", "Segoe UI Variable Display", "Cascadia Mono"), "radius": 22,
        "brand": "Mirror", "gradient": True, "style": "clay", "shadow_dark": "#cbb9f4", "btn_top": "#ffffff",
    },
    "Skeuo": {
        "engine": "custom", "dark": False, "tagline": "Skeuomorphism: glossy, embossed, iOS 6-style",
        "bg": "#cbd2da", "side": "#dfe4ea", "hover": "#d3dae2", "sel": "#bccbe0", "card": "#cbd2da",
        "border": "#9aa6b3", "accent": "#3d6fc6", "accent2": "#7c98c8", "on_accent": "#ffffff",
        "fg": "#1f2a37", "muted": "#566475", "field": "#ffffff", "ok": "#2f8a3d", "warn": "#a86b00",
        "fonts": ("Segoe UI", "Segoe UI Semibold", "Consolas"), "radius": 10,
        "brand": "Mirror", "gradient": True, "gloss": True, "style": "skeuo",
        "btn_top": "#fdfdfd", "btn_bottom": "#d0d6dd", "btn_border": "#7d8896",
    },
}
ORDER = ["System", "Light", "Dark", "Glass", "Neumorph", "Clay", "Skeuo", "Developer", "Hacker", "Gamer",
         "Aurora", "Paper", "Luna", "Aero"]

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


def shadow(x, y, w, h, r, color, blur, strength):
    """A soft shadow / glow shape for raster(): a rounded box whose edge fades over `blur` px."""
    return ("shadow", x, y, w, h, r, color, blur, strength)


def raster(w, h, shapes, outside, opaque=False):
    """Draw anti-aliased rounded boxes (and soft shadows) into a PhotoImage.

    shapes: [(x, y, w, h, radius, fill, border, border_width)] or shadow(...), painted in order.
    outside: colour used to blend the anti-aliased outer edge; pixels fully
    outside every shape are transparent, unless opaque (then they are `outside`,
    which soft shadows need to fade into)."""
    img = tk.PhotoImage(width=w, height=h)
    rows, clear = [], []
    for y in range(h):
        row = []
        for x in range(w):
            col, alpha = (outside, 1.0) if opaque else (None, 0.0)
            for shape in shapes:
                if shape[0] == "shadow":
                    _, sx, sy, sw, sh, r, color, blur, strength = shape
                    r = min(r, sw / 2.0, sh / 2.0)
                    d = _sd_round_box(x + 0.5, y + 0.5, sx + sw / 2.0, sy + sh / 2.0, sw / 2.0, sh / 2.0,
                                      max(r, 0.01))
                    f = 1.0 if d <= 0 else max(0.0, 1.0 - d / float(blur))
                    cov = strength * f * f
                    if cov > 0:
                        col = mix(col if col is not None else outside, color, cov)
                        alpha = max(alpha, cov)
                    continue
                (sx, sy, sw, sh, r, fill, border, bw) = shape
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


def _morph_images(s, im, fills, btn_border):
    """Buttons, cards and switches for Neumorph / Clay / Skeuo (replaces entries of im).

    Returns (button stretch border, button content padding, card stretch border).
    Images that carry soft shadows are opaque (painted on the skin's background)."""
    bg, acc = s["bg"], s["accent"]
    style = s["style"]
    dark = s.get("shadow_dark", mix(bg, "#000000", 0.25))
    light = s.get("shadow_light", "#ffffff")
    if style == "neu":
        m, R, H = 6, 10, 28  # shadow margin, corner radius, face height
        W = 2 * R + 12

        def btn(face, raised=True, strong=False):
            sh = ([shadow(m - 3, m - 3, W, H, R, light, 6, 0.95),
                   shadow(m + 3, m + 3, W, H, R, dark, 7, 0.75 if strong else 0.55)] if raised
                  else [shadow(m, m, W, H, R, dark, 2, 0.18)])
            return raster(W + 2 * m, H + 2 * m, sh + [(m, m, W, H, R, face, face, 0)], bg, opaque=True)
        up = gloss(mix(bg, "#ffffff", 0.35), mix(bg, "#000000", 0.02), False)
        down = gloss(mix(bg, "#000000", 0.08), mix(bg, "#ffffff", 0.30), False)  # sunk in: dark top
        aup = gloss(mix(acc, "#ffffff", 0.22), mix(acc, "#000000", 0.08), False)
        im.update(btn=btn(up), btn_hover=btn(up, strong=True), btn_press=btn(down, raised=False),
                  btn_dis=btn(bg), acc=btn(aup), acc_hover=btn(aup, strong=True),
                  acc_press=btn(gloss(mix(acc, "#000000", 0.18), acc, False), raised=False),
                  acc_dis=btn(mix(acc, bg, 0.5)), tog_sel=btn(down, raised=False))
        cm, CR = 12, 18
        CW = 2 * CR + 2 * cm + 10
        im["card"] = raster(CW, CW, [shadow(cm - 5, cm - 5, CW - 2 * cm, CW - 2 * cm, CR, light, 12, 0.9),
                                     shadow(cm + 6, cm + 6, CW - 2 * cm, CW - 2 * cm, CR, dark, 14, 0.5),
                                     (cm, cm, CW - 2 * cm, CW - 2 * cm, CR, bg, bg, 0)], bg, opaque=True)
        sw, sh = 44, 24
        track_in = gloss(mix(bg, "#000000", 0.10), mix(bg, "#ffffff", 0.35), False)
        knob = gloss(mix(bg, "#ffffff", 0.6), bg, False)
        im["sw_off"] = raster(sw, sh, [(1, 1, sw - 2, sh - 2, 11, track_in, mix(bg, "#000000", 0.12), 1),
                                       shadow(4, 6, 15, 15, 7.5, dark, 3, 0.55),
                                       (4, 4, 15, 15, 7.5, knob, knob, 0)], bg, opaque=True)
        im["sw_on"] = raster(sw, sh, [(1, 1, sw - 2, sh - 2, 11, gloss(mix(acc, "#000000", 0.12), acc, False),
                                       acc, 0), shadow(sw - 19, 6, 15, 15, 7.5, mix(acc, "#000000", 0.4), 3, 0.5),
                                      (sw - 19, 4, 15, 15, 7.5, knob, knob, 0)], bg, opaque=True)
        im["sw_dis"] = im["sw_off"]
        return (m + R, m + H // 2 - 1, m + R, m + H // 2 - 1), (m + R, m + 4, m + R, m + 4), cm + CR + 2
    if style == "clay":
        m, R, H = 7, 13, 28
        W = 2 * R + 12
        shade = dark

        def btn(top, bottom, glow, pressed=False):
            sh = [] if pressed else [shadow(m, m + 4, W, H, R, glow, 8, 0.6)]
            rim = (m + 4, m + 2, W - 8, int(H * 0.45), max(R - 4, 2),
                   gloss(mix(top, "#ffffff", 0.55), top, False), top, 0)  # puffy top highlight
            return raster(W + 2 * m, H + 2 * m, sh + [(m, m + (2 if pressed else 0), W, H, R,
                                                        gloss(top, bottom, False), bottom, 0), rim], bg, opaque=True)
        white = s.get("btn_top", "#ffffff")
        cand2 = s["accent2"]
        im.update(btn=btn(white, mix(white, shade, 0.25), shade), btn_hover=btn(white, mix(white, acc, 0.2), acc),
                  btn_press=btn(mix(white, shade, 0.3), white, shade, True), btn_dis=btn(white, white, bg),
                  acc=btn(mix(acc, "#ffffff", 0.25), acc, mix(acc, "#000000", 0.1)),
                  acc_hover=btn(mix(acc, "#ffffff", 0.4), mix(acc, cand2, 0.4), acc),
                  acc_press=btn(acc, mix(acc, "#000000", 0.15), acc, True), acc_dis=btn(mix(acc, bg, 0.5),
                                                                                         mix(acc, bg, 0.5), bg),
                  tog_sel=btn(mix(cand2, "#ffffff", 0.25), cand2, mix(cand2, "#000000", 0.1)))
        cm, CR = 12, 22
        CW = 2 * CR + 2 * cm + 10
        im["card"] = raster(CW, CW, [shadow(cm, cm + 8, CW - 2 * cm, CW - 2 * cm, CR, shade, 16, 0.55),
                                     (cm, cm, CW - 2 * cm, CW - 2 * cm, CR, bg, mix(bg, "#ffffff", 0.85), 2)],
                            bg, opaque=True)
        sw, sh = 44, 24
        im["sw_off"] = raster(sw, sh, [(1, 1, sw - 2, sh - 2, 11, mix(bg, shade, 0.5), mix(bg, shade, 0.5), 0),
                                       shadow(4, 6, 15, 15, 7.5, shade, 3, 0.6), (4, 4, 15, 15, 7.5, "#ffffff",
                                                                                   "#ffffff", 0)], bg, opaque=True)
        im["sw_on"] = raster(sw, sh, [(1, 1, sw - 2, sh - 2, 11, gloss(mix(acc, "#ffffff", 0.2), acc, False),
                                       acc, 0), shadow(sw - 19, 6, 15, 15, 7.5, mix(acc, "#000000", 0.3), 3, 0.6),
                                      (sw - 19, 4, 15, 15, 7.5, "#ffffff", "#ffffff", 0)], bg, opaque=True)
        im["sw_dis"] = im["sw_off"]
        return (m + R, m + H // 2 - 1, m + R, m + H // 2 - 1), (m + R, m + 4, m + R, m + 4), cm + CR + 2
    # skeuo: glossy fills with a dark outline and a white embossed edge underneath (iOS 6)
    m, R, H = 2, 6, 28
    W = 2 * R + 12

    def btn(fill, border):
        return raster(W + 2 * m, H + 2 * m, [(m, m + 1, W, H, R, "#ffffff", "#ffffff", 0),
                                             (m, m, W, H, R, fill, border, 1)], bg, opaque=True)
    acc_border = mix(acc, "#000000", 0.35)
    im.update(btn=btn(fills["btn"], btn_border), btn_hover=btn(fills["btn_hover"], mix(btn_border, acc, 0.5)),
              btn_press=btn(fills["btn_press"], btn_border), btn_dis=btn(fills["btn_dis"], mix(btn_border, bg, 0.5)),
              acc=btn(fills["acc"], acc_border), acc_hover=btn(fills["acc_hover"], acc_border),
              acc_press=btn(fills["acc_press"], acc_border), acc_dis=btn(fills["acc_dis"], mix(acc_border, bg, 0.5)))
    im["tog_sel"] = im["acc"]
    cm, CR = 3, 10
    CW = 2 * CR + 2 * cm + 10
    im["card"] = raster(CW, CW, [(cm, cm + 1, CW - 2 * cm, CW - 2 * cm, CR, "#ffffff", "#ffffff", 0),
                                 (cm, cm, CW - 2 * cm, CW - 2 * cm, CR, s["card"], s["border"], 1)], bg, opaque=True)
    return (m + R + 1, m + H // 2 - 1, m + R + 1, m + H // 2 - 1), (m + R + 4, m + 4, m + R + 4, m + 4), cm + CR + 2


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
        # switch: track 40x22, knob (iOS-style skins use green for "on")
        sw, sh = 40, 22
        on = s.get("switch_on", s["accent"])
        knob = s.get("switch_knob", s["on_accent"])
        im["sw_off"] = raster(sw, sh, [(0, 0, sw, sh, 11, s["field"], s["muted"], 1.2),
                                       (5, 5, 12, 12, 6, s["muted"], s["muted"], 0)], card)
        im["sw_on"] = raster(sw, sh, [(0, 0, sw, sh, 11, on, on, 0),
                                      (sw - 18, 4, 14, 14, 7, knob, knob, 0)], card)
        im["sw_dis"] = raster(sw, sh, [(0, 0, sw, sh, 11, s["field"], mix(s["muted"], card, 0.5), 1),
                                       (5, 5, 12, 12, 6, mix(s["muted"], card, 0.5), s["muted"], 0)], card)
        vb = (bh_ // 2 - 1) if glossy else R + 2
        b = (R + 2, vb, R + 2, vb)
        p = (R + 4, 4, R + 4, 4)  # content inset (independent of the stretch border)
        cb = max(r, 2) + 4
        if s.get("style") in ("neu", "clay", "skeuo"):
            b, p, cb = _morph_images(s, im, fills, btn_border)
        im.setdefault("tog_sel", im["acc"])
        imgs[name] = im
        st.element_create("Skin.Button.border", "image", im["btn"], ("disabled", im["btn_dis"]),
                          ("pressed", im["btn_press"]), ("active", im["btn_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Accent.border", "image", im["acc"], ("disabled", im["acc_dis"]),
                          ("pressed", im["acc_press"]), ("active", im["acc_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Toggle.border", "image", im["btn"], ("disabled", im["btn_dis"]),
                          ("selected", im["tog_sel"]), ("pressed", im["btn_press"]), ("active", im["btn_hover"]),
                          border=b, padding=p, sticky="nsew")
        st.element_create("Skin.Card.border", "image", im["card"], border=cb, sticky="nsew")
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
    st.map("Toggle.TButton", foreground=[("selected", s.get("toggle_sel_fg", s["on_accent"])), ("disabled", muted)])
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
    border = skin.get("border", skin["muted"])
    canvas.configure(bg=bg)
    if skin.get("glass"):  # hint of what shows through the glass
        for i, c in enumerate(("#ff375f", "#0a84ff", "#30d158")):
            x = w * (0.35 + 0.22 * i)
            canvas.create_oval(x - 16, h * 0.15, x + 16, h * 0.15 + 32, fill=mix(c, bg, 0.55), width=0)
    sb = int(w * 0.22)
    canvas.create_rectangle(0, 0, sb, h, fill=side, width=0)
    for i in range(4):
        y = 8 + i * 8
        canvas.create_rectangle(4, y, sb - 4, y + 3, fill=acc if i == 1 else skin["muted"], width=0)
    x0 = sb + 6
    if skin.get("gradient"):
        for i in range(16):
            canvas.create_rectangle(sb + i * (w - sb) / 16.0, 0, sb + (i + 1) * (w - sb) / 16.0 + 1, 2,
                                    fill=mix(acc, skin["accent2"], i / 15.0), width=0)
    canvas.create_rectangle(x0, 7, w - 8, 10, fill=skin["fg"], width=0)
    canvas.create_rectangle(x0, 13, w - 20, 15, fill=skin["muted"], width=0)
    style = skin.get("style")
    cy0, cy1 = 20, h - 13
    if style == "neu":  # raised card: light top-left, shadow bottom-right
        canvas.create_rectangle(x0 + 2, cy0 + 2, w - 6, cy1 + 2, fill=skin.get("shadow_dark", border), width=0)
        canvas.create_rectangle(x0 - 1, cy0 - 1, w - 9, cy1 - 1, fill="#ffffff", width=0)
        canvas.create_rectangle(x0, cy0, w - 8, cy1, fill=bg, width=0)
    elif style == "clay":
        canvas.create_rectangle(x0 + 1, cy0 + 3, w - 7, cy1 + 3, fill=skin.get("shadow_dark", border), width=0)
        canvas.create_rectangle(x0, cy0, w - 8, cy1, fill=bg, outline="#ffffff", width=1)
    else:
        canvas.create_rectangle(x0, cy0, w - 8, cy1, outline=border, width=1,
                                fill=mix(bg, "#ffffff", 0.06) if skin.get("glass") else "")
    bx1 = x0 + int((w - 8 - x0) * 0.45)
    canvas.create_rectangle(x0 + 4, cy0 + 5, bx1, cy0 + 12, fill=acc, width=0)
    if skin.get("gloss"):
        canvas.create_rectangle(x0 + 4, cy0 + 5, bx1, cy0 + 8, fill=mix(acc, "#ffffff", 0.45), width=0)
    canvas.create_rectangle(bx1 + 4, cy0 + 5, w - 12, cy0 + 12, outline=border, width=1)
    canvas.create_text(x0 + (w - x0) / 2 - 4, h - 6, text=skin["name"], fill=skin["fg"], font=(label_font, 7, "bold"))
    if selected:
        canvas.create_rectangle(1, 1, w - 2, h - 2, outline=acc, width=3)


def hue_cycle(t):
    """RGB-cycling colour for Gamer (t: any float)."""
    r, g, b = colorsys.hsv_to_rgb(t % 1.0, 0.85, 1.0)
    return rgb2hex((r * 255, g * 255, b * 255))
