import json

from views.common import save_parsed_history


def _reply(*transactions):
    return "```json\n" + json.dumps({"transactions": list(transactions)}) + "\n```"


def _txn(**overrides):
    txn = {"type": "expense", "amount": 50, "category": "Food",
           "description": "groceries", "date": "2026-08-01"}
    txn.update(overrides)
    return txn


def test_no_currency_from_model_uses_default(db, fake_ai):
    db.set_default_currency("KRW")
    fake_ai.text = _reply(_txn())
    assert save_parsed_history("I spent 50 on groceries") == 1
    (saved,) = db.get_all_transactions()
    assert (saved["currency"], saved["source"]) == ("KRW", "onboarding")


def test_currency_from_model_is_kept(db, fake_ai):
    fake_ai.text = _reply(_txn(currency="EUR"))
    save_parsed_history("I spent 50 euros on groceries")
    assert db.get_all_transactions()[0]["currency"] == "EUR"


def test_invalid_transactions_are_skipped(db, fake_ai):
    fake_ai.text = _reply(_txn(), _txn(category="Crypto"), _txn(amount=0))
    assert save_parsed_history("...") == 1
    assert len(db.get_all_transactions()) == 1


def test_unparseable_reply_returns_none(db, fake_ai):
    fake_ai.text = "Sorry, I couldn't find any transactions in that."
    assert save_parsed_history("hello") is None
    assert db.get_all_transactions() == []


def test_prompt_asks_the_model_for_a_currency(db, fake_ai):
    fake_ai.text = _reply()
    save_parsed_history("Last month I spent 50 euros on food")
    system = fake_ai.requests[-1]["system"]
    assert '"currency"' in system
    assert "EUR" in system
