# Phase 0 — Workbook → Validated Store Bundle Pipeline (Implementation Spec)

**Status:** DRAFT for review. Not yet implemented. Read-only audit + this spec only.
**Date:** 2026-05-31
**Branch baseline:** `nocturnal-redesign` @ `cd1a293` (origin/main, verified live).
**Scope:** Phase 0 tooling + validation only. No scoring changes, no touch-event
changes, no Code.gs behavior changes, no architecture rewrite, app stays a
single-file SPA. See "Scope guard" at the end.

> **Design north star.** "1-day onboarding" is shorthand for *streamlined,
> painless, repeatable, almost one-size-fits-all* — **not** a literal 24h promise.
> A few dev-days is fine if the result is a **uniform** path: every retailer runs
> the exact same steps with zero per-store special-casing. Optimize for uniformity,
> not raw speed.

---

## 1. Current live fetch contract (ground truth)

The deployed SPA fetches exactly four data artifacts at runtime. Verified in
`index.html` at `cd1a293`:

| Artifact | Fetch site | Shape | Currently produced by |
|---|---|---|---|
| `data/dict-{lang}.json` (+ `dict-en.json` fallback) | 6683 / 6689 | shared UI dictionary, generic | hand-maintained, **not** per-retailer |
| `data/mattresses.json` | 7063 | `{gold:[],silver:[],bronze:[]}`, 17–18 fields/mattress incl. `_es` | `build-data.ps1` ← `mattresses.csv` (+ `mattresses-es.csv`) |
| `data/store-config.json` | 7064 | branding + `text`/`voice`/`salesNotes` (+ `_es`) | hand-maintained |
| `data/accessories.json` | 7089 | flat array, each field bilingual `{en,es}` | hand-maintained |

Hydration: `MATTRESSES = await …json()` (7068); `STORE_CONFIG = await …json()`
(7069); `let ACCESSORIES = []` then populated from `accessories.json` (7268, 7091).
The old inline `const MATTRESSES = {…}` / `const ACCESSORIES = […]` literals **no
longer exist in the HTML**, and `salesNotes` already migrated into store-config
(comment at 6761). The `docs/proposal-externalize-config-2026-05-28.md` work has
effectively shipped.

**Per-store files NOT fetched but still required by a deployment:**
`manifest.json` (PWA), `icon-192.png` / `icon-512.png` (repo root), brand/store
logos under `images/`, mattress/accessory images, the domain-lock `allowed` array
in `index.html`, and `Code.gs` (deployed separately to Google Apps Script).

### 1a. Mattress JSON field contract (target for CSV emit)

`build-data.ps1` emits these keys per mattress (ordered): `id, name, brand,
subBrand, pitchKey, archetype, displayPriority, firmness, firmnessLabel,
locallyMade, features, tags, highlight, tags_es, highlight_es, imageUrl, reasons,
reasons_es`, plus optional `topPickReason {en,es}`. Source CSV column order:

```
tier,id,name,brand,subBrand,pitchKey,archetype,displayPriority,firmnessScore,
firmnessLabel,price,quizTags,displayBadges,highlight,locally-made,features,
reason_cooling,reason_pressureRelief,reason_motionIsolation,reason_support,
reason_plush,reason_medium,reason_firm,reason_durability,reason_default,topPickReason
```

`mattresses-es.csv` columns: `id,displayBadges,highlight,reason_*,topPickReason`.

> **quizTags trap (carry forward):** CLAUDE.md describes `quizTags` as the scoring
> input, but `build-data.ps1` reads only the `features` column into the JSON
> `features` array. The documented `quizTags` column currently has **zero effect**.
> The converter must populate `features` (not just `quizTags`) or scoring silently
> breaks. Resolve the doc/column mismatch in this phase (do not change scoring math).

---

## 2. Current tooling gaps

### 2.1 `tools/convert_store_data.py` — stale, every output wrong

