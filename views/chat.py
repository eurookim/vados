"""Log / Chat page: natural-language logging and Q&A."""
import anthropic
import streamlit as st

from ai import chat, parse_ai_response, validate_transaction
from database import (
    CATEGORIES,
    add_transaction,
    get_default_currency,
    get_last_transaction,
    resolve_category,
    update_transaction,
)


MAX_CHAT_DISPLAY = 50


def trim_conversation_history():
    """Keep only last 10 turns (5 user + 5 assistant)."""
    hist = st.session_state.conversation_history
    if len(hist) > 10:
        st.session_state.conversation_history = hist[-10:]
    msgs = st.session_state.chat_messages
    if len(msgs) > MAX_CHAT_DISPLAY:
        st.session_state.chat_messages = msgs[-MAX_CHAT_DISPLAY:]


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
                    _append_and_trim(user_input, response_text)
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
