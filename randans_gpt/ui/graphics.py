"""
ui/graphics.py
--------------
Procedurally generated artwork (Pillow): welcome-screen glow, the AI orb, the
logo, gradient send button and circular avatars.
"""
from __future__ import annotations

import os

import customtkinter as ctk
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from ui import icons, theme


def _rgb(hex_color: str) -> tuple:
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def gradient_img(w: int, h: int, c0: str, c1: str) -> Image.Image:
    """Diagonal two-colour gradient."""
    v = Image.linear_gradient("L").resize((w, h))
    hz = Image.linear_gradient("L").rotate(90).resize((w, h))
    g = ImageChops.add(v, hz, scale=2)
    return ImageOps.colorize(g, _rgb(c0), _rgb(c1)).convert("RGBA")


def _circle_mask(size: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    return m


def radial_mask(size: int, power: float = 1.6, strength: float = 1.0) -> Image.Image:
    """255 at the centre, falling to exactly 0 at the inscribed circle (no square edges)."""
    t0 = 1 - 2 ** -0.5                       # PIL's gradient is 255 at the corners
    base = ImageOps.invert(Image.radial_gradient("L")).resize((size, size))
    return base.point(lambda v: int(max(0.0, (v / 255 - t0) / (1 - t0)) ** power * 255 * strength))


# --------------------------------------------------------------- welcome bg
def _glow(base: Image.Image, cx: float, cy: float, r: float, color: tuple, strength: float) -> None:
    w, h = base.size
    radius = max(2, int(r * max(w, h)))
    m = radial_mask(2 * radius, 1.3, strength)
    base.paste(Image.new("RGB", (2 * radius, 2 * radius), color),
               (int(cx * w) - radius, int(cy * h) - radius), m)


def welcome_bg(w: int, h: int, mode: str) -> Image.Image:
    """Soft green / olive glows on the panel colour (rendered small, scaled up)."""
    sw, sh = max(16, w // 6), max(16, h // 6)
    base = Image.new("RGB", (sw, sh), _rgb(theme.PALETTES[mode]["panel"]))
    if mode == "Dark":
        _glow(base, .08, .20, .55, (120, 140, 22), .34)
        _glow(base, .55, 1.0, .60, (22, 110, 55), .40)
        _glow(base, .95, .05, .30, (20, 80, 55), .20)
    else:
        _glow(base, .08, .20, .55, (205, 232, 150), .55)
        _glow(base, .55, 1.0, .60, (150, 215, 170), .50)
    return base.resize((w, h), Image.BILINEAR)


# ---------------------------------------------------------------- orb
def orb_core(px: int, mode: str) -> Image.Image:
    """Static orb layer: soft glow + dark disc with a glowing green core."""
    S = px * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow = radial_mask(S, 2.0, 0.75)
    green = Image.new("RGBA", (S, S), _rgb(theme.PALETTES[mode]["accent"]) + (0,))
    green.putalpha(glow)
    img.alpha_composite(green)
    disc = int(S * 0.36)
    off = (S - disc) // 2
    dark = "#020504" if mode == "Dark" else "#0d2a16"
    d = ImageDraw.Draw(img)
    d.ellipse((off, off, off + disc, off + disc), fill=_rgb(dark) + (255,))
    core = radial_mask(disc, 1.5, 0.8)
    c = Image.new("RGBA", (disc, disc), _rgb("#7dff8a") + (0,))
    c.putalpha(core)
    img.alpha_composite(c, (off, off))
    return img


def orb_pill(px: int, mode: str) -> Image.Image:
    """Small static orb (rings drawn as arcs) for icons."""
    S = px * 4
    img = orb_core(S // 2, mode).resize((S, S), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    for i, (inset, w, col, a0, a1) in enumerate((
            (.10, .07, theme.PALETTES[mode]["accent"], 20, 300),
            (.20, .05, theme.PALETTES[mode]["accent2"], 160, 400))):
        b = S * inset
        d.arc((b, b, S - b, S - b), a0, a1, fill=_rgb(col) + (255,), width=max(2, int(S * w)))
    return img.resize((px, px), Image.LANCZOS)


def orb_image(px: int) -> ctk.CTkImage:
    return ctk.CTkImage(light_image=orb_pill(px * 2, "Light"), dark_image=orb_pill(px * 2, "Dark"),
                        size=(px, px))


# ---------------------------------------------------------------- logo
def _logo_pil(px: int, mode: str) -> Image.Image:
    S = px * 4
    p = theme.PALETTES[mode]
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = gradient_img(S, S, p["accent"], p["accent2"])
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .26), fill=255)
    img.paste(grad, (0, 0), m)
    inset = int(S * .09)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((inset, inset, S - inset, S - inset), radius=int(S * .20), fill=_rgb(p["panel"]) + (255,))
    # a geometric "R" drawn in the gradient colours
    import math
    arrow = Image.new("L", (S, S), 0)
    ad = ImageDraw.Draw(arrow)
    w = int(S * .105)
    cx, cy, r = .53, .385, .125
    bowl = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(-90, 91, 10)]
    path = [(.35, .74), (.35, .26), (cx, .26)] + bowl + [(.35, .51)]
    leg = [(.52, .51), (.68, .74)]
    for pts in (path, leg):
        pix = [(x * S, y * S) for x, y in pts]
        ad.line(pix, fill=255, width=w, joint="curve")
        for x, y in (pix[0], pix[-1]):
            ad.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=255)
    img.paste(grad, (0, 0), arrow)
    return img.resize((px, px), Image.LANCZOS)


