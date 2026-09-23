import html

import anthropic
import plotly.graph_objects as go
import plotly.express as px
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
    get_monthly_summaries,
    get_budget_targets,
    set_budget_target,
    remove_budget_target,
    get_last_transaction,
    get_default_currency,
    set_default_currency,
    format_currency,
    get_recurring_transactions,
    add_recurring_transaction,
    update_recurring_transaction,
    delete_recurring_transaction,
    process_due_recurring_transactions,
    get_upcoming_recurring,
    CATEGORIES,
    EXPENSE_CATEGORIES,
    SUPPORTED_CURRENCIES,
    resolve_category,
)
from ai import chat, parse_ai_response, validate_transaction, generate_insight, parse_onboarding_history

st.set_page_config(page_title="Vados", page_icon="💰", layout="wide")

init_db()

# Process recurring transactions once per session
if "recurring_processed" not in st.session_state:
    _recurring_count = process_due_recurring_transactions()
    st.session_state.recurring_processed = True
    if _recurring_count > 0:
        st.toast(f"Auto-logged {_recurring_count} recurring transaction(s)")

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


def _save_parsed_history(text):
    """Parse free-text spending history and save the valid transactions.
    Returns the number saved, or None if the text couldn't be parsed."""
    result = parse_onboarding_history(text)
    if not result or "transactions" not in result:
        return None
    count = 0
    for txn in result["transactions"]:
        valid, _ = validate_transaction(txn)
        if valid:
            add_transaction(
                txn["date"], txn["type"], txn["amount"],
                txn["category"], txn["description"],
                source="onboarding", currency=txn["currency"],
            )
            count += 1
    return count


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
                        count = _save_parsed_history(history_text)
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
            "Trends": "📈",
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
    cur = get_default_currency()

    # Summary cards
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", format_currency(summary['total_income'], cur))
    c2.metric("Total Spent", format_currency(summary['total_expenses'], cur))
    net = summary["net_balance"]
    net_color = "#34D399" if net >= 0 else "#F87171"
    net_display = format_currency(net, cur)
    c3.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E2235, #252A40); border: 1px solid #2D3350;
        border-radius: 16px; padding: 20px 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <p style="color: #9BA1B8; font-size: 0.85rem; font-weight: 500; text-transform: uppercase;
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

    # Upcoming recurring transactions
    upcoming = get_upcoming_recurring(30)
    if upcoming:
        st.markdown("---")
        st.subheader("Upcoming Recurring")
        for rec in upcoming:
            rec_cur = rec.get("currency", cur)
            freq_label = rec["frequency"].capitalize()
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1E2235, #252A40); border: 1px solid #2D3350;
                border-radius: 12px; padding: 14px 18px; margin-bottom: 8px;
                display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #E8EAF0; font-weight: 600;">{html.escape(rec['description'])}</span>
                    <span style="color: #6B7094; font-size: 0.85rem; margin-left: 8px;">{freq_label} &middot; {rec['category']}</span>
                </div>
                <div>
                    <span style="color: #A78BFA; font-weight: 700;">{format_currency(rec['amount'], rec_cur)}</span>
                    <span style="color: #6B7094; font-size: 0.8rem; margin-left: 8px;">Due {rec['next_due_date']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)


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
                            txn["category"], txn["description"],
                            currency=txn.get("currency", get_default_currency()),
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
        txn_cur = txn.get("currency", "USD")
        amount_str = f":{color}[{sign}{format_currency(txn['amount'], txn_cur)}]"

        with st.expander(
            f"{txn['date']} | {txn['description']} | {amount_str} | `{txn['category']}` | {txn_cur}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                new_cat = st.selectbox(
                    "Category",
                    CATEGORIES,
                    index=CATEGORIES.index(txn["category"]) if txn["category"] in CATEGORIES else 0,
                    key=f"cat_{txn['id']}",
                )
                new_desc = st.text_input(
                    "Description", value=txn["description"], key=f"desc_{txn['id']}"
                )
            with col2:
                new_amount = st.number_input(
                    "Amount", min_value=0.01, value=float(txn["amount"]),
                    step=0.01, key=f"amt_{txn['id']}"
                )
                st.markdown(f"**Source:** {txn['source']}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save Changes", key=f"save_{txn['id']}"):
                    update_transaction(txn["id"], category=new_cat, description=new_desc, amount=new_amount)
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
            status_color = "#34D399" if rec.get("active") else "#6B7094"
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
                count = _save_parsed_history(history_text)
            if count is None:
                st.error("Couldn't parse that. Try rephrasing.")
            else:
                st.success(f"Saved {count} historical transactions!")
                st.rerun()


# ============================================================
# TRENDS
# ============================================================

CATEGORY_COLORS = {
    "Food": "#FF6B6B", "Transport": "#4ECDC4", "Entertainment": "#45B7D1",
    "Shopping": "#FFA07A", "Subscriptions": "#DDA0DD", "Health": "#98D8C8",
    "Housing": "#F7DC6F", "Education": "#BB8FCE", "Personal": "#85C1E9",
    "Income": "#34D399",
}


