from datetime import date

import ai


class TestParseAiResponse:
    def test_fenced_json(self):
        text = 'Sure!\n```json\n{"intent": "confirmed"}\n```'
        assert ai.parse_ai_response(text) == {"intent": "confirmed"}

    def test_bare_json(self):
        assert ai.parse_ai_response('  {"intent": "cancelled"} ') == {"intent": "cancelled"}

    def test_json_embedded_in_prose(self):
        assert ai.parse_ai_response('ok {"intent": "cancelled"} done') == {"intent": "cancelled"}

    def test_plain_text_is_none(self):
        assert ai.parse_ai_response("You spent $40 on food this month.") is None


class TestIsValidDate:
    def test_valid(self):
        assert ai.is_valid_date("2026-02-28")

    def test_wrong_format(self):
        assert not ai.is_valid_date("02/28/2026")

    def test_impossible_day(self):
        assert not ai.is_valid_date("2026-02-30")


def _txn(**overrides):
    txn = {
        "type": "expense", "amount": 12.0, "category": "Food",
        "description": "lunch", "date": "2026-03-01", "currency": "EUR",
    }
    txn.update(overrides)
    return txn


class TestValidateTransaction:
    def test_valid_passes_unchanged(self, db):
        txn = _txn()
        assert ai.validate_transaction(txn) == (True, None)
        assert txn == _txn()

    def test_resolves_category_synonym(self, db):
        txn = _txn(category="groceries")
        assert ai.validate_transaction(txn)[0]
        assert txn["category"] == "Food"

    def test_rejects_bad_type(self, db):
        assert ai.validate_transaction(_txn(type="transfer"))[0] is False

    def test_rejects_non_positive_or_non_numeric_amount(self, db):
        assert ai.validate_transaction(_txn(amount=0))[0] is False
        assert ai.validate_transaction(_txn(amount="12"))[0] is False

    def test_rejects_unknown_category(self, db):
        assert ai.validate_transaction(_txn(category="Crypto")) == (False, "Unknown category: Crypto")

    def test_rejects_missing_description(self, db):
        assert ai.validate_transaction(_txn(description=""))[0] is False

    def test_missing_or_invalid_date_defaults_to_today(self, db):
        for bad in (None, "", "yesterday", "2026-13-01"):
            txn = _txn(date=bad)
            assert ai.validate_transaction(txn)[0]
            assert txn["date"] == date.today().isoformat()

    def test_missing_or_unsupported_currency_uses_default(self, db):
        db.set_default_currency("KRW")
        for bad in (None, "", "XYZ"):
            txn = _txn(currency=bad)
            assert ai.validate_transaction(txn)[0]
            assert txn["currency"] == "KRW"