| Emits | Live app needs | Verdict |
|---|---|---|
| inline `const MATTRESSES` JS (`store_mattresses.js`) | `data/mattresses.json` via CSV→build | wrong artifact + target |
| inline `const ACCESSORIES` JS | `data/accessories.json` | wrong artifact |
| `--output-html` regex on `const MATTRESSES`/`const ACCESSORIES`/footer/`Bel Furniture` | none of those patterns exist now | silently no-ops / corrupts |
| CSS `.txt` + footer `.html` fragments | colors/footer runtime-driven from config | obsolete |
| branding-replacement `.txt` checklist | values live in `store-config.json` | obsolete |
| **WebP** images | **JPG** kebab-case (Outlook/iOS Mail break on webp) | violates CLAUDE.md image rule |
| image URL = `Image File Name` stem, absolute, `.webp` | build-data derives from mattress **`name`** (lowercased), relative path, jpg/png/webp probe | filename + path convention mismatch |
| **no `store-config.json`** | primary white-label target | missing the file that matters most |
| **no CSV** | CSV is the source of truth | missing |
| mattress fields: `{id,name,brand,subBrand,firmness,tags,features,imageUrl,reasons}` | adds `pitchKey, archetype, displayPriority, firmnessLabel, locallyMade, highlight, topPickReason` + all `_es` | drops fields incl. **`locallyMade` (+25 scoring bonus)** |

### 2.2 `tools/create_template.py` — workbook stale vs. schema

- **Store Info tab missing:** `storeKey`, `accent` color, the entire `voice.*`
  welcome-screen block (eyebrow/headline/subCopy/ctaPrimary/timeEstimate),
  `heritage`, `emailHeader`/`emailSubtext`/`inStockText`/`emailPrivacy`/
  `privacyPolicyContact`, the `languages` array, and **all Spanish columns**
  (`text_es`, `voice_es`) — the Onboarding Guide *promises* Spanish columns the
  template never creates.
- **Captures fields with no store-config home:** `store_phone/address/hours`,
  `contact_email`, `footer_text`, `email_sender/subject`, `default_discount` →
  these belong to `Code.gs` / `manifest.json` / discount block, not the `text`
  object. Mapping is undocumented.
- **No `salesNotes` capture at all** — the largest retailer-content block in
  store-config (sub-brand lead/demo/close + coaching `rsaNote`, bilingual).
- **Mattresses tab missing:** `locally-made` (scoring), `highlight`, `pitchKey`,
  `archetype`, `displayPriority`, `firmnessLabel`, `topPickReason`.

### 2.3 `onboarding/Build_Runbook.md` — documents the dead flow

Phase 2 tells operators to run the broken converter + manual string replacement
that no longer applies. Phase 6 says `git push origin main` (no `--force`,
contra CLAUDE.md / `git ship`). Domain-lock line cited inconsistently (3837 vs
6254; actual is `6627`).

### 2.4 Per-store special cases that defeat "one-size-fits-all"

Each forces a manual, error-prone, per-retailer edit outside the workbook flow:

1. **Domain lock** — `index.html:6627` `var allowed = ['beford782.github.io', …]`
   is hardcoded; every store needs a hand-edit.
2. **Dream-code split-brain** — `generateDreamCode` (`index.html:6643–6651`)
   hardcodes `'DREAM'` + exactly 3 digits and ignores config; the welcome-screen
   teaser tiles (`7220–7221`) *do* read `discount.codePrefix`/`codeDigits`. A
   retailer setting `codePrefix:"SLEEP", codeDigits:4` sees `SLEEP—####` on the
   welcome tiles but the **real emailed/logged code is `DREAM###`**.
3. **`manifest.json`** — hardcoded Bel `name`/`description`/`theme_color`
   (`#0f1f33`); per-store hand-edit.
4. **Logo / brand / PWA-icon assets** — no pipeline; "zero index.html edits" is
   true but "zero manual asset wrangling" is not.

---

## 3. Target pipeline: workbook → validated store bundle

```
 retailer workbook (.xlsx)  +  raw image folders
            │
            ▼
   tools/convert_store_data.py   (rewritten)
            │
   ┌────────┼──────────────────────────────────────────────┐
   │        │                                               │
   ▼        ▼                                               ▼
 validate   emit bundle files                       normalize images
 (fail loud) │                                       (jpg, kebab, resize)
            ▼
   data/store-config.json
   data/mattresses.csv  (+ data/mattresses-es.csv if ES present)
   data/accessories.json
   manifest.json
            │
            ▼
   build-data.ps1   (UNCHANGED, trusted)
            │
            ▼
   data/mattresses.json
            │
            ▼
   validation report + onboarding TODO report
```

