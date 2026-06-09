#!/usr/bin/env python3
"""DreamFinder onboarding validation (V1) - structure + Store Info / store-config.

Hard validation so a bad workbook cannot silently produce a broken DreamFinder
deployment. V1 covers the highest-value gates:

  * workbook structure: required tabs, required headers, duplicate headers,
    Store Info exactly one data row, schema-required cells non-empty.
  * store-config values: storeName, slug-safe storeKey, languages, hex colors,
    HTTPS publicAssetRoot with trailing slash, allowedHosts hygiene, discount
    digits, manifest.start_url, gasUrl placeholder policy.

Deep per-row mattress/accessory/SalesNotes checks, image-existence checks, and
post-emit output validation are LATER phases (V2/V3) - not implemented here.

"Required" is derived from `tools/workbook_schema.py` `required` flags (the curated
source of truth), NOT a broad wishlist - fields like price / quizTags / pitchKey /
subBrand / topPickReason are legitimately blank in real data and are not required.

Dependency-light: stdlib + workbook_schema only. No openpyxl, no app imports. It
validates already-parsed structures (the converter's read rows + assembled config),
so it is unit-testable with plain dicts. ASCII console output. Run `--self-test`.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Shared schema lives alongside this file in tools/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workbook_schema as schema  # noqa: E402


SUPPORTED_LANGUAGES = (["en"], ["en", "es"])
CODE_DIGITS_MIN, CODE_DIGITS_MAX = 3, 10
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# -- Report -------------------------------------------------------------------

@dataclass
class ValidationReport:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok

    def merge(self, other: "ValidationReport") -> "ValidationReport":
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self

    def blocking(self, warnings_as_errors: bool = False) -> bool:
        """True if the converter should abort: any error, or (under
        --warnings-as-errors) any warning."""
        return bool(self.errors) or (warnings_as_errors and bool(self.warnings))

    def summary(self) -> str:
        if not self.errors and not self.warnings:
            return "[validate] OK - no issues."
        lines = []
        if self.errors:
            lines.append(f"[validate] {len(self.errors)} error(s):")
            lines += [f"  ERROR: {e}" for e in self.errors]
        if self.warnings:
            lines.append(f"[validate] {len(self.warnings)} warning(s):")
            lines += [f"  WARN:  {w}" for w in self.warnings]
        return "\n".join(lines)


# -- Helpers ------------------------------------------------------------------

def _blank(v) -> bool:
    return v is None or str(v).strip() == ""


def _is_hex(v) -> bool:
    return isinstance(v, str) and bool(_HEX_RE.match(v.strip()))


def _is_slug(v) -> bool:
    return isinstance(v, str) and bool(_SLUG_RE.match(v.strip()))


def _host_from_url(url: str) -> str:
    """Extract the host from an https URL (no scheme, no path). '' if unparseable."""
    s = str(url).strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    return s.split("/", 1)[0]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


# Live accessory categories (the real enum the app/template use - NOT a generic
# lowercase list). matchScores are non-negative integers (Bel uses values up to
# 10 for the featured "default" weight, so there is no 0-5 upper bound).
ACCESSORY_CATEGORIES = {"Foundations & Support", "Pillows", "Protectors"}
# G1: the Accessories "Image File Name" cell must be the FULL relative path the live
# app renders verbatim (index.html uses accessories.json `image` as-is). A bare
# filename (or a non-jpg / extra-path value) builds clean but 404s on the deployed
# host - the live image is always normalized to <prefix><file>.jpg (TFM migration lesson).
ACCESSORY_IMAGE_PREFIX = "images/accessories/"
SOURCE_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MATTRESS_TIERS = {"gold", "silver", "bronze"}
SALESNOTE_TYPES = {"subBrand", "brand"}
SALESNOTE_FORMATS = {"full", "coaching"}


def _source_stems(src_dir: str):
    """Lowercased stems of supported images in src_dir, or None if dir missing."""
    if not os.path.isdir(src_dir):
        return None
    stems = set()
    for fn in os.listdir(src_dir):
        stem, ext = os.path.splitext(fn)
        if ext.lower() in SOURCE_IMAGE_EXTS:
            stems.add(stem.lower())
    return stems


def _source_names(src_dir: str):
    """Lowercased full filenames of supported images in src_dir, or None if the
    dir is missing. Brand logos are matched by exact filename (not stem) because
    the workbook's Logo File Name is copied verbatim into store-config, so the
    source extension must match what ships (e.g. a transparent .png logo)."""
    if not os.path.isdir(src_dir):
        return None
    names = set()
    for fn in os.listdir(src_dir):
        if os.path.splitext(fn)[1].lower() in SOURCE_IMAGE_EXTS:
            names.add(fn.lower())
    return names


def _png_dimensions(path: str):
    """Return (width, height) of a PNG by reading its IHDR header, or None if the
    file is not a valid PNG. Stdlib only - keeps validation.py Pillow-free so it
    runs in --validate-only without the imaging dependency."""
    try:
        with open(path, "rb") as f:
            header = f.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def _brands_from(raw_tabs) -> set:
    if "Brands" not in raw_tabs:
        return set()
    _, rows = raw_tabs["Brands"]
    return {_s(r.get("Brand Name")) for r in rows if _s(r.get("Brand Name"))}


# -- Structure validation (raw tabs) ------------------------------------------
# raw_tabs maps PRESENT tab name -> (headers: list[str], rows: list[dict]).
# A required tab absent from raw_tabs is reported as missing.

def validate_structure(raw_tabs: Dict[str, Tuple[List[str], List[dict]]]) -> ValidationReport:
    r = ValidationReport()
    for tab in schema.get_tab_names():
        if tab not in raw_tabs:
            r.add_error(f"missing required tab: {tab!r}")
            continue
        headers, rows = raw_tabs[tab]

        # duplicate headers
        seen = set()
        for h in headers:
            if h in seen:
                r.add_error(f"{tab}: duplicate header {h!r}")
            seen.add(h)

        # required headers present
        required = schema.required_columns(tab)
        for col in required:
            if col.name not in headers:
                r.add_error(f"{tab}: missing required header {col.name!r}")

        # Store Info: exactly one data row
        if tab == "Store Info" and len(rows) != 1:
            r.add_error(f"Store Info: expected exactly 1 data row, found {len(rows)}")

        # schema-required cells non-empty (only for headers that are present)
        for col in required:
            if col.name not in headers:
                continue
            for i, row in enumerate(rows, start=1):
                if _blank(row.get(col.name)):
                    r.add_error(f"{tab} row {i}: required {col.name!r} is empty")
    return r


# -- Store-config value validation (assembled config dict) --------------------

def validate_store_config(config: dict, manifest: Optional[dict] = None, *,
                          require_gas_url: bool = False) -> ValidationReport:
    r = ValidationReport()

    if _blank(config.get("storeName")):
        r.add_error("storeName is empty")

    sk = config.get("storeKey")
    if _blank(sk):
        r.add_error("storeKey is empty")
    elif not _is_slug(sk):
        r.add_error(f"storeKey {sk!r} is not slug-safe (lowercase letters/digits/hyphens)")

    langs = config.get("languages")
    if langs not in SUPPORTED_LANGUAGES:
        r.add_error(f"languages must be ['en'] or ['en','es'], got {langs!r}")

    colors = config.get("colors") or {}
    if not _is_hex(colors.get("storePrimary")):
        r.add_error(f"colors.storePrimary missing or not a #hex color: {colors.get('storePrimary')!r}")
    for k in ("storePrimaryLight", "accent"):
        v = colors.get(k)
        if not _blank(v) and not _is_hex(v):
            r.add_error(f"colors.{k} is not a valid #hex color: {v!r}")

    par = config.get("publicAssetRoot")
    if _blank(par):
        r.add_error("publicAssetRoot is empty")
    else:
        par = str(par).strip()
        if not par.startswith("https://"):
            r.add_error(f"publicAssetRoot must be an HTTPS URL: {par!r}")
        if not par.endswith("/"):
            r.add_error(f"publicAssetRoot must end with a trailing slash: {par!r}")

    ah = config.get("allowedHosts")
    if not isinstance(ah, list) or not ah:
        r.add_error("allowedHosts is empty (the M1 domain lock requires at least the Pages host)")
    else:
        for h in ah:
            hs = str(h)
            if "://" in hs:
                r.add_error(f"allowedHosts entry {hs!r} must not include a protocol")
            if "/" in hs:
                r.add_error(f"allowedHosts entry {hs!r} must not include a path/slash")
            if hs in ("localhost", "127.0.0.1"):
                r.add_error(f"allowedHosts must not include {hs!r} (localhost/127.0.0.1 are a built-in fallback)")
        host = _host_from_url(par) if not _blank(par) else ""
        if host and host not in ah:
            r.add_warning(f"allowedHosts {ah} does not include the publicAssetRoot host {host!r} - "
                          f"the live site will blank on that host")

    disc = config.get("discount") or {}
    cd = disc.get("codeDigits")
    if isinstance(cd, bool) or not isinstance(cd, int) or not (CODE_DIGITS_MIN <= cd <= CODE_DIGITS_MAX):
        r.add_error(f"discount.codeDigits must be an integer {CODE_DIGITS_MIN}-{CODE_DIGITS_MAX}, got {cd!r}")

    gas = str(config.get("gasUrl") or "").strip()
    is_placeholder = _blank(gas) or "example" in gas.lower() or gas.upper() in ("TODO", "PLACEHOLDER")
    if is_placeholder:
        msg = "gasUrl is blank/placeholder (set it after the Google Apps Script deploy)"
        if require_gas_url:
            r.add_error(msg)
        else:
            r.add_warning(msg)

    if manifest is not None and _blank(manifest.get("start_url")):
        r.add_error("manifest.start_url is empty")

    return r


# -- Promotions validation (scenario-aware) -----------------------------------

# Accepted evidence-status values for promotion items (provenance ladder).
PROMO_EVIDENCE_STATUSES = {
    "wgr-current-page",
    "wgr-product-page",
    "wgr-full-page-archive",
    "wgr-indexed-historical",
    "operator-reported-wgr-indexed-historical",
    "prior-research-observation",
}
# Statuses that assert the offer was seen on WG&R's own site -> a non-empty
# sourceUrl must be a wgrfurniture.com page or a web.archive.org capture whose
# embedded target is wgrfurniture.com.
PROMO_WGR_SOURCE_STATUSES = {
    "wgr-current-page", "wgr-product-page", "wgr-full-page-archive",
    "wgr-indexed-historical", "operator-reported-wgr-indexed-historical",
}
_WGR_HOST_SUFFIX = "wgrfurniture.com"


def _archive_embedded_host(url: str) -> str:
    """For a web.archive.org capture URL, return the embedded target host (''
    when not an archive URL / unparseable)."""
    m = re.search(r"web\.archive\.org/web/[^/]+/(https?://\S+)", str(url))
    return _host_from_url(m.group(1)) if m else ""


def _is_wgr_source(url: str) -> bool:
    host = _host_from_url(url)
    if host.endswith(_WGR_HOST_SUFFIX):
        return True
    if "web.archive.org" in host:
        return _archive_embedded_host(url).endswith(_WGR_HOST_SUFFIX)
    return False


def validate_promotions(config: dict, *, mattress_ids=None, accessory_ids=None,
                        accessory_categories=None) -> ValidationReport:
    """Validate the optional promotions block (scenario-aware or flat back-compat).

    Pure: takes the assembled config dict plus the known mattress/accessory id and
    accessory-category sets. No-op when there is no promotions block."""
    r = ValidationReport()
    promos = config.get("promotions")
    if not promos:
        return r
    mids = set(mattress_ids or [])
    aids = set(accessory_ids or [])
    acats = set(c for c in (accessory_categories or []) if c)

    scenarios = promos.get("scenarios")
    if scenarios is None:
        _validate_promo_scenario(r, "(flat)", promos, True, mids, aids, acats)
        return r
    if not isinstance(scenarios, dict):
        r.add_error("promotions.scenarios must be an object")
        return r
    active = promos.get("activeScenario")
    if active and active not in scenarios:
        r.add_error(f"promotions.activeScenario {active!r} is not a defined scenario "
                    f"{sorted(scenarios)}")
    for sid, sc in scenarios.items():
        if not isinstance(sc, dict):
            r.add_error(f"promotions.scenarios[{sid!r}] must be an object")
            continue
        _validate_promo_scenario(r, sid, sc, sid == active, mids, aids, acats)
    return r


def _validate_promo_scenario(r, sid, sc, is_active, mids, aids, acats):
    kind = sc.get("kind")
    items = sc.get("items") or []
    storewide = sc.get("storewide") or []

    # duplicate promotion ids within a scenario (items + storewide share an id space)
    seen = set()
    for it in list(items) + list(storewide):
        iid = it.get("id")
        if iid in seen:
            r.add_error(f"promotions[{sid}]: duplicate promotion id {iid!r}")
        else:
            seen.add(iid)

    # historical-demo guardrails
    if kind == "historical-demo":
        if sc.get("disableEmailSubmission") is not True:
            r.add_error(f"promotions[{sid}]: historical-demo scenario must set "
                        f"disableEmailSubmission=true")
        if is_active:
            disc = sc.get("disclosure") or {}
            if not (_s(disc.get("en")) and _s(disc.get("es"))):
                r.add_error(f"promotions[{sid}]: active historical-demo scenario must "
                            f"have a disclosure in EN and ES")

    for it in items:
        _validate_promo_item(r, sid, it, mids, aids, acats)
    for it in storewide:
        _validate_promo_item(r, sid, it, mids, aids, acats)


def _validate_promo_item(r, sid, it, mids, aids, acats):
    iid = it.get("id", "?")
    tag = f"promotions[{sid}].{iid}"

    # eligibility references resolve to real catalog entries
    for mid in (it.get("eligibleMattressIds") or []):
        if mids and mid not in mids:
            r.add_error(f"{tag}: eligibleMattressIds {mid!r} not in mattresses")
    for aid in (it.get("eligibleAccessoryIds") or []):
        if aids and aid not in aids:
            r.add_error(f"{tag}: eligibleAccessoryIds {aid!r} not in accessories")
    for cat in (it.get("eligibleAccessoryCategories") or []):
        if acats and cat not in acats:
            r.add_error(f"{tag}: eligibleAccessoryCategories {cat!r} not a known accessory category")

    # customer-visible bilingual copy: badge + headline must carry EN and ES
    for field in ("badge", "headline"):
        obj = it.get(field)
        if not isinstance(obj, dict) or not _s(obj.get("en")) or not _s(obj.get("es")):
            r.add_error(f"{tag}: {field} missing EN or ES")
    # detail/disclosure: if one language is present the other must be too
    for field in ("detail", "disclosure"):
        obj = it.get(field)
        if isinstance(obj, dict) and (bool(_s(obj.get("en"))) != bool(_s(obj.get("es")))):
            r.add_error(f"{tag}: {field} has one language but not the other")

    # evidence status enum + source rules
    ev = it.get("evidenceStatus")
    if ev is not None and ev not in PROMO_EVIDENCE_STATUSES:
        r.add_error(f"{tag}: evidenceStatus {ev!r} not in {sorted(PROMO_EVIDENCE_STATUSES)}")
    src = _s(it.get("sourceUrl"))
    if ev in PROMO_WGR_SOURCE_STATUSES and src and not _is_wgr_source(src):
        r.add_error(f"{tag}: sourceUrl {src!r} is not a wgrfurniture.com source "
                    f"(required for evidenceStatus {ev!r})")
    if ev == "wgr-full-page-archive" and src and not _archive_embedded_host(src).endswith(_WGR_HOST_SUFFIX):
        r.add_error(f"{tag}: wgr-full-page-archive sourceUrl must be a web.archive.org capture of wgrfurniture.com")
    if ev == "prior-research-observation" and not _s(it.get("evidenceProvenance")):
        r.add_error(f"{tag}: evidenceStatus prior-research-observation requires evidenceProvenance")

    # the reconstructed 20% storewide event must not target individual products
    # unless explicitly marked eligible
    if it.get("type") == "reconstructed-storewide" or "storewide-20" in str(iid):
        targets_products = bool(it.get("eligibleMattressIds") or it.get("eligibleAccessoryIds")
                                or it.get("eligibleAccessoryCategories"))
        if targets_products and it.get("eligibleForStorewide20") is not True:
            r.add_error(f"{tag}: 20% storewide event applied to individual products "
                        f"without eligibleForStorewide20=true")


# -- V2: catalog validation (raw tabs) ----------------------------------------

def validate_mattresses(raw_tabs, *, source_images=None, skip_images=False,
                        languages=None) -> ValidationReport:
    r = ValidationReport()
    if "Mattresses" not in raw_tabs:
        return r  # missing tab already reported by validate_structure
    headers, rows = raw_tabs["Mattresses"]
    brands = _brands_from(raw_tabs)
    es_cols = [h for h in headers if h.endswith(" (ES)")]
    check_images = bool(source_images) and not skip_images
    src_stems = None
    if check_images:
        d = os.path.join(source_images, "mattresses")
        src_stems = _source_stems(d)
        if src_stems is None:
            r.add_error(f"Mattresses: source image folder not found: {d}")

    seen_ids = {}
    seen_names = {}
    for i, row in enumerate(rows, start=1):
        mid, name, brand = _s(row.get("id")), _s(row.get("name")), _s(row.get("brand"))
        tier, fs = _s(row.get("tier")), _s(row.get("firmnessScore"))
        tag = mid or name or f"row {i}"

        if tier and tier not in MATTRESS_TIERS:
            r.add_error(f"Mattresses {tag}: tier {tier!r} not gold/silver/bronze")
        if mid:
            if mid in seen_ids:
                r.add_error(f"Mattresses: duplicate id {mid!r} (rows {seen_ids[mid]} & {i})")
            else:
                seen_ids[mid] = i
            if not _is_slug(mid):
                r.add_error(f"Mattresses {tag}: id {mid!r} is not slug-safe")
        if brand and brands and brand not in brands:
            r.add_error(f"Mattresses {tag}: brand {brand!r} is not in the Brands tab {sorted(brands)}")
        if fs:
            try:
                n = int(float(fs)) if isinstance(fs, str) else int(fs)
                if not (1 <= n <= 10):
                    r.add_error(f"Mattresses {tag}: firmnessScore {fs!r} not in 1-10")
            except (ValueError, TypeError):
                r.add_error(f"Mattresses {tag}: firmnessScore {fs!r} is not an integer")
        if name:
            key = name.lower()
            if key in seen_names:
                r.add_error(f"Mattresses: duplicate name {name!r} -> image filename "
                            f"collision (rows {seen_names[key]} & {i})")
            else:
                seen_names[key] = i
            if check_images and src_stems is not None and key not in src_stems:
                r.add_error(f"Mattresses {tag}: no source image for "
                            f"{key}.[jpg|jpeg|png|webp] in {os.path.join(source_images, 'mattresses')}")
        # ES policy (warnings only)
        if languages and "es" in languages and es_cols:
            if all(_blank(row.get(h)) for h in es_cols):
                r.add_warning(f"Mattresses {tag}: no Spanish (ES) copy (languages includes 'es')")
        elif languages and "es" not in languages and es_cols:
            if any(not _blank(row.get(h)) for h in es_cols):
                r.add_warning(f"Mattresses {tag}: Spanish (ES) copy present but languages excludes 'es'")
    return r


def validate_accessories(raw_tabs, *, source_images=None, skip_images=False,
                         languages=None) -> ValidationReport:
    r = ValidationReport()
    if "Accessories" not in raw_tabs:
        return r
    headers, rows = raw_tabs["Accessories"]
    score_headers = [h for h in headers if h.startswith("Score:")]
    check_images = bool(source_images) and not skip_images
    src_stems = None
    if check_images:
        d = os.path.join(source_images, "accessories")
        src_stems = _source_stems(d)
        if src_stems is None:
            r.add_error(f"Accessories: source image folder not found: {d}")

    seen_ids = {}
    seen_basenames = {}
    es_pairs = (("Name", "Name (ES)"), ("Category", "Category (ES)"),
                ("Description", "Description (ES)"))
    for i, row in enumerate(rows, start=1):
        aid, cat, img = _s(row.get("ID")), _s(row.get("Category")), _s(row.get("Image File Name"))
        tag = aid or _s(row.get("Name")) or f"row {i}"

        if aid:
            if aid in seen_ids:
                r.add_error(f"Accessories: duplicate id {aid!r} (rows {seen_ids[aid]} & {i})")
            else:
                seen_ids[aid] = i
            if not _is_slug(aid):
                r.add_error(f"Accessories {tag}: id {aid!r} is not slug-safe")
        if cat and cat not in ACCESSORY_CATEGORIES:
            r.add_error(f"Accessories {tag}: category {cat!r} not in {sorted(ACCESSORY_CATEGORIES)}")
        price = row.get("Price")
        if not _blank(price):
            try:
                float(str(price))
            except ValueError:
                r.add_error(f"Accessories {tag}: price {price!r} is not numeric")
        if _blank(img):
            r.add_error(f"Accessories {tag}: Image File Name is empty")
        else:
            img_s = str(img).strip()
            # G1: the cell must be the full relative path images/accessories/<file>.jpg.
            # index.html renders accessories.json `image` verbatim, so a bare filename,
            # a non-jpg extension, or an extra sub-path builds clean but 404s on the
            # live host. The normalized live file is always <prefix><basename>.jpg.
            rest = (img_s[len(ACCESSORY_IMAGE_PREFIX):]
                    if img_s.startswith(ACCESSORY_IMAGE_PREFIX) else None)
            if rest is None or not rest or "/" in rest or not rest.lower().endswith(".jpg"):
                r.add_error(f"Accessories {tag}: Image File Name {img!r} must be a full "
                            f"relative path of the form '{ACCESSORY_IMAGE_PREFIX}<file>.jpg' "
                            f"- a bare filename builds clean but 404s live (index.html "
                            f"renders it verbatim)")
            base = os.path.splitext(os.path.basename(img_s))[0].lower()
            if base in seen_basenames:
                r.add_warning(f"Accessories: duplicate image basename {base!r} "
                              f"(rows {seen_basenames[base]} & {i})")
            else:
                seen_basenames[base] = i
            if check_images and src_stems is not None and base not in src_stems:
                r.add_error(f"Accessories {tag}: no source image for "
                            f"{base}.[jpg|jpeg|png|webp] in {os.path.join(source_images, 'accessories')}")
        for h in score_headers:
            v = row.get(h)
            if _blank(v):
                continue
            try:
                n = int(str(v).strip()) if isinstance(v, str) else int(v)
                if n < 0:
                    r.add_error(f"Accessories {tag}: {h} {v!r} is negative")
            except (ValueError, TypeError):
                r.add_error(f"Accessories {tag}: {h} {v!r} is not an integer")
        # ES policy (warnings only)
        if languages and "es" in languages:
            for en_h, es_h in es_pairs:
                if not _blank(row.get(en_h)) and _blank(row.get(es_h)):
                    r.add_warning(f"Accessories {tag}: {es_h} missing (languages includes 'es')")
        elif languages and "es" not in languages:
            for _, es_h in es_pairs:
                if not _blank(row.get(es_h)):
                    r.add_warning(f"Accessories {tag}: {es_h} present but languages excludes 'es'")
    return r


def validate_brands(raw_tabs, *, source_images=None, skip_images=False) -> ValidationReport:
    """V2: Brands tab. When a brand sets a Logo File Name and --source-images is
    provided, require a matching source logo in <source-images>/brands/ (matched by
    exact filename, case-insensitive - brand logos are copied verbatim, preserving
    format/transparency). A blank Logo File Name is allowed: the app then shows the
    brand name only."""
    r = ValidationReport()
    if "Brands" not in raw_tabs:
        return r  # missing tab already reported by validate_structure
    _, rows = raw_tabs["Brands"]
    check_images = bool(source_images) and not skip_images
    src_names = None
    if check_images:
        d = os.path.join(source_images, "brands")
        src_names = _source_names(d)
        if src_names is None:
            r.add_error(f"Brands: source logo folder not found: {d}")

    seen = {}
    for i, row in enumerate(rows, start=1):
        name = _s(row.get("Brand Name"))
        logo = _s(row.get("Logo File Name"))
        tag = name or f"row {i}"
        if not logo:
            continue  # optional - app renders the brand name without a logo
        key = logo.lower()
        if key in seen:
            r.add_warning(f"Brands: duplicate Logo File Name {logo!r} "
                          f"(rows {seen[key]} & {i})")
        else:
            seen[key] = i
        if check_images and src_names is not None and key not in src_names:
            r.add_error(f"Brands {tag}: no source logo {logo!r} in "
                        f"{os.path.join(source_images, 'brands')}")
    return r


def validate_app_icon(raw_tabs, *, source_images=None, skip_images=False) -> ValidationReport:
    """V2: optional PWA app icon (Store Info "App Icon File"). Blank = no icons
    (allowed - the converter emits no manifest.icons). When set, the file must be a
    .png; and when --source-images is provided it must exist at <source-images>/
    logos/<file> and be a square PNG >= 512px (read via stdlib PNG header, no
    Pillow). Errors block the build before any icons are generated."""
    r = ValidationReport()
    if "Store Info" not in raw_tabs:
        return r
    _, rows = raw_tabs["Store Info"]
    if not rows:
        return r
    icon = _s(rows[0].get("App Icon File"))
    if not icon:
        return r  # optional - no PWA icons for this store
    # M2: icons are generated only when --source-images is provided AND image
    # normalization is not skipped. If the workbook requests an app icon but the run
    # cannot generate it, block: writing the bundle anyway would emit manifest.json
    # WITHOUT its icons array, silently stripping a deployed PWA icon set.
    if not source_images or skip_images:
        r.add_error(f"Store Info: App Icon File {icon!r} is set but PWA icons cannot "
                    f"be generated - re-run with --source-images and without "
                    f"--skip-image-normalization (otherwise manifest.json is written "
                    f"without its icons).")
    if not icon.lower().endswith(".png"):
        r.add_error(f"Store Info: App Icon File {icon!r} must be a .png")
    if bool(source_images) and not skip_images:
        src = os.path.join(source_images, "logos", icon)
        if not os.path.isfile(src):
            r.add_error(f"Store Info: App Icon File {icon!r} not found in "
                        f"{os.path.join(source_images, 'logos')}")
        else:
            dims = _png_dimensions(src)
            if dims is None:
                r.add_error(f"Store Info: App Icon File {icon!r} is not a readable PNG")
            else:
                w, h = dims
                if w != h:
                    r.add_error(f"Store Info: App Icon File {icon!r} must be square "
                                f"(got {w}x{h})")
                elif w < 512:
                    r.add_error(f"Store Info: App Icon File {icon!r} must be >= 512px "
                                f"(got {w}x{h})")
    return r


def validate_sales_notes(raw_tabs, *, languages=None) -> ValidationReport:
    r = ValidationReport()
    if "SalesNotes" not in raw_tabs:
        return r
    _, rows = raw_tabs["SalesNotes"]
    brands = _brands_from(raw_tabs)
    for i, row in enumerate(rows, start=1):
        typ, key = _s(row.get("Type")), _s(row.get("Key"))
        tag = key or f"row {i}"
        if typ and typ not in SALESNOTE_TYPES:
            r.add_error(f"SalesNotes {tag}: Type {typ!r} not subBrand/brand")
        elif typ == "subBrand":
            fmt = _s(row.get("Format"))
            if fmt not in SALESNOTE_FORMATS:
                r.add_error(f"SalesNotes {tag}: Format {fmt!r} must be full/coaching")
            elif fmt == "full":
                for f in ("Lead", "Demo", "Close"):
                    if _blank(row.get(f)):
                        r.add_error(f"SalesNotes {tag} (full): {f} is required")
            elif fmt == "coaching":
                if _blank(row.get("RSA Note")):
                    r.add_error(f"SalesNotes {tag} (coaching): RSA Note is required")
        elif typ == "brand":
            if _blank(row.get("Story")):
                r.add_error(f"SalesNotes {tag} (brand): Story is required")
            if key and brands and key not in brands:
                r.add_warning(f"SalesNotes brand note {key!r} is not a known brand {sorted(brands)}")
        # subBrand-key cross-ref intentionally NOT validated (real data has
        # pitchKey-mapped / aspirational keys that are not literal mattress
        # subBrands). ES sales-notes intentionally NOT validated (optional,
        # generated-later block).
    return r


# -- V3: post-emit output validation ------------------------------------------

def _parse_allowed_hosts_js(path: str):
    text = open(path, encoding="utf-8").read()
    m = re.search(r"__DF_ALLOWED_HOSTS\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
    if not m:
        raise ValueError("no __DF_ALLOWED_HOSTS assignment found")
    return json.loads(m.group(1))


def _csv_header(path: str):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def validate_generated_outputs(output_dir: str, *, build_json: bool = True,
                               languages=None) -> ValidationReport:
    """Validate the bundle the converter just wrote. `build_json` should reflect
    whether build-data.ps1 actually ran (and thus mattresses.json should exist)."""
    r = ValidationReport()
    data = os.path.join(output_dir, "data")

    def load_json(path, label):
        if not os.path.exists(path):
            r.add_error(f"{label}: missing ({path})")
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError) as e:
            r.add_error(f"{label}: invalid JSON ({e})")
            return None

    config = load_json(os.path.join(data, "store-config.json"), "store-config.json")

    # allowed-hosts.js array must equal store-config.allowedHosts
    ah_path = os.path.join(data, "allowed-hosts.js")
    if not os.path.exists(ah_path):
        r.add_error(f"allowed-hosts.js: missing ({ah_path})")
    else:
        try:
            arr = _parse_allowed_hosts_js(ah_path)
        except (ValueError, OSError) as e:
            r.add_error(f"allowed-hosts.js: parse failure ({e})")
        else:
            if config is not None and arr != config.get("allowedHosts"):
                r.add_error(f"allowed-hosts.js array {arr} != store-config.allowedHosts "
                            f"{config.get('allowedHosts')}")

    # mattresses.csv header == live EN contract
    en_path = os.path.join(data, "mattresses.csv")
    if not os.path.exists(en_path):
        r.add_error(f"mattresses.csv: missing ({en_path})")
    else:
        exp = schema.get_column_headers("Mattresses", lang="")
        if _csv_header(en_path) != exp:
            r.add_error("mattresses.csv: header does not match the live schema contract")

    # mattresses-es.csv: validate header if present (the converter omits it when
    # there is no Spanish copy, so absence is not an error).
    es_path = os.path.join(data, "mattresses-es.csv")
    if os.path.exists(es_path):
        if _csv_header(es_path) != list(schema.MATTRESSES_ES_CSV_COLUMNS):
            r.add_error("mattresses-es.csv: header does not match the ES schema contract")
    elif languages and "es" in languages:
        r.add_warning("mattresses-es.csv absent (languages includes 'es'; ok if no "
                      "Spanish mattress copy was provided)")

    # accessories.json: top-level array, each item has id/name/category/image
    acc = load_json(os.path.join(data, "accessories.json"), "accessories.json")
    if acc is not None:
        if not isinstance(acc, list):
            r.add_error("accessories.json: top-level is not a JSON array")
        else:
            for i, a in enumerate(acc):
                if not isinstance(a, dict):
                    r.add_error(f"accessories.json[{i}]: not an object")
                    continue
                for k in ("id", "name", "category", "image"):
                    if k not in a:
                        r.add_error(f"accessories.json[{i}]: missing {k!r}")
                if _blank(a.get("image")):
                    r.add_error(f"accessories.json[{i}] ({a.get('id')}): image is empty")

    # manifest.json: required keys
    man = load_json(os.path.join(output_dir, "manifest.json"), "manifest.json")
    if man is not None:
        for k in ("name", "short_name", "description", "start_url",
                  "display", "orientation", "background_color", "theme_color"):
            if k not in man:
                r.add_error(f"manifest.json: missing key {k!r}")
        # When the manifest declares icons, each referenced file must exist at the
        # output root (icon src is relative to the manifest URL).
        if isinstance(man.get("icons"), list) and man["icons"]:
            for ic in man["icons"]:
                src = ic.get("src") if isinstance(ic, dict) else None
                if src and not os.path.exists(os.path.join(output_dir, src)):
                    r.add_error(f"manifest.json: icon {src!r} not found on disk")
            # M3: icon generation always emits apple-touch-icon.png alongside the
            # manifest icons (index.html references it via <link rel=apple-touch-icon>),
            # but it is not listed in manifest.icons, so verify it explicitly here.
            if not os.path.exists(os.path.join(output_dir, "apple-touch-icon.png")):
                r.add_error("manifest.json declares icons but apple-touch-icon.png is "
                            "missing at the output root (index.html references it)")

    # brand logos referenced by store-config must exist on disk. Only checked when
    # the brands image folder was emitted (mirrors the mattress-image guard below):
    # a no-image build has nothing to verify.
    if config is not None and os.path.isdir(os.path.join(output_dir, "images", "brands")):
        for b in (config.get("brands") or []):
            logo = b.get("logo")
            if logo and not os.path.exists(os.path.join(output_dir, logo)):
                r.add_error(f"store-config brand {b.get('name')!r}: logo file "
                            f"{logo!r} not found on disk")

    # mattresses.json: structural sanity (only when build-json actually produced it)
    if build_json:
        mj = load_json(os.path.join(data, "mattresses.json"), "mattresses.json")
        if mj is not None:
            images_dir = os.path.join(output_dir, "images", "mattresses")
            check_imgs = os.path.isdir(images_dir)
            for tier in ("gold", "silver", "bronze"):
                if tier not in mj:
                    r.add_error(f"mattresses.json: missing tier {tier!r}")
                elif not isinstance(mj[tier], list):
                    r.add_error(f"mattresses.json: tier {tier!r} is not a list")
                else:
                    for m in mj[tier]:
                        for k in ("id", "name", "imageUrl"):
                            if k not in m:
                                r.add_error(f"mattresses.json {tier} item missing {k!r}")
                        if _blank(m.get("imageUrl")):
                            r.add_error(f"mattresses.json ({m.get('id')}): imageUrl is empty")
                        elif check_imgs and not os.path.exists(os.path.join(output_dir, m.get("imageUrl"))):
                            r.add_warning(f"mattresses.json ({m.get('id')}): imageUrl "
                                          f"{m.get('imageUrl')!r} not found on disk")
    return r


# -- Entrypoint ---------------------------------------------------------------

def validate_bundle_inputs(raw_tabs, store_config, manifest=None, *,
                           source_images=None, skip_images=False,
                           require_gas_url: bool = False) -> ValidationReport:
    """Full input validation: workbook structure (V1), store-config values (V1),
    and catalog checks for mattresses/accessories/SalesNotes (V2), plus source-image
    existence when `source_images` is provided and not skipped. Caller passes the
    converter's parsed tabs and the assembled config/manifest."""
    langs = store_config.get("languages")
    r = ValidationReport()
    r.merge(validate_structure(raw_tabs))
    r.merge(validate_store_config(store_config, manifest, require_gas_url=require_gas_url))
    r.merge(validate_mattresses(raw_tabs, source_images=source_images,
                                skip_images=skip_images, languages=langs))
    r.merge(validate_accessories(raw_tabs, source_images=source_images,
                                 skip_images=skip_images, languages=langs))
    r.merge(validate_brands(raw_tabs, source_images=source_images,
                            skip_images=skip_images))
    r.merge(validate_app_icon(raw_tabs, source_images=source_images,
                              skip_images=skip_images))
    r.merge(validate_sales_notes(raw_tabs, languages=langs))
    return r


