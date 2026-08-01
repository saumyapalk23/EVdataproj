"""
Streamlit app on top of the MySQL "portfolio" database (companies /
financing_rounds / data_quality_log; see data/portfolio.sql for the schema).
Tab 1 (Add / Update Round) is implemented; Tabs 2-3 (Model Future Round,
Exit Assumptions) are stubbed pending review of Tab 1.
"""

from datetime import date, datetime

import pandas as pd
import pymysql
import streamlit as st

# The app reads/writes the MySQL "portfolio" database (see data/portfolio.sql
# for the schema this expects -- run that file against MySQL, e.g. via
# DataGrip or `mysql < data/portfolio.sql`, before starting the app).
# Connection details come from .streamlit/secrets.toml (gitignored), under
# an [mysql] table with host/port/user/password/database keys.

# Dropdown options shared by the Add/Edit form — kept as module-level
# constants so both the form and any validation logic reference the same list.
ROUND_TYPES = ["SAFE", "Convertible Note", "Priced Equity"]
ROUND_STATUSES = ["Closed", "Planned"]

# Configure the browser tab title and use the full page width (rather than
# Streamlit's default centered/narrow layout) since the tables here are wide.
st.set_page_config(page_title="Portfolio Tracker", layout="wide")


# --------------------------------------------------------------------- #
# Database access helpers
# --------------------------------------------------------------------- #

def get_conn():
    """Open a new connection to the MySQL "portfolio" database, using
    credentials from .streamlit/secrets.toml. Foreign key enforcement is on
    by default in MySQL/InnoDB, so there's no SQLite-style PRAGMA to set."""
    creds = st.secrets["mysql"]
    return pymysql.connect(
        host=creds["host"], port=int(creds.get("port", 3306)),
        user=creds["user"], password=creds["password"],
        database=creds["database"], autocommit=False,
    )


def load_companies(conn):
    """Return all companies (id + name), alphabetically, for the sidebar picker."""
    return pd.read_sql("SELECT company_id, company_name FROM companies ORDER BY company_name", conn)


def load_rounds(conn, company_id):
    """Return every financing round for one company, in display order."""
    df = pd.read_sql(
        "SELECT * FROM financing_rounds WHERE company_id = %s ORDER BY round_order, round_id",
        conn, params=(company_id,),
    )
    # MySQL's DATE column comes back as datetime.date objects (or None), but
    # the rest of this app expects ISO date strings (matching the old SQLite
    # TEXT column) -- normalize once here rather than downstream everywhere.
    df["date_closed"] = df["date_closed"].apply(lambda d: d.isoformat() if pd.notna(d) else None)
    return df


def load_quality_log(conn, company_id=None):
    """Return data-quality log entries.

    With no company_id, returns the full log (used by the Data Quality tab).
    With a company_id, returns that company's entries plus any dataset-wide
    entries (company_id IS NULL -- the synthetic "All Companies" rows), so
    global caveats surface on every company page. Joins on company_id/round_id
    rather than matching company_name/round_name text, but still returns
    those text columns for display.
    """
    if company_id is None:
        return pd.read_sql("SELECT * FROM data_quality_log ORDER BY issue_id", conn)
    return pd.read_sql(
        "SELECT * FROM data_quality_log WHERE company_id = %s OR company_id IS NULL "
        "ORDER BY issue_id",
        conn, params=(company_id,),
    )


def renumber_rounds(conn, company_id):
    """Auto-derive round_order per company from date_closed (Planned/undated
    rounds sort last), so no one has to type an order number by hand."""
    # Pull every round's id + closing date for this company, then sort:
    # undated (Planned) rows sort after dated ones, dated rows sort
    # chronologically, and round_id breaks ties deterministically.
    cur = conn.cursor()
    cur.execute(
        "SELECT round_id, date_closed FROM financing_rounds WHERE company_id = %s",
        (company_id,),
    )
    rows = cur.fetchall()
    rows = sorted(rows, key=lambda r: (r[1] is None, r[1] or date.min, r[0]))
    # Re-write round_order sequentially (1, 2, 3, ...) to match the new sort order.
    for order, (round_id, _) in enumerate(rows, start=1):
        cur.execute(
            "UPDATE financing_rounds SET round_order = %s WHERE round_id = %s",
            (order, round_id),
        )


# --------------------------------------------------------------------- #
# Display formatting helpers — convert raw numeric values (or NaN) into
# the strings shown in tables/metrics.
# --------------------------------------------------------------------- #

def money_fmt(x):
    """Format a dollar amount with thousands separators, or an em-dash if missing."""
    return "–" if pd.isna(x) else f"${x:,.0f}"