**Principle:** the converter never writes JSON the trusted path already owns.
It emits **CSV** and hands off to `build-data.ps1` for `mattresses.json`. One
code path, hook-guarded (pre-commit CSV/JSON sync), no second JSON generator to
keep in sync.

**Principle:** the converter never edits `index.html`. Per-store variation moves
into `store-config.json` (§3.4 fixes) so the HTML is genuinely store-agnostic and
the `--output-html` path is deleted outright.

### 3.1 Exact generated outputs

| Output | Source tab(s) | Notes |
|---|---|---|
| `data/store-config.json` | Store Info, Brands, SalesNotes | full schema incl. `text`/`text_es`/`voice`/`voice_es`/`salesNotes`/`salesNotes_es`/`brands`/`colors`/`discount`/`languages`/**`allowedHosts`** (§3.4). Merge onto a skeleton so unmapped keys keep documented placeholders, not vanish. |
| `data/mattresses.csv` | Mattresses (EN cols) | exact column order from §1a, incl. `locally-made`, `highlight`, `displayPriority`, `archetype`, `firmnessLabel`, `topPickReason`, `pitchKey`. |
| `data/mattresses-es.csv` *(optional)* | Mattresses (ES cols) | emitted only if any Spanish mattress cell is non-empty. |
| `data/mattresses.json` | *(via `build-data.ps1`)* | converter shells out to it; never written directly. |
| `data/accessories.json` | Accessories | bilingual `{en,es}` per `name`/`category`/`description`; `matchTags`/`matchScores` preserved. |
| `manifest.json` | Store Info | `name`/`short_name`/`description`/`start_url`/`theme_color`/`background_color` from config; `start_url` derived from repo/Pages path. |
| normalized image assets | raw folders | `images/mattresses/<name>.jpg`, `images/accessories/<id>.jpg`, brand logos, store logo; **JPG q85–90**, kebab-case, resized (long edge cap). PWA icons + logos pass through (not converted). |
| validation report | all tabs | machine + human readable; lists errors (block) and warnings (advise). |
| onboarding TODO report | n/a | the irreducible manual steps (§6): GAS deploy + `gasUrl`, Pages settings, icon drop, domain confirm. |

### 3.2 Image normalization rules (replaces WebP path)

- Format **JPG, quality 85–90** (was WebP@82). Rationale: Outlook desktop /
  iOS Mail break on WebP in result emails (CLAUDE.md image convention).
- Filenames **lowercase kebab-case**. Mattress image filename derived from the
  mattress **`name`** (lowercased) to match `build-data.ps1`'s resolver
  (`images/mattresses/<name>.<ext>` probe order jpg→png→webp). Accessory image
  filename = `<id>.jpg` to match `accessories.json` `image` paths.
- Resize long edge to a cap (keep the existing 1000px) then re-encode JPG.
- Store/brand logos and PWA icons (192/512) **pass through unconverted** (PNG,
  transparency preserved).
- Paths emitted **relative** (`images/...`); `publicAssetRoot` makes them absolute
  for email only — converter must not bake absolute URLs into CSV/JSON.

### 3.3 SalesNotes workbook/tab design

New **SalesNotes** tab. Emits `salesNotes.subBrands{}`, `salesNotes.brands{}`,
and `_es` mirrors. Two row formats keyed by the `Format` column:

| Column | Applies to | Maps to |
|---|---|---|
| `Type` (`subBrand` / `brand`) | all | which dict (`subBrands` vs `brands`) |
| `Key` | all | sub-brand name (e.g. `Copper`) or brand name (e.g. `Spring Air`) |
| `Format` (`full` / `coaching`) | subBrand | shape selector |
| `Lead` | full | `lead` |
| `Demo` | full | `demo` |
| `Close` | full | `close` |
| `RSA Note` | coaching | `rsaNote` |
| `Story` | brand | `story` |
| `Lead (ES)` … `Story (ES)` | all | `salesNotes_es.*` (emit only if non-empty) |

Validation: `full` rows require `Lead`+`Demo`+`Close`; `coaching` rows require
`RSA Note`; `brand` rows require `Story`. Every sub-brand referenced by a mattress
row's `subBrand`/`pitchKey` SHOULD have a matching SalesNotes entry (warn if
missing — the renderer falls back to a dev placeholder).

> Reference current content shape: `data/store-config.json` `salesNotes` (13
> sub-brand entries, 2 brand entries) and `docs/5d-content-spec.md`.

### 3.4 Per-store special-case fixes (fold into Phase 0)

These are **the** uniformity blockers; each removes a manual edit from the path.
All are config/codegen changes, not scoring/touch/architecture.

1. **Domain lock → config (M1: generated synchronous allowed-hosts JS).**
   *Approved 2026-05-31 per the domain-lock load-order audit.* The lock is a
   synchronous parse-time IIFE at `index.html:6626–6633`; it runs **before**
   `STORE_CONFIG` is declared (`7034`) or fetched (`7064`/`7069`), so it **cannot**
   read `STORE_CONFIG.allowedHosts` directly (timing + temporal-dead-zone + the
   object is still `{}` at lock time). Mechanism:
   - `store-config.json.allowedHosts` remains the **human source of truth**.
   - The converter **projects** it into a generated `data/allowed-hosts.js`
     defining `window.__DF_ALLOWED_HOSTS = [...]` (never hand-edited; same
     generated-from-source relationship `mattresses.json` has to the CSV).
   - `index.html` gets **one static, store-agnostic, blocking** script tag placed
     immediately *before* the main `<script>`:
     `<script src="./data/allowed-hosts.js"></script>` (identical for every
     retailer — does not reintroduce per-store HTML surgery).
   - The lock IIFE is amended once (store-agnostic) to:
     `var allowed = (window.__DF_ALLOWED_HOSTS || []).concat(['localhost','127.0.0.1']);`
     — lock logic otherwise unchanged.
   - **Fail-closed contract:** configured list ∪ `localhost`/`127.0.0.1`. Unknown
     public hosts blank (parse-time, no content flash, no pre-check app code on
     unauthorized hosts). `localhost` and `127.0.0.1` always pass.
   - **New availability risk:** a missing/404 `data/allowed-hosts.js` → global
     undefined → only localhost passes → the **production host blanks**. Accepted
     because the localhost fallback keeps dev working and the risk is covered by
     validation (§5: file present + Pages host listed) and the golden-bundle test
     (§4). This is the deliberate fail-closed tradeoff.
   - **Web review required** — this touches a security boundary (the IIFE amendment
     + the new blocking script tag; paste raw before/after of 6619–6633).
   - **Implementation prerequisite — RESOLVED (audit 2026-05-31).** The second
     `window.location.hostname` read at `index.html:6815` is `isDevelopmentMode()`
     (`6814–6817`), an environment detector whose only caller (`renderPitchHtml`,
     `9593`) toggles a dev-only "missing pitch content" placeholder; not an
     authorization gate. It needs no change under M1 and must not be unified with
     `allowedHosts`. A live retailer host is authorized but must not register as dev
     mode, or the placeholder could leak to customers. The 6627 IIFE remains the
     sole gate M1 touches.
2. **Dream code → config, variable length.** Change `generateDreamCode`
   (`6643–6651`) to honor `discount.codePrefix` (default `DREAM`) **and
   `discount.codeDigits` (default 3, retailer-customizable, supports *longer*
   codes)**, matching the teaser-tile logic at `7220–7221`.
   - The current digit step is `Math.abs(hash) % 900 + 100` — **hard-locked to
     exactly 3 digits**. Supporting an arbitrary `codeDigits = N` requires a new
     generator that emits N digits (e.g. derive from the session hash and
     left-pad/truncate to N, keeping the deterministic-per-session property so the
     same session always yields the same code across welcome tile → reveal → email
     → Sheet).
   - **Entropy/collision note:** `Math.abs(hash)` is a 32-bit value (~10 digits
     max). Codes longer than that gain no real entropy and zero-padding becomes
     cosmetic; codes get more collision-resistant as they lengthen, not less.
     Document a sane supported range (recommend `codeDigits` 3–10) and clamp out
     of range in code + validation (§5).
   - Prefix is free-text (already config-driven on the tiles); keep a default so
     an unset/blank value still produces `DREAM`.
   - Verify the email/handoff/Sheet paths (`8839`, `8944`, `9831`) and the teaser
     tiles all flow through the single updated function with the new length.
   - **Does not change the discount percentage logic.**
3. **`manifest.json` generated** from Store Info (§3.1).
4. **Asset pipeline** brings logos + PWA icons into the validated bundle so the
   operator drops nothing by hand (§3.2).

> Fixes 1+2 make `index.html` need **zero** per-store edits. 3+4 remove the last
> manual asset/file edits. Remaining manual step after this = GAS only (§6).

---

## 4. Golden-bundle Bel regression test

**Goal:** prove the path is one-size-fits-all by showing the converter can
*reproduce Bel's own committed bundle* from a Bel workbook.

- **Fixture (decided 2026-05-31):** **generate** the Bel workbook from the
  committed `data/`+config by a checked-in script (`tests/fixtures/build_bel_workbook.py`),
  rather than relying only on an opaque binary `.xlsx`. The generator reads the
  current committed `data/store-config.json`, `data/mattresses.csv`(+`-es`),
  `data/accessories.json`, `manifest.json` and emits the workbook, so the fixture
  can never silently drift from the bundle. (A binary `.xlsx` may be produced as a
  build artifact, but the script is the source of truth.)
- **Test:** run the converter on the generated fixture into a temp dir; run
  `build-data.ps1`; compare each generated file against the committed Bel file.
- **Pass criteria (decided 2026-05-31):** **semantic / canonical comparison**, not
  byte-identical. Parse both sides into a canonical form (normalize key order,
  whitespace, number formatting, JSON/CSV serialization quirks) and compare; a
  **curated allow-list** captures any remaining cosmetic-only diffs. Any
  semantically meaningful or unexplained diff fails.
- **Why this is the correctness argument:** if the converter regenerates Bel
  exactly, then any retailer with a correctly-filled workbook gets a correct bundle
  by construction — no per-store code.
- **Anti-drift:** test runs in CI/local pre-ship. When the bundle schema changes,
  the fixture must change in the same commit (mirrors the pre-commit CSV/JSON sync
  guard philosophy).
- **Budget note:** authoring the round-tripping Bel workbook is the bulk of the
  cost. With speed off the table this is in-scope, not stretch.

### S1 harness structure (approved 2026-05-31)

**Files (all under `tests/`, which is tracked — only `docs/` is gitignored):**
- `tests/fixtures/workbook_schema.py` — **shared workbook tab/column schema**. The
  **single source of truth** for which tabs exist and which columns each carries.
  The Bel fixture generator consumes it now; the `create_template.py` rewrite (S7)
  consumes the *same* module later. Neither defines tabs/columns independently —
  this is what keeps the golden-bundle test proving the *real* onboarding path
  rather than a parallel one that has silently drifted from the retailer template.
- `tests/fixtures/build_bel_workbook.py` — script-generated Bel workbook fixture.
  Reads the committed `data/store-config.json`, `data/mattresses.csv`(+`-es`),
  `data/accessories.json`, `manifest.json` and emits a workbook whose tabs/columns
  come from `workbook_schema.py`.
- `tests/golden/canonical.py` — canonical compare helpers + the curated allow-list.
- `tests/golden/run_golden.py` — temp-workspace runner.

**Decisions:**
- **Commit the generators/helpers, not the generated `.xlsx`.** The workbook is
  emitted into a temp workspace (never committed); a binary `.xlsx` can't be diffed
  and silently rots.
- **Generator self-verifies by round-trip:** emit → read back → reconstruct →
  deep-equal the committed `data/`. This proves fixture faithfulness before the
  converter exists.
- **Temp-workspace isolation:** the harness copies scripts + `data/` + `images/`
  into a tempdir and runs there; it never targets repo `data/` (`build-data.ps1` is
  `$PSScriptRoot`-bound and would mutate the tree / trip the pre-commit hook).
  Shell out to `pwsh`/`powershell` reusing the detection in `tools/hooks/pre-commit`.
- **Canonical comparison** (no byte compare): JSON = parse + key-order-insensitive
  deep-equal (numbers numeric, strings verbatim); CSV = parse by column name, row
  order semantic, tolerate line-endings/quoting/empty-cell noise; images (S4) =
  filename/extension/presence/dimensions, never JPEG bytes; `allowed-hosts.js` (S6)
  = extract array, compare to `store-config.allowedHosts`.
- **Staged activation:** the end-to-end golden target starts **expected-failing /
  skipped** until the converter rewrite lands, then flips each comparison to
  **required** incrementally — **S2** CSV, **S3** store-config/accessories, **S4**
  `mattresses.json` + images, **S5** `manifest.json`, **S6** `allowed-hosts.js`.
- **No CI wiring in S1** — locally runnable only.

---

## 5. Validation rules (the "validated" half)

Run **before** emit; errors block, warnings advise. Emit a report either way.

**Store Info / config**
- required: `storeName`, `storeKey`, `colors.storePrimary` (+ derive light/glow if
  absent), `publicAssetRoot`.
- `storeKey` unique-ish + slug-safe (lowercase, no spaces) — collision risk:
  shared `storeKey` → cross-store `localStorage` RSA bleed. Warn loudly.
- hex colors well-formed (`#rrggbb`).
- `publicAssetRoot` ends with `/` (missing trailing slash silently breaks email
  images — known footgun).
- `languages` ⊆ `{en,es}`; if `es` present, require `text_es`/`voice_es`
  populated (warn if generated-later placeholders remain).
- no leftover example values (e.g. literal `Bel Furniture`, `belfurniture.com`).
- `allowedHosts` present and includes the retailer Pages host.
- `discount.codePrefix` slug-safe / display-safe; `discount.codeDigits` integer in
  the supported range (3–10) — clamp + warn out of range (§3.4.2).

**Mattresses**
- required per row: `tier`, `id`, `name`, `brand`, `firmnessScore`,
  `reason_default`.
- `tier` ∈ `{gold,silver,bronze}`; `firmnessScore` integer 1–10;
  `displayPriority` integer if present; `locally-made` ∈ `{yes,no,blank}`.
- `id` unique across all rows; never reused.
- `features` column populated (scoring input — see quizTags trap §1a).
- image file resolvable for each `name` (warn/err per policy).

**Accessories**
- required: `id`, `name`, `category`, `price`, `description`.
- `category` ∈ `{Foundations & Support, Pillows, Protectors}`; `subType` ∈
  `{adjustable, foundation, low_profile, bunkie, blank}`.
- `matchScores` numeric 0–N; image `<id>.jpg` resolvable.
- `id` unique.

**SalesNotes** — per §3.3 format rules; warn on sub-brand referenced by a mattress
but missing a note.

**Images** — every mattress `name` and accessory `id` has a source image; report
any orphan images (in folder, no row) and any missing images (row, no file).

---

## 6. Manual irreducible step (cannot be automated)

**Per-store Google Apps Script deploy.** Each retailer needs their own GAS web app
(their Google account, their Sheet). This is ~30–60 min of manual clicking in the
Apps Script UI and **cannot be scripted from the repo**. The pipeline produces an
**onboarding TODO report** listing exactly:

1. Create Sheet + bound Apps Script; paste `Code.gs` (with retailer text edits).
2. Deploy web app; copy `/exec` URL → paste into `store-config.json` `gasUrl`.
3. Drop PWA icons at repo root; confirm Pages domain matches `allowedHosts`.
4. GitHub Pages settings (Deploy from branch / main / root).

Honest pitch: **"fill one workbook → validated bundle in ~1 hr, plus a developer's
backend/deploy half-day."** Not fully non-dev — the dev sits mid-critical-path
(`gasUrl` + `publicAssetRoot` must be right before final verification).

> Code.gs text edits remain manual and out of Phase 0 (scope guard). The converter
> emits a **checklist** of the exact strings to replace as part of the TODO report
> — **not** a generated Code.gs diff (decided 2026-05-31: a diff re-introduces a
> generated artifact to keep in sync). The converter never writes or deploys
> Code.gs.

---

## 7. Implementation sequencing (each step independently shippable + verifiable)

> Order chosen so the golden-bundle test exists early and gates every later step.

- **S0 — Spec sign-off (this doc).** Stop for review. ← *current gate*
- **S1 — Golden-bundle harness + Bel fixture.** Author the round-tripping Bel
  workbook + diff test against committed Bel bundle. Establishes the regression
  net before any converter change. (Test will fail until S2–S4 land — that's
  expected; it's the target.)
- **S2 — Converter rewrite, mattresses path.** Emit `mattresses.csv`(+`-es`) in
  exact column order; shell out to `build-data.ps1`. Delete inline-JS +
  `--output-html` paths. Verify: S1 mattresses diff clean.
- **S3 — Converter: store-config + accessories emit.** Emit `store-config.json`
  (skeleton-merge) + `accessories.json`. Verify: S1 config/accessories diff clean.
- **S4 — Image normalization → JPG.** Switch WebP→JPG q85–90, kebab-case, `name`/
  `id`-derived filenames; logos/icons passthrough. Verify: filenames resolve via
  `build-data.ps1`; sample email render.
- **S5 — manifest.json codegen.** From Store Info. Verify against committed
  `manifest.json` (S1 extension).
- **S6 — Special-case config fixes** (separate, reviewed; security-adjacent):
  - S6a domain-lock `allowedHosts` (web review — security boundary).
  - S6b `generateDreamCode` honors `codePrefix`/`codeDigits`.
  - Each verified by browser click-path, EN + ES.
- **S7 — Template + docs.** Expand `create_template.py` (added cols + SalesNotes +
  ES); rewrite `Build_Runbook.md`/`Onboarding_Guide.md` to the new flow (kill
  WebP + "fully white-label index.html" + bare `git push` claims).
- **S8 — Validation rules.** Wire §5 into the converter; emit reports.

S2–S5 + S8 are pure tooling (no app code) — lowest risk, land first. S6 touches
`index.html` (config-driven, no scoring/touch) and gets web review. S1 is the
spine; S7 is docs.

---

## 8. Verification plan

- **Automated:** golden-bundle diff test (S1) green for all bundle files after
  S2–S5. Validation rules unit-covered with deliberately-broken fixtures (bad
  tier, missing reason_default, dup id, malformed hex, missing trailing slash).
- **Manual (per the working pattern):** browser click-path on a real generated
  bundle, EN + ES — welcome screen, quiz, results tiers, drawer, accessories,
  email capture, handoff. Confirm dream code reflects config prefix/digits
  end-to-end (welcome tile → reveal → email → Sheet), **including a custom prefix
  and a longer-than-3-digit code** (e.g. `SLEEP` + 6 digits), with the welcome
  tile and the emailed/logged code matching exactly. Confirm domain lock rejects
  an unknown host and allows the configured one + localhost.
- **Web review handoff** (paste raw terminal output, not summaries) for: §3.4
  domain-lock + dream-code edits, store-config schema additions (`allowedHosts`),
  and the golden-bundle diff allow-list.
- **No GUI automation locally** — manual click-path stands in, as in prior ships.

---

## Scope guard (restated)

- Start read-only; this spec is the only artifact until sign-off.
- Do **not** edit `Code.gs` (may emit a checklist only).
- Do **not** change scoring logic or weights.
- Do **not** touch touch-event handling.
- Do **not** continue dead-code / CSS cleanup.
- Do **not** implement a broad architecture rewrite or multi-tenant.
- App stays the existing single-file SPA.
- Quiz questions stay as-is (externalizing them is a separate, later, reviewed
  pass — coupled to locked scoring).

## Open questions for review

1. **Golden-bundle diff tolerance — RESOLVED (2026-05-31).** Use
   **semantic/canonical comparison with a curated allow-list** for cosmetic diffs,
   not byte-identical (§4).
2. **Domain-lock timing (S6a) — RESOLVED (audit + approval 2026-05-31).** A direct
   `STORE_CONFIG.allowedHosts` read is impossible: the lock is a synchronous
   parse-time IIFE that runs before the config is declared/fetched (timing + TDZ +
   async fetch). **Approved mechanism: M1** — project `store-config.allowedHosts`
   into a generated synchronous `data/allowed-hosts.js` (see §3.4.1). Remaining
   review items before implementation: (a) confirm/accept M1's availability
   tradeoff (missing `allowed-hosts.js` blanks production; mitigated by validation
   + golden test). Sub-item (b) inspect the second `hostname` read at
   `index.html:6815` — **RESOLVED (audit 2026-05-31)**: it is `isDevelopmentMode()`,
   not a gate, and needs no change under M1 (see §3.4.1).
3. **Code.gs in the TODO report — RESOLVED (2026-05-31).** Emit a **checklist** of
   strings to replace, **not** a generated diff (§6).
4. **Workbook fixture form — RESOLVED (2026-05-31).** **Script-generated** from the
   committed `data/`+config so it can't drift; binary `.xlsx` only as a build
   artifact (§4).
