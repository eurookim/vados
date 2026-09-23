"""Dashboard page: monthly summary, budgets, AI insight, upcoming recurring."""
import html
from datetime import date, datetime

import streamlit as st

from ai import generate_insight
from database import (
    format_currency,
    get_budget_targets,
    get_default_currency,
    get_monthly_summary,
    get_or_create_profile,
    get_upcoming_recurring,
    update_profile,
)


def _insight_is_stale(profile):
    last = profile.get("last_insight_at")
    if last is None:
        return True
    try:
        return (datetime.now() - datetime.fromisoformat(last)).days >= 7
    except (ValueError, TypeError):
        return True


def _fetch_insight(record_time):
    try:
        insight = generate_insight()
        if record_time:
            update_profile(last_insight_at=datetime.now().isoformat())
    except Exception:
        insight = "Couldn't generate an insight right now."
    st.session_state["last_insight"] = insight
    return insight


def show_dashboard():
    st.title("Dashboard")
    today = date.today()

    # Month selector
    col_month, col_year, _ = st.columns([1, 1, 2])
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    with col_month:
        sel_month = st.selectbox(
            "Month", months, index=today.month - 1, key="dash_month", label_visibility="collapsed"
        )
    with col_year:
        sel_year = st.selectbox(
            "Year", range(today.year - 2, today.year + 1), index=2, key="dash_year", label_visibility="collapsed"
        )
    view_month = months.index(sel_month) + 1
    view_year = sel_year

    summary = get_monthly_summary(view_year, view_month)
    targets = get_budget_targets()
    cur = get_default_currency()

    # Summary cards
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", format_currency(summary['total_income'], cur))
    c2.metric("Total Spent", format_currency(summary['total_expenses'], cur))
    net = summary["net_balance"]
    net_color = "var(--positive)" if net >= 0 else "var(--negative)"
    net_display = format_currency(net, cur)
    c3.markdown(f"""
    <div style="background: linear-gradient(135deg, var(--card), var(--card-end)); border: 1px solid var(--border);
        border-radius: 16px; padding: 20px 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <p style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 500; text-transform: uppercase;
            letter-spacing: 0.05em; margin: 0;">Net Balance</p>
        <p style="color: {net_color}; font-size: 1.8rem; font-weight: 700; margin: 0;">
            {net_display}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Category spending bars
    st.subheader("Spending by Category")
    by_cat = summary["by_category"]
    if by_cat:
        cats = sorted(by_cat.keys(), key=lambda c: -by_cat[c])
        max_val = max(by_cat.values()) if by_cat else 1

        for cat in cats:
            spent = by_cat[cat]
            limit = targets.get(cat)
            col1, col2 = st.columns([3, 1])
            with col1:
                if limit:
                    pct = spent / limit
                    bar_label = f"{cat}: {format_currency(spent, cur)} / {format_currency(limit, cur)} ({pct*100:.0f}%)"
                    st.progress(min(pct, 1.0), text=bar_label)
                    if pct >= 0.8 and pct < 1.0:
                        with col2:
                            st.warning("Near limit")
                    elif pct >= 1.0:
                        with col2:
                            st.error("Over budget!")
                else:
                    pct_of_max = spent / max_val if max_val > 0 else 0
                    st.progress(min(pct_of_max, 1.0), text=f"{cat}: {format_currency(spent, cur)}")
    else:
        st.info("No expenses logged this month yet.")

    st.markdown("---")

    # AI Insight card
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("AI Insight")
    with col_btn:
        if st.button("🔄 New Insight", key="refresh_insight", use_container_width=True):
            st.session_state["force_insight"] = True
            st.rerun()

    profile = get_or_create_profile()

    # A new insight is due weekly, on request, or when this session has none yet.
    force = st.session_state.pop("force_insight", False)
    has_data = summary["total_income"] > 0 or summary["total_expenses"] > 0
    insight = st.session_state.get("last_insight")
    if has_data and (force or _insight_is_stale(profile)):
        with st.spinner("Generating insight..."):
            insight = _fetch_insight(record_time=True)
    elif has_data and insight is None:
        with st.spinner("Generating insight..."):
            insight = _fetch_insight(record_time=False)

    if insight:
        safe_insight = html.escape(insight)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, var(--info-bg), #1E2850); border: 1px solid var(--border-accent);
            border-left: 4px solid var(--accent); border-radius: 14px; padding: 20px 24px;
            box-shadow: 0 4px 20px rgba(124, 92, 252, 0.1);">
            <p style="color: var(--text-secondary); font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.08em; margin: 0 0 8px 0;">🧠 AI Insight</p>
            <p style="color: var(--text-primary); font-size: 1rem; line-height: 1.5; margin: 0;">{safe_insight}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Start logging transactions to get AI-powered insights!")

    # Upcoming recurring transactions
    upcoming = get_upcoming_recurring(30)
    if upcoming:
        st.markdown("---")
        st.subheader("Upcoming Recurring")
        for rec in upcoming:
            rec_cur = rec.get("currency", cur)
            freq_label = rec["frequency"].capitalize()
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, var(--card), var(--card-end)); border: 1px solid var(--border);
                border-radius: 12px; padding: 14px 18px; margin-bottom: 8px;
                display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: var(--text-primary); font-weight: 600;">{html.escape(rec['description'])}</span>
                    <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 8px;">{freq_label} &middot; {rec['category']}</span>
                </div>
                <div>
                    <span style="color: var(--accent-light); font-weight: 700;">{format_currency(rec['amount'], rec_cur)}</span>
                    <span style="color: var(--text-muted); font-size: 0.8rem; margin-left: 8px;">Due {rec['next_due_date']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
