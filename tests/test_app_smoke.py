"""Render every page headlessly with Streamlit's AppTest.

The Anthropic client is replaced with a fake, so no API calls are made.
"""
import os
from datetime import date, timedelta

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture
def seeded(db, fake_ai):
    db.set_default_currency("EUR")
    month = date.today().strftime("%Y-%m")
    db.add_transaction(f"{month}-01", "income", 3000, "Income", "salary", currency="EUR")
    db.add_transaction(f"{month}-02", "expense", 420, "Food", "groceries", currency="EUR")
    db.add_transaction(f"{month}-03", "expense", 900, "Housing", "rent", currency="EUR")
    db.set_budget_target("Food", 300)
    db.add_recurring_transaction(
        "expense", 15, "Subscriptions", "music", "monthly",
        (date.today() + timedelta(days=5)).isoformat(), currency="EUR",
    )
    db.update_profile(onboarding_complete=1)
    return db


def run_page(page):
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["page"] = page
    at.run()
    assert not at.exception, at.exception
    return at


def all_markdown(at):
    return "\n".join(m.value for m in at.markdown)


def test_onboarding_shown_until_complete(db, fake_ai):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Welcome to Vados" in all_markdown(at)
    assert at.subheader[0].value == "Step 1: Your Financial Goals"


@pytest.mark.parametrize("page, title", [
    ("Dashboard", "Dashboard"),
    ("Trends", "Spending Trends"),
    ("Log / Chat", "Log / Chat"),
    ("Transaction History", "Transaction History"),
    ("Settings", "Settings"),
])
def test_every_page_renders(seeded, page, title):
    assert run_page(page).title[0].value == title


def test_sidebar_navigates_between_pages(seeded):
    at = run_page("Dashboard")
    at.button(key="nav_Trends").click().run()
    assert not at.exception
    assert at.title[0].value == "Spending Trends"
    assert at.button(key="nav_Trends").proto.type == "primary"


def test_dashboard_metrics_and_insight(seeded):
    at = run_page("Dashboard")
    assert [m.value for m in at.metric] == ["€3,000.00", "€1,320.00"]
    md = all_markdown(at)
    assert "€1,680.00" in md          # net balance card
    assert "Fake insight." in md       # AI insight card
    assert "music" in md               # upcoming recurring card


def test_dashboard_insight_failure_is_handled(seeded, fake_ai):
    fake_ai.error = RuntimeError("boom")
    at = run_page("Dashboard")
    assert "generate an insight right now" in all_markdown(at)


def test_trends_renders_all_three_charts(seeded):
    assert len(run_page("Trends").get("plotly_chart")) == 3


def test_history_lists_every_transaction(seeded):
    assert len(run_page("Transaction History").expander) == 3


def test_example_prompt_is_sent_once(seeded, fake_ai):
    fake_ai.text = "You spent €420 on food."
    at = run_page("Log / Chat")
    at.button(key="example_0").click().run()
    assert not at.exception
    roles = [m["role"] for m in at.session_state["chat_messages"]]
    assert roles == ["user", "assistant"]


def test_chat_api_error_is_reported(seeded, fake_ai):
    fake_ai.error = ValueError("bad")
    at = run_page("Log / Chat")
    at.chat_input[0].set_value("hello").run()
    assert not at.exception
    assert at.session_state["chat_messages"][-1]["content"].startswith("I couldn't process that")
