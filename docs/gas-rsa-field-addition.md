# GAS leads Sheet — column contract & the `rsa` field

`Code.gs` `doPost()` appends one row per submitted lead via
`SpreadsheetApp.getActiveSpreadsheet().getActiveSheet().appendRow([...])`.
The script must be **container-bound to the leads Google Sheet** (so
`getActiveSpreadsheet()` resolves to it).

## Column order (must match the Sheet header row exactly)

`appendRow` writes these 9 values, in this order (see `Code.gs`):

| # | Column header (suggested) | Source / value |
|---|---|---|
| 1 | Timestamp     | `new Date()` (script timezone) |
| 2 | Name          | `name` (`_safeText`, ≤200) |
| 3 | Email         | `email` (validated) |
| 4 | Phone         | `phone` (`_safeText`, ≤40) |
| 5 | Dream Code    | `dreamCode` (Savings Pass code) |
| 6 | Lang          | `en` \| `es` |
| 7 | Matches       | top-6 joined: `"Name (94%)"`, or `"Name (additional comparison option)"` for sub-threshold backfills |
| 8 | Accessories   | up-to-20 accessory names, comma-joined |
| 9 | RSA           | salesperson id from `localStorage 'dreamfinder.<storeKey>.deviceRsa'` (may be empty) |

## Why `rsa` is appended at the END (append, don't insert)

`rsa` was added **as the right-most column** on purpose. Inserting it
mid-row would re-index every column after it and silently misalign all
prior data + any downstream consumers (filters, reports, exports). Appending
at the end keeps existing columns stable.

**Sheet operator action:** add an `RSA` header in column 9 (right of
`Accessories`). If the header is missing, rows still append — the value just
lands in an unlabeled column.

## Notes
- Logging is shape-only (`Logger.log` records `name_len`, `email=set/unset`,
  counts, `lang` — never raw PII). The **Sheet** intentionally stores raw
  name/email/phone (that is the lead).
- This contract is consumed only when `STORE_CONFIG.gasUrl` is set (live mode).
  While `gasUrl` is blank the kiosk never POSTs and no row is written.
