"""First-run onboarding flow."""
import streamlit as st

from database import (
    EXPENSE_CATEGORIES,
    SUPPORTED_CURRENCIES,
    format_currency,
    get_budget_targets,
    get_default_currency,
    get_or_create_profile,
    set_budget_target,
    update_profile,
)
from views.common import save_parsed_history


def show_onboarding():
    profile = get_or_create_profile()
    step = st.session_state.onboarding_step

    st.markdown("""
    <div style="text-align:center; padding: 2rem 0 1rem 0;">
        <span style="font-size: 3rem;">💰</span>
        <h1 style="margin: 0.5rem 0 0.2rem 0; font-size: 2.4rem; background: linear-gradient(135deg, var(--accent), var(--accent-light));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;">
            Welcome to Vados
        </h1>
        <p style="color: var(--text-muted); font-size: 1rem;">Let's set up your personal finance assistant.</p>
    </div>
    """, unsafe_allow_html=True)
    st.progress((step + 1) / 4)

    if step == 0:
        st.subheader("Step 1: Your Financial Goals")
        st.markdown(
            '*What are you trying to do with your money? (e.g. save more, pay off debt, '
            'build an emergency fund, stop overspending on food)*'
        )
        goals = st.text_area("Your goals", key="onboarding_goals", height=100)
        if st.button("Next", key="goals_next"):
            update_profile(goals=goals)
            st.session_state.onboarding_step = 1
            st.rerun()

    elif step == 1:
        st.subheader("Step 2: Budget Targets (Optional)")
        st.markdown("Set monthly spending limits for each category. Leave blank to skip.")
        cur_symbol = SUPPORTED_CURRENCIES.get(get_default_currency(), "$")
        cols = st.columns(3)
        budgets = {}
        for i, cat in enumerate(EXPENSE_CATEGORIES):
            with cols[i % 3]:
                val = st.number_input(
                    f"{cat} ({cur_symbol})", min_value=0.0, value=0.0, step=10.0, key=f"budget_{cat}"
                )
                if val > 0:
                    budgets[cat] = val

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Skip", key="budget_skip"):
                st.session_state.onboarding_step = 2
                st.rerun()
        with col2:
            if st.button("Save & Next", key="budget_save"):
                for cat, limit in budgets.items():
                    set_budget_target(cat, limit)
                st.session_state.onboarding_step = 2
                st.rerun()

    elif step == 2:
        st.subheader("Step 3: Historical Spending (Optional)")
        st.markdown(
            'Tell us about last month\'s spending in plain English. For example:\n\n'
            '> *"Last month I spent about $200 on food, $800 on rent, $50 on transport, and made $1,800."*'
        )
        history_text = st.text_area("Your past spending", key="onboarding_history", height=100)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Skip", key="history_skip"):
                st.session_state.onboarding_step = 3
                st.rerun()
        with col2:
            if st.button("Parse & Save", key="history_save"):
                if history_text.strip():
                    with st.spinner("Parsing your spending history..."):
                        count = save_parsed_history(history_text)
                    if count is None:
                        st.error("Couldn't parse that. Try rephrasing or click Skip.")
                        return
                    st.success(f"Saved {count} historical transaction(s)!")
                st.session_state.onboarding_step = 3
                st.rerun()

    elif step == 3:
        st.subheader("You're all set!")
        profile = get_or_create_profile()
        targets = get_budget_targets()
        st.markdown("Here's what we have:")
        if profile.get("goals"):
            st.markdown(f"**Goals:** {profile['goals']}")
        if targets:
            cur = get_default_currency()
            st.markdown("**Budget targets:** " + ", ".join(f"{c}: {format_currency(v, cur)}" for c, v in targets.items()))
        else:
            st.markdown("**Budget targets:** None set (you can add them later in Settings)")

        if st.button("Enter Vados", key="enter_app", type="primary"):
            update_profile(onboarding_complete=1)
            welcome = "Welcome to Vados! "
            if profile.get("goals"):
                welcome += f"I see your goal is to {profile['goals'].lower().rstrip('.')}. "
            if targets:
                welcome += f"I'll keep an eye on your budgets for {', '.join(targets.keys())}. "
            welcome += "Type a transaction or ask me anything about your finances!"
            st.session_state.chat_messages.append({"role": "assistant", "content": welcome})
            st.rerun()