def pct_fmt(x):
    """Format a fraction (0.25) as a percentage (25.0%), or an em-dash if missing."""
    return "–" if pd.isna(x) else f"{x:.1%}"


def shares_fmt(x):
    """Format a share count with thousands separators, or an em-dash if missing."""
    return "–" if pd.isna(x) else f"{x:,.0f}"


def escape_markdown_dollars(text):
    """Escape literal $ so Streamlit's markdown renderer doesn't
    interpret a pair of them as a LaTeX math block."""
    return "" if pd.isna(text) else str(text).replace("$", "\\$")


def build_display_table(rounds_df):
    """Turn the raw financing_rounds columns into the human-readable table
    shown in the Add/Update Round tab (formatted currency/percent strings,
    friendlier column names, and a flag column for rows needing review)."""
    if rounds_df.empty:
        return rounds_df
    df = rounds_df.copy()
    # Flag rows that are estimates or explicitly marked as needing review,
    # so they can be visually highlighted below.
    df["Flag"] = df.apply(
        lambda r: "⚠️" if (r["is_estimate"] == 1 or r["source_confidence"] == "needs_review") else "",
        axis=1,
    )
    # Build the presentation-only DataFrame: same data, formatted for reading
    # rather than computation, with renamed columns for the on-screen table.
    display = pd.DataFrame({
        "Flag": df["Flag"],
        "Round": df["round_name"],
        "Order": df["round_order"],
        "Status": df["round_status"],
        "Date Closed": df["date_closed"].fillna("—"),
        "Type": df["round_type"],
        "Amount Raised": df["amount_raised_usd"].map(money_fmt),
        "Pre-Money": df["pre_money_usd"].map(money_fmt),
        "Post-Money": df["post_money_usd"].map(money_fmt),
        "Price/Share": df["price_per_share"].map(lambda x: "–" if pd.isna(x) else f"${x:,.2f}"),
        "Shares Post": df["shares_post_round"].map(shares_fmt),
        "Own% (New Inv.)": df["ownership_pct_new_investor"].map(pct_fmt),
        "Own% (Fund Pos.)": df["ownership_pct_fund_position"].map(pct_fmt),
        "Confidence": df["source_confidence"],
    })
    return display


def highlight_flagged(row):
    """Row-styling function for st.dataframe: give flagged rows a highlighted
    background so they stand out from confirmed/clean rows."""
    if row["Flag"] == "⚠️":
        return ["background-color: #fff3cd"] * len(row)
    return [""] * len(row)


# --------------------------------------------------------------------- #
# Tab 1: Add / Update Round
# --------------------------------------------------------------------- #

