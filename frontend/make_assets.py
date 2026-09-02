from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter


BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
ASSET_DIR.mkdir(exist_ok=True)


def tomato(draw, x, y, r, color):
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=(135, 29, 29), width=2)
    draw.polygon(
        [(x, y - r - 7), (x - 8, y - r + 5), (x + 8, y - r + 5)],
        fill=(38, 112, 55),
    )
    draw.ellipse((x - r // 3, y - r // 3, x - r // 8, y - r // 8), fill=(255, 139, 112))


def make_market_image(path, width, height, seed, title=False):
    rng = Random(seed)
    img = Image.new("RGB", (width, height), (237, 245, 235))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        shade = int(235 - y * 32 / height)
        draw.line((0, y, width, y), fill=(shade, min(246, shade + 10), shade))

    draw.rectangle((0, int(height * 0.54), width, height), fill=(194, 147, 91))
    draw.rectangle((0, int(height * 0.58), width, height), fill=(170, 119, 68))

    crate_count = 4 if width > 900 else 3
    crate_w = width // crate_count - 26
    base_y = int(height * 0.54)

    for i in range(crate_count):
        x0 = 18 + i * (crate_w + 24)
        y0 = base_y + rng.randint(-20, 20)
        x1 = x0 + crate_w
        y1 = y0 + int(height * 0.26)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=10, fill=(132, 83, 43), outline=(88, 54, 28), width=3)
        draw.rectangle((x0 + 8, y0 + 16, x1 - 8, y0 + 28), fill=(184, 126, 67))
        draw.rectangle((x0 + 8, y0 + 54, x1 - 8, y0 + 66), fill=(184, 126, 67))

        cols = max(4, crate_w // 48)
        rows = 3
        for row in range(rows):
            for col in range(cols):
                tx = x0 + 28 + col * ((crate_w - 50) // max(1, cols - 1)) + rng.randint(-5, 5)
                ty = y0 + 44 + row * 38 + rng.randint(-5, 5)
                tomato(draw, tx, ty, rng.randint(14, 19), rng.choice([(204, 47, 39), (226, 73, 49), (184, 38, 35)]))

    if title:
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle((0, 0, width, height), fill=(0, 0, 0, 38))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=115, threshold=3))
    img.save(ASSET_DIR / path, quality=92)


make_market_image("tomato-hero.png", 1200, 720, 5, True)
make_market_image("tomato-crates.png", 700, 500, 11)
make_market_image("market-compare.png", 700, 500, 19)
make_market_image("produce-signal.png", 700, 500, 29)

print(f"Created assets in {ASSET_DIR}")
