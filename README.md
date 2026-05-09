# DreamFinder — Bel Furniture

Personalized mattress finder kiosk for Bel Furniture showrooms. A single-page
tablet web app: customers take a 9–12 question sleep quiz, get personalized
mattress recommendations across Gold/Silver/Bronze tiers, browse accessories,
and receive their results plus a discount code by email. Salespeople get a
handoff screen showing the customer's saved picks.

DreamFinder is a **white-label** product — each retailer gets its own repo and
deployment. This repo is Bel Furniture's instance, deployed at:

  https://beford782.github.io/DreamFinder

## Repo orientation

- `index.html` — the entire kiosk app (single-file SPA, no build step). Domain-locked to the configured GitHub Pages host.
- `Code.gs` — Google Apps Script backend for email send + Sheet logging. Deployed separately via the Apps Script editor.
- `data/store-config.json` — Bel-specific branding, copy, GAS endpoint, public asset root, languages, and discount config.
- `data/mattresses.csv` — source-of-truth mattress lineup. Edit here.
- `data/mattresses.json` — generated. **Never edit by hand.** Regenerate with `.\build-data.ps1` from the repo root.
- `data/dict-en.json` / `data/dict-es.json` — generic UI strings, shared across all retailer deployments.
- `images/mattresses/` and `images/accessories/` — JPG product images (lowercase kebab-case filenames, no spaces).

## Day-to-day workflow

1. Edit `data/mattresses.csv` (and optionally `data/mattresses-es.csv` for Spanish translations).
2. Run `.\build-data.ps1` to regenerate `data/mattresses.json`.
3. Commit both the CSV and the JSON together.
4. Push to `main`. GitHub Pages picks up within 1–2 minutes.

For local development, serve the repo over HTTP — `python -m http.server 8000`
or VS Code Live Server. `file://` is not supported (CORS + domain lock).

## Deeper docs

- **Project guide & development conventions** — see [`CLAUDE.md`](CLAUDE.md). Covers app architecture, scoring engine, white-label boundaries, iPad/touch rules, image format conventions, and what not to touch without checking first.
- **New retailer onboarding** — see [`onboarding/Build_Runbook.md`](onboarding/Build_Runbook.md). Step-by-step guide for spinning up a new white-label deployment from a completed onboarding spreadsheet.

## Updating the Apps Script backend

Changes to `Code.gs` in this repo do **not** auto-deploy. After editing, paste
the new contents into the bound Apps Script project, then:

  Manage Deployments → pencil → New version → Deploy

Without the new-version step, the live web app keeps serving the previous
code.
