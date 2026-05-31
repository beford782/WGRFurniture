#!/usr/bin/env python3
"""Golden-bundle harness runner - phase-aware (S2-S6 active, full flow).

Phase 0 plan: docs/phase0-onboarding-pipeline-spec-2026-05-31.md section4
("S1 harness structure" + staged activation).

End-to-end (the full golden bundle):

    build_bel_workbook -> Bel.xlsx (temp workspace)
        -> [converter]       -> mattresses.csv(+es)                [S2]
                              -> store-config.json, accessories.json [S3]
                              -> normalized images (jpg)             [S4]
                              -> manifest.json                       [S5]
                              -> data/allowed-hosts.js               [S6]
        -> [build-data.ps1]  -> mattresses.json (in workspace)       [S4]
        -> canonical compare generated outputs vs committed data/ + manifest.json

The converter runs into a temp workspace with --source-images <repo>/images,
producing CSVs, JSON, normalized JPGs, manifest.json, and allowed-hosts.js. We
then copy build-data.ps1 into the workspace and run it (pwsh/powershell) to
regenerate mattresses.json, and canonically compare all outputs to the committed
files: CSVs (S2), store-config/accessories JSON (S3), image outputs + mattresses.json
(S4), manifest.json (S5), and the parsed allowed-hosts.js array (S6). All compares
are REQUIRED.

If PowerShell is unavailable: normal mode loudly SKIPS the mattresses.json compare
(still passes if everything else passes); --strict fails.

--strict: full flow; exits non-zero on any failure (including a PowerShell skip).

Never mutates repo data/ or images/ (everything goes to a tempfile workspace).
Stdlib only in this file; openpyxl/Pillow are pulled in transitively by the
fixture generator / converter.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.fixtures import build_bel_workbook  # noqa: E402
from tests.golden import canonical  # noqa: E402

CONVERTER = REPO_ROOT / "tools" / "convert_store_data.py"
SOURCE_IMAGES = REPO_ROOT / "images"
IMAGE_LONG_EDGE = 1000

CSV_COMPARES = ["mattresses.csv", "mattresses-es.csv"]
JSON_COMPARES = ["store-config.json", "accessories.json"]

# Phases not yet wired into the runner (reported as pending). Empty: S2-S6 are
# all wired - the full golden bundle is now reproduced.
PENDING_PHASES = []


def parse_allowed_hosts(path) -> list:
    """Extract the __DF_ALLOWED_HOSTS array from an allowed-hosts.js file and
    return it as a Python list (in-place parse; no canonical.py helper needed)."""
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"__DF_ALLOWED_HOSTS\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
    if not m:
        raise ValueError(f"no __DF_ALLOWED_HOSTS assignment in {path}")
    return json.loads(m.group(1))


def generate_workbook(workspace: str) -> str | None:
    wb_path = os.path.join(workspace, "bel_onboarding.xlsx")
    print(f"[prep] Generating Bel workbook fixture -> {wb_path}")
    rc = build_bel_workbook.main(["--output", wb_path])
    if rc != 0 or not os.path.exists(wb_path):
        print(f"[prep] FAIL: fixture generation rc={rc}, exists={os.path.exists(wb_path)}")
        return None
    print(f"[prep] OK: workbook present ({os.path.getsize(wb_path)} bytes)")
    print(f"[prep] OK: canonical helpers importable; "
          f"DEFAULT_ALLOWLIST empty: {canonical.DEFAULT_ALLOWLIST == []}")
    return wb_path


def run_converter(workspace: str, wb_path: str) -> bool:
    """Run the converter into the workspace: CSV + JSON + normalized images."""
    print(f"[convert] Running converter -> {workspace} "
          f"(--source-images {SOURCE_IMAGES}, --skip-build-json)")
    proc = subprocess.run(
        [sys.executable, str(CONVERTER), wb_path,
         "--output-dir", workspace, "--source-images", str(SOURCE_IMAGES),
         "--skip-build-json"],
        capture_output=True, text=True)
    if proc.stdout.strip():
        print("  " + proc.stdout.strip().replace("\n", "\n  "))
    if proc.returncode != 0:
        print(f"[convert] FAIL: converter exited {proc.returncode}")
        if proc.stderr.strip():
            print("  " + proc.stderr.strip().replace("\n", "\n  "))
        return False
    return True


def compare_outputs(workspace: str) -> canonical.CompareResult:
    """S2 CSVs (mattresses) + S3 JSON (store-config, accessories) + S5 manifest."""
    result = canonical.CompareResult()
    data = Path(workspace) / "data"
    for phase, names, fn in (("S2", CSV_COMPARES, canonical.compare_csv_files),
                             ("S3", JSON_COMPARES, canonical.compare_json_files)):
        for name in names:
            committed = REPO_ROOT / "data" / name
            generated = data / name
            if not generated.exists():
                result.differences.append(f"{name} - generated file missing at {generated}")
                result.ok = False
                print(f"[{phase}] {name}: MISSING")
                continue
            r = fn(str(committed), str(generated), label=name,
                   allowlist=canonical.DEFAULT_ALLOWLIST)
            print(f"[{phase}] {name}: {r.summary().splitlines()[0]}")
            result.merge(r)

    # S5: manifest.json lives at the workspace root, not under data/.
    committed_m = REPO_ROOT / "manifest.json"
    generated_m = Path(workspace) / "manifest.json"
    if not generated_m.exists():
        result.differences.append(f"manifest.json - generated file missing at {generated_m}")
        result.ok = False
        print("[S5] manifest.json: MISSING")
    else:
        r = canonical.compare_json_files(str(committed_m), str(generated_m),
                                         label="manifest.json",
                                         allowlist=canonical.DEFAULT_ALLOWLIST)
        print(f"[S5] manifest.json: {r.summary().splitlines()[0]}")
        result.merge(r)

    # S6: data/allowed-hosts.js - compare the parsed __DF_ALLOWED_HOSTS array.
    committed_ah = REPO_ROOT / "data" / "allowed-hosts.js"
    generated_ah = Path(workspace) / "data" / "allowed-hosts.js"
    if not generated_ah.exists():
        result.differences.append(f"allowed-hosts.js - generated file missing at {generated_ah}")
        result.ok = False
        print("[S6] allowed-hosts.js: MISSING")
    else:
        try:
            committed_hosts = parse_allowed_hosts(committed_ah)
            generated_hosts = parse_allowed_hosts(generated_ah)
        except ValueError as e:
            result.differences.append(f"allowed-hosts.js - parse error: {e}")
            result.ok = False
            print(f"[S6] allowed-hosts.js: PARSE ERROR ({e})")
        else:
            if committed_hosts == generated_hosts:
                print(f"[S6] allowed-hosts.js: [PASS] {generated_hosts}")
            else:
                result.differences.append(
                    f"allowed-hosts.js - array mismatch: committed {committed_hosts} "
                    f"vs generated {generated_hosts}")
                result.ok = False
                print(f"[S6] allowed-hosts.js: [FAIL] committed {committed_hosts} "
                      f"!= generated {generated_hosts}")
    return result


def check_s4_images(workspace: str) -> bool:
    """Verify normalized image outputs: expected filename set, all .jpg, each
    opens, long-edge<=cap. Never compares bytes or dims-vs-committed."""
    try:
        from PIL import Image
    except ImportError:
        print("[S4] FAIL: Pillow not available for image checks.")
        return False

    data = Path(workspace) / "data"
    expected = {"mattresses": set(), "accessories": set()}
    with open(data / "mattresses.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            nm = (r.get("name") or "").strip()
            if nm:
                expected["mattresses"].add(nm.lower() + ".jpg")
    for a in json.load(open(data / "accessories.json", encoding="utf-8")):
        img = a.get("image", "")
        if img:
            expected["accessories"].add(os.path.splitext(os.path.basename(img))[0] + ".jpg")

    ok = True
    for sub in ("mattresses", "accessories"):
        d = Path(workspace) / "images" / sub
        allfiles = {p.name for p in d.glob("*") if p.is_file()} if d.exists() else set()
        jpgs = {f for f in allfiles if f.lower().endswith(".jpg")}
        nonjpg = allfiles - jpgs
        exp = expected[sub]
        problems = []
        if jpgs != exp:
            problems.append(f"set mismatch missing={sorted(exp - jpgs)[:5]} "
                            f"extra={sorted(jpgs - exp)[:5]}")
        if nonjpg:
            problems.append(f"non-jpg files {sorted(nonjpg)[:5]}")
        for fn in sorted(jpgs):
            try:
                with Image.open(d / fn) as im:
                    w, h = im.size
                if max(w, h) > IMAGE_LONG_EDGE:
                    problems.append(f"{fn} over cap {(w, h)}")
            except Exception as e:  # noqa: BLE001
                problems.append(f"{fn} cannot open ({e})")
        status = "ok" if not problems else "FAIL"
        if problems:
            ok = False
        print(f"[S4] images/{sub}: {len(jpgs)} jpg (expected {len(exp)}) {status}")
        for p in problems:
            print(f"     - {p}")
    return ok


def run_s4_json(workspace: str) -> str:
    """Run workspace-local build-data.ps1 and compare mattresses.json.
    Returns 'pass' / 'fail' / 'skip' (skip = no PowerShell)."""
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if not ps:
        print("[S4] SKIP mattresses.json compare: no PowerShell (pwsh/powershell) found.")
        return "skip"
    shutil.copy(str(REPO_ROOT / "build-data.ps1"), str(Path(workspace) / "build-data.ps1"))
    script = str(Path(workspace) / "build-data.ps1")
    print(f"[S4] Running {os.path.basename(ps)} -File {script}")
    proc = subprocess.run(
        [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
        capture_output=True, text=True)
    if proc.stdout.strip():
        print("  " + proc.stdout.strip().replace("\n", "\n  "))
    if proc.returncode != 0:
        print(f"[S4] FAIL: build-data.ps1 exited {proc.returncode}")
        if proc.stderr.strip():
            print("  " + proc.stderr.strip().replace("\n", "\n  "))
        return "fail"
    gen = Path(workspace) / "data" / "mattresses.json"
    if not gen.exists():
        print("[S4] FAIL: mattresses.json was not produced.")
        return "fail"
    r = canonical.compare_json_files(str(REPO_ROOT / "data" / "mattresses.json"),
                                     str(gen), label="mattresses.json",
                                     allowlist=canonical.DEFAULT_ALLOWLIST)
    print(f"[S4] mattresses.json: {r.summary().splitlines()[0]}")
    if not r.ok:
        for d in r.differences[:10]:
            print(f"     - {d}")
    return "pass" if r.ok else "fail"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true",
                        help="Full golden flow; exit non-zero on any failure "
                             "(including a PowerShell skip of the mattresses.json compare).")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("DreamFinder golden-bundle harness (S2-S6 active - full flow)")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="dreamfinder_golden_") as workspace:
        print(f"Temp workspace: {workspace}")
        print("-" * 70)

        wb_path = generate_workbook(workspace)
        if wb_path is None:
            print("-" * 70)
            print("[FAIL] prep failed.")
            return 1

        print("-" * 70)
        converted = run_converter(workspace, wb_path)
        compares_ok = False
        s4_img_ok = False
        s4_json = "fail"
        if converted:
            result = compare_outputs(workspace)
            print(result.summary())
            compares_ok = result.ok
            print("-" * 70)
            s4_img_ok = check_s4_images(workspace)
            s4_json = run_s4_json(workspace)

        print("-" * 70)
        print(f"[S2+S3+S5+S6] {'PASS' if compares_ok else 'FAIL'}: CSV + "
              f"store-config/accessories/manifest JSON + allowed-hosts.js.")
        print(f"[S4]          images {'PASS' if s4_img_ok else 'FAIL'}; "
              f"mattresses.json compare: {s4_json.upper()}")

        print("-" * 70)
        if PENDING_PHASES:
            print("Pending phases (not yet wired):")
            for sid, what, kind in PENDING_PHASES:
                print(f"  {sid} -> {what}   [{kind}]")
        else:
            print("All phases wired (S2-S6).")
        print("-" * 70)

    # Decide outcome. S2-S6 are all wired; nothing is "pending" anymore.
    active_ok = compares_ok and s4_img_ok
    if s4_json == "fail":
        active_ok = False
    elif s4_json == "skip" and args.strict:
        active_ok = False  # strict treats a PowerShell skip as failure

    if not active_ok:
        print("[FAIL] A golden check failed"
              + (" (PowerShell required under --strict)." if s4_json == "skip" else "."))
        return 1

    note = "" if s4_json == "pass" else " (mattresses.json compare skipped - no PowerShell)"
    print(f"[PASS] Full golden bundle (S2-S6) reproduced{note}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
