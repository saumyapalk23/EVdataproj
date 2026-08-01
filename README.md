# EVdataproj

A normalized MySQL portfolio database built from `Portfolio_Data_RAW_practice.xlsx`,
plus a Streamlit app on top of it.

- Build script: `engineventures/build_portfolio_db.py`
- Schema + data, as a MySQL dump: `engineventures/data/portfolio.sql`
- App: `engineventures/app.py`

## Running it

**1. MySQL credentials.** Create `engineventures/.streamlit/secrets.toml`
(gitignored — never commit this) with:
```toml
[mysql]
host = "localhost"
port = 3306
user = "your_mysql_user"
password = "your_mysql_password"
database = "portfolio"
```

**2. Build/load the database.** Either run the build script (regenerates
`data/portfolio.sql` from the raw xlsx and executes it against MySQL):
```
cd engineventures
pip install streamlit pandas openpyxl pymysql
python build_portfolio_db.py
```
or, if you just want the already-built data without rerunning extraction,
load the SQL dump directly — via **DataGrip** (open a MySQL data source,
open `data/portfolio.sql` as a query console, run it) or from a terminal:
```
mysql -u your_mysql_user -p < engineventures/data/portfolio.sql
```
The dump starts with `DROP DATABASE IF EXISTS portfolio; CREATE DATABASE portfolio;`,
so it's always a clean rebuild — safe to rerun, but it will wipe anything
added through the app since the last build.

**3. Run the app:**
```
streamlit run app.py
```

I used DataGrip mainly to poke around the schema directly, spot-check rows
against the raw xlsx while cleaning, and re-run the dump by hand when
iterating on the build script without going through Streamlit. I also wanted to get a proper GUI or visual representation of my schema, and DataGrip is often crucial to doing that!
 
## Schema

Three tables in the `portfolio` MySQL database:

- **companies** — `company_id`, `company_name`.
- **financing_rounds** — one row per round: amount raised, pre/post-money,
  price/share, shares outstanding, `round_status` (`Closed`/`Planned`),
  `round_type` (`SAFE`/`Convertible Note`/`Priced Equity`), plus
  `source_confidence` and `is_estimate` flags and a free-text `source_note`.
- **data_quality_log** — every judgment call made while cleaning the data,
  tagged `Resolved` or `Open`, with the issue and how (or whether) it was
  resolved.

Why this shape:
- **One row per round, not one row per company.** The raw sheets already
  had this granularity; keeping it lets the app model dilution round-by-round
  instead of just showing a current snapshot.
- **`round_status` and `round_type` as separate fields.** SAFEs and
  convertible notes don't have a pre-money valuation, and rounds like
  Nimbus's Series B are priced-on-paper but not legally closed. Collapsing
  these into one status field would have hidden that distinction.
- **`ownership_pct_new_investor` is recomputed for every row** as
  `amount_raised / post_money`, rather than trusting each sheet's own
  Ownership% column. Those columns used inconsistent (and in Halcyon's case,
  broken) formulas — see Data Issues below. Recomputing gives one comparable
  number across all five companies.
- **`ownership_pct_fund_position`** is a separate column, used only for
  Verdant Bio, which is the one sheet that appeared to track Engine's own
  cumulative diluting stake rather than each round's new-money %. Kept
  separate rather than merged so the two different meanings don't get
  conflated.
- **`source_confidence` / `is_estimate` flags** exist so the app can visibly
  warn a user when they're looking at a row built on an unresolved conflict,
  instead of presenting every number with equal confidence.
- **CHECK constraints in the schema itself** (`round_status`, `round_type`,
  `source_confidence`, `is_estimate`) enforce the allowed vocabulary at the
  database layer; other rules — amounts must be positive, post-money should
  reconcile with pre-money + raise, dates can't be in the future for a
  Closed round — are enforced in the app's form validation instead.

## Data issues found (full list in the `data_quality_log` table — also
baked into `data/portfolio.sql`'s INSERT statements, so it's readable
without a database connection)

Resolved with a clear basis:
- **Ridgeline Materials** was in $000s per its own footnote — all dollar
  fields multiplied by 1,000.
- **Ridgeline Series B** amount raised was entered as -22,000 — corrected to
  positive; confirmed as a typo by both the sheet footnote and the Slack notes.
- **Verdant Bio**'s sheet stacked two scenarios ("continue pro-rata" and
  "pause after Series B") in one tab. Only the base-case "continue" scenario
  was loaded as history; the "pause" branch is a hypothetical, not something
  that happened, so it was excluded rather than merged in.
- **Nimbus Series B** and **Verdant Series C** are priced on paper but not
  closed (Nimbus: "TBD 2027" / IC guidance only; Verdant: notes say the
  close date slipped a quarter) — both set to `round_status = Planned`
  with no `date_closed`, rather than treated as confirmed rounds.

Left open (flagged, not guessed):
- **Nimbus "Series A-2" vs "Series A2"**, both dated 5/22/2023 with different
  amounts ($4.0M vs $4.5M raised). Nothing in the workbook says which is
  right, or whether they're two real tranches. Both rows are kept, each
  flagged `needs_review`, cross-referencing the other.
- **Halcyon Series A**, two rows for the same round — one with a broken
  `#DIV/0!` share count, one complete. Kept the complete ($9.5M / 15.2M
  shares) row and flagged it, but the sheet and Slack notes both say this
  still needs finance to confirm 9.0M vs 9.5M.
- **Fathom Pre-Seed**: tracker shows $750K on 1/10/22; a Slack note mentions
  an unconfirmed "$1.2M SAFE" on the same date, possibly the same event.
  Kept the tracker's $750K rather than overwrite it with an unconfirmed note.

## What I'd do next with more time

- Reconcile the three open items above with the deal team instead of leaving
  them flagged indefinitely.
- Model liquidation preferences/participation and an option-pool refresh in
  the exit scenario — right now both the future-round and exit tools use a
  straight-line ownership % × exit value, which the app calls out in-app but
  is a real simplification.
- Track Engine's actual dollars invested and dates per round (not just each
  round's total), which would let the exit tab show a real IRR on Engine's
  cash flows instead of an implied valuation CAGR.
- Add a proper `ownership_pct_fund_position` for all five companies rather
  than just Verdant, if/when Engine's actual check size per round is
  available — right now the other four companies approximate Engine's stake
  using the new-investor % as a stand-in, which the app flags but isn't ideal.
- Editing an existing round in the app currently doesn't clear/update
  `source_confidence` or `is_estimate` on save — a flagged row stays flagged
  even after the edit resolves the underlying issue. Worth fixing.

## AI assistant use

I used Claude Code throughout this project. I defined the schema decisions,
the data issues to resolve (and which ones to leave open), and the
functionality I wanted in the interface — Claude Code then generated the
extraction script, database build, and Streamlit app to match. I reviewed
its output against the raw source data to confirm nothing was invented or
mis-transcribed, and directed the data-quality judgment calls myself rather
than letting the tool decide how to handle conflicts or ambiguity.