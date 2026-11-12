"""
ui/icons.py
-----------
Crisp line icons drawn on the fly with Pillow (no icon font / image files
needed, so the frozen .exe stays self-contained). Every icon is rendered in
both the light and dark colour so it follows the theme automatically.
"""
from __future__ import annotations

from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui import theme

SS = 4  # supersampling factor for smooth edges


def _mask(name: str, size: int) -> Image.Image:
    n = size * SS
    m = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(m)
    lw = max(3, int(n * 0.085))
    u = lambda v: v * n  # noqa: E731 - unit coords -> pixels

    def line(pts, w=None):
        pts = [(u(x), u(y)) for x, y in pts]
        w = w or lw
        d.line(pts, fill=255, width=w, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)

    def circ(cx, cy, r, fill=False, w=None):
        d.ellipse((u(cx - r), u(cy - r), u(cx + r), u(cy + r)),
                  outline=255, width=w or lw, fill=255 if fill else None)

    def rrect(x0, y0, x1, y1, r):
        d.rounded_rectangle((u(x0), u(y0), u(x1), u(y1)), radius=u(r), outline=255, width=lw)

    def arc(box, a0, a1):
        d.arc(tuple(u(v) for v in box), a0, a1, fill=255, width=lw)

    def poly(pts):
        line(pts + [pts[0]])

    if name == "sun":
        circ(.5, .5, .17)
        import math
        for i in range(8):
            a = math.pi / 4 * i
            line([(.5 + .30 * math.cos(a), .5 + .30 * math.sin(a)),
                  (.5 + .42 * math.cos(a), .5 + .42 * math.sin(a))])
    elif name == "moon":
        d.ellipse((u(.16), u(.16), u(.84), u(.84)), fill=255)
        d.ellipse((u(.38), u(.08), u(1.0), u(.70)), fill=0)
    elif name == "chat":
        rrect(.14, .16, .86, .70, .16)
        line([(.34, .70), (.28, .86), (.52, .70)])
    elif name == "bell":
        arc((.26, .14, .74, .62), 180, 360)
        line([(.26, .38), (.20, .68)])
        line([(.74, .38), (.80, .68)])
        line([(.16, .70), (.84, .70)])
        arc((.42, .72, .58, .90), 0, 180)
    elif name == "paperclip":
        arc((.34, .10, .66, .42), 180, 360)       # outer top
        line([(.34, .26), (.34, .70)])
        arc((.34, .58, .66, .90), 0, 180)         # outer bottom
        line([(.66, .74), (.66, .34)])
        arc((.46, .26, .66, .46), 180, 360)       # inner top
        line([(.46, .36), (.46, .66)])
    elif name == "note":
        rrect(.20, .14, .80, .86, .08)
        line([(.32, .36), (.68, .36)])
        line([(.32, .52), (.68, .52)])
        line([(.32, .68), (.52, .68)])
    elif name == "bulb":
        circ(.5, .38, .24)
        line([(.36, .54), (.42, .68)])
        line([(.64, .54), (.58, .68)])
        line([(.40, .68), (.60, .68)])
        line([(.43, .80), (.57, .80)])
    elif name == "research":
        rrect(.12, .16, .88, .68, .07)
        line([(.5, .68), (.5, .82)])
        line([(.34, .86), (.66, .86)])
        line([(.32, .56), (.32, .46)])
        line([(.48, .56), (.48, .36)])
        line([(.64, .56), (.64, .28)])
    elif name == "mic":
        rrect(.38, .10, .62, .56, .12)
        arc((.26, .30, .74, .74), 0, 180)
        line([(.5, .74), (.5, .88)])
        line([(.38, .88), (.62, .88)])
    elif name == "send":
        poly([(.14, .46), (.86, .14), (.62, .86), (.46, .58)])
        line([(.46, .58), (.86, .14)])
    elif name == "stop":
        d.rounded_rectangle((u(.30), u(.30), u(.70), u(.70)), radius=u(.07), fill=255)
    elif name == "gear":
        import math
        circ(.5, .5, .13)
        circ(.5, .5, .30)
        for i in range(8):
            a = math.pi / 4 * i
            line([(.5 + .30 * math.cos(a), .5 + .30 * math.sin(a)),
                  (.5 + .42 * math.cos(a), .5 + .42 * math.sin(a))], w=int(lw * 1.6))
    elif name == "logout":
        line([(.46, .16), (.20, .16), (.20, .84), (.46, .84)])
        line([(.40, .50), (.84, .50)])
        line([(.68, .34), (.84, .50), (.68, .66)])
    elif name == "chevron_down":
        line([(.24, .38), (.50, .64), (.76, .38)])
    elif name == "chevron_up":
        line([(.24, .62), (.50, .36), (.76, .62)])
    elif name == "dots":
        for y in (.22, .5, .78):
            circ(.5, y, .07, fill=True)
    elif name == "plus":
        line([(.5, .20), (.5, .80)])
        line([(.20, .5), (.80, .5)])
    elif name == "close":
        line([(.24, .24), (.76, .76)])
        line([(.76, .24), (.24, .76)])
    elif name == "code":
        line([(.36, .30), (.16, .50), (.36, .70)])
        line([(.64, .30), (.84, .50), (.64, .70)])
        line([(.56, .22), (.44, .78)])
    elif name == "grid":
        rrect(.16, .16, .84, .84, .07)
        line([(.5, .16), (.5, .84)])
        line([(.16, .5), (.84, .5)])
    elif name == "pen":
        poly([(.20, .80), (.28, .58), (.66, .20), (.80, .34), (.42, .72)])
        line([(.56, .30), (.70, .44)])
    elif name == "globe":
        circ(.5, .5, .36)
        d.ellipse((u(.34), u(.14), u(.66), u(.86)), outline=255, width=lw)
        line([(.14, .5), (.86, .5)])
    elif name == "lines":
        rrect(.20, .12, .80, .88, .08)
        line([(.32, .34), (.68, .34)])
        line([(.32, .50), (.68, .50)])
        line([(.32, .66), (.54, .66)])
    elif name == "sparkle":
        poly([(.5, .10), (.58, .42), (.90, .50), (.58, .58), (.5, .90),
              (.42, .58), (.10, .50), (.42, .42)])
    elif name == "mail":
        rrect(.12, .24, .88, .76, .07)
        line([(.14, .30), (.5, .58), (.86, .30)])
    elif name == "book":
        rrect(.20, .12, .80, .88, .06)
        line([(.34, .12), (.34, .88)])
        line([(.46, .34), (.68, .34)])
    elif name == "bars":
        line([(.28, .80), (.28, .52)])
        line([(.50, .80), (.50, .26)])
        line([(.72, .80), (.72, .42)])
    elif name == "user":
        circ(.5, .34, .17)
        arc((.20, .56, .80, 1.12), 180, 360)
    elif name == "trash":
        line([(.20, .28), (.80, .28)])
        line([(.40, .28), (.40, .16), (.60, .16), (.60, .28)])
        line([(.28, .28), (.32, .86), (.68, .86), (.72, .28)])
        line([(.46, .42), (.46, .72)])
        line([(.56, .42), (.56, .72)])
    elif name == "copy":
        rrect(.34, .34, .84, .86, .07)
        line([(.62, .34), (.62, .20), (.16, .20), (.16, .66), (.34, .66)])
    elif name == "check":
        line([(.20, .52), (.42, .72), (.80, .30)])
    elif name == "download":
        line([(.5, .14), (.5, .62)])
        line([(.32, .46), (.5, .64), (.68, .46)])
        line([(.18, .72), (.18, .86), (.82, .86), (.82, .72)])
    elif name == "plug":
        rrect(.28, .36, .72, .64, .09)
        line([(.40, .36), (.40, .16)])
        line([(.60, .36), (.60, .16)])
        line([(.50, .64), (.50, .78), (.70, .78), (.70, .90)])
    elif name == "history":
        circ(.5, .5, .36)
        line([(.5, .28), (.5, .5), (.66, .6)])
    return m.resize((size, size), Image.LANCZOS)


def render(name: str, size: int, color: str) -> Image.Image:
    """PIL RGBA icon of `size` px in `color` (hex)."""
    mask = _mask(name, size)
    img = Image.new("RGBA", (size, size), color)
    img.putalpha(mask)
    return img


@lru_cache(maxsize=None)
def icon(name: str, size: int = 20, color: str | None = None) -> ctk.CTkImage:
    """Theme-aware CTkImage (rendered at 2x for crisp HiDPI)."""
    px = size * 2
    if color:
        light = dark = render(name, px, color)
    else:
        light = render(name, px, theme.PALETTES["Light"]["icon"])
        dark = render(name, px, theme.PALETTES["Dark"]["icon"])
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))
