# EVdataproj

A normalized SQLite portfolio database built from `Portfolio_Data_RAW_practice.xlsx`, plus a Streamlit app on top of it. Build script: `engineventures/build_portfolio_db.py`. Output: `engineventures/data/portfolio.db` and `engineventures/data/data_quality_log.csv`. App: `engineventures/app.py`.

## 1. Schema and reasoning

Three tables: `companies` (`company_id`, `company_name`), `financing_rounds`, and `data_quality_log`.

`financing_rounds` is one row per round per company (`company_id`, `round_name`, `round_order`, `date_closed`, `round_status`, `round_type`, `amount_raised_usd`, `pre_money_usd`, `post_money_usd`, `price_per_share`, `shares_post_round`, `ownership_pct_new_investor`, `ownership_pct_fund_position`, `source_confidence`, `is_estimate`, `source_note`, `created_at`, `updated_at`). Each source workbook tab (Nimbus Robotics, Verdant Bio, Fathom Analytics, Ridgeline Materials, Halcyon Health) had a different column layout and different unit/label conventions, so the build script reads every tab by header name rather than column position, and normalizes into this one shared shape.

- **`round_status` ('Closed'/'Planned') and `round_type` ('SAFE'/'Convertible Note'/'Priced Equity')** are separate fields because they answer different questions. `round_status` comes from whether the row has a real close date (`parse_date` returns `None` for non-date text like "TBD 2027", which the script maps to `Planned`/`date_closed=NULL`). `round_type` is classified in `classify_round_type` from whether the row has a `pre_money` value: no pre-money and "bridge" in the round name → `Convertible Note`, no pre-money otherwise → `SAFE`, pre-money present → `Priced Equity`. `price_per_share`/`shares_post_round`/ownership are left blank for unpriced rounds since those figures don't exist for a SAFE/note.
- **`ownership_pct_new_investor` is always recomputed** as `amount_raised_usd / post_money_usd` (function `pct`) rather than trusted from the source sheets. Per `data_quality_log` issue 15, every sheet's own "Ownership%" column used a different, unreliable basis (e.g. Halcyon's was a cap-table stat, not deal ownership, and two Halcyon rows were `#DIV/0!`), so the script standardizes on one formula applied uniformly.
- **`ownership_pct_fund_position`** is a separate column that exists only because Verdant Bio's sheet had a second, legitimate meaning for "Ownership%": Engine's own cumulative diluting fund stake, not the round's new-money %. That column is preserved here rather than discarded or conflated with `ownership_pct_new_investor` (issue 6).
- **`source_confidence` ('confirmed'/'needs_review') and `is_estimate` (0/1)** flag rows the script isn't fully sure of: unpriced IC-guidance rounds, rows from unresolved duplicate/conflicting entries, and rows where a usable-but-unconfirmed figure was chosen over a broken one. `source_note` carries the specific reasoning per row (e.g. cross-referencing the other conflicting row's numbers) so the flag isn't just a bare boolean.
- **`round_order`** is assigned sequentially per company (`assign_round_orders`) rather than typed by hand; genuinely duplicate/conflicting rows (same round name + date) intentionally share an order number instead of being forced into an artificial sequence.

`data_quality_log` (`issue_id`, `company_name`, `round_name`, `issue`, `resolution`, `status`, `logged_at`) records every judgment call made while building the database, with `status` constrained to `'Resolved'`/`'Open'` — see below.

## 2. Data issues found and how they were handled

From `data/data_quality_log.csv` (16 entries, 13 Resolved, 3 Open):

