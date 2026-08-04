# EVdataproj

MySQL portfolio database built from `Portfolio_Data_RAW_practice.xlsx`, plus a
Streamlit app on top. Build: `engineventures/buildportfolio.py`. Schema + data:
`engineventures/data/portfolio.sql`. App: `engineventures/app.py`.

**Running it:**

1. Copy `engineventures/.streamlit/secrets.toml.example` to
   `engineventures/.streamlit/secrets.toml`.
2. Fill in real MySQL credentials (`host`, `port`, `user`, `password`,
   `database`) in that file. It's gitignored and won't be committed.
3. Load the schema + data — either:
   - Run `python buildportfolio.py` from `engineventures/` to rebuild the
     database from the raw xlsx, or
   - Load `data/portfolio.sql` directly (`mysql -u user -p < data/portfolio.sql`,
     or open it in DataGrip).
4. Run `streamlit run app.py` from `engineventures/`.

## Schema

Three tables: **companies** (id, name); **financing_rounds**, one row per
round (amount raised, pre/post-money, price/share, shares outstanding,
`round_status`, `round_type`, plus `source_confidence`/`is_estimate` flags);
**data_quality_log**, every cleaning judgment call, linked to companies/rounds
via nullable FKs.

Why: one row per round matches the raw sheets and lets the app model dilution
round-by-round rather than a single snapshot. `round_status`/`round_type` are
split out because SAFEs/notes have no pre-money valuation, and some rounds
are priced but not legally closed. `ownership_pct_new_investor` is
recomputed (`amount_raised / post_money`) rather than trusted from each
sheet's own column, since those formulas were inconsistent and in one case
broken. `source_confidence`/`is_estimate` let the app flag rows resting on
an unresolved conflict instead of showing every number with equal confidence.

## Data issues

Resolved:
- Ridgeline Materials was in $000s per its footnote â€” dollar fields Ã—1,000.
- Ridgeline Series B's amount raised was entered as negative â€” corrected,
  confirmed as a typo by the footnote and Slack notes.
- Verdant Bio's sheet stacked two scenarios in one tab â€” only the base-case
  history was loaded; the hypothetical branch was excluded.
- Nimbus Series B and Verdant Series C are priced but not closed â€” set to
  `round_status = Planned`, no `date_closed`.

Left open (flagged, not guessed):
- Nimbus has two same-date rows ("Series A-2" vs "A2") with different
  amounts â€” nothing in the workbook resolves it, so both are kept and
  cross-flagged.
- Halcyon Series A has a duplicate row with a broken share count â€” kept the
  complete row, flagged for finance to confirm.
- Fathom Pre-Seed: an unconfirmed Slack note suggests a different amount
  than the tracker â€” kept the tracker's figure rather than overwrite it
  with an unconfirmed one.

## What I'd do next

- Sit down with the deal team and actually settle the three flagged conflicts instead of leaving them open forever.
- Make the exit math less of a straight line — right now it's just ownership % × exit value, but real payouts depend on who gets paid first (preferred vs. common), so that's the next thing to build in.
- Actually track how much Engine put into each round and when, so we can calculate a real return (IRR) instead of just inferring it from valuation growth.
- Right now the "Engine's ownership" tracking only really works cleanly for one company (Verdant) — extend that to the other four once we know what Engine actually put in.
- Throw some messier inputs at it — huge numbers, extra spaces, typos, blank fields — since the current data doesn't really stress-test the form or the backfill logic.

## AI/general tool use

I used Claude Code throughout this project. I defined the schema decisions, the data issues to resolve (and which ones to leave open), and the functionality I wanted in the interface — Claude Code then generated the extraction script, database build, and Streamlit app to match. Throughout this process, I learned more about prompt engineering and directing my requests to get an attainable and desirable answer. For a lot of my prompts, I wanted to make sure I didn't accidentally skew the LLM in a direction where it also messed with the logic of the system, and only focused on one specific aspect. I reviewed its output against the raw source data to confirm nothing was invented or mis-transcribed, and directed the data-quality judgment calls myself rather than letting the tool decide how to handle conflicts or ambiguity. I also used VSCode for all my files and DataGrip for a visual and clear representation to ensure my schema was looking the way I intended.

