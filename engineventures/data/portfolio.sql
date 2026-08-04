-- MySQL dump for the "portfolio" database -- open this in
-- DataGrip, or it's run directly against MySQL by this script.
-- Includes referential integrity

DROP DATABASE IF EXISTS portfolio;
CREATE DATABASE portfolio;
USE portfolio;

DROP TABLE IF EXISTS companies;
CREATE TABLE IF NOT EXISTS companies (
    company_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) UNIQUE NOT NULL
);

DROP TABLE IF EXISTS financing_rounds;
CREATE TABLE IF NOT EXISTS financing_rounds (
    round_id INT AUTO_INCREMENT PRIMARY KEY,
    company_id INT NOT NULL,
    round_name VARCHAR(255) NOT NULL,
    round_order INT NOT NULL,
    date_closed DATE,
    round_status VARCHAR(20) NOT NULL CHECK (round_status IN ('Closed', 'Planned')),
    round_type VARCHAR(30) NOT NULL CHECK (round_type IN ('SAFE', 'Convertible Note', 'Priced Equity')),
    amount_raised_usd DOUBLE,
    pre_money_usd DOUBLE,
    post_money_usd DOUBLE,
    price_per_share DOUBLE,
    shares_post_round DOUBLE,
    ownership_pct_new_investor DOUBLE,
    ownership_pct_fund_position DOUBLE,
    source_confidence VARCHAR(20) NOT NULL CHECK (source_confidence IN ('confirmed', 'needs_review')),
    is_estimate TINYINT NOT NULL CHECK (is_estimate IN (0, 1)),
    source_note TEXT,
    created_at VARCHAR(32) NOT NULL,
    updated_at VARCHAR(32) NOT NULL,
    CONSTRAINT fk_financingRoundsCompany FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

DROP TABLE IF EXISTS data_quality_log;
CREATE TABLE IF NOT EXISTS data_quality_log (
    issue_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    round_name VARCHAR(255),
    company_id INT NULL,
    round_id INT NULL,
    issue TEXT NOT NULL,
    resolution TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('Resolved', 'Open')),
    logged_at VARCHAR(32) NOT NULL,
    CONSTRAINT fk_dataQualityLogCompany FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT fk_dataQualityLogRound FOREIGN KEY (round_id) REFERENCES financing_rounds (round_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

INSERT INTO companies (company_id, company_name) VALUES
    (1, 'Nimbus Robotics'),
    (2, 'Verdant Bio'),
    (3, 'Fathom Analytics'),
    (4, 'Ridgeline Materials'),
    (5, 'Halcyon Health');

INSERT INTO financing_rounds (round_id, company_id, round_name, round_order, date_closed, round_status, round_type, amount_raised_usd, pre_money_usd, post_money_usd, price_per_share, shares_post_round, ownership_pct_new_investor, ownership_pct_fund_position, source_confidence, is_estimate, source_note, created_at, updated_at) VALUES
    (1, 1, 'Pre-Seed SAFE', 1, '2021-03-12', 'Closed', 'SAFE', 500000, NULL, NULL, NULL, NULL, NULL, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (2, 1, 'Seed', 2, '2021-11-04', 'Closed', 'Priced Equity', 3200000, 9000000, 12200000, 1.05, 11619047, 0.26229508196721313, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (3, 1, 'Series A', 3, '2022-09-30', 'Closed', 'Priced Equity', 11000000, 40000000, 51000000, 3.4, 15000000, 0.21568627450980393, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (4, 1, 'Series A2', 4, '2023-05-22', 'Closed', 'Priced Equity', 4000000, 51000000, 55000000, 3.67, 15000000, 0.07272727272727272, NULL, 'needs_review', 1, 'Duplicate/conflicting round dated 5/22/2023 (sheet had both ''Series A-2'' and ''Series A2'' labels); cross-ref: other row shows $4.5M raised / $55.5M post. Not reconciled -- see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (5, 1, 'Series A2', 4, '2023-05-22', 'Closed', 'Priced Equity', 4500000, 51000000, 55500000, 3.7, 15000000, 0.08108108108108109, NULL, 'needs_review', 1, 'Duplicate/conflicting round dated 5/22/2023 (sheet had both ''Series A-2'' and ''Series A2'' labels); cross-ref: other row shows $4.0M raised / $55.0M post. Not reconciled -- see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (6, 1, 'Bridge Note', 5, '2024-08-01', 'Closed', 'Convertible Note', 2000000, NULL, NULL, NULL, NULL, NULL, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (7, 1, 'Series B', 6, NULL, 'Planned', 'Priced Equity', 25000000, 110000000, 135000000, 7.33, 18409091, 0.18518518518518517, NULL, 'needs_review', 1, 'IC guidance only; unpriced as of last IC update per sheet footnote and Portfolio Notes (~$135M post, nothing signed). price_per_share/shares_post_round/ownership_pct_new_investor left blank at extraction, later back-computed as projected/unconfirmed estimates -- see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (8, 2, 'Seed', 1, '2020-06-01', 'Closed', 'Priced Equity', 2000000, 6000000, 8000000, NULL, NULL, 0.25, 0.25, 'confirmed', 0, 'Tracker sheet (''Continue Pro-Rata Participation'' scenario); stored Ownership% preserved as fund position metric, see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (9, 2, 'Series A', 2, '2021-08-15', 'Closed', 'Priced Equity', 9000000, 30000000, 39000000, NULL, NULL, 0.23076923076923078, 0.1923, 'confirmed', 0, 'Tracker sheet (''Continue Pro-Rata Participation'' scenario); stored Ownership% preserved as fund position metric, see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (10, 2, 'Series B', 3, '2023-02-10', 'Closed', 'Priced Equity', 20000000, 90000000, 110000000, NULL, NULL, 0.18181818181818182, 0.0727, 'confirmed', 0, 'Tracker sheet (''Continue Pro-Rata Participation'' scenario); stored Ownership% preserved as fund position metric, see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (11, 2, 'Series C', 4, NULL, 'Planned', 'Priced Equity', 35000000, 200000000, 235000000, NULL, NULL, 0.14893617021276595, 0.0521, 'needs_review', 1, 'Expected/target close date 2025-04-01 per Portfolio Notes (''pushed to Q2 2025'' update); round not yet confirmed closed as of last tracker update, so date_closed left NULL and status set to Planned.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (12, 3, 'Pre-Seed', 1, '2022-01-10', 'Closed', 'SAFE', 750000, NULL, NULL, NULL, NULL, NULL, NULL, 'needs_review', 0, 'Tracker''s existing $750K figure retained; Portfolio Notes mentions an unconfirmed ''new SAFE $1.2M dated 1/10/22'' referencing the same date -- possible duplicate/conflict, not applied. See data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (13, 3, 'Seed', 2, '2022-10-05', 'Closed', 'Priced Equity', 2500000, 7000000, 9500000, 1.15, 8260870, 0.2631578947368421, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (14, 3, 'Series A', 3, '2023-12-01', 'Closed', 'Priced Equity', 8000000, 26000000, 34000000, 2.9, 11724138, 0.23529411764705882, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (15, 3, 'Series B', 4, '2025-06-18', 'Closed', 'Priced Equity', 22000000, 70000000, 92000000, 6.1, 15081967, 0.2391304347826087, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (16, 4, 'SAFE 1', 1, '2021-02-01', 'Closed', 'SAFE', 400000, NULL, NULL, NULL, NULL, NULL, NULL, 'confirmed', 0, 'Unit conversion: source figures in $000s, multiplied by 1,000.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (17, 4, 'SAFE 2', 2, '2021-09-14', 'Closed', 'SAFE', 600000, NULL, NULL, NULL, NULL, NULL, NULL, 'confirmed', 0, 'Unit conversion: source figures in $000s, multiplied by 1,000.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (18, 4, 'Seed', 3, '2022-04-19', 'Closed', 'Priced Equity', 4200000, 14000000, 18200000, NULL, NULL, 0.23076923076923078, NULL, 'confirmed', 0, 'Unit conversion: source figures in $000s, multiplied by 1,000.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (19, 4, 'Series A', 4, '2023-11-03', 'Closed', 'Priced Equity', 15000000, 60000000, 75000000, NULL, NULL, 0.2, NULL, 'confirmed', 0, 'Unit conversion: source figures in $000s, multiplied by 1,000.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (20, 4, 'Series B', 5, '2025-03-08', 'Closed', 'Priced Equity', 22000000, 150000000, 172000000, NULL, NULL, 0.12790697674418605, NULL, 'confirmed', 0, 'Unit conversion: source figures in $000s, multiplied by 1,000. Amount Raised corrected from -22,000 to +22,000 (typo confirmed by sheet footnote and Portfolio Notes).', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (21, 5, 'Seed', 1, '2021-05-03', 'Closed', 'Priced Equity', 3000000, 8000000, 11000000, 1.0, 11000000, 0.2727272727272727, NULL, 'confirmed', 0, 'Tracker sheet, reconciled, no adjustments.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (22, 5, 'Series A', 2, '2022-06-14', 'Closed', 'Priced Equity', 9500000, 35000000, 44500000, 2.93, 15200000, 0.21348314606741572, NULL, 'needs_review', 1, 'Two Series A rows existed in source (sheet footnote: ''not yet reconciled''); this $9.5M/15.2M-share row retained as the only one with usable share data. Alternate unconfirmed figure: $9.0M raised, shares_post_round and Ownership% broken (#DIV/0!) in source. Pending finance confirmation per Portfolio Notes.', '2026-08-03T00:32:45', '2026-08-03T00:32:45'),
    (23, 5, 'Series B', 3, '2024-01-20', 'Closed', 'Priced Equity', 20000000, 90000000, 110000000, 5.92, 18577778, 0.18181818181818182, NULL, 'confirmed', 0, 'shares_post_round unavailable in source (#DIV/0!); left NULL at extraction rather than estimated. Amount/pre/post-money figures reliable independent of the broken share count. price_per_share/shares_post_round later back-computed by chaining from Series A''s confirmed Shares Post -- see data_quality_log.', '2026-08-03T00:32:45', '2026-08-03T00:32:45');

INSERT INTO data_quality_log (issue_id, company_name, round_name, company_id, round_id, issue, resolution, status, logged_at) VALUES
    (1, 'Nimbus Robotics', 'Series B', 1, 7, 'Series B date given as text ''TBD 2027'' rather than a real date; round not yet priced per sheet footnote.', 'Set round_status=''Planned'', date_closed=NULL, and left price_per_share/shares_post_round/ownership columns blank; amount/pre/post-money retained as IC guidance figures (is_estimate=1).', 'Resolved', '2026-08-03T00:32:45'),
    (2, 'Nimbus Robotics', 'Series A2', 1, 4, 'Two rows both dated 5/22/2023, one labeled ''Series A-2'' ($4.0M raised, $55.0M post) and one ''Series A2'' ($4.5M raised, $55.5M post) -- conflicting or duplicate entries with no basis in the workbook to determine which (if either) is correct, or whether they represent sequential tranches.', 'Not resolved -- inserted both rows sharing round_order, each flagged source_confidence=''needs_review'', is_estimate=1, with source_note cross-referencing the other row''s figures.', 'Open', '2026-08-03T00:32:45'),
    (3, 'Nimbus Robotics', 'Bridge Note', 1, 6, 'Portfolio Notes: ''nimbus robotics - bridge note closed 8/1/24, $2.0M, existing investors only''.', 'Cross-checked against tracker (Bridge Note, 8/1/2024, $2.0M) -- matches exactly, no change needed.', 'Resolved', '2026-08-03T00:32:45'),
    (4, 'Nimbus Robotics', 'Series B', 1, 7, 'Portfolio Notes: ''Nimbus Robotics Series B still not priced, IC guidance is ~$135M post but nothing signed''.', 'Cross-checked against tracker -- confirms Series B is correctly represented as unpriced/Planned with ~$135M post-money guidance, no change needed.', 'Resolved', '2026-08-03T00:32:45'),
    (5, 'Verdant Bio', NULL, 2, NULL, 'Sheet stacks two scenarios in one tab: ''Continue Pro-Rata Participation'' and ''Pause Investing After Series B''.', 'Only ''Continue Pro-Rata Participation'' rows inserted as realized/base-case history. ''Pause'' scenario excluded entirely as a hypothetical forward-looking branch, not settled history.', 'Resolved', '2026-08-03T00:32:45'),
    (6, 'Verdant Bio', NULL, 2, NULL, 'Stored Ownership% column (25% -> 19.2% -> 7.3% -> 5.2%, monotonically decreasing) diverges from amount_raised/post_money recompute (25% -> 23.1% -> 18.2% -> 14.9%).', 'Recomputed ownership_pct_new_investor per the standard rule for all rows. Stored values represent Engine''s own cumulative diluting fund position, not each round''s new-money %, and were preserved separately in ownership_pct_fund_position.', 'Resolved', '2026-08-03T00:32:45'),
    (7, 'Verdant Bio', 'Series C', 2, 11, 'Series C carries a firm date (4/1/2025) and full deal terms in the tracker, but is not confirmed closed.', 'Set round_status=''Planned'', date_closed=NULL. Expected/target close date (2025-04-01, reflecting the ''pushed to Q2 2025'' update in Portfolio Notes) recorded in source_note instead of date_closed.', 'Resolved', '2026-08-03T00:32:45'),
    (8, 'Verdant Bio', 'Series C', 2, 11, 'Portfolio Notes: ''Verdant Bio Series C round pushed back a quarter, expected close now Q2 2025 not Q1''.', 'Cross-checked against tracker date (4/1/2025, which is Q2) -- already reflects this update, no date change needed. (Status handled separately, see other Series C entry.)', 'Resolved', '2026-08-03T00:32:45'),
    (9, 'Fathom Analytics', 'Pre-Seed', 3, 12, 'Portfolio Notes mentions an unconfirmed ''new SAFE, $1.2M, dated 1/10/22'' -- same date as the tracker''s existing Pre-Seed row, which shows $750K raised. Possible duplicate or conflicting entry for the same event.', 'Kept the tracker''s existing $750K figure (not overwritten by the unconfirmed note); flagged source_confidence=''needs_review'' pending deal-team confirmation.', 'Open', '2026-08-03T00:32:45'),
    (10, 'Fathom Analytics', 'Series B', 3, 15, 'Portfolio Notes: ''Fathom Analytics Inc. Series B - closed June 2025, $22M raised, post money ~$92M''.', 'Cross-checked against tracker (6/18/2025, $22M raised, $92M post) -- matches, no change needed.', 'Resolved', '2026-08-03T00:32:45'),
    (11, 'Ridgeline Materials', NULL, 4, NULL, 'Sheet footnote states all dollar figures are in $000s, differing from every other sheet''s raw-dollar convention.', 'Multiplied all Ridgeline dollar fields (amount_raised_usd, pre_money_usd, post_money_usd) by 1,000 before inserting.', 'Resolved', '2026-08-03T00:32:45'),
    (12, 'Ridgeline Materials', 'Series B', 4, 20, 'Amount Raised entered as -22,000 (in $000s) -- both the sheet''s own footnote and Portfolio Notes confirm this is a typo.', 'Corrected to +22,000 ($22M after unit conversion) before insert.', 'Resolved', '2026-08-03T00:32:45'),
    (13, 'Halcyon Health', 'Series A', 5, 22, 'Two conflicting Series A rows in source: $9.0M raised (shares_post_round=0, #DIV/0! ownership -- broken formula artifact) vs. $9.5M raised (complete, 15.2M shares). Sheet footnote and Portfolio Notes both flag as unreconciled, pending finance confirmation.', 'Inserted only the $9.5M row (the only one with usable share data), flagged source_confidence=''needs_review'', is_estimate=1. $9.0M figure preserved here for reference, not inserted as a row.', 'Open', '2026-08-03T00:32:45'),
    (14, 'Halcyon Health', 'Series B', 5, 23, 'shares_post_round was 0/#DIV/0! in source (broken formula, no real share count available).', 'Left shares_post_round and price_per_share NULL rather than estimate a value. ownership_pct_new_investor still computed from amount_raised_usd/post_money_usd, both of which are reliable.', 'Resolved', '2026-08-03T00:32:45'),
    (15, 'All Companies', NULL, NULL, NULL, 'Every sheet''s stored Ownership% column uses a different, unreliable basis (e.g. Halcyon''s equals prior_shares/total_shares_post_round, a cap-table stat, not deal ownership; two Halcyon rows are outright #DIV/0!).', 'Recomputed ownership_pct_new_investor for every row as amount_raised_usd / post_money_usd; no sheet''s stored Ownership% column was used directly (Verdant''s stored values were preserved separately as ownership_pct_fund_position, see separate entry).', 'Resolved', '2026-08-03T00:32:45'),
    (16, 'All Companies', NULL, NULL, NULL, 'Footnote/context text rows are embedded directly inside the data ranges on several sheets (Nimbus row 11, Ridgeline row 8, Halcyon row 7, Verdant row 17), which if not filtered would become garbage financing_rounds rows with null amounts.', 'Rows without a valid Amount Raised value were excluded from extraction; footnote text was reviewed and folded into the relevant data_quality_log entries above as context rather than inserted as rows.', 'Resolved', '2026-08-03T00:32:45'),
    (17, 'Nimbus Robotics', 'Series B', 1, 7, 'Backfill: price_per_share & shares_post_round (Rule 4, chained from prior Shares Post = 15,000,000), ownership_pct_new_investor (Rule 5) had no source value.', 'Auto-computed per the documented rules (projected/unconfirmed, round is Planned and not yet closed); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (18, 'Verdant Bio', NULL, 2, NULL, 'Backfill (Rule 4e): Seed, Series A, Series B, Series C priced round(s) have no Price/Share or Shares Post recorded, and no earlier round for Verdant Bio has a confirmed Shares Post to chain a per-share price from.', 'Left NULL rather than estimated; Price/Share and Shares Post need either a direct source value or a prior round''s confirmed Shares Post to derive from (see README).', 'Resolved', '2026-08-03T00:32:45'),
    (19, 'Fathom Analytics', 'Seed', 3, 13, 'Backfill: shares_post_round (Rule 2) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (20, 'Fathom Analytics', 'Series A', 3, 14, 'Backfill: shares_post_round (Rule 2) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (21, 'Fathom Analytics', 'Series B', 3, 15, 'Backfill: shares_post_round (Rule 2) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (22, 'Ridgeline Materials', NULL, 4, NULL, 'Backfill (Rule 4e): Seed, Series A, Series B priced round(s) have no Price/Share or Shares Post recorded, and no earlier round for Ridgeline Materials has a confirmed Shares Post to chain a per-share price from.', 'Left NULL rather than estimated; Price/Share and Shares Post need either a direct source value or a prior round''s confirmed Shares Post to derive from (see README).', 'Resolved', '2026-08-03T00:32:45'),
    (23, 'Halcyon Health', 'Seed', 5, 21, 'Backfill: price_per_share (Rule 3) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (24, 'Halcyon Health', 'Series A', 5, 22, 'Backfill: price_per_share (Rule 3) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45'),
    (25, 'Halcyon Health', 'Series B', 5, 23, 'Backfill: price_per_share & shares_post_round (Rule 4, chained from prior Shares Post = 15,200,000) had no source value.', 'Auto-computed per the documented rules (computed from this closed round''s own figures); see README ''Data Computation & NULL Handling'' for the formulas used.', 'Resolved', '2026-08-03T00:32:45');
