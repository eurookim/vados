import streamlit as st

from database import get_or_create_profile, init_db, process_due_recurring_transactions
from views.chat import show_chat
from views.dashboard import show_dashboard
from views.history import show_history
from views.onboarding import show_onboarding
from views.settings import show_settings
from views.sidebar import show_sidebar
from views.theme import apply_theme
from views.trends import show_trends

st.set_page_config(page_title="Vados", page_icon="💰", layout="wide")

init_db()

# Process recurring transactions once per session
if "recurring_processed" not in st.session_state:
    _recurring_count = process_due_recurring_transactions()
    st.session_state.recurring_processed = True
    if _recurring_count > 0:
        st.toast(f"Auto-logged {_recurring_count} recurring transaction(s)")

apply_theme()

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

# Page name -> (sidebar icon, renderer), in sidebar order.
PAGES = {
    "Dashboard": ("📊", show_dashboard),
    "Trends": ("📈", show_trends),
    "Log / Chat": ("💬", show_chat),
    "Transaction History": ("📋", show_history),
    "Settings": ("⚙️", show_settings),
}


def main():
    profile = get_or_create_profile()

    if not profile.get("onboarding_complete"):
        show_onboarding()
        return

    show_sidebar({name: icon for name, (icon, _) in PAGES.items()})

    page = PAGES.get(st.session_state.page)
    if page:
        page[1]()


if __name__ == "__main__":
    main()
