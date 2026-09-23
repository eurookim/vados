"""Transaction History page: browse, edit and delete transactions."""
import streamlit as st

from database import (
    CATEGORIES,
    delete_transaction,
    format_currency,
    get_all_transactions,
    update_transaction,
)


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
