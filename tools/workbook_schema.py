"""DreamFinder onboarding workbook — shared tab/column schema (SOURCE OF TRUTH).

This module is the *single* definition of which tabs the DreamFinder onboarding
workbook has and which columns each tab carries. It exists so that two pieces of
tooling cannot drift apart:

  * ``tests/fixtures/build_bel_workbook.py`` (S1) — generates the Bel golden-bundle
    fixture workbook from the committed ``data/`` + config.
  * ``tools/create_template.py`` (S7 rewrite) — generates the blank retailer-facing
    onboarding template.

If those two defined tabs/columns independently and diverged, the golden-bundle
regression test would stop proving the *real* onboarding path. Both must import
the schema from here instead. See ``docs/phase0-onboarding-pipeline-spec-2026-05-31.md``
§4 ("S1 harness structure") and §3 (the workbook → bundle pipeline) for context.

Design rules for this module:
  * Dependency-free. Standard library only (``dataclasses``, ``typing``). No
    openpyxl, no project app code, no file I/O. It is pure declarative data plus
    small lookup helpers.
  * Stable, readable names. ``Column.name`` is the literal header text written into
    the workbook; ``Column.key`` is a stable machine identifier for code. Changing
    either is a schema change that ripples into the fixture generator, the
    converter, and the retailer template — do it deliberately.
  * The ``note`` field is human context only (e.g. where a value lands in the
    output bundle). It is documentation, not a machine contract — the converter
    owns the actual mapping logic.

Column language tagging:
  * ``lang=""``  — language-neutral or English column.
  * ``lang="es"`` — Spanish-variant column. On the Mattresses tab these carry a
    "(ES)" header suffix and feed ``data/mattresses-es.csv`` (whose own headers are
    the plain, un-suffixed names — see ``note``). On the Store Info / Accessories /
    SalesNotes tabs they feed the ``*_es`` blocks of the output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Core types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Column:
    """One workbook column.

    name     literal header text written into the workbook row 1
    key      stable machine identifier used by tooling
    required whether onboarding validation should treat a blank as an error
    lang     ""  -> language-neutral / English ;  "es" -> Spanish variant
    note     free-text human context (maps-to hint, etc.); NOT a machine contract
    """
    name: str
    key: str
    required: bool = False
    lang: str = ""
    note: str = ""


@dataclass(frozen=True)
class Tab:
    """One workbook tab: an ordered, immutable list of columns."""
    name: str
    columns: Tuple[Column, ...]
    note: str = ""


def col(name: str, key: Optional[str] = None, required: bool = False,
        lang: str = "", note: str = "") -> Column:
    """Convenience constructor. ``key`` defaults to ``name`` when omitted.

    Used heavily below so the Mattresses tab (whose headers ARE the live CSV
    column names) can be written without repeating the name as the key.
    """
    return Column(name=name, key=key if key is not None else name,
                  required=required, lang=lang, note=note)


# ── Tab: Store Info ──────────────────────────────────────────────────────────
# One row. Produces the scalar/identity parts of data/store-config.json plus
# manifest.json. Nested store-config blocks (text / voice and their _es mirrors)
# are flattened to one column per leaf field; the converter re-nests them.
# Brands and SalesNotes live on their own tabs. List-valued fields (languages,
# allowedHosts) are single comma-separated cells.

STORE_INFO = Tab(
    name="Store Info",
    note="One data row. -> store-config.json (identity/text/voice) + manifest.json",
    columns=(
        # Identity
        col("Store Name", "storeName", required=True, note="-> storeName"),
        col("Store Key", "storeKey", required=True,
            note="-> storeKey; slug-safe, unique per retailer (localStorage namespace)"),
        col("Languages", "languages", required=True,
            note="comma-sep subset of {en,es} -> languages[]"),
        col("Logo Line 1", "logo.main", note="-> logo.main"),
        col("Logo Line 2", "logo.sub", note="-> logo.sub"),

        # Colors
        col("Primary Color (hex)", "colors.storePrimary", required=True, note="-> colors.storePrimary"),
        col("Primary Color Light (hex)", "colors.storePrimaryLight", note="-> colors.storePrimaryLight"),
        col("Primary Color Glow (rgba)", "colors.storePrimaryGlow", note="-> colors.storePrimaryGlow"),
        col("Accent Color (hex)", "colors.accent", note="-> colors.accent"),

        # Backend / hosting
        col("GAS URL", "gasUrl", note="-> gasUrl; left blank until GAS deploy (manual, §6)"),
        col("Public Asset Root", "publicAssetRoot", required=True,
            note="-> publicAssetRoot; trailing slash required (email image base)"),
        col("Allowed Hosts", "allowedHosts", required=True,
            note="comma-sep -> store-config.allowedHosts -> generated data/allowed-hosts.js (M1)"),

        # Discount / Savings Pass
        col("Discount Code Prefix", "discount.codePrefix", note="-> discount.codePrefix (default DREAM)"),
        col("Discount Code Digits", "discount.codeDigits", note="-> discount.codeDigits (int, 3-10)"),

        # text.* (English UI copy)
        col("Page Title", "text.pageTitle", note="-> text.pageTitle"),
        col("Meta Description", "text.metaDescription", note="-> text.metaDescription"),
        col("OG Title", "text.ogTitle", note="-> text.ogTitle"),
        col("Trust Signal", "text.trustSignal", note="-> text.trustSignal"),
        col("Heritage", "text.heritage", note="-> text.heritage"),
        col("Email Privacy", "text.emailPrivacy", note="-> text.emailPrivacy"),
        col("Privacy Policy Contact", "text.privacyPolicyContact", note="-> text.privacyPolicyContact"),
        col("In-Stock Text", "text.inStockText", note="-> text.inStockText"),
        col("Email Header", "text.emailHeader", note="-> text.emailHeader"),
        col("Email Subtext", "text.emailSubtext", note="-> text.emailSubtext"),
        col("Location Label", "text.locationLabel", note="-> text.locationLabel"),

        # text_es.* (Spanish UI copy — same keys as text.*)
        col("Page Title (ES)", "text_es.pageTitle", lang="es", note="-> text_es.pageTitle"),
        col("Meta Description (ES)", "text_es.metaDescription", lang="es", note="-> text_es.metaDescription"),
        col("OG Title (ES)", "text_es.ogTitle", lang="es", note="-> text_es.ogTitle"),
        col("Trust Signal (ES)", "text_es.trustSignal", lang="es", note="-> text_es.trustSignal"),
        col("Heritage (ES)", "text_es.heritage", lang="es", note="-> text_es.heritage"),
        col("Email Privacy (ES)", "text_es.emailPrivacy", lang="es", note="-> text_es.emailPrivacy"),
        col("Privacy Policy Contact (ES)", "text_es.privacyPolicyContact", lang="es", note="-> text_es.privacyPolicyContact"),
        col("In-Stock Text (ES)", "text_es.inStockText", lang="es", note="-> text_es.inStockText"),
        col("Email Header (ES)", "text_es.emailHeader", lang="es", note="-> text_es.emailHeader"),
        col("Email Subtext (ES)", "text_es.emailSubtext", lang="es", note="-> text_es.emailSubtext"),
        col("Location Label (ES)", "text_es.locationLabel", lang="es", note="-> text_es.locationLabel"),

        # voice.* (English welcome-screen copy)
        col("Voice Eyebrow", "voice.eyebrow", note="-> voice.eyebrow"),
        col("Voice Headline Main", "voice.headlineMain", note="-> voice.headlineMain"),
        col("Voice Headline Accent", "voice.headlineAccent", note="-> voice.headlineAccent"),
        col("Voice Sub-Copy Before", "voice.subCopyBefore", note="-> voice.subCopyBefore"),
        col("Voice Sub-Copy Accent", "voice.subCopyAccent", note="-> voice.subCopyAccent"),
        col("Voice Sub-Copy After", "voice.subCopyAfter", note="-> voice.subCopyAfter"),
        col("Voice CTA Primary", "voice.ctaPrimary", note="-> voice.ctaPrimary"),
        col("Voice Time Estimate", "voice.timeEstimate", note="-> voice.timeEstimate"),

        # voice_es.* (Spanish welcome-screen copy — same keys as voice.*)
        col("Voice Eyebrow (ES)", "voice_es.eyebrow", lang="es", note="-> voice_es.eyebrow"),
        col("Voice Headline Main (ES)", "voice_es.headlineMain", lang="es", note="-> voice_es.headlineMain"),
        col("Voice Headline Accent (ES)", "voice_es.headlineAccent", lang="es", note="-> voice_es.headlineAccent"),
        col("Voice Sub-Copy Before (ES)", "voice_es.subCopyBefore", lang="es", note="-> voice_es.subCopyBefore"),
        col("Voice Sub-Copy Accent (ES)", "voice_es.subCopyAccent", lang="es", note="-> voice_es.subCopyAccent"),
        col("Voice Sub-Copy After (ES)", "voice_es.subCopyAfter", lang="es", note="-> voice_es.subCopyAfter"),
        col("Voice CTA Primary (ES)", "voice_es.ctaPrimary", lang="es", note="-> voice_es.ctaPrimary"),
        col("Voice Time Estimate (ES)", "voice_es.timeEstimate", lang="es", note="-> voice_es.timeEstimate"),

        # manifest.json (PWA). display/orientation are converter constants, not columns.
        col("Manifest Name", "manifest.name", note="-> manifest.json name"),
        col("Manifest Short Name", "manifest.short_name", note="-> manifest.json short_name"),
        col("Manifest Description", "manifest.description", note="-> manifest.json description"),
        col("Manifest Start URL", "manifest.start_url", note="-> manifest.json start_url (e.g. /DreamFinder/)"),
        col("Manifest Theme Color", "manifest.theme_color", note="-> manifest.json theme_color"),
        col("Manifest Background Color", "manifest.background_color", note="-> manifest.json background_color"),
        col("App Icon File", "manifest.iconSource",
            note="optional; PWA icons. Square PNG >=512 in source-images/logos/. "
                 "Converter generates root icon-192/512.png + manifest.icons. Blank = no icons."),
    ),
)


# ── Tab: Brands ──────────────────────────────────────────────────────────────
# One row per mattress brand. -> store-config.json brands[].

BRANDS = Tab(
    name="Brands",
    note="One row per brand -> store-config.json brands[]",
    columns=(
        col("Brand Name", "name", required=True, note="-> brands[].name"),
        col("Logo File Name", "logoFile", note="-> brands[].logo (images/brands/<file>)"),
    ),
)


# ── Tab: Mattresses ──────────────────────────────────────────────────────────
# One row per mattress. The English columns map 1:1 to the live data/mattresses.csv
# header (exact order/names), so build-data.ps1 consumes them unchanged. The "(ES)"
# columns feed data/mattresses-es.csv, whose file headers are the PLAIN names
# (id, displayBadges, highlight, reason_*, topPickReason) keyed by the shared id.

MATTRESSES = Tab(
    name="Mattresses",
    note="One row per mattress. EN cols -> data/mattresses.csv ; (ES) cols -> data/mattresses-es.csv",
    columns=(
        # English — exact live CSV contract, in CSV column order.
        col("tier", required=True, note="gold|silver|bronze"),
        col("id", required=True, note="unique, never reused"),
        col("name", required=True, note="image filename derives from lower(name)"),
        col("brand", required=True),
        col("subBrand", note="customer-visible sub-line; SalesNotes key"),
        col("pitchKey", note="internal SUBBRAND_NOTES cascade override (pitchKey || subBrand)"),
        col("archetype", note="RSA/customer chip tag"),
        col("displayPriority", note="int tiebreaker; default 1 (manufacturer), 2 (house)"),
        col("firmnessScore", required=True, note="int 1-10; scoring input"),
        col("firmnessLabel", note="display text (Plush/Medium/Firm)"),
        col("price", note="left blank — not displayed"),
        col("quizTags", note="legacy column; build-data reads `features`, not this (see spec §1a)"),
        col("displayBadges", note="pipe-delimited -> JSON tags[]"),
        col("highlight", note="card hero line"),
        col("locally-made", note="yes|no — +25 scoring bonus when yes"),
        col("features", required=True, note="pipe-delimited scoring tags -> JSON features[]"),
        col("reason_cooling", note="per-match reason"),
        col("reason_pressureRelief", note="per-match reason"),
        col("reason_motionIsolation", note="per-match reason"),
        col("reason_support", note="per-match reason"),
        col("reason_plush", note="per-match reason"),
        col("reason_medium", note="per-match reason"),
        col("reason_firm", note="per-match reason"),
        col("reason_durability", note="per-match reason"),
        col("reason_default", required=True, note="main selling point shown to everyone"),
        col("topPickReason", note="top-pick badge reason (EN)"),
        col("differentiator1Title", required=True, note="model-specific trial distinction title"),
        col("differentiator1Detail", required=True, note="plain-language felt or functional difference"),
        col("differentiator2Title", required=True, note="second model-specific trial distinction title"),
        col("differentiator2Detail", required=True, note="second plain-language felt or functional difference"),

        # Spanish — feed mattresses-es.csv (plain header given in note), keyed by `id`.
        col("displayBadges (ES)", "displayBadges_es", lang="es", note="-> mattresses-es.csv displayBadges"),
        col("highlight (ES)", "highlight_es", lang="es", note="-> mattresses-es.csv highlight"),
        col("reason_cooling (ES)", "reason_cooling_es", lang="es", note="-> mattresses-es.csv reason_cooling"),
        col("reason_pressureRelief (ES)", "reason_pressureRelief_es", lang="es", note="-> mattresses-es.csv reason_pressureRelief"),
        col("reason_motionIsolation (ES)", "reason_motionIsolation_es", lang="es", note="-> mattresses-es.csv reason_motionIsolation"),
        col("reason_support (ES)", "reason_support_es", lang="es", note="-> mattresses-es.csv reason_support"),
        col("reason_plush (ES)", "reason_plush_es", lang="es", note="-> mattresses-es.csv reason_plush"),
        col("reason_medium (ES)", "reason_medium_es", lang="es", note="-> mattresses-es.csv reason_medium"),
        col("reason_firm (ES)", "reason_firm_es", lang="es", note="-> mattresses-es.csv reason_firm"),
        col("reason_durability (ES)", "reason_durability_es", lang="es", note="-> mattresses-es.csv reason_durability"),
        col("reason_default (ES)", "reason_default_es", lang="es", note="-> mattresses-es.csv reason_default"),
        col("topPickReason (ES)", "topPickReason_es", lang="es", note="-> mattresses-es.csv topPickReason"),
        col("differentiator1Title (ES)", "differentiator1Title_es", lang="es", note="-> mattresses-es.csv differentiator1Title"),
        col("differentiator1Detail (ES)", "differentiator1Detail_es", lang="es", note="-> mattresses-es.csv differentiator1Detail"),
        col("differentiator2Title (ES)", "differentiator2Title_es", lang="es", note="-> mattresses-es.csv differentiator2Title"),
        col("differentiator2Detail (ES)", "differentiator2Detail_es", lang="es", note="-> mattresses-es.csv differentiator2Detail"),
    ),
)

# The exact column order of data/mattresses-es.csv (plain headers, id-keyed).
# Kept explicit so the converter and golden test agree on the ES file contract.
MATTRESSES_ES_CSV_COLUMNS: Tuple[str, ...] = (
    "id",
    "displayBadges",
    "highlight",
    "reason_cooling",
    "reason_pressureRelief",
    "reason_motionIsolation",
    "reason_support",
    "reason_plush",
    "reason_medium",
    "reason_firm",
    "reason_durability",
    "reason_default",
    "topPickReason",
    "differentiator1Title",
    "differentiator1Detail",
    "differentiator2Title",
    "differentiator2Detail",
)


# ── Tab: Accessories ─────────────────────────────────────────────────────────
# One row per accessory. -> data/accessories.json (bilingual {en,es} per name/
# category/description). Score columns are 0-N integers; blank/0 = not applicable.

ACCESSORIES = Tab(
    name="Accessories",
    note="One row per accessory -> data/accessories.json (bilingual)",
    columns=(
        col("ID", "id", required=True),
        col("Name", "name.en", required=True, note="-> name.en"),
        col("Name (ES)", "name.es", lang="es", note="-> name.es"),
        col("Category", "category.en", required=True, note="Foundations & Support|Pillows|Protectors -> category.en"),
        col("Category (ES)", "category.es", lang="es", note="-> category.es"),
        col("Sub-Type", "subType", note="adjustable|foundation|low_profile|bunkie|blank"),
        col("Price", "price", required=True, note="number"),
        col("Description", "description.en", required=True, note="-> description.en"),
        col("Description (ES)", "description.es", lang="es", note="-> description.es"),
        col("Image File Name", "image", note="-> image (images/accessories/<file>)"),
        col("Match Tags", "matchTags", note="comma-sep -> matchTags[]"),
        # matchScores.* — keys present in live data/accessories.json
        col("Score: Default", "matchScores.default", note="-> matchScores.default"),
        col("Score: Cooling", "matchScores.cooling", note="-> matchScores.cooling"),
        col("Score: Hot", "matchScores.hot", note="-> matchScores.hot"),
        col("Score: Back Pain", "matchScores.back_pain", note="-> matchScores.back_pain"),
        col("Score: Snoring", "matchScores.snoring", note="-> matchScores.snoring"),
        col("Score: Reflux", "matchScores.reflux", note="-> matchScores.reflux"),
        col("Score: Premium", "matchScores.premium", note="-> matchScores.premium"),
        col("Score: Position Side", "matchScores.position_side", note="-> matchScores.position_side"),
        col("Score: Position Back", "matchScores.position_back", note="-> matchScores.position_back"),
        col("Score: Position Stomach", "matchScores.position_stomach", note="-> matchScores.position_stomach"),
        col("Score: Allergies", "matchScores.allergies", note="-> matchScores.allergies"),
    ),
)


# ── Tab: SalesNotes ──────────────────────────────────────────────────────────
# One row per sub-brand or brand sales note. -> store-config.json salesNotes
# (subBrands{} / brands{}) and salesNotes_es. Row shape depends on Format:
#   Type=subBrand, Format=full     -> requires Lead + Demo + Close
#   Type=subBrand, Format=coaching -> requires RSA Note
#   Type=brand                     -> requires Story
# (Validation of the per-format requirements lives in the converter/§5, not here.)

SALES_NOTES = Tab(
    name="SalesNotes",
    note="One row per sub-brand/brand note -> store-config.json salesNotes / salesNotes_es",
    columns=(
        col("Type", "type", required=True, note="subBrand|brand -> salesNotes.subBrands / .brands"),
        col("Key", "key", required=True, note="sub-brand name (e.g. Copper) or brand name (e.g. Spring Air)"),
        col("Format", "format", note="full|coaching (subBrand rows only)"),
        col("Lead", "lead", note="full subBrand -> lead"),
        col("Demo", "demo", note="full subBrand -> demo"),
        col("Close", "close", note="full subBrand -> close"),
        col("RSA Note", "rsaNote", note="coaching subBrand -> rsaNote"),
        col("Story", "story", note="brand -> story"),
        col("Lead (ES)", "lead_es", lang="es", note="-> salesNotes_es lead"),
        col("Demo (ES)", "demo_es", lang="es", note="-> salesNotes_es demo"),
        col("Close (ES)", "close_es", lang="es", note="-> salesNotes_es close"),
        col("RSA Note (ES)", "rsaNote_es", lang="es", note="-> salesNotes_es rsaNote"),
        col("Story (ES)", "story_es", lang="es", note="-> salesNotes_es story"),
    ),
)


# ── Registry + helpers ───────────────────────────────────────────────────────
# Ordered tuple defines the canonical tab order in the generated workbook.

TABS: Tuple[Tab, ...] = (
    STORE_INFO,
    BRANDS,
    MATTRESSES,
    ACCESSORIES,
    SALES_NOTES,
)

_TABS_BY_NAME: Dict[str, Tab] = {t.name: t for t in TABS}


def get_tab_names() -> List[str]:
    """Canonical workbook tab names, in workbook order."""
    return [t.name for t in TABS]


def require_known_tab(tab_name: str) -> Tab:
    """Return the Tab for ``tab_name`` or raise KeyError listing valid names."""
    try:
        return _TABS_BY_NAME[tab_name]
    except KeyError:
        raise KeyError(
            "Unknown workbook tab %r. Known tabs: %s"
            % (tab_name, ", ".join(get_tab_names()))
        )


def get_tab(tab_name: str) -> Tab:
    """Alias for require_known_tab — fetch a Tab by name."""
    return require_known_tab(tab_name)


def get_columns(tab_name: str, lang: Optional[str] = None) -> List[Column]:
    """Columns for a tab, in order.

    lang=None  -> all columns
    lang=""    -> only language-neutral / English columns
    lang="es"  -> only Spanish-variant columns
    """
    cols = list(require_known_tab(tab_name).columns)
    if lang is None:
        return cols
    return [c for c in cols if c.lang == lang]


def get_column_headers(tab_name: str, lang: Optional[str] = None) -> List[str]:
    """Literal header strings (Column.name) for a tab, in order."""
    return [c.name for c in get_columns(tab_name, lang=lang)]


def get_column_keys(tab_name: str, lang: Optional[str] = None) -> List[str]:
    """Stable machine keys (Column.key) for a tab, in order."""
    return [c.key for c in get_columns(tab_name, lang=lang)]


def required_columns(tab_name: str) -> List[Column]:
    """Columns flagged required (for onboarding validation, §5)."""
    return [c for c in require_known_tab(tab_name).columns if c.required]