def logo_image(px: int) -> ctk.CTkImage:
    return ctk.CTkImage(light_image=_logo_pil(px * 2, "Light"), dark_image=_logo_pil(px * 2, "Dark"),
                        size=(px, px))


def save_logo_assets(folder: str) -> None:
    """Writes assets/logo.png and assets/icon.ico (used by the build)."""
    img = _logo_pil(256, "Dark")
    img.save(os.path.join(folder, "logo.png"))
    img.save(os.path.join(folder, "icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


# ------------------------------------------------------- send / stop button
def send_button_image(px: int, stop: bool = False) -> ctk.CTkImage:
    S = px * 4
    p = theme.PALETTES["Dark"]
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(gradient_img(S, S, p["accent"], p["accent2"]), (0, 0), _circle_mask(S))
    ic = icons.render("stop" if stop else "send", S // 2, "#04140a")
    shift = 0 if stop else int(S * .02)
    img.alpha_composite(ic, (S // 4 + shift, S // 4))
    img = img.resize((px * 2, px * 2), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(px, px))


# ---------------------------------------------------------------- avatar
def _font(px: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def avatar_pil(path: str, name: str, px: int) -> Image.Image:
    S = px * 3
    if path and os.path.exists(path):
        try:
            im = Image.open(path).convert("RGB")
            side = min(im.size)
            left, top = (im.width - side) // 2, (im.height - side) // 2
            im = im.crop((left, top, left + side, top + side)).resize((S, S), Image.LANCZOS)
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.paste(im, (0, 0), _circle_mask(S))
            return out.resize((px * 2, px * 2), Image.LANCZOS)
        except OSError:
            pass
    p = theme.PALETTES["Dark"]
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(gradient_img(S, S, p["accent"], p["accent2"]), (0, 0), _circle_mask(S))
    letter = (name.strip()[:1] or "?").upper()
    d = ImageDraw.Draw(out)
    f = _font(int(S * .5))
    box = d.textbbox((0, 0), letter, font=f)
    d.text(((S - (box[2] - box[0])) / 2 - box[0], (S - (box[3] - box[1])) / 2 - box[1]),
           letter, font=f, fill=(4, 20, 10, 255))
    return out.resize((px * 2, px * 2), Image.LANCZOS)


def avatar_image(path: str, name: str, px: int) -> ctk.CTkImage:
    img = avatar_pil(path, name, px)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(px, px))
