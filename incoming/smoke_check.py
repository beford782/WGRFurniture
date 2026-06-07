#!/usr/bin/env python3
"""Structural smoke for the WGR local bundle: validate the files the app fetches,
confirm every referenced image exists on disk, and report tier/feature coverage.
Does NOT drive the browser (no interactive quiz/drawer click-through)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems, notes = [], []

def jload(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        problems.append(f"missing {rel}")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

# shared/runtime files present?
for rel in ["index.html", "manifest.json", "data/store-config.json",
            "data/mattresses.json", "data/accessories.json",
            "data/allowed-hosts.js", "data/dict-en.json"]:
    if not os.path.exists(os.path.join(ROOT, rel)):
        problems.append(f"missing runtime file {rel}")

cfg = jload("data/store-config.json")
if cfg:
    if cfg.get("storeName") != "WG&R Furniture": problems.append(f"storeName={cfg.get('storeName')!r}")
    if cfg.get("languages") != ["en", "es"]: problems.append(f"languages={cfg.get('languages')!r}")
    if cfg.get("allowedHosts") != ["beford782.github.io"]: problems.append(f"allowedHosts={cfg.get('allowedHosts')!r}")
    if (cfg.get("gasUrl") or "") != "": notes.append(f"gasUrl set unexpectedly: {cfg.get('gasUrl')!r}")
    if cfg.get("colors", {}).get("storePrimary") != "#B12D15": problems.append("storePrimary != #B12D15")
    notes.append(f"brands in config: {len(cfg.get('brands', []))}")

ah = os.path.join(ROOT, "data/allowed-hosts.js")
if os.path.exists(ah):
    if "beford782.github.io" not in open(ah, encoding="utf-8").read():
        problems.append("allowed-hosts.js missing host")

mj = jload("data/mattresses.json")
if mj:
    counts = {t: len(mj.get(t, [])) for t in ("gold", "silver", "bronze")}
    total = sum(counts.values())
    notes.append(f"mattresses: total={total} {counts}")
    if total != 26: problems.append(f"expected 26 mattresses, got {total}")
    if counts != {"gold": 9, "silver": 10, "bronze": 7}: problems.append(f"tier counts {counts}")
    miss_img, blank_url, no_feat = [], [], []
    for t in ("gold", "silver", "bronze"):
        for m in mj.get(t, []):
            url = m.get("imageUrl") or ""
            if not url:
                blank_url.append(m.get("id"))
            elif not os.path.exists(os.path.join(ROOT, url)):
                miss_img.append(f"{m.get('id')}:{url}")
            if not m.get("features"):
                no_feat.append(m.get("id"))
    if blank_url: problems.append(f"blank imageUrl: {blank_url}")
    if miss_img: problems.append(f"imageUrl file missing: {miss_img}")
    if no_feat: problems.append(f"no features (scoring): {no_feat}")
    locally = [m.get("id") for t in mj for m in mj[t] if m.get("locallyMade")]
    notes.append(f"locallyMade=yes: {sorted(locally)}")

acc = jload("data/accessories.json")
if acc is not None:
    notes.append(f"accessories: {len(acc)}")
    if len(acc) != 12: problems.append(f"expected 12 accessories, got {len(acc)}")
    cats = {}
    bad_path, miss = [], []
    for a in acc:
        cats[a.get("category", {}).get("en") if isinstance(a.get("category"), dict) else a.get("category")] = \
            cats.get(a.get("category", {}).get("en") if isinstance(a.get("category"), dict) else a.get("category"), 0) + 1
        img = a.get("image", "")
        if not img.startswith("images/accessories/") or not img.endswith(".jpg"):
            bad_path.append(f"{a.get('id')}:{img}")
        elif not os.path.exists(os.path.join(ROOT, img)):
            miss.append(f"{a.get('id')}:{img}")
    notes.append(f"accessory categories: {cats}")
    if bad_path: problems.append(f"bad accessory image path: {bad_path}")
    if miss: problems.append(f"accessory image file missing: {miss}")
    # adjustable base present? (hero requirement)
    adj = [a.get("id") for a in acc if a.get("subType") == "adjustable"]
    notes.append(f"adjustable bases (hero): {adj}")
    if not adj: problems.append("no adjustable base -> hero cannot fire")

print("=== NOTES ===")
for n in notes: print(f"  {n}")
print("=== RESULT ===")
if problems:
    print(f"  FAIL ({len(problems)} issue(s)):")
    for p in problems: print(f"   - {p}")
else:
    print("  PASS - bundle is structurally complete; every referenced image exists on disk.")
