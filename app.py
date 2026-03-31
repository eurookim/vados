import html

import anthropic
import streamlit as st
from datetime import date, datetime

from database import (
    init_db,
    get_or_create_profile,
    update_profile,
    add_transaction,
    update_transaction,
    delete_transaction,
    get_all_transactions,
    get_monthly_summary,
    get_budget_targets,
    set_budget_target,
    remove_budget_target,
    get_last_transaction,
    CATEGORIES,
    EXPENSE_CATEGORIES,
    resolve_category,
)
from ai import chat, parse_ai_response, validate_transaction, generate_insight, parse_onboarding_history

st.set_page_config(page_title="Vados", page_icon="💰", layout="wide")

init_db()

# --- Custom Dark Theme CSS ---
st.markdown("""
<style>
/* ---- Global ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ---- Main container ---- */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1100px;
}

/* ---- Rounded cards for metrics ---- */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1E2235 0%, #252A40 100%);
    border: 1px solid #2D3350;
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

[data-testid="stMetricLabel"] {
    color: #9BA1B8 !important;
    font-size: 0.85rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

[data-testid="stMetricValue"] {
    color: #E8EAF0 !important;
    font-size: 1.8rem;
    font-weight: 700;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #13152A 0%, #1A1D34 100%);
    border-right: 1px solid #2D3350;
}

[data-testid="stSidebar"] .stTitle {
    color: #7C5CFC !important;
    font-weight: 700;
    letter-spacing: 0.02em;
}

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 12px !important;
    padding: 0.55rem 1.4rem !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    border: 1px solid #2D3350 !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(124, 92, 252, 0.3) !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7C5CFC 0%, #6B4CE0 100%) !important;
    color: white !important;
    border: none !important;
}

.stButton > button[kind="secondary"] {
    background: #1E2235 !important;
    color: #B0B7D1 !important;
}

/* ---- Inputs ---- */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 12px !important;
    border: 1px solid #2D3350 !important;
    background-color: #1A1D29 !important;
    color: #E8EAF0 !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus {
    border-color: #7C5CFC !important;
    box-shadow: 0 0 0 2px rgba(124, 92, 252, 0.2) !important;
}

/* ---- Chat ---- */
[data-testid="stChatMessage"] {
    border-radius: 16px !important;
    padding: 16px 20px !important;
    margin-bottom: 12px !important;
    border: 1px solid #2D3350;
}

[data-testid="stChatInput"] > div {
    border-radius: 16px !important;
    border: 1px solid #2D3350 !important;
    background-color: #1A1D29 !important;
}

[data-testid="stChatInput"] textarea {
    color: #E8EAF0 !important;
}

/* ---- Expanders (transaction history) ---- */
[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid #2D3350 !important;
    background-color: #1A1D29 !important;
    margin-bottom: 8px;
    overflow: hidden;
}

[data-testid="stExpander"] summary {
    border-radius: 14px !important;
    padding: 12px 16px !important;
}

/* ---- Progress bars ---- */
.stProgress > div > div {
    border-radius: 10px !important;
    height: 12px !important;
}

.stProgress > div > div > div {
    border-radius: 10px !important;
    background: linear-gradient(90deg, #7C5CFC 0%, #A78BFA 100%) !important;
}

/* ---- Alerts / Info / Warning / Error ---- */
[data-testid="stAlert"] {
    border-radius: 14px !important;
    border: 1px solid #2D3350 !important;
}

.stInfo, [data-baseweb="notification"][kind="info"] {
    background-color: #1A2340 !important;
    border-left: 4px solid #7C5CFC !important;
    border-radius: 14px !important;
}

.stSuccess {
    background-color: #1A3328 !important;
    border-left: 4px solid #34D399 !important;
    border-radius: 14px !important;
}

.stWarning {
    background-color: #332A1A !important;
    border-left: 4px solid #FBBF24 !important;
    border-radius: 14px !important;
}

.stError {
    background-color: #331A1A !important;
    border-left: 4px solid #F87171 !important;
    border-radius: 14px !important;
}

/* ---- Dividers ---- */
hr {
    border-color: #2D3350 !important;
    opacity: 0.5;
}

/* ---- Headings ---- */
h1 {
    color: #E8EAF0 !important;
    font-weight: 700 !important;
}

h2, h3 {
    color: #C4C9E0 !important;
    font-weight: 600 !important;
}

/* ---- Scrollbar ---- */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

::-webkit-scrollbar-track {
    background: #0E1117;
}

::-webkit-scrollbar-thumb {
    background: #2D3350;
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: #7C5CFC;
}

/* ---- Number input buttons ---- */
.stNumberInput button {
    border-radius: 8px !important;
}

/* ---- Selectbox dropdown ---- */
[data-baseweb="select"] {
    border-radius: 12px !important;
}

[data-baseweb="popover"] {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# --- Session state defaults ---
defaults = {
    "conversation_history": [],
    "chat_messages": [],
    "pending_transaction": None,
    "onboarding_step": 0,
    "page": "Dashboard",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


MAX_CHAT_DISPLAY = 50

def trim_conversation_history():
    """Keep only last 10 turns (5 user + 5 assistant)."""
    hist = st.session_state.conversation_history
    if len(hist) > 10:
        st.session_state.conversation_history = hist[-10:]
    msgs = st.session_state.chat_messages
    if len(msgs) > MAX_CHAT_DISPLAY:
        st.session_state.chat_messages = msgs[-MAX_CHAT_DISPLAY:]


# ============================================================
# ONBOARDING
# ============================================================
def show_onboarding():
    profile = get_or_create_profile()
    step = st.session_state.onboarding_step

    st.markdown("""
    <div style="text-align:center; padding: 2rem 0 1rem 0;">
        <span style="font-size: 3rem;">💰</span>
        <h1 style="margin: 0.5rem 0 0.2rem 0; font-size: 2.4rem; background: linear-gradient(135deg, #7C5CFC, #A78BFA);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;">
            Welcome to Vados
        </h1>
        <p style="color: #6B7094; font-size: 1rem;">Let's set up your personal finance assistant.</p>
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
        cols = st.columns(3)
        budgets = {}
        for i, cat in enumerate(EXPENSE_CATEGORIES):
            with cols[i % 3]:
                val = st.number_input(
                    f"{cat} ($)", min_value=0.0, value=0.0, step=10.0, key=f"budget_{cat}"
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
                        result = parse_onboarding_history(history_text)
                    if result and "transactions" in result:
                        count = 0
                        for txn in result["transactions"]:
                            valid, err = validate_transaction(txn)
                            if valid:
                                add_transaction(
                                    txn["date"], txn["type"], txn["amount"],
                                    txn["category"], txn["description"], source="onboarding"
                                )
                                count += 1
                        st.success(f"Saved {count} historical transaction(s)!")
                    else:
                        st.error("Couldn't parse that. Try rephrasing or click Skip.")
                        return
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
            st.markdown("**Budget targets:** " + ", ".join(f"{c}: ${v:.0f}" for c, v in targets.items()))
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


# ============================================================
# SIDEBAR
# ============================================================
def show_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 1.5rem 0 1rem 0;">
            <span style="font-size: 2.2rem;">💰</span>
            <h1 style="margin:0; font-size:1.8rem; background: linear-gradient(135deg, #7C5CFC, #A78BFA);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight:800;">
                Vados
            </h1>
            <p style="color:#6B7094; font-size:0.8rem; margin-top:4px;">AI Finance Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        nav_icons = {
            "Dashboard": "📊",
            "Log / Chat": "💬",
            "Transaction History": "📋",
            "Settings": "⚙️",
        }
        for p in nav_icons:
            label = f"{nav_icons[p]}  {p}"
            if st.button(label, key=f"nav_{p}", use_container_width=True,
                         type="primary" if st.session_state.page == p else "secondary"):
                st.session_state.page = p
                st.rerun()


# ============================================================
# DASHBOARD
# ============================================================
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

    # Summary cards
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", f"${summary['total_income']:,.2f}")
    c2.metric("Total Spent", f"${summary['total_expenses']:,.2f}")
    net = summary["net_balance"]
    net_color = "#34D399" if net >= 0 else "#F87171"
    c3.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E2235, #252A40); border: 1px solid #2D3350;
        border-radius: 16px; padding: 20px 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <p style="color: #9BA1B8; font-size: 0.85rem; font-weight: 500; text-transform: uppercase;
            letter-spacing: 0.05em; margin: 0;">Net Balance</p>
        <p style="color: {net_color}; font-size: 1.8rem; font-weight: 700; margin: 0;">
            ${net:,.2f}</p>
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
                    color = "red" if pct >= 1.0 else ("orange" if pct >= 0.8 else "green")
                    bar_label = f"{cat}: ${spent:.2f} / ${limit:.2f} ({pct*100:.0f}%)"
                    st.progress(min(pct, 1.0), text=bar_label)
                    if pct >= 0.8 and pct < 1.0:
                        with col2:
                            st.warning("Near limit")
                    elif pct >= 1.0:
                        with col2:
                            st.error("Over budget!")
                else:
                    pct_of_max = spent / max_val if max_val > 0 else 0
                    st.progress(min(pct_of_max, 1.0), text=f"{cat}: ${spent:.2f}")
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

    # Check if we should generate a weekly insight
    force = st.session_state.pop("force_insight", False)
    should_generate = False
    if summary["total_income"] > 0 or summary["total_expenses"] > 0:
        if force:
            should_generate = True
        else:
            last_insight = profile.get("last_insight_at")
            if last_insight is None:
                should_generate = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last_insight)
                    if (datetime.now() - last_dt).days >= 7:
                        should_generate = True
                except (ValueError, TypeError):
                    should_generate = True

    if should_generate:
        with st.spinner("Generating insight..."):
            try:
                insight = generate_insight()
                st.session_state["last_insight"] = insight
                update_profile(last_insight_at=datetime.now().isoformat())
            except Exception as e:
                insight = "Couldn't generate an insight right now."
                st.session_state["last_insight"] = insight
    else:
        insight = st.session_state.get("last_insight", None)
        if insight is None and (summary["total_income"] > 0 or summary["total_expenses"] > 0):
            with st.spinner("Generating insight..."):
                try:
                    insight = generate_insight()
                    st.session_state["last_insight"] = insight
                except Exception:
                    insight = "Couldn't generate an insight right now."
                    st.session_state["last_insight"] = insight

    if insight:
        safe_insight = html.escape(insight)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1A2340, #1E2850); border: 1px solid #3B4580;
            border-left: 4px solid #7C5CFC; border-radius: 14px; padding: 20px 24px;
            box-shadow: 0 4px 20px rgba(124, 92, 252, 0.1);">
            <p style="color: #9BA1B8; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.08em; margin: 0 0 8px 0;">🧠 AI Insight</p>
            <p style="color: #E8EAF0; font-size: 1rem; line-height: 1.5; margin: 0;">{safe_insight}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Start logging transactions to get AI-powered insights!")


# ============================================================
# LOG / CHAT
# ============================================================
def show_chat():
    st.title("Log / Chat")
    st.caption("Type a transaction to log it, or ask a question about your finances.")

    # Empty state with example prompts
    if not st.session_state.chat_messages:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 1rem; color: #6B7094;">
            <p style="font-size: 2rem; margin-bottom: 0.5rem;">💬</p>
            <p style="font-size: 1.1rem; color: #9BA1B8; margin-bottom: 1.5rem;">
                Start by logging a transaction or asking a question
            </p>
        </div>
        """, unsafe_allow_html=True)
        examples = [
            "Spent $12 on lunch today",
            "Got paid $2,000 from work",
            "How much have I spent on food this month?",
            "Am I on track with my budget?",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(f'"{ex}"', key=f"example_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": ex})
                    st.session_state["_run_example"] = ex
                    st.rerun()

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("e.g. 'Spent $45 on groceries' or 'How much have I spent on food?'")

    # Handle example button clicks
    if "_run_example" in st.session_state:
        user_input = st.session_state.pop("_run_example")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response_text = chat(
                        user_input,
                        st.session_state.conversation_history,
                        st.session_state.pending_transaction,
                    )
                except anthropic.AuthenticationError:
                    response_text = "API key is invalid. Check your .env file."
                    st.markdown(response_text)
                except anthropic.RateLimitError:
                    response_text = "Rate limited by the API. Wait a moment and try again."
                    st.markdown(response_text)
                except Exception as e:
                    response_text = f"I couldn't process that — {type(e).__name__}. Try again."
                    st.markdown(response_text)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": response_text}
                    )
                    st.session_state.conversation_history.append(
                        {"role": "user", "content": user_input}
                    )
                    st.session_state.conversation_history.append(
                        {"role": "assistant", "content": response_text}
                    )
                    trim_conversation_history()
                    st.rerun()
                    return

            parsed = parse_ai_response(response_text)

            if parsed and parsed.get("intent") == "confirmed" and st.session_state.pending_transaction:
                # User confirmed pending transaction(s)
                pending = st.session_state.pending_transaction
                txns = pending if isinstance(pending, list) else [pending]
                saved = 0
                for txn in txns:
                    valid, err = validate_transaction(txn)
                    if valid:
                        add_transaction(
                            txn["date"], txn["type"], txn["amount"],
                            txn["category"], txn["description"]
                        )
                        saved += 1
                st.session_state.pending_transaction = None
                confirm_msg = f"Saved {saved} transaction(s)!"
                st.markdown(confirm_msg)
                _append_and_trim(user_input, confirm_msg)
                st.rerun()

            elif parsed and parsed.get("intent") == "cancelled":
                # User rejected/cancelled pending transaction
                st.session_state.pending_transaction = None
                cancel_msg = parsed.get("confirmation_message", "Transaction cancelled.")
                st.markdown(cancel_msg)
                _append_and_trim(user_input, cancel_msg)
                st.rerun()

            elif parsed and parsed.get("intent") == "transaction":
                # Clear any stale pending transaction before setting new one
                st.session_state.pending_transaction = None

                txns = parsed.get("transactions", [])
                confirm_msg = parsed.get("confirmation_message", "Please confirm this transaction.")

                valid_txns = []
                for txn in txns:
                    valid, err = validate_transaction(txn)
                    if valid:
                        valid_txns.append(txn)
                    else:
                        cat = resolve_category(txn.get("category", ""))
                        if cat is None:
                            confirm_msg = (
                                f"I wasn't sure how to categorize that. Which category fits best? "
                                f"Options: {', '.join(CATEGORIES)}"
                            )
                            valid_txns = []
                            break
                        txn["category"] = cat
                        valid_txns.append(txn)

                if valid_txns:
                    st.session_state.pending_transaction = valid_txns

                st.markdown(confirm_msg)
                _append_and_trim(user_input, confirm_msg)
                st.rerun()

            elif parsed and parsed.get("intent") == "correction":
                # Correction of last transaction
                last_txn = get_last_transaction()
                if last_txn:
                    new_cat = parsed.get("category")
                    new_desc = parsed.get("description")
                    if new_cat:
                        resolved = resolve_category(new_cat)
                        if resolved is None:
                            confirm_msg = (
                                f"Unknown category '{new_cat}'. "
                                f"Options: {', '.join(CATEGORIES)}"
                            )
                        else:
                            update_transaction(last_txn["id"], category=resolved, description=new_desc)
                            confirm_msg = parsed.get("confirmation_message", "Updated!")
                    else:
                        if new_desc:
                            update_transaction(last_txn["id"], description=new_desc)
                        confirm_msg = parsed.get("confirmation_message", "Updated!")
                else:
                    confirm_msg = "No recent transaction found to update."

                st.markdown(confirm_msg)
                _append_and_trim(user_input, confirm_msg)
                st.rerun()

            else:
                # Plain Q&A response — also clear pending if user changed topic
                if st.session_state.pending_transaction:
                    st.session_state.pending_transaction = None
                st.markdown(response_text)
                _append_and_trim(user_input, response_text)
                st.rerun()


def _append_and_trim(user_input, assistant_msg):
    """Helper to append to both histories and trim."""
    st.session_state.chat_messages.append(
        {"role": "assistant", "content": assistant_msg}
    )
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_input}
    )
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": assistant_msg}
    )
    trim_conversation_history()


# ============================================================
# TRANSACTION HISTORY
# ============================================================
def show_history():
    st.title("Transaction History")

    txns = get_all_transactions()
    if not txns:
        st.info("No transactions yet. Go to Log / Chat to start!")
        return

    for txn in txns:
        color = "green" if txn["type"] == "income" else "red"
        sign = "+" if txn["type"] == "income" else "-"
        amount_str = f":{color}[{sign}${txn['amount']:.2f}]"

        with st.expander(
            f"{txn['date']} | {txn['description']} | {amount_str} | `{txn['category']}`"
        ):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                new_cat = st.selectbox(
                    "Category",
                    CATEGORIES,
                    index=CATEGORIES.index(txn["category"]) if txn["category"] in CATEGORIES else 0,
                    key=f"cat_{txn['id']}",
                )
            with col2:
                new_desc = st.text_input(
                    "Description", value=txn["description"], key=f"desc_{txn['id']}"
                )
            with col3:
                st.markdown(f"**Source:** {txn['source']}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save Changes", key=f"save_{txn['id']}"):
                    update_transaction(txn["id"], category=new_cat, description=new_desc)
                    st.success("Updated!")
                    st.rerun()
            with c2:
                confirm_key = f"confirm_del_{txn['id']}"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False

                if not st.session_state[confirm_key]:
                    if st.button("Delete", key=f"del_{txn['id']}", type="secondary"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("Are you sure?")
                    yes_col, no_col = st.columns(2)
                    with yes_col:
                        if st.button("Yes, delete", key=f"yes_del_{txn['id']}", type="primary"):
                            delete_transaction(txn["id"])
                            st.session_state[confirm_key] = False
                            st.rerun()
                    with no_col:
                        if st.button("Cancel", key=f"no_del_{txn['id']}"):
                            st.session_state[confirm_key] = False
                            st.rerun()


# ============================================================
# SETTINGS
# ============================================================
def show_settings():
    st.title("Settings")

    profile = get_or_create_profile()
    targets = get_budget_targets()

    # Goals
    st.subheader("Financial Goals")
    goals = st.text_area("Your goals", value=profile.get("goals", ""), key="settings_goals")
    if st.button("Update Goals"):
        update_profile(goals=goals)
        st.success("Goals updated!")
        st.rerun()

    st.markdown("---")

    # Budget targets
    st.subheader("Budget Targets")
    st.caption("Set monthly spending limits per category. Set to 0 to remove.")
    cols = st.columns(3)
    new_targets = {}
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        with cols[i % 3]:
            current = targets.get(cat, 0.0)
            val = st.number_input(
                f"{cat} ($)", min_value=0.0, value=current, step=10.0,
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

    # Re-seed historical data
    st.subheader("Add Historical Spending")
    st.caption("Describe past spending in plain English to seed your data.")
    history_text = st.text_area("Historical spending", key="settings_history", height=100)
    if st.button("Parse & Save Historical Data"):
        if history_text.strip():
            with st.spinner("Parsing..."):
                result = parse_onboarding_history(history_text)
            if result and "transactions" in result:
                count = 0
                for txn in result["transactions"]:
                    valid, err = validate_transaction(txn)
                    if valid:
                        add_transaction(
                            txn["date"], txn["type"], txn["amount"],
                            txn["category"], txn["description"], source="onboarding"
                        )
                        count += 1
                st.success(f"Saved {count} historical transactions!")
                st.rerun()
            else:
                st.error("Couldn't parse that. Try rephrasing.")


# ============================================================
# MAIN
# ============================================================
def main():
    profile = get_or_create_profile()

    if not profile.get("onboarding_complete"):
        show_onboarding()
        return

    show_sidebar()

    page = st.session_state.page
    if page == "Dashboard":
        show_dashboard()
    elif page == "Log / Chat":
        show_chat()
    elif page == "Transaction History":
        show_history()
    elif page == "Settings":
        show_settings()


if __name__ == "__main__":
    main()