**Resolved:**
- Nimbus Series B's date was the text "TBD 2027", not a real date → set `round_status='Planned'`, `date_closed=NULL`, `is_estimate=1`, keeping the ~$135M post-money IC guidance figure.
- Verdant Bio's tab stacked two forward-looking scenarios ("Continue Pro-Rata Participation" and "Pause Investing After Series B") in one sheet → only the "Continue Pro-Rata Participation" rows were inserted as realized history; the "Pause" branch was excluded entirely as hypothetical.
- Verdant's stored Ownership% column diverged from the amount/post-money recompute → recomputed `ownership_pct_new_investor` for every row and kept Verdant's original values separately in `ownership_pct_fund_position`.
- Verdant Series C has firm terms and a date in the tracker but isn't confirmed closed → `round_status='Planned'`, `date_closed=NULL`, expected close date recorded in `source_note` instead.
- Ridgeline Materials' whole sheet is denominated in $000s, unlike every other sheet → all Ridgeline dollar fields multiplied by 1,000 on insert.
- Ridgeline Series B's Amount Raised was entered as -22,000 → corrected to +22,000, per the sheet's own footnote and Portfolio Notes confirming it was a typo.
- Halcyon Series B's `shares_post_round` was 0/`#DIV/0!` in source → left `shares_post_round`/`price_per_share` NULL rather than estimated; `ownership_pct_new_investor` still computed since amount/post-money were reliable independent of the broken share count.
- Every sheet's own Ownership% column used an inconsistent basis dataset-wide → standardized on the recompute described above for all rows.
- Footnote/context text embedded inside data ranges on several sheets (Nimbus row 11, Ridgeline row 8, Halcyon row 7, Verdant row 17) → excluded from extraction by requiring a valid Amount Raised value; the footnote text itself was reviewed and folded into the relevant log entries as context.
- Three Portfolio Notes cross-checks (Nimbus Bridge Note, Nimbus Series B guidance, Fathom Series B, Verdant Series C timing) all matched the tracker with no changes needed.

**Open (left unresolved, not softened):**
- **Nimbus Series A2**: two rows both dated 5/22/2023 — one "Series A-2" ($4.0M raised / $55.0M post), one "Series A2" ($4.5M raised / $55.5M post) — with no basis in the workbook to tell which is correct or whether they're sequential tranches. Both rows were inserted sharing a `round_order`, each flagged `needs_review`/`is_estimate=1`, cross-referencing the other's figures in `source_note`. Not reconciled.
- **Fathom Pre-Seed**: Portfolio Notes mention an unconfirmed "new SAFE, $1.2M, dated 1/10/22" on the same date as the tracker's existing $750K Pre-Seed row — possible duplicate or conflicting entry. The tracker's $750K figure was kept and flagged `needs_review`, pending deal-team confirmation; the $1.2M note was not applied.
- **Halcyon Series A**: two conflicting rows — $9.0M raised with `shares_post_round=0`/`#DIV/0!` ownership (broken formula) vs. $9.5M raised with complete 15.2M-share data — both flagged in the sheet footnote and Portfolio Notes as unreconciled. Only the $9.5M row (the one with usable share data) was inserted, flagged `needs_review`/`is_estimate=1`; the $9.0M figure is preserved in the log for reference only.

## 3. What I'd do next

- Reconcile the three Open issues above with the deal team/finance rather than carrying flagged-but-unresolved rows indefinitely.
- The exit-scenario modeling in `app.py` (`tab_model_future_round`, `tab_exit_assumptions`) is explicitly a straight-line ownership% × exit-value calculation — the code's own caption states it does **not** model liquidation preferences, participation rights, option pool refreshes, or a waterfall, which would change actual proceeds for preferred stock.
- Engine's ownership is only directly tracked as a fund position for Verdant Bio; for every other company it's approximated from the latest round's new-investor % (`get_engine_baseline_ownership`), which the app itself flags as able to overstate or understate Engine's real stake.
- The Fathom exit assumptions (3.0x post-money step-up, 4-year timeline) are stated in `tab_exit_assumptions` as generic growth-stage SaaS benchmarks, not figures derived from Fathom's own data — worth replacing with company-specific assumptions if available.
- The dilution model in `tab_model_future_round` assumes no cap-table changes beyond the new investor's shares (e.g. no option pool top-up), which the code calls out directly.
- No true IRR is computed on Engine's actual cash-in/cash-out — `tab_exit_assumptions` substitutes an implied valuation CAGR because per-round Engine investment amounts aren't tracked separately from each round's total.
- The module docstring in `app.py` describes Tabs 2-3 as "stubbed pending review of Tab 1," which no longer matches the current implementation — worth cleaning up that comment or confirming those tabs still need the intended review pass.

## AI assistant use

I used Claude Code throughout this project. I defined the schema decisions, the data issues to resolve (and which ones to leave open), and the functionality I wanted in the interface. Claude Code then generated the extraction script, database build, and Streamlit app to match. I reviewed its output against the raw source data to confirm nothing was invented or mis-transcribed, and directed the data-quality judgment calls myself rather than letting the tool decide how to handle conflicts or ambiguity.