def tab_add_update_round(conn, company_id, company_name):
    """Tab that lists a company's existing rounds and lets the user add a
    new one or edit an existing one, with validation before writing to the DB."""
    st.subheader(f"Funding rounds — {company_name}")

    # A save just above may have queued warning/success messages into
    # session_state (see the bottom of this function) because st.rerun()
    # there would otherwise wipe them before they're visible for more than
    # an instant. Show them now, once, so they stay on screen until the
    # user's next interaction reruns the page.
    for level, text in st.session_state.pop("round_save_messages", []):
        getattr(st, level)(text)

    # --- Existing rounds table -------------------------------------- #
    rounds_df = load_rounds(conn, company_id)
    display_df = build_display_table(rounds_df)
    if display_df.empty:
        st.info("No financing rounds recorded yet for this company.")
    else:
        st.dataframe(
            display_df.style.apply(highlight_flagged, axis=1),
            use_container_width=True,
            hide_index=True,
        )

    # --- Data quality notes relevant to this company ----------------- #
    log_df = load_quality_log(conn, company_id)
    if not log_df.empty:
        open_count = (log_df["status"] == "Open").sum()
        with st.expander(f"⚠️ Data quality notes for {company_name} ({len(log_df)} total, {open_count} open)"):
            for _, r in log_df.iterrows():
                badge = "🔴 Open" if r["status"] == "Open" else "✅ Resolved"
                st.markdown(f"**{badge}** — {r['round_name'] or '(dataset-wide)'}")
                st.caption(f"Issue: {escape_markdown_dollars(r['issue'])}")
                st.caption(f"Resolution: {escape_markdown_dollars(r['resolution'])}")
                st.divider()

    st.divider()

    # --- Add / Edit selector (outside the form so the page reacts immediately) ---
    mode = st.radio("Action", ["Add new round", "Edit existing round"], horizontal=True, key="mode_radio")

    # editing_round_id stays None (and prefill stays empty) for the "Add new
    # round" path; for "Edit existing round" they get populated from the
    # selected row so the form below can be pre-filled with its current values.
    editing_round_id = None
    prefill = {}
    if mode == "Edit existing round":
        if rounds_df.empty:
            st.warning("No existing rounds to edit yet.")
            return
        # Build a human-readable label per round for the selectbox, then map
        # the chosen label back to its round_id.
        labels = {
            row.round_id: f"{row.round_name} — {row.date_closed or 'Planned'} (order {row.round_order})"
            for row in rounds_df.itertuples()
        }
        chosen_label = st.selectbox("Select round to edit", list(labels.values()), key="edit_select")
        editing_round_id = [rid for rid, lbl in labels.items() if lbl == chosen_label][0]
        prefill = rounds_df[rounds_df.round_id == editing_round_id].iloc[0].to_dict()

        # --- Delete, gated behind an explicit confirmation checkbox so a
        # stray click can't silently destroy a round (there's no undo). ---
        with st.expander(f"🗑️ Delete '{prefill['round_name']}'"):
            st.warning(
                f"This permanently deletes **{prefill['round_name']}** "
                f"({prefill.get('date_closed') or 'Planned'}) for {company_name}. "
                "This can't be undone."
            )
            confirm_delete = st.checkbox(
                "Yes, permanently delete this round.",
                key=f"delete_confirm_{editing_round_id}",
            )
            if st.button(
                "Delete round", type="primary", disabled=not confirm_delete,
                key=f"delete_btn_{editing_round_id}",
            ):
                cur = conn.cursor()
                cur.execute("DELETE FROM financing_rounds WHERE round_id = %s", (editing_round_id,))
                renumber_rounds(conn, company_id)
                conn.commit()
                st.session_state["round_save_messages"] = [
                    ("success", f"Deleted '{prefill['round_name']}'.")
                ]
                st.rerun()

    # Unique key suffix so widget state doesn't leak between companies/rounds
    # when Streamlit reruns the script (e.g. switching companies or the round
    # being edited shouldn't reuse another round's stale widget values).
    widget_scope = f"{company_id}_{editing_round_id or 'new'}"

    # --- Reactive controls that determine what the form below looks like ---
    # These live outside st.form so changing them (e.g. round type) immediately
    # re-renders the form fields below (enabling/disabling priced-round fields)
    # without waiting for a submit click.
    col1, col2 = st.columns(2)
    with col1:
        round_type = st.selectbox(
            "Round type", ROUND_TYPES,
            index=ROUND_TYPES.index(prefill.get("round_type", "Priced Equity")),
            key=f"round_type_{widget_scope}",
        )
    with col2:
        round_status = st.selectbox(
            "Round status", ROUND_STATUSES,
            index=ROUND_STATUSES.index(prefill.get("round_status", "Closed")),
            key=f"round_status_{widget_scope}",
        )

    is_priced = round_type == "Priced Equity"

    col3, col4 = st.columns(2)
    with col3:
        amount_raised = st.number_input(
            "Amount raised (USD)", min_value=0.0,
            value=float(prefill.get("amount_raised_usd") or 0.0),
            step=10000.0, format="%.2f",
            key=f"amount_{widget_scope}",
        )
    with col4:
        # Pre-money only makes sense for a priced round (SAFEs/notes convert
        # later without a set valuation at this stage), so disable it otherwise.
        pre_money = st.number_input(
            "Pre-money (USD)", min_value=0.0,
            value=float(prefill.get("pre_money_usd") or 0.0),
            step=10000.0, format="%.2f",
            disabled=not is_priced,
            key=f"pre_money_{widget_scope}",
            help="Disabled for SAFE / Convertible Note — these instruments don't have a priced pre-money valuation.",
        )

    # Live-computed post-money (pre-money + amount raised) used to pre-fill
    # the post-money field inside the form below; the user can still override it.
    computed_post_money = (pre_money + amount_raised) if is_priced else None

    # --- The form itself: final details + submit ---
    # Wrapped in st.form so these fields don't trigger a rerun on every
    # keystroke — only the "Save round" button submits them all at once.
    with st.form(key=f"round_form_{widget_scope}"):
        round_name = st.text_input("Round name", value=prefill.get("round_name", ""))

        date_closed_value = None
        if round_status == "Closed":
            # Default to today, unless editing a round that already has a
            # closing date — then default to that date instead.
            default_date = date.today()
            if prefill.get("date_closed"):
                try:
                    default_date = datetime.strptime(prefill["date_closed"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass
            date_closed_input = st.date_input("Date closed", value=default_date)
            date_closed_value = date_closed_input.isoformat()
        else:
            st.caption("No date — round is Planned, not yet closed. date_closed will be left blank.")

        post_money = st.number_input(
            "Post-money (USD) — auto-computed as pre-money + amount raised; override if needed",
            min_value=0.0,
            value=float(computed_post_money if computed_post_money is not None else (prefill.get("post_money_usd") or 0.0)),
            step=10000.0, format="%.2f",
            disabled=not is_priced,
        )
        price_per_share = st.number_input(
            "Price per share (USD)", min_value=0.0,
            value=float(prefill.get("price_per_share") or 0.0),
            step=0.01, format="%.4f",
            disabled=not is_priced,
        )
        shares_post_round = st.number_input(
            "Shares post-round", min_value=0.0,
            value=float(prefill.get("shares_post_round") or 0.0),
            step=1000.0, format="%.0f",
        )

        submitted = st.form_submit_button("Save round")

    # Nothing below matters until the form is actually submitted — Streamlit
    # reruns this whole function on every interaction, so bail out early
    # otherwise (e.g. while the user is still typing into the form fields).
    if not submitted:
        return

    # ------------------------------------------------------------------ #
    # Validation — nothing is written until all of this passes.
    # ------------------------------------------------------------------ #
    errors = []
    warnings = []

    if not round_name.strip():
        errors.append("Round name is required.")

    if amount_raised <= 0:
        errors.append("Amount raised must be greater than 0.")

    if is_priced:
        if pre_money <= 0:
            errors.append("Pre-money is required for Priced Equity rounds.")
        if post_money <= 0:
            errors.append("Post-money is required for Priced Equity rounds.")
        if pre_money > 0 and post_money > 0:
            # Post-money should reconcile with pre-money + amount raised;
            # allow a small tolerance for rounding, but warn (not block) if
            # the user has entered something that doesn't add up.
            expected_post = pre_money + amount_raised
            tolerance = max(1.0, 0.005 * expected_post)
            if abs(post_money - expected_post) > tolerance:
                warnings.append(
                    f"Post-money (\\${post_money:,.0f}) does not reconcile with "
                    f"pre-money + amount raised (\\${expected_post:,.0f}). Proceeding "
                    f"with the value you entered — please confirm this is intentional."
                )

    if round_status == "Closed" and date_closed_value:
        if datetime.strptime(date_closed_value, "%Y-%m-%d").date() > date.today():
            errors.append("Date closed can't be in the future for a Closed round.")

    # Hard errors stop the save entirely; nothing is written to the DB.
    if errors:
        for e in errors:
            st.error(e)
        return

    # Warnings don't block the save, but we can't just st.warning() them here
    # -- st.rerun() below wipes the page before they'd be visible for more
    # than an instant. Queue them in session_state instead so they survive
    # the rerun and get shown (once) at the top of the tab.
    pending_messages = [("warning", w) for w in warnings]

    # ------------------------------------------------------------------ #
    # Compute derived fields and write.
    # ------------------------------------------------------------------ #
    # Priced-round-only fields collapse to None for SAFE/Convertible Note
    # rounds, since those instruments don't have these values yet.
    final_pre = pre_money if is_priced else None
    final_post = post_money if is_priced else None
    final_price = price_per_share if (is_priced and price_per_share > 0) else None
    final_shares = shares_post_round if shares_post_round > 0 else None
    ownership_new_investor = (amount_raised / final_post) if final_post else None
    now = datetime.utcnow().isoformat(timespec="seconds")

    cur = conn.cursor()
    if editing_round_id is None:
        # New round: insert with round_order=0 as a placeholder — it gets
        # recalculated correctly by renumber_rounds() right after.
        cur.execute(
            """
            INSERT INTO financing_rounds (
                company_id, round_name, round_order, date_closed, round_status,
                round_type, amount_raised_usd, pre_money_usd, post_money_usd,
                price_per_share, shares_post_round, ownership_pct_new_investor,
                ownership_pct_fund_position, source_confidence, is_estimate,
                source_note, created_at, updated_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                company_id, round_name.strip(), 0, date_closed_value, round_status,
                round_type, amount_raised, final_pre, final_post, final_price,
                final_shares, ownership_new_investor, None, "confirmed", 0,
                "Entered via Streamlit app.", now, now,
            ),
        )
    else:
        # Existing round: update in place. Fields like
        # ownership_pct_fund_position, source_confidence, is_estimate, and
        # source_note are intentionally left untouched here — they're not
        # collected by this form and shouldn't be overwritten with defaults.
        cur.execute(
            """
            UPDATE financing_rounds SET
                round_name=%s, date_closed=%s, round_status=%s, round_type=%s,
                amount_raised_usd=%s, pre_money_usd=%s, post_money_usd=%s,
                price_per_share=%s, shares_post_round=%s, ownership_pct_new_investor=%s,
                updated_at=%s
            WHERE round_id=%s
            """,
            (
                round_name.strip(), date_closed_value, round_status, round_type,
                amount_raised, final_pre, final_post, final_price, final_shares,
                ownership_new_investor, now, editing_round_id,
            ),
        )

    # Recompute round_order for the whole company (dates may have shifted
    # the ordering), commit, confirm, and rerun so the table above refreshes.
    renumber_rounds(conn, company_id)
    conn.commit()
    pending_messages.append(("success", f"Saved '{round_name}'."))
    st.session_state["round_save_messages"] = pending_messages
    st.rerun()


# --------------------------------------------------------------------- #
# Shared helpers for the "Model Future Round" and "Exit Assumptions" tabs
# --------------------------------------------------------------------- #

def get_latest_priced_round(rounds_df):
    """Most recent Closed round with a post-money value -- i.e. the last
    round that actually established a valuation. Returns (row, is_ambiguous)
    where is_ambiguous flags the Nimbus-style case of multiple conflicting
    rows sharing the same (latest) round_order."""
    # Only Closed rounds with a post-money value count as an established
    # valuation — Planned rounds or unpriced instruments (SAFE/note) don't.
    priced_closed = rounds_df[
        (rounds_df["round_status"] == "Closed") & rounds_df["post_money_usd"].notna()
    ]
    if priced_closed.empty:
        return None, False
    # "Latest" means highest round_order; if more than one row shares that
    # order (a data-quality conflict), flag it as ambiguous and fall back to
    # the most recently entered row (highest round_id) as a best guess.
    max_order = priced_closed["round_order"].max()
    at_max_order = priced_closed[priced_closed["round_order"] == max_order].sort_values("round_id")
    is_ambiguous = len(at_max_order) > 1
    return at_max_order.iloc[-1], is_ambiguous


def get_engine_baseline_ownership(latest_row):
    """Returns (pct, is_approximate). None if nothing is trackable at all."""
    # Prefer the directly-tracked fund position if it exists; otherwise fall
    # back to the new-investor % from the latest round as an approximation
    # (flagged via is_approximate so callers can caveat it in the UI).
    if pd.notna(latest_row["ownership_pct_fund_position"]):
        return float(latest_row["ownership_pct_fund_position"]), False
    if pd.notna(latest_row["ownership_pct_new_investor"]):
        return float(latest_row["ownership_pct_new_investor"]), True
    return None, None


# --------------------------------------------------------------------- #
# Tab 2: Model Future Round
# --------------------------------------------------------------------- #

def tab_model_future_round(conn, company_id, company_name):
    """Tab that projects a hypothetical next financing round (and an
    optional exit) from the company's current cap-table baseline."""
    st.subheader(f"Model a future round — {company_name}")

    # --- Establish the current-state baseline from the latest priced round ---
    rounds_df = load_rounds(conn, company_id)
    latest, is_ambiguous = get_latest_priced_round(rounds_df)

    if latest is None:
        st.warning(
            "No closed, priced round on record for this company yet — "
            "there's nothing to build a cap table baseline from."
        )
        return

    st.markdown("#### Current cap table state")

    if is_ambiguous:
        st.warning(
            f"The latest priced round ('{latest['round_name']}', round_order "
            f"{latest['round_order']}) has multiple conflicting entries in the "
            f"tracker — see the Data Quality tab for the open issue. Using the "
            f"most recently entered row (${latest['post_money_usd']:,.0f} post-money) "
            f"below; treat this baseline as provisional until reconciled."
        )

    engine_pct, engine_is_approx = get_engine_baseline_ownership(latest)

    # Three headline metrics summarizing the baseline: last valuation, total
    # shares outstanding, and Engine's current ownership (if trackable).
    c1, c2, c3 = st.columns(3)
    c1.metric("Latest post-money", money_fmt(latest["post_money_usd"]))
    c1.caption(f"As of {latest['round_name']} ({latest['date_closed'] or 'undated'})")

    c2.metric(
        "Total shares (post-round)",
        shares_fmt(latest["shares_post_round"]) if pd.notna(latest["shares_post_round"]) else "Not tracked",
    )

    if engine_pct is not None:
        c3.metric("Engine's current ownership", pct_fmt(engine_pct))
        if engine_is_approx:
            c3.caption("⚠️ Approximate — see note below.")
        else:
            c3.caption("Tracked fund position.")
    else:
        c3.metric("Engine's current ownership", "Not trackable")

    # Explain *why* the ownership figure is approximate/missing, since the
    # metric above alone doesn't convey that nuance.
    if engine_pct is not None and engine_is_approx:
        st.caption(
            "⚠️ Engine's cumulative ownership isn't separately tracked for this "
            "company, so the latest round's new-investor % is used as a stand-in "
            "for Engine's position. This can overstate or understate Engine's "
            "actual stake if Engine didn't invest in every round, or invested "
            "a different amount than a typical new investor."
        )
    elif engine_pct is None:
        st.caption(
            "No ownership figure (fund position or new-investor %) is available "
            "on the latest priced round to approximate Engine's stake from."
        )

    st.divider()
    st.markdown("#### Assumed new round")

    # --- User-adjustable assumptions for the hypothetical next round ---
    col_a, col_b = st.columns(2)
    with col_a:
        assumed_raise = st.number_input(
            "Assumed new raise amount (USD)", min_value=0.0,
            value=float(latest["amount_raised_usd"] or 0.0),
            step=100_000.0, format="%.2f",
            key=f"future_raise_{company_id}",
        )
    with col_b:
        assumed_pre = st.number_input(
            "Assumed pre-money valuation (USD)", min_value=0.0,
            value=float(latest["post_money_usd"]),
            step=100_000.0, format="%.2f",
            key=f"future_pre_{company_id}",
            help="Defaults to the latest known post-money (a 'flat' round) — adjust as needed.",
        )

    if assumed_raise <= 0 or assumed_pre <= 0:
        st.info("Enter a raise amount and pre-money valuation above to see projections.")
        return

    # --- Derived projections for the hypothetical round ---
    new_post = assumed_pre + assumed_raise
    new_investor_pct = assumed_raise / new_post
    # Existing holders (including Engine) get diluted by pre-money/post-money;
    # only computed if Engine's current ownership is trackable at all.
    diluted_engine_pct = engine_pct * (assumed_pre / new_post) if engine_pct is not None else None

    st.markdown("#### Resulting round")
    r1, r2, r3 = st.columns(3)
    r1.metric("Resulting post-money", money_fmt(new_post))
    r2.metric("New investor ownership % (this round)", pct_fmt(new_investor_pct))

    if diluted_engine_pct is not None:
        r3.metric("Engine's diluted ownership % after round", pct_fmt(diluted_engine_pct))
        if engine_is_approx:
            r3.caption("⚠️ Built on the approximate baseline above — directional, not precise.")
    else:
        r3.metric("Engine's diluted ownership % after round", "Not trackable")
        st.info(
            "Engine's existing stake isn't trackable from this dataset, so a "
            "diluted post-round ownership % can't be computed for Engine — "
            "only the new investor's ownership is shown above."
        )

    st.caption(
        "Dilution model: existing holders (including Engine) are diluted by "
        "pre-money / post-money; this assumes no other changes to the cap "
        "table (e.g. no option pool top-up) beyond the new investor's shares."
    )

    st.divider()
    st.markdown("#### Exit scenario")
    st.caption(
        "⚠️ Simplifying assumption: this is a straight-line ownership% × exit "
        "value calculation only. It does **not** model liquidation preferences, "
        "participation rights, option pool refreshes, or a waterfall — actual "
        "proceeds at exit, especially for preferred stock, would differ."
    )

    # Default exit value is an arbitrary 3x placeholder multiple on the
    # resulting post-money — purely a starting point for the user to adjust.
    exit_value = st.number_input(
        "Assumed exit value (USD)", min_value=0.0,
        value=float(new_post * 3),
        step=1_000_000.0, format="%.2f",
        key=f"exit_value_future_{company_id}",
        help="Default is a placeholder (3x resulting post-money) — adjust to whatever scenario you want to test.",
    )

    if exit_value > 0:
        e1, e2 = st.columns(2)
        if diluted_engine_pct is not None:
            engine_return = diluted_engine_pct * exit_value
            e1.metric("Engine's straight-line return", money_fmt(engine_return))
            if engine_is_approx:
                e1.caption("⚠️ Based on the approximate ownership baseline above.")
        else:
            e1.metric("Engine's straight-line return", "Not trackable")
        new_investor_return = new_investor_pct * exit_value
        e2.metric("New investor's straight-line return", money_fmt(new_investor_return))


# --------------------------------------------------------------------- #
# Tab 3: Exit Assumptions (Fathom Analytics only — see main())
# --------------------------------------------------------------------- #

def tab_exit_assumptions(conn):
    """Fixed walkthrough tab modeling an exit scenario for Fathom Analytics
    specifically, independent of whichever company is selected in the sidebar.
    Only rendered when Fathom Analytics is the selected company (see main())."""
    st.subheader("Exit Assumptions — Fathom Analytics")
    st.caption(
        "Fixed walkthrough company (chosen per instruction) — independent of "
        "the sidebar company selector used in the other tabs."
    )

    # Always load Fathom Analytics specifically, regardless of the sidebar
    # selection, since this tab is a fixed case study rather than per-company.
    companies = load_companies(conn)
    fathom_id = int(companies.loc[companies["company_name"] == "Fathom Analytics", "company_id"].iloc[0])
    rounds_df = load_rounds(conn, fathom_id)
    latest, _ = get_latest_priced_round(rounds_df)

    if latest is None:
        st.error("No priced, closed round found for Fathom Analytics.")
        return

    engine_pct, engine_is_approx = get_engine_baseline_ownership(latest)
    last_post_money = float(latest["post_money_usd"])
    last_round_name = latest["round_name"]
    last_date = latest["date_closed"]
    last_year = datetime.strptime(last_date, "%Y-%m-%d").year if last_date else date.today().year

    # Only "Open" data-quality issues matter here — resolved ones don't need
    # a caveat in the assumptions writeup below.
    open_issues = load_quality_log(conn, fathom_id)
    open_issues = open_issues[open_issues["status"] == "Open"]

    # Explanation of how Engine's ownership baseline was derived, phrased
    # differently depending on whether it's a tracked figure or an approximation.
    engine_note = (
        "tracked directly as a fund position."
        if not engine_is_approx else
        "**not** separately tracked for Fathom — approximated using the "
        f"{last_round_name}'s new-investor % ({pct_fmt(engine_pct) if engine_pct else 'n/a'}) "
        "as a stand-in for Engine's cumulative ownership. This can overstate or "
        "understate the real figure if Engine's actual investment differed from "
        "a pro-rata new-investor position across all rounds."
    )

    # Long-form writeup documenting every assumption behind the numbers below,
    # so the reasoning is transparent rather than a black-box calculation.
    with st.expander("Assumptions & reasoning (read before trusting the numbers below)", expanded=True):
        st.markdown(
            f"""
- **Baseline valuation**: Fathom's last priced round is **{last_round_name}**,
  closed {last_date}, at a **{money_fmt(last_post_money)} post-money**. That's
  the anchor for the exit scenario below.
- **Why a valuation step-up multiple, not a revenue multiple**: this dataset
  tracks financing rounds only — there's no ARR/revenue figure for Fathom to
  apply a "4x revenue" style multiple to. The exit scenario is instead framed
  as a **step-up multiple on the last post-money valuation**, a coarser but
  honestly-available basis given what's actually in the tracker.
- **Default assumed exit multiple: 3.0x** the last post-money. Reasoning: a
  3-5x valuation step-up from a Series B to an eventual exit (strategic
  acquisition or IPO) is a commonly-cited rough benchmark for growth-stage
  SaaS/data-analytics companies that continue to scale. 3.0x is picked as a
  conservative point in that range — it is not a forecast specific to Fathom.
- **Default assumed timeline: 4 years** from the last round ({last_year} →
  {last_year + 4}). Reasoning: 4-6 years from a Series B to strategic
  exit/IPO is a typical hold period cited for venture-backed SaaS companies;
  4 years is the low end of that range.
- **Engine's ownership stake** is {engine_note}
- **Return calculation is straight-line only**: ownership % × exit
  valuation. No liquidation preference, participation rights, option pool
  refresh, or transaction costs/carry are modeled.
- **No IRR on actual cash flows**: Engine's real investment amount/timing per
  round isn't tracked separately from each round's total, so we show an
  implied **valuation compound annual growth rate** (how fast Fathom's valuation would need to
  compound to hit the assumed exit number) rather than a true IRR on Engine's
  cash-in/cash-out.
"""
            # Append an extra bullet noting open data-quality issues, but only
            # if there are any — otherwise this evaluates to an empty string.
            + (
                f"\n- ℹ️ Fathom has {len(open_issues)} open data-quality issue(s) in "
                "the tracker (Pre-Seed SAFE amount conflict) — it doesn't affect "
                "this Series-B-anchored baseline, but see the Data Quality tab."
                if len(open_issues) > 0 else ""
            )
        )

    st.divider()
    st.markdown("#### Adjust the assumptions")
    multiple = st.number_input(
        "Assumed exit multiple (× last post-money)", min_value=0.1,
        value=3.0, step=0.5, key="fathom_exit_multiple",
    )

    # Exit valuation defaults to multiple × last post-money, but the user can
    # override it directly with a specific dollar figure instead.
    computed_exit_valuation = last_post_money * multiple
    exit_valuation = st.number_input(
        "Assumed exit valuation (USD) — defaults to multiple × last post-money; override for a specific scenario",
        min_value=0.0, value=float(computed_exit_valuation),
        step=1_000_000.0, format="%.2f", key="fathom_exit_valuation",
    )
    effective_multiple = exit_valuation / last_post_money if last_post_money else None
    # If the user overrode the computed default, surface what multiple that
    # override actually implies, for consistency with the multiple entered above.
    if abs(exit_valuation - computed_exit_valuation) > max(1.0, 0.005 * computed_exit_valuation):
        st.caption(
            f"ℹ️ Overridden — this implies an effective multiple of "
            f"{effective_multiple:.2f}x on the last post-money, vs. the "
            f"{multiple:.2f}x entered above."
        )

    st.divider()
    st.markdown("#### Resulting return to Engine's position")

    if engine_pct is None:
        st.warning(
            "Engine's ownership stake isn't trackable for Fathom Analytics "
            "from this dataset, so a return can't be computed."
        )
        return

    engine_return = engine_pct * exit_valuation

    r1, r2, r3 = st.columns(3)
    r1.metric("Engine's ownership % (baseline)", pct_fmt(engine_pct))
    if engine_is_approx:
        r1.caption("⚠️ Approximate — see assumptions above.")
    r2.metric("Assumed exit valuation", money_fmt(exit_valuation))
    r2.caption(f"≈ {effective_multiple:.2f}x last post-money")
    r3.metric("Engine's straight-line return", money_fmt(engine_return))
    if engine_is_approx:
        r3.caption("⚠️ Built on the approximate ownership figure above.")

    cagr_col1, cagr_col2 = st.columns(2)
    with cagr_col1:
        years = st.number_input(
            "Years to exit (only affects the growth-rate check below — "
            "doesn't change the return above)",
            min_value=1, value=4, step=1, key="fathom_exit_years",
        )
    # Implied CAGR: the valuation growth rate that would need to hold over
    # `years` to go from last_post_money to exit_valuation.
    cagr = (exit_valuation / last_post_money) ** (1 / years) - 1 if last_post_money and years else None
    if cagr is not None:
        with cagr_col2:
            st.caption(
                f"Implied valuation compound annual growth rate to hit this exit: {cagr:.1%}/year over "
                f"{years} years — a company-valuation growth rate, not a "
                f"cash-flow IRR on Engine's position."
            )


# --------------------------------------------------------------------- #
# Tab 4: Data Quality
# --------------------------------------------------------------------- #

def tab_data_quality(conn):
    """Tab listing every data-quality log entry across all companies, with
    a status filter and summary counts."""
    st.subheader("Data Status Log — all companies")
    log_df = load_quality_log(conn)
    open_count = (log_df["status"] == "Open").sum()
    resolved_count = (log_df["status"] == "Resolved").sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total issues", len(log_df))
    c2.metric("Open", int(open_count))
    c3.metric("Resolved", int(resolved_count))

    status_filter = st.multiselect("Filter by status", ["Open", "Resolved"], default=["Open", "Resolved"])
    filtered = log_df[log_df["status"].isin(status_filter)]
    st.dataframe(
        filtered[["issue_id", "company_name", "round_name", "issue", "resolution", "status", "logged_at"]],
        use_container_width=True, hide_index=True,
    )


# --------------------------------------------------------------------- #
# App entry point
# --------------------------------------------------------------------- #

def main():
    st.title("Portfolio Tracker")

    conn = get_conn()
    companies = load_companies(conn)

    # Sidebar company selector drives which company's data tabs 1, 2, and 4
    # show; tab 3 (Exit Assumptions) ignores this and is Fathom-only.
    st.sidebar.header("Company")
    company_name = st.sidebar.selectbox("Select a company", companies["company_name"])
    company_id = int(companies.loc[companies.company_name == company_name, "company_id"].iloc[0])

    # The Exit Assumptions tab is a fixed Fathom Analytics case study, so it
    # only makes sense to show it when Fathom is the selected company —
    # otherwise the tab list is built without it.
    show_exit_assumptions = company_name == "Fathom Analytics"

    tab_labels = ["Add / Update Round", "Model Future Round"]
    if show_exit_assumptions:
        tab_labels.append("Exit Assumptions")
    tab_labels.append("Data Status Log")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        tab_add_update_round(conn, company_id, company_name)
    with tabs[1]:
        tab_model_future_round(conn, company_id, company_name)
    # Tab indices shift depending on whether Exit Assumptions was included
    # above, so next_tab tracks the current position instead of a fixed index.
    next_tab = 2
    if show_exit_assumptions:
        with tabs[next_tab]:
            tab_exit_assumptions(conn)
        next_tab += 1
    with tabs[next_tab]:
        tab_data_quality(conn)

    conn.close()


if __name__ == "__main__":
    main()
