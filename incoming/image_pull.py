#!/usr/bin/env python3
"""Acquire source images for the WG&R local demo.

For each of the 26 mattresses and 12 accessories:
  * if we have a known WG&R CDN image URL -> download it (1000px) and verify it
    is a real image; else
  * generate a clean labeled placeholder (WG&R red) so the bundle still builds.

Mattress source filename = lower(name).<ext>  (converter matches by lower(name))
Accessory source filename = <id>.<ext>         (converter matches by basename)

Outputs to incoming/images/{mattresses,accessories}. Reports real vs placeholder.
This is a LOCAL spec demo; all manufacturer imagery is permission-pending.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_wgr_workbook as wgr  # reuse the approved M (mattresses) + A (accessories)

from PIL import Image, ImageDraw, ImageFont

MATT_DIR = os.path.join(HERE, "images", "mattresses")
ACC_DIR = os.path.join(HERE, "images", "accessories")
os.makedirs(MATT_DIR, exist_ok=True)
os.makedirs(ACC_DIR, exist_ok=True)

CDN = "https://wgrco.bp-cdn.net/images/"
AK = "?akimg=product-img-1000x1000"

# Known direct CDN image URLs captured during recon (stem = lower(name)).
DIRECT_MATT = {
    "lux estate firm":      CDN + "product/bedding-no-discount_2200287_2246345.jpg" + AK,
    "reserve medium":       CDN + "product/bedding-no-discount_2006977_2248129.jpg" + AK,
    "classic 5.1":          CDN + "product/bedding-no-discount_4875022_2330144.jpg" + AK,
    "classic 5.1 hybrid":   CDN + "product/bedding-no-discount_6986216_2524737.jpeg" + AK,
    "luxe 5.1 hybrid":      CDN + "product/bedding-no-discount_3097008_2524588.jpeg" + AK,
    "classic hybrid":       CDN + "product/bedding-no-discount_0618628_2372017.jpg" + AK,
    "hybrid premier":       CDN + "product/bedding-no-discount_5895062_2524640.jpeg" + AK,
    "rejuvenate":           CDN + "content/REJUV%20USE_2530205.png",
}
# Accessory direct URLs (stem = id).
DIRECT_ACC = {
    "base-bedtech-relax":                 CDN + "product/adjustable-bases_0235594_2245407.jpg" + AK,
    "base-tempur-ergo-smart":             CDN + "product/bedding-no-discount_7331319_2247356.jpg" + AK,
    "base-purple-premium-plus":           CDN + "product/bedding-no-discount_5803490_2254895.jpg" + AK,
    "pillow-tempur-breeze-prolo":         CDN + "product/pillows_6503768_2333580.jpg" + AK,
    "pillow-tempur-proadjust":            CDN + "product/pillows_5102049_2333574.jpg" + AK,
    "pillow-cooltech-graphite":           CDN + "product/pillows_2081021_2245110.jpg" + AK,
    "protector-healthy-sleep-encasement": CDN + "product/treated-mattress-pad_584249_2252700.jpg" + AK,
    "protector-purple-waterproof":        CDN + "content/Power%20Buy_MC_2368669.png",
}

RED = (177, 45, 21)

def _font(size):
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except Exception:
        try:
            return ImageFont.load_default(size)
        except Exception:
            return ImageFont.load_default()

def make_placeholder(path, line1, line2):
    img = Image.new("RGB", (1000, 1000), RED)
    d = ImageDraw.Draw(img)
    f1, f2 = _font(58), _font(40)
    def center(text, font, y):
        w = d.textbbox((0, 0), text, font=font)[2]
        d.text(((1000 - w) / 2, y), text, fill=(255, 255, 255), font=font)
    center(line1, f1, 430)
    center(line2, f2, 510)
    center("[demo placeholder]", _font(28), 600)
    img.save(path, "JPEG", quality=88)

def download(url, dest):
    """curl -> dest; verify it's a real image. Returns True on success."""
    try:
        r = subprocess.run(["curl", "-sS", "-L", "-m", "30", "-o", dest, url],
                           capture_output=True, text=True, timeout=40)
        if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) < 2000:
            return False
        with Image.open(dest) as im:
            im.verify()
        return True
    except Exception:
        return False

def acquire(stem, ext_url, dest_dir, label1, label2):
    """Try the known URL; fall back to placeholder. Returns ('real'|'placeholder', bytes)."""
    if ext_url:
        ext = ".png" if ".png" in ext_url.split("?")[0].lower() else ".jpg"
        dest = os.path.join(dest_dir, stem + ext)
        if download(ext_url, dest):
            return "real", os.path.getsize(dest)
        # clean a failed partial
        if os.path.exists(dest):
            os.remove(dest)
    dest = os.path.join(dest_dir, stem + ".jpg")
    make_placeholder(dest, label1, label2)
    return "placeholder", os.path.getsize(dest)

def main():
    real, ph = [], []
    print("=== Mattresses ===")
    for t in wgr.M:
        name, brand = t[2], t[3]
        stem = name.lower()
        kind, sz = acquire(stem, DIRECT_MATT.get(stem), MATT_DIR, brand, name)
        (real if kind == "real" else ph).append(f"{name} ({brand})")
        print(f"  [{kind:11}] {stem}.* ({sz} bytes)")
    print("=== Accessories ===")
    for a in wgr.A:
        aid, name = a[0], a[1]
        kind, sz = acquire(aid, DIRECT_ACC.get(aid), ACC_DIR, name.split()[0], name)
        (real if kind == "real" else ph).append(f"{name}")
        print(f"  [{kind:11}] {aid}.* ({sz} bytes)")
    print(f"\nSUMMARY: {len(real)} real image(s), {len(ph)} placeholder(s)")
    print("PLACEHOLDERS (need real images before any client-facing use):")
    for p in ph:
        print(f"  - {p}")

if __name__ == "__main__":
    main()