# -- Self-test (no pytest; stdlib only) ---------------------------------------

def _good_tabs():
    """A fully-valid raw_tabs (structure + catalog) for every schema tab - passes
    with zero errors and zero warnings under _good_config (languages en+es)."""
    tabs = {}
    for tab in schema.get_tab_names():
        headers = schema.get_column_headers(tab)
        req = [c.name for c in schema.required_columns(tab)]
        row = {h: ("x" if h in req else "") for h in headers}
        tabs[tab] = (headers, [row])
    tabs["Brands"][1][0].update({"Brand Name": "Acme"})
    tabs["Mattresses"][1][0].update({
        "tier": "gold", "id": "m1", "name": "Athena", "brand": "Acme",
        "firmnessScore": "5", "features": "hybrid", "reason_default": "Great bed",
        "highlight (ES)": "es-copy",
    })
    tabs["Accessories"][1][0].update({
        "ID": "a1", "Name": "Pillow", "Name (ES)": "Almohada",
        "Category": "Pillows", "Category (ES)": "Almohadas", "Price": 100,
        "Description": "Soft", "Description (ES)": "Suave",
        "Image File Name": "images/accessories/a1.jpg", "Match Tags": "all",
    })
    tabs["SalesNotes"][1][0].update({
        "Type": "brand", "Key": "Acme", "Story": "Family-owned since 1900",
    })
    return tabs