def _style_chart(fig, **overrides):
    """Apply consistent dark theme styling to a Plotly figure."""
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C4C9E0", family="Inter", size=13),
        xaxis=dict(
            gridcolor="rgba(45,51,80,0.5)", showgrid=False,
            tickfont=dict(color="#9BA1B8", size=12),
            linecolor="#2D3350", zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(45,51,80,0.4)", showgrid=True, griddash="dot",
            tickfont=dict(color="#9BA1B8", size=12),
            linecolor="#2D3350", zeroline=False,
        ),
        margin=dict(l=50, r=30, t=50, b=50),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color="#9BA1B8", size=12),
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        ),
        hoverlabel=dict(
            bgcolor="#1E2235", bordercolor="#7C5CFC",
            font=dict(color="#E8EAF0", family="Inter", size=13),
        ),
        bargap=0.3,
    )
    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


def show_trends():
    st.title("Spending Trends")
    cur = get_default_currency()
    symbol = SUPPORTED_CURRENCIES.get(cur, "$")

    summaries = get_monthly_summaries(6)
    targets = get_budget_targets()

    month_labels = [date(s["year"], s["month"], 1).strftime("%b %Y") for s in summaries]
    expenses = [s["total_expenses"] for s in summaries]
    incomes = [s["total_income"] for s in summaries]

    # --- Chart 1: Income vs Expenses ---
    st.subheader("Income vs Expenses")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=month_labels, y=incomes, name="Income",
        line=dict(color="#34D399", width=3, shape="spline"),
        mode="lines+markers",
        marker=dict(size=9, color="#34D399", line=dict(width=2, color="#1A3328")),
        fill="tozeroy",
        fillcolor="rgba(52,211,153,0.08)",
        hovertemplate="%{x}<br>Income: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        x=month_labels, y=expenses, name="Expenses",
        line=dict(color="#F87171", width=3, shape="spline"),
        mode="lines+markers",
        marker=dict(size=9, color="#F87171", line=dict(width=2, color="#331A1A")),
        fill="tozeroy",
        fillcolor="rgba(248,113,113,0.08)",
        hovertemplate="%{x}<br>Expenses: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    _style_chart(fig2, yaxis_title=f"Amount ({cur})", height=380)
    st.plotly_chart(fig2, use_container_width=True)

    # --- Chart 3: Net Savings ---
    st.subheader("Net Savings")
    net_vals = [i - e for i, e in zip(incomes, expenses)]
    bar_colors = ["#34D399" if n >= 0 else "#F87171" for n in net_vals]
    fig3 = go.Figure(go.Bar(
        x=month_labels, y=net_vals,
        marker=dict(color=bar_colors, cornerradius=6, line=dict(width=0)),
        text=[f"{symbol}{abs(n):,.0f}" for n in net_vals],
        textposition="outside",
        textfont=dict(color="#9BA1B8", size=12, family="Inter"),
        hovertemplate="%{x}<br>Net: " + symbol + "%{y:,.0f}<extra></extra>",
    ))
    # Add zero line
    fig3.add_hline(y=0, line_dash="dot", line_color="#6B7094", line_width=1)
    _style_chart(fig3, yaxis_title=f"Net ({cur})", height=340)
    st.plotly_chart(fig3, use_container_width=True)

    # --- Chart 4: Budget vs Actual ---
    if targets:
        st.subheader("Budget vs Actual")
        current = summaries[-1]["by_category"]
        budget_cats = [c for c in targets if c in current or targets[c] > 0]
        if budget_cats:
            actual_vals = [current.get(c, 0) for c in budget_cats]
            budget_vals = [targets[c] for c in budget_cats]
            pct_vals = [a / b * 100 if b > 0 else 0 for a, b in zip(actual_vals, budget_vals)]
            bar_colors_budget = [
                "#F87171" if p >= 100 else "#FBBF24" if p >= 80 else "#34D399"
                for p in pct_vals
            ]
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(
                x=budget_cats, y=budget_vals, name="Budget",
                marker=dict(color="rgba(45,51,80,0.6)", cornerradius=6, line=dict(width=1, color="#3B4580")),
                hovertemplate="%{x}<br>Budget: " + symbol + "%{y:,.0f}<extra></extra>",
            ))
            fig4.add_trace(go.Bar(
                x=budget_cats, y=actual_vals, name="Actual",
                marker=dict(color=bar_colors_budget, cornerradius=6, line=dict(width=0)),
                text=[f"{p:.0f}%" for p in pct_vals],
                textposition="outside",
                textfont=dict(color="#9BA1B8", size=12, family="Inter"),
                hovertemplate="%{x}<br>Spent: " + symbol + "%{y:,.0f} (%{text})<extra></extra>",
            ))
            _style_chart(fig4, barmode="group", yaxis_title=f"Amount ({cur})", height=380, bargap=0.25)
            st.plotly_chart(fig4, use_container_width=True)


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
    elif page == "Trends":
        show_trends()
    elif page == "Log / Chat":
        show_chat()
    elif page == "Transaction History":
        show_history()
    elif page == "Settings":
        show_settings()


if __name__ == "__main__":
    main()
