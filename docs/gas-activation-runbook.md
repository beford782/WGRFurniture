# WG&R lead-capture activation runbook (Apps Script + Sheet)

How to turn the **preview-mode** Save-your-Sleep-Brief flow into **live** lead
capture. The app is built for **single-field activation**: the only repo change
to go live is setting `STORE_CONFIG.gasUrl` in `data/store-config.json`.
Everything else in the UI already branches off that value.

> Preflight truth (current state): `gasUrl=""` ⇒ no POST, no email, nothing
> stored. `Code.gs` is committed but **not deployed**.

---

## Phase B — Google Sheet + Apps Script (outside the repo)
1. Create the **leads Google Sheet**. Add the header row per
   `docs/gas-rsa-field-addition.md` (9 columns; `RSA` last).
2. **Extensions → Apps Script** from that Sheet (container-bound, so
   `getActiveSpreadsheet()` resolves correctly).
3. Paste the repo's `Code.gs`.
4. Set `RESULT_EMAIL_BCC` (top of `Code.gs`) to WG&R's lead-intake inbox
   (or `''` to disable BCC). Default today is the shared `dreamfinderleads@gmail.com`.
5. **Deploy → New deployment → Web app**: *Execute as: Me*, *Who has access:
   Anyone*. Authorize the Gmail + Sheets scopes when prompted.
6. Copy the **`/exec` Web App URL**.

## Phase C — Test deployment with a seed inbox (no live change)
1. Point a **local, uncommitted** `gasUrl` at the test `/exec`.
2. Submit the flow in **EN and ES** with a seed email you control. Verify:
   - Sheet row appends with correct columns (incl. `lang`, `rsa`, matches, accessories).
   - Customer email arrives — correct EN/ES subject (now "Sleep Brief & Savings
     Pass" / "Resumen de Sueño y Pase de Ahorro"), body renders in Gmail/Outlook/iOS,
     images load, DREAM code + Sleep Brief + matches present, no broken links.
   - BCC inbox receives a copy.
   - Error paths: invalid email → friendly message; GAS unreachable → network error.
   - GAS execution log is shape-only (no raw PII).
   - POST works cross-origin from `beford782.github.io`.
3. Iterate on `Code.gs` email copy/rendering here (this is where the email is
   first actually viewable). Consider reordering the email body to lead with the
   Sleep Brief section before the Savings Pass band.

## Phase D — Go live (with explicit approval)
1. Set `data/store-config.json` `gasUrl` to the **production** `/exec`.
2. Commit → back up feature branch → fast-forward `origin/main` (no force).
3. Live-verify one real seed submission end-to-end (Sheet + email + BCC) and the
   preview→live confirmation copy swap.

## Phase E — Production handoff
Document the live deployment (gasUrl, Sheet id, deployment id, BCC, scopes,
unsubscribe process); hand WG&R Sheet access; final live QA; update the session
handoff/memory.

---

## Blocking items before real PII collection (need WG&R-provided content)
- **Privacy/consent:** real Privacy & Terms content for the in-app
  `privacyOverlay`, a value for `text.privacyPolicyContact`, and confirmed
  consent wording (EN/ES).
- **CAN-SPAM for the sent email:** the email currently has **no functional
  unsubscribe** and **no physical mailing address**. Add both (or revise copy)
  before sending real commercial email. WG&R must supply the postal address and
  an unsubscribe destination/process.
