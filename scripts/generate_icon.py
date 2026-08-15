"""Generate the Windows and PNG variants of the DNS Switcher Pro app icon."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SCALE = 4
SIZE = 256


def point(value: float) -> int:
    return round(value * SCALE)


def main() -> None:
    canvas = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    pixels = canvas.load()
    for y in range(point(8), point(248)):
        for x in range(point(8), point(248)):
            blend = min(1.0, max(0.0, ((x + y) / SCALE - 36) / 430))
            pixels[x, y] = (
                round(22 * (1 - blend) + 8 * blend),
                round(33 * (1 - blend) + 11 * blend),
                round(58 * (1 - blend) + 19 * blend),
                255,
            )
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((point(8), point(8), point(248), point(248)), radius=point(58), fill=255)
    canvas.putalpha(mask)
    draw = ImageDraw.Draw(canvas)
    cyan, violet = "#62c5ff", "#9b7cff"
    draw.arc((point(53), point(51), point(203), point(160)), 195, 342, fill=cyan, width=point(13))
    draw.line([(point(185), point(70)), (point(199), point(93)), (point(172), point(95))], fill=cyan, width=point(13), joint="curve")
    draw.arc((point(53), point(96), point(203), point(205)), 15, 162, fill=violet, width=point(13))
    draw.line([(point(71), point(186)), (point(57), point(163)), (point(84), point(161))], fill=violet, width=point(13), joint="curve")
    hexagon = [(point(128), point(98)), (point(158), point(115)), (point(158), point(149)), (point(128), point(166)), (point(98), point(149)), (point(98), point(115))]
    draw.polygon(hexagon, fill="#10192b", outline="#78a8ff", width=point(7))
    draw.ellipse((point(117), point(121), point(139), point(143)), fill="#71d7ff")
    for x, y, color, edge in ((57, 105, cyan, "#d9f4ff"), (199, 151, violet, "#eee8ff")):
        draw.ellipse((point(x - 12), point(y - 12), point(x + 12), point(y + 12)), fill=edge)
        draw.ellipse((point(x - 8), point(y - 8), point(x + 8), point(y + 8)), fill=color)

    final = canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    ASSETS.mkdir(exist_ok=True)
    final.save(ASSETS / "dns-switcher-pro.png", optimize=True)
    final.save(ASSETS / "dns-switcher-pro.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    splash = Image.new("RGB", (420, 180), "#0b1020")
    splash_pixels = splash.load()
    for y in range(180):
        for x in range(420):
            blend = min(1.0, (x + y) / 600)
            splash_pixels[x, y] = (
                round(15 * (1 - blend) + 8 * blend),
                round(23 * (1 - blend) + 11 * blend),
                round(42 * (1 - blend) + 19 * blend),
            )
    splash_icon = final.resize((112, 112), Image.Resampling.LANCZOS)
    splash.paste(splash_icon, (22, 28), splash_icon)
    splash_draw = ImageDraw.Draw(splash)
    fonts = Path("C:/Windows/Fonts")
    try:
        title_font = ImageFont.truetype(str(fonts / "segoeuib.ttf"), 25)
        pro_font = ImageFont.truetype(str(fonts / "segoeuib.ttf"), 13)
        small_font = ImageFont.truetype(str(fonts / "segoeui.ttf"), 11)
    except OSError:
        title_font = pro_font = small_font = ImageFont.load_default()
    splash_draw.text((154, 43), "DNS SWITCHER", font=title_font, fill="#edf2ff")
    splash_draw.text((155, 78), "PRO", font=pro_font, fill="#9b7cff")
    splash_draw.text((155, 103), "Controllo DNS locale", font=small_font, fill="#9aa7bd")
    splash_draw.line((154, 128, 392, 128), fill="#25304a", width=1)
    splash.save(ASSETS / "startup-splash.png", optimize=True)
    print(f"Icone generate in {ASSETS}")


if __name__ == "__main__":
    main()
