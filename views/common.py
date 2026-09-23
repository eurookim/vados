"""Helpers shared by more than one page."""
from ai import parse_onboarding_history, validate_transaction
from database import add_transaction


def save_parsed_history(text):
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