def _good_config():
    return {
        "storeName": "Acme Mattress",
        "storeKey": "acme",
        "languages": ["en", "es"],
        "logo": {"main": "acme", "sub": "mattress"},
        "colors": {"storePrimary": "#123abc", "storePrimaryLight": "#2244cc",
                   "storePrimaryGlow": "rgba(1,2,3,0.15)", "accent": "#b8935d"},
        "gasUrl": "https://script.google.com/macros/s/AKxyz/exec",
        "publicAssetRoot": "https://acme.github.io/DreamFinder/",
        "allowedHosts": ["acme.github.io"],
        "discount": {"codePrefix": "DREAM", "codeDigits": 3},
    }


def _good_manifest():
    return {"name": "DreamFinder - Acme", "start_url": "/DreamFinder/"}


def _self_test() -> int:
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [ok]   {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    # minimal valid sample passes
    r = validate_bundle_inputs(_good_tabs(), _good_config(), _good_manifest())
    check("valid sample passes", r.ok and not r.warnings)

    # missing required tab
    t = _good_tabs(); del t["SalesNotes"]
    check("missing required tab -> error",
          any("missing required tab" in e for e in validate_structure(t).errors))

    # duplicate header
    t = _good_tabs()
    h, rows = t["Brands"]; t["Brands"] = (h + [h[0]], rows)
    check("duplicate header -> error",
          any("duplicate header" in e for e in validate_structure(t).errors))

    # Store Info multiple rows
    t = _good_tabs(); h, rows = t["Store Info"]; t["Store Info"] = (h, rows + [dict(rows[0])])
    check("Store Info multiple rows -> error",
          any("expected exactly 1 data row" in e for e in validate_structure(t).errors))

    # missing schema-required value
    t = _good_tabs(); h, rows = t["Mattresses"]; rows[0]["reason_default"] = ""
    check("missing required cell -> error",
          any("reason_default" in e for e in validate_structure(t).errors))

    # invalid hex color
    c = _good_config(); c["colors"]["storePrimary"] = "8B1A1A"
    check("invalid hex color -> error",
          any("storePrimary" in e for e in validate_store_config(c).errors))

    # missing allowedHosts
    c = _good_config(); c["allowedHosts"] = []
    check("missing allowedHosts -> error",
          any("allowedHosts is empty" in e for e in validate_store_config(c).errors))

    # allowedHosts with protocol
    c = _good_config(); c["allowedHosts"] = ["https://acme.github.io"]
    check("allowedHosts with protocol -> error",
          any("must not include a protocol" in e for e in validate_store_config(c).errors))

    # allowedHosts with localhost
    c = _good_config(); c["allowedHosts"] = ["acme.github.io", "localhost"]
    check("allowedHosts with localhost -> error",
          any("localhost" in e for e in validate_store_config(c).errors))

    # publicAssetRoot missing trailing slash
    c = _good_config(); c["publicAssetRoot"] = "https://acme.github.io/DreamFinder"
    check("publicAssetRoot no trailing slash -> error",
          any("trailing slash" in e for e in validate_store_config(c).errors))

    # blank gasUrl -> warning (not error) by default
    c = _good_config(); c["gasUrl"] = ""
    r = validate_store_config(c)
    check("blank gasUrl -> warning only", r.ok and any("gasUrl" in w for w in r.warnings))

    # --require-gas-url promotes gasUrl to error
    c = _good_config(); c["gasUrl"] = ""
    r = validate_store_config(c, require_gas_url=True)
    check("require_gas_url promotes gasUrl to error",
          any("gasUrl" in e for e in r.errors))

    # warnings_as_errors promotes allowedHosts-missing-Pages-host warning to blocking
    c = _good_config(); c["allowedHosts"] = ["someoneelse.github.io"]
    r = validate_store_config(c)
    check("allowedHosts missing Pages host -> warning",
          r.ok and any("does not include the publicAssetRoot host" in w for w in r.warnings))
    check("warnings_as_errors makes that warning blocking",
          r.blocking(warnings_as_errors=True) and not r.blocking(warnings_as_errors=False))

    # discount.codeDigits out of range
    c = _good_config(); c["discount"]["codeDigits"] = 2
    check("codeDigits out of range -> error",
          any("codeDigits" in e for e in validate_store_config(c).errors))

    # manifest.start_url empty
    m = dict(_good_manifest()); m["start_url"] = ""
    check("manifest.start_url empty -> error",
          any("manifest.start_url" in e for e in validate_store_config(_good_config(), m).errors))

    # ---- V2: catalog ----
    langs = ["en", "es"]

    # duplicate mattress id
    t = _good_tabs(); h, rows = t["Mattresses"]; t["Mattresses"] = (h, [rows[0], dict(rows[0])])
    check("duplicate mattress id -> error",
          any("duplicate id" in e for e in validate_mattresses(t, languages=langs).errors))

    # invalid tier
    t = _good_tabs(); t["Mattresses"][1][0]["tier"] = "platinum"
    check("invalid tier -> error",
          any("tier 'platinum'" in e for e in validate_mattresses(t, languages=langs).errors))

    # invalid mattress id slug
    t = _good_tabs(); t["Mattresses"][1][0]["id"] = "M 1"
    check("invalid mattress id slug -> error",
          any("not slug-safe" in e for e in validate_mattresses(t, languages=langs).errors))

    # firmness out of range
    t = _good_tabs(); t["Mattresses"][1][0]["firmnessScore"] = "11"
    check("firmness out of range -> error",
          any("firmnessScore" in e for e in validate_mattresses(t, languages=langs).errors))

    # brand not in Brands tab
    t = _good_tabs(); t["Mattresses"][1][0]["brand"] = "Nope"
    check("brand not in Brands tab -> error",
          any("not in the Brands tab" in e for e in validate_mattresses(t, languages=langs).errors))

    # duplicate lower(name) image collision
    t = _good_tabs(); h, rows = t["Mattresses"]
    r2 = dict(rows[0]); r2["id"] = "m2"; r2["name"] = "athena"
    t["Mattresses"] = (h, [rows[0], r2])
    check("duplicate lower(name) collision -> error",
          any("image filename collision" in e for e in validate_mattresses(t, languages=langs).errors))

    # invalid accessory score (negative)
    t = _good_tabs(); t["Accessories"][1][0]["Score: Cooling"] = "-1"
    check("negative accessory score -> error",
          any("Score: Cooling" in e for e in validate_accessories(t, languages=langs).errors))

    # accessory score 10 is allowed (Bel uses high 'default' weights)
    t = _good_tabs(); t["Accessories"][1][0]["Score: Default"] = 10
    check("accessory score 10 allowed (not 0-5 capped)",
          validate_accessories(t, languages=langs).ok)

    # duplicate accessory id
    t = _good_tabs(); h, rows = t["Accessories"]; t["Accessories"] = (h, [rows[0], dict(rows[0])])
    check("duplicate accessory id -> error",
          any("duplicate id" in e for e in validate_accessories(t, languages=langs).errors))

    # invalid accessory category
    t = _good_tabs(); t["Accessories"][1][0]["Category"] = "widgets"
    check("invalid accessory category -> error",
          any("category 'widgets'" in e for e in validate_accessories(t, languages=langs).errors))

    # accessory image basename != id is accepted when the cell is a full
    # images/accessories/<file>.jpg path
    t = _good_tabs(); t["Accessories"][1][0]["Image File Name"] = "images/accessories/copper-ice.jpg"
    check("accessory full path, basename != id accepted",
          validate_accessories(t, languages=langs).ok)

    # G1: bare accessory image filename (no images/accessories/ prefix) -> error
    t = _good_tabs(); t["Accessories"][1][0]["Image File Name"] = "copper-ice.jpg"
    check("G1 bare accessory image path -> error",
          any("must be a full" in e and "images/accessories/" in e
              for e in validate_accessories(t, languages=langs).errors))

    # G1: full path but non-jpg extension -> error (live file is normalized to .jpg)
    t = _good_tabs(); t["Accessories"][1][0]["Image File Name"] = "images/accessories/copper-ice.png"
    check("G1 accessory full path, wrong extension -> error",
          any("must be a full" in e for e in validate_accessories(t, languages=langs).errors))

    # G1: wrong directory prefix -> error
    t = _good_tabs(); t["Accessories"][1][0]["Image File Name"] = "images/mattresses/copper-ice.jpg"
    check("G1 accessory wrong directory prefix -> error",
          any("must be a full" in e for e in validate_accessories(t, languages=langs).errors))

    # G1: extra sub-path under images/accessories/ -> error
    t = _good_tabs(); t["Accessories"][1][0]["Image File Name"] = "images/accessories/sub/copper-ice.jpg"
    check("G1 accessory extra sub-path -> error",
          any("must be a full" in e for e in validate_accessories(t, languages=langs).errors))

    # invalid salesNote Type
    t = _good_tabs(); t["SalesNotes"][1][0] = {"Type": "vendor", "Key": "X"}
    check("invalid salesNote Type -> error",
          any("Type 'vendor'" in e for e in validate_sales_notes(t).errors))

    # subBrand full missing Lead/Demo/Close
    t = _good_tabs()
    t["SalesNotes"][1][0] = {"Type": "subBrand", "Key": "Copper", "Format": "full",
                             "Lead": "", "Demo": "d", "Close": "c"}
    check("salesNote full missing Lead -> error",
          any("Lead is required" in e for e in validate_sales_notes(t).errors))

    # subBrand coaching missing RSA Note
    t = _good_tabs()
    t["SalesNotes"][1][0] = {"Type": "subBrand", "Key": "Charcoal", "Format": "coaching",
                             "RSA Note": ""}
    check("salesNote coaching missing RSA Note -> error",
          any("RSA Note is required" in e for e in validate_sales_notes(t).errors))

    # brand salesNote missing Story
    t = _good_tabs()
    t["SalesNotes"][1][0] = {"Type": "brand", "Key": "Acme", "Story": ""}
    check("brand salesNote missing Story -> error",
          any("Story is required" in e for e in validate_sales_notes(t).errors))

    # missing mattress source image when source-images provided
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "mattresses"))
        os.makedirs(os.path.join(d, "accessories"))
        t = _good_tabs()  # name "Athena" -> needs athena.* in d/mattresses (absent)
        check("missing mattress source image -> error",
              any("no source image" in e and "Mattresses" in e
                  for e in validate_mattresses(t, source_images=d, languages=langs).errors))
        check("missing accessory source image -> error",
              any("no source image" in e and "Accessories" in e
                  for e in validate_accessories(t, source_images=d, languages=langs).errors))

        # Brands: logo source existence (brands/ subdir of --source-images)
        os.makedirs(os.path.join(d, "brands"))
        tb = _good_tabs(); tb["Brands"][1][0]["Logo File Name"] = "acme.png"
        check("missing brand source logo -> error",
              any("no source logo" in e and "Brands" in e
                  for e in validate_brands(tb, source_images=d).errors))
        open(os.path.join(d, "brands", "acme.png"), "w").close()
        check("present brand source logo -> ok",
              validate_brands(tb, source_images=d).ok)
        check("blank brand logo -> ok (no source needed)",
              validate_brands(_good_tabs(), source_images=d).ok)
        check("brands source folder missing -> error",
              any("source logo folder not found" in e
                  for e in validate_brands(tb, source_images=os.path.join(d, "nope")).errors))

        # App icon (Store Info "App Icon File") - optional PWA icon source in logos/
        os.makedirs(os.path.join(d, "logos"))

        def _png(w, h):
            return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
                    + w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00")

        def _put_icon(w, h, name="app-icon.png"):
            with open(os.path.join(d, "logos", name), "wb") as f:
                f.write(_png(w, h))

        ti = _good_tabs(); ti["Store Info"][1][0]["App Icon File"] = "app-icon.png"
        check("app icon: blank -> ok (no source needed)",
              validate_app_icon(_good_tabs(), source_images=d).ok)
        check("app icon: missing source -> error",
              any("not found" in e and "App Icon File" in e
                  for e in validate_app_icon(ti, source_images=d).errors))
        _put_icon(512, 512)
        check("app icon: square >=512 png -> ok", validate_app_icon(ti, source_images=d).ok)
        _put_icon(400, 400)
        check("app icon: under 512px -> error",
              any(">= 512px" in e for e in validate_app_icon(ti, source_images=d).errors))
        _put_icon(512, 256)
        check("app icon: non-square -> error",
              any("must be square" in e for e in validate_app_icon(ti, source_images=d).errors))
        tj = _good_tabs(); tj["Store Info"][1][0]["App Icon File"] = "icon.jpg"
        check("app icon: non-png -> error",
              any("must be a .png" in e for e in validate_app_icon(tj).errors))
        # M2: App Icon File set but the run cannot generate icons -> blocking error.
        check("app icon: set but no --source-images -> error",
              any("cannot be generated" in e for e in validate_app_icon(ti).errors))
        check("app icon: set with --skip-image-normalization -> error",
              any("cannot be generated" in e
                  for e in validate_app_icon(ti, source_images=d, skip_images=True).errors))
        # ...and a valid run (source images, not skipped) does NOT trip the M2 gate.
        _put_icon(512, 512)
        check("app icon: source provided, not skipped -> no M2 error",
              not any("cannot be generated" in e
                      for e in validate_app_icon(ti, source_images=d).errors))

    # ES missing copy warns when languages includes es
    t = _good_tabs()
    for hh in [c for c in t["Mattresses"][0] if c.endswith(" (ES)")]:
        t["Mattresses"][1][0][hh] = ""
    rr = validate_mattresses(t, languages=langs)
    check("ES missing mattress copy -> warning (not error)",
          rr.ok and any("no Spanish (ES) copy" in w for w in rr.warnings))

    # ---- V3: post-emit output validation ----
    import tempfile

    def _write(path, text):
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def _write_good_output(d, *, with_es=True, with_mj=False):
        data = os.path.join(d, "data")
        os.makedirs(data, exist_ok=True)
        _write(os.path.join(data, "store-config.json"),
               json.dumps({"storeName": "Acme", "allowedHosts": ["acme.github.io"]}))
        _write(os.path.join(data, "allowed-hosts.js"),
               'window.__DF_ALLOWED_HOSTS = ["acme.github.io"];\n')
        with open(os.path.join(data, "mattresses.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(schema.get_column_headers("Mattresses", lang=""))
        if with_es:
            with open(os.path.join(data, "mattresses-es.csv"), "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(list(schema.MATTRESSES_ES_CSV_COLUMNS))
        _write(os.path.join(data, "accessories.json"), json.dumps(
            [{"id": "a1", "name": {"en": "P"}, "category": {"en": "Pillows"},
              "image": "images/accessories/a1.jpg"}]))
        _write(os.path.join(d, "manifest.json"), json.dumps(
            {"name": "n", "short_name": "s", "description": "d", "start_url": "/x/",
             "display": "standalone", "orientation": "landscape",
             "background_color": "#000", "theme_color": "#000"}))
        if with_mj:
            _write(os.path.join(data, "mattresses.json"), json.dumps(
                {"gold": [{"id": "g1", "name": "A", "imageUrl": "images/mattresses/a.jpg"}],
                 "silver": [], "bronze": []}))
        return d

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        check("post-emit valid output passes (build_json=False)",
              validate_generated_outputs(d, build_json=False, languages=["en", "es"]).ok)

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        os.remove(os.path.join(d, "data", "store-config.json"))
        check("post-emit missing store-config -> error",
              any("store-config.json: missing" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        _write(os.path.join(d, "data", "store-config.json"), "{not valid json")
        check("post-emit invalid JSON -> error",
              any("invalid JSON" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        _write(os.path.join(d, "data", "allowed-hosts.js"),
               'window.__DF_ALLOWED_HOSTS = ["other.github.io"];\n')
        check("post-emit allowed-hosts mismatch -> error",
              any("allowed-hosts.js array" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        _write(os.path.join(d, "data", "allowed-hosts.js"), "// no assignment here\n")
        check("post-emit allowed-hosts parse failure -> error",
              any("parse failure" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        with open(os.path.join(d, "data", "mattresses.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["wrong", "header"])
        check("post-emit mattresses.csv header mismatch -> error",
              any("mattresses.csv: header" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        del man["theme_color"]
        _write(os.path.join(d, "manifest.json"), json.dumps(man))
        check("post-emit manifest missing key -> error",
              any("manifest.json: missing key" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d, with_mj=False)
        check("post-emit mattresses.json missing when build_json=True -> error",
              any("mattresses.json: missing" in e
                  for e in validate_generated_outputs(d, build_json=True).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d, with_mj=False)
        check("post-emit mattresses.json not required when build_json=False",
              validate_generated_outputs(d, build_json=False, languages=["en", "es"]).ok)

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        _write(os.path.join(d, "data", "accessories.json"), json.dumps({"not": "array"}))
        check("post-emit accessories.json wrong shape -> error",
              any("top-level is not a JSON array" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        cfgp = os.path.join(d, "data", "store-config.json")
        cfg = json.load(open(cfgp, encoding="utf-8"))
        cfg["brands"] = [{"name": "Acme", "logo": "images/brands/acme.jpg"}]
        _write(cfgp, json.dumps(cfg))
        bdir = os.path.join(d, "images", "brands"); os.makedirs(bdir, exist_ok=True)
        _write(os.path.join(bdir, "acme.jpg"), "x")
        check("post-emit brand logo present -> ok",
              validate_generated_outputs(d, build_json=False, languages=["en", "es"]).ok)
        os.remove(os.path.join(bdir, "acme.jpg"))
        check("post-emit brand logo missing -> error",
              any("not found on disk" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    with tempfile.TemporaryDirectory() as d:
        _write_good_output(d)
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        man["icons"] = [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]
        _write(os.path.join(d, "manifest.json"), json.dumps(man))
        _write(os.path.join(d, "icon-192.png"), "x")
        _write(os.path.join(d, "icon-512.png"), "x")
        _write(os.path.join(d, "apple-touch-icon.png"), "x")
        check("post-emit manifest icons present -> ok",
              validate_generated_outputs(d, build_json=False, languages=["en", "es"]).ok)
        # M3: apple-touch-icon.png must exist when the manifest declares icons.
        os.remove(os.path.join(d, "apple-touch-icon.png"))
        check("post-emit apple-touch-icon missing -> error",
              any("apple-touch-icon.png" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))
        _write(os.path.join(d, "apple-touch-icon.png"), "x")  # restore
        os.remove(os.path.join(d, "icon-512.png"))
        check("post-emit manifest icon missing -> error",
              any("icon 'icon-512.png' not found" in e
                  for e in validate_generated_outputs(d, build_json=False).errors))

    # ---- promotions (scenario-aware) validation ----
    MIDS = {"g7", "s1", "s2", "g1"}

    def _pc(promos):
        return {"promotions": promos}

    good_promo = {
        "activeScenario": "demo",
        "scenarios": {"demo": {
            "kind": "historical-demo", "disableEmailSubmission": True,
            "disclosure": {"en": "Historical demo", "es": "Demo historica"},
            "items": [{"id": "p1", "eligibleMattressIds": ["g7"],
                       "badge": {"en": "B", "es": "B"}, "headline": {"en": "H", "es": "H"},
                       "evidenceStatus": "prior-research-observation",
                       "evidenceProvenance": "seen prior",
                       "sourceUrl": "https://www.wgrfurniture.com/x"}],
            "storewide": [{"id": "s20", "type": "reconstructed-storewide",
                           "badge": {"en": "E", "es": "E"}, "headline": {"en": "H", "es": "H"},
                           "evidenceStatus": "prior-research-observation", "evidenceProvenance": "x"}]}},
    }
    check("promotions valid scenario -> ok",
          validate_promotions(_pc(good_promo), mattress_ids=MIDS).ok)

    def _mut(**path_set):
        return json.loads(json.dumps(good_promo))

    dup = _mut(); dup["scenarios"]["demo"]["storewide"][0]["id"] = "p1"
    check("promotions duplicate id -> error",
          any("duplicate promotion id" in e for e in validate_promotions(_pc(dup), mattress_ids=MIDS).errors))

    badm = _mut(); badm["scenarios"]["demo"]["items"][0]["eligibleMattressIds"] = ["zzz"]
    check("promotions invalid mattress id -> error",
          any("not in mattresses" in e for e in validate_promotions(_pc(badm), mattress_ids=MIDS).errors))

    badacc = _mut(); badacc["scenarios"]["demo"]["items"][0]["eligibleAccessoryIds"] = ["nope"]
    check("promotions invalid accessory id -> error",
          any("not in accessories" in e
              for e in validate_promotions(_pc(badacc), mattress_ids=MIDS, accessory_ids={"base-x"}).errors))

    mes = _mut(); mes["scenarios"]["demo"]["items"][0]["headline"] = {"en": "H", "es": ""}
    check("promotions missing ES headline -> error",
          any("headline missing EN or ES" in e for e in validate_promotions(_pc(mes), mattress_ids=MIDS).errors))

    ua = _mut(); ua["activeScenario"] = "nope"
    check("promotions unknown activeScenario -> error",
          any("activeScenario" in e for e in validate_promotions(_pc(ua), mattress_ids=MIDS).errors))

    bev = _mut(); bev["scenarios"]["demo"]["items"][0]["evidenceStatus"] = "bogus"
    check("promotions bad evidenceStatus -> error",
          any("evidenceStatus" in e for e in validate_promotions(_pc(bev), mattress_ids=MIDS).errors))

    nws = _mut()
    nws["scenarios"]["demo"]["items"][0]["evidenceStatus"] = "wgr-product-page"
    nws["scenarios"]["demo"]["items"][0]["sourceUrl"] = "https://purple.com/x"
    check("promotions non-WG&R source -> error",
          any("not a wgrfurniture.com source" in e for e in validate_promotions(_pc(nws), mattress_ids=MIDS).errors))

    arc = _mut()
    arc["scenarios"]["demo"]["items"][0]["evidenceStatus"] = "wgr-full-page-archive"
    arc["scenarios"]["demo"]["items"][0]["sourceUrl"] = "https://web.archive.org/web/20260525/https://www.wgrfurniture.com/x"
    check("promotions archive of WG&R -> ok",
          validate_promotions(_pc(arc), mattress_ids=MIDS).ok)

    nde = _mut(); nde["scenarios"]["demo"]["disableEmailSubmission"] = False
    check("promotions historical-demo without disableEmailSubmission -> error",
          any("disableEmailSubmission" in e for e in validate_promotions(_pc(nde), mattress_ids=MIDS).errors))

    ndd = _mut(); ndd["scenarios"]["demo"]["disclosure"] = {"en": "x", "es": ""}
    check("promotions active demo missing ES disclosure -> error",
          any("disclosure in EN and ES" in e for e in validate_promotions(_pc(ndd), mattress_ids=MIDS).errors))

    t20 = _mut(); t20["scenarios"]["demo"]["storewide"][0]["eligibleMattressIds"] = ["g7"]
    check("promotions 20% on product without eligibility -> error",
          any("eligibleForStorewide20" in e for e in validate_promotions(_pc(t20), mattress_ids=MIDS).errors))

    npp = _mut(); del npp["scenarios"]["demo"]["items"][0]["evidenceProvenance"]
    check("promotions prior-research-observation without provenance -> error",
          any("requires evidenceProvenance" in e for e in validate_promotions(_pc(npp), mattress_ids=MIDS).errors))

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true",
                        help="Run built-in validation checks and exit.")
    args = parser.parse_args(argv)
    if args.self_test:
        print("validation.py self-test:")
        return _self_test()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
