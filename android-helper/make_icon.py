"""Draws Mirror's icon (assets/icon.ico + assets/icon.png). Run once; needs Pillow (dev only)."""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
S = 1024  # draw big, scale down for crisp small sizes


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def icon():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # squircle-ish rounded square with a diagonal violet -> cyan gradient
    grad = Image.new("RGB", (S, S))
    gp = grad.load()
    c1, c2 = (124, 92, 255), (34, 211, 238)
    for y in range(S):
        for x in range(0, S, 1):
            gp[x, y] = lerp(c1, c2, (x + y) / (2.0 * S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((32, 32, S - 32, S - 32), radius=230, fill=255)
    img.paste(grad, (0, 0), mask)
    # soft top sheen
    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).ellipse((-200, -620, S + 200, 470), fill=(255, 255, 255, 46))
    sheen_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen_mask).rounded_rectangle((32, 32, S - 32, S - 32), radius=230, fill=255)
    img.alpha_composite(Image.composite(sheen, Image.new("RGBA", (S, S)), sheen_mask))
    # the mirrored twin (behind, fainter), then the phone
    def phone(off_x, alpha, glow=False):
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        box = (330 + off_x, 205, 650 + off_x, 815)
        d.rounded_rectangle(box, radius=70, outline=(255, 255, 255, alpha), width=46)
        d.rounded_rectangle((box[0] + 105, box[1] + 50, box[2] - 105, box[1] + 72), radius=11,
                            fill=(255, 255, 255, alpha))
        if glow:
            g = layer.filter(ImageFilter.GaussianBlur(18))
            img.alpha_composite(g)
        img.alpha_composite(layer)
    phone(140, 110)
    phone(-40, 255, glow=True)
    return img


big = icon()
os.makedirs(ASSETS, exist_ok=True)
big.resize((256, 256), Image.LANCZOS).save(os.path.join(ASSETS, "icon.png"))
big.save(os.path.join(ASSETS, "icon.ico"), sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
                                                  (64, 64), (96, 96), (128, 128), (256, 256)])
sheet = Image.new("RGBA", (16 + 24 + 32 + 48 + 64 + 128 + 256 + 8 * 10, 260), (32, 32, 32, 255))
x = 8
for s in (16, 24, 32, 48, 64, 128, 256):
    sheet.alpha_composite(big.resize((s, s), Image.LANCZOS), (x, 250 - s))
    x += s + 10
sheet.save(os.path.join(HERE, "icon_preview.png"))
print("icon.ico / icon.png written")
