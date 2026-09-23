from datetime import date, timedelta

import pytest

import database


class TestResolveCategory:
    def test_exact_match(self):
        assert database.resolve_category("Food") == "Food"

    def test_case_and_whitespace_insensitive(self):
        assert database.resolve_category("  sHoPpInG ") == "Shopping"

    def test_synonym(self):
        assert database.resolve_category("Groceries") == "Food"
        assert database.resolve_category("uber") == "Transport"

    def test_unknown_is_none(self):
        assert database.resolve_category("Crypto") is None

    def test_empty_is_none(self):
        assert database.resolve_category("") is None
        assert database.resolve_category(None) is None


class TestFormatCurrency:
    def test_usd_two_decimals(self):
        assert database.format_currency(1234.5, "USD") == "$1,234.50"

    def test_yen_and_won_have_no_decimals(self):
        assert database.format_currency(5000, "JPY") == "¥5,000"
        assert database.format_currency(12345.6, "KRW") == "₩12,346"

    def test_unknown_currency_uses_code_prefix(self):
        assert database.format_currency(10, "CHF") == "CHF 10.00"


class TestAdvanceDate:
    def test_weekly(self):
        assert database._advance_date("2026-03-01", "weekly") == "2026-03-08"

    def test_biweekly(self):
        assert database._advance_date("2026-03-01", "biweekly") == "2026-03-15"

    def test_monthly(self):
        assert database._advance_date("2026-03-15", "monthly") == "2026-04-15"

    def test_monthly_clamps_to_short_month(self):
        assert database._advance_date("2026-03-31", "monthly") == "2026-04-30"

    def test_monthly_clamps_to_february(self):
        assert database._advance_date("2026-01-31", "monthly") == "2026-02-28"

    def test_monthly_leap_year(self):
        assert database._advance_date("2024-01-31", "monthly") == "2024-02-29"

    def test_century_is_not_a_leap_year(self):
        assert database._advance_date("2100-01-31", "monthly") == "2100-02-28"

    def test_monthly_rolls_over_year(self):
        assert database._advance_date("2026-12-10", "monthly") == "2027-01-10"


class TestTransactions:
    def test_add_stores_resolved_category_and_positive_amount(self, db):
        db.add_transaction("2026-03-01", "expense", -12.5, "groceries", "lunch", currency="EUR")
        (txn,) = db.get_all_transactions()
        assert txn["category"] == "Food"
        assert txn["amount"] == 12.5
        assert txn["currency"] == "EUR"
        assert txn["source"] == "manual"

    def test_add_rejects_unknown_category(self, db):
        with pytest.raises(ValueError):
            db.add_transaction("2026-03-01", "expense", 5, "Crypto", "coin")
        assert db.get_all_transactions() == []

    def test_update_fields(self, db):
        db.add_transaction("2026-03-01", "expense", 10, "Food", "lunch")
        txn_id = db.get_last_transaction()["id"]
        db.update_transaction(txn_id, category="gym", description="class", amount=-30)
        txn = db.get_last_transaction()
        assert (txn["category"], txn["description"], txn["amount"]) == ("Health", "class", 30)

    def test_update_rejects_unknown_category(self, db):
        db.add_transaction("2026-03-01", "expense", 10, "Food", "lunch")
        txn_id = db.get_last_transaction()["id"]
        with pytest.raises(ValueError):
            db.update_transaction(txn_id, category="Crypto")
        assert db.get_last_transaction()["category"] == "Food"

    def test_delete(self, db):
        db.add_transaction("2026-03-01", "expense", 10, "Food", "lunch")
        db.delete_transaction(db.get_last_transaction()["id"])
        assert db.get_all_transactions() == []

    def test_recent_is_newest_first_and_limited(self, db):
        for day in range(1, 6):
            db.add_transaction(f"2026-03-0{day}", "expense", day, "Food", f"d{day}")
        recent = db.get_recent_transactions(limit=2)
        assert [t["description"] for t in recent] == ["d5", "d4"]


