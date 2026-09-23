"""Settings page: goals, currency, budgets, recurring transactions, history import."""
from datetime import date

import streamlit as st

from database import (
    CATEGORIES,
    EXPENSE_CATEGORIES,
    SUPPORTED_CURRENCIES,
    add_recurring_transaction,
    delete_recurring_transaction,
    format_currency,
    get_budget_targets,
    get_default_currency,
    get_or_create_profile,
    get_recurring_transactions,
    remove_budget_target,
    set_budget_target,
    set_default_currency,
    update_profile,
    update_recurring_transaction,
)
from views.common import save_parsed_history


def show_settings():
    st.title("Settings")

    profile = get_or_create_profile()
    targets = get_budget_targets()
    cur = get_default_currency()
    cur_symbol = SUPPORTED_CURRENCIES.get(cur, "$")

    # Goals
    st.subheader("Financial Goals")
    goals = st.text_area("Your goals", value=profile.get("goals", ""), key="settings_goals")
    if st.button("Update Goals"):
        update_profile(goals=goals)
        st.success("Goals updated!")
        st.rerun()

    st.markdown("---")

    # Default currency
    st.subheader("Default Currency")
    currency_list = list(SUPPORTED_CURRENCIES.keys())
    cur_index = currency_list.index(cur) if cur in currency_list else 0
    new_currency = st.selectbox(
        "Currency",
        currency_list,
        index=cur_index,
        format_func=lambda c: f"{c} ({SUPPORTED_CURRENCIES[c]})",
        key="settings_currency",
    )
    if st.button("Update Currency"):
        set_default_currency(new_currency)
        st.success(f"Default currency set to {new_currency}!")
        st.rerun()

    st.markdown("---")

    # Budget targets
    st.subheader("Budget Targets")
    st.caption(f"Set monthly spending limits per category ({cur}). Set to 0 to remove.")
    cols = st.columns(3)
    new_targets = {}
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        with cols[i % 3]:
            current = targets.get(cat, 0.0)
            val = st.number_input(
                f"{cat} ({cur_symbol})", min_value=0.0, value=current, step=10.0,
                key=f"settings_budget_{cat}"
            )
            new_targets[cat] = val

    if st.button("Save Budget Targets"):
        for cat, val in new_targets.items():
            if val > 0:
                set_budget_target(cat, val)
            else:
                remove_budget_target(cat)
        st.success("Budget targets updated!")
        st.rerun()

    st.markdown("---")

    # Recurring transactions
    st.subheader("Recurring Transactions")
    st.caption("Set up transactions that auto-log on a schedule.")

    recurring = get_recurring_transactions(active_only=False)
    if recurring:
        for rec in recurring:
            rec_cur = rec.get("currency", cur)
            active_label = "Active" if rec.get("active") else "Paused"
            with st.expander(
                f"{rec['description']} | {format_currency(rec['amount'], rec_cur)} | "
                f"{rec['frequency']} | :{('green' if rec.get('active') else 'gray')}[{active_label}]"
            ):
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    new_amount = st.number_input(
                        "Amount", min_value=0.01, value=float(rec["amount"]),
                        step=1.0, key=f"rec_amt_{rec['id']}"
                    )
                with rc2:
                    new_freq = st.selectbox(
                        "Frequency", ["weekly", "biweekly", "monthly"],
                        index=["weekly", "biweekly", "monthly"].index(rec["frequency"]),
                        key=f"rec_freq_{rec['id']}"
                    )
                with rc3:
                    new_active = st.checkbox("Active", value=bool(rec.get("active")), key=f"rec_active_{rec['id']}")

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("Save Changes", key=f"rec_save_{rec['id']}"):
                        update_recurring_transaction(
                            rec["id"], amount=new_amount, frequency=new_freq,
                            active=1 if new_active else 0
                        )
                        st.success("Updated!")
                        st.rerun()
                with bc2:
                    if st.button("Delete", key=f"rec_del_{rec['id']}", type="secondary"):
                        delete_recurring_transaction(rec["id"])
                        st.success("Deleted!")
                        st.rerun()

    # Add new recurring transaction
    st.markdown("**Add New Recurring Transaction**")
    ac1, ac2 = st.columns(2)
    with ac1:
        new_rec_type = st.selectbox("Type", ["expense", "income"], key="new_rec_type")
        new_rec_amount = st.number_input("Amount", min_value=0.01, step=1.0, key="new_rec_amount")
        new_rec_cat = st.selectbox("Category", CATEGORIES, key="new_rec_cat")
    with ac2:
        new_rec_desc = st.text_input("Description", key="new_rec_desc")
        new_rec_freq = st.selectbox("Frequency", ["monthly", "weekly", "biweekly"], key="new_rec_freq")
        new_rec_date = st.date_input("Next Due Date", value=date.today(), key="new_rec_date")
        new_rec_currency = st.selectbox(
            "Currency", currency_list,
            index=cur_index,
            format_func=lambda c: f"{c} ({SUPPORTED_CURRENCIES[c]})",
            key="new_rec_currency",
        )

    if st.button("Add Recurring Transaction", type="primary"):
        if new_rec_desc.strip() and new_rec_amount > 0:
            add_recurring_transaction(
                new_rec_type, new_rec_amount, new_rec_cat,
                new_rec_desc.strip(), new_rec_freq,
                new_rec_date.isoformat(), currency=new_rec_currency,
            )
            st.success("Recurring transaction added!")
            st.rerun()
        else:
            st.error("Please fill in description and amount.")

    st.markdown("---")

    # Re-seed historical data
    st.subheader("Add Historical Spending")
    st.caption("Describe past spending in plain English to seed your data.")
    history_text = st.text_area("Historical spending", key="settings_history", height=100)
    if st.button("Parse & Save Historical Data"):
        if history_text.strip():
            with st.spinner("Parsing..."):
                count = save_parsed_history(history_text)
            if count is None:
                st.error("Couldn't parse that. Try rephrasing.")
            else:
                st.success(f"Saved {count} historical transactions!")
                st.rerun()
