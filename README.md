# EVdataproj

A normalized MySQL portfolio database built from `Portfolio_Data_RAW_practice.xlsx`,
plus a Streamlit app on top of it. Build script: `engineventures/buildportfolio.py`.
Schema + data dump: `engineventures/data/portfolio.sql`. App: `engineventures/app.py`.

**Running it:** put MySQL credentials in `engineventures/.streamlit/secrets.toml`
(see keys in `buildportfolio.py`/`app.py`), then either run
`python buildportfolio.py` from `engineventures/` to rebuild the dump from the raw
xlsx and load it, or load `data/portfolio.sql` directly (`mysql -u user -p < data/portfolio.sql`,
or via DataGrip). Then `streamlit run app.py`. The dump drops and recreates the
`portfolio` database, so it's a clean, repeatable rebuild.

## Schema

Three tables in `portfolio`: **companies** (`company_id`, `company_name`);
**financing_rounds**, one row per round — amount raised, pre/post-money,
price/share, shares outstanding, `round_status` (Closed/Planned), `round_type`
(SAFE/Convertible Note/Priced Equity), plus `source_confidence`/`is_estimate`
flags and a `source_note`; and **data_quality_log**, every cleaning judgment
call, tagged Resolved/Open, linked to companies/rounds via nullable
`company_id`/`round_id` FKs (text columns kept alongside for display).

Why this shape:
- **One row per round**, matching the raw sheets' granularity, so the app can
  model dilution round-by-round instead of a single current snapshot.
- **`round_status`/`round_type` split out** rather than one status field —
  SAFEs/notes have no pre-money valuation, and some rounds (e.g. Nimbus Series B)
  are priced on paper but not legally closed.
- **`ownership_pct_new_investor` is recomputed** as `amount_raised / post_money`
  for every row instead of trusting each sheet's own Ownership% column, which
  used inconsistent (and in Halcyon's case, broken) formulas.
- **`ownership_pct_fund_position`** is a separate column used only for Verdant
  Bio, the one sheet tracking Engine's own cumulative stake rather than each
  round's new-money % — kept separate so the two meanings aren't conflated.
- **`source_confidence`/`is_estimate` flags** let the app warn when a row rests
  on an unresolved conflict instead of showing every number with equal confidence.
- **CHECK constraints** enforce allowed vocabulary at the DB layer; numeric/date
  sanity rules (positive amounts, pre+raise≈post, no future dates on Closed
  rounds) live in the app's form validation instead.

## Data issues found

(also visible in `data/portfolio.sql`'s INSERT statements)

Resolved with a clear basis:
- Ridgeline Materials was in $000s per its own footnote — dollar fields ×1,000.
- Ridgeline Series B's amount raised was entered as -22,000 — corrected to
  positive, confirmed as a typo by the sheet footnote and Slack notes.
- Verdant Bio's sheet stacked two scenarios in one tab; only the base-case
  "continue pro-rata" history was loaded, the hypothetical "pause" branch excluded.
- Nimbus Series B and Verdant Series C are priced on paper but not closed —
  set to `round_status = Planned` with no `date_closed`.
- `data_quality_log` originally linked to companies/rounds only by free-text
  name, so a rename would silently break the association — added nullable
  `company_id`/`round_id` FKs, populated at insert time instead of matched by
  name after the fact.

Left open (flagged, not guessed):
- Nimbus "Series A-2" vs "Series A2", same date, different amounts ($4.0M vs
  $4.5M) — nothing in the workbook resolves it, so both rows are kept and
  cross-flagged `needs_review`.
- Halcyon Series A has two rows, one with a broken `#DIV/0!` share count — kept
  the complete ($9.5M / 15.2M shares) row, flagged, since Slack notes say
  finance still needs to confirm 9.0M vs 9.5M.
- Fathom Pre-Seed: tracker shows $750K on 1/10/22; an unconfirmed Slack note
  mentions a possibly-same-event "$1.2M SAFE." Kept the tracker's $750K rather
  than overwrite it with an unconfirmed figure.

## What I'd do next with more time

- Reconcile the three open items above with the deal team instead of leaving
  them flagged indefinitely.
- Model liquidation preferences/participation and an option-pool refresh in
  the exit scenario — currently a straight-line ownership % × exit value.
- Track Engine's actual dollars invested and dates per round, to show real
  IRR on Engine's cash flows instead of an implied valuation CAGR.
- Extend `ownership_pct_fund_position` to all five companies once Engine's
  actual check size per round is available, rather than approximating it from
  new-investor % for four of them.
- Fix the Add/Edit Round form so saving an edit clears/updates
  `source_confidence`/`is_estimate` instead of leaving a resolved row flagged.
- Harden form validation for edge cases not exercised by the current dataset
  (very large amounts, stray whitespace, other malformed input).

## AI assistant use
I used Claude Code throughout this project. I defined the schema decisions, the data issues to resolve (and which ones to leave open), and the functionality I wanted in the interface — Claude Code then generated the extraction script, database build, and Streamlit app to match. I reviewed its output against the raw source data to confirm nothing was invented or mis-transcribed, and directed the data-quality judgment calls myself rather than letting the tool decide how to handle conflicts or ambiguity.

