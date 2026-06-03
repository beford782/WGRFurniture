#!/usr/bin/env python3
"""Resolve real WG&R CDN product images for the placeholder slots via the
public sitemap.xml (which pairs each product page with its <image:loc> CDN URL),
then download the chosen image to incoming/images/{mattresses,accessories}.

LOCAL spec demo only; manufacturer imagery is permission-pending.

Usage: python fetch_real_images.py [--astor]
  --astor also fills the two Astor Park house-brand slots (Tranquility/Eminence)
  with the real Astor Park *Obsidian* photos (see note below).
"""
import os, re, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SM = os.path.join(HERE, "sitemap.xml")
MATT_DIR = os.path.join(HERE, "images", "mattresses")
ACC_DIR = os.path.join(HERE, "images", "accessories")

# chosen product-page slug -> dest stem (mattress stem = lower(name), acc stem = id)
MATT = {
    "tempur-adapt-20-medium-twin-mattress":                 "adapt 2.0 medium",
    "tempur-pro-breeze-20-medium-hybrid-twin-xl-mattress":  "pro breeze 2.0 medium hybrid",
    "tempur-luxe-breeze-20-firm-twin-xl-mattress":          "luxe breeze 2.0 firm",
    "pranasleep-asha-luxe-plush-twin-mattress":             "asha luxe plush",
    "beautyrest-black-series-three-medium-twin-xl-mattress":"black series three medium",
    "smartlife-by-king-koil-lotus-20-queen-mattress":       "smartlife lotus 2.0",
    "purple-twin-mattress":                                 "purple mattress",
    "purple-restore-firm-twin-xl-mattress":                 "restore firm",
    "casper-snow-30-twin-xl-hybrid-mattress":               "snow 3.0 hybrid",
    "casper-dream-twin-hybrid-mattress":                    "dream hybrid",
    "sealy-brenham-2-medium-twin-xl-mattress":              "brenham 2 medium",
    "sealy-high-point-2-firm-hybrid-twin-xl-mattress":      "high point 2 firm",
    "beautyrest-black-series-one-firm-twin-xl-mattress":    "black series one firm",
    "sealy-moreland-avenue-plush-special-purchase-twin-mattress": "moreland avenue plush",
    "wg-r-factory-direct-drake-twin-mattress":              "drake",
    "beautysleep-dreamweaver-medium-euro-top-full-mattress":"dreamweaver medium euro top",
}
# Astor Park: demo names Tranquility/Eminence don't exist on the site. Renamed to
# real WG&R Astor Park models, each with its real CDN photo and a distinct image
# (Midnight Bliss -> plush slot, Obsidian -> firm slot). Filled when --astor passed.
MATT_ASTOR = {
    "astor-park-midnight-bliss-plush-twin-mattress":        "midnight bliss plush",
    "astor-park-obsidian-firm-twin-mattress":               "obsidian firm",
}
ACC = {
    "wg-r-factory-direct-slate-twin-foundation":            "foundation-wgr-slate",
    "wg-r-factory-direct-slate-queen-low-profile-foundation":"foundation-wgr-slate-lowpro",
    "twin-size-bunkie-board":                               "bunkie-wgr",
    "purple-waterproof-standard-twin-mattress-protector":   "protector-purple-waterproof",
    "tempur-protect-breeze-twin-mattress-protector":        "protector-tempur-breeze",
}

def load_pairs():
    xml = open(SM, encoding="utf-8").read()
    pairs = {}
    for b in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", b)
        img = re.search(r"<image:loc>([^<]+)</image:loc>", b)
        if not (loc and img):
            continue
        segs = [s for s in loc.group(1).rstrip("/").split("/") if s]
        slug = next((s.lower() for s in reversed(segs) if re.search("[a-z]", s)), "")
        pairs[slug] = img.group(1)
    return pairs

def download(url, dest):
    # CDN 1000px variant for mattress photos
    full = url + ("?akimg=product-img-1000x1000" if url.lower().endswith((".jpg",".jpeg")) else "")
    r = subprocess.run(["curl","-sS","-L","-m","40","-o",dest,"-A","Mozilla/5.0",full],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) < 3000:
        return False, 0
    try:
        from PIL import Image
        with Image.open(dest) as im: im.verify()
    except Exception:
        return False, 0
    return True, os.path.getsize(dest)

def run(mapping, dest_dir):
    pairs = load_pairs()
    ok, miss = [], []
    for slug, stem in mapping.items():
        url = pairs.get(slug)
        if not url:
            miss.append((stem, slug, "slug not in sitemap")); continue
        # normalize ext to .jpg (CDN returns jpeg/png; convert if needed)
        tmp = os.path.join(dest_dir, "_tmp_dl")
        good, sz = download(url, tmp)
        if not good:
            if os.path.exists(tmp): os.remove(tmp)
            miss.append((stem, slug, "download/verify failed")); continue
        dest = os.path.join(dest_dir, stem + ".jpg")
        from PIL import Image
        with Image.open(tmp) as im:
            im.convert("RGB").save(dest, "JPEG", quality=88, optimize=True)
        os.remove(tmp)
        ok.append((stem, os.path.getsize(dest), url))
    return ok, miss

def main():
    do_astor = "--astor" in sys.argv
    m = dict(MATT);
    if do_astor: m.update(MATT_ASTOR)
    print("=== MATTRESSES ===")
    ok1, miss1 = run(m, MATT_DIR)
    for stem, sz, url in ok1: print(f"  [ok {sz:>7}] {stem}")
    print("=== ACCESSORIES ===")
    ok2, miss2 = run(ACC, ACC_DIR)
    for stem, sz, url in ok2: print(f"  [ok {sz:>7}] {stem}")
    miss = miss1 + miss2
    print(f"\nDOWNLOADED {len(ok1)+len(ok2)} real image(s); {len(miss)} miss")
    for stem, slug, why in miss:
        print(f"  MISS: {stem}  <- {slug}  ({why})")
    if not do_astor:
        print("\nNOTE: 2 Astor Park slots (tranquility plush / eminence firm) NOT filled.")
        print("      Demo names don't exist on site; real line is 'Astor Park Obsidian'.")
        print("      Re-run with --astor to fill them from Obsidian Plush/Firm photos.")

if __name__ == "__main__":
    main()