class TestMonthlySummary:
    def test_totals_and_breakdown(self, db):
        db.add_transaction("2026-03-01", "income", 1000, "Income", "pay")
        db.add_transaction("2026-03-05", "expense", 200, "Food", "groceries")
        db.add_transaction("2026-03-06", "expense", 50, "Food", "lunch")
        db.add_transaction("2026-03-31", "expense", 150, "Housing", "rent")
        db.add_transaction("2026-04-01", "expense", 999, "Housing", "next month")

        s = db.get_monthly_summary(2026, 3)
        assert s["total_income"] == 1000
        assert s["total_expenses"] == 400
        assert s["net_balance"] == 600
        assert s["savings_rate"] == pytest.approx(60.0)
        assert s["by_category"] == {"Food": 250, "Housing": 150}

    def test_december_boundary(self, db):
        db.add_transaction("2026-12-31", "expense", 10, "Food", "nye")
        db.add_transaction("2027-01-01", "expense", 99, "Food", "new year")
        assert db.get_monthly_summary(2026, 12)["total_expenses"] == 10

    def test_no_income_gives_zero_savings_rate(self, db):
        db.add_transaction("2026-03-01", "expense", 10, "Food", "x")
        assert db.get_monthly_summary(2026, 3)["savings_rate"] == 0

    def test_summaries_are_oldest_first(self, db):
        rows = db.get_monthly_summaries(3)
        today = date.today()
        assert len(rows) == 3
        assert (rows[-1]["year"], rows[-1]["month"]) == (today.year, today.month)


class TestProfileBudgetsCurrency:
    def test_profile_is_created_once(self, db):
        db.get_or_create_profile()
        db.update_profile(goals="save", onboarding_complete=1)
        p = db.get_or_create_profile()
        assert p["goals"] == "save"
        assert p["onboarding_complete"] == 1

    def test_budget_targets(self, db):
        db.set_budget_target("Food", 300)
        db.set_budget_target("Food", 400)
        db.set_budget_target("Health", 50)
        db.remove_budget_target("Health")
        assert db.get_budget_targets() == {"Food": 400}

    def test_default_currency(self, db):
        assert db.get_default_currency() == "USD"
        db.set_default_currency("KRW")
        assert db.get_default_currency() == "KRW"


class TestRecurring:
    def test_add_rejects_unknown_category(self, db):
        with pytest.raises(ValueError):
            db.add_recurring_transaction("expense", 10, "Crypto", "x", "monthly", "2026-03-01")

    def test_update_ignores_unknown_fields_and_categories(self, db):
        db.add_recurring_transaction("expense", 10, "Food", "meal kit", "weekly", "2026-03-01")
        rec_id = db.get_recurring_transactions()[0]["id"]
        db.update_recurring_transaction(rec_id, amount=20, category="Crypto", bogus=1)
        rec = db.get_recurring_transactions()[0]
        assert rec["amount"] == 20
        assert rec["category"] == "Food"

    def test_inactive_hidden_by_default(self, db):
        db.add_recurring_transaction("expense", 10, "Food", "x", "weekly", "2026-03-01")
        rec_id = db.get_recurring_transactions()[0]["id"]
        db.update_recurring_transaction(rec_id, active=0)
        assert db.get_recurring_transactions() == []
        assert len(db.get_recurring_transactions(active_only=False)) == 1

    def test_process_due_logs_and_advances(self, db):
        due = (date.today() - timedelta(days=1)).isoformat()
        later = (date.today() + timedelta(days=5)).isoformat()
        db.add_recurring_transaction("expense", 15, "Subscriptions", "music", "weekly", due, currency="GBP")
        db.add_recurring_transaction("expense", 99, "Housing", "rent", "monthly", later)

        assert db.process_due_recurring_transactions() == 1
        (txn,) = db.get_all_transactions()
        assert (txn["description"], txn["date"], txn["source"], txn["currency"]) == (
            "music", due, "recurring", "GBP",
        )
        music = next(r for r in db.get_recurring_transactions() if r["description"] == "music")
        assert music["next_due_date"] == db._advance_date(due, "weekly")

    def test_upcoming_window(self, db):
        soon = (date.today() + timedelta(days=3)).isoformat()
        far = (date.today() + timedelta(days=60)).isoformat()
        db.add_recurring_transaction("expense", 1, "Food", "soon", "weekly", soon)
        db.add_recurring_transaction("expense", 1, "Food", "far", "weekly", far)
        assert [r["description"] for r in db.get_upcoming_recurring(30)] == ["soon"]
